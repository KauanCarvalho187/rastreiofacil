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
import time
NOME_B = "José André Ção 📦"
codigo_b = "BB" + str(int(time.time()*1000)%1000000000).zfill(9) + "BR"
st, b = raw("POST", "/api/envios", {"destinatario": NOME_B, "codigo": codigo_b,
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

# ---------------- eventos: historico existe e DELETE (soft) mantem ----------------
st, b = raw("PUT", f"/api/envios/{id_b}", {"status": "a_caminho"}, AH)
check("B: mudar status gera evento", st == 200, str(st))
st, b = raw("GET", f"/api/envios/{id_b}/eventos", None, AH)
try:
    n_antes = len(json.loads(b)["eventos"])
except Exception:
    n_antes = 0
check("B: historico tem evento", n_antes >= 1, str(n_antes))

# Soft delete: move to lixeira, KEEPS events (audit trail)
st, b = raw("DELETE", f"/api/envios/{id_b}", None, AH)
check("B: DELETE ok (soft -> lixeira)", st == 200 and json.loads(b).get("message") == "Envio movido para lixeira", str(st))
st, b = raw("GET", f"/api/envios/{id_b}/eventos", None, AH)
try:
    n_depois_soft = len(json.loads(b)["eventos"])
except Exception:
    n_depois_soft = -1
# Soft delete cria evento "Movido para lixeira", então total = n_antes + 1
check("B: soft DELETE MANTÉM historico (auditoria) + cria evento lixeira", n_depois_soft == n_antes + 1 and n_antes >= 1,
      f"antes={n_antes} depois={n_depois_soft}")

# Verifica que está na lixeira
st, b = raw("GET", "/api/envios?status=excluido&q=" + quote("José"), None, AH)
try:
    na_lixeira = any(e["_id"] == id_b for e in json.loads(b)["envios"])
except Exception:
    na_lixeira = False
check("B: item soft-deletado aparece na lixeira", na_lixeira, f"{st} {b[:80]}")

# Restaurar da lixeira
st, b = raw("POST", f"/api/envios/{id_b}/restaurar", None, AH)
check("B: restaurar da lixeira", st == 200 and "restaurado" in json.loads(b).get("message", ""), f"{st} {b[:80]}")

# Para purgar, precisa estar na lixeira: soft delete novamente
st, b = raw("DELETE", f"/api/envios/{id_b}", None, AH)
check("B: soft delete novamente para purga", st == 200 and json.loads(b).get("message") == "Envio movido para lixeira", f"{st} {b[:80]}")

# Purga (hard delete) - remove eventos
st, b = raw("DELETE", f"/api/envios/{id_b}/purga", None, AH)
check("B: PURGA definitiva", st == 200 and json.loads(b).get("message") == "Envio removido permanentemente", f"{st} {b[:80]}")
st, b = raw("GET", f"/api/envios/{id_b}/eventos", None, AH)
try:
    n_depois_purga = len(json.loads(b)["eventos"])
except Exception:
    n_depois_purga = -1
check("B: PURGA limpa historico (sem orfaos)", n_depois_purga == 0,
      f"eventos orfaos restantes: {n_depois_purga}")

# ================= PERMISSÕES LIXEIRA: usuário apaga, admin restaura =================
# Cria outro item de teste para testar permissões
import time
NOME_PERM = "Teste Permissao Lixeira"
codigo_perm = "PP" + str(int(time.time()*1000)%1000000000).zfill(9) + "BR"
st, b = raw("POST", "/api/envios", {"destinatario": NOME_PERM, "codigo": codigo_perm,
    "email": "perm@teste.com"}, AH)
criado_perm = st == 200
id_perm = None
try:
    id_perm = json.loads(b)["envios"][0]["_id"]
except Exception:
    pass

# Login do usuário comum (joao)
st, b = raw("POST", "/api/auth/login", {"email": "joao@empresa.com", "senha": "joao12345"})
joao_tok = json.loads(b)["token"] if st == 200 else None
AH_JOAO = {"Authorization": "Bearer " + joao_tok} if joao_tok else None

# Login do usuário comum (maria)
st, b = raw("POST", "/api/auth/login", {"email": "maria@empresa.com", "senha": "maria12345"})
maria_tok = json.loads(b)["token"] if st == 200 else None
AH_MARIA = {"Authorization": "Bearer " + maria_tok} if maria_tok else None

if criado_perm and id_perm and AH_JOAO and AH_MARIA:
    # 1. Usuário comum (João) APAGA o envio (soft delete) - DEVE FUNCIONAR
    st, b = raw("DELETE", f"/api/envios/{id_perm}", None, AH_JOAO)
    check("B: user comum PODE apagar (soft delete)", st == 200 and json.loads(b).get("message") == "Envio movido para lixeira", f"{st} {b[:80]}")
    
    # 2. Mesmo usuário (João) tenta RESTAURAR - DEVE FALHAR (403)
    st, b = raw("POST", f"/api/envios/{id_perm}/restaurar", None, AH_JOAO)
    check("B: user comum NÃO PODE restaurar (403)", st == 403, f"{st} {b[:80]}")
    
    # 3. Outro usuário comum (Maria) tenta RESTAURAR - DEVE FALHAR (403)
    st, b = raw("POST", f"/api/envios/{id_perm}/restaurar", None, AH_MARIA)
    check("B: outro user comum NÃO PODE restaurar (403)", st == 403, f"{st} {b[:80]}")
    
    # 4. User comum tenta PURGAR - DEVE FALHAR (403)
    st, b = raw("DELETE", f"/api/envios/{id_perm}/purga", None, AH_JOAO)
    check("B: user comum NÃO PODE purgar (403)", st == 403, f"{st} {b[:80]}")
    
    # 5. Admin RESTAURA - DEVE FUNCIONAR
    st, b = raw("POST", f"/api/envios/{id_perm}/restaurar", None, AH)
    check("B: admin PODE restaurar", st == 200 and "restaurado" in json.loads(b).get("message", ""), f"{st} {b[:80]}")
    
    # 6. Item deve voltar à lista normal
    st, b = raw("GET", "/api/envios?q=" + quote("Teste Permissao"), None, AH)
    try:
        voltou = any(e["_id"] == id_perm for e in json.loads(b)["envios"])
    except Exception:
        voltou = False
    check("B: item restaurado aparece na lista normal", voltou, f"{st} {b[:80]}")
    
    # 7. Apaga novamente (admin) para poder purgar
    st, b = raw("DELETE", f"/api/envios/{id_perm}", None, AH)
    # 8. Admin PURGA - DEVE FUNCIONAR
    st, b = raw("DELETE", f"/api/envios/{id_perm}/purga", None, AH)
    check("B: admin PODE purgar", st == 200 and json.loads(b).get("message") == "Envio removido permanentemente", f"{st} {b[:80]}")
    
    # 9. Verifica que sumiu de tudo
    st, b = raw("GET", "/api/envios?q=" + quote("Teste Permissao"), None, AH)
    try:
        sumiu = not any(e["_id"] == id_perm for e in json.loads(b)["envios"])
    except Exception:
        sumiu = False
    check("B: item purgado sumiu da lista", sumiu, f"{st} {b[:80]}")

else:
    check("B: setup permissões lixeira (login users)", False, "falhou criar item ou login users")

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
# id_b já foi purgado acima

print(f"\nBORDAS: {ok} passou, {fal} falhou")
exit(1 if fal else 0)
