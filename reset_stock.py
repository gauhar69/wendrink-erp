"""
Очистка склада и загрузка новых остатков из 'склад .xlsx'
Запуск: venv\Scripts\python.exe reset_stock.py
"""
import sqlite3
import uuid
import openpyxl
from datetime import datetime, timezone

DB_PATH    = "wendrink.db"
SKLAD_XLSX = "склад .xlsx"
BUSINESS_DATE = "2026-03-02"

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

# ШАГ 1: Очистка
print("Очищаю inventory_ledger...")
cur.execute("DELETE FROM inventory_ledger")
deleted = cur.rowcount
print(f"Удалено: {deleted} записей")

# ШАГ 2: Загрузка ингредиентов из БД
ing_map = {r[0]: (r[1], r[2]) for r in cur.execute("SELECT name, id, unit FROM ingredients").fetchall()}

# ШАГ 3: Читаем Excel
wb = openpyxl.load_workbook(SKLAD_XLSX, data_only=True)
ws = wb.active

now = datetime.now(timezone.utc).isoformat()
loaded = 0
errors = []

print("\nЗагружаю новые остатки...")
for row in ws.iter_rows(values_only=True):
    if not row[0] or str(row[0]).strip() == "№":
        continue

    name     = str(row[1]).strip()
    wac      = float(row[2]) if row[2] else 0.0
    quantity = float(row[3]) if row[3] else 0.0

    if name not in ing_map:
        errors.append(name)
        continue

    ing_id, unit = ing_map[name]
    ledger_id = str(uuid.uuid4()).replace("-", "")

    cur.execute("""
        INSERT INTO inventory_ledger
            (id, ingredient_id, event_type, change_amount, unit_cost, weighted_average_cost, cost_snapshot, negative_stock, business_date, created_at)
        VALUES (?, ?, 'RECEIPT', ?, ?, ?, ?, 0, ?, ?)
    """, (ledger_id, ing_id, quantity, wac, wac, wac * quantity, BUSINESS_DATE, now))

    loaded += 1

conn.commit()
conn.close()

print(f"\n=== РЕЗУЛЬТАТ ===")
print(f"Загружено: {loaded} позиций")
if errors:
    print(f"Не найдено в БД ({len(errors)}):")
    for e in errors:
        print(f"  ❌ {e}")
else:
    print("Ошибок: 0")
print("ГОТОВО")
