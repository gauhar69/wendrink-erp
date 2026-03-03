---
trigger: always_on
---


# BUSINESS DATE RULE (ALMATY TIMEZONE)

В Казахстане время другое. Это критично для отчётов!

## ПРАВИЛО

Сохраняй в UTC. Считай в Asia/Almaty.

Время торговли в кофейне (Almaty):
- 6:00 AM — начало рабочего дня
- 5:59 AM (ночью) — конец предыдущего дня

00:00–05:59 (Almaty) → business_date ВЧЕРА
06:00–23:59 (Almaty) → business_date СЕГОДНЯ

## ПРИМЕРЫ

Пример 1:
UTC timestamp: 2026-01-27 01:30:00 (полночь)
Almaty time: 2026-01-27 06:30:00 (утро)
business_date: 2026-01-27 ✅

Пример 2:
UTC timestamp: 2026-01-27 04:30:00 (ночь)
Almaty time: 2026-01-27 09:30:00 (утро)
business_date: 2026-01-27 ✅

Пример 3:
UTC timestamp: 2026-01-27 00:30:00 (полночь)
Almaty time: 2026-01-27 05:30:00 (ночь, ДО 6 AM)
business_date: 2026-01-26 ✅ (ВЧЕРА!)

## ФУНКЦИЯ

Функция get_business_date() преобразует UTC timestamp в business_date:

Правило:
- 00:00–05:59 (Almaty) → предыдущий день
- 06:00–23:59 (Almaty) → текущий день

Убедись что timestamp в UTC (с timezone информацией).
Конвертируй в Almaty через ZoneInfo("Asia/Almaty").
Если час < 6, это день ВЧЕРА.
Иначе это день СЕГОДНЯ.

## ХРАНЕНИЕ

created_at колонка = UTC (для аудита)
business_date колонка = вычисленный через Almaty (для отчётов)

Важно:
- created_at = UTC (для точного временного порядка)
- business_date = вычисленный (для правильной группировки по дням торговли)

## ПРИМЕРЫ: DAILY P&L

P&L за день считается по business_date (в Almaty):

Выручка за день:
SELECT SUM(total_amount) FROM sales WHERE business_date = '2026-01-27'

COGS за день:
SELECT SUM(ABS(change_amount) * cost_snapshot) FROM inventory_ledger WHERE event_type='SALE' AND business_date='2026-01-27'

Gross Profit = Revenue - COGS

## ЧАСТЫЕ ОШИБКИ

ПЛОХО: Используешь datetime.now() без timezone
bdate = datetime.now().date()

ХОРОШО: Вызываешь функцию
bdate = get_business_date(datetime.now(timezone.utc))

ПЛОХО: Сохраняешь Almaty time в БД
sale.created_at = almaty_time

ХОРОШО: Сохраняешь UTC
sale.created_at = utc_ts
sale.business_date = get_business_date(utc_ts)

## ПРОВЕРКА ПЕРЕД КОММИТОМ

1. created_at везде в UTC? → ДА!
2. business_date везде через get_business_date()? → ДА!
3. Часовой пояс явно указан? → ДА!
4. Нет магических часов? → ДА!
5. Тесты проверяют граничные случаи (23:59, 00:00)? → ДА!

## ИТОГ

Timezone = не шутки. Одна часовая зона разница = неправильный P&L за день.

Всегда используй:
1. UTC для хранения (created_at)
2. Almaty для расчётов (business_date)
3. ZoneInfo для конвертации (get_business_date())