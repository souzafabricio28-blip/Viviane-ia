$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Viviane.lnk")
$Shortcut.TargetPath = "C:\claude.ia\viviane-ia\run_viviane.bat"
$Shortcut.WorkingDirectory = "C:\claude.ia\viviane-ia"
$Shortcut.Description = "Inicia a Viviane - Assistente de Voz Inteligente"
$Shortcut.Save()
Write-Host "Atalho criado na Área de Trabalho"