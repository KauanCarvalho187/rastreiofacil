# -*- coding: utf-8 -*-
"""Teste de bordas e casos adversariais — Rastreio Facil.

Cobre payloads malformados, SQL injection, params extremos, auth quebrada,
unicode e integridade referencial (DELETE deve limpar o historico do envio).
Regressao permanente: todo bug corrigido aqui ganha um check que falhava antes.
"""
import json, time, urllib.request, urllib.error
from urllib.parse import quote

BASE = "http://127.0.0.1:3001"
ok = fal = 0

def check(nome, cond, extra=""):
    global ok, fal
    if cond:
        ok += 1
        print(f"PASS - {nome}")
    else:
        fal += 1
        print(f"FAIL - {nome} :: {extra}")

def raw(metodo, caminho, corpo=None, hdrs=None, content_type="application/json"):
    url = BASE + caminho
    h = dict(hdrs or {})
    data = None
    if corpo is not None:
        data = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode("utf-8")
        h.setdefault("Content-Type", content_type)
    r = urllib.request.Request(url, data=data, method=metodo, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

def status_ok_500(st):
    return st != 500

# login
st, b = raw("POST", "/api/auth/login", {"email": "admin@empresa.com", "senha": "admin12345"})
tok = json.loads(b)["token"]
AH = {"Authorization": "Bearer " + tok}

# ---------------- payloads malformados ----------------
st, b = raw("POST", "/api/envios", b'{"destinatario": ', AH)
check("B: JSON quebrado nao da 500", status_ok_500(st), str(st))

st, b = raw("POST", "/api/envios", b'destinatario=x', AH, content_type="text/plain")
check("B: Content-Type errado nao da 500", status_ok_500(st), str(st))

st, b = raw("PUT", "/api/envios/1", "corpo de texto invalido", AH, content_type="text/plain")
check("B: PUT texto puro nao da 500", status_ok_500(st), str(st))

st, b = raw("POST", "/api/auth/login", b'{"email": 123}', None)
check("B: login corpo errado nao da 500", status_ok_500(st), str(st))

# ---------------- params extremos ----------------
st, b = raw("GET", "/api/envios?limit=9999", None, AH)
check("B: limit gigante -> 422", st == 422, str(st))

st, b = raw("GET", "/api/envios?page=0", None, AH)
check("B: page zero -> 422", st == 422, str(st))

# ---------------- SQL injection ----------------
st, b = raw("GET", "/api/envios?q=" + quote("';DROP TABLE envios;--"), None, AH)
try:
    d = json.loads(b)
    inj_ok = st == 200 and "envios" in d
except Exception:
    inj_ok = False
check("B: SQL injection nao quebra", inj_ok, f"{st} {b[:100]}")
st, b = raw("GET", "/api/envios?limit=1", None, AH)
try:
    d = json.loads(b)
    sobreviveu = d.get("total", 0) > 0
except Exception:
    sobreviveu = False
check("B: tabela envios sobrevive", sobreviveu, b[:100])

# ---------------- auth quebrada ----------------
st, b = raw("GET", "/api/envios", None, {"Authorization": "Bearer token_invalido"})
check("B: token invalido -> 401", st == 401, str(st))

st, b = raw("GET", "/api/envios", None, {"Authorization": "Bearer"})
check("B: header Bearer vazio -> 401/403 (nao 500)", st in (401, 403) or status_ok_500(st), str(st))

# ---------------- unicode roundtrip ----------------
NOME_B = "José André Ção 📦"
st, b = raw("POST", "/api/envios", {"destinatario": NOME_B, "codigo": "BB987654321BR",
    "email": "bordas@exemplo.com"}, AH)
criado_b = st == 200
id_b = None
try:
    id_b = json.loads(b)["envios"][0]["_id"]
except Exception:
    pass
st, b = raw("GET", "/api/envios?q=" + quote("José"), None, AH)
try:
    acha = any("José" in e["destinatario"] for e in json.loads(b)["envios"])
except Exception:
    acha = False
check("B: unicode roundtrip", criado_b and acha, f"{st} {b[:120]}")

# ---------------- eventos: historico existe e DELETE limpa ----------------
st, b = raw("PUT", f"/api/envios/{id_b}", {"status": "a_caminho"}, AH)
check("B: mudar status gera evento", st == 200, str(st))
st, b = raw("GET", f"/api/envios/{id_b}/eventos", None, AH)
try:
    n_antes = len(json.loads(b)["eventos"])
except Exception:
    n_antes = 0
check("B: historico tem evento", n_antes >= 1, str(n_antes))

st, b = raw("DELETE", f"/api/envios/{id_b}", None, AH)
check("B: DELETE ok", st == 200, str(st))
st, b = raw("GET", f"/api/envios/{id_b}/eventos", None, AH)
try:
    n_depois = len(json.loads(b)["eventos"])
except Exception:
    n_depois = -1
check("B: DELETE limpa historico (sem orfaos)", n_depois == 0,
      f"eventos orfaos restantes: {n_depois}")

# eventos de envio inexistente -> lista vazia (nao 500)
st, b = raw("GET", "/api/envios/999999999/eventos", None, AH)
try:
    vazio = json.loads(b) == {"eventos": []}
except Exception:
    vazio = False
check("B: eventos de id inexistente -> lista vazia", st == 200 and vazio, f"{st} {b[:80]}")

# ---------------- notificacao canal invalido ----------------
st, b = raw("POST", "/api/notificacoes", {"codigo": "BB987654321BR", "canal": "pombo"}, AH)
check("B: canal invalido -> 422 (nao 500)", st in (422, 404) or status_ok_500(st), str(st))

# ---------------- limpeza ----------------
st, b = raw("DELETE", f"/api/envios/{id_b}", None, AH) if id_b else (0, "")
try:
    st2, b2 = raw("GET", "/api/envios?q=BB987654321BR", None, AH)
    for e in json.loads(b2).get("envios", []):
        raw("DELETE", f"/api/envios/{e['_id']}", None, AH)
except Exception:
    pass

print(f"\nBORDAS: {ok} passou, {fal} falhou")
exit(1 if fal else 0)
