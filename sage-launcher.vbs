' SAGE[ai] Silent Launcher
' Starts backend + frontend with zero visible windows, then opens the browser.
' If SAGE is already running (port 8000 in use), just opens the browser.

Option Explicit

Dim WshShell, fso, dir, http, status, elapsed

Set WshShell = CreateObject("WScript.Shell")
Set fso      = CreateObject("Scripting.FileSystemObject")

' Resolve the directory this script lives in
dir = fso.GetParentFolderName(WScript.ScriptFullName)

' Create logs directory if it doesn't exist
If Not fso.FolderExists(dir & "\logs") Then
    fso.CreateFolder(dir & "\logs")
End If

' ── Check if backend is already running ────────────────────────────────────
If IsPortOpen("127.0.0.1", 8000) Then
    WshShell.Run "http://localhost:5173"
    WScript.Quit
End If

' ── Start backend (no --reload for regular use — faster start, one process) ─
WshShell.Run "cmd /c cd /d """ & dir & """ && " & _
             """.venv\Scripts\python.exe"" src\main.py api " & _
             ">> """ & dir & "\logs\backend.log"" 2>&1", _
             0, False

' ── Start frontend ─────────────────────────────────────────────────────────
WshShell.Run "cmd /c cd /d """ & dir & "\web"" && npm run dev " & _
             ">> """ & dir & "\logs\frontend.log"" 2>&1", _
             0, False

' ── Poll health endpoint until ready (max 40 seconds) ─────────────────────
elapsed = 0
Do While elapsed < 40
    WScript.Sleep 1500
    elapsed = elapsed + 1.5
    If IsPortOpen("127.0.0.1", 8000) Then
        ' Backend is up — give frontend 2 more seconds then open browser
        WScript.Sleep 2000
        WshShell.Run "http://localhost:5173"
        WScript.Quit
    End If
Loop

' ── Timeout: backend didn't start — show log location ─────────────────────
WshShell.Popup "SAGE backend did not start after 40 seconds." & vbCrLf & vbCrLf & _
               "Check the log for errors:" & vbCrLf & _
               dir & "\logs\backend.log", _
               0, "SAGE[ai] — Start failed", 48

' ─────────────────────────────────────────────────────────────────────────────
' Helper: returns True if a TCP port is accepting connections
' ─────────────────────────────────────────────────────────────────────────────
Function IsPortOpen(host, port)
    Dim sock
    On Error Resume Next
    sock = WshShell.Run( _
        "powershell -NonInteractive -Command """ & _
        "try { $t = New-Object Net.Sockets.TcpClient('" & host & "'," & port & "); " & _
        "$t.Close(); exit 0 } catch { exit 1 }""", _
        0, True)
    IsPortOpen = (sock = 0)
    On Error GoTo 0
End Function
