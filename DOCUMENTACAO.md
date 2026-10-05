# 📦 Rastreio Fácil — Documentação Completa do Sistema

> Sistema web de gestão e notificação de códigos de rastreio dos Correios.
> Backend **FastAPI (Python)** + Frontend **HTML/CSS/JS vanilla** + Banco **SQLite** (local) **ou Postgres** (`DATABASE_URL`).
> Documentação **revisada em 05/10/2026** (front na versão `19`) — conferida linha a linha contra
> `main.py`, `db.py`, `static/app.js`, `static/index.html` e `static/resgate.html`. Reflete o estado atual e corrigido do código.

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
10. [Sistema de notificações](#10-sistema-de-notificações)
11. [Configuração (.env)](#11-configuração-env)
12. [Histórico de correções importantes](#12-histórico-de-correções-importantes)
13. [Solução de problemas (troubleshooting)](#13-solução-de-problemas-troubleshooting)
14. [Segurança](#14-segurança)
15. [Limitações e melhorias futuras](#15-limitações-e-melhorias-futuras)
16. [Roteiro de verificação (smoke test)](#16-roteiro-de-verificação-smoke-test)

---

## 1. Visão geral

O **Rastreio Fácil** permite que uma loja/vendedor cadastre envios (destinatário + código de rastreio + contato) e notifique cada cliente por **e-mail** ou **WhatsApp** com o código e o link de rastreamento oficial dos Correios.

**Fluxo principal:**

```
Cadastro (manual, CSV ou Excel)
        │
        ▼
  Lista de envios ──► Editar / Excluir / Buscar / Filtrar por status
        │
        ▼
  Notificação (botão por envio: WhatsApp ou E-mail)
        ├── canal E-mail   → envio automático via SMTP (se configurado)
        └── canal WhatsApp → copia a mensagem e abre wa.me (envio manual)
        │
        ▼
  Status do envio: pendente → a caminho → entregue + Estatísticas no dashboard
```

> 🔌 **Modo offline:** se o backend estiver parado, o sistema continua utilizável — os envios ficam no
> `localStorage` do navegador e são **sincronizados automaticamente** quando o servidor volta (ver §9.9).

**Acesso:**

| Página | URL | Descrição |
|---|---|---|
| Sistema (tela única) | `http://localhost:3000/` | Tela principal (`static/index.html` + `app.js`) |
| Aliases da tela | `http://localhost:3000/main` e `.../login` | Mesma tela (`/login` abre com o modal de login disponível) |
| API | `http://localhost:3000/api/*` | Endpoints REST |
| Diagnóstico | `http://localhost:3000/api/health` | `{ ok, db, smtp }` |

**Credenciais:** não existe usuário padrão. No primeiro acesso (`GET /api/auth/estado` → `temUsuarios: false`) a tela
mostra o formulário de **cadastro do primeiro administrador** (bootstrap, botão *Criar admin*). Em banco já populado,
só o login funciona — em ambiente de teste local o admin usado foi `admin@empresa.com` / `123456`.

## 2. Stack tecnológica

| Camada | Tecnologia | Observação |
|---|---|---|
| Backend | **Python 3.12 + FastAPI** | `main.py`, servido por **Uvicorn** na porta 3000 |
| Banco de dados | **SQLite** (padrão) **ou Postgres** | `db.py` decide: com `DATABASE_URL` (postgres://) usa `asyncpg`; sem ela usa `aiosqlite` + `database.db` |
| E-mail | **aiosmtplib** | SMTP (padrão Gmail :587 com STARTTLS; :465 usa TLS direto) |
| Config | **python-dotenv** | Arquivo `.env` (modelo em `.env.example`) |
| Frontend | **HTML5 + CSS3 + JavaScript vanilla** | Sem frameworks; tela única com abas/cards e modais |
| Planilhas | **SheetJS (xlsx.full.min.js)** | Local, em `static/libs/` — import/export Excel |
| Senhas | **PBKDF2-HMAC-SHA256** (100k iterações) | `hashlib` nativo + sal aleatório de 16 bytes |
| Sessões | **Token Bearer** (64 hex) | Tabela `sessoes` com expiração de 7 dias (`SESSAO_DIAS`) |
| Testes | **Script próprio** | `test_analise_erros.py` (59 verificações estáticas de main.py/bat/app.js/index.html/resgate.html) |

**Dependências (`requirements.txt`):**
```
fastapi
uvicorn[standard]
python-dotenv
aiosqlite
aiosmtplib
asyncpg
```
> `asyncpg` só é importado quando `DATABASE_URL` aponta para Postgres (`db.py` faz o `import` dentro de `get_pool()`).

---

## 3. Estrutura de arquivos

```
rastreio-sistema1/
├── main.py                  # Backend FastAPI — TODA a API + rotas de páginas (executa o app)
├── db.py                    # Camada de banco dual (SQLite ↔ Postgres) + init_db/migrações
├── database.db              # Banco SQLite (criado automaticamente no 1º start; Postgres não usa)
├── requirements.txt         # Dependências Python
├── .env                     # Config real (SMTP/porta/DATABASE_URL — NÃO versionar!)
├── .env.example             # Modelo comentado do .env
├── .gitignore               # Ignora database.db, .env, .venv, __pycache__, *.log, etc.
├── DOCUMENTACAO.md          # Este documento (referência técnica completa)
├── COMO_RODAR.md            # Guia curto de execução/deploy
├── iniciar-sistema.bat      # Atalho Windows: acha um Python funcional, instala o que faltar e sobe o servidor
├── abrir-servidor-local.bat # Atalho Windows: abre o app por um servidor local SEM CACHE (não precisa de Python)
├── servidor-local.ps1       # Servidor HTTP estático em PowerShell (usado pelo .bat acima; porta 8080, no-store)
├── test_analise_erros.py    # Testes/verificações estáticas (59 checks) — rodar: python test_analise_erros.py
├── abrir-resgate.bat        # Atalho: abre a página de resgate (importação independente, sem app.js)
├── importar_planilha.py     # Importação CSV/Excel direto no banco pelo terminal (--dry-run disponível)
├── .vscode/settings.json    # Ajustes do Live Server (ignora logs/banco)
├── static/                  # Frontend servido em /static (tela única)
│   ├── index.html           # Tela principal (rotas /, /main e /login — login em modal)
│   ├── app.js               # TODA a lógica do front (dark UI, modais, offline, import/export)
│   ├── resgate.html         # Página de RESGATE: importa e salva no localStorage sozinha (não usa app.js)
│   ├── styles.css           # Estilos (tema escuro)
│   └── libs/
│       └── xlsx.full.min.js # SheetJS (leitura/geração de .xlsx)
└── .venv/                   # Ambiente virtual (não versionado)
```

> ℹ️ O projeto **não tem mais código morto**: em 29/09/2026 foram removidos `main_new.py` e
> `main_legado_backup.py` (backends antigos que nada importava) e o `iniciar-localhost.bat` (duplicava o
> `iniciar-sistema.bat`). Hoje o sistema é **`main.py` + `db.py` + `static/`**.
>
> 🔧 No mesmo dia o código vivo também foi enxugado: saíram o campo `criadoPor` (e o `JOIN` que só existia para
> alimentá-lo), os nomes duplicados de data (`createdAt`/`data`/`criado_em` → só **`criado_em`**), a normalização dos
> status antigos (`notificado`/`enviado`) e a migração de schema antigo do `db.py`. O CORS e o fallback de API para o
> Live Server foram **mantidos de propósito** — são o que permite testar o front fora do `:3000` (ver §5).

> ✅ Limpeza em 28/09/2026: removido o frontend legado (`static/main.html`, `static/script.js`, `static/index.html` antigo de login, `static/login.js`, `static/style.css`); o antigo `novo.*` virou o principal (`static/index.html` + `static/app.js` + `static/styles.css`). Antes (15/09/2026): removidos `server.js`, `script.js` (raiz), `package.json`, `data.json` e `static/_test_regex.js` (legados Node/teste). O sistema real é **`main.py` + `static/`**.
>
> ✅ Limpeza de 29/09/2026 (arquivos órfãos): removidos os logs mortos `py.err.log` (apontava para o venv quebrado de outro usuário), `py.out.log`, `server.err.log`, `server.out.log` (agora `*.log` está no `.gitignore`) e as imagens `static/img/bate-papo.svg` + `static/img/whatsapp-canal.svg` (não eram referenciadas por `index.html`, `styles.css` nem `app.js` — sobra do front legado; a pasta `static/img/` foi removida). Na mesma data foram removidos também os backends antigos `main_new.py` e `main_legado_backup.py`, o atalho duplicado `iniciar-localhost.bat`, as rotas órfãs do `main.py` (`/api/estatisticas`, `/api/usuarios`, `/api/auth/me`, `/api/auth/logout`, `/api/envios/rastrear/{codigo}`, `/main` e `/login`), a dependência `auth_admin` e a função `ui_status()` — nada disso era chamado pelo front.


---

## 4. Como executar

### 4.1 Pré-requisito

**Python 3.12** instalado de [python.org](https://www.python.org/downloads/) com a opção
**“Add python.exe to PATH”** marcada. Sem Python real, o comando `python` no Windows abre a **Microsoft Store**
(atalho fantasma) e nada funciona — ver §13.

### 4.2 Primeira vez (uma única vez)

```powershell
cd <pasta-do-projeto>          # ex.: a pasta que contém este DOCUMENTACAO.md
python -m venv .venv           # cria o ambiente virtual
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env         # opcional: edite SMTP/DATABASE_URL/porta
```

> ⚠️ A `.venv` **não é portátil**: se a pasta for copiada de outro computador/usuário, o `pyvenv.cfg` continua
> apontando para o Python do dono original. Nesse caso apague a `.venv` e recrie com `python -m venv .venv`.

### 4.3 Rodar o servidor

```powershell
cd <pasta-do-projeto>
.venv\Scripts\python.exe main.py      # ou: python main.py
```

Ou, no Windows, apenas **duplo clique** em:
- `iniciar-sistema.bat` — testa a `.venv` (e cai para `py`/`python` do sistema se ela estiver quebrada), instala as
  dependências que faltarem, avisa se a porta 3000 já está em uso e sobe o servidor em `http://localhost:3000/`

> A janela do `.bat` deve ficar **aberta** enquanto o sistema estiver em uso (é o servidor).

> Nunca abra `static/index.html` direto (`file://`) para usar o sistema: sem o backend as chamadas `/api/*`
> falham e o app cai no modo offline (§9.9). Use sempre `http://localhost:3000/`.

O servidor sobe em **http://localhost:3000** (`0.0.0.0:3000`; porta configurável via `PORT` no `.env`).

> O banco `database.db` e as tabelas são criados/migrados automaticamente no primeiro start (`lifespan` → `init_db()`).

### 4.4 Sem Python: abrir a interface (modo offline, com servidor local sem cache)

Se você **não tem Python instalado** (ou quer só usar a interface com os dados no navegador):

1. **Duplo clique em `abrir-servidor-local.bat`** → abre `http://localhost:8080/`. Esse `.bat` chama o
   `servidor-local.ps1`, um servidor de arquivos em PowerShell que responde **tudo com `Cache-Control: no-store`**
   (nada de HTML/JS antigos em cache) e não exige instalar nada nem rodar como administrador.
2. Cadastre e **importe planilha/texto normalmente**: sem backend, tudo é gravado no `localStorage` do navegador
   e sincroniza sozinho quando o backend ligar (§9.9).
3. Para parar o servidor: feche a janela **Rastreio-Facil-Servidor-Local**.

> ❓ Por que não abrir o `index.html` direto (`file://`)? Porque o HTML usa caminhos absolutos (`/static/app.js`,
> `/static/styles.css`), que só resolvem através de um servidor — no `file://` a página fica sem CSS/JS.
> ❓ Por que não o Live Server? Ele pode entregar o HTML antigo do cache do navegador (sintoma clássico:
> o console mostra `app.js?v=12` e os POSTs caem nele com **405**); o `servidor-local.ps1` elimina isso com `no-store`.

### 4.5 Parar o servidor

`Ctrl+C` no terminal onde está rodando, ou:
```powershell
Get-Process python | Stop-Process -Force
```

> 💡 Se aparecer `ERR_CONNECTION_REFUSED` no navegador, o backend está parado. Se aparecer `Errno 10048` (porta em uso) no log, há **duas instâncias** disputando a porta — mate todas (`Get-Process python | Stop-Process -Force`) e suba uma só.

---

## 5. Arquitetura geral

```
Navegador — tela única em `/` (static/index.html + app.js, envios + login admin em modal)
        │  fetch('/api/...') em paths relativos + Bearer token (localStorage)
        ▼
FastAPI (main.py :3000)
  • Middleware cache-busting (libs immutable 1 ano; js/css/html/json no-cache)
  • Middleware CORS (liberado p/ Live Server / file://)
  • Dependências auth_usuario / auth_opcional (Bearer)
  • Validações: regex código (AB123456789BR), e-mail e celular
  • SMTP assíncrono (aiosmtplib) p/ notificações de e-mail
        │
        │ db.py (SQLite ou Postgres)
        ▼
  database.db → envios | usuarios | sessoes
```

**Decisões de arquitetura relevantes:**

- **Mesma origem (uso normal)**: abrindo `http://localhost:3000/`, o `app.js` usa paths relativos (`/api/...`) porque é o próprio backend que serve a página.
- **Live Server / `file://` (modo de teste do front)**: fora do `:3000` o `app.js` aponta para `http://localhost:3000/api` e depende do **CORS** (`allow_origins=["*"]`) liberado no backend. Remover um dos dois quebra o import/cadastro nesse modo (o Live Server responde **405 Method Not Allowed** a POSTs).
- **Modo backend vs modo local**: o `app.js` mantém um fallback local (localStorage) para funcionar sem backend; com o backend no ar, todo CRUD passa pela API.
- **`_id` é inteiro**: o backend devolve o `id` da tabela SQLite como **número**. O front foi corrigido para **sempre comparar com `Number()`** (ver seção 12) e adota o `_id` do backend logo após criar um envio.
- **Cache-busting**: o middleware marca `/static/libs/*` (e `/static/img/*`, se existir) como
  `public, max-age=31536000, immutable` e todo `.js/.css/.html/.json` como `no-cache, must-revalidate`;
  as rotas de página (`/`, `/main`, `/login`) respondem com `Cache-Control: no-store`.
- **Auto-atualização do front**: `main.py` expõe `APP_VERSAO` em `GET /api/versao`; o `app.js` compara com sua
  própria `APP_V` (hoje `19`) a cada 15 s e recarrega a página sozinho quando o servidor está mais novo.
- **Camada de banco única**: todo acesso a dados passa por `db.py` (`fetch_all`, `fetch_one`, `execute`, `init_db`),
  que traduz `?` → `$n` no Postgres — as queries do `main.py` são escritas uma vez só.

## 6. Banco de dados

O sistema usa **um dos dois drivers**, escolhidos em tempo de execução pelo `db.py`:

| Situação | Driver | Onde os dados ficam |
|---|---|---|
| Sem `DATABASE_URL` (padrão) | `aiosqlite` | arquivo **`database.db`** na raiz do projeto |
| `DATABASE_URL=postgres://…` / `postgresql://…` | `asyncpg` (pool 1–5 conexões) | servidor Postgres (Neon, Supabase, Railway, Render, Docker…) |

Tabelas (criadas/migradas automaticamente): `envios`, `usuarios`, `sessoes`.
`GET /api/db-status` informa `{ configured, connected, driver, url_safe }` — a URL sai com a senha mascarada.

### 6.1 `envios`

| Coluna | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id` | INTEGER | AUTOINCREMENT | PK — exposto ao front como **`_id`** (inteiro) |
| `destinatario` | TEXT | `''` | Nome do cliente |
| `codigo` | TEXT NOT NULL | — | Código de rastreio `AB123456789BR` (índice) |
| `celular` | TEXT | `''` | Só dígitos (backend remove não-dígitos) |
| `email` | TEXT | `''` | Validado por regex se preenchido |
| `descricao` | TEXT | `''` | Descrição livre do produto |
| `status` | TEXT | `'pendente'` | **`pendente` / `a_caminho` / `entregue`** (índice). Qualquer valor fora desses três é gravado como `pendente` |
| `notificado` | INTEGER | 0 | Flag 0/1 para notificação enviada |
| `criado_em` | TEXT | `datetime('now')` | Timestamp ISO |
| `criado_por` | INTEGER | NULL | FK lógica → `usuarios.id` de quem cadastrou (auditoria no banco; **não** é exposto na API) |

### 6.2 `usuarios`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | INTEGER | PK AUTOINCREMENT |
| `nome` | TEXT NOT NULL | Nome de exibição |
| `email` | TEXT NOT NULL UNIQUE | Login (normalizado minúsculo) |
| `senha_hash` | TEXT NOT NULL | Formato `sal$hash` (PBKDF2-SHA256, 100k iterações) |
| `admin` | INTEGER | 1 = administrador |
| `ativo` | INTEGER | 0 = desativado (exclusão lógica) |
| `criado_em` | TEXT | Timestamp |

### 6.3 `sessoes`

| Coluna | Tipo | Descrição |
|---|---|---|
| `token` | TEXT PK | 64 caracteres hex (32 bytes aleatórios) |
| `usuario_id` | INTEGER | FK → `usuarios.id` |
| `expira_em` | TEXT | Timestamp; sessão dura `SESSAO_DIAS` (padrão 7 dias) |

### 6.4 Migrações automáticas

`init_db()` (em `db.py`) roda no `lifespan` do FastAPI e trata os dois drivers:

**Caminho Postgres** (`USE_POSTGRES = True`)
1. `CREATE TABLE IF NOT EXISTS` para `envios`, `usuarios` e `sessoes` (ids `SERIAL`).
2. `CREATE INDEX IF NOT EXISTS` para `idx_envios_codigo` e `idx_envios_status`.
3. Nada de migração destrutiva — bancos antigos não são apagados.

**Caminho SQLite** (`USE_POSTGRES = False`)
1. `CREATE TABLE IF NOT EXISTS` de `envios`, `usuarios` e `sessoes` + criação dos mesmos índices.

> ℹ️ Não existe mais migração de schema antigo: as conversões que ficavam aqui (o `DROP TABLE` do schema com
> `codigo_rastreio`/`email_destino` e o `ALTER TABLE … ADD criado_por`) foram removidas em 29/09/2026 — o
> `database.db` atual já está no schema novo.

> 💡 Se o `init_db()` falhar, o servidor sobe mesmo assim (o erro é apenas impresso como `[DB] init falhou: …`) —
> confirme a saúde com `GET /api/health`.

---

## 7. Autenticação e sessões

- **Login** (`POST /api/auth/login`): valida e-mail + senha (PBKDF2) e cria um token de sessão de **7 dias** (`SESSAO_DIAS`). Retorna `{ token, user: { id, nome, email, admin } }`. Credenciais erradas → **401**.
- **Registro** (`POST /api/auth/registrar`): **aberto apenas enquanto não existir nenhum usuário** (bootstrap do primeiro admin — quem se registra primeiro vira admin automaticamente). Depois disso a rota exige `Authorization: Bearer <token>` de um **admin** (caso contrário **403**).
- **Uso**: o front guarda o token em `localStorage` (**`rf_token`**) e envia `Authorization: Bearer <token>` nas chamadas autenticadas.
- **Validação**: dependência `auth_usuario` faz `JOIN sessoes × usuarios`, checando expiração e `ativo = 1`; `auth_opcional` deixa passar quando o banco está vazio (bootstrap) — é o que autoriza as rotas de envios e de notificações.
- **Sem rota de logout**: o `main.py` não expõe `/api/auth/logout` e a interface não tem botão de sair; o token é descartado no cliente quando chega um 401 (`pedirLogin()`).
- **`/` serve a tela única** (`index.html`); a proteção é via token Bearer no client-side (modal de login, aberto por `pedirLogin()`).
- **Sessões no banco**: o token é `secrets.token_hex(32)` (64 caracteres). No Postgres a expiração é gravada com `NOW() + INTERVAL '7 days'`; no SQLite, com um timestamp UTC calculado.
- **Sessão expirada**: ao receber 401 o front limpa `rf_token` e reabre o modal de login automaticamente.


## 8. Referência completa da API

Base: `http://localhost:3000`. Salvo indicação, as rotas de dados usam `auth_opcional` — que libera o acesso **apenas
enquanto o banco não tem usuários** (bootstrap) e depois exige `Authorization: Bearer <token>`.

### 8.1 Páginas (frontend)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Tela principal (`static/index.html`) |
| GET | `/main` e `/login` | Aliases da mesma tela (compatibilidade com links/bookmarks antigos) |
| GET | `/static/*` | Assets (JS/CSS/libs): `no-cache` no JS/CSS e `immutable` (1 ano) em `/static/libs/*` |

### 8.2 Autenticação

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/auth/estado` | — | `{ temUsuarios: bool }` — controla tela de 1º acesso |
| POST | `/api/auth/registrar` | — (só com 0 usuários) / admin | Cria usuário. Body: `{ nome, email, senha, admin? }`. O 1º usuário vira admin. 403 se já houver usuários e o token não for admin; 409 se e-mail existe; 422 se senha < 4 |
| POST | `/api/auth/login` | — | Body: `{ email, senha }` → `{ token, user }`. 401 se inválido |

> Observação: a única rota de usuários é `POST /api/auth/registrar` (o 1º vira admin). Não existem
> `GET/POST /api/usuarios` nem `DELETE /api/usuarios/{id}`: para desativar alguém, altere direto no banco
> (`usuarios.ativo = 0`).


### 8.3 Envios (CRUD + status)

**`GET /api/envios`** — lista todos (mais recentes primeiro: `ORDER BY id DESC`), `auth_opcional`:
```json
{ "envios": [ {
  "_id": 8, "destinatario": "Maria", "codigo": "AB123456789BR",
  "celular": "11987654321", "email": "maria@teste.com", "descricao": "...",
  "status": "pendente", "notificado": false, "criado_em": "2026-09-29 14:03:11",
  "link": "https://rastreamento.correios.com.br/app/index.php?objeto=AB123456789BR"
} ] }
```
> `criado_em` é o timestamp do banco (`YYYY-MM-DD HH:MM:SS`); o front converte para `dd/mm/aaaa` na mensagem de rastreio
> (nos envios feitos offline, o próprio `app.js` grava um `criado_em` local).

**`POST /api/envios`** — cria 1 item **ou lote** (importação CSV/Excel), `auth_opcional`:
```json
{ "destinatario": "Maria", "codigo": "AB123456789BR",
  "celular": "11987654321", "email": "m@x.com", "descricao": "livro" }
```
ou `{ "envios": [ {...}, {...} ] }`
→ `{ "message": "1 envio(s) criado(s)", "envios": [ { ...com _id inteiro... } ], "erros": [] }`

Regras implementadas em `criar_envios()` (aceita também os apelidos `nome` e `observacoes`):
1. **Lote máximo de 500 itens** (422 acima disso) e corpo vazio/inválido → 422.
2. **Valida tudo antes de inserir**; se nenhuma linha for válida → **422** com a lista dos erros (até 8).
3. Linhas inválidas são **ignoradas** e o resto é gravado; a resposta traz `"erros": ["linha 3: ..."]`.
4. Código repetido **dentro do lote** → `linha N: código duplicado na planilha` (ignorado).
5. Código já existente no banco → `AB123456789BR: já cadastrado (ignorado)`.
6. Exige **destinatário** e ao menos **um contato** (e-mail ou WhatsApp).
7. `status` inválido vira `pendente` (só `pendente`/`a_caminho`/`entregue` são aceitos).

**`PUT /api/envios/{id}`** — edição parcial (modal ✏️ do front, `salvarEdicao`). Body com qualquer subconjunto de
`{ destinatario, codigo, celular, email, descricao, status }` → retorna o envio atualizado.
Erros: **404** se não existir; **422** se destinatário vazio, se ficar sem contato (e-mail/WhatsApp) ou se código/e-mail/celular forem inválidos; **409** se o código já pertence a outro envio.

**`PATCH /api/envios/{id}/status`** — muda o status: body `{ "status": "pendente" | "a_caminho" | "entregue" }`.
Outro valor → **422**; envio inexistente → **404**. A flag `notificado` vai junto (0 apenas em `pendente`).

**`PATCH /api/envios/{id}/notificado`** — marca `status='a_caminho', notificado=1` (usado pelo front após enviar a mensagem do WhatsApp). 404 se não existir.

**`DELETE /api/envios/{id}`** → `{ "message": "Envio removido" }`. 404 se não existir.

> ⚠️ Não existe rota de consulta/rastreio no backend (a API oficial dos Correios exige token pago): o front abre o
> link oficial `https://rastreamento.correios.com.br/app/index.php?objeto=<codigo>`, que já vem no campo `link` de cada envio.

### 8.4 Notificações e cartões

**`POST /api/notificacoes`** (`auth_opcional`) — Body:
```json
{ "codigo": "AB123456789BR", "canal": "email",
  "mensagem": "<p>HTML pronto do front</p>", "assunto": "opcional" }
```
- `canal: "email"` → se `SMTP_USER`/`SMTP_PASS` estiverem no `.env`, envia o HTML via SMTP assíncrono; em sucesso
  marca `status='a_caminho', notificado=1` pelo código e retorna
  `{ "success": true, "result": { "enviado": true, "email": "cliente@x.com" } }`.
  Sem SMTP, sem e-mail cadastrado ou com falha no envio → `{ "success": false, "fallback": true, "message": "..." }`
  (o front abre `mailto:`).
- `canal: "whatsapp"` → **nunca envia pelo servidor**: retorna `{ "success": false, "fallback": true, "message": "WhatsApp via wa.me" }`
  e o front copia a mensagem para a área de transferência, abre `wa.me/55<celular>` e depois chama
  `PATCH /api/envios/{id}/notificado` para persistir o status.
- `mensagem` vazia → o backend monta um HTML padrão (`_montar_html_email`) com nome, código, descrição, data e o link dos Correios.
- Código não cadastrado → **404** `Codigo nao cadastrado`.

> Os cartões **Total / Pendentes / A caminho / Entregues** são calculados no próprio front, a partir da lista
> carregada (`state.envios` + `uiStatus()`), para refletir também os itens offline. Havia um
> `GET /api/estatisticas` no backend, mas era código morto (ninguém chamava) e foi removido em 29/09/2026.

### 8.5 Usuários

Criação de usuários: apenas `POST /api/auth/registrar` (§8.2) — o 1º usuário do sistema é sempre admin.
> O `main.py` **não tem** `GET/POST /api/usuarios` nem `DELETE /api/usuarios/{id}` (essas rotas existiam só no
> backend antigo, removido em 29/09/2026). Desativar alguém = `usuarios.ativo = 0` direto no banco.

### 8.6 Diagnóstico / infraestrutura

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | `{ ok, db, smtp }` — `ok:false` + `error` quando o `SELECT 1` falha; `db` traz `{ configured, connected, driver, url_safe }` e `smtp` diz se há credenciais |
| GET | `/api/db-status` | Somente o bloco `db` do health (`{ configured, connected, driver, url_safe }`) — alimenta a pílula de status (`#db-pill`) no cabeçalho |
| GET | `/api/versao` | `{ versao: "13" }` — comparado com a `APP_V` do `app.js` para recarregar a página sozinho |

### 8.7 Códigos de erro HTTP

| Código | Quando |
|---|---|
| 401 | Sem header Bearer / sessão inválida ou expirada / e-mail ou senha incorretos |
| 403 | Rota admin acessada por usuário comum; tentativa de `POST /api/auth/registrar` sem ser admin quando já existem usuários |
| 404 | Envio inexistente ou código não cadastrado em `/api/notificacoes` |
| 409 | E-mail já cadastrado (registro de usuário) / código de rastreio já usado em **outro** envio (PUT) |
| 422 | Validações: código fora de `AB123456789BR`, e-mail inválido, celular sem DDD+8/9 dígitos, destinatário vazio, envio sem contato, corpo vazio, lote > 500, senha < 4, status fora de `pendente/a_caminho/entregue` |

---

## 9. Funcionalidades do frontend

Todo o app vive em `static/app.js` (dark UI, tela única `index.html`). Não há abas: a página tem **duas colunas**
(formulário/importação à esquerda, lista de envios à direita), 4 cartões de estatística no topo, a pílula de
status do banco (`#db-pill`) no cabeçalho e 3 modais (`modal-wa`, `modal-edit`, `modal-login`).

### 9.1 Autenticação (modal `#modal-login`)
- Login com validação de e-mail no padrão RFC simplificado (`erroEmail`, `RX_MAIL`) e mostrar/ocultar senha.
- **Primeiro uso**: `GET /api/auth/estado` → `temUsuarios: false` habilita o botão *Criar admin (1º uso)*.
- **Uso recorrente**: se o sistema já tem usuários e não há token, `pedirLogin()` abre o modal automaticamente
  (e o reabre quando qualquer chamada devolve 401).
- Sessão persistente: o token fica salvo em `rf_token` (localStorage) e é reenviado em toda chamada autenticada até expirar (7 dias).
- **Não existe logout na interface**: quando o servidor responde 401, `pedirLogin()` apaga o `rf_token` do localStorage e reabre o modal.

### 9.2 Cabeçalho, cartões e conexão
- Os 4 cartões são calculados no cliente a partir de `state.envios` (`render()` + `uiStatus()`): **Total**, **Pendentes**, **A caminho**, **Entregues**.
- `#db-pill` mostra o estado da conexão em todo momento (`GET /api/db-status`): *banco local*, *Postgres conectado/com erro* ou *modo offline — salvando no navegador*.
- Com o backend fora, não há aviso fixo na tela: um **toast** avisa uma única vez na transição e o front **tenta reconectar sozinho** (backoff); ao voltar, confere a versão e sincroniza os pendentes.
- Reconexão com **backoff** (`_esperaBackoff`): 5s → 10s → 20s → 30s → 60s (mais um timer de segurança de 60 s), para não encher o console de `ERR_CONNECTION_REFUSED`.
- `load()` tem trava anti-loop (`_carregando` + intervalo mínimo de 700 ms entre ciclos).

### 9.3 Cadastro de envios
- Formulário: destinatário, **código com máscara** (`limparCodigo`/`mascaraRastreio` — normaliza `AA123 456 789 BR` → `AA123456789BR` e valida a posição de letras/números), WhatsApp com máscara `(11) 91234-5678` (`mascaraFone`), e-mail (`mascaraEmail`) e observações.
- Validação no cliente (`codigoValido`, `erroEmail`, `foneValido`) **e** no servidor (422 com mensagem explicativa).
- Seletor de status inicial (`#f-status`: a caminho / pendente / entregue).
- Exige ao menos um contato (e-mail ou WhatsApp) — há aviso fixo no formulário.

### 9.4 Importação e exportação
- **Arraste e solte** na área `#drop` ou clique para selecionar; aceita **.csv**, **.xlsx** e **.xls** (`lerArquivo` → `parseCsvLinhas` para CSV ou SheetJS para Excel).
- Também dá para **colar CSV** em `#f-csv` e clicar em *Importar texto* (aceita separador `,`, `;` ou **TAB** — inclusive texto copiado direto do Excel — com ou sem linha de cabeçalho).
- Cada linha passa por `validarLinha` antes do envio; a criação é **em lote** (`importarLinhas` → `POST /api/envios { envios: [...] }`) e o resumo mostra criados/sincronizados e as linhas ignoradas.
- *Baixar modelo CSV* (`#btn-modelo`) gera `modelo-importacao.csv` com o cabeçalho esperado (`Nome,Codigo,Celular,Email,Descricao`).
- **Exportação**: *Exportar CSV* (`exportarCSV`) e *Exportar Excel* (`exportarXLSX`, via SheetJS) exportam a **lista filtrada atual**.

### 9.5 Lista de envios
- Cards renderizados por `render()` dentro de `#lista` (invólucro rolável `.lista-scroll`, altura máx. ~560px com barra fina no tema escuro) com: destinatário, **badge de status** (`badge()`), código de rastreio, contato (e-mail • WhatsApp formatado) e observações.
- **Busca** por destinatário/código/observações (`#f-busca`) e **filtro por status** (`#f-filtro`) recalculam a lista imediatamente; o contador fica em `Envios (N)`.
- A lista rola em uma área que acompanha a altura do cartão da esquerda (`.grid` com `align-items:stretch` + `.lista-scroll` com `flex:1`/`min-height:0`): o fim fica rente à última linha do Exportar; só aparece barra quando os cards estouram esse espaço (no celular, teto de `60vh`).
- Botões de cada card: **A caminho / Entregue / Pendente** (aparece apenas o que muda o status atual → `PATCH /api/envios/{id}/status`), **WhatsApp**, **E-mail**, **Rastrear**, **✏️ Editar** e **Excluir**.
- **Excluir**: `confirm()` → `DELETE /api/envios/{id}` (ou remove do `localStorage` se o item for offline).
- Itens offline entram na mesma lista (id negativo, `_local: true`).
- Não existe seleção múltipla nem "limpar tudo": as ações são sempre por envio.

### 9.6 Edição (modal `#modal-edit`)
- `abrirEdicao(id, envio, local)` preenche o modal com os dados atuais; as máscaras de código/WhatsApp/e-mail continuam ativas dentro dele.
- `salvarEdicao()` valida antes de gravar: destinatário e código obrigatórios, código no formato `AA123456789BR`, e-mail válido, WhatsApp com DDD + 8/9 dígitos e pelo menos um contato.
- Código já usado por outro envio → pede confirmação (`confirm`) antes de continuar.
- Com backend: `PUT /api/envios/{id}` → toast *"Envio atualizado!"* + recarga da lista. Erros de validação do servidor (422/409) aparecem no próprio modal (`#ed-err`).
- Itens **locais** (criados offline) são editados direto no `localStorage` (`Object.assign` + `gravarLocais`) e avisam que sincronizam quando o servidor voltar.
- Itens que vieram do **banco** exigem o backend: se a rede falhar, o próprio modal mostra o aviso (`#ed-err`) pedindo para salvar de novo quando o servidor voltar — **não** é criada cópia local (isso duplicava o card, forçava o status para `pendente` e a cópia era descartada na sincronização).

### 9.7 Notificações
- **WhatsApp** (`data-act="wa"`): monta a mensagem (`montarMsgRastreio`), abre o modal `#modal-wa`; o botão *Copiar e abrir WhatsApp* copia o texto (`copiarTexto`), abre `https://wa.me/55<numero>` e marca o envio como **a caminho/notificado** (`PATCH /api/envios/{id}/notificado`, ou no `localStorage` quando offline).
- **E-mail** (`data-act="mail"`): chama `POST /api/notificacoes { codigo, canal:"email" }`; se `success` → *"E-mail enviado!"*; senão abre `mailto:` com assunto e corpo prontos.
- Não há envio em massa nem "notificar todos pendentes": cada envio é notificado pelo próprio card.
- Emojis da mensagem usam escapes `\uXXXX` para não depender do encoding do arquivo; no WhatsApp o texto sai com `*negrito*`.

### 9.8 Rastreamento
- O botão **Rastrear** (`data-act="track"`) abre o **link oficial dos Correios** em nova aba: usa o campo `link` que o backend devolve em cada envio (`gerar_link_rastreio`) ou, sem backend, o `linkRastreio(codigo)` local.
- O sistema **não** consulta os Correios (a API oficial exige token pago) e não existe rota de rastreio no backend: quem mostra os eventos é o próprio site dos Correios.

### 9.9 Modo offline (resiliência)
- `state.online` guarda o resultado do último `checkDB()` (`GET /api/db-status`); o sistema continua utilizável sem backend.
- **Offline-first**: quando `state.online === false`, o cadastro manual e a importação (texto/arquivo) gravam **direto no navegador**, sem nem tentar a rede — e a resposta não-JSON (ex.: HTML de 404/405 do Live Server) também é tratada como "sem servidor" (`api()` lança `TypeError`), evitando o caso "cliquei e não aconteceu nada".
- Envios criados/editados offline vão para o `localStorage` (`LSK_ENVIOS = "rf_envios_locais"`) com `_id` negativo e flag `_local`.
- Ao reconectar, `load()` **sincroniza** os pendentes via `POST /api/envios`: para no primeiro erro de rede (mantendo o resto) e descarta o que o servidor recusar por validação, informando no toast.
- `file://` é detectado no `boot()` (toast único orientando a usar `abrir-servidor-local.bat` ou o backend);
- Offline, `checarVersao()` fica suspenso — sem enxurrada de `ERR_CONNECTION_REFUSED` no console.

### 9.10 Utilitários internos
- `esc()` escapa todo valor do usuário renderizado em HTML (mitiga XSS); `toast()` dá o feedback rápido; `$()` é o atalho para `getElementById`.
- `api()` centraliza o `fetch` (base `/api` no `:3000`, `http://localhost:3000/api` fora dele — Live Server/`file://`), injeta `Authorization: Bearer` e trata 401 chamando `pedirLogin()`.
- Atualização automática do front: `checarVersao()` roda 5 s após o boot e a cada 15 s, comparando `/api/versao` com a constante `APP_V`.

---

## 10. Sistema de notificações

### 10.1 E-mail (automático)
1. O front chama `POST /api/notificacoes` com `{ codigo, canal: "email" }` (mensagem vazia).
2. O backend valida o código, procura o envio **pelo código** e monta o HTML padrão (`_montar_html_email`): emojis por escape Unicode, nome, código, descrição, data em `dd/mm/aaaa` e o link dos Correios. Se o front mandar `mensagem`, ela é usada no lugar.
3. Envia via **SMTP assíncrono** (`aiosmtplib`): STARTTLS na porta 587 ou TLS direto quando `SMTP_PORT=465`.
4. Sucesso → `status='a_caminho', notificado=1`. Falha, sem credenciais ou sem e-mail cadastrado → `fallback: true` e o front abre `mailto:`.

> ⚠️ **Gmail**: use **Senha de App** (conta Google → Segurança → Verificação em 2 etapas → Senhas de app). Senha normal da conta será recusada pelo Google.

### 10.2 WhatsApp (manual)
Sem API paga integrada: o sistema abre o WhatsApp Web/App do destinatário (`wa.me/55...`) com a mensagem pronta. O clique de envio é humano — sem custo e sem token.

### 10.3 Fluxo de status

```
pendente ──(notificação enviada: SMTP confirmado ou WhatsApp disparado no front)──► a_caminho
                                                                                      │
                                        (botão "Entregue" no card / PATCH status)──────┘
                                                                                      ▼
                                                                                  entregue
```
- `notificado` (0/1) acompanha o status: 0 somente em `pendente`.
- Valores antigos (`notificado`, `enviado`) continuam aceitos na entrada e são convertidos para `a_caminho`.

---

## 11. Configuração (.env)

```env
# Banco (opcional): com DATABASE_URL usa Postgres; sem ela, SQLite local
DATABASE_URL=postgresql://usuario:senha@host:5432/banco?sslmode=require
DB_PATH=database.db
PORT=3000

# SMTP (necessário apenas para e-mail automático)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seuemail@gmail.com
SMTP_PASS=senha-de-app-do-gmail
SENDER_NAME=Rastreio Fácil

# Sessão
SESSAO_DIAS=7
```
> O arquivo `.env.example` (versionado) traz esse mesmo modelo com comentários — copie com `copy .env.example .env`.

| Variável | Padrão | Efeito |
|---|---|---|
| `DATABASE_URL` | vazio | Se começar com `postgres://`/`postgresql://`, ativa o driver Postgres (`asyncpg`); caso contrário o sistema usa SQLite |
| `DB_PATH` | `database.db` | Caminho do arquivo SQLite (ignorado no modo Postgres) |
| `PORT` | `3000` | Porta do Uvicorn |
| `SMTP_HOST` / `SMTP_PORT` | Gmail / 587 | Servidor de e-mail |
| `SMTP_USER` / `SMTP_PASS` | vazio | **Se vazios, e-mail automático fica desativado** (só fallback) |
| `SENDER_NAME` | `Rastreio Fácil` | Nome do remetente no e-mail |
| `SESSAO_DIAS` | `7` | Validade do token de sessão |

## 12. Histórico de correções importantes

Bugs corrigidos durante o desenvolvimento — úteis para entender o código atual:

### 12.1 Comparação de tipos `_id` (string × inteiro) — **o bug principal**
O backend devolve `_id` como **inteiro**, mas o HTML gerado embutia o valor como **string** (`data-id="3"` lido por `dataset.id` → `"3"`). Em JS, `3 === "3"` é `false`, então **editar, excluir e mudar status de envios salvos não funcionavam**.

**Correção:** toda busca na lista compara os dois lados como texto (`String(x._id) === String(id)`):
- `render()`/delegação de clique em `#lista` (`data-act`), `abrirEdicao`, `salvarEdicao`, `enviar` (WhatsApp), exclusão e atualização de status.
- Itens offline usam `_id` **negativo** (`idLocal()`), o que também evita colisão com os ids do banco.

### 12.2 `_id` local string após criar envio
`gerarId()` (front antigo) gerava uma string local que nunca casava com o inteiro do backend. **Correção:** o `POST /api/envios` no front agora adota o `_id` retornado pelo backend e recarrega a lista via `load()`; só no modo offline o item mantém id local negativo.

### 12.3 Cache do navegador
Alterações no `app.js` não apareciam. **Correção:** a rota `/` responde com `Cache-Control: no-store` e o HTML referencia `app.js?v=19` (bump de versão força recarregar).

### 12.4 Encoding (mojibake) no antigo `login.js` (removido em 28/09/2026)
Texto exibido como `FÃCIL`, `âš ï¸`, `Ã£` — o arquivo tinha **dupla codificação UTF-8/Latin-1**. **Correção:** reversão programática (`ISO-8859-1 → UTF-8`) + regravação dos emojis. Os HTMLs já tinham `<meta charset="UTF-8">` corretos.

### 12.5 Outras correções no backend (`main.py`)
- `/api/estatisticas` (rota removida em 29/09/2026): antes usava `{dict(r) for r in rows}` (set de dicts → `TypeError`); corrigido com dict comprehension — hoje os cartões são calculados no front.
- Migração automática de schema antigo (`codigo_rastreio` → `codigo`) e da coluna `criado_por`: eram feitas no `db.py` e foram removidas em 29/09/2026 (o banco já está no schema novo).
- Gestão de usuários (`GET/POST /api/usuarios`, `DELETE /api/usuarios/{id}`): existia apenas no backend antigo (`main_legado_backup.py`, removido em 29/09/2026) — exclusão **lógica** (`ativo = 0`) + invalidação de sessões. Hoje a API não expõe essas rotas (ver §8.5).
- Validação de e-mail com mensagem específica (`falta o @`, `falta o ponto no domínio`, …) em vez de um genérico "E-mail inválido".
- Celular normalizado (`0055`/`55`/`0` inicial removidos) e recusado fora de DDD + 8/9 dígitos.

### 12.6 Venv corrompida + "servidor fantasma" (set/2026)
Sintomas combinados: `ImportError: cannot import name 'ObjectReceiveStream' from 'anyio.abc' (unknown location)`, depois `cannot import name '_repr' from 'pydantic._internal' (unknown location)`, `ModuleNotFoundError: No module named 'pip._internal.cli.main'` e, ao mesmo tempo, `/api/db-status` retornava **404** no navegador.

**Causas:** (1) a `.venv` ficou com **instalações parciais** (pacotes com arquivos faltando — provável interrupção no meio de um `pip install`, que também quebrou o próprio pip); (2) um **processo antigo** (Python do sistema, código velho) continuava escutando na porta 3000 e "mascarava" a venv quebrada (por isso alguns `/api/*` davam 404/401 mesmo com o código novo em disco).

**Correção (passo a passo que funcionou):**
```powershell
# 1. Descobrir e matar o processo fantasma da porta 3000
netstat -ano | Select-String ':3000.*LISTENING'   # anote o PID final
Stop-Process -Id <PID> -Force

# 2. Restaurar o pip da venv (se estiver corrompido)
#    (se pip reclamar, apague .venv\Lib\site-packages\pip* antes)
.venv\Scripts\python.exe -m ensurepip --upgrade

# 3. Reinstalar TODA a stack (corrige pacotes com arquivos faltando)
.venv\Scripts\python.exe -m pip install --force-reinstall --no-cache-dir -r requirements.txt

# 4. Conferir os imports antes de subir
.venv\Scripts\python.exe -c "import fastapi, uvicorn, pydantic, anyio, aiosqlite, aiosmtplib; print('IMPORTS-OK')"

# 5. Subir pelo .bat (usa a venv; cai para o `py` se a venv não existir)
iniciar-sistema.bat
```
### 12.7 Edição de envios ausente (corrigido em 29/09/2026)
O `PUT /api/envios/{id}` já existia no backend, mas o front **não tinha como editar**: não havia botão nem modal, então um código digitado errado só podia ser corrigido excluindo e recriando o envio.

**Correção:** criado o modal `#modal-edit` com os campos atuais e o fluxo `abrirEdicao()` / `salvarEdicao()`:
- botão **✏️ Editar** em cada card (`data-act="edit"`);
- validações iguais às do cadastro (código, e-mail, WhatsApp, contato mínimo, destinatário) com mensagem no próprio modal (`#ed-err`);
- aviso de código duplicado (`confirm`) antes de salvar;
- `PUT /api/envios/{id}` quando há backend e gravação local (`Object.assign` + `localStorage`) quando não há — inclusive se o servidor cair durante o salvamento;
- máscaras ativas nos campos do modal; `test_analise_erros.py` ganhou 4 verificações de edição (total: **41**).

### 12.8 Abas velhas, console poluído e loop de recarregamento
Sintomas: abas antigas continuavam pedindo `/api/*` depois do token expirar (401 repetidos no console), `ERR_CONNECTION_REFUSED` em enxurrada quando o backend estava parado e, no Live Server, a página **recarregava sozinha em loop**.

**Correções no front:**
- `checarVersao()` é suspenso quando `state.online === false` (sem spam de requisições) e o `load()` reagenda a reconexão com **backoff** 5s→60s + botão *Tentar conectar agora*.
- `APP_V` do `app.js` é comparado com `APP_VERSAO` de `GET /api/versao`; quando o servidor está mais novo, a página se recarrega **uma vez** (`setTimeout(..., 600)`).
- As rotas de página respondem `Cache-Control: no-store` e o HTML referencia `app.js?v=19`, então `Ctrl+F5` deixou de ser obrigatório (ver 12.3).
- O log do servidor saiu de dentro da pasta vigiada pelo Live Server (foi para `%TEMP%\rastreio_server.log`), acabando com o loop de reload.

### 12.9 `.venv` copiada de outro computador (o "Python que não existe")
Sintoma: `python` abre a **Microsoft Store** (atalho fantasma do Windows), `py` não existe e, dentro do projeto, existe uma `.venv` de ~33 MB que **não executa nada** — o `pyvenv.cfg` aponta para o Python de outro usuário/computador (ex.: `C:\Users\kauan\...`) e há logs antigos como `py.err.log` apontando para caminhos inexistentes.

**Causa:** a pasta do projeto foi copiada com a `.venv` junto. Ambiente virtual **não é portátil**.

**Solução:**
```powershell
where.exe python          # se aparecer WindowsApps\python.exe, é o atalho falso da Store
Remove-Item .venv -Recurse -Force
python -m venv .venv      # depois de instalar o Python de python.org com "Add to PATH"
.venv\Scripts\python.exe -m pip install -r requirements.txt
iniciar-sistema.bat
```
> Os logs `py.err.log`, `py.out.log`, `server.err.log` e `server.out.log` (do servidor fantasma/abas antigas) foram removidos na limpeza de 29/09/2026 e `*.log` passou a ser ignorado no `.gitignore`.

**Aprendizado:** nunca rodar `main.py` com o Python do sistema "por cima" da venv — sempre `iniciar-sistema.bat` ou `.venv\Scripts\python.exe main.py`. E antes de investigar 404/401 "impossíveis", confirmar **qual** processo está na porta 3000.

---

## 13. Solução de problemas (troubleshooting)

| Sintoma | Causa provável | Solução |
|---|---|---|
| `ERR_CONNECTION_REFUSED` em `/api/*` | Backend parado | Duplo clique em `iniciar-sistema.bat` (ou `.venv\Scripts\python.exe main.py`) |
| `POST http://<host>:5501/api/envios 405 (Method Not Allowed)` no console | Página aberta pelo **Live Server** e a API sendo chamada na origem errada (ou sem CORS) | Deixe a janela do `iniciar-sistema.bat` aberta (backend no `:3000`): fora do `:3000` o `app.js` chama `http://localhost:3000/api` e o backend mantém o **CORS** liberado. Alternativa: use `http://localhost:3000/` direto |
| `app.js?v=19` no console mesmo depois de editar o front | Navegador (ou Live Server) servindo HTML/JS **antigos do cache** | Abra por **`abrir-servidor-local.bat`** (`http://localhost:8080/`, tudo com `no-store`) ou force `Ctrl+Shift+R` com *Disable cache*; confirme no console se `window.APP_V` é `'19'` |
| Importação não faz nada e não mostra mensagem | `app.js` antigo em cache ou erro de JavaScript | Use **`abrir-resgate.bat`** (página independente do `app.js`). Se abrir o `index.html` por duplo clique (`file://`), o `localStorage` é outro e o salvo não aparece — abra por `http://localhost:8080/` |
| Barra vermelha no rodapé da tela principal | Erro de JavaScript | A barra mostra a mensagem; envie esse texto. Erros de rede do modo offline são ignorados de propósito |
| `Errno 10048` no log ao iniciar | Outra instância já usa a porta 3000 | `Get-Process python \| Stop-Process -Force` e subir 1 só |
| Tela "Sem conexão com o servidor" no login | Backend offline | Idem acima |
| Excluir/mudar status/notificar não faz nada | F5 não pegou o JS novo (raro; cache-bust e `/api/versao` já ativos) | `Ctrl+F5` |
| 401 ao listar envios | Sessão expirada (7 dias) ou token antigo | Fechar **todas** as abas do sistema, abrir de novo e logar (`Ctrl+F5`) |
| 401 em `/api/envios` repetindo sozinho no console | Aba antiga aberta com JS cacheado + token expirado (fica em polling de 60s) | Fechar essa aba; o HTML agora sai com `Cache-Control: no-store` (sem cache de página) |
| Tela "recarregando sozinha" sem parar, sem conseguir clicar | Aba do **Live Server (porta 5501)** + servidor gravando `_server.log` **dentro da pasta vigiada** pelo Live Server → cada requisição altera o arquivo, o Live Server recarrega a página, a página gera novo request... loop infinito | Corrigido: o log do servidor agora fica em `%TEMP%\rastreio_server.log` (fora do projeto) e o `.vscode/settings.json` ignora logs/banco no Live Server. Se acontecer de novo, use `http://localhost:3000` em vez da aba do Live Server |
| 422 "Código inválido" | Formato fora de `AB123456789BR` | Usar 2 letras + 9 dígitos + BR |
| 422 "E-mail inválido" | E-mail malformado no cadastro/import | Corrigir na planilha ou no form |
| E-mail não envia, cai no `mailto:` | SMTP sem credenciais ou senha recusada | Preencher `.env` com **Senha de App** do Gmail |
| Acentos/emojis estranhos na tela | Arquivo salvo com encoding errado | Salvar como UTF-8 (sem BOM) |
| Rota antiga dá 404 ou a tela parece velha | Pode haver um servidor **antigo** ocupando a porta 3000 (o `main.py` atual serve `/`, `/main`, `/login`, `/static/*` e `/api/*`) | `netstat -ano \| Select-String ':3000.*LISTENING'` → `Stop-Process -Id <PID> -Force` e subir de novo com `iniciar-sistema.bat` |
| Múltiplos python no `Get-Process` | Instâncias órfãs de testes | Encerrar todas e subir uma |
| `cannot import name '...' from 'anyio.abc'/_internal' (unknown location)` | Venv com pacotes corrompidos (instalação parcial) | `python -m ensurepip --upgrade` + `pip install --force-reinstall --no-cache-dir -r requirements.txt` |
| `No module named 'pip._internal.cli.main'` | pip da venv corrompido | Apagar `.venv\Lib\site-packages\pip*` e rodar `python -m ensurepip --upgrade` |
| `/api/db-status` dá 404 (mas o código tem a rota) | "Servidor fantasma" antigo ocupando a porta 3000 | `netstat -ano \| Select-String ':3000.*LISTENING'` → `Stop-Process` no PID e subir de novo pela venv |
| `python` abre a **Microsoft Store** | Atalho fantasma do Windows (`WindowsApps\python.exe`) | Instalar o Python de python.org marcando **"Add python.exe to PATH"** |
| `.venv` existe mas não executa nada | Venv copiada de outro computador (`pyvenv.cfg` aponta para outro usuário) | `Remove-Item .venv -Recurse -Force` → `python -m venv .venv` → reinstalar `requirements.txt` |
| `[DB] init falhou: ...` no log | Banco inacessível (URL/credencial/rede) | Conferir `DATABASE_URL` (use `?sslmode=require` em Neon/Supabase/Railway) e testar `GET /api/health` |
| Tarja sobre banco/backend | A tarja antiga (`#db-alert`) foi removida do layout | Conexão é indicada só pela pílula `#db-pill` + toast único na transição; a reconexão continua automática (backoff) |
| Botão ✏️ Editar não salva | Aba rodando `app.js` antigo | `Ctrl+F5` (o `/api/versao` já força reload quando o servidor é atualizado) |
| 409 ao salvar a edição | Código de rastreio já usado em **outro** envio | Confirmar o aviso de duplicidade ou trocar o código |
| Toast "sincroniza quando o backend ligar" | Envio foi salvo no navegador (modo offline) | Subir o backend; o `load()` sincroniza sozinho |

**Verificação rápida de saúde (PowerShell):**
```powershell
# Backend respondendo + estado do banco e do SMTP
Invoke-RestMethod http://127.0.0.1:3000/api/health
# Banco sem senha exposta + versão do front
Invoke-RestMethod http://127.0.0.1:3000/api/db-status
Invoke-RestMethod http://127.0.0.1:3000/api/versao
# O sistema já tem usuário cadastrado?
Invoke-RestMethod http://127.0.0.1:3000/api/auth/estado
# Porta escutando?
netstat -ano | Select-String ':3000.*LISTENING'
```

**Testes do projeto:**
```powershell
.venv\Scripts\python.exe test_analise_erros.py   # 59 verificações estáticas → imprime "RESULTADO: TUDO OK"
```

---

## 14. Segurança

**Implementado:**
- Senhas com **PBKDF2-HMAC-SHA256** (100.000 iterações) + sal aleatório de 16 bytes, comparação em tempo constante (`secrets.compare_digest`).
- Sessões server-side com token aleatório de 256 bits e **expiração** (7 dias); sem rota de logout (o token é descartado no cliente quando expira).
- Rotas de dados exigem `Bearer` sempre que o sistema já tem usuários (`auth_opcional` libera só no estado de bootstrap).
- Usuários desativados perdem acesso imediato (`ativo = 1` checado na validação).
- Registro aberto **apenas** no estado "zero usuários" (bootstrap); depois disso só admin registra.
- XSS mitigado no front: `esc()` escapa valores do usuário renderizados no HTML.
- `/api/db-status` mascara a senha da `DATABASE_URL` (`url_safe`).
- Proteção de credenciais: SMTP/DATABASE_URL em `.env` (não versionar — `.gitignore`).

**Pontos de atenção (para produção):**
- CORS `allow_origins=["*"]` — necessário no modo Live Server/`file://`; em produção restrinja à origem real do front.
- A tela (`/`) é protegida só no client-side (token Bearer); ideal mover a proteção para o servidor.
- HTTPS obrigatório em produção (hoje é HTTP local).
- Sem rate limiting no login (brute force teoricamente possível).
- SQLite: ótimo para uso local/single-server; considere PostgreSQL se escalar.

---

## 15. Limitações e melhorias futuras

| Item | Situação atual | Melhoria sugerida |
|---|---|---|
| Rastreamento de eventos | O sistema só monta o link oficial dos Correios (não consulta eventos) | Integrar API dos Correios ou serviço terceiro (ex.: LinkMyRastreio) |
| WhatsApp | Envio manual via `wa.me` | Integrar WhatsApp Business API |
| Proteção da tela | Client-side (token Bearer) | Middleware/server-side com redirect |
| Rate limiting | Ausente | `slowapi` no login |
| Testes automatizados | `test_analise_erros.py` faz **59 verificações estáticas** (substrings de `main.py`, `app.js`, `index.html`, `resgate.html` e dos `.bat`) | Migrar para `pytest` (backend) + Playwright (e2e do front) |
| Edição de envios | Completa no front e na API (`PUT /api/envios/{id}`, modal `#modal-edit`) | Permitir editar também o status pelo modal |
| Gestão de usuários | Só `POST /api/auth/registrar` (sem listar/editar/remover pela API) | Criar `GET /api/usuarios` + `DELETE` com exclusão lógica (como no backend antigo) |
| Modo offline | Sincronização automática ao reconectar, sem resolução de conflito | Estratégia de merge (ex.: chave `codigo` + `updated_at`) e aviso de duplicidade offline |
| Código morto | ✅ Nenhum — backends antigos, rotas órfãs e atalho duplicado removidos em 29/09/2026 (ver §3) | — |
| Limpeza feita (29/09/2026) | Frontend legado e arquivos órfãos removidos (ver §3) | — |
| `status`/`ativo` de usuário editáveis pela UI? | Não — só via banco | Tela de administração com ativar/desativar |
| CI/CD | Inexistente | GitHub Actions com lint + testes |
| Deploy | Manual local | Dockerfile + gunicorn/uvicorn workers |

---

## 16. Roteiro de verificação (smoke test)

Checklist rápido depois de qualquer alteração (backend em `http://localhost:3000/`):

1. `GET /api/health` → `{ "ok": true, "db": { "driver": "sqlite"|"postgres", "connected": true }, "smtp": false }`.
2. Abrir `http://localhost:3000/` → `#db-pill` indica `banco local (sem Postgres)` (sem nenhum bloco de aviso).
3. Banco vazio: *Criar admin (1º uso)* no modal 👤 → login automático.
4. Cadastrar envio com destinatário + `AA123456789BR` + WhatsApp → card na lista com badge **pendente**.
5. **✏️ Editar** → trocar o nome → **Salvar** → toast *"Envio atualizado!"*; recarregar a página e confirmar que persistiu.
6. Salvar um código já usado em outro envio → aviso de duplicidade (e 409 no servidor).
7. Chips **A caminho** / **Entregue** → cartões do topo mudam.
8. **WhatsApp** → modal com a mensagem → *Copiar e abrir WhatsApp* abre `wa.me` e o envio vai para **a caminho**.
9. **E-mail** → sem SMTP abre `mailto:`; com SMTP configurado mostra *"E-mail enviado!"*.
10. **Excluir** → confirmar → card removido (`DELETE /api/envios/{id}`).
11. Importar `.csv`/`.xlsx` (cabeçalho `Nome,Codigo,Celular,Email,Descricao`) → resumo de criados e ignorados.
12. **Offline**: parar o servidor, cadastrar/editar um envio (fica no navegador), subir o servidor → toast de sincronização e o envio aparece vindo do banco.
13. `.venv\Scripts\python.exe test_analise_erros.py` → `RESULTADO: TUDO OK`.

---

*Documento atualizado em 29/09/2026: revisão completa contra o código atual (`main.py`, `db.py`, `static/app.js`, `static/index.html`),
inclusão da edição de envios, do modo offline, do banco dual SQLite/Postgres, das rotas de diagnóstico (`/api/health`,
`/api/db-status`, `/api/versao`), correção dos nomes de token/status/funções do front e remoção das rotas inexistentes.
Anterior: 28/09/2026 (remoção do frontend legado e promoção de `index.html` + `app.js` + `styles.css` a principal).
Última limpeza (29/09/2026): removidos `main_new.py`, `main_legado_backup.py`, `iniciar-localhost.bat`, `JSONResponse`/`DATABASE_URL`/`DB_PATH` (imports), `auth_admin`, `ui_status()` e as rotas `/api/estatisticas`, `/api/usuarios`, `/api/auth/me`, `/api/auth/logout` e `/api/envios/rastrear/{codigo}` — depois disso, `/main` e `/login` foram **restaurados** como aliases de compatibilidade.
API final: página `/` + `/static/*`, envios (`/api/envios*`), `/api/notificacoes`, auth (`/api/auth/estado|login|registrar`) e diagnóstico (`/api/health`, `/api/db-status`, `/api/versao`).
Enxugamento do código vivo: removidos `criadoPor` + o `JOIN` do `GET /api/envios`, os aliases de data (`createdAt`/`data`) em favor de `criado_em`, a normalização dos status antigos (`notificado`/`enviado`) e a migração de schema antigo do `db.py` (o CORS e o fallback de API do Live Server continuam, com comentário no código para não serem removidos). Front bumpado para `v=13`.*

