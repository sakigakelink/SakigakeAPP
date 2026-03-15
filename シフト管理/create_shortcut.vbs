Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

strDesktop = WshShell.SpecialFolders("Desktop")
strAppDir = FSO.GetParentFolderName(WScript.ScriptFullName)
strTarget = strAppDir & "\launch.vbs"
strIcon = strAppDir & "\app.ico"

' Delete old shortcut first
strOld = strDesktop & "\Sakigake Shift.lnk"
If FSO.FileExists(strOld) Then FSO.DeleteFile strOld, True

' Force rebuild Windows icon cache
strLocal = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
WshShell.Run "cmd /c taskkill /f /im explorer.exe & del /f /a """ & strLocal & "\IconCache.db"" 2>nul & del /f /a /s """ & strLocal & "\Microsoft\Windows\Explorer\iconcache*"" 2>nul & start explorer.exe", 0, True
WScript.Sleep 2000

' Create shortcut
strShortcut = strDesktop & "\Sakigake Shift.lnk"
Set oShortcut = WshShell.CreateShortcut(strShortcut)
oShortcut.TargetPath = "wscript.exe"
oShortcut.Arguments = """" & strTarget & """"
oShortcut.WorkingDirectory = strAppDir
oShortcut.Description = "Sakigake Shift"
oShortcut.IconLocation = strIcon & ",0"
oShortcut.WindowStyle = 7
oShortcut.Save

MsgBox "Done. Shortcut created.", vbInformation, "Sakigake Shift"
