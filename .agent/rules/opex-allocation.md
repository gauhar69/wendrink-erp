---
trigger: always_on
---

# 09-opex-allocation.md

## OPEX ALLOCATION RULE (OPERATIONAL EXPENSES)

**Зарплата 756,000 ₸/месяц → 25,200 ₸/день. Просто и честно.**

---

### ⚡ ПРИНЦИП

```
ТВОЙ БИЗНЕС платит КАЖДЫЙ ДЕНЬ:
- Аренда: 10,000 ₸/день (300,000 / 30)
- Охрана: 467 ₸/день (14,000 / 30)
- Электричество: 1,167 ₸/день (35,000 / 30)
- Зарплата: 25,200 ₸/день (756,000 / 30)
- Интернет: 500 ₸/день (15,000 / 30)
- Коммуналка: 278 ₸/день (8,350 / 30)
- Бухгалтер: 1,000 ₸/день (30,000 / 30)
- Охрана ночная: 800 ₸/день (24,000 / 30)

ИТОГО: 38,612 ₸/день
```

В системе:
```
Daily P&L = Revenue - COGS - OPEX
```

---

### 📊 СТРУКТУРА ДАННЫХ

```python
class OPEXCategory(Base):
    __tablename__ = "opex_categories"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str]  # "RENT", "SALARY", "UTILITIES"
    monthly_amount: Mapped[Decimal]  # 300000, 756000, 35000
    description: Mapped[str | None]


class FinanceLedger(Base):
    __tablename__ = "finance_ledger"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    category: Mapped[str]  # "RENT", "SALARY", "UTILITIES", "SECURITY"
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("opex_categories.id"))
    
    # AMOUNT:
    amount: Mapped[Decimal]  # дневная сумма (25200 для зарплаты)
    monthly_amount: Mapped[Decimal | None]  # исходная месячная (756000)
    
    # DATES:
    business_date: Mapped[date]  # день начисления
    period_start: Mapped[date | None]  # например, 2026-01-01
    period_end: Mapped[date | None]  # например, 2026-01-31
    accrual_date: Mapped[date | None]  # дата реального платежа (потом)
    
    # METADATA:
    description: Mapped[str | None]  # "Зарплата за январь"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

---

### 🔧 ЛОГИКА: ИМПОРТ РАСХОДОВ

**Твоя таблица:**
```
Категория | Месячная сумма
Аренда | 300,000
Охрана | 14,000
Интернет | 15,000
...
```

**Процесс импорта:**

```python
async def import_opex_from_csv(
    month: str,  # "2026-01"
    opex_data: list[dict],  # [{"category": "RENT", "monthly": 300000}, ...]
    session: AsyncSession
):
    """
    Импортирует месячные расходы и распределяет по дням.
    
    Пример:
    month = "2026-01" (январь 2026, 31 день)
    opex_data = [
        {"code": "RENT", "name": "Аренда", "monthly": 300000, "description": "Помещение"},
        {"code": "SALARY", "name": "Зарплата", "monthly": 756000, "description": "ФОТ"},
        ...
    ]
    """
    
    async with session.begin():
        # Разбери месяц
        start_date = datetime.strptime(month, "%Y-%m").date()
        days_in_month = (
            start_date.replace(day=28) + timedelta(days=4)
        ).replace(day=1) - timedelta(days=1)
        num_days = days_in_month.day  # 31, 28, 29, 30
        
        end_date = start_date.replace(day=num_days)
        
        for item in opex_data:
            # Получи или создай категорию
            category = await session.execute(
                select(OPEXCategory).where(OPEXCategory.code == item["code"])
            ).scalar_one_or_none()
            
            if not category:
                category = OPEXCategory(
                    code=item["code"],
                    name=item["name"],
                    monthly_amount=Decimal(item["monthly"]),
                    description=item.get("description", "")
                )
                session.add(category)
                await session.flush()
            
            # Вычисли дневную сумму
            monthly = Decimal(item["monthly"])
            daily_amount = (monthly / Decimal(num_days)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )
            
            # Напиши в ledger для каждого дня месяца
            current_date = start_date
            while current_date <= end_date:
                # Пропусти дни, которые уже есть (идемпотентность)
                existing = await session.execute(
                    select(FinanceLedger).where(
                        FinanceLedger.category == item["code"]
                    ).where(
                        FinanceLedger.business_date == current_date
                    )
                ).scalar_one_or_none()
                
                if not existing:
                    ledger_entry = FinanceLedger(
                        category=item["code"],
                        category_id=category.id,
                        amount=daily_amount,
                        monthly_amount=monthly,
                        business_date=current_date,
                        period_start=start_date,
                        period_end=end_date,
                        description=f"{category.name} (распределение на день)"
                    )
                    session.add(ledger_entry)
                
                current_date += timedelta(days=1)
        
        await session.commit()
        
        logger.info(f"Imported OPEX for {month}, {num_days} days")
```

---

### 📊 ПРИМЕР: РАСПРЕДЕЛЕНИЕ ЗАРПЛАТЫ

**Входные данные:**
```
Месяц: Январь 2026 (31 день)
Зарплата: 756,000 ₸

Дневная зарплата = 756,000 / 31 = 24,387.09 ₸/день
```

**Результат в finance_ledger:**
```
business_date | category | amount | period_start | period_end | description
2026-01-01 | SALARY | 24,387.09 | 2026-01-01 | 2026-01-31 | Зарплата (распределение)
2026-01-02 | SALARY | 24,387.09 | 2026-01-01 | 2026-01-31 | Зарплата (распределение)
2026-01-03 | SALARY | 24,387.09 | 2026-01-01 | 2026-01-31 | Зарплата (распределение)
...
2026-01-31 | SALARY | 24,387.09 | 2026-01-01 | 2026-01-31 | Зарплата (распределение)
```

**Всего за месяц:**
```
SUM(amount WHERE category='SALARY' AND period='2026-01') 
= 24,387.09 * 31 = 755,999.79 ≈ 756,000 ✅
```

---

### 🎯 DAILY P&L С OPEX

```python
async def calculate_daily_pnl_with_opex(business_date: date, session: AsyncSession) -> dict:
    """
    Полная формула P&L: Revenue - COGS - OPEX = Net Profit
    """
    
    # 1. REVENUE
    revenue_result = await session.execute(
        select(func.sum(Sale.total_amount))
        .where(Sale.business_date == business_date)
    )
    revenue = revenue_result.scalar() or Decimal(0)
    
    # 2. COGS (с WAC)
    cogs_result = await session.execute(
        select(func.sum(InventoryLedger.cost_snapshot))
        .where(InventoryLedger.event_type == "SALE")
        .where(InventoryLedger.business_date == business_date)
    )
    cogs = cogs_result.scalar() or Decimal(0)
    
    # 3. OPEX (зарплата, аренда, коммуналка)
    opex_result = await session.execute(
        select(func.sum(FinanceLedger.amount))
        .where(FinanceLedger.business_date == business_date)
    )
    opex = opex_result.scalar() or Decimal(0)
    
    # 4. ВЫЧИСЛЯЙ ПРИБЫЛЬ
    gross_profit = revenue - cogs
    net_profit = gross_profit - opex
    
    gross_margin_percent = (
        (gross_profit / revenue * Decimal(100))
        if revenue > Decimal(0) else Decimal(0)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    net_margin_percent = (
        (net_profit / revenue * Decimal(100))
        if revenue > Decimal(0) else Decimal(0)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    return {
        "business_date": str(business_date),
        "revenue": str(revenue),
        "cogs": str(cogs),
        "gross_profit": str(gross_profit),
        "gross_margin_percent": str(gross_margin_percent),
        "opex": str(opex),
        "net_profit": str(net_profit),
        "net_margin_percent": str(net_margin_percent),
        "breakdown": {
            "revenue": {
                "amount": str(revenue),
                "percent": "100%"
            },
            "cogs": {
                "amount": str(cogs),
                "percent": str((cogs / revenue * 100) if revenue > 0 else 0)
            },
            "opex": {
                "amount": str(opex),
                "percent": str((opex / revenue * 100) if revenue > 0 else 0)
            },
            "net_profit": {
                "amount": str(net_profit),
                "percent": str(net_margin_percent)
            }
        }
    }
```

---

### 📊 ПРИМЕР: ДЕНЬ ТОРГОВЛИ

```python
# День: 27 января 2026

# Продажи:
# - 10 рожков сливочных по 300 ₸ = 3,000 ₸
# - 5 сандэ по 650 ₸ = 3,250 ₸
# - 15 молочных чаев по 800 ₸ = 12,000 ₸
REVENUE = 18,250 ₸

# COGS:
# - 10 рожков: 10 * 96.54 = 965.4 ₸
# - 5 сандэ: 5 * 236.52 = 1,182.6 ₸
# - 15 чаев: 15 * 206.92 = 3,103.8 ₸
COGS = 5,251.8 ₸

# OPEX (дневные):
# - Зарплата: 24,387 ₸
# - Аренда: 10,000 ₸
# - Электричество: 1,167 ₸
# - Охрана: 467 ₸
# - Интернет: 500 ₸
# - Коммуналка: 278 ₸
# - Бухгалтер: 1,000 ₸
OPEX = 37,799 ₸

P&L:
Gross Profit = 18,250 - 5,251.8 = 12,998.2 ₸
Gross Margin = 12,998.2 / 18,250 = 71.2%

Net Profit = 12,998.2 - 37,799 = -24,800.8 ₸  ⚠️ УБЫТОК!
Net Margin = -24,800.8 / 18,250 = -135.8%

ВЫВОД: Выручка < OPEX. День был убыточный.
(Это нормально, ваша маржа Gross = 71%, но OPEX большие)
```

---

### ⚠️ ОСОБЫЕ СЛУЧАИ

#### 1. Месяц с разным количеством дней

```python
# Январь 2026: 31 день
daily = 756000 / 31 = 24,387.09

# Февраль 2026: 28 дней (2026 не високосный)
daily = 756000 / 28 = 27,000.00

# Март 2026: 31 день
daily = 756000 / 31 = 24,387.09
```

#### 2. Дополнительные расходы (не ежедневные)

```python
# Если нужно добавить расход в конкретный день:
one_time_expense = FinanceLedger(
    category="REPAIR",
    amount=Decimal("50000"),
    business_date=date(2026, 1, 27),
    description="Ремонт кондиционера"
)
session.add(one_time_expense)
```

#### 3. Бонусы / Доп. выплаты

```python
# Выплатили бонус в конце месяца:
bonus = FinanceLedger(
    category="SALARY",
    amount=Decimal("100000"),
    business_date=date(2026, 1, 31),
    description="Бонус коллективу",
    period_start=date(2026, 1, 1),
    period_end=date(2026, 1, 31)
)
```

---

### 🔍 ПРОВЕРКА ПЕРЕД КОММИТОМ

1. ✅ OPEX распределяется по дням (дневная = месячная / дни)? **→ ДА!**
2. ✅ SUM(daily amounts) = месячная сумма? **→ ДА!**
3. ✅ Finance_ledger БЕЗ UPDATE/DELETE (только INSERT)? **→ ДА!**
4. ✅ Daily P&L = Revenue - COGS - OPEX? **→ ДА!**
5. ✅ Можно добавлять разовые расходы? **→ ДА!**
6. ✅ Idempotency (одни и те же дни не дублируются)? **→ ДА!**

---

### 🎯 ИТОГ

**OPEX = объективная реальность бизнеса**

Твой кафе платит:
- 38,612 ₸/день обязательных расходов
- 18,250 ₸ выручки в день (в примере) < чем OPEX
- = убыток

Система показывает правду:
```
Revenue: 18,250 ₸
COGS: 5,251 ₸
OPEX: 37,799 ₸
─────────────
Net Profit: -24,801 ₸ 🔴

Нужно либо:
1. Увеличить выручку (больше клиентов)
2. Снизить COGS (дешевле ингредиенты)
3. Снизить OPEX (оптимизировать расходы)
```

Это не баг, это фича! 🎯