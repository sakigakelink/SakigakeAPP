@echo off
chcp 65001 >nul
title シフト管理アプリ
cd /d "%~dp0シフト"

echo ========================================
echo   シフト管理アプリ 起動中...
echo   http://localhost:5000/
echo ========================================
echo.

C:\Python314\python.exe app.py
pause
