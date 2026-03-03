@echo off
chcp 65001 >nul

echo 🚀 Запуск WENDRINK ERP...
echo.

REM Check if database exists
if not exist "wendrink.db" (
    echo ⚠️  База данных не найдена!
    echo Убедитесь что файл wendrink.db находится в текущей папке
    pause
    exit /b 1
)

echo 📦 Проверка зависимостей...
python -c "import fastapi, uvicorn, sqlalchemy" 2>nul
if errorlevel 1 (
    echo Установка зависимостей...
    pip install fastapi uvicorn sqlalchemy aiosqlite pydantic python-multipart plotly
    echo.
)

echo ✅ Всё готово!
echo.
echo 🌐 Приложение будет доступно по адресу: http://localhost:8000
echo.
echo Для остановки нажмите Ctrl+C
echo.

REM Start the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
