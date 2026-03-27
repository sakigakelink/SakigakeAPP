@echo off
chcp 65001 >nul
title SakigakeAPP 統合ポータル
cd /d "%~dp0"

echo ========================================
echo   SakigakeAPP 統合ポータル 起動中...
echo   http://localhost:5000/
echo ========================================
echo.

C:\Python314\python.exe app.py
pause
