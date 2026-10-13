# 📦 Rastreio Fácil — Documentação Completa do Sistema

> Sistema web de gestão e notificação de códigos de rastreio dos Correios.
> Backend **FastAPI (Python)** + Frontend **HTML/CSS/JS vanilla** (sem build) +
> Banco **SQLite** (local), **Postgres** (`DATABASE_URL`) ou **Cloudflare D1**.
>
> **Versão do front/back: `27`** (campo `APP_VERSAO` no `main.py` e `APP_V` no `static/app.js`).
> Documentação revisada em **13/10/2026**, conferida linha a linha contra
> `main.py`, `db.py`, `validacao.py`, `rastreio.py`, `static/app.js`, `static/index.html`,
> `cloudflare/worker.js` e os testes.

---

## Índice

1. [Visão geral](#1-visão-geral)
2. [Stack tecnológica](#2-stack-tecnológica)
3. [Estrutura de arquivos](#3-estrutura-de-arquivos)
4. [Como executar](#4-como-executar)
5. [Arquitetura geral](#5-arquitetura-geral)
6. [Banco de dados](#6-banco-de-dados)
7. [Autenticação e sessões](#7-autenticação-e-sessões)
8. [Referência completa da API](#8-referência-completa-da-api)
9. [Funcionalidades do frontend](#9-funcionalidades-do-frontend)
10. [Notificações (e-mail / WhatsApp / massa)](#10-notificações)
11. [Rastreio automático](#11-rastreio-automático)
12. [Configuração (.env / .dev.vars)](#12-configuração)
13. [Docker e Deploy](#13-docker-e-deploy)
14. [Testes e verificação](#14-testes-e-verificação)
15. [Histórico de versões](#15-histórico-de-versões)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. Visão geral

O Rastreio Fácil serve para uma loja/atendimento cadastrar **códigos de rastreio** dos Correios
de vários clientes e **avisar cada cliente** (e-mail ou WhatsApp) que a encomenda está a caminho.
O sistema acompanha o status (`pendente` → `a_caminho` → `entregue`), guarda **histórico** de
mudanças, tem **lixeira** (exclusão reversível), **backup** do banco e **consulta automática** de
eventos na API de rastreio.

Ele funciona em **dois ambientes** com o mesmo front:
- **Backend local/nuvem** (`main.py` + FastAPI);
- **Cloudflare Workers + D1** (`cloudflare/worker.js`), um porte 1:1 das rotas.
- Sem nenhum backend, o front ainda funciona **offline** no navegador (`localStorage`).

---

## 2. Stack tecnológica

| Camada | Tecnologia |
|---|---|
| Backend | **FastAPI**, **Uvicorn**, Pydantic |
| Banco | **SQLite** (`aiosqlite`), **Postgres** (`asyncpg`), **Cloudflare D1** |
| E-mail | **aiosmtplib** (SMTP) + `mailto:` como fallback |
| Rastreio | API **Site Rastreio / Wonca Labs** (`httpx` via `rastreio.py`) |
| Planilhas | **openpyxl** (import/export `.xlsx`), CSV nativo |
| Front | HTML + CSS + **JavaScript vanilla** (sem framework, sem build) |
| Testes | **pytest**, verificador estático próprio, **Selenium** (navegador) |
| Deploy | **Docker**, **Cloudflare Workers + D1**, Render/Railway/VPS |

Pacotes e versões exatas: `requirements.txt` (produção) e `requirements-dev.txt` (testes).
Principais: `fastapi 0.143.0`, `uvicorn 0.54.0`, `aiosqlite 0.22.1`, `aiosmtplib 5.1.3`,
`asyncpg 0.32.0`, `openpyxl 3.1.5`, `httpx 0.28.1`, `python-dotenv 1.2.4`.

> Não há bundler, `node_modules` nem etapa de build no front. O navegador carrega
> `static/index.html` → `styles.css` + `app.js` diretamente.

---

## 3. Estrutura de arquivos

```
rastreio-asistema1_1/
├─ main.py                  # Backend FastAPI: rotas /api, SMTP, rastreio, segurança
├─ db.py                    # Camada de banco (SQLite/Postgres) + init_db/migrações
├─ validacao.py             # Regras de validação compartilhadas (código, e-mail, celular)
├─ rastreio.py              # Cliente da API de rastreio + normalização dos eventos
├─ importar_planilha.py     # CLI: importa CSV/Excel direto no banco
├─ inspecionar_db.py        # CLI: inspeciona o banco
├─ reset_senha.py           # CLI: redefine a senha de um usuário
├─ limpar_teste.py          # CLI: limpa dados de teste
├─ servidor-local.ps1       # Servidor de arquivos (PowerShell) sem Python, porta 8080
├─ abrir-servidor-local.bat # Atalho para o servidor-local.ps1 (só interface)
├─ iniciar-sistema.bat      # Atalho: cria/usa .venv, instala deps e sobe o backend
│
├─ static/                  # Front (servido em /static e como raiz da tela única)
│  ├─ index.html            # Tela única (cadastro, lista, modais, login)
│  ├─ styles.css            # Tema escuro
│  ├─ app.js                # Toda a lógica do front (API + offline localStorage)
│  └─ libs/                 # Bibliotecas vendorizadas (sem CDN)
│
├─ cloudflare/
│  ├─ worker.js             # Backend para Cloudflare Workers (espelha o main.py)
│  └─ schema.sql            # Esquema do D1 (espelha o init_db do db.py)
├─ wrangler.jsonc           # Config do Worker + D1 + assets
│
├─ tests/                   # Suíte pytest
│  ├─ conftest.py           # Fixtures (client in-process, live_server, browser)
│  ├─ test_api.py           # API completa (in-process, banco temporário)
│  ├─ test_rastreio.py      # Normalização do provedor + rota /rastrear
│  └─ test_browser.py       # Navegador (Selenium) — roda com `pytest --browser`
├─ pytest.ini               # Config do pytest + marcador "browser"
│
├─ test_analise_erros.py    # Verificador estático (rotas, HTML, JS, paridade Worker)
├─ teste_fluxo.py           # E2E via ASGI (banco temporário)
├─ teste_rastreio.py        # Rastreio com provedor simulado
├─ teste_api_real.py        # E2E HTTP contra servidor em 127.0.0.1:3001
├─ teste_crud.py            # CRUD exaustivo da API (HTTP)
├─ teste_bordas.py          # Casos adversariais (payloads, SQL injection, unicode)
├─ teste_canais.py          # E2E navegador dos 3 canais de notificação
├─ teste_chrome.py          # E2E navegador (CRUD na UI)
├─ teste_operacional.py     # E2E da API: login, cadastro em lote, lixeira/purgar, Excel
├─ teste_navegador_demo.py  # Demonstração no Chrome (Selenium visível) + prints em evidencias/
├─ teste_usuarios_brave.py  # Demonstração no Brave: criar usuário não-admin + prints em evidencias_usuarios/
│
├─ Dockerfile               # Imagem (usuário non-root + HEALTHCHECK)
├─ docker-compose.yml       # Compose (volume do SQLite; Postgres opcional)
├─ .dockerignore            # Não envia .env, .venv, *.db, etc. para a imagem
├─ requirements.txt         # Dependências de produção
├─ requirements-dev.txt     # Dependências de teste (pytest, selenium)
├─ .env.example             # Modelo de configuração
├─ .github/workflows/ci.yml # CI (GitHub Actions)
├─ DOCUMENTACAO.md          # Este arquivo
└─ COMO_RODAR.md            # Guia rápido de execução
```

Arquivos/pastas ignorados no git: `.venv/`, `database.db`, `*.db`, `.env`, `.dev.vars`,
`.wrangler/`, `__pycache__/`, `restreiofacil/` (cópia antiga, mantida só por segurança).

---

## 4. Como executar

O passo a passo detalhado (Windows, Docker, Cloudflare, Render e testes) está em
**`COMO_RODAR.md`**. Resumo:

- **Só a interface (sem Python):** `abrir-servidor-local.bat` → `http://localhost:8080`.
- **Local (Windows):** `iniciar-sistema.bat` (ou `python main.py`) → `http://localhost:3000`.
- **Docker:** `docker compose up -d --build` → `http://localhost:3000`.
- **Cloudflare:** `wrangler deploy` (Worker + D1 + assets).
- **Nuvem:** `uvicorn main:app --host 0.0.0.0 --port $PORT` (com `DATABASE_URL`).

---

## 5. Arquitetura geral

```
 Navegador (static/index.html + app.js)
        │  fetch JSON  (/api/*)
        ▼
 main.py (FastAPI)  ──►  db.py  ──►  SQLite  ou  Postgres
        │
        ├─► SMTP (aiosmtplib)                → e-mail
        ├─► wa.me / mailto: (fallback no front) → WhatsApp / e-mail manual
        └─► rastreio.py ─► API Wonca Labs    → eventos do objeto
```

O mesmo front também fala com o **Cloudflare Worker** (`cloudflare/worker.js`) + **D1**,
que expõe exatamente as mesmas rotas `/api`. Sem backend disponível, o `app.js` cai em
**modo offline** (dados no `localStorage`) e sincroniza quando o backend voltar.

### 5.1 Middleware de resposta (`main.py`)

Para **toda** resposta:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`

Cache:
- `/static/libs/*` e `/static/img/*` → `public, max-age=31536000, immutable`;
- arquivos `.js/.css/.html/.json` → `no-cache, must-revalidate`;
- `/`, `/main`, `/login` (HTML) → `no-store`.

### 5.2 CORS
Controlado por `CORS_ORIGINS` (lista separada por vírgula; padrão `*`). Padrão `*` mantém
compatibilidade com Live Server (`:5500`–`:5503`) e `file://`. **Em produção**, defina
`CORS_ORIGINS=https://seu-dominio.com`.

### 5.3 Versionamento do front (anti "aba velha")
O `app.js` guarda `APP_V = '27'` e pergunta `GET /api/versao`. Se o servidor responder outra
versão, o front se recarrega sozinho. O `index.html` referencia os assets com `?v=27`.
**Ao publicar mudanças no front, suba a versão nos dois lugares** (`main.py` → `APP_VERSAO`
e `static/app.js` → `APP_V`, além do `?v=` no `index.html` e no `cloudflare/worker.js`).

---

## 6. Banco de dados

### 6.1 SQLite (padrão) e Postgres
- **SQLite:** arquivo `database.db` na pasta do projeto (ou `DB_PATH`). Zero configuração.
- **Postgres:** basta definir `DATABASE_URL` (prefixo `postgres://` ou `postgresql://`). O `db.py`
  detecta e troca o driver para `asyncpg`, convertendo `?` → `$1` automaticamente.

O `db.py` expõe: `fetch_all`, `fetch_one`, `execute`, `init_db`, `db_status_info`,
`USE_POSTGRES`, `DB_PATH`.

### 6.2 Tabelas (criadas por `init_db`)

| Tabela | Campos principais |
|---|---|
| `envios` | `id`, `destinatario`, `codigo`, `celular`, `email`, `descricao`, `status`, `notificado`, `criado_em`, `atualizado_em`, `criado_por`, `excluido_por`, `excluido_em`, `status_anterior` |
| `usuarios` | `id`, `nome`, `email` (único), `senha_hash`, `admin`, `ativo`, `criado_em` |
| `sessoes` | `token` (PK), `usuario_id`, `expira_em` |
| `eventos` | `id`, `envio_id`, `de_status`, `para_status`, `por_usuario`, `detalhe`, `criado_em` |
| `rastreios` | `id`, `envio_id` (único), `situacao`, `carrier`, `eventos` (JSON), `consultado_em` |

Índices: `idx_envios_codigo`, `idx_envios_status`, `idx_eventos_envio` e o **índice único**
`idx_envios_codigo_unico` (um código de rastreio só pode existir uma vez).

### 6.3 Migrações leves
O `init_db` se adapta a bancos antigos:
- garante a coluna `atualizado_em` e as colunas de **lixeira** (`excluido_por`, `excluido_em`,
  `status_anterior`) em `envios`;
- tenta criar o **índice único** de `codigo`; se o banco legado tiver códigos duplicados, o
  `CREATE UNIQUE INDEX` falha silenciosamente e mantém-se só o índice simples (o app continua
  funcionando e o app continua checando duplicidade antes de inserir).

### 6.4 Lixeira (soft delete)
- `DELETE /api/envios/{id}` **não apaga**: grava `status='excluido'`, `excluido_por`, `excluido_em`
  e `status_anterior`.
- A listagem normal **esconde** a lixeira; use `?status=excluido` para vê-la.
- **Restaurar** (`POST .../restaurar`) e **purgar** (`DELETE .../purga`) são **exclusivos de admin**.
  A purga remove também `eventos` e `rastreios` daquele envio.

---

## 7. Autenticação e sessões

- **Senha:** armazenada como `PBKDF2-HMAC-SHA256`, 100.000 iterações, sal aleatório de 16 bytes
  (`sal$hash`). A senha **nunca** é guardada em texto puro.
- **Sessão:** token aleatório (`secrets.token_hex(32)`) na tabela `sessoes`, com validade de
  `SESSAO_DIAS` (padrão 7). O cliente envia `Authorization: Bearer <token>`.
- **Bootstrap:** enquanto não há usuários, `POST /api/auth/registrar` cria o primeiro como **admin**
  sem precisar de token. Depois disso, só um **admin** cria usuários.
- **Rate-limit de login:** por IP, `LOGIN_MAX_TENT` (10) falhas em `LOGIN_JANELA_SEG` (300s) → `429`.
- **Logout:** `POST /api/auth/logout` **revoga** o token no banco (não é só no navegador).
- Sessões **expiradas** são limpas no boot do app (`lifespan`).
- `GET /api/auth/estado` informa `{temUsuarios, admin}` — usado pelo front para exibir ações de admin.

---

## 8. Referência completa da API

Base: `http://localhost:3000`. Todas as rotas `/api/*` respondem JSON.
Erros do FastAPI vêm como `{"detail": "mensagem"}`.

### 8.1 Rotas de serviço (públicas)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | `{ok, db:{configured,connected,driver,url_safe}, smtp, rastreio}` |
| GET | `/api/db-status` | Status detalhado do banco |
| GET | `/api/versao` | `{versao}` (hoje `"27"`) |
| GET | `/api/auth/estado` | `{temUsuarios, admin}` (usa o token do header, se houver) |

### 8.2 Autenticação

| Método | Rota | Corpo | Observações |
|---|---|---|---|
| POST | `/api/auth/registrar` | `{nome, email, senha, admin?}` | 1º usuário vira admin sem token; depois exige admin. `senha` ≥ 8. `409` se e-mail existe. |
| POST | `/api/auth/login` | `{email, senha}` | `{token, user:{id,nome,email,admin}}`; `401` inválido; `429` rate-limit. |
| POST | `/api/auth/logout` | — (header) | Revoga o token. |
| POST | `/api/auth/trocar-senha` | `{senha_atual, senha_nova}` | `401` senha atual errada; `422` nova < 8. |

### 8.3 Envios

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/envios` | Cria 1 ou vários (até **500**). Aceita `{...}` ou `{envios:[...]}`. |
| GET | `/api/envios` | Lista com `q`, `status`, `page`, `limit`. |
| PUT | `/api/envios/{id}` | Edita destinatário/código/celular/e-mail/descrição/status. |
| PATCH | `/api/envios/{id}/status` | `{status}` ∈ `pendente\|a_caminho\|entregue`. |
| PATCH | `/api/envios/{id}/notificado` | Marca notificado **sem regredir** status. |
| DELETE | `/api/envios/{id}` | Move para a **lixeira** (soft delete). |
| POST | `/api/envios/{id}/restaurar` | **Admin.** Volta ao `status_anterior`. |
| DELETE | `/api/envios/{id}/purga` | **Admin.** Apaga de vez (+ eventos e rastreios). |
| POST | `/api/envios/{id}/rastrear` | Consulta o provedor (ver §11). |
| GET | `/api/envios/{id}/eventos` | Últimos 50 eventos (auditoria). |

**POST /api/envios — exemplo**
```json
// requisição (lote)
{ "envios": [
  { "destinatario": "Maria Silva", "codigo": "AA123456789BR",
    "celular": "(11) 91234-5678", "email": "maria@email.com",
    "descricao": "Pedido #1024" }
]}

// resposta 200
{ "message": "1 envio(s) criado(s)",
  "envios": [ { "_id": 1, "destinatario": "Maria Silva", "codigo": "AA123456789BR",
                "status": "pendente", "notificado": false,
                "link": "https://rastreamento.correios.com.br/app/index.php?objeto=AA123456789BR",
                ... } ],
  "erros": [] }
```
Regras de validação (campos aceitos no lote: `destinatario`/`nome`, `codigo`,
`celular`, `email`, `descricao`/`observacoes`, `status`):
- `destinatario` obrigatório;
- `codigo` no formato **2 letras + 9 números + BR** (ex.: `AA123456789BR`);
- e-mail válido **ou** celular (DDD + 8/9 dígitos) — ao menos um contato;
- códigos duplicados na planilha e códigos já cadastrados são **ignorados** (vão para `erros`);
- se **nada** for válido → `422`.

**GET /api/envios — parâmetros**

| Param | Padrão | Regra |
|---|---|---|
| `q` | `""` | Busca em `destinatario`, `codigo` e `descricao` (LIKE). |
| `status` | `""` | `pendente`/`a_caminho`/`entregue`/`excluido`. Vazio = só os ativos (sem lixeira). |
| `page` | `1` | ≥ 1 (senão `422`). |
| `limit` | `200` | 1..500 (senão `422`). |

Resposta: `{ "envios":[...], "total": N, "page": P, "limit": L }`.
Cada envio traz `criado_por_nome` e, para admins, `excluido_por_nome`.

**PUT /api/envios/{id}** — corpo parcial (`EnvioUpdate`): `destinatario`, `codigo`, `celular`,
`email`, `descricao`, `status`. Erros: `404` não existe; `422` destinatário vazio ou sem contato;
`409` código já usado por outro envio.

### 8.4 Gestão, dashboard e backup

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/usuarios` | **Admin.** Lista usuários (sem expor hash). |
| PATCH | `/api/usuarios/{uid}` | **Admin.** `{admin?, ativo?}`; não permite desativar a si mesmo (`422`). Desativar revoga as sessões. |
| GET | `/api/estatisticas` | `{total, pendente, a_caminho, entregue}` (contado no SQL). |
| GET | `/api/backup` | **Admin.** Baixa o arquivo SQLite (`backup-rastreio-<data>.db`). `400` se Postgres; `404` se o arquivo não existe. |

### 8.5 Páginas

| Método | Rota | Retorno |
|---|---|---|
| GET | `/` | `static/index.html` (sem cache) |
| GET | `/main`, `/login` | Aliases de compatibilidade → mesma tela |
| GET | `/static/*` | Arquivos estáticos |

---

## 9. Funcionalidades do frontend

- **Tela única** (`index.html`): cadastro, importação, lista, estatísticas e modais.
- **Autenticação:** modal de login/Criar-admin; botões que só aparecem para admin (backup).
- **Cadastro rápido** e **em lote** (textarea de CSV ou arraste de arquivo `.csv/.xlsx/.xls`).
- **Lista** com busca (com **debounce** de 150ms), filtro por status (cards clicáveis) e
  lixeira. A busca percorre **todas as páginas** do servidor (não trava em 200).
- **Edição** em modal (`PUT`) e **status** por atalho.
- **WhatsApp:** monta a mensagem e abre `wa.me` (o envio real é feito pelo usuário).
- **E-mail:** chama `POST /api/notificacoes`; se o SMTP não estiver configurado, cai em `mailto:`.
- **Rastrear:** modal que consome `POST .../rastrear` e mostra a linha do tempo; botão para o
  site dos Correios.
- **Exportar** CSV/Excel do recorte filtrado e **Backup do banco** (admin).
- **Modo offline:** detecta se há backend; sem ele, grava no `localStorage` e mostra um aviso.
  Quando a API volta, sincroniza (com *backoff* de 5s até 60s).
- **Erros visíveis:** erros de JS aparecem numa **barra vermelha** no rodapé.
- **Anti-aba-velha:** confere `GET /api/versao` e se recarrega se o servidor estiver em versão mais nova.

### 9.1 Detecção de backend / portas
O front decide se o backend está disponível tentando as portas do Live Server
(`5500`–`5503`) e a própria origem. Isso evita o antigo problema de "backend confirmado na 5501
mas rodando na 5502". `window.APP_V` mostra a versão do front no console.

---

## 10. Notificações

### 10.1 E-mail
- Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SENDER_NAME`.
- Porta **465** → TLS direto; as demais (ex.: 587) → STARTTLS.
- Gmail exige **senha de app** (não a senha normal).

`POST /api/notificacoes`
```json
// req: { "codigo": "AA123456789BR", "canal": "email", "mensagem": "", "assunto": null }
// resp (enviado):     { "success": true,  "result": { "enviado": true, "email": "..." } }
// resp (sem SMTP):    { "success": false, "fallback": true, "message": "SMTP nao configurado — usar mailto:" }
```
Se `mensagem` vier vazia, o backend monta um **HTML padrão** bonito (com link de rastreio).
Ao enviar com sucesso, o envio passa para `a_caminho` e `notificado=1`.

`POST /api/notificacoes/massa` — notifica **todos os pendentes com e-mail** de uma vez.
Só aceita `canal="email"` (`422` caso contrário) e exige SMTP (`422` se não configurado).
Resposta: `{message, enviadas, falhas}`.

### 10.2 WhatsApp
O envio é **client-side**: o backend apenas devolve `{success:false, fallback:true, message:"WhatsApp via wa.me"}`
e o front monta o link `https://wa.me/55<DDD><numero>?text=...`. Não há API de WhatsApp integrada.

### 10.3 Fallback offline
Sem backend, o front guarda a notificação como "para enviar" e oferece `mailto:`/`wa.me`.

---

## 11. Rastreio automático

Implementado em `rastreio.py` (backend) e replicado no `cloudflare/worker.js`.

- **Provedor:** API *Site Rastreio* (Wonca Labs). Requer `RASTREIO_API_KEY`
  (grátis em <https://labs.wonca.com.br>, ~1000 consultas/mês). Sem a chave, o modal "Rastrear"
  só abre o site dos Correios.
- **Chamada:** `POST /api/envios/{id}/rastrear` com corpo opcional `{ "forcar": true }`.
- **Cache:** o resultado fica na tabela `rastreios` por `RASTREIO_CACHE_MIN` (padrão 30) minutos.
  Uma consulta com situação **`entregue`** nunca expira (não gasta cota de novo).
- **Normalização:** aceita Correios (`eventos`) e Cainiao (`module[].detailList`) e devolve uma
  lista única `[{data, descricao, detalhe, local, destino}]`, ordenada do mais recente para o mais antigo.
- **Situação:** `entregue`, `em_transito` ou `sem_eventos` (obs.: "saiu para entrega" **não** é "entregue").
- **Atualização automática:** se o provedor disser `entregue`, o envio vira `entregue`/`notificado`.
  Os outros status **não** são alterados sozinhos.
- **Resposta:**
```json
{ "codigo": "AA123456789BR", "status": "entregue", "situacao": "entregue",
  "carrier": "CARRIER_CORREIOS", "eventos": [ ... ], "consultado_em": "...",
  "cache": false, "aviso": "", "status_atualizado": true,
  "link": "https://rastreamento.correios.com.br/app/index.php?objeto=AA123456789BR" }
```
- **Erros:** `502` se o provedor falhar com chave configurada; `503` se a chave não estiver
  configurada; se havia cache, devolve a última consulta boa com `aviso`.

---

## 12. Configuração

Copie `.env.example` para `.env` (nunca commite o `.env`).

| Variável | Padrão | Função |
|---|---|---|
| `DATABASE_URL` | *(vazio)* | Postgres; vazio = SQLite local |
| `DB_PATH` | `database.db` | Caminho do SQLite (no Docker: `/data/database.db`) |
| `PORT` | `3000` | Porta do Uvicorn (Render injeta `PORT`) |
| `SMTP_HOST` | `smtp.gmail.com` | Servidor SMTP |
| `SMTP_PORT` | `587` | Porta (465 = TLS direto) |
| `SMTP_USER` / `SMTP_PASS` | — | Credenciais (Gmail: senha de app) |
| `SENDER_NAME` | `Rastreio Facil` | Nome do remetente |
| `SESSAO_DIAS` | `7` | Validade da sessão |
| `CORS_ORIGINS` | `*` | Origens permitidas (produção: seu domínio) |
| `LOGIN_MAX_TENT` | `10` | Tentativas de login por IP |
| `LOGIN_JANELA_SEG` | `300` | Janela do rate-limit (s) |
| `RASTREIO_API_KEY` | — | Chave da API de rastreio |
| `RASTREIO_API_URL` | API Wonca | URL do provedor (raramente muda) |
| `RASTREIO_CACHE_MIN` | `30` | Minutos de cache do rastreio |

Para a Cloudflare, os valores sensíveis vão em `wrangler secret put ...` ou em `.dev.vars`
(local). As variáveis não sensíveis ficam no `vars` do `wrangler.jsonc`.

---

## 13. Docker e Deploy

### 13.1 Docker
```bash
docker compose up -d --build
```
- Imagem: `python:3.12-slim`, usuário **non-root** (`appuser`), **HEALTHCHECK** em `/api/health`.
- O SQLite fica no volume nomeado **`rastreio-data`** (`/data/database.db`), preservado entre
  reinícios. **Não** use bind-mount de arquivo (`./database.db:/app/database.db`): o Docker cria
  um diretório se o arquivo não existir e o SQLite falha.
- `.dockerignore` impede que `.env`, `.venv`, `*.db`, `.wrangler/` etc. entrem na imagem.
- Para Postgres, descomente o serviço `db:` no `docker-compose.yml` e ajuste `DATABASE_URL`.

### 13.2 Cloudflare Workers + D1
1. `wrangler d1 create rastreio-facil` → copie o `database_id` para `wrangler.jsonc`.
2. `wrangler d1 execute rastreio-facil --remote --file cloudflare/schema.sql`.
3. `wrangler secret put RASTREIO_API_KEY` (e `SMTP_USER`/`SMTP_PASS`).
4. `wrangler deploy`.

> **Regra de ouro:** `cloudflare/worker.js` e `cloudflare/schema.sql` devem acompanhar o
> `main.py`/`db.py`. O `test_analise_erros.py` compara as rotas dos dois e o `APP_VERSAO`.

### 13.3 Nuvem (Render/Railway/VPS)
Build `pip install -r requirements.txt`; start
`uvicorn main:app --host 0.0.0.0 --port $PORT`; configure `DATABASE_URL` e os segredos.

---

## 14. Testes e verificação

### 14.1 Suíte pytest (`tests/`)
```bat
pip install -r requirements.txt -r requirements-dev.txt
pytest
```
- `tests/test_api.py` — **in-process** (TestClient + banco temporário): serviço, auth,
  CRUD, validações, listagem/busca/paginação, lixeira e permissões, estatísticas, backup,
  notificações (fallbacks), SQL injection, unicode, payloads malformados. **Não precisa de servidor.**
- `tests/test_rastreio.py` — normalização do provedor (Correios/Cainiao) e
  `POST /rastrear` (atualização + cache), com o provedor **simulado**.
- `tests/test_browser.py` — **navegador** (Selenium + Chrome). Marcado `browser`, roda só com:
  ```bat
  pytest --browser
  ```
  A fixture `live_server` sobe um Uvicorn real em porta livre com banco temporário.

Marcadores são configurados em `pytest.ini`; sem `--browser`, os testes de navegador são pulados.

### 14.2 Verificador estático (`test_analise_erros.py`)
Confere invariantes de código/HTML/JS sem subir nada, incluindo:
versão front/back, **paridade de rotas** entre `main.py` e `cloudflare/worker.js`
(método + caminho), headers de segurança, debounce da busca, índice único de código,
e "arquivos mortos" que não podem voltar. Rode: `python test_analise_erros.py`.

### 14.3 Scripts E2E manuais (contra servidor real em `127.0.0.1:3001`)
`teste_fluxo.py`, `teste_rastreio.py` (banco temporário, sem servidor) e, contra um servidor real:
`teste_api_real.py`, `teste_crud.py`, `teste_bordas.py`, `teste_canais.py`, `teste_chrome.py`.
Semeie `admin@empresa.com` / `admin12345`.

Dois scripts sobem o servidor sozinhos (banco temporário) e não precisam de nada semeado:

- `python teste_operacional.py` — E2E da API: health, bootstrap do admin, login (ok/401),
  cadastro de 8 pessoas, duplicado, status, lixeira (excluir/restaurar/purgar), estatísticas e Excel.
- `python teste_navegador_demo.py --pausa 20` — abre o **Chrome visível** e clica o fluxo de verdade
  (login → cadastrar várias → mudar status → apagar → ver lixeira → **Exportar Excel**), salvando
  prints de cada etapa em `evidencias/` e a planilha em `envios_teste.xlsx`.
- `python teste_usuarios_brave.py --pausa 20` — abre o **Brave** (ou `--chrome`) e cria um **usuário
  não-admin** pela tela 👥 *Usuários*, provando que ele não vê a gestão de usuários; prints em
  `evidencias_usuarios/`. Use `--base http://127.0.0.1:3000` para rodar no servidor que já está no ar.

### 14.4 CI
`.github/workflows/ci.yml` roda em push/PR: `test_analise_erros.py`, `pytest`,
`teste_fluxo.py` e `teste_rastreio.py` (Python 3.12), mais um job `navegador` que roda
`pytest --browser` (Chrome headless) cobrindo login, cadastro e lixeira na interface.

> **Dica Windows:** se aparecer `UnicodeEncodeError` nos scripts (por causa de `→`), rode com
> `set PYTHONUTF8=1`.

---

## 15. Histórico de versões

| Versão | Principais mudanças |
|---|---|
| **v20** | Segurança (logout com revogação, senha ≥ 8, rate-limit, CORS por env, limpeza de sessões); paginação/busca server-side; estatísticas no SQL; gestão de usuários; troca de senha; eventos/histórico; notificação em massa. |
| **v21** | Correção: "notificado" **não** regride `entregue` (só `pendente` → `a_caminho`). |
| **v22** | Lixeira (soft delete) com restaurar/purgar (admin); **backup** do SQLite; `/auth/estado` informa admin; cards de estatística filtram a lista; export CSV/XLSX do recorte filtrado; histórico por envio. |
| **v23** | **Rastreio automático** (API Wonca) com cache; modal de rastreio; **Cloudflare Worker + D1** espelhando o backend (`cloudflare/worker.js`, `cloudflare/schema.sql`). |
| **v24** | Detecção de backend em várias portas do Live Server (5500–5503); **debounce** na busca; **cabeçalhos de segurança**; **índice único** de `codigo` + insert a prova de corrida; `restreiofacil/` ignorado; suíte **pytest** + **CI**; **Dockerfile** non-root com HEALTHCHECK; documentação reescrita. |
| **v25** | Correção: o **card "Lixeira" mostrava sempre vazio** — o front não buscava os `status='excluido'` (a listagem padrão da API os exclui), deixando os botões **Restaurar/Apagar def.** inalcançáveis. Agora o admin carrega a lixeira e o filtro "Todos" não mistura excluídos. Testes de navegador passam a rodar (`pytest --browser`). |
| **v26** | **Gestão de usuários na interface** (antes só existia na API): botão 👥 no topo (só admin), com lista de usuários (badge admin/usuário, inativo) e formulário para **criar usuário não-admin** (nome, e-mail, senha ≥ 8) na própria tela; permite alternar admin/ativo. Correção de CSS: a regra global `[hidden]` faz o atributo vencer o `display` dos componentes — antes o **card "Lixeira" aparecia para não-admins** (`#stat-lix` com `.stat { display:flex }`). Teste de navegador novo (`test_cria_usuario_nao_admin_pelo_modal`). |
| **v27** | **Blindagem (self-admin-guard)**: o chip "Remover admin" não fica ativo na **própria linha** do usuário logado — evita o admin se rebaixar sozinho e ficar sem nenhum administrador. Teste de navegador verifica que a linha do próprio admin não tem o botão de alternar admin. |

---

## 16. Troubleshooting

| Sintoma | Causa provável / solução |
|---|---|
| HTML/JS antigo no navegador | Headers `no-store`/`?v=27` já cobrem; force recarga (Ctrl+F5). Confira `window.APP_V`. |
| Login não entra | Senha errada, usuário **inativo**, ou rate-limit (`429`) — espere a janela. |
| `401` em rotas de dados | Token ausente/expirado ou sessão revogada; faça login de novo. |
| `403` no restaurar/purgar/backup/usuarios | Recurso exclusivo de **admin**. |
| `409` ao editar | O código informado já pertence a outro envio. |
| `422` ao criar/editar | Código fora do padrão, destinatário vazio, sem e-mail nem celular, ou senha < 8. |
| E-mail não sai | `SMTP_USER`/`SMTP_PASS` ausentes ou senha não é "senha de app" do Gmail. |
| "Rastrear" só abre os Correios | Falta `RASTREIO_API_KEY`. |
| `503`/`502` no rastrear | `503` = sem chave; `502` = provedor fora do ar (se havia cache, ele é mostrado). |
| Índice único não foi criado | Banco legado tem códigos duplicados; remova os duplicados e recrie o banco/índice. |
| Docker não acha o banco | Use o volume (`/data`), não bind-mount de arquivo. |
| `UnicodeEncodeError` nos testes | Console Windows em cp1252: rode com `set PYTHONUTF8=1`. |
| Worker diverge do main.py | Espelhe a mudança; o CI/`test_analise_erros.py` acusa a divergência. |

---

*Documentação mantida junto ao código. Ao mudar comportamento, atualize este arquivo e, se for
mudança de front, suba a versão (§5.3).*
