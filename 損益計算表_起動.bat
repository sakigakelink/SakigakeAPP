@echo off
chcp 65001 >nul
title 損益計算表アプリ
cd /d "%~dp0損益計算表"

echo ========================================
echo   損益計算表アプリ 起動中...
echo   http://localhost:5002
echo ========================================
echo.

echo [1/2] パッケージ確認中...
C:\Users\Mining-Base\AppData\Local\Python\bin\python.exe -m pip install -q flask pdfplumber pandas openpyxl 2>nul
echo       完了

echo [2/2] サーバー起動中...
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5002"

C:\Users\Mining-Base\AppData\Local\Python\bin\python.exe app.py
pause
