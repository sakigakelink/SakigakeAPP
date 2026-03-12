@echo off
chcp 65001 >nul
title TKC Monthly Analyzer
cd /d "%~dp0"

echo ================================
echo   TKC Monthly Analyzer 起動中...
echo ================================
echo.

REM 依存パッケージ確認・インストール
echo [1/2] パッケージ確認中...
C:\Users\Mining-Base\AppData\Local\Python\bin\python.exe -m pip install -q flask pdfplumber pandas openpyxl 2>nul
echo       完了

echo [2/2] サーバー起動中...
echo.
echo   ブラウザで http://localhost:5002 を開きます
echo   終了するにはこのウィンドウを閉じてください
echo.

REM 2秒後にブラウザを開く
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5002"

C:\Users\Mining-Base\AppData\Local\Python\bin\python.exe app.py
pause
