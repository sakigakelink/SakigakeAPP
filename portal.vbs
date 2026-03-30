Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ws.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
ws.Run "cmd /c taskkill /f /fi ""WINDOWTITLE eq SakigakeAPP-Server"" >nul 2>&1", 0, True
WScript.Sleep 500
ws.Run "cmd /c title SakigakeAPP-Server && C:\Python314\python.exe app.py --no-browser", 0, False
WScript.Sleep 1500
chrome = ""
If fso.FileExists("C:\Program Files\Google\Chrome\Application\chrome.exe") Then
  chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
ElseIf fso.FileExists("C:\Program Files (x86)\Google\Chrome\Application\chrome.exe") Then
  chrome = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
End If
If chrome <> "" Then ws.Run """" & chrome & """ --app=http://localhost:5000/ --start-maximized", 0, False
