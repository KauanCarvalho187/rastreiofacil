# Rastreio Facil - servidor local de arquivos (sem precisar instalar Python/Node)
#
# Serve a propria pasta do projeto em http://localhost:8080/ com Cache-Control: no-store,
# ou seja: o navegador SEMPRE pega o index.html/app.js/styles.css atuais (nada de
# "app.js velho em cache" - o que fazia os POSTs caírem no Live Server com 405).
#
# Uso: duplo clique em abrir-servidor-local.bat (ou: powershell -ExecutionPolicy Bypass -File servidor-local.ps1)
param([int]$Porta = 8080)

$ErrorActionPreference = 'Stop'
$raiz = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$prefixo = "http://localhost:$Porta/"

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add($prefixo)
$listener.Prefixes.Add("http://127.0.0.1:$Porta/")
try {
    $listener.Start()
} catch {
    Write-Host "[ERRO] Nao consegui abrir $prefixo"
    Write-Host "       $($_.Exception.Message)"
    Write-Host "       Dica: feche quem estiver usando a porta $Porta ou rode com -Porta 8081"
    Read-Host "Enter para sair"
    exit 1
}

$tipos = @{
    '.html' = 'text/html; charset=utf-8'
    '.js'   = 'application/javascript; charset=utf-8'
    '.css'  = 'text/css; charset=utf-8'
    '.json' = 'application/json; charset=utf-8'
    '.svg'  = 'image/svg+xml'
    '.png'  = 'image/png'
    '.ico'  = 'image/x-icon'
}

Write-Host '============================================'
Write-Host ' Rastreio Facil - servidor local de arquivos'
Write-Host '============================================'
Write-Host " Pasta:     $raiz"
Write-Host " Endereco:  $prefixo   (abre em /static/index.html)"
Write-Host " Sem cache: todo arquivo sai com Cache-Control: no-store"
Write-Host ' Deixe esta janela ABERTA. Ctrl+C para parar.'
Write-Host '============================================'

while ($listener.IsListening) {
    try {
        $ctx = $listener.GetContext()
        $caminho = [System.Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath)
        if ($caminho -eq '/' -or $caminho -eq '') { $caminho = '/static/index.html' }
        $rel = ($caminho -replace '^/+', '') -replace '/', '\'
        $arquivo = Join-Path $raiz $rel
        $ctx.Response.Headers['Cache-Control'] = 'no-store'
        if ((Test-Path -LiteralPath $arquivo -PathType Leaf) -and $arquivo.StartsWith($raiz)) {
            $ext = [IO.Path]::GetExtension($arquivo).ToLower()
            $ctx.Response.ContentType = if ($tipos.ContainsKey($ext)) { $tipos[$ext] } else { 'application/octet-stream' }
            $bytes = [IO.File]::ReadAllBytes($arquivo)
            $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
        } else {
            $ctx.Response.StatusCode = 404
            $ctx.Response.ContentType = 'text/plain; charset=utf-8'
            $msg = [Text.Encoding]::UTF8.GetBytes("404 - nao encontrado: $caminho")
            $ctx.Response.OutputStream.Write($msg, 0, $msg.Length)
        }
        $ctx.Response.Close()
    } catch {
        # conexao cancelada pelo navegador: segue servindo
    }
}