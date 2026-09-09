@echo off
title Mapeador de Politicas Publicas - Prefeitos Eleitos 2024
cd /d "%~dp0"

echo.
echo   Mapeador de Politicas Publicas Municipais
echo   Planos de governo dos prefeitos eleitos em 2024
echo.
echo   Abrindo a interface...
echo.

python "app\gui.py"

if errorlevel 1 (
    echo.
    echo   Nao foi possivel abrir a interface.
    echo   Verifique se o Python esta instalado e se as dependencias
    echo   do arquivo requirements.txt foram instaladas:
    echo.
    echo       pip install -r requirements.txt
    echo.
    pause
)
