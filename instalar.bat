@echo off
title Viviane - Instalador
cd /d "%~dp0"

echo ========================================
echo     Viviane - instalacao local
echo ========================================
echo.

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Python nao encontrado. Instale Python 3.10+ de python.org
    pause
    exit /b 1
)

python --version

echo.
echo Criando ambiente virtual...
if exist "venv" (
    echo [AVISO] Ambiente virtual ja existe.
) else (
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo [ERRO] Falha ao criar ambiente virtual
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado
)

echo.
echo Instalando dependencias. Isso pode levar varios minutos...
call "venv\Scripts\pip.exe" install --upgrade pip -q
call "venv\Scripts\pip.exe" install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Falha ao instalar dependencias
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas

if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo [OK] .env criado a partir do exemplo. Coloque suas chaves de API.
) else (
    echo [OK] .env ja existe
)

echo.
echo Criando atalho no Desktop...
set "DESKTOP=%USERPROFILE%\Desktop"
copy /Y "run_viviane.bat" "%DESKTOP%\Viviane.bat" >nul
echo [OK] Atalho: %DESKTOP%\Viviane.bat

echo.
echo ========================================
echo  Instalacao concluida
echo ========================================
echo.
echo A Viviane roda somente neste computador.
echo Duplo clique em Viviane.bat na area de trabalho,
echo ou execute iniciar.bat nesta pasta.
echo.
pause
