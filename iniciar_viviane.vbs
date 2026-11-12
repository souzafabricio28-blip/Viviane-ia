Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

base = fso.GetParentFolderName(WScript.ScriptFullName)
py = "C:\Users\souza\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"
If Not fso.FileExists(py) Then py = "pythonw.exe"

sh.CurrentDirectory = base
' pythonw não abre console. Estilo 1 mostra só a janela da Viviane.
sh.Run """" & py & """ """ & base & "\viviane.pyw""", 1, False
