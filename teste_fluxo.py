# -*- coding: utf-8 -*-
"""E2E v20: cadastra 4, edita 2, exclui 1. Uso: python teste_fluxo.py"""
import asyncio, os, sys
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ["DB_PATH"] = os.path.join(BASE, "teste_e2e.db")
P = 0
F = 0
def check(nome, cond, detalhe=""):
    global P, F
    if cond:
        P += 1; print(f"PASS - {nome}")
    else:
        F += 1; print(f"FAIL - {nome} {detalhe}")
async def main():
    try:
        os.remove(os.path.join(BASE, "teste_e2e.db"))
    except OSError:
        pass
    import db
    db.DB_PATH = os.environ["DB_PATH"]
    await db.init_db()
    from httpx import AsyncClient, ASGITransport
    import main as appmod
    await appmod.init_db()
    t = ASGITransport(app=appmod.app)
    async with AsyncClient(transport=t, base_url="http://t") as c:
        r = await c.get("/api/auth/estado")
        check("estado sem usuarios", r.json().get("temUsuarios") is False, r.text)
        r = await c.post("/api/auth/registrar", json={"nome": "Admin", "email": "a@t.com", "senha": "12345678"})
        check("criar admin", r.status_code == 200, r.text)
        r = await c.post("/api/auth/login", json={"email": "a@t.com", "senha": "12345678"})
        check("login", r.status_code == 200 and "token" in r.json(), r.text)
        H = {"Authorization": "Bearer " + r.json()["token"]}
        pessoas = [
            {"destinatario": "Ana Souza", "codigo": "AA111111111BR", "celular": "11987654321", "email": "ana@t.com", "descricao": "P1"},
            {"destinatario": "Bruno Lima", "codigo": "BB222222222BR", "celular": "21976543210", "email": "bruno@t.com", "descricao": "P2"},
            {"destinatario": "Carla Reis", "codigo": "CC333333333BR", "celular": "31965432109", "email": "carla@t.com", "descricao": "P3"},
            {"destinatario": "Diego Alves", "codigo": "DD444444444BR", "celular": "41954321098", "email": "diego@t.com", "descricao": "P4"},
        ]
        r = await c.post("/api/envios", json={"envios": pessoas}, headers=H)
        check("cadastrar 4", len(r.json().get("envios", [])) == 4, r.text)
        ids = {e["codigo"]: e["_id"] for e in r.json()["envios"]}
        r = await c.put(f"/api/envios/{ids['AA111111111BR']}", json={"descricao": "P1 EDITADO"}, headers=H)
        check("editar Ana", "EDITADO" in r.json().get("descricao", ""), r.text)
        r = await c.patch(f"/api/envios/{ids['BB222222222BR']}/status", json={"status": "a_caminho"}, headers=H)
        check("status Bruno", r.json().get("status") == "a_caminho", r.text)
        r = await c.get("/api/estatisticas", headers=H)
        check("estatisticas total 4", r.json().get("total") == 4, r.text)
        r = await c.get("/api/envios", params={"q": "Bruno"}, headers=H)
        check("busca Bruno", len(r.json().get("envios", [])) == 1, r.text)
        r = await c.delete(f"/api/envios/{ids['DD444444444BR']}", headers=H)
        check("excluir Diego", r.status_code == 200, r.text)
        r = await c.get("/api/envios", headers=H)
        check("restam 3", r.json().get("total") == 3, r.text)
        r = await c.get("/api/usuarios", headers=H)
        check("listar usuarios", r.status_code == 200, r.text)
        r = await c.post("/api/auth/logout", headers=H)
        check("logout", r.status_code == 200, r.text)
        r = await c.get("/api/versao")
        check("versao 22", r.json().get("versao") == "22", r.text)
    print(f"E2E: {P} passou, {F} falhou")
    try:
        os.remove(os.path.join(BASE, "teste_e2e.db"))
    except OSError:
        pass
    sys.exit(0 if F == 0 else 1)
if __name__ == "__main__":
    asyncio.run(main())
