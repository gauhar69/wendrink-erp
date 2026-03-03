"""
Инвентаризация — загружает реальные остатки в БД.
Создаёт STOCKTAKE_ADJUSTMENT записи для каждого ингредиента.
Дата: 2026-02-23
"""
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH       = "wendrink.db"
BUSINESS_DATE = "2026-02-23"

# Реальные остатки (позиция: кол-во)
ACTUAL_STOCK = {
    1:  144000,  # Ориг. порошок мороженое
    2:  144000,  # Шоколадное мороженое
    3:   48000,  # Компаньон для чая с молоком
    4:   20000,  # Латте (порошок)
    5:   20000,  # Пудинговый порошок
    6:  100000,  # Черная Жемчужина (тапиоковые шарики)
    7:  110000,  # Нектар (Сироп)
    8:  125000,  # Фруктоза
    9:   20800,  # Апельсиновый сок
    10:  20800,  # Виноградный соус
    11:  48000,  # Маракуйя сироп
    12: 100000,  # Кокос
    13:  20800,  # Малиновый сок
    14:  24000,  # Клубничное варенье
    15:  43200,  # Шоколадный соус
    16:  10200,  # Частицы грейпфрута
    17:  32400,  # Консервированная красная фасоль
    18:  28800,  # Варенье из розовых персиков
    19:  20000,  # Порошок нектара тополя
    20:  28800,  # Гранулированный джем из Манго
    21:  20000,  # Персиковое желе
    22:  24000,  # Прохладный ветерок (жасминовый чай)
    23:  30600,  # Консервированый виноград
    24:  36000,  # Черный чай Мэйжан
    25:  21600,  # Сироп из коричневого сахара
    26:  24000,  # Черничная мякоть
    27:   6400,  # Рожок (Вафельный)
    28:   5000,  # Стакан пластиковый 0.5
    29:   4000,  # Стакан пластиковый 0.7
    30:    400,  # Тонна тонна бочка (новая)
    31:   2000,  # U-образная чашка
    32:  12000,  # Соломинки из бумажной пленки
    33:  10000,  # Трубочки из бумажной пленки
    34:   4000,  # Сферическая крышка (90)
    35:   4000,  # КОВШ
    36:    100,  # специальная ложка
    37:  12200,  # уплотнительная пленка
    38:  20000,  # Сумка на 1 чашку
    39:  10000,  # Сумка на 2 чашки
    40:   6000,  # Сумка на 4 чашки
    41:   1000,  # Бумажный стакан (Полый)
    42:   1000,  # 90 литая герметичная крышка
    43:   1000,  # PET Стаканы для кофе
    44:   1000,  # Крышки для стаканов
    45:  36000,  # кокосовое молоко
    46:  10000,  # Кофе в зернах
    47:  12000,  # Смесь Гонконг. вафли
    48:  40000,  # Желе шарики (Кристалл)
    49:   3365,  # Апельсины свежие
    50:   3794,  # Лимоны свежие
    51:   4000,  # Орео (Весовое)
    52:     30,  # Яйца
    53:   2000,  # Растительное масло
    54:  20000,  # Капучино
    55:  24000,  # порошок для мороженного матча
}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Получаем все ингредиенты
ingredients = {
    r[0]: {"id": r[1], "name": r[2], "wac": r[3]}
    for r in cur.execute("""
        SELECT i.position_number, i.id, i.name, i.initial_cost
        FROM ingredients i
    """).fetchall()
}

# Получаем текущий баланс из ledger
def get_current_balance(ing_id):
    row = cur.execute("""
        SELECT COALESCE(SUM(change_amount), 0)
        FROM inventory_ledger
        WHERE ingredient_id = ?
    """, (ing_id,)).fetchone()
    return float(row[0]) if row else 0.0

print("=" * 60)
print(f"  ИНВЕНТАРИЗАЦИЯ — {BUSINESS_DATE}")
print("=" * 60)

now = datetime.now(timezone.utc).isoformat()
adjusted = 0
skipped  = 0

for pos, actual in ACTUAL_STOCK.items():
    ing = ingredients.get(pos)
    if not ing:
        print(f"  ⚠️  Позиция {pos}: не найдена в БД — пропуск")
        skipped += 1
        continue

    current_balance = get_current_balance(ing["id"])
    diff = actual - current_balance

    if abs(diff) < 0.01:
        continue  # Совпадает — не трогаем

    # Получаем последний WAC
    last_wac = cur.execute("""
        SELECT weighted_average_cost FROM inventory_ledger
        WHERE ingredient_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, (ing["id"],)).fetchone()
    wac = float(last_wac[0]) if last_wac else float(ing["wac"] or 0)

    entry_id    = str(uuid.uuid4()).replace("-", "")
    cost_snap   = round(diff * wac, 2)
    new_balance = actual

    cur.execute("""
        INSERT INTO inventory_ledger
            (id, ingredient_id, event_type, event_id, change_amount,
             unit_cost, weighted_average_cost, cost_snapshot,
             negative_stock, reason, business_date, created_at)
        VALUES (?, ?, 'STOCKTAKE_ADJUSTMENT', ?, ?, ?, ?, ?, 0,
                'Инвентаризация 23.02.2026', ?, ?)
    """, (
        entry_id, ing["id"], entry_id,
        diff, wac, wac, cost_snap,
        BUSINESS_DATE, now
    ))

    direction = "▲" if diff > 0 else "▼"
    print(f"  {direction} [{pos:>2}] {ing['name'][:35]:<35} "
          f"{current_balance:>8.0f} → {actual:>8.0f}  ({diff:+.0f})")
    adjusted += 1

conn.commit()
conn.close()

print("\n" + "=" * 60)
print(f"  Скорректировано: {adjusted} ингредиентов")
print(f"  Пропущено:       {skipped}")
print("  ✓ Обнови страницу в браузере!")
print("=" * 60)
