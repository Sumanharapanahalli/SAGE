' SAGE[ai] Silent Launcher
' Starts backend + frontend with zero visible windows, then opens the browser.

Option Explicit

Dim WshShell, fso, dir

Set WshShell = CreateObject("WScript.Shell")
Set fso     = CreateObject("Scripting.FileSystemObject")

' Resolve the directory this script lives in
dir = fso.GetParentFolderName(WScript.ScriptFullName)

' Create logs directory if it doesn't exist
If Not fso.FolderExists(dir & "\logs") Then
    fso.CreateFolder(dir & "\logs")
End If

' ── Start backend with --reload so code changes take effect automatically ──
WshShell.Run "cmd /c cd /d """ & dir & """ && " & _
             """.venv\Scripts\python.exe"" src\main.py api --reload " & _
             ">> """ & dir & "\logs\backend.log"" 2>&1", _
             0, False

' ── Start frontend (hidden window = 0, don't wait = False) ────────────────
WshShell.Run "cmd /c cd /d """ & dir & "\web"" && npm run dev " & _
             ">> """ & dir & "\logs\frontend.log"" 2>&1", _
             0, False

' ── Wait 6 seconds for servers to be ready ────────────────────────────────
WScript.Sleep 6000

' ── Open browser ──────────────────────────────────────────────────────────
WshShell.Run "http://localhost:5173"
