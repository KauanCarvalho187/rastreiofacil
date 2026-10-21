# -*- coding: utf-8 -*-
"""Testes de API in-process (banco temporario por teste).

Cobrem, em pytest, o comportamento antes verificado por teste_fluxo.py,
teste_api_real.py, teste_crud.py e teste_bordas.py. Nao precisam de servidor.

v28: o sistema tem UM admin so (admin@admin.com) — as rotas de gestao de
usuarios (/api/usuarios) e de registro (/api/auth/registrar) nao existem mais.
"""


def _cod(n):
    return f"AA{n:09d}BR"


def _criar(client, H, codigo, destinatario="Cliente", **extra):
    body = {"destinatario": destinatario, "codigo": codigo, "email": "cliente@t.com"}
    body.update(extra)
    return client.post("/api/envios", json=body, headers=H)


def _id_de(client, H, codigo):
    d = client.get("/api/envios", params={"q": codigo}, headers=H).json()
    return d["envios"][0]["_id"]


# ------------------------------------------------------------------ servico

def test_health(client):
    d = client.get("/api/health").json()
    assert d["ok"] is True
    assert d["db"]["driver"] == "sqlite"


def test_versao(client):
    assert client.get("/api/versao").json()["versao"] == "30"


def test_db_status(client, auth):
    d = client.get("/api/db-status").json()
    assert d and isinstance(d, dict)


def test_cabecalhos_seguranca(client):
    h = client.get("/").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "SAMEORIGIN"
    assert h["referrer-policy"] == "no-referrer"
    assert "geolocation=()" in h["permissions-policy"]


def test_index_serve_e_sem_cache(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Rastreio Fácil" in r.text
    assert r.headers["cache-control"] == "no-store"
    # aliases de compatibilidade
    assert client.get("/main").status_code == 200
    assert client.get("/login").status_code == 200


# --------------------------------------------------------------------- auth

def test_estado_informa_admin_unico(client, auth):
    d = client.get("/api/auth/estado").json()
    assert d["email"] == "admin@admin.com"
    assert d["admin"] is False
    d = client.get("/api/auth/estado", headers=auth["H"]).json()
    assert d["admin"] is True and d["email"] == "admin@admin.com"


def test_login_errado_401(client, auth):
    r = client.post("/api/auth/login", json={"email": "admin@admin.com", "senha": "errada"})
    assert r.status_code == 401


def test_login_email_inexistente_401(client, auth):
    assert client.post("/api/auth/login", json={"email": "ninguem@t.com", "senha": "x1234567"}).status_code == 401


def test_somente_o_admin_entra(client, auth):
    """v28: nao existe mais cadastro de usuarios — so o admin@admin.com entra."""
    assert client.post("/api/auth/login",
                       json={"email": "outro@t.com", "senha": "admin12345"}).status_code == 401


def test_rotas_de_usuarios_nao_existem_mais(client, auth):
    """v28: /api/usuarios e /api/auth/registrar foram removidas."""
    assert client.get("/api/usuarios", headers=auth["H"]).status_code == 404
    assert client.patch("/api/usuarios/1", json={"ativo": False}, headers=auth["H"]).status_code == 404
    assert client.post("/api/auth/registrar",
                       json={"nome": "X", "email": "x@t.com", "senha": "12345678"},
                       headers=auth["H"]).status_code == 404


def test_logout_revoga_sessao(client, auth):
    assert client.post("/api/auth/logout", headers=auth["H"]).status_code == 200
    assert client.get("/api/envios", headers=auth["H"]).status_code == 401


def test_trocar_senha(client, auth):
    r = client.post("/api/auth/trocar-senha",
                    json={"senha_atual": "admin12345", "senha_nova": "novasenha1"}, headers=auth["H"])
    assert r.status_code == 200
    assert client.post("/api/auth/login", json={"email": "admin@admin.com", "senha": "novasenha1"}).status_code == 200
    r = client.post("/api/auth/trocar-senha",
                    json={"senha_atual": "errada", "senha_nova": "outrasenha1"}, headers=auth["H"])
    assert r.status_code == 401


def test_token_invalido_401(client, auth):
    assert client.get("/api/envios", headers={"Authorization": "Bearer nao_existe"}).status_code == 401


# ------------------------------------------------------- admin unico (v28)

def _usuarios_no_banco():
    """Le a tabela usuarios direto do SQLite temporario do teste."""
    import asyncio
    import aiosqlite
    import db

    async def _l():
        async with aiosqlite.connect(db.DB_PATH) as c:
            c.row_factory = aiosqlite.Row
            cur = await c.execute("SELECT email, admin, ativo FROM usuarios")
            return [dict(r) for r in await cur.fetchall()]

    return asyncio.run(_l())


def test_admin_unico_criado_no_boot(client, auth):
    """A conta admin@admin.com existe sozinha (sem usuario de equipe)."""
    rows = _usuarios_no_banco()
    assert len(rows) == 1
    assert rows[0]["email"] == "admin@admin.com"
    assert rows[0]["admin"] == 1 and rows[0]["ativo"] == 1


def test_contas_antigas_sao_removidas(client, auth):
    """v28: contas antigas (era multi-usuario) somem no boot."""
    import asyncio
    import aiosqlite
    import db
    import main

    async def _insere():
        async with aiosqlite.connect(db.DB_PATH) as c:
            await c.execute("INSERT INTO usuarios (nome,email,senha_hash,admin,ativo) VALUES (?,?,?,0,1)",
                            ("Antigo", "antigo@t.com", "x"))
            await c.commit()

    asyncio.run(_insere())
    asyncio.run(main.garantir_admin())
    assert [r["email"] for r in _usuarios_no_banco()] == ["admin@admin.com"]


# --------------------------------------------------------------- envios CRUD

def test_criar_simples(client, auth):
    r = _criar(client, auth["H"], _cod(1), "Fulano")
    d = r.json()
    assert r.status_code == 200 and len(d["envios"]) == 1
    e = d["envios"][0]
    assert e["_id"] and e["link"].endswith("objeto=" + _cod(1))


def test_criar_lote_parcial(client, auth):
    r = client.post("/api/envios", json={"envios": [
        {"destinatario": "A", "codigo": _cod(1), "email": "a@t.com"},
        {"destinatario": "B", "codigo": "INVALIDO", "email": "b@t.com"}]}, headers=auth["H"])
    d = r.json()
    assert r.status_code == 200 and len(d["envios"]) == 1 and len(d["erros"]) == 1


def test_duplicado_ignorado(client, auth):
    _criar(client, auth["H"], _cod(1))
    d = _criar(client, auth["H"], _cod(1), "Dup").json()
    assert len(d["envios"]) == 0
    assert any("cadastrado" in e for e in d["erros"])


def test_sem_contato_422(client, auth):
    r = client.post("/api/envios", json={"destinatario": "X", "codigo": _cod(1)}, headers=auth["H"])
    assert r.status_code == 422


def test_lote_grande_422(client, auth):
    lote = [{"destinatario": "X", "codigo": _cod(i), "email": "x@t.com"} for i in range(501)]
    assert client.post("/api/envios", json={"envios": lote}, headers=auth["H"]).status_code == 422


def test_corpo_nao_dict_422(client, auth):
    H = {**auth["H"], "Content-Type": "application/json"}
    assert client.post("/api/envios", content=b"[1,2,3]", headers=H).status_code == 422


def test_lista_busca_filtro_paginacao(client, auth):
    for i in (1, 2, 3):
        _criar(client, auth["H"], _cod(i), f"Pessoa {i}")
    alvo = _id_de(client, auth["H"], _cod(1))
    client.patch(f"/api/envios/{alvo}/status", json={"status": "entregue"}, headers=auth["H"])

    d = client.get("/api/envios", headers=auth["H"]).json()
    assert d["total"] == 3
    d = client.get("/api/envios", params={"q": "Pessoa 2"}, headers=auth["H"]).json()
    assert len(d["envios"]) == 1
    d = client.get("/api/envios", params={"status": "entregue"}, headers=auth["H"]).json()
    assert d["envios"] and all(e["status"] == "entregue" for e in d["envios"])
    d = client.get("/api/envios", params={"limit": 2, "page": 1}, headers=auth["H"]).json()
    assert len(d["envios"]) == 2


def test_parametros_invalidos_422(client, auth):
    assert client.get("/api/envios", params={"limit": 9999}, headers=auth["H"]).status_code == 422
    assert client.get("/api/envios", params={"page": 0}, headers=auth["H"]).status_code == 422


def test_unicode_roundtrip(client, auth):
    r = client.post("/api/envios",
                    json={"destinatario": "José André Ção 📦", "codigo": _cod(9), "email": "j@t.com"},
                    headers=auth["H"])
    assert r.status_code == 200
    d = client.get("/api/envios", params={"q": "José"}, headers=auth["H"]).json()
    assert any("José" in e["destinatario"] for e in d["envios"])


def test_sql_injection_nao_quebra(client, auth):
    _criar(client, auth["H"], _cod(1))
    r = client.get("/api/envios", params={"q": "';DROP TABLE envios;--"}, headers=auth["H"])
    assert r.status_code == 200
    assert client.get("/api/envios", headers=auth["H"]).json()["total"] == 1


def test_put_edita(client, auth):
    eid = _criar(client, auth["H"], _cod(1)).json()["envios"][0]["_id"]
    d = client.put(f"/api/envios/{eid}",
                   json={"descricao": "EDITADO", "celular": "11999998888"}, headers=auth["H"]).json()
    assert d["descricao"] == "EDITADO" and d["celular"] == "11999998888"


def test_put_validacoes(client, auth):
    eid = _criar(client, auth["H"], _cod(1)).json()["envios"][0]["_id"]
    assert client.put(f"/api/envios/{eid}", json={"destinatario": "  "}, headers=auth["H"]).status_code == 422
    assert client.put(f"/api/envios/{eid}", json={"email": "", "celular": ""}, headers=auth["H"]).status_code == 422


def test_put_codigo_de_outro_409(client, auth):
    a = _criar(client, auth["H"], _cod(1)).json()["envios"][0]["_id"]
    _criar(client, auth["H"], _cod(2))
    assert client.put(f"/api/envios/{a}", json={"codigo": _cod(2)}, headers=auth["H"]).status_code == 409


def test_put_inexistente_404(client, auth):
    assert client.put("/api/envios/999999", json={"destinatario": "x"}, headers=auth["H"]).status_code == 404


def test_patch_status(client, auth):
    eid = _criar(client, auth["H"], _cod(1)).json()["envios"][0]["_id"]
    d = client.patch(f"/api/envios/{eid}/status", json={"status": "a_caminho"}, headers=auth["H"]).json()
    assert d["status"] == "a_caminho" and d["notificado"] is True
    assert client.patch(f"/api/envios/{eid}/status", json={"status": "voando"}, headers=auth["H"]).status_code == 422
    assert client.patch("/api/envios/999999/status", json={"status": "entregue"}, headers=auth["H"]).status_code == 404


def test_notificado_nao_regride_entregue(client, auth):
    eid = _criar(client, auth["H"], _cod(1)).json()["envios"][0]["_id"]
    client.patch(f"/api/envios/{eid}/status", json={"status": "entregue"}, headers=auth["H"])
    client.patch(f"/api/envios/{eid}/notificado", json={}, headers=auth["H"])
    alvo = next(e for e in client.get("/api/envios", headers=auth["H"]).json()["envios"] if e["_id"] == eid)
    assert alvo["status"] == "entregue"


def test_eventos_historico(client, auth):
    eid = _criar(client, auth["H"], _cod(1)).json()["envios"][0]["_id"]
    client.patch(f"/api/envios/{eid}/status", json={"status": "a_caminho"}, headers=auth["H"])
    d = client.get(f"/api/envios/{eid}/eventos", headers=auth["H"]).json()
    assert len(d["eventos"]) >= 1
    assert client.get("/api/envios/999999999/eventos", headers=auth["H"]).json() == {"eventos": []}


# ------------------------------------------------------------------- lixeira

def test_lixeira_fluxo_completo(client, auth):
    eid = _criar(client, auth["H"], _cod(1)).json()["envios"][0]["_id"]
    assert client.delete(f"/api/envios/{eid}", headers=auth["H"]).json()["message"] == "Envio movido para lixeira"
    assert client.get("/api/envios", headers=auth["H"]).json()["total"] == 0
    lix = client.get("/api/envios", params={"status": "excluido"}, headers=auth["H"]).json()
    assert lix["total"] == 1 and lix["envios"][0]["_id"] == eid
    r = client.post(f"/api/envios/{eid}/restaurar", headers=auth["H"])
    assert r.status_code == 200 and r.json()["message"] == "Envio restaurado como pendente"
    assert client.get("/api/envios", headers=auth["H"]).json()["total"] == 1
    client.delete(f"/api/envios/{eid}", headers=auth["H"])
    r = client.delete(f"/api/envios/{eid}/purga", headers=auth["H"])
    assert r.json()["message"] == "Envio removido permanentemente"
    assert client.get("/api/envios", params={"status": "excluido"}, headers=auth["H"]).json()["total"] == 0


def test_lixeira_permissoes(client, auth):
    """v28: ha um unico usuario (o admin) — restaurar/purgar exigem token de admin."""
    eid = _criar(client, auth["H"], _cod(1)).json()["envios"][0]["_id"]
    assert client.post(f"/api/envios/{eid}/restaurar").status_code == 401
    assert client.delete(f"/api/envios/{eid}/purga").status_code == 401
    client.delete(f"/api/envios/{eid}", headers=auth["H"])
    assert client.post(f"/api/envios/{eid}/restaurar", headers=auth["H"]).status_code == 200


def test_delete_inexistente_404(client, auth):
    assert client.delete("/api/envios/999999", headers=auth["H"]).status_code == 404


# ---------------------------------------------- estatisticas / backup / auth

def test_estatisticas(client, auth):
    _criar(client, auth["H"], _cod(1))
    eid = _criar(client, auth["H"], _cod(2)).json()["envios"][0]["_id"]
    client.patch(f"/api/envios/{eid}/status", json={"status": "entregue"}, headers=auth["H"])
    d = client.get("/api/estatisticas", headers=auth["H"]).json()
    assert d["total"] == 2 and d["entregue"] == 1 and d["pendente"] == 1


def test_backup_so_admin(client, auth):
    assert client.get("/api/backup").status_code == 401
    r = client.get("/api/backup", headers=auth["H"])
    assert r.status_code == 200 and len(r.content) > 0
    assert "backup-rastreio" in r.headers.get("content-disposition", "")


def test_rotas_de_dados_exigem_token(client, auth):
    assert client.get("/api/envios").status_code == 401
    assert client.get("/api/estatisticas").status_code == 401
    assert client.post("/api/envios",
                       json={"destinatario": "x", "codigo": _cod(1), "email": "x@t.com"}).status_code == 401


# --------------------------------------------------------------- notificacoes

def test_notificacao_whatsapp_fallback(client, auth):
    _criar(client, auth["H"], _cod(1))
    d = client.post("/api/notificacoes", json={"codigo": _cod(1), "canal": "whatsapp"}, headers=auth["H"]).json()
    assert d["success"] is False and d["fallback"] is True


def test_notificacao_email_sem_smtp_fallback(client, auth):
    _criar(client, auth["H"], _cod(1))
    d = client.post("/api/notificacoes", json={"codigo": _cod(1), "canal": "email"}, headers=auth["H"]).json()
    assert d["success"] is False and d["fallback"] is True


def test_notificacao_codigo_inexistente_404(client, auth):
    assert client.post("/api/notificacoes",
                       json={"codigo": _cod(7), "canal": "email"}, headers=auth["H"]).status_code == 404


def test_notificacao_massa_sem_smtp_422(client, auth):
    assert client.post("/api/notificacoes/massa", json={"canal": "email"}, headers=auth["H"]).status_code == 422
    assert client.post("/api/notificacoes/massa", json={"canal": "whatsapp"}, headers=auth["H"]).status_code == 422


# ------------------------------------------------------------------- bordas

def test_payloads_malformados_nao_dao_500(client, auth):
    H = {**auth["H"], "Content-Type": "application/json"}
    assert client.post("/api/envios", content=b'{"destinatario": ', headers=H).status_code != 500
    assert client.post("/api/envios", content=b"destinatario=x",
                       headers={**auth["H"], "Content-Type": "text/plain"}).status_code != 500
    assert client.post("/api/auth/login", content=b'{"email": 123}', headers=H).status_code != 500
