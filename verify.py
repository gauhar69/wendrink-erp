#!/usr/bin/env python3
"""
WENDRINK ERP - Скрипт верификации
Запускай ПОСЛЕ каждого изменения кода!

Использование:
    python verify.py              # Проверка кода (без сервера)
    python verify.py --live       # Проверка работающего сервера (localhost:8000)
    python verify.py --db         # Проверка целостности базы данных
    python verify.py --all        # Всё вместе
"""

import sys
import os
import sqlite3
import importlib
import ast
from pathlib import Path
from decimal import Decimal

# Цвета для консоли
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

passed = 0
failed = 0
warnings = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  {GREEN}✅ {msg}{RESET}")


def fail(msg):
    global failed
    failed += 1
    print(f"  {RED}❌ {msg}{RESET}")


def warn(msg):
    global warnings
    warnings += 1
    print(f"  {YELLOW}⚠️  {msg}{RESET}")


# ============================================================
# 1. ПРОВЕРКА СТРУКТУРЫ ФАЙЛОВ
# ============================================================
def check_file_structure():
    print(f"\n{BOLD}📁 Проверка структуры файлов:{RESET}")

    required_files = [
        "app/main.py",
        "app/api/router.py",
        "app/api/finance.py",
        "app/api/reports.py",
        "app/api/sales.py",
        "app/api/recipes.py",
        "app/api/inventory.py",
        "app/api/ingredients.py",
        "app/api/products.py",
        "app/api/analytics.py",
        "app/api/charts.py",
        "app/templates/dashboard.html",
        "app/services/inventory.py",
        "app/models/product.py",
        "app/models/ingredient.py",
        "app/models/recipe.py",
        "app/schemas/recipe.py",
        "requirements.txt",
        "CLAUDE.md",
        "SPEC.md",
    ]

    for f in required_files:
        if Path(f).exists():
            ok(f"Файл {f} существует")
        else:
            fail(f"Файл {f} НЕ НАЙДЕН!")


# ============================================================
# 2. ПРОВЕРКА СИНТАКСИСА PYTHON
# ============================================================
def check_python_syntax():
    print(f"\n{BOLD}🐍 Проверка синтаксиса Python:{RESET}")

    py_files = list(Path("app").rglob("*.py"))

    for f in py_files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                source = fh.read()
            ast.parse(source)
            ok(f"{f} - синтаксис OK")
        except SyntaxError as e:
            fail(f"{f} - СИНТАКСИЧЕСКАЯ ОШИБКА: {e}")


# ============================================================
# 3. ПРОВЕРКА ИМПОРТОВ
# ============================================================
def check_imports():
    print(f"\n{BOLD}📦 Проверка критических импортов:{RESET}")

    critical_modules = [
        "fastapi",
        "sqlalchemy",
        "pydantic",
        "jinja2",
    ]

    for mod in critical_modules:
        try:
            importlib.import_module(mod)
            ok(f"Модуль {mod} доступен")
        except ImportError:
            fail(f"Модуль {mod} НЕ УСТАНОВЛЕН!")


# ============================================================
# 4. ПРОВЕРКА БАЗЫ ДАННЫХ
# ============================================================
def check_database():
    print(f"\n{BOLD}🗄️  Проверка базы данных:{RESET}")

    db_path = "wendrink.db"

    if not Path(db_path).exists():
        fail("wendrink.db не найдена!")
        return

    ok("wendrink.db существует")

    # Проверка journal lock
    if Path(f"{db_path}-journal").exists():
        fail("wendrink.db-journal существует! База заблокирована! Перезапустите сервер.")
    else:
        ok("Нет journal lock файла")

    # Проверка таблиц
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        required_tables = [
            "products", "ingredients", "recipes", "sales", "sale_items",
            "inventory_ledger", "finance_ledger", "fixed_cost_settings",
        ]

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        for table in required_tables:
            if table in existing_tables:
                # Подсчёт записей
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                ok(f"Таблица {table}: {count} записей")
            else:
                fail(f"Таблица {table} НЕ НАЙДЕНА!")

        # Проверка целостности рецептов
        cursor.execute("""
            SELECT COUNT(*) FROM recipes r
            LEFT JOIN products p ON r.product_id = p.id
            WHERE p.id IS NULL
        """)
        orphan_recipes = cursor.fetchone()[0]
        if orphan_recipes > 0:
            fail(f"Найдено {orphan_recipes} рецептов без продуктов!")
        else:
            ok("Все рецепты связаны с продуктами")

        # Проверка целостности рецептов → ингредиенты
        cursor.execute("""
            SELECT COUNT(*) FROM recipes r
            LEFT JOIN ingredients i ON r.ingredient_id = i.id
            WHERE i.id IS NULL
        """)
        orphan_ingredients = cursor.fetchone()[0]
        if orphan_ingredients > 0:
            fail(f"Найдено {orphan_ingredients} рецептов с несуществующими ингредиентами!")
        else:
            ok("Все рецепты связаны с ингредиентами")

        conn.close()

    except Exception as e:
        fail(f"Ошибка при проверке БД: {e}")


# ============================================================
# 5. ПРОВЕРКА DASHBOARD HTML
# ============================================================
def check_dashboard():
    print(f"\n{BOLD}🖥️  Проверка dashboard.html:{RESET}")

    html_path = Path("app/templates/dashboard.html")
    if not html_path.exists():
        fail("dashboard.html не найден!")
        return

    content = html_path.read_text(encoding="utf-8")

    # Проверка обязательных секций
    required_sections = [
        ("dashboard-section", "Dashboard"),
        ("analytics-section", "Аналитика"),
        ("cogs-variance-section", "Проверка COGS"),
        ("daily-input-section", "Финансы (Ввод данных)"),
        ("warehouse-section", "Склад"),
        ("recipes-section", "Рецепты"),
        ("sales-section", "Продажи"),
    ]

    for section_id, name in required_sections:
        if section_id in content:
            ok(f"Секция '{name}' ({section_id}) найдена")
        else:
            fail(f"Секция '{name}' ({section_id}) НЕ НАЙДЕНА!")

    # Проверка на известные проблемы
    if "try { console.error" in content and "catch" in content:
        warn("Возможно есть молчаливые catch блоки - проверьте обработку ошибок")

    # Проверка размера файла
    size_kb = len(content) / 1024
    if size_kb > 500:
        warn(f"dashboard.html слишком большой: {size_kb:.0f}KB - рассмотрите разделение")
    else:
        ok(f"dashboard.html размер: {size_kb:.0f}KB")


# ============================================================
# 6. ПРОВЕРКА REQUIREMENTS.TXT
# ============================================================
def check_requirements():
    print(f"\n{BOLD}📋 Проверка requirements.txt:{RESET}")

    req_path = Path("requirements.txt")
    if not req_path.exists():
        fail("requirements.txt не найден!")
        return

    content = req_path.read_text(encoding="utf-8")

    required_packages = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "aiosqlite",
        "pydantic",
        "jinja2",
    ]

    for pkg in required_packages:
        if pkg in content.lower():
            ok(f"Пакет {pkg} в requirements.txt")
        else:
            fail(f"Пакет {pkg} ОТСУТСТВУЕТ в requirements.txt!")

    # Проверка на мусор
    suspicious = ["openpyxl", "pandas", "numpy", "tensorflow"]
    for pkg in suspicious:
        if pkg in content.lower():
            warn(f"Подозрительный пакет {pkg} в requirements.txt - возможно добавлен случайно")


# ============================================================
# 7. ПРОВЕРКА ЖИВОГО СЕРВЕРА (--live)
# ============================================================
def check_live_server():
    print(f"\n{BOLD}🌐 Проверка работающего сервера:{RESET}")

    try:
        import urllib.request
        import json

        base = "http://localhost:8000"

        # Health check
        try:
            resp = urllib.request.urlopen(f"{base}/health", timeout=5)
            ok("GET /health - 200 OK")
        except Exception as e:
            fail(f"GET /health - ОШИБКА: {e}")
            return

        # Dashboard
        try:
            resp = urllib.request.urlopen(f"{base}/", timeout=5)
            if resp.status == 200:
                ok("GET / (Dashboard) - 200 OK")
            else:
                fail(f"GET / - статус {resp.status}")
        except Exception as e:
            fail(f"GET / - ОШИБКА: {e}")

        # API endpoints
        api_endpoints = [
            "/api/products?limit=1",
            "/api/ingredients?limit=1",
            "/api/recipes?limit=1",
            "/api/inventory/balance",
        ]

        for endpoint in api_endpoints:
            try:
                resp = urllib.request.urlopen(f"{base}{endpoint}", timeout=5)
                if resp.status == 200:
                    ok(f"GET {endpoint} - 200 OK")
                else:
                    fail(f"GET {endpoint} - статус {resp.status}")
            except Exception as e:
                fail(f"GET {endpoint} - ОШИБКА: {e}")

    except ImportError:
        fail("urllib не доступен")


# ============================================================
# MAIN
# ============================================================
def main():
    print(f"\n{BOLD}{'='*60}")
    print(f"  WENDRINK ERP - ВЕРИФИКАЦИЯ")
    print(f"{'='*60}{RESET}")

    args = sys.argv[1:]

    # Всегда проверяем код
    check_file_structure()
    check_python_syntax()
    check_requirements()
    check_dashboard()

    if "--db" in args or "--all" in args:
        check_database()

    if "--live" in args or "--all" in args:
        check_live_server()

    if not args:
        check_imports()
        check_database()

    # Итог
    print(f"\n{BOLD}{'='*60}")
    total = passed + failed
    if failed == 0:
        print(f"  {GREEN}✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! ({passed}/{total}){RESET}")
    else:
        print(f"  {RED}❌ НАЙДЕНЫ ПРОБЛЕМЫ: {failed} ошибок из {total} проверок{RESET}")
    if warnings > 0:
        print(f"  {YELLOW}⚠️  Предупреждений: {warnings}{RESET}")
    print(f"{'='*60}\n")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
