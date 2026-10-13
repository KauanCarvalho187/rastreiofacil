# Rastreio Fácil — Como rodar

> Documentação técnica completa (arquitetura, API, banco, deploy): **`DOCUMENTACAO.md`**.
> Versão do front/back: **24**.

Escolha o cenário:

| Cenário | Precisa de Python? | Onde salva os dados |
|---|---|---|
| [0. Só a interface](#0-só-a-interface-sem-python) | Não | `localStorage` do navegador |
| [1. Local no Windows](#1-local-no-windows) | Sim | SQLite (`database.db`) |
| [2. Docker](#2-docker) | Não (só Docker) | SQLite em volume |
| [3. Cloudflare](#3-cloudflare-workers--d1) | Não | D1 (banco da Cloudflare) |
| [4. Servidor/Render](#4-servidor-na-nuvem-render-railway-vps) | — | Postgres (`DATABASE_URL`) |

---

## 0. Só a interface (sem Python)
Duplo clique em **`abrir-servidor-local.bat`**. Ele sobe um servidor de arquivos em PowerShell
(`servidor-local.ps1`) na porta **8080** com `Cache-Control: no-store` e abre `http://localhost:8080/`.

Sem backend, cadastro e importação ficam salvos **no navegador** (`localStorage`) e sincronizam
sozinhos quando o Python estiver instalado. Para parar, feche a janela *Rastreio-Facil-Servidor-Local*.

> Erros de JavaScript aparecem numa **barra vermelha no rodapé**. A versão do front aparece no
> console como `window.APP_V` e precisa bater com `APP_VERSAO` do `main.py` (hoje `24`).

---

## 1. Local no Windows

**Pré-requisito:** Python 3.12 de [python.org](https://www.python.org/downloads/) com *"Add python.exe to PATH"*.

### Jeito rápido
Duplo clique em **`iniciar-sistema.bat`**. Ele:
1. usa a `.venv` se existir funcional (senão o Python do sistema);
2. instala as dependências que faltarem (`requirements.txt`);
3. avisa se a porta 3000 já estiver ocupada;
4. sobe o servidor em `http://localhost:3000`.

### Manual
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py            REM sobe em http://localhost:3000
```
Alternativa com reload automático durante o desenvolvimento:
```bat
uvicorn main:app --reload --port 3000
```

### Primeiro acesso (admin)
No primeiro uso o banco está vazio: clique em **👤 → "Criar admin (1º uso)"** e informe nome,
e-mail e senha (mínimo 8 caracteres). Esse primeiro usuário vira administrador; os próximos só
podem ser criados por um admin logado.

### Banco de dados
- **Padrão:** SQLite no arquivo `database.db` (pasta do projeto). Não precisa configurar nada.
- **Postgres:** defina `DATABASE_URL` no `.env` (veja `.env.example`).

---

## 2. Docker

```bash
cp .env.example .env        # edite se quiser SMTP / Postgres / rastreio
docker compose up -d --build
```
Abre em `http://localhost:3000`. O banco SQLite fica no volume nomeado **`rastreio-data`**
(montado em `/data/database.db` dentro do container), então sobrevive a `docker compose down`/upgrade.

Detalhes da imagem:
- roda como usuário **sem privilégios** (`appuser`, uid 10001);
- tem **HEALTHCHECK** batendo em `/api/health`;
- o `.env` **não** entra na imagem (veja `.dockerignore`).

Comandos úteis:
```bash
docker compose logs -f          # ver os logs
docker compose down             # parar (mantém o volume)
docker compose down -v          # parar e APAGAR o banco do volume
```

> Usar Postgres em vez do SQLite no Compose? Abra `docker-compose.yml`: há um bloco `db:`
> comentado com as instruções.

---

## 3. Cloudflare (Workers + D1)

O sistema roda 100% na Cloudflare: o **Worker** (`cloudflare/worker.js`) responde as mesmas rotas
`/api` do `main.py`, o **D1** é o banco e a pasta `static/` é servida como assets.

```bash
npm install -g wrangler      # ou use npx
wrangler login
# 1) criar o banco D1 (só na primeira vez) e copiar o database_id para wrangler.jsonc
wrangler d1 create rastreio-facil
# 2) criar as tabelas
wrangler d1 execute rastreio-facil --remote --file cloudflare/schema.sql
# 3) segredos (não ficam no arquivo)
wrangler secret put RASTREIO_API_KEY
wrangler secret put SMTP_USER
wrangler secret put SMTP_PASS
# 4) publicar
wrangler deploy
```
Para testar localmente: `wrangler dev` (usa `cloudflare/schema.sql` via `--local` quando configurado).

> ⚠️ Toda mudança de regra/rota no `main.py` **precisa ser espelhada no `cloudflare/worker.js`**.
> O teste `test_analise_erros.py` compara automaticamente as rotas dos dois (método + caminho).

---

## 4. Servidor na nuvem (Render, Railway, VPS)

1. Suba o repositório (GitHub) e crie um serviço Python.
2. **Build:** `pip install -r requirements.txt`
3. **Start:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Variáveis: `DATABASE_URL` (Postgres), `SMTP_*`, `RASTREIO_API_KEY`, `CORS_ORIGINS`.
5. Docker também funciona: use a imagem deste repositório.

---

## 5. Testes

```bat
pip install -r requirements.txt -r requirements-dev.txt
pytest                      REM suíte pytest (API in-process + rastreio)
python test_analise_erros.py  REM verificação estática (rotas, HTML, JS)
```

Testes que abrem **navegador** (precisam de Chrome + selenium):
```bat
pytest --browser
```

Os testes E2E já existentes (contra um servidor real em `127.0.0.1:3001`) continuam disponíveis:
`teste_api_real.py`, `teste_crud.py`, `teste_bordas.py`, `teste_canais.py`, `teste_chrome.py`,
`teste_fluxo.py`, `teste_rastreio.py`. Para rodá-los, suba o servidor com
`uvicorn main:app --port 3001` e um banco semeado (`admin@empresa.com` / `admin12345`).

---

## 6. Troubleshooting rápido

| Sintoma | O que fazer |
|---|---|
| Página com HTML/JS antigo | A versão (`?v=24`) e o header `no-store` resolvem; force recarga (Ctrl+F5). |
| `porta 3000 já em uso` | Feche a outra janela do servidor ou `Get-Process python \| Stop-Process -Force`. |
| Erro ao mover a pasta do projeto | A `.venv` quebra de caminho; apague a `.venv` e recrie (`iniciar-sistema.bat` cobre o Python do sistema). |
| E-mail não envia | Configure `SMTP_USER`/`SMTP_PASS` (Gmail precisa de *senha de app*). Sem SMTP, o app usa `mailto:`/wa.me. |
| "Rastrear" só abre os Correios | Falta `RASTREIO_API_KEY` (chave grátis em labs.wonca.com.br). |
| Erros de `UnicodeEncodeError` nos testes | Rode com `set PYTHONUTF8=1` (console do Windows em cp1252). |

Mais detalhes em **`DOCUMENTACAO.md` §14 (Testes)** e **§16 (Troubleshooting)**.
