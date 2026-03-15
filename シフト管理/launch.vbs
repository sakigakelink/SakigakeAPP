Set FSO = CreateObject("Scripting.FileSystemObject")
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """C:\Users\Mining-Base\AppData\Local\Python\bin\pythonw.exe"" """ & strDir & "\app.py""", 0, False
