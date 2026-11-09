' Hermes Quick Launch: Win+R -> "hermes" -> Windows Terminal (or PowerShell) running Hermes.
' Uses Windows PowerShell WITH your profile, so a `hermes` wrapper function (e.g. from hermes-device-sync)
' is used when you have one; otherwise the normal hermes command runs. Author: Francisco Moniz (MIT).
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
home = sh.ExpandEnvironmentStrings("%USERPROFILE%")
cmd = "powershell.exe -NoExit -Command hermes"
wt = ""
For Each c In Array("%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe", "%LOCALAPPDATA%\WindowsTerminal\wt.exe")
  p = sh.ExpandEnvironmentStrings(c)
  If wt = "" And fso.FileExists(p) Then wt = p
Next
If wt <> "" Then
  sh.Run """" & wt & """ -d """ & home & """ " & cmd, 1, False
Else
  sh.CurrentDirectory = home
  sh.Run cmd, 1, False
End If
