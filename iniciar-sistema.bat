@echo off
title Rastreio Facil - Servidor
cd /d "%~dp0"
echo ============================================
echo   Rastreio Facil - iniciando servidor...
echo   A janela deve ficar ABERTA enquanto usa o sistema.
echo ============================================
echo.
REM 1) Acha um Python que realmente funciona (a .venv pode ter quebrado ao mover a pasta)
set "PY="
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" --version >nul 2>&1
  if not errorlevel 1 set "PY=.venv\Scripts\python.exe"
)
if not defined PY (
  echo [aviso] venv ausente ou quebrada - usando o Python do sistema.
  py --version >nul 2>&1
  if not errorlevel 1 (set "PY=py") else (set "PY=python")
)
echo [ok] Python: %PY%
"%PY%" --version
if errorlevel 1 (
  echo [ERRO] Nenhum Python funcional encontrado. Instale o Python 3.12 em python.org
  pause
  exit /b 1
)
echo.
REM 2) Confere dependencias e instala o que faltar
"%PY%" -c "import fastapi, uvicorn, aiosqlite, aiosmtplib, dotenv" >nul 2>&1
if errorlevel 1 (
  echo [info] Instalando dependencias (requirements.txt)...
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias. Veja a mensagem acima.
    pause
    exit /b 1
  )
)
REM 3) Porta 3000 ja em uso?
netstat -ano | findstr ":3000 " | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
  echo [aviso] Ja existe um servidor rodando na porta 3000!
  echo.
  echo   - Para USAR: abra o navegador em http://localhost:3000
  echo   - Para REINICIAR: feche a outra janela do servidor antes
  echo     ^(ou rode no PowerShell: Get-Process python ^| Stop-Process -Force^)
  echo.
  pause
  exit /b 0
)
echo.
echo [ok] Subindo em http://localhost:3000 ...
echo      Deixe esta janela ABERTA enquanto usa o sistema.
echo.
"%PY%" main.py
set "EC=%errorlevel%"
echo.
if not "%EC%"=="0" (
  echo O servidor PAROU com erro ^(codigo %EC%^).
) else (
  echo O servidor foi fechado.
)
echo Pressione uma tecla para sair.
pause > nul
