# -*- coding: utf-8 -*-
"""Banco dual: Postgres (DATABASE_URL) ou SQLite local."""
import os
import re

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
DB_PATH = os.getenv("DB_PATH", "database.db")
USE_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))
_pool = None

def db_status_info() -> dict:
    if USE_POSTGRES:
        safe = re.sub(r"://([^:]+):[^@]+@", r"://\1:****@", DATABASE_URL)
        return {"configured": True, "connected": _pool is not None,
                "driver": "postgres", "url_safe": safe}
    return {"configured": False, "connected": True,
            "driver": "sqlite", "url_safe": ""}

async def get_pool():
    global _pool
    if not USE_POSTGRES:
        return None
    if _pool is None:
        import asyncpg
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool

def q(sql: str) -> str:
    if not USE_POSTGRES:
        return sql
    out = []
    idx = 0
    for ch in sql:
        if ch == "?":
            idx += 1
            out.append(f"${idx}")
        else:
            out.append(ch)
    return "".join(out)

async def fetch_all(sql: str, args: tuple = ()):
    if USE_POSTGRES:
        pool = await get_pool()
        async with pool.acquire() as con:
            rows = await con.fetch(q(sql), *args)
            return [dict(r) for r in rows]
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, args)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def fetch_one(sql: str, args: tuple = ()):
    rows = await fetch_all(sql, args)
    return rows[0] if rows else None

async def execute(sql: str, args: tuple = ()):
    if USE_POSTGRES:
        pool = await get_pool()
        async with pool.acquire() as con:
            if sql.strip().upper().startswith("INSERT"):
                s2 = sql if "RETURNING" in sql.upper() else sql + " RETURNING id"
                row = await con.fetchrow(q(s2), *args)
                return (1, row["id"] if row else None)
            res = await con.execute(q(sql), *args)
            try:
                n = int(res.split()[-1])
            except Exception:
                n = 0
            return (n, None)
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(sql, args)
        await db.commit()
        return (cur.rowcount, cur.lastrowid)
async def init_db():
    if USE_POSTGRES:
        pool = await get_pool()
        async with pool.acquire() as con:
            await con.execute("""CREATE TABLE IF NOT EXISTS envios (
                id SERIAL PRIMARY KEY, destinatario TEXT DEFAULT '',
                codigo TEXT NOT NULL, celular TEXT DEFAULT '',
                email TEXT DEFAULT '', descricao TEXT DEFAULT '',
                status TEXT DEFAULT 'pendente', notificado INTEGER DEFAULT 0,
                criado_em TIMESTAMP DEFAULT NOW(),
                atualizado_em TIMESTAMP DEFAULT NOW(),
                criado_por INTEGER DEFAULT NULL,
                excluido_por INTEGER DEFAULT NULL,
                excluido_em TIMESTAMP DEFAULT NULL,
                status_anterior TEXT DEFAULT NULL)""")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_envios_codigo ON envios(codigo)")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_envios_status ON envios(status)")
            # unicidade do codigo (defesa em profundidade: o app ja checa antes de inserir)
            try:
                await con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_envios_codigo_unico ON envios(codigo)")
            except Exception:
                pass  # banco legado com codigos duplicados: mantem o indice simples acima
            await con.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY, nome TEXT NOT NULL DEFAULT '',
                email TEXT UNIQUE NOT NULL, senha_hash TEXT NOT NULL,
                admin INTEGER DEFAULT 0, ativo INTEGER DEFAULT 1,
                criado_em TIMESTAMP DEFAULT NOW())""")
            await con.execute("""CREATE TABLE IF NOT EXISTS sessoes (
                token TEXT PRIMARY KEY, usuario_id INTEGER NOT NULL,
                expira_em TIMESTAMP NOT NULL)""")
            await con.execute("""CREATE TABLE IF NOT EXISTS eventos (
                id SERIAL PRIMARY KEY, envio_id INTEGER NOT NULL,
                de_status TEXT DEFAULT '', para_status TEXT DEFAULT '',
                por_usuario INTEGER DEFAULT NULL, detalhe TEXT DEFAULT '',
                criado_em TIMESTAMP DEFAULT NOW())""")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_eventos_envio ON eventos(envio_id)")
            # cache do rastreio automatico (1 linha por envio; eventos = JSON em texto)
            await con.execute("""CREATE TABLE IF NOT EXISTS rastreios (
                id SERIAL PRIMARY KEY, envio_id INTEGER UNIQUE NOT NULL,
                situacao TEXT DEFAULT '', carrier TEXT DEFAULT '',
                eventos TEXT DEFAULT '[]', consultado_em TEXT DEFAULT '')""")
            # migracao: garante colunas atualizado_em + lixeira (soft delete) em bancos Postgres antigos
            for _ddl in (
                "ALTER TABLE envios ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMP DEFAULT NOW()",
                "ALTER TABLE envios ADD COLUMN IF NOT EXISTS excluido_por INTEGER DEFAULT NULL",
                "ALTER TABLE envios ADD COLUMN IF NOT EXISTS excluido_em TIMESTAMP DEFAULT NULL",
                "ALTER TABLE envios ADD COLUMN IF NOT EXISTS status_anterior TEXT DEFAULT NULL",
            ):
                try:
                    await con.execute(_ddl)
                except Exception:
                    pass
    else:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS envios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destinatario TEXT DEFAULT '', codigo TEXT NOT NULL,
                celular TEXT DEFAULT '', email TEXT DEFAULT '',
                descricao TEXT DEFAULT '', status TEXT DEFAULT 'pendente',
                notificado INTEGER DEFAULT 0,
                criado_em TEXT DEFAULT (datetime('now')),
                atualizado_em TEXT DEFAULT (datetime('now')),
                criado_por INTEGER DEFAULT NULL)""")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_envios_codigo ON envios(codigo)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_envios_status ON envios(status)")
            # unicidade do codigo (defesa em profundidade: o app ja checa antes de inserir)
            try:
                await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_envios_codigo_unico ON envios(codigo)")
            except Exception:
                pass  # banco legado com codigos duplicados: mantem o indice simples acima
            await db.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL DEFAULT '', email TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL, admin INTEGER DEFAULT 0,
                ativo INTEGER DEFAULT 1,
                criado_em TEXT DEFAULT (datetime('now')))""")
            await db.execute("""CREATE TABLE IF NOT EXISTS sessoes (
                token TEXT PRIMARY KEY, usuario_id INTEGER NOT NULL,
                expira_em TEXT NOT NULL)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                envio_id INTEGER NOT NULL, de_status TEXT DEFAULT '',
                para_status TEXT DEFAULT '', por_usuario INTEGER DEFAULT NULL,
                detalhe TEXT DEFAULT '',
                criado_em TEXT DEFAULT (datetime('now')))""")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_eventos_envio ON eventos(envio_id)")
            # cache do rastreio automatico (1 linha por envio; eventos = JSON em texto)
            await db.execute("""CREATE TABLE IF NOT EXISTS rastreios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                envio_id INTEGER UNIQUE NOT NULL, situacao TEXT DEFAULT '',
                carrier TEXT DEFAULT '', eventos TEXT DEFAULT '[]',
                consultado_em TEXT DEFAULT '')""")
            # migração leve: garante coluna atualizado_em em bancos antigos
            try:
                cur = await db.execute("PRAGMA table_info(envios)")
                cols = [r[1] for r in await cur.fetchall()]
                if "atualizado_em" not in cols:
                    await db.execute("ALTER TABLE envios ADD COLUMN atualizado_em TEXT DEFAULT (datetime('now'))")
                # migração lixeira: colunas para soft delete
                for col, ddl in [
                    ("excluido_por", "INTEGER DEFAULT NULL"),
                    ("excluido_em", "TEXT DEFAULT NULL"),
                    ("status_anterior", "TEXT DEFAULT NULL"),
                ]:
                    if col not in cols:
                        await db.execute(f"ALTER TABLE envios ADD COLUMN {col} {ddl}")
            except Exception:
                pass
            await db.commit()

