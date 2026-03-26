@echo off
chcp 65001 >nul
title 給与分析アプリ
cd /d "%~dp0給与"

echo ========================================
echo   給与分析アプリ 起動中...
echo   http://localhost:5001
echo ========================================
echo.

C:\Python314\python.exe -c "import flask" 2>nul || C:\Python314\python.exe -m pip install -q flask flask-cors pdfplumber

C:\Python314\python.exe app.py
pause
