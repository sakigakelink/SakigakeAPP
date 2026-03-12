@echo off
chcp 65001 >nul
title 入院収益レポート生成
cd /d "%~dp0診療報酬"

echo ========================================
echo   入院収益レポート 生成中...
echo ========================================
echo.

echo パッケージ確認中...
C:\Users\Mining-Base\AppData\Local\Python\bin\python.exe -m pip install -q pdfplumber openpyxl 2>nul
echo 完了
echo.

C:\Users\Mining-Base\AppData\Local\Python\bin\python.exe inpatient_report.py
echo.
echo 処理が完了しました。
pause
