@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Rastreio Facil - servidor local (porta 8080)
echo   Serve a pasta do projeto SEM cache.
echo   Nao precisa de Python.
echo ============================================
REM Porta 8080 ja em uso?
netstat -ano | findstr ":8080 " | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
  echo [aviso] Ja existe algo na porta 8080 - tentando usar mesmo assim...
)
echo Subindo o servidor em outra janela...
start "Rastreio-Facil-Servidor-Local" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0servidor-local.ps1"
timeout /t 3 /nobreak >nul
start "" http://localhost:8080/
echo.
echo Servidor rodando na janela "Rastreio-Facil-Servidor-Local".
echo Para parar: feche aquela janela.
echo.
echo Depois de instalar o Python, use http://localhost:3000/ (backend) para salvar no banco.
pause