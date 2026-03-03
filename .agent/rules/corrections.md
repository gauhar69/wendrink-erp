---
trigger: always_on
---

# CORRECTIONS RULE (IMMUTABLE HISTORY)

Ошибка? Не UPDATE! Пиши CORRECTION event!

## ПРИНЦИП

History is sacred. Никогда не трогай прошлое.

Ошибка при вводе данных → пиши компенсирующий event

НЕПРАВИЛЬНО: UPDATE ledger SET change_amount = ... WHERE id = 5
ПРАВИЛЬНО: INSERT INTO ledger (event_type = 'CORRECTION', ...)

## СЦЕНАРИЙ 1: НЕПРАВИЛЬНО ВВЁЛ РАСХОД

Было записано:
- молоко: -50 гр (вместо -30 гр)

Исправление:
INSERT INTO inventory_ledger (
  ingredient_id = молоко,
  change_amount = +20 гр,
  event_type = 'CORRECTION',
  cost_snapshot = последний_известный,
  business_date = 2026-01-27,
  original_event_id = (id неправильной записи)
)

Результат:
-50 + 20 = -30 ✅ Правильно!

## СЦЕНАРИЙ 2: НЕПРАВИЛЬНАЯ ЦЕНА ЗАКУПКИ

Было записано:
- Ингредиент с cost_snapshot = 100

Реальная цена = 120

Исправление:
INSERT INTO inventory_ledger (
  ingredient_id = ...,
  change_amount = 0,
  event_type = 'CORRECTION',
  cost_snapshot = 120,
  business_date = 2026-01-27,
  memo = 'Corrected unit cost from 100 to 120'
)

## СТРУКТУРА CORRECTION EVENT

InventoryLedger таблица содержит для corrections:

id - primary key
ingredient_id - на какой ингредиент исправление
change_amount - может быть 0 для коррекции цены
event_type - 'CORRECTION'
original_event_id - ссылка на неправильный event (если есть)
correction_reason - почему исправили
cost_snapshot - цена на момент
business_date - дата исправления
created_at - когда сделано исправление

## ENDPOINT: POST /correction

Создаёт CORRECTION event в inventory_ledger.

Примеры:
1. Исправление количества:
   change_amount = -20 (компенсация)
   cost_snapshot = последний_известный

2. Исправление цены:
   change_amount = 0 (не меняем кол-во)
   cost_snapshot = новая_цена

## ПРИМЕР: ПОЛНЫЙ WORKFLOW

День 1, 10:00 → Продали кофе
INSERT INTO inventory_ledger (
  ingredient_id='coffee',
  change_amount=-30,
  event_type='SALE',
  cost_snapshot=500.00,
  business_date='2026-01-27'
)
→ остаток кофе = SUM() = -30

День 1, 14:00 → Обнаружили ошибку (не было -30, было -20)
INSERT INTO inventory_ledger (
  ingredient_id='coffee',
  change_amount=+10,
  event_type='CORRECTION',
  original_event_id='sale_123',
  cost_snapshot=500.00,
  correction_reason='Wrong quantity recorded in sale #123',
  business_date='2026-01-27'
)
→ остаток кофе = SUM() = -30 + 10 = -20 ✅ Правильно!

История остаётся:
2026-01-27 10:00 | SALE | -30 | coffee | (id=abc)
2026-01-27 14:00 | CORRECTION | +10 | coffee | (original_event_id=abc)

Оба события видны! История священна! Но баланс правильный!

## ПРАВИЛА CORRECTION

1. Никогда не UPDATE исходный event
2. Пиши INSERT с event_type = 'CORRECTION'
3. Ссылайся на оригинал через original_event_id
4. Объясняй причину в correction_reason
5. Ответственность - добавь user_id (потом)
6. Дата не меняется - correction пишется на ту же business_date

## ЧАСТЫЕ ОШИБКИ

ПЛОХО: Удаляешь неправильную запись
session.delete(wrong_ledger_entry)

ХОРОШО: Пишешь компенсирующий event
correction = InventoryLedger(
  change_amount=-wrong_ledger_entry.change_amount,
  event_type='CORRECTION',
  original_event_id=wrong_ledger_entry.id
)

ПЛОХО: Исправляешь старый event напрямую
old_event.cost_snapshot = 200.00

ХОРОШО: Пишешь новый event
correction = InventoryLedger(
  change_amount=0,
  cost_snapshot=200.00,
  event_type='CORRECTION',
  original_event_id=old_event.id
)

## ИТОГ

Correction = единственный способ исправления. История никогда не стирается.

Это не удобство. Это финансовая безопасность.