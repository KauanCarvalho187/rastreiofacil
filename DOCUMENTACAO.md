# 📦 Rastreio Fácil — Documentação Completa do Sistema

> Sistema web de gestão e notificação de códigos de rastreio dos Correios.
> Backend **FastAPI (Python)** + Frontend **HTML/CSS/JS vanilla** (sem build) +
> Banco **SQLite** (local), **Postgres** (`DATABASE_URL`) ou **Cloudflare D1**.
>
> **Versão do front/back: `31`** (campo `APP_VERSAO` no `main.py` e `APP_V` no `static/app.js`).
> Documentação revisada em **21/10/2026**, conferida linha a linha contra
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

> **Backlog de melhorias:** o arquivo [`AUDITORIA.md`](AUDITORIA.md) lista (com status) os
> itens pendentes de segurança, acessibilidade, CI, Docker e dependências.

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
├─ servidor-local.ps1       # Servidor de arquivos (PowerShell) sem Python, porta 8080
├─ abrir-servidor-local.bat # Atalho para o servidor-local.ps1 (só interface)
├─ iniciar-sistema.bat      # Atalho: cria/usa .venv, instala deps e sobe o backend
│
├─ static/                  # Front (servido em /static e como raiz da tela única)
│  ├─ index.html            # Tela única (cadastro, lista, modais, login)
│  ├─ styles.css            # Tema escuro
│  ├─ app.js                # Toda a lógica do front (API + offline localStorage)
│  └─ libs/                 # Bibliotecas vendorizadas (sem CDN)
│     └─ xlsx.full.min.js   # SheetJS 0.18.5 (861 KB) — carregado SOB DEMANDA (v29)
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
├─ teste_operacional.py     # E2E da API: login, cadastro em lote, lixeira/purgar, Excel
├─ teste_navegador_demo.py  # Demonstração no Chrome (Selenium visível) + prints em evidencias/
│
├─ Dockerfile               # Imagem (usuário non-root + HEALTHCHECK)
├─ docker-compose.yml       # Compose (volume do SQLite; Postgres opcional)
├─ .dockerignore            # Não envia .env, .venv, *.db, etc. para a imagem
├─ requirements.txt         # Dependências de produção
├─ requirements-dev.txt     # Dependências de teste (pytest, selenium)
├─ .env.example             # Modelo de configuração
├─ .github/workflows/ci.yml # CI (GitHub Actions)
├─ DOCUMENTACAO.md          # Este arquivo
├─ COMO_RODAR.md            # Guia rápido de execução
├─ AUDITORIA.md             # Backlog de melhorias (segurança, a11y, CI, deps) + status
├─ README.md                # Resumo do projeto (GitHub)
└─ PROMPT-VERIFICACAO-PROFUNDA.md # Roteiro de verificação profunda do sistema
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
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self' http://localhost:* http://127.0.0.1:*; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'` (v31)
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` — **só** quando a requisição
  chega por HTTPS (direto ou via proxy, detectado pelo `X-Forwarded-Proto`).

O `cloudflare/worker.js` aplica os **mesmos** cabeçalhos de segurança (inclusive nos assets
servidos pelo `ASSETS`).

Cache:
- `/static/libs/*` e `/static/img/*` → `public, max-age=31536000, immutable`;
- arquivos `.js/.css/.html/.json` → `no-cache, must-revalidate`;
- `/`, `/main`, `/login` (HTML) → `no-store`.

### 5.2 CORS
Controlado por `CORS_ORIGINS` (lista separada por vírgula).

**v31:** o padrão **não é mais `*`**. Sem `CORS_ORIGINS` vale uma lista restrita ao ambiente
local — `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:8080`,
`http://127.0.0.1:8080`, Live Server `:5500`–`:5503` (localhost e 127.0.0.1) e `null`
(páginas abertas via `file://`). Qualquer outra origem **não** recebe
`Access-Control-Allow-Origin`.

**Em produção**, defina as origens do app:
```
CORS_ORIGINS=https://app.seu-dominio.com,https://seu-dominio.com
```

### 5.3 Versionamento do front (anti "aba velha")
O `app.js` guarda `APP_V = '31'` e pergunta `GET /api/versao`. Se o servidor responder outra
versão, o front se recarrega sozinho. O `index.html` referencia os assets com `?v=31`.
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
| `usuarios` | `id`, `nome`, `email` (único), `senha_hash`, `admin`, `ativo`, `criado_em` — **v28: sempre 1 linha** (o admin) |
| `sessoes` | `token` (PK), `usuario_id`, `expira_em` |
| `eventos` | `id`, `envio_id`, `de_status`, `para_status`, `por_usuario`, `detalhe`, `criado_em` |
| `rastreios` | `id`, `envio_id` (único), `situacao`, `carrier`, `eventos` (JSON), `consultado_em` |

Índices: `idx_envios_codigo`, `idx_envios_status`, `idx_eventos_envio` e o **índice único**
`idx_envios_codigo_unico` (um código de rastreio só pode existir uma vez).

> **v28:** a tabela `usuarios` continua no banco (o login precisa dela), mas passa a ter
> **uma única linha**: a conta do admin. Contas antigas são apagadas no boot do servidor
> (junto com as sessões) — ver §7.

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

O sistema tem **uma única conta de acesso**: o **admin**. Não existe cadastro de usuários,
nem tela/API de gestão de contas.

### 7.1 A conta única

| Item | Valor |
|---|---|
| E-mail (login) | `ADMIN_EMAIL` — padrão **`admin@admin.com`** |
| Nome exibido | `ADMIN_NOME` — padrão `Admin` |
| Senha inicial | `ADMIN_SENHA` — **obrigatória em produção**; em dev local (SQLite) o padrão é `admin12345` |

**v31 — a senha padrão pública saiu do código:**
- **Desenvolvimento local (SQLite):** sem `ADMIN_SENHA` no `.env`, o admin é criado com
  `admin12345` (o log só avisa que a senha padrão foi usada).
- **Produção (Postgres / `DATABASE_URL`):** sem `ADMIN_SENHA` o admin **não é criado** e o
  log mostra um erro pedindo a variável.
- **Cloudflare Worker:** sem o segredo `ADMIN_SENHA` o admin **não é criado** — rode
  `npx wrangler secret put ADMIN_SENHA` **antes** do primeiro deploy.
- A senha **nunca** é impressa no log.

**`garantir_admin()`** roda no boot do servidor (`lifespan` do FastAPI) e, no Worker da
Cloudflare, a cada requisição `/api` (`garantirAdmin(env)`). Ela:

1. cria a conta `ADMIN_EMAIL` se ainda não existir, com a senha de `ADMIN_SENHA`;
2. garante que ela está com `admin=1` e `ativo=1` (repromove/reativa se alguém mexer no banco);
3. **apaga todas as outras contas** (`DELETE FROM usuarios WHERE email <> ?`) e as
   **sessões** delas (`DELETE FROM sessoes WHERE usuario_id <> ...`).

> ⚠️ A senha de `ADMIN_SENHA` só vale **na criação** da conta. Depois que ela existe,
> trocar o `.env` não muda a senha do banco — use `POST /api/auth/trocar-senha` na tela.

> 🔁 **Migração de bancos antigos:** quem vem da era multi-usuário tem as contas extras
> apagadas no primeiro boot — o sistema volta a ter um único login automaticamente.

### 7.2 Mecanismo

- **Senha:** armazenada como `PBKDF2-HMAC-SHA256`, 100.000 iterações, sal aleatório de 16 bytes
  (`sal$hash`). A senha **nunca** é guardada em texto puro.
- **Sessão:** token aleatório (`secrets.token_hex(32)`) na tabela `sessoes`, com validade de
  `SESSAO_DIAS` (padrão 7). O cliente envia `Authorization: Bearer <token>`.
- **Login:** `POST /api/auth/login` com `{email, senha}` — o e-mail precisa ser o do admin.
- **Rate-limit de login:** por IP, `LOGIN_MAX_TENT` (10) falhas em `LOGIN_JANELA_SEG` (300s) → `429`.
- **Logout:** `POST /api/auth/logout` **revoga** o token no banco (não é só no navegador).
- **Troca de senha:** `POST /api/auth/trocar-senha` (senha nova ≥ 8 caracteres).
  **v31:** a troca **encerra as outras sessões** do admin (a sessão que fez a troca continua
  válida) — assim, um token vazado deixa de funcionar depois que a senha muda.
- **Rotas de dados:** todas exigem token (`Depends(auth_usuario)`) — **não existe modo anônimo**.
- Sessões **expiradas** são limpas no boot do app (`lifespan`).
- `GET /api/auth/estado` responde `{admin, email}` — o front usa o `email` para mostrar o login fixo
  e o `admin` para decidir se exibe o botão de **Backup**.

---

## 8. Referência completa da API

Base: `http://localhost:3000`. Todas as rotas `/api/*` respondem JSON.
Erros do FastAPI vêm como `{"detail": "mensagem"}`.

### 8.1 Rotas de serviço (públicas)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | `{ok, db:{configured,connected,driver,url_safe}, smtp, rastreio}` |
| GET | `/api/db-status` | Status detalhado do banco |
| GET | `/api/versao` | `{versao}` (hoje `"30"`) |
| GET | `/api/auth/estado` | `{admin, email}` — `admin` = o token do header é de admin; `email` = login do admin (`admin@admin.com`) |

### 8.2 Autenticação

| Método | Rota | Corpo | Observações |
|---|---|---|---|
| POST | `/api/auth/login` | `{email, senha}` | `{token, user:{id,nome,email,admin}}`; `401` inválido; `429` rate-limit. Só existe a conta do admin. |
| POST | `/api/auth/logout` | — (header) | Revoga o token. |
| POST | `/api/auth/trocar-senha` | `{senha_atual, senha_nova}` | `401` senha atual errada; `422` nova < 8. |

> **v28:** não existe mais `POST /api/auth/registrar` (cadastro de usuário) nem
> `GET /api/usuarios` / `PATCH /api/usuarios/{uid}` (gestão de contas). A conta do admin
> é criada sozinha no boot do servidor (§7).

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

> **v28:** todas as rotas desta tabela exigem **token** (`Authorization: Bearer <token>`);
> sem ele a resposta é `401`. Como existe **uma única conta** (o admin), os itens marcados
> como "**Admin.**" são liberados para o único usuário do sistema.

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

### 8.4 Dashboard e backup

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/estatisticas` | `{total, pendente, a_caminho, entregue}` (contado no SQL). |
| GET | `/api/backup` | **Admin.** Baixa o arquivo SQLite (`backup-rastreio-<data>.db`). `400` se Postgres; `404` se o arquivo não existe. |

> **v28:** as rotas de gestão de usuários (`GET /api/usuarios` e `PATCH /api/usuarios/{uid}`)
> foram **removidas**. Não há mais lista de contas nem alteração de perfil: existe uma só conta.

### 8.5 Páginas

| Método | Rota | Retorno |
|---|---|---|
| GET | `/` | `static/index.html` (sem cache) |
| GET | `/main`, `/login` | Aliases de compatibilidade → mesma tela |
| GET | `/static/*` | Arquivos estáticos |

---

## 9. Funcionalidades do frontend

- **Tela única** (`index.html`): cadastro, importação, lista, estatísticas e modais.
- **Autenticação:** modal de login com **apenas o campo de senha** — o e-mail do admin é fixo e
  aparece na tela (preenchido com o valor de `GET /api/auth/estado`). Botão que só aparece para
  admin (backup).
- **Cadastro rápido** e **em lote** (textarea de CSV ou arraste de arquivo `.csv/.xlsx/.xls`).
- **Lista** com busca (com **debounce** de 150ms), filtro por status (cards clicáveis) e
  lixeira. A busca percorre **todas as páginas** do servidor (não trava em 200).
  Renderiza em **blocos de 120 linhas** com o botão "Carregar mais" (v29) — evita um
  `innerHTML` gigante que travava a rolagem com centenas de envios.
- **Edição** em modal (`PUT`) e **status** por atalho.
- **WhatsApp:** monta a mensagem e abre `wa.me` (o envio real é feito pelo usuário).
- **E-mail:** chama `POST /api/notificacoes`; se o SMTP não estiver configurado, cai em `mailto:`.
- **Rastrear:** modal que consome `POST .../rastrear` e mostra a linha do tempo; botão para o
  site dos Correios.
- **Exportar** CSV/Excel do recorte filtrado e **Backup do banco** (admin).
  A lib do Excel é baixada **sob demanda** (v29) — ver §9.2.
- **Modo offline:** detecta se há backend; sem ele, grava no `localStorage` e mostra um aviso.
  Quando a API volta, sincroniza (com *backoff* de 5s até 60s).
- **Erros visíveis:** erros de JS aparecem numa **barra vermelha** no rodapé.
- **Anti-aba-velha:** confere `GET /api/versao` e se recarrega se o servidor estiver em versão mais nova.

### 9.1 Detecção de backend / portas
O front decide se o backend está disponível tentando as portas do Live Server
(`5500`–`5503`) e a própria origem. Isso evita o antigo problema de "backend confirmado na 5501
mas rodando na 5502". `window.APP_V` mostra a versão do front no console.

### 9.2 Performance do front (v29)

**O peso do site.** Medido no Chrome (`performance.getEntriesByType('resource')`):

| | Antes (v28) | Depois (v29) |
|---|---|---|
| Payload inicial | **957 KB** | **71 KB** (−93%) |
| `xlsx.full.min.js` (SheetJS) | 861 KB, `<script>` **bloqueante** | 861 KB, **sob demanda** |
| Requisições por `load()` | 5 | 4 |
| Passes de `.filter()` por `render()` | 5 | 1 |

**Lazy-load do Excel.** A lib `static/libs/xlsx.full.min.js` (SheetJS 0.18.5, 861 KB) saiu do
`<body>` do `index.html`. Agora o `app.js` a injeta no `<head>` **só quando** o usuário clica em
*Exportar Excel* ou solta um `.xlsx` na área de importação (`carregarXLSX()` — uma promise
compartilhada, para não baixar duas vezes em cliques seguidos). Quem nunca usa Excel **nunca
paga** os 861 KB.

> ⚠️ **Ao mexer no Excel:** o `XLSX` só existe **depois** do `await carregarXLSX()`.
> Se for adicionar código que use `XLSX`, ele tem que ser `async` e esperar a promise.

**Demais otimizações.**
- `filtrados()` faz **uma única passagem** sobre `state.envios` e devolve a lista **e** os
  contadores dos cards (antes eram 5 `.filter()` separados a cada tecla digitada).
- O total da lixeira vem do `total` que a **própria página da lixeira** já devolve
  (antes era uma requisição extra `?limit=1` só para contar).
- A lista é renderizada em **blocos de 120** (`PAGINA_LINHAS`) com o botão **"Carregar mais"**.
- O CSS usa `content-visibility: auto` + `contain-intrinsic-size` em `.item`: o browser pula o
  layout/paint das linhas fora da tela.

### 9.3 Área de rolagem dos rastreios (v30)

A lista da direita (onde ficam os rastreios cadastrados) tem a própria barra de rolagem.
Até a v29 ela era limitada a `min(92vh, 1150px)`, o que deixava a barra **cortada embaixo**
da tela (era preciso rolar a página para alcançar o fim dela).

Na **v30** o limite desktop foi removido e a área passou a ocupar **a coluna inteira**:

```css
@media (min-width: 861px) {
  .lista-scroll { max-height: none; min-height: 0; contain: size; }
}
```

O `contain: size` é o truque: ele faz o tamanho da área **não depender do conteúdo**
(são 43+ itens = 6.259px). Assim ela preenche a coluna da lista (a mesma altura do
formulário, 989px) e o excesso passa a rolar **por dentro** dela.

| Janela | Altura da área de rolagem (v29) | (v30) |
|---|---|---|
| 1920×1080 | 854px | **957px** |
| 1536×864 | 655px | **957px** |
| 1366×768 | 567px | **957px** |

> No celular (≤860px) a coluna vira uma só e a área mantém o limite de `60vh`
> (senão a página ficaria com 6.000px de rolagem).

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
| `CORS_ORIGINS` | lista local de dev | Origens permitidas (produção: seu domínio) |
| `LOGIN_MAX_TENT` | `10` | Tentativas de login por IP |
| `LOGIN_JANELA_SEG` | `300` | Janela do rate-limit (s) |
| `ADMIN_EMAIL` | `admin@admin.com` | Login da única conta de acesso |
| `ADMIN_NOME` | `Admin` | Nome exibido do admin |
| `ADMIN_SENHA` | `admin12345` (só em dev local) | Senha **inicial** do admin (vale só na criação da conta; **obrigatória** em produção) |
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
1. `wrangler d1 create rastreio-facil` → copie o `database_id` para o `wrangler.jsonc`.
2. `wrangler d1 execute rastreio-facil --remote --file cloudflare/schema.sql`.
3. `wrangler secret put RASTREIO_API_KEY` (e `SMTP_USER`/`SMTP_PASS`).
4. `wrangler secret put ADMIN_SENHA` — senha inicial do `admin@admin.com`.
   **v31: obrigatório** — sem esse segredo o Worker **não cria** a conta do admin
   (não existe mais senha padrão pública).
5. `wrangler deploy`.

> O e-mail e o nome do admin ficam no `vars` do `wrangler.jsonc` (`ADMIN_EMAIL` / `ADMIN_NOME`).
> O `CORS_ORIGINS` do Worker também fica no `vars` (vazio = lista local de dev).

> **Regra de ouro:** `cloudflare/worker.js` e `cloudflare/schema.sql` devem acompanhar o
> `main.py`/`db.py`. O `test_analise_erros.py` compara as rotas dos dois e o `APP_VERSAO`.

### 13.3 Nuvem (Render/Railway/VPS)
Build `pip install -r requirements.txt`; start
`uvicorn main:app --host 0.0.0.0 --port $PORT`; configure `DATABASE_URL` e os segredos
(inclusive `ADMIN_EMAIL`/`ADMIN_SENHA`).

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
o modo **admin único** (sem tela nem rotas de usuários) e "arquivos mortos" que não podem
voltar. Rode: `python test_analise_erros.py`.

### 14.3 Scripts E2E manuais
Dois scripts sobem o servidor sozinhos (banco temporário) e não precisam de nada semeado:

- `python teste_operacional.py` — E2E da API: health, criação do admin, login (ok/401),
  cadastro de 8 pessoas, duplicado, status, lixeira (excluir/restaurar/purgar), estatísticas e Excel.
- `python teste_navegador_demo.py --pausa 20` — abre o **Chrome visível** e clica o fluxo de verdade
  (login → cadastrar várias → mudar status → apagar → ver lixeira → **Exportar Excel**), salvando
  prints de cada etapa em `evidencias/` e a planilha em `envios_teste.xlsx`.

### 14.4 CI
`.github/workflows/ci.yml` roda em push/PR: o verificador estático `test_analise_erros.py` e a
suíte `pytest` (Python 3.12), mais um job `navegador` que roda `pytest --browser` (Chrome headless)
cobrindo login, cadastro e lixeira na interface.

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
| **v28** | **Admin único**: o sistema passa a ter **uma só conta de acesso** — `admin@admin.com` (configurável por `ADMIN_EMAIL`/`ADMIN_NOME`/`ADMIN_SENHA`). O backend cria/repara essa conta no boot (`garantir_admin()`) e **apaga as contas extras** (e suas sessões) — bancos da era multi-usuário migram sozinhos. **Removidos**: `POST /api/auth/registrar`, `GET /api/usuarios`, `PATCH /api/usuarios/{uid}`, o botão/modal 👥 *Usuários* e o `UsuarioCreate`. O login no front agora pede **só a senha** (o e-mail do admin aparece fixo na tela, preenchido por `GET /api/auth/estado` → `{admin, email}`); **todas** as rotas de dados exigem token (não há mais modo anônimo). Worker da Cloudflare espelhado (`garantirAdmin(env)`). Documentação (`README`, `DOCUMENTACAO`, `COMO_RODAR`) atualizada para o modo de conta única. |

| **v30** | **A área de rolagem dos rastreios desce a página inteira.** A lista da direita tinha a barra limitada a `min(92vh, 1150px)` e ela ficava **cortada embaixo** da tela (era preciso rolar a página para alcançar o fim). No desktop o limite foi removido e a área agora ocupa a coluna inteira (`contain: size` faz o tamanho não depender dos 6.259px de conteúdo): **957px em qualquer resolução** (era 854px em 1080p, 655px em 864p e 567px em 768p). No celular segue o limite de `60vh`. Também foi removida a regra `.lista-scroll` duplicada no CSS. |
| **v31** | **Segurança (5 críticos corrigidos — see [`AUDITORIA.md`](AUDITORIA.md)).** ① **Senha padrão pública fora do código**: o Worker usava `env.ADMIN_SENHA \|\| 'admin12345'` e as `vars` do `wrangler.jsonc` não tinham `ADMIN_SENHA` → sem o segredo (`npx wrangler secret put ADMIN_SENHA`) o admin **não é criado**; no FastAPI, em produção (Postgres) sem `ADMIN_SENHA` também não; em dev local (SQLite) segue `admin12345` — e a senha **não é mais impressa no log**. ② **CORS**: o padrão deixou de ser `*` e passou a ser a lista local de dev (app `:3000`/`:8080`, Live Server `:5500`–`:5503`, `file://`); em produção, defina `CORS_ORIGINS`. ③ **Trocar a senha agora encerra as outras sessões** (a atual continua) — um token vazado deixa de valer. ④ **Content-Security-Policy** (`default-src 'self'`, `script-src 'self'`, `frame-ancestors 'self'`, …) + **HSTS** quando a conexão é HTTPS — no FastAPI **e** no Worker (inclusive nos assets). ⑤ **Bug do modal de login**: a flag `_loginPedido` ficava presa e o modal **nunca mais abria** — agora é liberada ao fechar o modal e no logout. Extras: o Worker não repassa mais `Authorization`/`Cookie` do cliente ao asset server, `Access-Control-Max-Age` e `CORS_ORIGINS` no `vars`. Novo **`AUDITORIA.md`** com o backlog completo (86 itens) e o status de cada um. |
| **v29** | **Performance: o site ficou 13× mais leve.** A lib do Excel (`xlsx.full.min.js`, SheetJS 0.18.5, **861 KB**) saiu do `<script>` bloqueante do `index.html` e passa a ser baixada **sob demanda** (`carregarXLSX()`), só ao exportar/importar `.xlsx` → payload inicial de **957 KB → 71 KB (−93%)**. `filtrados()` agora faz **uma única passagem** devolvendo a lista e os contadores dos cards (antes eram 5 `.filter()` por render); o total da lixeira reaproveita o `total` da página já carregada (elimina 1 requisição por `load()`); a lista renderiza em **blocos de 120** com o botão **"Carregar mais"**; o CSS aplica `content-visibility: auto` em `.item` (rolagem leve sem virtualização em JS). Teste de navegador novo garante que a lib **não** é baixada no boot. |

---

## 16. Troubleshooting

| Sintoma | Causa provável / solução |
|---|---|
| HTML/JS antigo no navegador | Headers `no-store`/`?v=30` já cobrem; force recarga (Ctrl+F5). Confira `window.APP_V`. |
| Login não entra | Senha errada, conta ainda não criada (o servidor cria no boot) ou rate-limit (`429`) — espere a janela. |
| `401` em rotas de dados | Token ausente/expirado ou sessão revogada; faça login de novo. |
| `403` no restaurar/purgar/backup | Recurso exclusivo de **admin**. |
| `409` ao editar | O código informado já pertence a outro envio. |
| `422` ao criar/editar | Código fora do padrão, destinatário vazio, sem e-mail nem celular, ou senha < 8. |
| Não encontro a senha do admin | O padrão é `admin12345`; troque com `ADMIN_SENHA` **antes** do 1º boot ou use "Trocar senha" depois de entrar. |
| E-mail não sai | `SMTP_USER`/`SMTP_PASS` ausentes ou senha não é "senha de app" do Gmail. |
| "Rastrear" só abre os Correios | Falta `RASTREIO_API_KEY`. |
| "Biblioteca Excel não carregou" / export não abre | A lib é baixada sob demanda (v29): na 1ª vez pode demorar alguns segundos. Se falhar, é falta de internet — recarregue (Ctrl+F5) e tente de novo. |
| `503`/`502` no rastrear | `503` = sem chave; `502` = provedor fora do ar (se havia cache, ele é mostrado). |
| Índice único não foi criado | Banco legado tem códigos duplicados; remova os duplicados e recrie o banco/índice. |
| Docker não acha o banco | Use o volume (`/data`), não bind-mount de arquivo. |
| `UnicodeEncodeError` nos testes | Console Windows em cp1252: rode com `set PYTHONUTF8=1`. |
| Worker diverge do main.py | Espelhe a mudança; o CI/`test_analise_erros.py` acusa a divergência. |

---

*Documentação mantida junto ao código. Ao mudar comportamento, atualize este arquivo e, se for
mudança de front, suba a versão (§5.3).*
