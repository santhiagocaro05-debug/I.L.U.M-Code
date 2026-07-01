' ILUM AI - Launcher with admin elevation and startup diagnostics
Option Explicit

Function IsAdmin()
    On Error Resume Next
    Dim shell
    Set shell = CreateObject("WScript.Shell")
    shell.RegRead "HKEY_USERS\S-1-5-19\Environment\TEMP"
    IsAdmin = (Err.Number = 0)
    Err.Clear
    On Error GoTo 0
    Set shell = Nothing
End Function

Dim shellApp
If Not IsAdmin() Then
    Set shellApp = CreateObject("Shell.Application")
    shellApp.ShellExecute "wscript.exe", Chr(34) & WScript.ScriptFullName & Chr(34), "", "runas", 1
    Set shellApp = Nothing
    WScript.Quit 0
End If

Dim ws, fso, d, py, target, installer, cmd
Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
d = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
ws.CurrentDirectory = d

py = d & ".venv\Scripts\pythonw.exe"
If Not fso.FileExists(py) Then
    py = d & ".venv\Scripts\python.exe"
End If

If Not fso.FileExists(py) Then
    installer = d & "Instalar_ILUM.bat"
    If fso.FileExists(installer) Then
        MsgBox "ILUM AI necesita instalar dependencias antes del primer inicio. Se abrira el instalador.", 64, "ILUM AI"
        Set shellApp = CreateObject("Shell.Application")
        shellApp.ShellExecute installer, "", d, "runas", 1
        Set shellApp = Nothing
    Else
        MsgBox "No se encontro .venv ni Instalar_ILUM.bat. Descarga el repo completo y ejecuta el instalador.", 16, "ILUM AI"
    End If
    WScript.Quit 1
End If

target = d & "launch_ilum.py"
If Not fso.FileExists(target) Then
    target = d & "main.py"
End If

cmd = Chr(34) & py & Chr(34) & " " & Chr(34) & target & Chr(34)
ws.Run cmd, 1, False

Set ws = Nothing
Set fso = Nothing
