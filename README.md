# 📦 Rastreio Fácil

Sistema web para cadastrar **códigos de rastreio dos Correios** e **notificar os clientes**
(e-mail ou WhatsApp) quando a encomenda está a caminho — com histórico, lixeira, backup e
consulta automática de eventos.

- Backend **FastAPI (Python)** — `main.py`
- Frontend **HTML/CSS/JS vanilla** (sem build) — `static/`
- Banco **SQLite** (local), **Postgres** (`DATABASE_URL`) ou **Cloudflare D1**
- Roda também como **Cloudflare Worker** (`cloudflare/worker.js`, mesmas rotas `/api`)

> Versão atual do front/back: **25**

## Recursos

- Cadastro manual e **importação em lote** (CSV / Excel).
- **Notificação** por e-mail (SMTP) e WhatsApp (`wa.me`); envio em massa dos pendentes.
- **Rastreio automático** na API Wonca Labs (com cache) que marca "entregue" sozinho.
- **Lixeira** (exclusão reversível) e **backup** do banco (admin).
- **Histórico** de mudanças de status por envio.
- **Autenticação** com sessões revogáveis, senha com PBKDF2 e rate-limit de login.
- **Modo offline** no navegador (`localStorage`) quando não há backend.
- **Anti-aba-velha**: o front se recarrega quando o servidor é atualizado.

## Como rodar

Guia completo em **[`COMO_RODAR.md`](COMO_RODAR.md)**.

- **Só a interface (sem Python):** `abrir-servidor-local.bat` → `http://localhost:8080`
- **Local (Windows):** `iniciar-sistema.bat` (ou `python main.py`) → `http://localhost:3000`
- **Docker:** `docker compose up -d --build` → `http://localhost:3000`
- **Cloudflare:** `wrangler deploy` (Worker + D1 + assets)
- **Nuvem:** `uvicorn main:app --host 0.0.0.0 --port $PORT` com `DATABASE_URL`

Primeiro acesso: botão **👤 → "Criar admin (1º uso)"**.

## Testes

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest                      # suíte (API in-process + rastreio)
python test_analise_erros.py  # verificador estático (inclui paridade main.py x worker.js)
pytest --browser             # testes de navegador (Selenium + Chrome)
python teste_navegador_demo.py --pausa 20   # demo no Chrome: login, cadastro, lixeira, Excel
```

O CI (`.github/workflows/ci.yml`) roda pytest + verificador estático + E2E + navegador a cada push/PR.

## Documentação

- **[`DOCUMENTACAO.md`](DOCUMENTACAO.md)** — arquitetura, banco, API completa, deploy, troubleshooting.
- **[`COMO_RODAR.md`](COMO_RODAR.md)** — passo a passo de execução.

## Estrutura (resumo)

```
main.py            backend FastAPI
db.py              banco (SQLite/Postgres) + migrações
validacao.py       regras de validação
rastreio.py        cliente da API de rastreio
static/            front (index.html, app.js, styles.css)
cloudflare/        worker.js + schema.sql (D1)
tests/             suíte pytest
Dockerfile         imagem non-root com healthcheck
```

## Licença

Uso pessoal/privado do autor.
