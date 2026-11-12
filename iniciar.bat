@echo off
title Viviane
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat" >nul 2>&1
)

:menu
cls
echo ================================================
echo          Viviane - assistente local
echo ================================================
echo.
echo  [1] Voz      - modo comando de voz
echo  [2] Desktop  - janela da Viviane
echo.
echo  [I] Instalar dependencias
echo  [S] Sair
echo.
echo ================================================
echo.

choice /c 12IS /n /m "Digite a opcao: "
if errorlevel 4 exit /b 0
if errorlevel 3 goto instalar
if errorlevel 2 goto desktop
if errorlevel 1 goto voz

:voz
cls
echo Iniciando Viviane - modo voz...
echo Pressione Ctrl+C para encerrar
echo.
python main.py
pause
goto menu

:desktop
cls
echo Iniciando Viviane - janela...
echo.
start "" wscript //nologo "%~dp0iniciar_viviane.vbs"
goto menu
pause
goto menu

:instalar
cls
echo Instalando dependencias locais...
echo.
if not exist "venv" (
    python -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual
        pause
        goto menu
    )
)
call "venv\Scripts\activate.bat"
python -m pip install --upgrade pip -q
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias
    pause
    goto menu
)
if not exist ".env" (
    copy .env.example .env >nul
    echo [AVISO] Arquivo .env criado. Configure suas chaves de API.
)
echo.
echo Instalacao concluida. A Viviane fica somente neste computador.
pause
goto menu
