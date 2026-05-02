#!/usr/bin/env python3
"""
⚠️ DANGER: ЭТОТ СКРИПТ ИЗМЕНЯЕТ ПРОДАКШН ДАННЫЕ ⚠️
Запускать только с предварительным бэкапом БД.
"""
"""
Полное удаление всех данных за указанную дату:
  - SALE записи из inventory_ledger
  - sales таблица
  - finance_ledger (зарплата + фикс. расходы)

Использование: python delete_day.py 2026-02-09
"""
import sqlite3, sys

date_str = sys.argv[1] if len(sys.argv) > 1 else "2026-02-09"
conn = sqlite3.connect("wendrink.db")
cur = conn.cursor()

print(f"Удаление всех данных за {date_str}...")

# 1. SALE из inventory_ledger
n1 = cur.execute(
    "DELETE FROM inventory_ledger WHERE event_type='SALE' AND business_date=?", (date_str,)
).rowcount

# 2. sales
n2 = cur.execute("DELETE FROM sales WHERE business_date=?", (date_str,)).rowcount

# 3. finance_ledger (зарплата, фикс. расходы)
n3 = cur.execute("DELETE FROM finance_ledger WHERE business_date=?", (date_str,)).rowcount

conn.commit()
conn.close()

print(f"  inventory_ledger SALE: {n1} удалено")
print(f"  sales:                 {n2} удалено")
print(f"  finance_ledger:        {n3} удалено")
print(f"✅ День {date_str} полностью очищен!")
