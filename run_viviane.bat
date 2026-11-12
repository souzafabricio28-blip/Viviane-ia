@echo off
cd /d "%~dp0"
rem Sobe a janela sem deixar o prompt aberto.
start "" wscript //nologo "%~dp0iniciar_viviane.vbs"
exit /b 0
