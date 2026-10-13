# PROMPT — Verificação profunda + autorreparo (sistema profissional)

> Use este prompt inteiro com um agente de IA (ou seja você). Objetivo: o sistema
> **Rastreio Fácil** deve operar como um sistema profissional — zero erros em
> cadastrar, editar, verificar (listar/buscar), excluir, importar, exportar e login —
> e **cada erro encontrado deve ser corrigido na raiz e transformado em aprendizado**
> (teste de regressão permanente) para não voltar a acontecer.

---

## 0. Contexto do projeto (não pule)

- **Stack**: Python 3.12 + FastAPI + SQLite (`database.db`; Postgres opcional via env) · front estático em `static/` (JS vanilla, sem build) · testes com `urllib` e Selenium.
- **Servidor**: `python -m uvicorn main:app --port 3001` (health: `GET /api/health` → `{"versao":"27"}`).
- **Arquivos principais**: `main.py` (rotas), `db.py` (acesso/diagrama), `validacao.py` (validações), `static/app.js`, `static/index.html`, `static/styles.css`.
- **Suítes existentes** (todas devem estar verdes no fim):

  | Suíte | Comando | Esperado hoje |
  |---|---|---|
  | análise estática/regressões | `python test_analise_erros.py` | `RESULTADO: TUDO OK` (73 checks) |
  | fluxo E2E API | `python teste_fluxo.py` | `13 passou, 0 falhou` |
  | API real (validações) | `python teste_api_real.py` | `23 passou, 0 falhou` |
  | canais (Correios/WhatsApp/e-mail) | `python teste_canais.py` | `17 passou, 0 falhou` |
  | CRUD exaustivo | `python teste_crud.py` | `30 passou, 0 falhou` |
  | UI no navegador (Selenium/Chrome) | `python teste_chrome.py` | `10 passou, 0 falhou` |

- **Banco baseline**: 43 envios (**3 originais + 40 cadastrados `QZ100000001BR`…`QZ100000040BR`**) + 2 usuários (`admin@empresa.com` / `admin12345` e `op@empresa.com`). **Nunca apague os 40 QZ nem os 3 originais.** Resíduos de teste remova com `python limpar_teste.py` (apaga só `Teste %`/`Fulano %`/códigos de teste) e inspecione com `python inspecionar_db.py`.
- **Ambiente Windows/PowerShell**: use `$env:PYTHONIOENCODING='utf-8'` antes de rodar Python no terminal.
- **Git**: `git status` limpo no início e no fim; commit por correção relevante com
  `git -c user.name='Rastreio Facil' -c user.email='rastreio@local' commit -m 'correcao: ...'`.

---

## 1. Etapa A — Verificação profunda (diagnóstico antes de mexer)

1. **Ambiente**: servidor no ar (`/api/health`), `git status` limpo, baseline conferido (`inspecionar_db.py`).
2. **Rode as 6 suítes** acima e anote cada falha com o nome exato do check.
3. **Auditoria de código** (`main.py`, `db.py`, `validacao.py`, `app.js`):
   - Todas as rotas CRUD respondem 200/401/404/409/422 corretamente? Algum caminho pode devolver **500** com stack trace?
   - Existe validação de entrada em **toda** rota POST/PUT/PATCH (destinatário, código, e-mail, celular, status)?
   - Auth: rotas privadas exigem token válido? token expirado/revogado → 401? admin-only (`/api/backup`, `/api/usuarios`) → 403 para não-admin?
   - No front: toda chamada `fetch` trata erro (res.ok) e mostra mensagem amigável? Há `try/catch` nas operações de salvar/editar/excluir? A lista re-renderiza após CUD (sem F5)?
   - Estado offline (`lerLocais`) não perde dados ao voltar online (merge por código)?
4. **E2E de UI** (Selenium, padrão do `teste_chrome.py`: login no `modal-login`, interceptar `window.open` para capturar links):
   - Cadastrar válido → aparece na lista e nos cards; cadastrar inválido → **erro visível e nenhum registro corrompido**.
   - Editar (modal) → campos salvos e refletidos; status muda nos cards; excluir → some da lista e dos contadores.
   - Busca/filtro/export/import (CSV válido e malformado).
5. **Bordas de carga/dados**: lote de 40+ via API, caracteres acentuados/emoji, códigos duplicados, IDs inexistentes, corpo vazio/não-JSON.

## 2. Etapa B — Regra de autorreparo (corrigir E aprender)

Para **cada erro** encontrado, siga este ciclo — nunca pule etapas:

1. **Reproduzir**: reduza o erro ao menor comando/teste que falha (anote a saída exata).
2. **Diagnosticar causa raiz**: leia o código envolvido até entender *por que* falha. Nunca adivinhe.
3. **Corrigir no código-fonte** (backend ou front) — **proibido** "consertar" apenas o teste, desativar check, apagar asserção ou esconder a UI para o erro sumir. Se o *teste* estiver errado, só altere-o com justificativa explícita de qual comportamento estava errado e qual é o correto.
4. **Aprender = teste de regressão permanente**: adicione um check novo que **falhava antes** e **passa depois**:
   - erro de rota/validação → check novo em `teste_api_real.py` ou `teste_crud.py`;
   - erro de comportamento estático (rota existe, tratamento existe) → check em `test_analise_erros.py`;
   - erro de UI → check novo em `teste_chrome.py`.
5. **Provar**: rode a suíte do teste novo + **todas as 6 suítes**. Tudo verde obrigatório.
6. **Registrar**: commit `correcao: <o que> (<arquivo>)` e inclua a lição no relatório final (seção 4). Se a lição for transversal (ex.: "toda rota nova precisa de validação"), adicione um check estático permanente que a imponha.

**Critério de "erro profissional"**: qualquer 500, mensagem crua ("Traceback...", "null", "undefined"), tela travada sem feedback, dado salvo sem validação, lista desatualizada após CUD ou perda de dados offline **conta como bug para este ciclo**.

## 3. Etapa C — Checklist "sistema profissional" (feche tudo que faltar)

- [ ] Nenhum 500 em fluxo nenhum (validação sempre antecede o handler)
- [ ] Mensagens de erro em pt-BR, específicas e no lugar certo (campo / toast)
- [ ] Exclusão sempre com confirmação; operações com feedback de loading (botão desabilitado durante a requisição)
- [ ] Estados vazios amigáveis (lista vazia, busca sem resultado)
- [ ] Navegação sem F5: criar/editar/excluir/atualizar status re-renderizam lista + cards
- [ ] Segurança básica: senha nunca em log/resposta, token só em memória, `.env` fora do git, admin check em rotas sensíveis
- [ ] Cache/versão consistente (`?v=` do front = `APP_VERSAO`)
- [ ] Consultas paginadas (sem `SELECT *` ilimitado na UI) e índices/`PRAGMA` ok

## 4. Etapa D — Relatório final (obrigatório)

Responda com:
1. **Verificado**: lista do que foi auditado (suítes + código + UI) com números.
2. **Erros encontrados**: cada um com reprodução e causa raiz.
3. **Correções**: arquivos alterados + commits.
4. **Aprendizados**: testes de regressão novos (nome do check + suíte) e regras que passaram a valer.
5. **Estado final**: resultados das 6 suítes, `git status` limpo, baseline do banco intacto.

**Regra máxima**: só declare "100% / sistema profissional" quando as 6 suítes estiverem
verdes **com os testes novos incluídos** e o E2E de UI passar de ponta a ponta.
