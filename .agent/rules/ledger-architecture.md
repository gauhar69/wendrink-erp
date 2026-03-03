---
trigger: always_on
---

# LEDGER-FIRST ARCHITECTURE

Это правило ФИЗИЧЕСКИ блокирует неправильный код!

## ПРИНЦИП

Ты НЕ МОЖЕШЬ создавать таблицы типа:
- current_stock
- current_balance
- cached_totals
- inventory_snapshot

ВМЕСТО ЭТОГО:

Остаток сырья = SUM(inventory_ledger.change_amount WHERE ingredient_id = X)

Выручка = SUM(sales.total_amount WHERE business_date = '2026-01-27')

Расход сырья (COGS) = SUM(ABS(inventory_ledger.change_amount * cost_snapshot) WHERE event_type='SALE' AND business_date='2026-01-27')

Расчёт всегда свежий. Нет кэша. Нет застаревших данных.

ИСТИНА = SUM()

## ТОЛЬКО INSERT В LEDGER

Таблицы inventory_ledger, sales, finance_ledger — ТОЛЬКО INSERT!

РАЗРЕШЕНО:
- INSERT INTO inventory_ledger (ingredient_id, change_amount, cost_snapshot, event_type) VALUES (1, -50, 2500.00, 'SALE')

ЗАПРЕЩЕНО:
- UPDATE inventory_ledger SET change_amount = -100 WHERE id = 5
- DELETE FROM inventory_ledger WHERE id = 5

Любое исправление = новый CORRECTION event!

Неправильно записали -50 вместо -30? Не UPDATE! Пиши CORRECTION:
INSERT INTO inventory_ledger (ingredient_id, change_amount, cost_snapshot, event_type) VALUES (1, 20, 2500.00, 'CORRECTION')

## СТРУКТУРА LEDGER

inventory_ledger таблица содержит:
- id (UUID primary key)
- ingredient_id (UUID foreign key)
- change_amount (Decimal) - +/- кол-во
- event_type (String) - SUPPLY / SALE / CORRECTION
- event_id (UUID nullable) - ссылка на sales/supply
- cost_snapshot (Decimal) - цена на момент
- business_date (Date) - бизнес-дата (Almaty)
- created_at (DateTime UTC)

## КАК СЧИТАТЬ ОСТАТОК

Остаток = SUM всех changes по дату включительно

Никакой current_stock колонки! Просто SUM!

Для ингредиента на определённую дату:
SELECT SUM(change_amount) FROM inventory_ledger WHERE ingredient_id = X AND business_date <= '2026-01-27'

## КАК СЧИТАТЬ РАСХОД (COGS)

COGS = SUM(ABS(change_amount * cost_snapshot)) для SALE events

Для дня:
SELECT SUM(ABS(change_amount) * cost_snapshot) FROM inventory_ledger WHERE event_type='SALE' AND business_date='2026-01-27'

## ПРОВЕРКА ПЕРЕД ДЕПЛОЕМ

Перед тем как пушить код:

1. Есть ли в моделях current_stock? → УДАЛИТЬ!
2. Есть ли UPDATE/DELETE для ledger? → УДАЛИТЬ!
3. Все расчёты используют SUM()? → ДА!
4. Cost snapshot хранится в ledger? → ДА!
5. Все timestamps в UTC? → ДА!

Если хоть один ответ НЕ ДА → STOP, не коммитить!

## ОПАСНЫЕ ПАТТЕРНЫ

ПЛОХО:
stock.current_qty = stock.current_qty - sale_qty

ХОРОШО:
ledger.insert(ingredient_id=ing_id, change_amount=-sale_qty, cost_snapshot=last_cost, event_type='SALE')
Остаток = SUM всех events

## ИТОГ

Ledger = священно. История = неизменна. Истина = SUM().

Это не рекомендация. Это закон архитектуры.