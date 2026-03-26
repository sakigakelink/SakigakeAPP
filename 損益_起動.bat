@echo off
chcp 65001 >nul
title 損益計算表アプリ
cd /d "%~dp0損益"

echo ========================================
echo   損益計算表アプリ 起動中...
echo   http://localhost:5002
echo ========================================
echo.

C:\Python314\python.exe -c "import flask" 2>nul || C:\Python314\python.exe -m pip install -q flask pdfplumber pandas openpyxl

start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5002"

C:\Python314\python.exe app.py
pause
