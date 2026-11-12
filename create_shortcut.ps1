$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Viviane.lnk")
$Shortcut.TargetPath = "C:\Windows\System32\wscript.exe"
$Shortcut.Arguments = "//nologo `"C:\claude.ia\viviane-ia\iniciar_viviane.vbs`""
$Shortcut.WorkingDirectory = "C:\claude.ia\viviane-ia"
$Shortcut.WindowStyle = 7
$Shortcut.Description = "Inicia a Viviane - Assistente de Voz Inteligente"
$Shortcut.Save()
Write-Host "Atalho criado na Área de Trabalho"