@echo off
chcp 65001 >nul
title シフト管理アプリ
cd /d "%~dp0シフト管理"

echo ========================================
echo   シフト管理アプリ 起動中...
echo   http://localhost:5000/
echo ========================================
echo.

C:\Users\Mining-Base\AppData\Local\Python\bin\python.exe app.py
pause
