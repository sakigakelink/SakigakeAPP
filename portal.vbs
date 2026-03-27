Set ws = CreateObject("WScript.Shell")
ws.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
ws.Run "cmd /c taskkill /f /fi ""WINDOWTITLE eq SakigakeAPP-Server"" >nul 2>&1", 0, True
WScript.Sleep 500
ws.Run "cmd /c title SakigakeAPP-Server && C:\Python314\python.exe app.py --no-browser", 0, False
WScript.Sleep 1500
ws.Run "http://localhost:5000/", 0, False
