@echo off
REM ==========================================================
REM  Gera o GiroBot.exe e, se o Inno Setup estiver instalado,
REM  tambem o GiroBot-Setup.exe (instalador).
REM  Uso: build.bat
REM ==========================================================
setlocal

echo [1/2] Gerando o executavel com PyInstaller...
call .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean girobot.spec
if errorlevel 1 goto :erro

echo.
echo [2/2] Gerando o instalador (Inno Setup)...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo.
    echo  Inno Setup nao encontrado - o instalador NAO foi gerado.
    echo  O aplicativo pronto esta em: dist\GiroBot\GiroBot.exe
    echo  Para gerar o instalador, instale o Inno Setup 6:
    echo    https://jrsoftware.org/isdl.php
    goto :fim
)
"%ISCC%" installer.iss
if errorlevel 1 goto :erro
echo.
echo  Instalador gerado em: instalador\GiroBot-Setup.exe

:fim
echo.
echo Concluido.
goto :eof

:erro
echo.
echo  FALHOU. Veja as mensagens acima.
exit /b 1
