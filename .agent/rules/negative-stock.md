---
trigger: always_on
---

# NEGATIVE STOCK RULE (ALLOW BUT FLAG)

Сырья нет, но продаём всё равно. Это бизнес-логика, не ошибка.

## ПРИНЦИП

Когда закончилось молоко, мы заказываем новое. А клиент ждёт.

Остаток молока: 100 гр
Клиент хочет: 150 гр напиток (требует 120 гр молока)
Что делаем?

ПЛОХО: "Простите, молока нет! Приходите завтра!"
ХОРОШО: Продаём напиток сегодня, молоко придёт завтра.

Остаток молока: 100 - 120 = -20 гр (в долгу)

Логика:
1. Продажа НЕ блокируется (даже если stock < 0)
2. Записываем в ledger отрицательное количество
3. Ставим флаг negative_stock_warning = true
4. UI показывает красный alert
5. Когда молоко приходит → становится положительным

## СТРУКТУРА

inventory_ledger таблица содержит:
- id (UUID primary key)
- ingredient_id (UUID)
- change_amount (Decimal) - может быть ОТРИЦАТЕЛЬНЫМ!
- event_type (String) - SUPPLY, SALE, CORRECTION
- cost_snapshot (Decimal)
- business_date (Date)
- negative_stock_warning (Boolean) - true если текущий остаток < 0 после этого события

## ЛОГИКА: SALE С NEGATIVE STOCK

Продажа напитка (с возможностью отрицательного stock):

Шаги:
1. Найди продукт и ACTIVE рецепт
2. Если рецепт или ингредиент отсутствует → ошибка
3. Создай sales запись
4. Для каждого ингредиента в рецепте:
   - Узнай ТЕКУЩИЙ остаток ДО продажи
   - Вычисли новый остаток ПОСЛЕ продажи
   - Определи нужно ли ставить warning (новый остаток < 0?)
   - Пиши в ledger (даже если становится отрицательным!)
   - Ставь negative_stock_warning = true если нужно

## ПРИМЕР

День 1, утро:
Молоко в запасе: 500 гр

День 1, 10:00 AM:
Продали 3 капучино × 150 гр = 450 гр молока
→ Остаток: 500 - 450 = 50 гр ✅ OK

День 1, 3:00 PM:
Продали 5 капучино × 150 гр = 750 гр молока
→ Остаток: 50 - 750 = -700 гр ⚠️ NEGATIVE!

INSERT INTO inventory_ledger (
  ingredient_id='milk',
  change_amount=-750,
  event_type='SALE',
  negative_stock_warning=TRUE,
  cost_snapshot=40.00
)

UI показывает: ⚠️ МОЛОКО В ДОЛГУ! -700 гр

День 1, 6:00 PM:
Приехала поставка молока: +1000 гр
→ Остаток: -700 + 1000 = 300 гр ✅ OK

INSERT INTO inventory_ledger (
  ingredient_id='milk',
  change_amount=+1000,
  event_type='SUPPLY',
  cost_snapshot=40.00
)

UI показывает: ✅ МОЛОКО OK 300 гр

## COST SNAPSHOT ПРИ NEGATIVE STOCK

Когда у нас отрицательный stock, какую цену использовать?

Ответ: ПОСЛЕДНИЙ ИЗВЕСТНЫЙ cost_snapshot из ledger

Когда молоко приходит → становится положительным.

Важно: Не пересчитываем прошлые продажи!
Берём текущую цену на момент продажи.

## NOTIFICATION: NEGATIVE STOCK WARNING

При отрицательном stock система должна:
- Логировать в систему
- Отправлять alert (Telegram, Email)
- Показывать в UI красным цветом

Пример alert:
⚠️ Milk в долгу на 700 гр!

## ПРОВЕРКА ПЕРЕД КОММИТОМ

1. Продажа НЕ блокируется если stock < 0? → ДА!
2. Ставится флаг negative_stock_warning когда нужно? → ДА!
3. Используется get_last_known_cost() для cost_snapshot? → ДА!
4. UI показывает warning? → ДА! (потом)
5. История НЕ пересчитывается задним числом? → ДА!

## ЧАСТЫЕ ОШИБКИ

ПЛОХО: Блокируешь продажу если stock < 0
if current_stock < required_qty:
  raise Exception("Not enough stock!")

ХОРОШО: Пишешь в ledger, ставишь flag
ledger_entry = InventoryLedger(
  change_amount=-required_qty,
  negative_stock_warning=(current_balance - required_qty) < 0
)

ПЛОХО: Пересчитываешь прошлые COGS когда приходит молоко
# Когда молоко приходит, пересчитываешь все прошлые продажи
# ЗАПРЕЩЕНО!

ХОРОШО: Просто пишешь новый entry
supply = InventoryLedger(
  change_amount=+1000,
  event_type='SUPPLY',
  cost_snapshot=новая_цена
)
# История прошлых продаж остаётся как есть!

## ИТОГ

Negative stock НЕ ошибка. Это нормальная часть бизнеса.

- Продажа всегда идёт
- Warning ставится
- История сохраняется
- Cost snapshot неизменен

Молоко приходит завтра — остаток становится положительным.