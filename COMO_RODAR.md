# Rastreio Fácil — Como rodar (modernizado)

> Documentação técnica completa: **`DOCUMENTACAO.md`** (arquitetura, API, banco, troubleshooting).

## 0. Sem Python (só a interface — dados no navegador)
Duplo clique em **`abrir-servidor-local.bat`**: abre `http://localhost:8080/` usando um servidor de arquivos em
PowerShell (`servidor-local.ps1`) que manda `Cache-Control: no-store` em tudo — **sem instalar nada** e sem o
problema de "HTML antigo em cache". Sem backend, cadastro e importação ficam salvos no navegador (`localStorage`)
e sincronizam sozinhos quando o Python estiver instalado (§1). Para parar, feche a janela *Rastreio-Facil-Servidor-Local*.

### 0.1 Se a importação não funcionar: página de resgate
Duplo clique em **`abrir-resgate.bat`** (sobe o servidor se preciso e abre a página). A `static/resgate.html`
é **independente**: não usa `app.js`, não precisa de backend e grava direto no `localStorage`.
Ela tem **Analisar** (mostra linha a linha o que será NOVO / ATUALIZA / IGNORA e por quê) e
**Salvar no navegador** (grava e confirma o total). Também dá para baixar backup em JSON.

> ⚠️ **Use sempre o mesmo endereço nos dois lugares.** O navegador guarda o `localStorage` separado por
> endereço. Se a tela principal está em `localhost:8080`, abra o resgate em
> `http://localhost:8080/static/resgate.html`; se está em `:3000`, use `.../static/resgate.html` nessa porta.
> Abrindo o `index.html` por duplo clique (`file://`), o que salvar **não** aparece na tela principal.

### 0.2 Erros na tela
Se algo quebrar, aparece uma **barra vermelha no rodapé** com o erro (antes ele só ia para o console).
Confira também a versão no console do navegador: `window.APP_V` (tem que bater com `APP_VERSAO` do `main.py`).

## 1. Local (Windows)
```bat
REM pre-requisito: Python 3.12 de python.org com "Add python.exe to PATH"
cd rastreio-sistema1
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
REM edite o .env (DATABASE_URL opcional; SMTP opcional)
python main.py
REM abra http://localhost:3000/
```

Ou apenas **duplo clique** em `iniciar-sistema.bat`: ele escolhe um Python funcional (venv ou sistema),
instala as dependências que faltarem e sobe o servidor em `http://localhost:3000/` (a janela deve ficar aberta).
Nunca abra `static/index.html` direto (`file://`): sem o backend, o app entra em modo offline.

> ⚠️ Se `python` abrir a **Microsoft Store** (atalho fantasma do Windows) ou a `.venv` vier copiada de outro
> computador, apague a `.venv` e recrie: `Remove-Item .venv -Recurse -Force` → `python -m venv .venv`.


## 2. Com Postgres local (Docker)
```bash
docker run --name pg -e POSTGRES_PASSWORD=123 -e POSTGRES_DB=rastreio -p 5432:5432 -d postgres:16
# .env:
DATABASE_URL=postgresql://postgres:123@localhost:5432/rastreio?sslmode=disable
```

## 3. Neon / Supabase / Railway (grátis)
1. Crie o banco e copie a `DATABASE_URL` (use `?sslmode=require`).
2. No Render/Railway/Fly: adicione a env `DATABASE_URL` + `SMTP_USER/SMTP_PASS` (senha de app do Gmail).
3. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Teste: `GET /api/health` e `GET /api/db-status`

## 4. Gmail (notificação por e-mail)
1. Conta Google → Segurança → Verificação em 2 etapas → **Senhas de app** → gere uma.
2. `.env`: `SMTP_USER=seu@gmail.com` + `SMTP_PASS=<16 letras>` (sem espaços).
3. Sem isso, o sistema abre `mailto:` como fallback (não quebra).

## 5. Rotas úteis
- `/` → mesma interface (tela única `static/index.html`); `/main` e `/login` são aliases da mesma tela
- `/api/health` → `{ok, db, smtp}`
- `/api/db-status` → `{configured, connected, driver, url_safe}`
- `/api/versao` → `{versao}` (o front se recarrega sozinho quando muda)
- Envios: `GET/POST /api/envios`, `PUT/DELETE /api/envios/{id}`,
  `PATCH /api/envios/{id}/status`, `PATCH /api/envios/{id}/notificado`
- `POST /api/notificacoes`
- Auth: `GET /api/auth/estado`, `POST /api/auth/login`, `POST /api/auth/registrar`

## 6. Testes
```bat
.venv\Scripts\python.exe test_analise_erros.py
REM 59 verificações estáticas -> imprime "RESULTADO: TUDO OK"
```


