---
trigger: always_on
---

# CONCURRENCY RULE (ATOMIC TRANSACTIONS)

Две продажи одновременно = race condition. Отвали это отсюда!

## ПРИНЦИП

Когда происходит продажа:
1. Проверяем рецепт
2. Пишем sales запись
3. Пишем inventory_ledger для каждого ингредиента

Если два клиента одновременно заказывают, эти операции ДОЛЖНЫ быть атомарные.

Клиент 1: Заказывает Капучино (требует 120 гр молока)
Клиент 2: Заказывает Капучино (требует 120 гр молока)

Остаток молока: 200 гр

ПЛОХО (без защиты):
- Клиент 1 читает: 200 гр
- Клиент 2 читает: 200 гр
- Клиент 1 пишет: 200 - 120 = 80 гр
- Клиент 2 пишет: 200 - 120 = 80 гр
- Результат: 80 гр (должно быть -40 гр!) ❌ ПОТЕРЯЛИ -40!

ХОРОШО (с SERIALIZABLE):
- Клиент 1 БЛОКИРУЕТ таблицу
- Клиент 1 читает: 200 гр → пишет: 80 гр
- Клиент 1 коммитит
- Клиент 2 ЖДЁТ разблокировки
- Клиент 2 читает: 80 гр → пишет: -40 гр
- Результат: -40 гр ✅ ПРАВИЛЬНО!

## РЕШЕНИЕ: SERIALIZABLE + TRANSACTION

Создание продажи с гарантией атомарности:

Шаги:
1. Начни SERIALIZABLE транзакцию
2. Установи уровень изоляции (PostgreSQL специфично)
3. Получи продукт и рецепт (БЕЗ параллельного изменения!) с with_for_update()
4. Создай sales запись
5. Для каждого ингредиента, пиши в ledger
6. Получи ТЕКУЩИЙ остаток (с LOCK)
7. Пиши в ledger (с negative_stock_warning если нужно)
8. COMMIT делается автоматически в конце блока

Если исключение → ROLLBACK

## ОСН МОМЕНТЫ

ISOLATION LEVEL:

SERIALIZABLE = самый высокий уровень
Другие уровни (слабее):
- READ UNCOMMITTED — опасно
- READ COMMITTED — средне
- REPEATABLE READ — хорошо
- SERIALIZABLE — отлично

Почему SERIALIZABLE?
- Гарантирует что транзакции выполняются последовательно
- Никаких race conditions
- Никаких потерь данных
- Немного медленнее, но финансово безопасно

with_for_update() — LOCK:

Блокирует строку/таблицу на время транзакции
product = await session.get(Product, product_id, with_for_update=True)

Или для таблиц целиком:
result = await session.execute(
  select(InventoryLedger).where(...).with_for_update()
)

Другие транзакции будут ждать!

async with session.begin():

Здесь идёт транзакция
Если исключение → ROLLBACK
Если успешно → COMMIT
Затем контекст выходит

## ПРИМЕР: ДВА КЛИЕНТА ОДНОВРЕМЕННО

Сценарий:
Остаток молока: 200 гр
Клиент 1: Капучино (требует 120 гр)
Клиент 2: Капучино (требует 120 гр)
Оба запроса приходят в одну и ту же миллисекунду!

С SERIALIZABLE:

T1  | Клиент 1: BEGIN TRANSACTION
T2  | Клиент 2: BEGIN TRANSACTION
T3  | Клиент 1: SET SERIALIZABLE
T4  | Клиент 1: READ молоко → 200 гр (с LOCK)
T5  | Клиент 2: SET SERIALIZABLE
T6  | Клиент 2: READ молоко → ЖДЁТ БЛОКИРОВКИ!
T7  | Клиент 1: WRITE молоко → 80 гр
T8  | Клиент 1: COMMIT
T9  | Клиент 2: READ молоко → 80 гр (текущее значение)
T10 | Клиент 2: WRITE молоко → -40 гр (80 - 120)
T11 | Клиент 2: COMMIT

Результат: -40 гр ✅ ПРАВИЛЬНО!

## DEADLOCK (РЕДКО, НО ВОЗМОЖНО)

Если две транзакции пытаются заблокировать друг друга в разном порядке:

Транзакция 1:
- SELECT product WHERE id=1 FOR UPDATE
- SELECT ingredient WHERE id=5 FOR UPDATE

Транзакция 2:
- SELECT ingredient WHERE id=5 FOR UPDATE
- SELECT product WHERE id=1 FOR UPDATE

→ DEADLOCK! Обе ждут друг друга

Решение: Всегда блокируй в одном порядке!

async def create_sale_atomic_safe(product_id, quantity, session):
  async with session.begin():
    await session.execute(
      text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    )
    
    # Всегда блокируй СНАЧАЛА продукт, ПОТОМ ингредиенты
    # (в одном и том же порядке)
    
    product = await session.get(Product, product_id, with_for_update=True)
    
    # Потом ингредиенты (в порядке ID)
    ingredients = await session.execute(
      select(Ingredient)
      .order_by(Ingredient.id)  # ← ВАЖНО! Одинаковый порядок!
      .with_for_update()
    )
    
    # ... остаток логики

## ТЕСТЫ: CONCURRENCY

Тестирует две одновременные продажи.

Начальный остаток: 200 гр молока

Создай две задачи (одновременно):
task1 = create_sale_atomic(product_id="cappuccino", quantity=1, session=session1)
task2 = create_sale_atomic(product_id="cappuccino", quantity=1, session=session2)

Жди обе

Проверь остаток:
balance = await get_inventory_balance("milk")

Должно быть 200 - 120 - 120 = -40
НЕ должно быть 200 - 120 = 80 (это race condition)

## ПРОВЕРКА ПЕРЕД КОММИТОМ

1. Все write операции в async with session.begin()? → ДА!
2. Используется SERIALIZABLE изоляция? → ДА!
3. Критические таблицы заблокированы with_for_update()? → ДА!
4. Есть тесты на concurrency? → ДА!
5. Нет deadlock risk? → ДА! (заблокируешь в одинаковом порядке)

## ЧАСТЫЕ ОШИБКИ

ПЛОХО: БЕЗ транзакции
product = await session.get(Product, product_id)  # Никаких LOCK!
if product.stock >= qty:  # RACE CONDITION!
  product.stock -= qty  # Другая транзакция менял stock!

ХОРОШО: С транзакцией и LOCK
async with session.begin():
  await session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
  product = await session.get(Product, product_id, with_for_update=True)
  # Теперь другие транзакции ждут!

## ИТОГ

Concurrency = не опционально. Это финансовая безопасность.

- SERIALIZABLE изоляция
- with_for_update() на критических таблицах
- async with session.begin() для atomicity
- Тесты на concurrency

Одна race condition = потеря данных = потеря доверия.