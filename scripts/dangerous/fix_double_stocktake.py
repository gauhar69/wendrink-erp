#!/usr/bin/env python3
"""
⚠️ DANGER: ЭТОТ СКРИПТ ИЗМЕНЯЕТ ПРОДАКШН ДАННЫЕ ⚠️
Запускать только с предварительным бэкапом БД.
"""
"""
Исправление двойного применения инвентаризации от 09.04.2026
Первое применение: 19:07:32 (правильное - оставляем)
Второе применение: 19:07:35 (дубликат - удаляем)
"""
import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = '/home/ubuntu/wendrink-erp/wendrink.db'
BACKUP_PATH = f'/home/ubuntu/wendrink-erp/wendrink_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'

# Шаг 1: Бэкап
print(f'Создаю бэкап: {BACKUP_PATH}')
shutil.copy2(DB_PATH, BACKUP_PATH)
print('Бэкап создан.')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Шаг 2: Считаем дубликаты которые удалим
cur.execute("""
    SELECT COUNT(*), SUM(ABS(change_amount))
    FROM inventory_ledger
    WHERE event_type='ADJUSTMENT'
    AND created_at >= '2026-04-09 19:07:35'
    AND created_at < '2026-04-09 19:07:36'
""")
count, total = cur.fetchone()
print(f'\nНайдено дубликатов для удаления: {count} записей')

# Шаг 3: Показываем что удалим
print('\nЗаписи которые будут удалены (дубликаты):')
cur.execute("""
    SELECT il.created_at, il.change_amount, i.name
    FROM inventory_ledger il
    JOIN ingredients i ON il.ingredient_id = i.id
    WHERE il.event_type='ADJUSTMENT'
    AND il.created_at >= '2026-04-09 19:07:35'
    AND il.created_at < '2026-04-09 19:07:36'
    ORDER BY il.created_at
""")
for r in cur.fetchall():
    print(f'  {r[0]} | {r[1]:>10.1f} | {r[2]}')

# Шаг 4: Удаляем дубликаты
cur.execute("""
    DELETE FROM inventory_ledger
    WHERE event_type='ADJUSTMENT'
    AND created_at >= '2026-04-09 19:07:35'
    AND created_at < '2026-04-09 19:07:36'
""")
deleted = cur.rowcount
conn.commit()

print(f'\nУдалено {deleted} дублирующих записей.')

# Шаг 5: Проверка результата для мороженого
print('\n=== ПРОВЕРКА: текущие остатки мороженого ===')
cur.execute("""
    SELECT i.name, SUM(il.change_amount) as total_change
    FROM inventory_ledger il
    JOIN ingredients i ON il.ingredient_id = i.id
    WHERE i.name LIKE '%мороженое%' OR i.name LIKE '%мороженного%'
    GROUP BY i.id, i.name
""")
for r in cur.fetchall():
    print(f'  {r[0]}: суммарное изменение = {r[1]}')

conn.close()
print('\nГотово! Двойное применение исправлено.')
print(f'Бэкап сохранён в: {BACKUP_PATH}')
