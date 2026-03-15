@echo off
cd /d "%~dp0"
echo ========================================
echo   Sakigake Shift
echo   http://localhost:5000/
echo ========================================
echo.
echo  [!] 通常は デスクトップの「Sakigake Shift」から起動してください
echo      ショートカット未作成の場合: create_shortcut.vbs をダブルクリック
echo.
C:\Users\Mining-Base\AppData\Local\Python\bin\python.exe app.py
pause
