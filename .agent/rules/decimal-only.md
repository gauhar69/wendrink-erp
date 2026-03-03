---
trigger: always_on
---

# DECIMAL-ONLY RULE (NEVER FLOAT!)

Float = путь к потерям денег. Decimal = финансовая безопасность.

## ПРАВИЛО

НИКОГДА не используй float для денег!
ВСЕГДА используй Decimal для денег, количеств, цен!

## ПОЧЕМУ?

Float имеет проблему точности:

FLOAT (ЗЛО):
0.1 + 0.2 == 0.3  → False! (в python это 0.30000000000000004)

DECIMAL (ДОБРО):
Decimal("0.1") + Decimal("0.2") == Decimal("0.3")  → True!

В ERP системе каждая копейка считается. Один ошибочный расчёт = потеря денег.

## ПРАВИЛА

1. ВСЕ деньги = Decimal
   - цены продажи
   - цены закупки
   - себестоимость
   - выручка
   - расходы

2. ВСЕ количества = Decimal (если используются в расчётах)
   - грамм сырья
   - объём напитка
   - кол-во порций

3. В БД = DECIMAL тип
   - DECIMAL(10, 4) для большинства
   - DECIMAL(10, 2) для денег
   - DECIMAL(12, 4) для больших сумм

4. В коде = Decimal класс
   from decimal import Decimal, ROUND_HALF_UP

## МОДЕЛИ (ПРИМЕР)

Product таблица:
- id: UUID
- code: String (50)
- name: String (255)
- sale_price: Decimal (Numeric(10, 2)) ← DECIMAL в БД!

InventoryLedger таблица:
- id: UUID
- ingredient_id: UUID
- change_amount: Decimal (Numeric(10, 4)) ← DECIMAL для кол-ва!
- cost_snapshot: Decimal (Numeric(10, 4)) ← DECIMAL для цены!

Sale таблица:
- id: UUID
- total_amount: Decimal (Numeric(12, 2)) ← DECIMAL для выручки!

FinanceLedger таблица:
- id: UUID
- amount: Decimal (Numeric(12, 2)) ← DECIMAL для расходов!

## ПРИМЕРЫ: РАСЧЁТЫ

Пример 1: Вычисление выручки

ПЛОХО (float):
def calculate_revenue(price: float, quantity: float) -> float:
  return price * quantity

ХОРОШО (Decimal):
def calculate_revenue(price: Decimal, quantity: Decimal) -> Decimal:
  return price * quantity

Использование:
price = Decimal("45.50")
quantity = Decimal("3")
revenue = calculate_revenue(price, quantity)
# revenue = Decimal("136.50")

Пример 2: Вычисление средней стоимости

ПЛОХО (float, потеря точности):
def avg_cost_float(old_qty, old_cost, new_qty, new_cost):
  total = (old_qty * old_cost) + (new_qty * new_cost)
  total_qty = old_qty + new_qty
  return total / total_qty  # Ошибка точности!

ХОРОШО (Decimal):
def avg_cost_decimal(old_qty, old_cost, new_qty, new_cost):
  total = (old_qty * old_cost) + (new_qty * new_cost)
  total_qty = old_qty + new_qty
  return (total / total_qty).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

Использование:
old_qty = Decimal("100")
old_cost = Decimal("500.0000")
new_qty = Decimal("50")
new_cost = Decimal("600.0000")
result = avg_cost_decimal(old_qty, old_cost, new_qty, new_cost)
# result = Decimal("533.3333") — точно!

Пример 3: Вычисление COGS

ПЛОХО (float):
total_cogs = sum([sale.quantity * sale.cost for sale in sales])

ХОРОШО (Decimal):
total_cogs = sum(
  (sale.quantity * sale.cost_snapshot for sale in sales),
  Decimal("0.00")
)

Пример 4: Вычисление P&L

ПРАВИЛЬНО:
async def calculate_daily_pnl(business_date):
  revenue = Decimal("0.00")
  cogs = Decimal("0.00")
  
  # Считаем выручку (Decimal + Decimal)
  sales_list = await session.execute(
    select(Sale.total_amount).where(Sale.business_date == business_date)
  )
  for sale in sales_list:
    revenue += sale.total_amount
  
  # Считаем COGS (Decimal * Decimal)
  ledger = await session.execute(
    select(InventoryLedger.change_amount, InventoryLedger.cost_snapshot)
    .where(InventoryLedger.event_type == "SALE")
    .where(InventoryLedger.business_date == business_date)
  )
  for entry in ledger:
    cogs += (abs(entry.change_amount) * entry.cost_snapshot)
  
  # Прибыль (Decimal - Decimal)
  gross_profit = revenue - cogs
  
  return {
    "revenue": revenue,
    "cogs": cogs,
    "gross_profit": gross_profit,
    "margin_percent": (
      (gross_profit / revenue * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
      if revenue > 0 else Decimal("0.00")
    )
  }

## PYDANTIC SCHEMAS

Используй Decimal в Pydantic моделях.

Валидируй в field_validator:
- Цена должна быть положительная
- Количество дней. точных дней после запятой (не более 2 для денег)

При сериализации в JSON:
- Decimal → String (потому что JSON не поддерживает Decimal)

## FASTAPI RESPONSE

Когда возвращаешь Decimal в JSON:
- Сериализуй как строка: str(decimal_value)

Пример:
GET /daily-pnl/2026-01-27
Ответ:
{
  "date": "2026-01-27",
  "revenue": "18250.50",
  "cogs": "5251.80",
  "gross_profit": "12998.70",
  "margin_percent": "71.16"
}

## ПРОВЕРКА ПЕРЕД КОММИТОМ

1. Нет ли float для денег? → ДА!
   grep -r "float" app/ | grep -E "(price|cost|amount|balance)"
   # Не должно быть совпадений!

2. ВСЕ денежные колонки = DECIMAL в БД? → ДА!
   # models.py
   sale_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

3. Импортируешь from decimal import Decimal? → ДА!

4. Используешь .quantize() для округления? → ДА!
   result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

## ЧАСТЫЕ ОШИБКИ

ПЛОХО:
price = 45.5  # float!
quantity = 3
revenue = price * quantity  # 136.5 (может быть неправильно)

ХОРОШО:
price = Decimal("45.50")
quantity = Decimal("3")
revenue = price * quantity  # Decimal("136.50") — точно!

ПЛОХО:
from sqlalchemy import Float
sale_price: Mapped[float] = mapped_column(Float)  # НЕЛЬЗЯ!

ХОРОШО:
from sqlalchemy import Numeric
sale_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # ПРАВИЛЬНО!

ПЛОХО:
avg = total / count  # Может быть 0.3333... (бесконечная дробь)

ХОРОШО:
avg = (total / count).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
# 0.3333 — точно!

## ИТОГ

Decimal = финансовая безопасность. Float = путь к потерям денег.

Не жалей времени на конвертацию строк в Decimal.
Одна ошибка в расчётах = потеря доверия клиентов.
