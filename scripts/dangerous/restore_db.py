#!/usr/bin/env python3
"""
⚠️ DANGER: ЭТОТ СКРИПТ ИЗМЕНЯЕТ ПРОДАКШН ДАННЫЕ ⚠️
Запускать только с предварительным бэкапом БД.
"""
"""
Полное восстановление данных склада на состояние 8 февраля
После того как Gemini испортил inventory_ledger
"""
import sqlite3, uuid, os
from datetime import datetime, timezone
import openpyxl

DB_PATH = "wendrink.db"
EXCEL_PATH = "initial_stock_09_02_2026.xlsx"
BUSINESS_DATE = "2026-02-08"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=" * 55)
print("  ВОССТАНОВЛЕНИЕ ДАННЫХ СКЛАДА")
print("=" * 55)

# ШАГ 1: Удаляем все записи inventory_ledger (все испорчены)
deleted = cur.execute("DELETE FROM inventory_ledger").rowcount
print(f"\n✅ Удалено записей inventory_ledger: {deleted}")

# ШАГ 2: Очищаем таблицу sales
deleted_sales = cur.execute("DELETE FROM sales").rowcount
print(f"✅ Удалено записей sales: {deleted_sales}")

conn.commit()

# ШАГ 3: Читаем Excel и создаём правильные RECEIPT записи
wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
ws = wb.active

now = datetime.now(timezone.utc).isoformat()
loaded = 0
skipped = 0

print(f"\nЗагружаем остатки из {EXCEL_PATH}...")

for row in ws.iter_rows(min_row=2, values_only=True):
    if not row[0]:
        continue

    pos_num = row[0]
    sebest  = row[6]   # Себест (колонка G)
    ostatok = row[7]   # ОСТАТОК (колонка H)

    if not sebest or not ostatok or float(ostatok) <= 0:
        skipped += 1
        continue

    sebest  = float(sebest)
    ostatok = float(ostatok)

    # Ищем ингредиент по position_number
    ing = cur.execute(
        "SELECT id FROM ingredients WHERE position_number=?", (pos_num,)
    ).fetchone()

    if not ing:
        skipped += 1
        continue

    ing_id     = ing[0]
    entry_id   = str(uuid.uuid4()).replace("-", "")
    total_cost = round(ostatok * sebest, 2)

    # Исправление поз.36 - специальная ложка
    if pos_num == 36:
        ostatok = 2405.0
        total_cost = round(2405.0 * sebest, 2)
        print(f"  ⚙️  Поз.36 (ложка): исправлено на 2405 шт")

    cur.execute("""
        INSERT INTO inventory_ledger
            (id, ingredient_id, event_type,
             change_amount, unit_cost, weighted_average_cost,
             cost_snapshot, negative_stock,
             reason, business_date, created_at)
        VALUES (?, ?, 'RECEIPT',
                ?, ?, ?,
                ?, 0,
                'Начальный остаток 08.02.2026 (ОСТАТОК)', ?, ?)
    """, (
        entry_id, ing_id,
        ostatok, sebest, sebest,
        total_cost,
        BUSINESS_DATE, now
    ))
    loaded += 1

conn.commit()
print(f"\n✅ Загружено RECEIPT записей: {loaded}")
print(f"   Пропущено: {skipped}")

# ШАГ 4: Исправляем WAC для поз. 29, 30 (были перепутаны)
fixes = {
    29: 27.3,    # Стакан 0.7 — правильная цена
    30: 109.2,   # Тонна тонна — правильная цена
}

for pos, correct_wac in fixes.items():
    ing = cur.execute(
        "SELECT id, name FROM ingredients WHERE position_number=?", (pos,)
    ).fetchone()
    if ing:
        cur.execute("""
            UPDATE inventory_ledger
            SET unit_cost=?, weighted_average_cost=?, cost_snapshot=change_amount*?
            WHERE ingredient_id=? AND event_type='RECEIPT'
        """, (correct_wac, correct_wac, correct_wac, ing[0]))
        print(f"✅ WAC поз.{pos} ({ing[1][:25]}): → {correct_wac}₸")

conn.commit()

# ШАГ 5: Проверка
total = cur.execute("SELECT COUNT(*) FROM inventory_ledger").fetchone()[0]
neg = cur.execute("""
    SELECT COUNT(*) FROM ingredients i
    WHERE (SELECT COALESCE(SUM(change_amount),0)
           FROM inventory_ledger WHERE ingredient_id=i.id) < 0
""").fetchone()[0]

print(f"\n{'='*55}")
print(f"  ИТОГ:")
print(f"  Записей в inventory_ledger: {total}")
print(f"  Отрицательных остатков:     {neg}")
print(f"  Дата начального склада:     {BUSINESS_DATE}")
print(f"{'='*55}")
print("\n✅ База восстановлена! Можешь запустить сервер.")

conn.close()
