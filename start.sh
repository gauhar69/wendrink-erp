#!/bin/bash

echo "🚀 Запуск WENDRINK ERP..."
echo ""

# Check if packages are installed
if ! python3 -c "import fastapi, uvicorn, sqlalchemy" 2>/dev/null; then
    echo "📦 Установка зависимостей..."
    pip install fastapi uvicorn sqlalchemy aiosqlite pydantic python-multipart plotly
    echo ""
fi

# Check if database exists
if [ ! -f "wendrink.db" ]; then
    echo "⚠️  База данных не найдена!"
    echo "Убедитесь что файл wendrink.db находится в текущей папке"
    exit 1
fi

echo "✅ Всё готово!"
echo ""
echo "🌐 Приложение будет доступно по адресу: http://localhost:8000"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

# Start the server
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
