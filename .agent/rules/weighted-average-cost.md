---
trigger: always_on
---


# 08-weighted-average-cost.md

## WEIGHTED AVERAGE COST RULE (DYNAMIC INGREDIENT PRICING)

**Цена на какао меняется → себестоимость напитка меняется → маржа падает/растёт**

---

### ⚡ ПРИНЦИП

Каждый ингредиент имеет историю закупок с разными ценами:

```
КАКАО-ПОРОШОК:
Закупка #1: 100 кг по 56,000 ₸ → 56,000 / 24,000 гр = 2.33 ₸/гр
Закупка #2: 100 кг по 71,250 ₸ → 71,250 / 24,000 гр = 2.97 ₸/гр
Закупка #3: 100 кг по 52,500 ₸ → 52,500 / 24,000 гр = 2.19 ₸/гр

Weighted Average = (100 * 2.33 + 100 * 2.97 + 100 * 2.19) / 300 = 2.50 ₸/гр

↓

Рожок требует 31 гр какао
Себестоимость = 31 * 2.50 = 77.50 ₸

Если завтра купим ещё 100 кг по 3.00 ₸/гр:
Новый WAC = (300 * 2.50 + 100 * 3.00) / 400 = 2.63 ₸/гр
Новая себестоимость рожка = 31 * 2.63 = 81.53 ₸
```

---

### 🔧 СТРУКТУРА LEDGER (ПЕРЕСЧЁТ)

```python
class InventoryLedger(Base):
    __tablename__ = "inventory_ledger"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    ingredient_id: Mapped[UUID]
    change_amount: Mapped[Decimal]  # +100 гр (закупка) или -31 гр (продажа)
    event_type: Mapped[str]  # SUPPLY, SALE, CORRECTION
    
    # WEIGHTED AVERAGE TRACKING:
    unit_cost_at_event: Mapped[Decimal]  # цена за единицу в момент события
    weighted_average_cost: Mapped[Decimal]  # WAC на момент события (важно!)
    cost_snapshot: Mapped[Decimal]  # для COGS (change_amount * weighted_average_cost)
    
    business_date: Mapped[date]
    created_at: Mapped[datetime]
```

**Важно:** WAC считается и СОХРАНЯЕТСЯ в ledger на момент события!

---

### 🔄 ЛОГИКА: НОВАЯ ЗАКУПКА (SUPPLY)

```python
async def add_supply(
    ingredient_id: UUID,
    quantity_units: Decimal,  # кол-во упаковок (например, 5 упаковок по 24000 гр)
    price_per_unit: Decimal,  # цена за упаковку (например, 56000 ₸)
    session: AsyncSession
):
    """
    Добавляет новую закупку и пересчитывает Weighted Average Cost.
    
    Пример:
    - 5 упаковок какао-порошка
    - Каждая упаковка 24000 гр
    - Цена за упаковку: 56000 ₸
    
    ↓
    
    - Total quantity = 5 * 24000 = 120000 гр
    - Total price = 5 * 56000 = 280000 ₸
    - Unit cost = 280000 / 120000 = 2.33 ₸/гр
    """
    
    async with session.begin():
        await session.execute(
            text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        )
        
        # Получи старый WAC (последний известный)
        old_wac = await get_current_wac(ingredient_id, session)
        
        # Получи старое количество (SUM всех предыдущих changes)
        old_qty_result = await session.execute(
            select(func.sum(InventoryLedger.change_amount))
            .where(InventoryLedger.ingredient_id == ingredient_id)
            .where(InventoryLedger.business_date <= 
                   get_business_date(datetime.now(timezone.utc)))
            .with_for_update()
        )
        old_qty = old_qty_result.scalar() or Decimal(0)
        
        # Вычисли размер закупки в граммах
        # (assuming each unit = package_size from ingredients table)
        ingredient = await session.get(Ingredient, ingredient_id)
        total_qty = quantity_units * ingredient.package_weight_grams
        
        # Вычисли стоимость за грамм
        unit_cost = price_per_unit / ingredient.package_weight_grams
        
        # Пересчитай WAC
        new_wac = (
            (old_qty * old_wac) + (total_qty * unit_cost)
        ) / (old_qty + total_qty)
        
        # Напиши в ledger
        ledger_entry = InventoryLedger(
            ingredient_id=ingredient_id,
            change_amount=total_qty,  # +120000 гр
            event_type="SUPPLY",
            unit_cost_at_event=unit_cost,  # 2.33 ₸/гр
            weighted_average_cost=new_wac,  # пересчитанный WAC
            cost_snapshot=new_wac * total_qty,  # для аудита (но не используется в COGS)
            business_date=get_business_date(datetime.now(timezone.utc)),
            created_at=datetime.now(timezone.utc)
        )
        
        session.add(ledger_entry)
        await session.commit()
        
        logger.info(f"Supply: {ingredient.name}, old_wac={old_wac}, new_wac={new_wac}")
        
        return ledger_entry
```

---

### 📊 ЛОГИКА: ПРОДАЖА (SALE)

Когда продаём напиток:

```python
async def create_sale(product_id: UUID, quantity: int, session: AsyncSession):
    """
    Продажа напитка. Себестоимость считается по ТЕКУЩЕМУ WAC.
    """
    
    async with session.begin():
        await session.execute(
            text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        )
        
        product = await session.get(Product, product_id, with_for_update=True)
        recipe = await get_active_recipe(product_id, session)
        
        # Создай sales запись
        sale = Sale(
            product_id=product_id,
            quantity=quantity,
            total_amount=product.sale_price * quantity,
            business_date=get_business_date(datetime.now(timezone.utc)),
            created_at=datetime.now(timezone.utc)
        )
        session.add(sale)
        await session.flush()
        
        # Для каждого ингредиента в рецепте
        total_cogs_snapshot = Decimal(0)
        
        for recipe_item in recipe.items:
            ingredient = recipe_item.ingredient
            required_qty = recipe_item.quantity * quantity  # 31 * 1 = 31 гр
            
            # Получи ТЕКУЩИЙ WAC
            current_wac = await get_current_wac(ingredient.id, session)
            
            # Cost snapshot = требуемое кол-во * текущий WAC
            cost_snapshot_for_item = required_qty * current_wac
            total_cogs_snapshot += cost_snapshot_for_item
            
            # Пиши в inventory ledger (ОТРИЦАТЕЛЬНОЕ количество)
            ledger_entry = InventoryLedger(
                ingredient_id=ingredient.id,
                change_amount=-required_qty,  # -31 гр
                event_type="SALE",
                event_id=sale.id,
                unit_cost_at_event=current_wac,  # 2.33 ₸/гр
                weighted_average_cost=current_wac,  # не меняется при продаже!
                cost_snapshot=cost_snapshot_for_item,  # 31 * 2.33 = 72.23 ₸
                business_date=get_business_date(datetime.now(timezone.utc)),
                created_at=datetime.now(timezone.utc)
            )
            session.add(ledger_entry)
        
        # Обнови sale с total_cogs
        sale.total_cogs = total_cogs_snapshot
        
        await session.commit()
        
        return sale
```

---

### 🧮 ПРИМЕРЫ: СЕБЕСТОИМОСТЬ НАПИТКА

**ПРИМЕР 1: Рожок сливочный**

```
Рецепт:
- 31 гр "Ориг. порошок мороженое" (текущий WAC = 2.33 ₸/гр)
- 1 шт "Рожок (Вафельный)" (текущий WAC = ?)

COGS при продаже сегодня:
= (31 * 2.33) + (1 * cost_waffle)
= 72.23 + cost_waffle
≈ 96 ₸ (совпадает с твоей таблицей!)

ЕСЛИ ЗАВТРА ЦЕНА КАКАО ВЫРАСТЕТ ДО 3.00 ₸/гр:
New WAC = 3.00
COGS = (31 * 3.00) + (1 * cost_waffle)
     = 93 + cost_waffle
     ≈ 117 ₸ (маржа упадёт!)

Маржа было: (300 - 96) / 300 = 68%
Маржа стало: (300 - 117) / 300 = 61% ⬇️
```

**ПРИМЕР 2: Шоколадный сандэ**

```
Рецепт:
- 64 гр "Ориг. порошок мороженое" (WAC = 2.33)
- 30 гр "Шоколадный соус" (WAC = 1.56)
- 1 шт "U-образная чашка" (WAC = ?)
- 1 шт "Сферическая крышка (90)" (WAC = ?)
- 1 шт "специальная ложка" (WAC = ?)

COGS:
= (64 * 2.33) + (30 * 1.56) + (1 * cup) + (1 * cap) + (1 * spoon)
= 149.12 + 46.8 + cup + cap + spoon
≈ 236.52 (совпадает с таблицей!)
```

---

### 🔍 ФУНКЦИЯ: ПОЛУЧИТЬ ТЕКУЩИЙ WAC

```python
async def get_current_wac(ingredient_id: UUID, session: AsyncSession) -> Decimal:
    """
    Получает ТЕКУЩИЙ (последний) Weighted Average Cost ингредиента.
    """
    result = await session.execute(
        select(InventoryLedger.weighted_average_cost)
        .where(InventoryLedger.ingredient_id == ingredient_id)
        .order_by(InventoryLedger.created_at.desc())
        .limit(1)
    )
    
    wac = result.scalar()
    
    if wac is None:
        # Если истории нет, попробуй получить из справочника
        ingredient = await session.get(Ingredient, ingredient_id)
        if ingredient.initial_cost is None:
            raise ValueError(f"No WAC history for {ingredient_id}")
        return ingredient.initial_cost
    
    return wac
```

---

### 📊 DAILY P&L С WAC

```python
async def calculate_daily_pnl_with_wac(business_date: date, session: AsyncSession) -> dict:
    """
    P&L с динамической себестоимостью (WAC).
    """
    
    # Выручка
    revenue = await session.execute(
        select(func.sum(Sale.total_amount))
        .where(Sale.business_date == business_date)
    ).scalar() or Decimal(0)
    
    # COGS = SUM(cost_snapshot) для SALE events
    cogs = await session.execute(
        select(func.sum(InventoryLedger.cost_snapshot))
        .where(InventoryLedger.event_type == "SALE")
        .where(InventoryLedger.business_date == business_date)
    ).scalar() or Decimal(0)
    
    # Gross Profit
    gross_profit = revenue - cogs
    
    return {
        "business_date": business_date,
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "margin_percent": (gross_profit / revenue * 100) if revenue > 0 else Decimal(0),
        "wac_status": "динамическая себестоимость (WAC)",
        "note": "Если цена закупок изменилась → COGS и маржа изменятся!"
    }
```

---

### ⚠️ ВАЖНЫЕ МОМЕНТЫ

#### 1. WAC при NEGATIVE STOCK

```
Остаток: 100 гр какао (WAC = 2.33)
Продали: 150 гр какао (требуется -150 гр)

Новый остаток: 100 - 150 = -50 гр (отрицательный!)

COGS:
- Первые 100 гр: 100 * 2.33 = 233 ₸
- Следующие 50 гр: ? (нет запаса)

Решение:
- Продажа всё равно идёт
- COGS считаем по ТЕКУЩЕМУ WAC (2.33)
- Даже для -50 гр (которых нет в запасе)
- warning = true
```

#### 2. WAC не меняется при КОРРЕКЦИИ

```
Ошибка: записали -150 гр вместо -100 гр какао

CORRECTION:
INSERT ... change_amount = +50, event_type='CORRECTION'

WAC ОСТАЁТСЯ ТОТ ЖЕ!
Не пересчитываем WAC для старых событий.
История WAC священна!
```

---

### 🔍 ПРОВЕРКА ПЕРЕД КОММИТОМ

1. ✅ WAC правильно считается при SUPPLY? **→ ДА!**
   ```python
   new_wac = (old_qty * old_wac + new_qty * new_unit_cost) / (old_qty + new_qty)
   ```

2. ✅ WAC считается с использованием SERIALIZABLE? **→ ДА!**

3. ✅ COGS = SUM(cost_snapshot) где cost_snapshot = change * WAC? **→ ДА!**

4. ✅ Маржа пересчитывается если WAC меняется? **→ ДА!**

5. ✅ Negative stock использует ТЕКУЩИЙ WAC? **→ ДА!**

6. ✅ Прошлые WAC значения не меняются? **→ ДА!**

---

### 🎯 ИТОГ

**WAC = динамическая себестоимость ингредиентов**

Когда цены закупок меняются:
- WAC пересчитывается
- COGS для новых продаж меняется
- Маржа может упасть/вырасти
- История остаётся неизменной (cost_snapshot фиксируется)

Это отражает РЕАЛЬНОСТЬ твоего кафе!