@echo off
chcp 65001 >nul
title 給与分析アプリ
cd /d "%~dp0"

echo ================================
echo   給与分析アプリ 起動中...
echo ================================
echo.

echo [1/2] パッケージ確認中...
C:\Users\Mining-Base\AppData\Local\Python\bin\python.exe -m pip install -q flask flask-cors pdfplumber 2>nul
echo       完了

echo [2/2] サーバー起動中...
echo.
echo   ブラウザで http://localhost:5001 を開きます
echo   終了するにはこのウィンドウを閉じてください
echo.

C:\Users\Mining-Base\AppData\Local\Python\bin\python.exe app.py
pause
