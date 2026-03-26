@echo off
chcp 65001 >nul
title 薬剤レポート生成
cd /d "%~dp0診療"

echo ========================================
echo   薬剤レポート 生成中...
echo ========================================
echo.

C:\Python314\python.exe -c "import pdfplumber" 2>nul || C:\Python314\python.exe -m pip install -q pdfplumber openpyxl

C:\Python314\python.exe pharmacy_report.py
echo.
echo 処理が完了しました。
pause
