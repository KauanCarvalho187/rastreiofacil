# -*- coding: utf-8 -*-
"""CRUD exaustivo da API: Create/Read/Update/Delete + validacoes + bordas + auth."""
import urllib.request, urllib.error, json

BASE = "http://127.0.0.1:3001"
P = F = 0
def check(nome, cond, detalhe=""):
    global P, F
    if cond: P += 1; print(f"PASS - {nome}", flush=True)
    else: F += 1; print(f"FAIL - {nome} :: {detalhe}", flush=True)

def api(metodo, caminho, corpo=None, token=None, raw=None):
    data = raw if raw is not None else (json.dumps(corpo).encode() if corpo is not None else None)
    req = urllib.request.Request(BASE + caminho, method=metodo, data=data)
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            b = r.read().decode()
            return r.status, (json.loads(b) if b else {})
    except urllib.error.HTTPError as e:
        b = e.read().decode()
        return e.code, (json.loads(b) if b else {})

criados = []  # ids criados neste teste (limpeza no final)
def criar(cod, nome="CRUD Teste", fone="11911112222", mail="crud@t.com", desc="x", status="pendente"):
    st, d = api("POST", "/api/envios", {"destinatario": nome, "codigo": cod,
        "celular": fone, "email": mail, "descricao": desc, "status": status}, tok)
    ids = [e["_id"] for e in d.get("envios", [])]
    criados.extend(ids)
    return st, d

# ---------- AUTH ----------
st, d = api("POST", "/api/envios", {"destinatario": "X", "codigo": "XX111111111BR", "email": "x@t.com"})
check("CRUD exige login (401 sem token)", st == 401, f"st={st} {d}")

_, tok_d = api("POST", "/api/auth/login", {"email": "admin@empresa.com", "senha": "admin12345"})
tok = tok_d.get("token", "")
check("login", bool(tok))

# ---------- CREATE ----------
st, d = criar("CR111111111BR")
check("C: create simples", st == 200 and len(d.get("envios", [])) == 1 and "objeto=CR111111111BR" in d["envios"][0].get("link", ""), str(d)[:150])
id1 = criados[-1] if criados else None

st, d = api("POST", "/api/envios", {"envios": [
    {"destinatario": "Lote A", "codigo": "CR222222222BR", "celular": "21911113333", "email": "a@t.com"},
    {"destinatario": "Lote B", "codigo": "CR333333333BR", "celular": "31911114444", "email": "b@t.com"}]}, tok)
check("C: create em lote (2 itens)", st == 200 and len(d.get("envios", [])) == 2, str(d)[:150])
id2 = d["envios"][0]["_id"] if d.get("envios") else None
criados.extend([e["_id"] for e in d.get("envios", []) if e["_id"] != id2])

st, d = api("POST", "/api/envios", {"envios": [
    {"destinatario": "Valido", "codigo": "CR444444444BR", "email": "v@t.com"},
    {"destinatario": "Invalido", "codigo": "ERRADO", "email": "i@t.com"}]}, tok)
novo = [e["_id"] for e in d.get("envios", [])]
criados.extend(novo)
check("C: lote parcial (1 valido + 1 erro detalhado)", st == 200 and len(novo) == 1 and len(d.get("erros", [])) == 1 and "inválido" in d["erros"][0], str(d)[:200])

st, d = api("POST", "/api/envios", {"destinatario": "Dup", "codigo": "CR111111111BR", "email": "d@t.com"}, tok)
check("C: codigo duplicado nao cria de novo", st == 200 and len(d.get("envios", [])) == 0 and any("já cadastrado" in e for e in d.get("erros", [])), str(d)[:180])

st, d = api("POST", "/api/envios", {"destinatario": "SemContato", "codigo": "CR555555555BR"}, tok)
check("C: sem e-mail nem celular = 422", st == 422, f"st={st}")

st, d = api("POST", "/api/envios", None, tok, raw=b"[1,2]")
check("C: corpo nao-dict = 422", st == 422, f"st={st} {d}")

st, d = api("POST", "/api/envios", {"envios": [{"destinatario": "Big", "codigo": f"CR{i:09d}BR", "email": "big@t.com"} for i in range(501)]}, tok)
check("C: lote >500 = 422", st == 422, f"st={st}")

# ---------- READ ----------
st, d = api("GET", "/api/envios?limit=500", None, tok)
cods = [e["codigo"] for e in d.get("envios", [])]
check("R: lista geral ve os criados", st == 200 and "CR111111111BR" in cods and "CR444444444BR" in cods, str(cods)[:150])
check("R: total coerente", d.get("total", 0) >= 4, str(d.get("total")))

st, d = api("GET", "/api/envios?q=Lote", None, tok)
check("R: busca q filtra", st == 200 and len(d.get("envios", [])) == 2 and all("Lote" in e["destinatario"] for e in d["envios"]), str([e['destinatario'] for e in d.get('envios', [])]))

st, d = api("GET", "/api/envios?status=entregue&limit=500", None, tok)
check("R: filtro status", st == 200 and all(e["status"] == "entregue" for e in d.get("envios", [])), "")

st, d = api("GET", "/api/envios?page=1&limit=2", None, tok)
check("R: paginacao limit=2", st == 200 and len(d.get("envios", [])) <= 2 and "total" in d, f"n={len(d.get('envios', []))}")

# ---------- UPDATE ----------
st, d = api("PUT", f"/api/envios/{id1}", {"destinatario": "CRUD Editado", "codigo": "CR999999999BR",
    "celular": "11999998888", "email": "edit@t.com", "descricao": "editado ok"}, tok)
check("U: PUT edita todos campos", st == 200 and d.get("destinatario") == "CRUD Editado" and d.get("codigo") == "CR999999999BR"
      and d.get("email") == "edit@t.com" and "objeto=CR999999999BR" in d.get("link", ""), str(d)[:200])

st, d = api("PUT", f"/api/envios/{id1}", {"destinatario": "   "}, tok)
check("U: destinatario vazio = 422", st == 422, f"st={st}")

st, d = api("PUT", f"/api/envios/{id1}", {"email": "", "celular": ""}, tok)
check("U: remover todos contatos = 422", st == 422, f"st={st}")

st, d = api("PUT", f"/api/envios/{id1}", {"codigo": "INVALIDO"}, tok)
check("U: codigo invalido = 422", st == 422, f"st={st} {d}")

st, d = api("PUT", f"/api/envios/{id1}", {"codigo": "CR222222222BR"}, tok)
check("U: codigo de outro envio = 409", st == 409, f"st={st} {d}")

st, d = api("PUT", "/api/envios/999999", {"destinatario": "Fantasma"}, tok)
check("U: PUT id inexistente = 404", st == 404, f"st={st}")

st, d = api("PUT", f"/api/envios/{id1}", {"status": "entregue"}, tok)
check("U: PUT com status inline", st == 200 and d.get("status") == "entregue" and d.get("notificado") is True, str(d.get('status')))

st, d = api("PATCH", f"/api/envios/{id2}/status", {"status": "a_caminho"}, tok)
check("U: PATCH status muda e registra", st == 200 and d.get("status") == "a_caminho", str(d)[:150])

st, d = api("PATCH", f"/api/envios/{id2}/status", {"status": "voando"}, tok)
check("U: PATCH status invalido = 422", st == 422, f"st={st}")

st, d = api("PATCH", f"/api/envios/{id1}/notificado", {}, tok)
check("U: notificado nao regride entregue", st == 200, f"st={st} {d}")
st, d = api("GET", f"/api/envios?q=CR999999999BR", None, tok)
alvo = next((e for e in d.get("envios", []) if e["_id"] == id1), None)
check("U: entregue continua entregue", alvo and alvo["status"] == "entregue", str(alvo and alvo["status"]))

st, d = api("PATCH", f"/api/envios/999999/status", {"status": "entregue"}, tok)
check("U: PATCH id inexistente = 404", st == 404, f"st={st}")

# ---------- DELETE ----------
st, d = api("DELETE", f"/api/envios/{id1}", None, tok)
check("D: delete existe", st == 200, f"st={st} {d}")
st, d = api("DELETE", f"/api/envios/{id1}", None, tok)
check("D: delete duas vezes = 404", st == 404, f"st={st}")
st, d = api("GET", "/api/envios?limit=500", None, tok)
resta = [e["_id"] for e in d.get("envios", []) if e["_id"] in criados]
check("D: removido da listagem", id1 not in resta, str(resta)[:120])

# ---------- LIMPEZA ----------
sobra = [i for i in set(criados) if i != id1] + ([id2] if id2 else [])
for i in sobra:
    api("DELETE", f"/api/envios/{i}", None, tok)
st, d = api("GET", "/api/envios?limit=500", None, tok)
lixo = [e["codigo"] for e in d.get("envios", []) if str(e["codigo"]).startswith("CR")]
check("limpeza: nada CR* sobrou", not lixo, str(lixo))

print(f"\nCRUD: {P} passou, {F} falhou")

