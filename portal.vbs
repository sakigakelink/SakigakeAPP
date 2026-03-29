Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ws.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)

' 前回のサーバーをPIDファイルで停止
Dim pidFile: pidFile = ws.CurrentDirectory & "\server.pid"
If fso.FileExists(pidFile) Then
    Dim oldPid: oldPid = Trim(fso.OpenTextFile(pidFile).ReadAll())
    If oldPid <> "" Then ws.Run "cmd /c taskkill /f /pid " & oldPid & " >nul 2>&1", 0, True
End If
WScript.Sleep 500

' サーバーを非表示で起動しPIDを保存
ws.Run "cmd /c powershell -NoProfile -Command """ & _
    "$p = Start-Process -PassThru -WindowStyle Hidden " & _
    "-FilePath 'C:\Python314\python.exe' " & _
    "-ArgumentList 'app.py','--no-browser' " & _
    "-WorkingDirectory '" & ws.CurrentDirectory & "'; " & _
    "$p.Id | Set-Content '" & pidFile & "'""", 0, True
WScript.Sleep 2000

' Chromeアプリモードで起動
ws.Run """C:\Program Files\Google\Chrome\Application\chrome.exe"" --app=http://localhost:5000/", 0, False
