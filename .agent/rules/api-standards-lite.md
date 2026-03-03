---
trigger: always_on
---

# API STANDARDS (SIMPLIFIED FOR MVP)

API = договор между фронтом и бэком. Договор должен быть чётким.

## БАЗОВЫЕ ПРАВИЛА

1. Все endpoints возвращают JSON
2. Статус коды имеют смысл (200, 400, 409, 422)
3. Ошибки структурированы (не просто текст)
4. Все I/O через validators

## HTTP STATUS CODES

200 OK — успешная операция
- GET /daily-pnl/2026-01-27 → 200 (нашли данные)
- POST /sale → 200 (создали продажу)

400 Bad Request — клиент отправил мусор
- POST /sale with invalid JSON → 400
- POST /sale with missing fields → 400

409 Conflict — обработка конфликта
- POST /sale for non-existent product → 409
- POST /supply with invalid ingredient → 409

422 Unprocessable Entity — валидация не прошла
- POST /sale with negative quantity → 422
- POST /supply with invalid price → 422

500 Internal Server Error — ошибка сервера (не отправляй!)
- Если есть исключение → лог + ответ 500

## PYDANTIC VALIDATORS

Валидируй входные данные через Pydantic.

CreateSaleRequest:
- product_id: UUID string
- quantity: Decimal (positive, not too large)

Validators:
- product_id должна быть валидный UUID
- quantity должна быть > 0
- quantity не должна быть слишком большая (>999999)

CreateSupplyRequest:
- ingredient_id: UUID string
- quantity: Decimal (positive)
- total_price: Decimal (positive)

Validators:
- ingredient_id должна быть валидный UUID
- quantity должна быть > 0
- total_price должна быть > 0

## FASTAPI ROUTES

Примеры endpoints:

POST /sale — создаёт продажу
- Input: product_id, quantity
- Output: {status, id, total_amount, business_date}
- Errors: 400 (bad input), 409 (conflict), 422 (validation)

POST /supply — добавляет приход товара
- Input: ingredient_id, quantity, total_price
- Output: {status, id, quantity, unit_price}
- Errors: 400, 409, 422

POST /correction — исправляет ошибку
- Input: ingredient_id, change_amount, cost_snapshot, reason
- Output: {status, id, event_type}
- Errors: 400, 409, 422

GET /daily-pnl/{date} — P&L за день
- Input: date (YYYY-MM-DD)
- Output: {date, revenue, cogs, gross_profit, margin_percent}
- Errors: 400 (bad format)

GET /inventory/{date} — остатки на дату
- Input: date (YYYY-MM-DD)
- Output: {date, items: [{ingredient_id, name, balance, unit}]}
- Errors: 400 (bad format)

GET /top-products/{date} — ТОП продуктов
- Input: date (YYYY-MM-DD), limit (1-100)
- Output: {date, products: [{product_id, name, qty, revenue, cogs}]}
- Errors: 400 (bad format), 422 (limit out of range)

## RESPONSE FORMATS

Успех:
{
  "status": "success",
  "id": "...",
  "data": {...}
}

Ошибка (4xx):
{
  "status": "error",
  "message": "Product not found",
  "code": 409
}

Ошибка (5xx):
{
  "status": "error",
  "message": "Internal server error"
}

## ПРОВЕРКА ПЕРЕД КОММИТОМ

1. ВСЕ endpoints возвращают JSON? → ДА!
2. Статус коды правильные? → ДА!
3. Pydantic validators на входе? → ДА!
4. Exception handlers правильные? → ДА!
5. Decimal сериализуется как строка? → ДА!
6. UUID сериализуется как строка? → ДА!
7. Документация (docstrings)? → ДА!

## ИТОГ

API = договор. Договор должен быть понятным и безопасным.

- Валидация на входе (Pydantic)
- Правильные статус коды
- Структурированные ошибки
- Полная сериализация (Decimal → string, UUID → string)