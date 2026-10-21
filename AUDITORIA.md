# Auditoria — Rastreio Fácil

> Lista de melhorias internas e externas do projeto, com o **status** de cada item.
> Use como backlog: marque `[ ]` → `[x]` conforme for fazendo.
> Gerada em 21/10/2026 sobre a base `e11ee9c` (v30) e atualizada na **v31**.

**Legenda:** `[x]` resolvido · `[ ]` pendente · `[~]` parcial

---

## 📊 Resumo

| Frente | Pendentes | Resolvidos |
|---|---|---|
| 🔴 Críticos (segurança/funcional) | 2 | **5** |
| 🟠 Backend | 23 | 0 |
| 🟡 Front-end / UX / a11y | 19 | 0 |
| 🔵 Infra / CI / Cloudflare / deps | 42 | 0 |
| **Total** | **86** | **5** |

**Estado verificado na v31 (tudo verde):**
`test_analise_erros.py` → **TUDO OK (104 checks)** · `pytest --browser` → **60 passed** ·
`teste_operacional.py` → **20/20 PASS** · servidor local em http://localhost:3000 (v31).

---

## 🔴 Críticos — corrigidos na v31

| # | Problema | Onde | Status |
|---|---|---|---|
| 1 | **Senha padrão pública no deploy Cloudflare** — `env.ADMIN_SENHA \|\| 'admin12345'` e as `vars` do `wrangler.jsonc` **sem** `ADMIN_SENHA`. O Worker criava o admin com uma senha que estava no README/.env.example | `cloudflare/worker.js:87`, `wrangler.jsonc:19-29` | [x] **v31** — sem `ADMIN_SENHA` o Worker **não cria** a conta (com log de erro); o segredo virou obrigatório no deploy (`npx wrangler secret put ADMIN_SENHA`) |
| 2 | **CORS liberado para qualquer origem no FastAPI** — default `"*"` (testado ao vivo: `Access-Control-Allow-Origin: *`) | `main.py:43` | [x] **v31** — default agora é uma lista restrita ao ambiente local (app `:3000`/`:8080`, Live Server `:5500-5503`, `file://`); produção define `CORS_ORIGINS` |
| 3 | **Trocar a senha não derrubava as sessões abertas** — tokens antigos continuavam válidos por 7 dias | `main.py:716-724` | [x] **v31** — o `trocar-senha` encerra as **outras** sessões (a atual continua). Worker com paridade |
| 4 | **Sem Content-Security-Policy** (confirmado ausente na resposta HTTP) | `main.py:265-278` | [x] **v31** — CSP restritiva (`default-src 'self'`, `script-src 'self'`, `frame-ancestors 'self'`, …) no FastAPI **e** no Worker (inclusive nos assets) |
| 5 | **Bug: o modal de login nunca mais reabre** — `_loginPedido` só era zerado no login bem-sucedido; se o usuário fechasse o modal, todas as expirações seguintes de sessão ficavam silenciosas | `static/app.js:199-200`, `:647` | [x] **v31** — a flag é liberada ao fechar o modal e no logout |

**Extras do mesmo bloco, também feitos na v31:**
- [x] A senha do admin **não é mais impressa no log** (`main.py:161`).
- [x] **HSTS** (`Strict-Transport-Security`) quando a conexão é HTTPS (inclusive atrás de proxy via `X-Forwarded-Proto`).
- [x] Em **produção** (Postgres/`DATABASE_URL`) sem `ADMIN_SENHA` o admin **não é criado** — em dev local (SQLite) segue o padrão `admin12345`.
- [x] O Worker **não repassa mais** `Authorization`/`Cookie` do cliente ao asset server; `Cache-Control` vazio não sobrescreve mais o do asset server.
- [x] `Access-Control-Max-Age` no CORS do Worker.

**Ainda em aberto (do mesmo bloco):**
- [ ] Token de sessão em texto puro no banco e no `localStorage` → considerar cookie `HttpOnly` + `SameSite=Strict`.
- [ ] Ainda falta escapar `e._id` (`app.js:380`) e validar o protocolo de `window.open(e.link)` (`app.js:461`, `:714`).

---

## 🟠 Backend — importante

| # | Problema | Onde | Status |
|---|---|---|---|
| 6 | **`/api/estatisticas` inconsistente**: `total` inclui a lixeira (46) mas os contadores não (15+16+11=42). O front nem usa a rota — calcula no cliente | `main.py:772-776`, `worker.js:637-640` | [ ] |
| 7 | **PBKDF2 com 100k iterações** — OWASP recomenda 600k (rehash transparente no login) | `main.py:130`, `worker.js:67` | [ ] |
| 8 | **Sessões expiradas só são limpas no boot**; sem índice em `sessoes.expira_em` → a tabela cresce (hoje: 25 linhas) | `main.py:245-249`, `cloudflare/schema.sql:46` | [ ] |
| 9 | **Rate-limit do login só em memória** — some a cada restart e o dicionário cresce sem limite por IP | `main.py:45-64` | [ ] |
| 10 | **SQLite sem WAL e sem FK** (`journal_mode=delete`, `foreign_keys=0`); `db.py` abre 1 conexão por query (~1,4 ms) | `db.py:41-76` | [ ] |
| 11 | **Rotas de notificação sem rate limit** → a conta SMTP pode virar relay de spam | `main.py:633`, `:660` | [ ] |
| 12 | **`notificacao_massa` envia em série, sem limite** → request longo (timeout de proxy/provedor) | `main.py:660-682`, `worker.js:579-594` | [ ] |
| 13 | **D1 sem índice UNIQUE em `codigo`** (o SQLite tem) → corrida permite duplicata no Worker | `cloudflare/schema.sql:15-16` | [ ] |
| 14 | Tabela `login_falhas` (D1) nunca é limpa → cresce sem limite e gasta cota de escrita do D1 | `cloudflare/worker.js:606` | [ ] |
| 15 | **Corrida no `INSERT` de `rastreios`** no Worker (`SELECT` → `UPDATE` → `INSERT`) → `UNIQUE constraint failed` → HTTP 500 | `cloudflare/worker.js:541-542` | [ ] — resolver com `INSERT … ON CONFLICT(envio_id) DO UPDATE` |
| 16 | **`status` inválido devolve tudo** na listagem (inclusive a lixeira) | `main.py:737-740`, `worker.js:422-423` | [ ] — retornar 422 |
| 17 | **`PATCH /api/envios/:id/notificado` não checa as linhas afetadas** no Worker (o `main.py` retorna 404) | `cloudflare/worker.js:483-490` | [ ] |
| 18 | **`garantirAdmin()` roda em toda requisição** no Worker → dobra as leituras do D1 em todas as rotas; o `catch` engolia o erro sem log | `cloudflare/worker.js:679`, `:104` | [~] **v31** — o erro agora é logado; falta cache/boot |
| 19 | **`item.mensagem` entra crua no HTML do e-mail** (o template padrão escapa tudo) → injeção de HTML no e-mail do cliente | `cloudflare/worker.js:570` | [ ] — escapar com `escHtml` |
| 20 | **`/api/auth/estado` devolve o e-mail do admin sem autenticação** (facilita phishing) | `main.py:306-316`, `worker.js:369` | [ ] |
| 21 | **`/api/db-status` e `/api/versao` são públicos** e expõem `driver`/`url_safe` do banco | `main.py:295-304`, `worker.js:362` | [ ] |
| 22 | **Timeout do SMTP não cancela o socket** (órfão consumindo conexão do Worker) | `cloudflare/worker.js:244-247` | [ ] — usar `AbortController` |
| 23 | **`AbortSignal.timeout(25000)`** no rastreio — perto demais do limite de duração do request | `cloudflare/worker.js:314` | [ ] — 10-15 s |
| 24 | **`parseInt('1abc') === 1`** — `page=1abc` passa como `page=1` | `cloudflare/worker.js:31`, `:419-420` | [ ] — validar com regex `^\d+$` |
| 25 | **`/api/backup` sempre retorna 400** no Worker → o botão "Backup" da tela nunca funciona no Cloudflare | `cloudflare/worker.js:647-651` | [ ] — implementar export via Cron/R2 ou avisar no front |
| 26 | **Divergência Worker × main.py**: no Worker, uma falha de e-mail no meio do lote **derruba o lote inteiro** (o `main.py` isola com `try/except` por item) | `cloudflare/worker.js:588` | [ ] |
| 27 | **Pool do asyncpg nunca é fechado** no shutdown do app (leak a cada restart) | `main.py:238-254`, `db.py:25` | [ ] |
| 28 | **`/api/health` sempre devolve 200**, mesmo com o banco quebrado → orquestrador não reinicia | `main.py:280-293`, `worker.js:358-362` | [ ] — 503 quando `ok == false` |

---

## 🟡 Front-end — UX, acessibilidade e robustez

### P0 (acessibilidade / funcionamento)

- [ ] **Sem `aria-*` / `role=` em todo o projeto** (verificado por grep) → 4 modais sem `role="dialog"`, **sem Esc**, sem *trap* de foco e sem retorno de foco (`index.html:75-121`, `app.js:470/494/706/715`).
- [ ] **Re-render com `innerHTML` destrói o foco a cada clique** (`app.js:374`) → a navegação por teclado reinicia do topo sempre.
- [ ] **Toast sem `role="status"`/`aria-live`** (`index.html:74`) → nada é anunciado ao leitor de tela.
- [ ] **Sem `manifest.json` e sem Service Worker** → o "modo offline" (diferencial do produto) **não funciona em *cold start***.
- [ ] Foco quase invisível nos inputs: `outline: none` + só mudança de borda (`styles.css:255-261`).
- [ ] **Labels sem `for`** e campos sem `aria-describedby` (os `<small>` de erro ficam órfãos).

### P1 (robustez)

- [ ] **Duplo clique dispara ações destrutivas em dobro**: 📣 **2 envios em massa** (`app.js:662-669`), 2 abas do WhatsApp (`app.js:583-595`), 2 PATCH.
- [ ] **`location.reload()` automático descarta o formulário preenchido** (`app.js:892-894`).
- [ ] **`fetch` sem timeout** (`app.js:182`) → se o backend aceitar e não responder, o app **trava**.
- [ ] **`window._retryT` nunca é limpo** (`app.js:23` vs `:884`) → a rede de segurança de 60 s é código morto.
- [ ] **`state.online !== true`** (`app.js:623`, `:829`) → antes do `checkDB` resolver, salva no `localStorage` (pode duplicar no banco).
- [ ] **WhatsApp falha com números importados com `+55`** (`app.js:465/587` vs `:783`) — regex diferente da importação.
- [ ] `idLocal()` = `-Date.now()` → colisão de id offline (`app.js:52`).

### P2 (polimento)

- [ ] `load()` re-baixa **todas as páginas** (até 500/pág) a cada mutação (`app.js:296-320`) → com 5.000 envios, cada clique baixa tudo.
- [ ] Polling de `/api/versao` a cada 15 s **para sempre** (`app.js:899`) → pausar em `visibilitychange`.
- [ ] `createObjectURL` sem `revokeObjectURL` (CSV/Excel) → vazamento de blob.
- [ ] Importação **1 POST por item** em série (`app.js:278-286`) — existe endpoint em lote.
- [ ] Filtros/busca sem rótulo acessível; `f-desc`/`f-csv` sem `maxlength`; sem `<form>` (Enter não cadastra).
- [ ] `index.html` sem `description`/Open Graph/`canonical`/`theme-color`/`robots.txt` (SEO — o site é público).

---

## 🔵 Infra, CI, Cloudflare e dependências

### GitHub Actions (`.github/workflows/ci.yml`)

- [ ] Sem `permissions:` → o `GITHUB_TOKEN` herda o default da org (pode ser `write`).
- [ ] Sem `concurrency:` → pushes sucessivos acumulam runs.
- [ ] Sem `timeout-minutes` nos jobs.
- [ ] Sem **matrix de Python** (só 3.12; as deps exigem `>=3.10`).
- [ ] `cache: pip` sem `cache-dependency-path` → a chave ignora o `requirements-dev.txt`.
- [ ] **Sem job de lint** — e o config do ESLint se chama `_eslint.config.mjs` (prefixo `_` ⇒ **o ESLint nunca carrega**); o `files` cobre só `static/app.js`, não o `cloudflare/worker.js`.
- [ ] **`cloudflare/worker.js` nunca é executado na CI** (só `grep` de strings) → erro de sintaxe passaria. Adicionar `node --check` + `wrangler deploy --dry-run` + teste unitário de `normalizarRastreio`.
- [ ] **Sem scan de segurança**: `pip-audit`, `bandit`, `gitleaks`, `trivy`, CodeQL.
- [ ] **Sem cobertura** (`pytest-cov`) nem `pytest-timeout`.
- [ ] Sem job de build do Docker nem de deploy.
- [ ] Actions fixadas por tag (`@v4`, `@v5`) em vez de SHA.
- [ ] Sem `paths-ignore` → mudança só em `.md` roda a suíte inteira.
- [ ] Sem `dependabot.yml` → dependências pinadas (0.143 / 0.54 / 9.1.1) sem alerta de CVE.

### Docker

- [ ] `Dockerfile:1` — `FROM python:3.12-slim` sem digest; sem `apt-get upgrade`/limpeza de cache.
- [ ] `Dockerfile:14` — `pip install` sem lockfile/hashes → build não reprodutível.
- [ ] `Dockerfile:16` — `COPY . .` copia `tests/`, `cloudflare/`, `evidencias/`, `envios.csv` (com dados de cliente) → completar o `.dockerignore`.
- [ ] `Dockerfile:28` — o healthcheck só olha o status 200 (que é sempre 200) → app com banco quebrado continua "saudável".
- [ ] `Dockerfile:30` — porta fixa `3000` ignora o `PORT` injetado pela plataforma (Render/Railway/K8s).
- [ ] `Dockerfile:30` — sem `--proxy-headers` → atrás de proxy o rate-limit do login bloqueia **todos** (IP vira o do proxy).
- [ ] `Dockerfile:30` — sem `--timeout-graceful-shutdown` → requisições em voo cortadas no `SIGTERM`.
- [ ] `docker-compose.yml:6` — `env_file: .env` **falha o `up`** se o `.env` não existir → `required: false`.
- [ ] `docker-compose.yml:17` — senha de exemplo do Postgres versionada (`postgres:123`) + `sslmode=disable` no comentário.
- [ ] `docker-compose.yml` — serviço `db` comentado → **sem backup automático** do volume SQLite; falta `stop_grace_period`, `logging` com rotação e `security_opt: no-new-privileges`.
- [ ] `envios.csv` está versionado e contém nome/e-mail/telefone de "clientes" (entra na imagem Docker).

### Cloudflare Worker / D1

- [ ] Sem **Cron Trigger** → nenhum backup automático do D1 (o único é manual: `wrangler d1 export`); falta rotacionar (manter N-1) e documentar o *restore*.
- [ ] `cloudflare/schema.sql` aplicado **manualmente** — sem `migrations_dir` ⇒ sem versionamento nem rollback.
- [ ] `schema.sql` — faltam FKs (`envios.criado_por`, `eventos.envio_id`) e índice em `login_falhas(ts)`.
- [ ] `wrangler.jsonc:22` — `"SENDER_NAME": "Sua Loja"` (placeholder) **vai para produção** no cabeçalho do e-mail.
- [ ] `wrangler.jsonc:19-29` — faltam `CORS_ORIGINS` (v31: adicionado, vazio = padrão local) e `RASTREIO_API_URL`.
- [ ] `wrangler.jsonc:6,17` — `account_id`/`database_id` versionados (baixo risco, mas amarram o repo a uma conta).
- [ ] **Rate limit só no `/api/auth/login`** — `POST /api/envios` (500 itens/lote), `/api/notificacoes/massa` e `/api/envios/:id/rastrear` (consome cota da API externa) **não têm limite**.
- [ ] Sem proteção contra **enumeração de usuário** nem bloqueio por conta (só por IP).
- [ ] Logs **não estruturados** (`console.log('[erro]', …)`) — sem JSON, request-id, duração ou status; `observability` sem `head_sampling_rate`/`traces`.
- [ ] Sem *health check* que verifique a existência do schema (só `SELECT 1`).
- [ ] **Sem feature flags / kill switch** — rastreio automático, e-mail e disparo em massa ligam só por variável de ambiente.
- [ ] Sem `package.json` → `npx wrangler` baixa a CLI na hora, sem versão fixada; `package-lock.json` está no `.gitignore`.

### Dependências

- [ ] **Sem lockfile/hashes** (`requirements.txt`) → build não reprodutível.
- [ ] `fastapi==0.143.0` exige `starlette>=0.46.0` **sem teto** — e o Starlette é justamente o pacote com CVEs recentes (Host header, SSRF/NTLM via `StaticFiles`, DoS em `request.form()`/`FileResponse`). Fixar `starlette>=1.3.1`.
- [ ] `uvicorn[standard]` arrasta `watchfiles`, `uvloop`, `websockets`, `httptools`, `PyYAML` sem uso → `uvicorn` puro.
- [ ] `openpyxl` só é usado por `importar_planilha.py`/`teste_operacional.py` (não pelo servidor) → mover para `requirements-tools.txt`.
- [ ] `requirements-dev.txt` — `pytest-asyncio` é **morto** (nenhum teste é async) e `webdriver-manager` também (o Selenium 4 usa o Selenium Manager embutido).
- [ ] Faltam `pytest-cov`, `pytest-timeout`, `ruff`/`flake8`, `mypy`, `bandit`, `pip-audit`.

---

## ✅ O que já está bem feito (não mexer)

- `esc()` aplicado corretamente em nome/código/contato/descrição dos cards (`app.js:377-383`).
- Guarda anti-loop `_carregando`/`_pendente` + throttle de 700 ms (`app.js:243-253`).
- Backoff 5 s → 60 s na reconexão + aviso único de transição offline.
- Guarda de resposta obsoleta no modal de rastreio (`app.js:504/516`).
- `carregarXLSX()` com Promise cacheada → 861 KB só quando necessário (`app.js:920`).
- `filtrados()` em **uma única passagem** + paginação de 120 linhas (`app.js:338-356`).
- Dockerfile: usuário sem privilégio, healthcheck e cache de camadas.
- Verificador estático (`test_analise_erros.py`) com **104 checks** que pega regressões de versão/paridade.
- Documentação completa e coerente (`DOCUMENTACAO.md`).
- Sem segredo no histórico do Git; `.env` e `.dev.vars` não versionados.
