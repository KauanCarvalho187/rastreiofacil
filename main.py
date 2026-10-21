# -*- coding: utf-8 -*-
"""
Rastreio Facil — Backend FastAPI modernizado (dark UI + Postgres/SQLite) v20.
Melhorias v20:
- seguranca: logout, senha min 8, rate-limit login, CORS por env, limpeza sessoes
- performance: paginacao/busca server-side, estatisticas reais
- gestao: admin unico, troca senha, eventos/historico, notificacao em massa
v28: modo admin unico — o sistema tem UMA conta (admin@admin.com); os
usuarios extras foram removidos (sem tela de usuarios, sem /api/usuarios,
sem /api/auth/registrar).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Body, Header, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import os, re, hashlib, secrets, time, json
from datetime import datetime, timedelta, timezone
from html import escape as _html_escape
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

from db import (
    USE_POSTGRES, DB_PATH,
    fetch_all, fetch_one, execute, init_db, db_status_info,
)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SENDER_NAME = os.getenv("SENDER_NAME", "Rastreio Facil")
PORT = int(os.getenv("PORT", "3000"))
SESSAO_DIAS = int(os.getenv("SESSAO_DIAS", "7"))
# CORS restrito por env (melhoria): padrao "*" para nao quebrar Live Server/file://,
# mas em producao defina CORS_ORIGINS=https://seu-dominio.com,https://app...
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
# Rate-limit simples em memoria para login (melhoria anti brute-force)
_LOGIN_TENTATIVAS: dict = {}
LOGIN_MAX_TENT = int(os.getenv("LOGIN_MAX_TENT", "10"))
LOGIN_JANELA_SEG = int(os.getenv("LOGIN_JANELA_SEG", "300"))
# v28: admin unico — o sistema tem UMA conta de acesso (admin@admin.com).
# A senha inicial vem do env ADMIN_SENHA (troque no 1o acesso ou defina no .env).
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "admin@admin.com").strip().lower()
ADMIN_NOME = (os.getenv("ADMIN_NOME") or "Admin").strip() or "Admin"
ADMIN_SENHA = os.getenv("ADMIN_SENHA") or "admin12345"

def _login_bloqueado(ip: str) -> bool:
    agora = time.time()
    lst = [t for t in _LOGIN_TENTATIVAS.get(ip, []) if agora - t < LOGIN_JANELA_SEG]
    _LOGIN_TENTATIVAS[ip] = lst
    return len(lst) >= LOGIN_MAX_TENT

def _login_registrar_falha(ip: str):
    _LOGIN_TENTATIVAS.setdefault(ip, []).append(time.time())

def _login_limpar(ip: str):
    _LOGIN_TENTATIVAS.pop(ip, None)

import rastreio
# minutos em que o resultado do rastreio fica em cache (a API tem cota mensal de consultas)
RASTREIO_CACHE_MIN = int(os.getenv("RASTREIO_CACHE_MIN", "30"))

from validacao import (
    REGEX_CODIGO as _REGEX_CODIGO, REGEX_EMAIL as _REGEX_EMAIL,
    limpar_codigo as _limpar_codigo, validar_codigo as _validar_codigo_raw,
    validar_email as _validar_email_raw, normalizar_celular as _normalizar_celular_raw,
    normalizar_status as _normalizar_status,
)
REGEX_CODIGO = _REGEX_CODIGO
REGEX_EMAIL = _REGEX_EMAIL

def smtp_configurado() -> bool:
    return bool(SMTP_USER and SMTP_PASS)

def validar_codigo(codigo: str) -> str:
    try:
        return _validar_codigo_raw(codigo)
    except ValueError as e:
        raise HTTPException(422, str(e))

def validar_email(email: str) -> str:
    email = (email or "").strip()
    if not email:
        return email
    if " " in email:
        raise HTTPException(422, f"E-mail invalido: {email} — nao pode ter espacos")
    if "@" not in email:
        raise HTTPException(422, f"E-mail invalido: {email} — falta o @ (ex: nome@dominio.com)")
    local, _, dom = email.partition("@")
    if not local:
        raise HTTPException(422, f"E-mail invalido: {email} — falta o nome antes do @ (ex: nome@dominio.com)")
    if not dom:
        raise HTTPException(422, f"E-mail invalido: {email} — falta o dominio depois do @ (ex: nome@dominio.com)")
    if "." not in dom:
        raise HTTPException(422, f"E-mail invalido: {email} — falta o ponto no dominio (ex: dominio.com)")
    if not REGEX_EMAIL.match(email):
        raise HTTPException(422, f"E-mail invalido: {email} — formato esperado: nome@dominio.com")
    return email

def normalizar_celular(valor: str) -> str:
    d = re.sub(r"\D", "", str(valor or ""))
    if d.startswith("0055"):
        d = "55" + d[4:]
    if d.startswith("0") and len(d) > 1:
        d = d[1:]
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if d and len(d) not in (10, 11):
        raise HTTPException(422, "Celular invalido — use DDD + 8/9 digitos, ex: (11) 98765-4321")
    return d

def gerar_link_rastreio(codigo: str) -> str:
    return f"https://rastreamento.correios.com.br/app/index.php?objeto={codigo}"

def _agora_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def _expira_iso(dias: int = SESSAO_DIAS) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")

def hash_senha(senha: str) -> str:
    sal = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), 100_000).hex()
    return f"{sal}${h}"

def verificar_senha(senha: str, armazenada: str) -> bool:
    try:
        sal, h = armazenada.split("$", 1)
        calc = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), 100_000).hex()
        return secrets.compare_digest(calc, h)
    except (ValueError, TypeError, AttributeError):
        return False

def _e_duplicado(e: Exception) -> bool:
    """Detecta violacao de unicidade tanto no SQLite (IntegrityError) quanto no Postgres (UniqueViolationError)."""
    txt = f"{type(e).__name__} {e}".lower()
    return "unique" in txt or "duplicat" in txt

async def garantir_admin() -> None:
    """v28: admin unico.

    Garante que exista exatamente uma conta de acesso: ADMIN_EMAIL (admin@admin.com),
    com perfil de administrador e ativa. Contas antigas (criadas na era multi-usuario)
    sao removidas — junto com as sessoes delas — para que o sistema volte a ter
    um unico login. A senha inicial vem de ADMIN_SENHA; depois de criada, a senha
    pode ser trocada pela tela (POST /api/auth/trocar-senha) e nao e sobrescrita aqui.
    """
    try:
        row = await fetch_one("SELECT id, admin, ativo FROM usuarios WHERE email = ?", (ADMIN_EMAIL,))
        if not row:
            await execute(
                "INSERT INTO usuarios (nome,email,senha_hash,admin,ativo) VALUES (?,?,?,1,1)",
                (ADMIN_NOME, ADMIN_EMAIL, hash_senha(ADMIN_SENHA)))
            print(f"[AUTH] admin criado: {ADMIN_EMAIL} (senha inicial: {ADMIN_SENHA}) — troque a senha no 1o acesso")
        elif not row.get("admin") or not row.get("ativo"):
            await execute("UPDATE usuarios SET admin=1, ativo=1 WHERE id = ?", (row["id"],))
        # remove as demais contas (modo admin unico) e as sessoes delas
        await execute("DELETE FROM sessoes WHERE usuario_id <> (SELECT id FROM usuarios WHERE email = ?)", (ADMIN_EMAIL,))
        await execute("DELETE FROM usuarios WHERE email <> ?", (ADMIN_EMAIL,))
    except Exception as e:
        print(f"[AUTH] nao foi possivel garantir o admin: {e}")


async def auth_usuario(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Nao autenticado")
    token = authorization[7:].strip()
    if USE_POSTGRES:
        row = await fetch_one(
            "SELECT u.id, u.nome, u.email, u.admin FROM sessoes s "
            "JOIN usuarios u ON u.id = s.usuario_id "
            "WHERE s.token = ? AND s.expira_em > NOW() AND u.ativo = 1", (token,))
    else:
        row = await fetch_one(
            "SELECT u.id, u.nome, u.email, u.admin FROM sessoes s "
            "JOIN usuarios u ON u.id = s.usuario_id "
            "WHERE s.token = ? AND s.expira_em > ? AND u.ativo = 1", (token, _agora_iso()))
    if not row:
        raise HTTPException(401, "Sessao invalida ou expirada")
    return dict(row)

def _row_to_envio(row: dict) -> dict:
    status = (row.get("status") or "pendente")
    notificado = bool(row.get("notificado"))
    criado = row.get("criado_em")
    criado_s = str(criado) if criado is not None else ""
    # campos de lixeira (apenas admin vê quem excluiu)
    excluido_por = row.get("excluido_por")
    excluido_em = row.get("excluido_em")
    status_anterior = row.get("status_anterior")
    # nomes dos usuários (via JOIN em listar_envios)
    criado_por_nome = row.get("criado_por_nome")
    excluido_por_nome = row.get("excluido_por_nome")
    return {
        "_id": row.get("id"),
        "destinatario": row.get("destinatario") or "",
        "codigo": row.get("codigo"),
        "celular": row.get("celular") or "",
        "email": row.get("email") or "",
        "descricao": row.get("descricao") or "",
        "status": status,
        "notificado": notificado,
        "criado_em": criado_s,
        "link": gerar_link_rastreio(row.get("codigo") or ""),
        # lixeira
        "excluido_por": excluido_por,
        "excluido_em": excluido_em,
        "status_anterior": status_anterior,
        "criado_por_nome": criado_por_nome,
        "excluido_por_nome": excluido_por_nome,
    }

class EnvioUpdate(BaseModel):
    destinatario: Optional[str] = None
    codigo: Optional[str] = None
    celular: Optional[str] = None
    email: Optional[str] = None
    descricao: Optional[str] = None
    status: Optional[str] = None

class NotificacaoItem(BaseModel):
    codigo: str
    canal: str = "email"
    mensagem: str = ""
    assunto: Optional[str] = None

class LoginItem(BaseModel):
    email: str
    senha: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        # v28: admin unico — cria/garante a conta admin@admin.com
        await garantir_admin()
        # melhoria: limpa sessoes expiradas no boot (evita tabela crescendo p/ sempre)
        try:
            if USE_POSTGRES:
                await execute("DELETE FROM sessoes WHERE expira_em <= NOW()")
            else:
                await execute("DELETE FROM sessoes WHERE expira_em <= ?", (_agora_iso(),))
        except Exception:
            pass
    except Exception as e:
        print(f"[DB] init falhou: {e}")
    yield

app = FastAPI(title="Rastreio Facil", lifespan=lifespan)
# CORS: por env (melhoria). Padrao "*" mantem compat. com Live Server :5501 / file://.
# Em producao defina CORS_ORIGINS com seus dominios.
# NÃO remover o CORSMiddleware: sem isso o navegador bloqueia as chamadas cross-origin para a API.
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],
    allow_headers=["Content-Type","Authorization"])

@app.middleware("http")
async def _cache(request: Request, call_next):
    resp = await call_next(request)
    p = request.url.path
    if p.startswith(("/static/libs/","/static/img/")):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif p.endswith((".js",".css",".html",".json")):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    # cabecalhos de seguranca basicos (defesa em profundidade; nao afeta o funcionamento do app)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return resp

@app.get("/api/health")
async def health():
    st = db_status_info()
    ok = True
    err = None
    try:
        await fetch_one("SELECT 1 AS ok")
    except Exception as e:
        ok = False
        err = str(e)[:300]
    st["connected"] = ok
    if err:
        st["error"] = err
    return {"ok": ok, "db": st, "smtp": smtp_configurado(), "rastreio": rastreio.configurado()}

@app.get("/api/db-status")
async def db_status():
    st = db_status_info()
    try:
        await fetch_one("SELECT 1 AS ok")
        st["connected"] = True
    except Exception as e:
        st["connected"] = False
        st["error"] = str(e)[:300]
    return st

@app.get("/api/auth/estado")
async def estado_auth(authorization: str = Header(None)):
    """v28: admin unico — informa o e-mail do admin e se o token atual e de admin."""
    admin = False
    if authorization and authorization.startswith("Bearer "):
        try:
            u = await auth_usuario(authorization)
            admin = bool(u.get("admin"))
        except HTTPException:
            admin = False
    return {"admin": admin, "email": ADMIN_EMAIL}


@app.post("/api/envios")
async def criar_envios(payload: dict = Body(...), usuario: dict = Depends(auth_usuario)):
    if not isinstance(payload, dict):
        raise HTTPException(422, "Corpo invalido")
    m = payload.get("envios") if "envios" in payload else None
    if m is None:
        itens = [payload]
    elif isinstance(m, list):
        itens = m
    else:
        itens = [m]
    if not isinstance(itens, list) or not itens:
        raise HTTPException(422, "Corpo vazio ou invalido")
    if len(itens) > 500:
        raise HTTPException(422, "Lote muito grande (máximo 500 por vez)")
    # valida TUDO antes de inserir (lote atômico: ou entra tudo ou erro detalhado)
    norm = []
    erros = []
    vistos = set()
    for idx, it in enumerate(itens):
        lin = idx + 1
        if not isinstance(it, dict):
            erros.append(f"linha {lin}: item inválido"); continue
        nome = str(it.get("destinatario","") or it.get("nome","")).strip()
        cod_raw = str(it.get("codigo",""))
        mail_raw = str(it.get("email",""))
        cel_raw = str(it.get("celular",""))
        desc = str(it.get("descricao","") or it.get("observacoes","")).strip()
        status = str(it.get("status","pendente") or "pendente").strip().lower()
        if status not in ("pendente","a_caminho","entregue"): status = "pendente"
        if not nome:
            erros.append(f"linha {lin}: destinatário vazio"); continue
        try:
            codigo = validar_codigo(cod_raw)
        except HTTPException:
            erros.append(f"linha {lin} ({cod_raw.strip() or 'vazio'}): código inválido — use 2 letras + 9 números + BR"); continue
        try:
            email = validar_email(mail_raw)
        except HTTPException:
            erros.append(f"linha {lin}: e-mail inválido ({mail_raw.strip()})"); continue
        try:
            celular = normalizar_celular(cel_raw)
        except HTTPException:
            erros.append(f"linha {lin}: celular inválido ({cel_raw.strip()}) — use DDD + 8/9 dígitos"); continue
        if not email and not celular:
            erros.append(f"linha {lin}: Informe ao menos e-mail ou WhatsApp"); continue
        if codigo in vistos:
            erros.append(f"linha {lin}: código duplicado na planilha ({codigo})"); continue
        vistos.add(codigo)
        norm.append((nome, codigo, celular, email, desc, status))
    if erros and not norm:
        raise HTTPException(422, "Nenhuma linha válida. " + "; ".join(erros[:8]))
    criados = []
    uid = usuario.get("id") if usuario.get("id") else None
    for (nome, codigo, celular, email, desc, status) in norm:
        if await fetch_one("SELECT id FROM envios WHERE codigo = ?", (codigo,)):
            erros.append(f"{codigo}: já cadastrado (ignorado)"); continue
        try:
            _, last = await execute(
                "INSERT INTO envios (destinatario,codigo,celular,email,descricao,status,criado_por) VALUES (?,?,?,?,?,?,?)",
                (nome, codigo, celular, email, desc, status, uid))
        except Exception as e:
            # corrida entre o SELECT acima e o INSERT: o indice UNICO de codigo barra o duplicado
            if _e_duplicado(e):
                erros.append(f"{codigo}: já cadastrado (ignorado)"); continue
            raise
        row = await fetch_one("SELECT * FROM envios WHERE id = ?", (last,))
        criados.append(_row_to_envio(row))
    msg = f"{len(criados)} envio(s) criado(s)"
    if erros: msg += f" — {len(erros)} ignorado(s): " + "; ".join(erros[:8])
    return {"message": msg, "envios": criados, "erros": erros}

async def registrar_evento(envio_id: int, de_status: str, para_status: str, por_usuario, detalhe: str = ""):
    """Melhoria: historico/auditoria — quem mudou o status e quando."""
    try:
        await execute(
            "INSERT INTO eventos (envio_id,de_status,para_status,por_usuario,detalhe) VALUES (?,?,?,?,?)",
            (envio_id, de_status or "", para_status or "", por_usuario, detalhe or ""))
    except Exception:
        pass

@app.put("/api/envios/{envio_id}")
async def atualizar_envio(envio_id: int, upd: EnvioUpdate, usuario: dict = Depends(auth_usuario)):
    row = await fetch_one("SELECT * FROM envios WHERE id = ?", (envio_id,))
    if not row:
        raise HTTPException(404, "Envio nao encontrado")
    novos = (
        str(upd.destinatario).strip() if upd.destinatario is not None else row["destinatario"],
        validar_codigo(upd.codigo) if upd.codigo else row["codigo"],
        normalizar_celular(upd.celular) if upd.celular is not None else row["celular"],
        validar_email(upd.email) if upd.email is not None else row["email"],
        str(upd.descricao).strip() if upd.descricao is not None else row["descricao"],
    )
    if not str(novos[0] or "").strip():
        raise HTTPException(422, "Destinatario vazio")
    if not novos[3] and not novos[2]:
        raise HTTPException(422, "Informe ao menos e-mail ou WhatsApp")
    outro = await fetch_one("SELECT id FROM envios WHERE codigo = ? AND id <> ?", (novos[1], envio_id))
    if outro:
        raise HTTPException(409, f"Codigo {novos[1]} ja usado em outro envio")
    try:
        await execute("UPDATE envios SET destinatario=?, codigo=?, celular=?, email=?, descricao=?, atualizado_em=? WHERE id=?", (*novos, _agora_iso(), envio_id))
    except Exception as e:
        # corrida: o indice UNICO de codigo barra o duplicado mesmo se dois cliques passarem juntos
        if _e_duplicado(e):
            raise HTTPException(409, f"Codigo {novos[1]} ja usado em outro envio")
        raise
    if upd.status:
        s = upd.status.lower()
        if s in ("pendente","a_caminho","entregue"):
            await execute("UPDATE envios SET status=?, notificado=?, atualizado_em=? WHERE id=?", (s, 1 if s!="pendente" else 0, _agora_iso(), envio_id))
            try:
                await registrar_evento(envio_id, row["status"], s, usuario.get("id"), "edicao")
            except Exception:
                pass
    row2 = await fetch_one("SELECT * FROM envios WHERE id = ?", (envio_id,))
    return _row_to_envio(row2)

@app.patch("/api/envios/{envio_id}/status")
async def atualizar_status(envio_id: int, payload: dict = Body(...), usuario: dict = Depends(auth_usuario)):
    s = str(payload.get("status","")).lower()
    if s not in ("pendente","a_caminho","entregue"):
        raise HTTPException(422, "status deve ser pendente, a_caminho ou entregue")
    anterior = await fetch_one("SELECT status FROM envios WHERE id = ?", (envio_id,))
    n, _ = await execute("UPDATE envios SET status=?, notificado=?, atualizado_em=? WHERE id=?", (s, 1 if s!="pendente" else 0, _agora_iso(), envio_id))
    if n == 0:
        raise HTTPException(404, "Envio nao encontrado")
    try:
        await registrar_evento(envio_id, (anterior or {}).get("status", ""), s, usuario.get("id"), "status")
    except Exception:
        pass
    row = await fetch_one("SELECT * FROM envios WHERE id = ?", (envio_id,))
    return _row_to_envio(row)

@app.patch("/api/envios/{envio_id}/notificado")
async def marcar_notificado(envio_id: int, payload: dict = Body({}), usuario: dict = Depends(auth_usuario)):
    anterior = await fetch_one("SELECT status FROM envios WHERE id = ?", (envio_id,))
    if not anterior:
        raise HTTPException(404, "Envio nao encontrado")
    # correcao v21: nao regride status — "entregue" permanece entregue;
    # somente "pendente" avanca para "a_caminho" ao enviar a notificacao.
    s = "a_caminho" if (anterior.get("status") or "pendente") == "pendente" else anterior.get("status")
    n,_ = await execute("UPDATE envios SET status=?, notificado=1, atualizado_em=? WHERE id=?", (s, _agora_iso(), envio_id))
    if n == 0:
        raise HTTPException(404, "Envio nao encontrado")
    try:
        await registrar_evento(envio_id, anterior.get("status", "") or "", s, usuario.get("id"), "notificado")
    except Exception:
        pass
    return {"message": "Marcado como notificado"}

@app.delete("/api/envios/{envio_id}")
async def deletar_envio(envio_id: int, usuario: dict = Depends(auth_usuario)):
    # Soft delete: move para lixeira (status='excluido'), guarda quem excluiu e status anterior
    row = await fetch_one("SELECT id, status FROM envios WHERE id=?", (envio_id,))
    if not row:
        raise HTTPException(404, "Envio nao encontrado")
    status_anterior = row["status"]
    await execute("""
        UPDATE envios 
        SET status='excluido', excluido_por=?, excluido_em=?, status_anterior=?
        WHERE id=?
    """, (usuario["id"], _agora_iso(), status_anterior, envio_id))
    await registrar_evento(envio_id, status_anterior, "excluido", usuario["id"], "Movido para lixeira")
    return {"message": "Envio movido para lixeira"}

@app.post("/api/envios/{envio_id}/restaurar")
async def restaurar_envio(envio_id: int, usuario: dict = Depends(auth_usuario)):
    # Apenas admin pode restaurar
    if not usuario.get("admin"):
        raise HTTPException(403, "Apenas administradores podem restaurar da lixeira")
    row = await fetch_one("SELECT id, status_anterior FROM envios WHERE id=? AND status='excluido'", (envio_id,))
    if not row:
        raise HTTPException(404, "Envio nao encontrado na lixeira")
    status_voltar = row["status_anterior"] or "pendente"
    await execute("""
        UPDATE envios 
        SET status=?, excluido_por=NULL, excluido_em=NULL, status_anterior=NULL
        WHERE id=?
    """, (status_voltar, envio_id))
    await registrar_evento(envio_id, "excluido", status_voltar, usuario["id"], "Restaurado da lixeira")
    return {"message": f"Envio restaurado como {status_voltar}"}

@app.delete("/api/envios/{envio_id}/purga")
async def purgar_envio(envio_id: int, usuario: dict = Depends(auth_usuario)):
    # Hard delete definitivo — apenas admin
    if not usuario.get("admin"):
        raise HTTPException(403, "Apenas administradores")
    n,_ = await execute("DELETE FROM envios WHERE id=? AND status='excluido'", (envio_id,))
    if n == 0:
        raise HTTPException(404, "Envio nao encontrado na lixeira")
    await execute("DELETE FROM eventos WHERE envio_id=?", (envio_id,))
    await execute("DELETE FROM rastreios WHERE envio_id=?", (envio_id,))
    return {"message": "Envio removido permanentemente"}

def _cache_valido(cache: dict) -> bool:
    """Entregue nao muda mais (nao gasta cota); o resto vale RASTREIO_CACHE_MIN minutos."""
    if cache.get("situacao") == "entregue":
        return True
    try:
        quando = datetime.strptime(cache.get("consultado_em") or "", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return datetime.now(timezone.utc) - quando < timedelta(minutes=RASTREIO_CACHE_MIN)

def _rastreio_resposta(row: dict, cache: dict, em_cache: bool, aviso: str = "", status_atualizado: bool = False) -> dict:
    try:
        eventos = json.loads(cache.get("eventos") or "[]")
    except ValueError:
        eventos = []
    return {
        "codigo": row["codigo"], "status": row["status"],
        "situacao": cache.get("situacao") or "sem_eventos",
        "carrier": cache.get("carrier") or "", "eventos": eventos,
        "consultado_em": cache.get("consultado_em") or "",
        "cache": em_cache, "aviso": aviso, "status_atualizado": status_atualizado,
        "link": gerar_link_rastreio(row["codigo"]),
    }

@app.post("/api/envios/{envio_id}/rastrear")
async def rastrear_envio(envio_id: int, payload: dict = Body({}), usuario: dict = Depends(auth_usuario)):
    """Consulta os eventos do objeto na API de rastreio (com cache) e marca 'entregue' sozinho."""
    row = await fetch_one("SELECT * FROM envios WHERE id = ? AND status <> 'excluido'", (envio_id,))
    if not row:
        raise HTTPException(404, "Envio nao encontrado")
    cache = await fetch_one("SELECT * FROM rastreios WHERE envio_id = ?", (envio_id,))
    forcar = bool((payload or {}).get("forcar"))
    if cache and not forcar and _cache_valido(cache):
        return _rastreio_resposta(row, cache, True)
    try:
        res = await rastreio.consultar(row["codigo"])
    except rastreio.RastreioErro as e:
        if cache:  # provedor fora do ar: mostra a ultima consulta boa em vez de erro
            return _rastreio_resposta(row, cache, True, aviso=str(e))
        raise HTTPException(502 if rastreio.configurado() else 503, str(e))
    novo = {"situacao": res["situacao"], "carrier": res["carrier"],
            "eventos": json.dumps(res["eventos"], ensure_ascii=False), "consultado_em": _agora_iso()}
    args = (novo["situacao"], novo["carrier"], novo["eventos"], novo["consultado_em"], envio_id)
    n, _ = await execute("UPDATE rastreios SET situacao=?, carrier=?, eventos=?, consultado_em=? WHERE envio_id=?", args)
    if n == 0:
        await execute("INSERT INTO rastreios (situacao,carrier,eventos,consultado_em,envio_id) VALUES (?,?,?,?,?)", args)
    # so avanca para "entregue": pendente/a_caminho continuam sob controle de quem notifica o cliente
    atualizou = False
    if res["situacao"] == "entregue" and row["status"] in ("pendente", "a_caminho"):
        await execute("UPDATE envios SET status='entregue', notificado=1, atualizado_em=? WHERE id=?", (_agora_iso(), envio_id))
        await registrar_evento(envio_id, row["status"], "entregue", usuario.get("id") or None, "rastreio automatico")
        row = dict(row); row["status"] = "entregue"
        atualizou = True
    return _rastreio_resposta(row, novo, False, aviso=res["mensagem"], status_atualizado=atualizou)

def _montar_email(destino, assunto, html):
    from email.header import Header
    from email.utils import formataddr
    msg = MIMEMultipart("alternative")
    msg["Subject"] = str(Header(assunto, "utf-8"))
    msg["From"] = formataddr((str(Header(SENDER_NAME, "utf-8")), SMTP_USER))
    msg["To"] = destino
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg

# emojis via escape Unicode (imunes a problema de codificação do arquivo)
E_PACK = "\U0001F4E6"   # 📦
E_WAVE = "\U0001F44B"   # 👋
E_LIST = "\U0001F4CB"   # 📋
E_LINK = "\U0001F517"   # 🔗
SETA = "\u25B8"         # ▸

def _data_envio_br(criado_em) -> str:
    try:
        s = str(criado_em or "")
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return datetime.now().strftime("%d/%m/%Y")

def _montar_html_email(destinatario: str, codigo: str, descricao: str = "", data_envio: str = "") -> str:
    nome = _html_escape(str(destinatario or "").strip() or "cliente")
    cod = _html_escape(str(codigo or ""))
    link = gerar_link_rastreio(str(codigo or ""))
    detalhes = [f"{SETA} <b>Código:</b> {cod}"]
    if str(descricao or "").strip():
        detalhes.append(f"{SETA} <b>Descrição:</b> {_html_escape(str(descricao).strip())}")
    detalhes.append(f"{SETA} <b>Data de Envio:</b> {_html_escape(str(data_envio or _data_envio_br(None)))}")
    return f"""
<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#222;line-height:1.6">
  <div style="background:#0f172a;color:#fff;padding:18px 24px;border-radius:10px 10px 0 0">
    <h2 style="margin:0;font-size:18px">{E_PACK} Correios — Código de Rastreio</h2>
  </div>
  <div style="border:1px solid #e2e8f0;border-top:0;padding:24px;border-radius:0 0 10px 10px">
    <p style="margin:0 0 12px">Olá, <b>{nome}</b>! Tudo bem? {E_WAVE}</p>
    <p style="margin:0 0 16px">Sua correspondência foi postada e já está em rota de entrega.</p>
    <p style="margin:0 0 6px"><b>{E_LIST} Detalhes do envio:</b><br>{'<br>'.join(detalhes)}</p>
    <p style="margin:20px 0">
      <a href="{link}" style="background:#2563eb;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none;display:inline-block">{E_LINK} Acompanhar em tempo real</a>
    </p>
    <p style="font-size:12px;color:#64748b;word-break:break-all;margin:0 0 16px">Ou copie o link:<br>{link}</p>
    <p style="margin:0 0 8px">Qualquer dúvida, estamos à disposição!</p>
    <p style="margin:0">Atenciosamente,<br><b>{_html_escape(SENDER_NAME)}</b></p>
  </div>
</div>"""

async def enviar_email(destino, assunto, html) -> bool:
    if not smtp_configurado():
        return False
    try:
        use_tls = (SMTP_PORT == 465)
        await aiosmtplib.send(_montar_email(destino, assunto, html),
            hostname=SMTP_HOST, port=SMTP_PORT,
            start_tls=(not use_tls), use_tls=use_tls,
            username=SMTP_USER, password=SMTP_PASS)
        return True
    except Exception as e:
        print(f"[SMTP] falha: {e}")
        return False

@app.post("/api/notificacoes")
async def enviar_notificacao(item: NotificacaoItem, usuario: dict = Depends(auth_usuario)):
    codigo = validar_codigo(item.codigo)
    canal = str(item.canal or "email").strip().lower()
    if canal == "whatsapp":
        return {"success": False, "fallback": True, "message": "WhatsApp via wa.me"}
    row = await fetch_one("SELECT * FROM envios WHERE codigo = ?", (codigo,))
    if not row:
        raise HTTPException(404, "Codigo nao cadastrado")
    destino = (row["email"] or "").strip()
    if not destino:
        return {"success": False, "fallback": True, "message": "Sem e-mail cadastrado"}
    html = item.mensagem.strip() or _montar_html_email(
        row["destinatario"] if row else "",
        codigo,
        (row["descricao"] if row else "") or "",
        _data_envio_br(row["criado_em"] if row else None),
    )
    ok = await enviar_email(destino, item.assunto or f"{E_PACK} Correios — Código de Rastreio: {codigo}", html)
    if ok:
        await execute("UPDATE envios SET status='a_caminho', notificado=1 WHERE codigo=?", (codigo,))
        return {"success": True, "result": {"enviado": True, "email": destino}}
    return {"success": False, "fallback": True, "message": "SMTP nao configurado — usar mailto:"}

class MassaItem(BaseModel):
    canal: str = "email"

@app.post("/api/notificacoes/massa")
async def notificacao_massa(item: MassaItem, usuario: dict = Depends(auth_usuario)):
    """Melhoria: notifica pendentes de uma vez (antes: 1 por 1)."""
    if (item.canal or "email").lower() != "email":
        raise HTTPException(422, "Massa disponivel para e-mail")
    if not smtp_configurado():
        raise HTTPException(422, "SMTP nao configurado")
    rows = await fetch_all("SELECT * FROM envios WHERE status='pendente' AND email<>'' ORDER BY id")
    enviadas, falhas = 0, []
    for r in rows:
        try:
            html = _montar_html_email(r.get("destinatario") or "", r.get("codigo") or "",
                r.get("descricao") or "", _data_envio_br(r.get("criado_em")))
            ok = await enviar_email((r.get("email") or "").strip(),
                f"{E_PACK} Correios - Codigo: {r.get('codigo')}", html)
            if ok:
                await execute("UPDATE envios SET status='a_caminho', notificado=1, atualizado_em=? WHERE id=?", (_agora_iso(), r["id"]))
                enviadas += 1
            else:
                falhas.append(r.get("codigo"))
        except Exception:
            falhas.append(r.get("codigo"))
    return {"message": f"{enviadas} enviado(s)", "enviadas": enviadas, "falhas": falhas}

@app.post("/api/auth/login")
async def login(item: LoginItem, request: Request):
    ip = (request.client.host if request.client else "desconhecido")
    if _login_bloqueado(ip):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
    email = item.email.strip().lower()
    row = await fetch_one("SELECT * FROM usuarios WHERE email = ? AND ativo = 1", (email,))
    if not row or not verificar_senha(item.senha, row["senha_hash"]):
        _login_registrar_falha(ip)
        raise HTTPException(401, "E-mail ou senha incorretos")
    _login_limpar(ip)
    token = secrets.token_hex(32)
    if USE_POSTGRES:
        await execute(f"INSERT INTO sessoes (token,usuario_id,expira_em) VALUES (?,?, NOW() + INTERVAL '{SESSAO_DIAS} days')", (token, row["id"]))
    else:
        await execute("INSERT INTO sessoes (token,usuario_id,expira_em) VALUES (?,?,?)", (token, row["id"], _expira_iso(SESSAO_DIAS)))
    return {"token": token, "user": {"id": row["id"], "nome": row["nome"], "email": row["email"], "admin": bool(row["admin"])}}

@app.post("/api/auth/logout")
async def logout(authorization: str = Header(None)):
    """Melhoria: revoga o token no banco (antes so apagava no navegador)."""
    if authorization and authorization.startswith("Bearer "):
        try:
            await execute("DELETE FROM sessoes WHERE token = ?", (authorization[7:].strip(),))
        except Exception:
            pass
    return {"message": "Sessao encerrada"}

class TrocaSenhaItem(BaseModel):
    senha_atual: str
    senha_nova: str

@app.post("/api/auth/trocar-senha")
async def trocar_senha(item: TrocaSenhaItem, usuario: dict = Depends(auth_usuario)):
    row = await fetch_one("SELECT * FROM usuarios WHERE id = ?", (usuario["id"],))
    if not row or not verificar_senha(item.senha_atual, row["senha_hash"]):
        raise HTTPException(401, "Senha atual incorreta")
    if len(item.senha_nova or "") < 8:
        raise HTTPException(422, "Senha muito curta (minimo 8)")
    await execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (hash_senha(item.senha_nova), usuario["id"]))
    return {"message": "Senha alterada"}

@app.get("/api/envios")
async def listar_envios(usuario: dict = Depends(auth_usuario),
    q: str = Query(""), status: str = Query(""),
    page: int = Query(1, ge=1), limit: int = Query(200, ge=1, le=500)):
    """Melhoria: paginacao + busca server-side (antes: SELECT * sem limite).
       Suporta filtro status='excluido' (lixeira). JOIN usuarios para nomes.
       Por padrao EXCLUI lixeira (status='excluido') da listagem normal."""
    where, args = [], []
    valid_status = ("pendente", "a_caminho", "entregue", "excluido")
    active_status = ("pendente", "a_caminho", "entregue")
    # Se status nao informado, filtra apenas status ativos (exclui lixeira)
    if status and status in valid_status:
        where.append("status = ?"); args.append(status)
    elif not status:
        where.append("status IN (?,?,?)"); args += active_status
    if q:
        like = f"%{q.strip()}%"
        where.append("(destinatario LIKE ? OR codigo LIKE ? OR descricao LIKE ?)")
        args += [like, like, like]
    w = ("WHERE " + " AND ".join(where)) if where else ""
    total_row = await fetch_one(f"SELECT COUNT(*) AS n FROM envios {w}", tuple(args))
    total = int((total_row or {}).get("n", 0))
    off = (page - 1) * limit
    # JOIN usuarios para nomes: criado_por_nome e (se admin) excluido_por_nome
    is_admin = bool(usuario and usuario.get("admin"))
    join_excluido = "LEFT JOIN usuarios u_del ON u_del.id = e.excluido_por" if is_admin else ""
    select_excluido = "u_del.nome AS excluido_por_nome" if is_admin else "NULL AS excluido_por_nome"
    sql = f"""
        SELECT e.*, u_cri.nome AS criado_por_nome, {select_excluido}
        FROM envios e
        LEFT JOIN usuarios u_cri ON u_cri.id = e.criado_por
        {join_excluido}
        {w}
        ORDER BY e.id DESC LIMIT ? OFFSET ?
    """
    rows = await fetch_all(sql, tuple(args) + (limit, off))
    return {"envios": [_row_to_envio(r) for r in rows], "total": total, "page": page, "limit": limit}

app.mount("/static", StaticFiles(directory="static"), name="static")

# versao do front: o navegador compara e recarrega sozinho quando o servidor atualiza (evita aba velha travada)
APP_VERSAO = "29"

@app.get("/api/estatisticas")
async def estatisticas(usuario: dict = Depends(auth_usuario)):
    """Melhoria: dashboard contado no SQL (antes: contado no navegador)."""
    rows = await fetch_all("SELECT status, COUNT(*) AS n FROM envios GROUP BY status")
    mapa = {r["status"]: int(r["n"]) for r in rows}
    total = sum(mapa.values())
    return {"total": total, "pendente": mapa.get("pendente", 0),
        "a_caminho": mapa.get("a_caminho", 0), "entregue": mapa.get("entregue", 0)}

@app.get("/api/backup")
async def backup_banco(usuario: dict = Depends(auth_usuario)):
    """Melhoria: backup do banco — admin baixa o SQLite inteiro (restore = copiar o arquivo de volta)."""
    if not usuario.get("admin"):
        raise HTTPException(403, "Apenas administradores")
    if USE_POSTGRES:
        raise HTTPException(400, "Backup de arquivo disponivel apenas com SQLite (Postgres: use pg_dump)")
    if not os.path.exists(DB_PATH):
        raise HTTPException(404, "Arquivo do banco nao encontrado")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return FileResponse(DB_PATH, media_type="application/octet-stream",
                        filename=f"backup-rastreio-{stamp}.db")

@app.get("/api/envios/{envio_id}/eventos")
async def historico_envio(envio_id: int, usuario: dict = Depends(auth_usuario)):
    rows = await fetch_all("SELECT * FROM eventos WHERE envio_id = ? ORDER BY id DESC LIMIT 50", (envio_id,))
    return {"eventos": [dict(r) for r in rows]}

@app.get("/api/versao")
async def versao():
    return {"versao": APP_VERSAO}

# HTML sempre sem cache: garante que o navegador pegue os ?v= mais novos do JS (evita aba rodando código velho)
_SEM_CACHE = {"Cache-Control": "no-store"}

@app.get("/")
async def root():
    return FileResponse("static/index.html", headers=_SEM_CACHE)

# Aliases de compatibilidade: links/bookmarks antigos apontavam para /main e /login.
# Servem a mesma tela única (o login é o modal do app.js) — mantidos para não dar 404.
@app.get("/main")
async def main_page():
    return FileResponse("static/index.html", headers=_SEM_CACHE)

@app.get("/login")
async def login_page():
    return FileResponse("static/index.html", headers=_SEM_CACHE)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
