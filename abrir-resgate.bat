@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Rastreio Facil - RESGATE (salvar no navegador)
echo   Abre a pagina de importacao que grava direto
echo   no localStorage, sem depender do sistema.
echo ============================================
echo.
REM Sobe o servidor local (porta 8080) se ainda nao estiver rodando
netstat -ano | findstr ":8080 " | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
  echo [ok] Ja existe um servidor na porta 8080 - reutilizando.
) else (
  echo Subindo o servidor local em outra janela...
  start "Rastreio-Facil-Servidor-Local" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0servidor-local.ps1"
  timeout /t 3 /nobreak >nul
)
start "" "http://localhost:8080/static/resgate.html"
echo.
echo Pagina de resgate aberta no navegador.
echo   1) Clique em "Colar exemplo (13 linhas)" ou escolha o arquivo envios.csv
echo   2) Clique em "Analisar" para conferir
echo   3) Clique em "Salvar no navegador"
echo   4) Volte para a tela principal e aperte F5
echo.
echo IMPORTANTE: use sempre http://localhost:8080/ para a tela principal,
echo senao o navegador salva em outro lugar.
pause
