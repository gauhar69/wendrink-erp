# WENDRINK ERP - Правила для ИИ-ассистента

## 🎯 О проекте
WENDRINK ERP - система управления кафе/баром в Алматы, Казахстан.
Стек: FastAPI + SQLAlchemy (async) + SQLite + Jinja2 + Plotly.js
Валюта: тенге (₸). Timezone: Asia/Almaty. Business day cutoff: 06:00.

## 🚨 КРИТИЧЕСКИЕ ПРАВИЛА (НЕ НАРУШАТЬ!)

### 1. НИКОГДА не трогай рабочий код без плана
- Перед ЛЮБЫМ изменением: опиши ЧТО меняешь, ЗАЧЕМ, и ЧТО может сломаться
- Покажи план пользователю ПЕРЕД началом работы
- Не добавляй фичи которые не просили

### 2. НИКОГДА не устанавливай новые пакеты без разрешения
- Все зависимости в requirements.txt - СВЯЩЕННЫЕ
- Хочешь добавить пакет? СПРОСИ сначала
- Используй ТОЛЬКО то что уже установлено

### 3. НИКОГДА не меняй структуру базы данных без миграции
- Все изменения БД через Alembic миграции
- Бэкап перед любыми изменениями в БД
- Проверь что миграция обратима

### 4. Один файл = одно изменение
- Не меняй 5 файлов одновременно
- Изменил → проверил → работает → следующий файл
- Если что-то сломал - СРАЗУ откатывай

### 5. ВСЕГДА проверяй после изменений
- Запусти verify.py после каждого изменения
- Проверь что сервер стартует без ошибок
- Проверь что основные endpoints отвечают

## 📋 ПАМЯТЬ ОШИБОК (PATCHES)

**ИТОГО: 8 патчей** (последний аудит: 2026-02-19, 48✅ / 0❌)

### PATCH-001: Payroll не аллоцирует fixed costs
- **Дата:** 2026-02-18
- **Проблема:** Endpoint /finance/payroll сохранял зарплату но НЕ вызывал allocate_daily_fixed_costs()
- **Результат:** OPEX показывал только зарплату без аренды/интернета
- **Фикс:** Добавлен вызов await service.allocate_daily_fixed_costs(data.business_date) в finance.py
- **Правило:** При сохранении payroll ВСЕГДА аллоцировать fixed costs

### PATCH-002: Database journal lock
- **Дата:** 2026-02-18
- **Проблема:** wendrink.db-journal блокировал базу, вызывая "disk I/O error"
- **Результат:** Все операции с БД падали
- **Фикс:** Перезапуск сервера (journal файл удаляется автоматически)
- **Правило:** При ошибке "disk I/O" - первым делом проверить наличие .journal файла

### PATCH-003: savePayroll() глотает ошибки
- **Дата:** 2026-02-18
- **Проблема:** try/catch в savePayroll() скрывал ошибки от пользователя
- **Результат:** Пользователь думал что данные сохранены, но они не сохранялись
- **Фикс:** Убран try/catch, добавлена проверка response.ok с throw Error
- **Правило:** НИКОГДА не глотать ошибки молча. Всегда показывать пользователю

### PATCH-004: Кнопка Excel экспорта ломала сервер
- **Дата:** 2026-02-19
- **Проблема:** Добавление кнопки "Скачать Excel" в рецепты потребовало новые пакеты и сложный endpoint
- **Результат:** Сервер не запускался, конфликт зависимостей
- **Фикс:** Полный откат - удалена кнопка, endpoint, импорты. Excel создан через отдельный скрипт
- **Правило:** НЕ ДОБАВЛЯТЬ endpoints требующие новые пакеты. Использовать отдельные скрипты

### PATCH-005: venv создан для Windows, запуск на Linux невозможен
- **Дата:** 2026-02-19
- **Проблема:** venv содержит Scripts/python.exe (Windows), Linux VM не может запустить
- **Результат:** Невозможно запустить сервер из Linux VM
- **Правило:** Для операций с сервером - давать команды пользователю для запуска в PowerShell

### PATCH-006: Stocktake list_stocktakes → 500 (lazy loading items)
- **Дата:** 2026-02-19
- **Проблема:** Endpoint GET /stocktake → 500. В `list_stocktakes()` запрос БЕЗ `selectinload(Stocktake.items)`, но API обращался к `s.items` → async lazy loading краш
- **Результат:** Невозможно получить список инвентаризаций
- **Фикс:** Добавлен `.options(selectinload(Stocktake.items))` в запрос
- **Правило:** В async SQLAlchemy ВСЕГДА загружать relationships через `selectinload()` если к ним обращаешься в коде

### PATCH-007: Payroll endpoint возвращал dict вместо None → 500
- **Дата:** 2026-02-19
- **Проблема:** GET /finance/payroll/{date} имел `response_model=DailyPayrollResponse | None`, но возвращал `dict` когда нет данных → FastAPI не мог сериализовать
- **Результат:** 500 ошибка при запросе payroll за дату без данных
- **Фикс:** Возвращать `None` вместо `{"message": "No payroll found"}`
- **Правило:** Если `response_model` включает `| None`, возвращать `None`, НЕ dict с сообщением

### PATCH-008: ingredient-usage chart → 500 (UUID строки в .in_())
- **Дата:** 2026-02-19
- **Проблема:** В `get_ingredient_usage_chart()` UUID строки передавались в `.in_()` → SQLAlchemy не мог сравнить строки с UUID колонкой
- **Результат:** GET /charts/ingredient-usage → 500
- **Фикс:** Добавлена конвертация `[uuid_mod.UUID(uid) for uid in top_ingredients.keys()]`
- **Правило:** UUID строки ВСЕГДА конвертировать в `uuid.UUID()` перед использованием в SQLAlchemy фильтрах

## 📁 СТРУКТУРА ПРОЕКТА

```
super-app-cost-calc/
├── app/
│   ├── api/           # API endpoints (FastAPI routers)
│   │   ├── finance.py     # Payroll, OPEX, fixed costs
│   │   ├── reports.py     # P&L, COGS variance, product costs
│   │   ├── sales.py       # Sales CRUD
│   │   ├── recipes.py     # Recipe CRUD
│   │   ├── inventory.py   # Inventory movements
│   │   ├── ingredients.py # Ingredients CRUD
│   │   ├── products.py    # Products CRUD
│   │   ├── analytics.py   # Analytics & forecasting
│   │   ├── charts.py      # Chart data endpoints
│   │   ├── stocktake.py   # Inventory counting
│   │   └── verification.py # Data verification
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # Business logic
│   │   └── inventory.py   # WAC, stock balance, COGS
│   ├── templates/
│   │   └── dashboard.html # Main UI (single page app)
│   └── main.py        # FastAPI app entry point
├── alembic/           # Database migrations
├── wendrink.db        # SQLite database (PRODUCTION DATA!)
├── requirements.txt   # Dependencies (DO NOT MODIFY without permission)
└── venv/              # Virtual environment (Windows)
```

## 🔑 КЛЮЧЕВЫЕ БИЗНЕС-ПРАВИЛА

### COGS (Себестоимость)
- Theoretical COGS = SUM(recipe.quantity × WAC) для каждого проданного продукта
- Actual COGS = SUM(inventory_ledger WHERE event_type='SALE')
- Variance = (Actual - Theoretical) / Theoretical × 100
- Допустимый порог: < 3%

### OPEX (Операционные расходы)
- Fixed costs: 404,350₸/месяц ÷ дней в месяце = ежедневный расход
- Категории: RENT, SECURITY, INTERNET, UTILITIES, OTHER
- Payroll: отдельная категория SALARY
- OPEX за день = fixed costs + salary

### WAC (Средневзвешенная стоимость)
- WAC = (старый_остаток × старый_WAC + новая_поставка × новая_цена) / (старый_остаток + новая_поставка)
- Используется для расчёта COGS при продаже

### Business Date
- Almaty timezone (UTC+5)
- Cutoff: 06:00 (продажи после полуночи до 06:00 = предыдущий день)

## ⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ

1. SQLite - однопользовательская запись (no concurrent writes)
2. venv создан для Windows - Linux VM не может запустить сервер
3. Dashboard.html - монолитный файл (~2500 строк) - изменения аккуратно!
4. Нет аутентификации - любой с URL может зайти
5. Нет бэкапов БД по расписанию

## 🛡️ ЧЕКЛИСТ ПЕРЕД ИЗМЕНЕНИЕМ

- [ ] Описал что меняю и зачем
- [ ] Проверил PATCHES - нет ли похожей ошибки в истории
- [ ] Сделал бэкап БД если трогаю данные
- [ ] Изменил ОДИН файл за раз
- [ ] Проверил что сервер стартует
- [ ] Проверил что UI отображается
- [ ] Обновил PATCHES если нашёл новую проблему
