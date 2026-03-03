"""
╔══════════════════════════════════════════════════════════╗
║   WENDRINK — Обработка Z-отчёта (продажи за день)       ║
╠══════════════════════════════════════════════════════════╣
║  Режимы:                                                 ║
║    python zreport.py load  2026-02-09  sales.txt        ║
║    python zreport.py check 2026-02-09                   ║
║    python zreport.py delete 2026-02-09                  ║
╚══════════════════════════════════════════════════════════╝

Формат файла продаж (sales.txt):
    12    Тапиока    4.00    600.00
    31    Кытырлак   12.00   3600.00
    ...
"""
import sys
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "wendrink.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

# ── ПАРСИНГ ФАЙЛА ПРОДАЖ ─────────────────────────────────
def parse_sales_file(filepath):
    sales = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                pos_code = str(int(parts[0]))
                qty      = float(parts[-2])
                amount   = float(parts[-1])
                sales.append({"pos_code": pos_code, "qty": qty, "amount": amount})
            except (ValueError, IndexError):
                continue
    return sales

# ── ЗАГРУЗКА ПРОДАЖ ──────────────────────────────────────
def load_sales(date_str, filepath):
    sales_data = parse_sales_file(filepath)
    if not sales_data:
        print("❌ Файл пустой или неправильный формат!")
        return

    conn = get_conn()
    cur  = conn.cursor()

    # Проверяем — уже есть данные за этот день?
    existing = cur.execute(
        "SELECT COUNT(*) FROM inventory_ledger WHERE event_type='SALE' AND business_date=?",
        (date_str,)
    ).fetchone()[0]
    if existing > 0:
        print(f"⚠️  За {date_str} уже есть {existing} записей расхода!")
        print("   Сначала удали: python zreport.py delete", date_str)
        conn.close()
        return

    # Получаем продукты
    products = {str(r[0]): r[1] for r in cur.execute(
        "SELECT pos_code, id FROM products"
    ).fetchall()}

    # Получаем рецепты: product_id → [(ingredient_id, quantity)]
    recipes = {}
    for r in cur.execute("SELECT product_id, ingredient_id, quantity FROM recipes").fetchall():
        recipes.setdefault(r[0], []).append((r[1], float(r[2])))

    # Получаем WAC ингредиентов
    def get_wac(ing_id):
        row = cur.execute("""
            SELECT weighted_average_cost FROM inventory_ledger
            WHERE ingredient_id=? ORDER BY created_at DESC LIMIT 1
        """, (ing_id,)).fetchone()
        if row:
            return float(row[0])
        row2 = cur.execute(
            "SELECT initial_cost FROM ingredients WHERE id=?", (ing_id,)
        ).fetchone()
        return float(row2[0]) if row2 else 0.0

    now = datetime.now(timezone.utc).isoformat()
    total_amount = 0.0
    ok_products  = []
    no_recipe    = []
    not_found    = []
    consumption   = {}  # ingredient_id → total qty consumed
    sale_items_list = []  # для таблицы sale_items (категории)

    for sale in sales_data:
        pos_code = sale["pos_code"]
        qty      = sale["qty"]
        amount   = sale["amount"]

        prod_id = products.get(pos_code)
        if not prod_id:
            not_found.append(pos_code)
            continue

        recipe = recipes.get(prod_id, [])
        if not recipe:
            no_recipe.append(pos_code)
            continue

        for ing_id, ing_qty in recipe:
            total_consumed = ing_qty * qty
            consumption[ing_id] = consumption.get(ing_id, 0.0) + total_consumed

        total_amount += amount
        ok_products.append(pos_code)
        unit_price = round(amount / qty, 2) if qty else 0.0
        sale_items_list.append((prod_id, qty, unit_price, amount))

    # Записываем расход в inventory_ledger
    sale_group_id = str(uuid.uuid4()).replace("-", "")
    for ing_id, consumed in consumption.items():
        wac      = get_wac(ing_id)
        entry_id = str(uuid.uuid4()).replace("-", "")
        cur.execute("""
            INSERT INTO inventory_ledger
                (id, ingredient_id, event_type, event_id, change_amount,
                 unit_cost, weighted_average_cost, cost_snapshot,
                 negative_stock, reason, business_date, created_at)
            VALUES (?, ?, 'SALE', ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """, (
            entry_id, ing_id, sale_group_id,
            -consumed, wac, wac,
            round(consumed * wac, 2),
            f"Z-отчёт {date_str}",
            date_str, now
        ))

    # Вычисляем total_cost из записанных SALE событий
    total_cogs = sum(
        round(consumed * get_wac(ing_id), 2)
        for ing_id, consumed in consumption.items()
    )

    # Записываем в sales (итог дня)
    sale_id = str(uuid.uuid4()).replace("-", "")
    cur.execute("""
        INSERT INTO sales (id, total_amount, total_cost, business_date, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (sale_id, total_amount, total_cogs, date_str, now))

    # Записываем позиции в sale_items (для графика "Продажи по категориям")
    for prod_id, qty, unit_price, line_total in sale_items_list:
        item_id = str(uuid.uuid4()).replace("-", "")
        cur.execute("""
            INSERT INTO sale_items
                (id, sale_id, product_id, quantity, unit_price, line_total, total_cost, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, (item_id, sale_id, prod_id, qty, unit_price, line_total, now))

    conn.commit()

    print(f"\n{'='*55}")
    print(f"  Z-ОТЧЁТ {date_str} — ЗАГРУЖЕН")
    print(f"{'='*55}")
    print(f"  Продуктов обработано:  {len(ok_products)}")
    print(f"  Ингредиентов списано:  {len(consumption)}")
    print(f"  Сумма продаж:          {total_amount:,.0f}₸")
    if not_found:
        print(f"\n  ⚠️  Коды не найдены в БД: {', '.join(not_found)}")
    if no_recipe:
        print(f"  ⚠️  Нет рецепта для кодов: {', '.join(no_recipe)}")

    conn.close()
    print(f"\n  → Запусти: python zreport.py check {date_str}")

# ── ПРОВЕРКА ОСТАТКОВ ПОСЛЕ ДНЯ ──────────────────────────
def check_stock(date_str):
    conn = get_conn()
    cur  = conn.cursor()

    rows = cur.execute("""
        SELECT i.position_number, i.name, i.unit,
               COALESCE(SUM(l.change_amount), 0) as balance,
               MAX(l.weighted_average_cost) as wac
        FROM ingredients i
        LEFT JOIN inventory_ledger l ON l.ingredient_id = i.id
        GROUP BY i.id
        ORDER BY i.position_number
    """).fetchall()

    print(f"\n{'='*65}")
    print(f"  ОСТАТКИ ПОСЛЕ {date_str}")
    print(f"{'='*65}")
    print(f"{'Поз':>4} {'Название':<35} {'Остаток':>10} {'Ед':>4}")
    print("-" * 65)

    negatives = 0
    for r in rows:
        pos, name, unit, balance, wac = r
        balance = round(float(balance), 1)
        marker = " ❌" if balance < 0 else ""
        if balance < 0:
            negatives += 1
        print(f"{pos:>4} {name[:35]:<35} {balance:>10.0f} {unit:>4}{marker}")

    conn.close()
    print("-" * 65)
    if negatives:
        print(f"  ⚠️  Отрицательных остатков: {negatives}")
    else:
        print("  ✅ Все остатки положительные!")

# ── УДАЛЕНИЕ ДНЯ ────────────────────────────────────────
def delete_day(date_str):
    conn = get_conn()
    cur  = conn.cursor()

    sale_rows = cur.execute(
        "DELETE FROM inventory_ledger WHERE event_type='SALE' AND business_date=?",
        (date_str,)
    ).rowcount

    sales_rows = cur.execute(
        "DELETE FROM sales WHERE business_date=?",
        (date_str,)
    ).rowcount

    conn.commit()
    conn.close()

    print(f"\n✅ День {date_str} удалён:")
    print(f"   Записей расхода удалено: {sale_rows}")
    print(f"   Записей продаж удалено:  {sales_rows}")

# ── ГЛАВНЫЙ БЛОК ─────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    mode     = sys.argv[1].lower()
    date_str = sys.argv[2]

    if mode == "load":
        if len(sys.argv) < 4:
            print("Укажи файл: python zreport.py load 2026-02-09 sales.txt")
            sys.exit(1)
        load_sales(date_str, sys.argv[3])

    elif mode == "check":
        check_stock(date_str)

    elif mode == "delete":
        delete_day(date_str)

    else:
        print("Неизвестный режим. Используй: load / check / delete")
