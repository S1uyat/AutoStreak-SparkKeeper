Option Explicit
Dim fso, base, py, app, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
py = fso.BuildPath(base, ".venv\Scripts\pythonw.exe")
app = fso.BuildPath(base, "manager.py")
If Not fso.FileExists(py) Then
  MsgBox "请先双击『安装并打开.bat』完成安装。", 48, "SparkKeeper"
  WScript.Quit 1
End If
cmd = Chr(34) & py & Chr(34) & " " & Chr(34) & app & Chr(34)
CreateObject("WScript.Shell").Run cmd, 0, False
