Option Explicit

Dim fso, shell, scriptDir, pythonwPath, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonwPath = scriptDir & "\.venv\Scripts\pythonw.exe"

If fso.FileExists(pythonwPath) Then
    cmd = "\"" & pythonwPath & "\" -m oledwall.cli gui"
Else
    cmd = "pythonw -m oledwall.cli gui"
End If

shell.CurrentDirectory = scriptDir
shell.Run cmd, 0, False
