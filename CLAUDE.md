# WENDRINK ERP - Правила для ИИ-ассистента

## 🎯 О проекте
WENDRINK ERP - система управления кафе/баром в Алматы, Казахстан.
Стек: FastAPI + SQLAlchemy (async) + SQLite + Jinja2 + Plotly.js
Валюта: тенге (₸). Timezone: Asia/Almaty. Business day cutoff: 06:00.

## 🖥️ ИНФРАСТРУКТУРА (читать при каждом старте)

| Параметр | Значение |
|----------|----------|
| Продакшн URL | https://n8n-483921.gripe/dashboard |
| Сервер IP | 80.225.201.64 |
| SSH пользователь | ubuntu |
| SSH ключ | C:\Users\ARMAN\.ssh\wendrink_new ✅ РАБОТАЕТ (добавлен на сервер 02.05.2026) |
| Папка на сервере | ~/wendrink-erp |
| Папка на ПК | C:\Users\ARMAN\super-app-cost-calc |
| GitHub репо | https://github.com/gauhar69/wendrink-erp (private) |
| GitHub аккаунт | gauhar69 |
| GitHub PAT | ghp_************************************ |

### Быстрый деплой (основной способ)
```
ssh -i C:\Users\ARMAN\.ssh\wendrink_new ubuntu@80.225.201.64 "cd ~/wendrink-erp && git pull && sudo docker compose -f docker-compose.prod.yml up -d --build"
```

### Восстановление доступа если SSH ключ утерян (через Oracle Bastion)
1. Сгенерируй новый ключ на ПК локально: `ssh-keygen -t ed25519 -f C:\Users\ARMAN\.ssh\wendrink_new -N ""`
2. Открой https://cloud.oracle.com → меню **☰** → **Identity & Security** → **Bastion**.
3. Зайди в свой бастион (например, `recovery-bastion`) → Вкладка **Sessions** → **Create session**.
4. Выбери: **Managed SSH session**, Username: `ubuntu`, Compute instance: `n8n-server`.
5. В разделе SSH key выбери **Choose SSH key file** и загрузи публичный ключ с ПК (например, `wendrink_new.pub`).
6. Дождись статуса **Active** (зеленый). Скопируй **SSH command** (через три точки справа).
7. Замени в команде `<privateKey>` на путь к приватному ключу на твоем ПК (`C:\Users\ARMAN\.ssh\wendrink_new`) и выполни её в **PowerShell**.
8. Войдя на сервер (увидишь `ubuntu@n8n-server:~$`), пропиши свой публичный ключ навсегда:
   `echo "ssh-ed25519 ТВОЙ_ПУБЛИЧНЫЙ_КЛЮЧ" >> ~/.ssh/authorized_keys`
9. Теперь можешь входить напрямую: `ssh -i C:\Users\ARMAN\.ssh\wendrink_new ubuntu@80.225.201.64`

## 📦 УСТАНОВЛЕННЫЕ СКИЛЛЫ (май 2026)
- `ui-ux-pro-max` — 161 палитра, 57 пар шрифтов, 50+ стилей UI
- `frontend-design` — правила типографики, spacing, анимаций
- Путь: C:\Users\ARMAN\.claude\skills\ и C:\Users\ARMAN\super-app-cost-calc\.claude\skills\

## 🔄 ТЕКУЩИЙ СТАТУС ЗАДАЧ (май 2026)

| Задача | Статус | Примечание |
|--------|--------|------------|
| PATCH-010: двойная инвентаризация | ✅ ИСПРАВЛЕНО | fix_double_stocktake.py запущен, UI кнопки разделены |
| PDF экспорт мобильный Firefox | ✅ ЗАДЕПЛОЕНО | git pull + rebuild выполнен 02.05.2026, коммит ada3d89 |
| SSH ключ | ✅ ВОССТАНОВЛЕН | C:\Users\ARMAN\.ssh\wendrink_new добавлен через Oracle Bastion 02.05.2026 |

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

**ИТОГО: 10 патчей** (последний аудит: 2026-04-10)

### PATCH-010: Двойное применение инвентаризации (кнопки UI)
- **Дата:** 2026-04-10
- **Проблема:** В форме инвентаризации показывались все 3 кнопки одновременно: "Сохранить", "Завершить" (→ /complete) и "Применить к остаткам" (→ /reapply). Обе последние кнопки применяют корректировки к остаткам. Нажатие обеих = двойное списание
- **Результат:** 09.04.2026 все 38 ингредиентов списаны дважды. Бэкап: wendrink_backup_20260410_154402.db. Исправлено скриптом fix_double_stocktake.py
- **Фикс:** В dashboard.html кнопки разделены по статусу: DRAFT → только "Сохранить" + "Завершить"; COMPLETED → только "Применить к остаткам"
- **Правило:** Кнопки меняющие статус и кнопки применяющие данные НИКОГДА не должны показываться одновременно

### PATCH-009: current_price не обновлялся при приходе товара
- **Дата:** 2026-04-03
- **Проблема:** При записи прихода (SUPPLY) `ingredient.current_price` не обновлялся. Заявка и Цены сырья всегда показывали старую цену из справочника
- **Результат:** Пользователь видел неактуальные цены в Заявке даже после нового прихода
- **Фикс:** В `record_supply()` и `create_bulk_supply()` добавлено автообновление `ingredient.current_price = unit_cost`
- **Правило:** При каждом SUPPLY событии ВСЕГДА обновлять `ingredient.current_price`

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
