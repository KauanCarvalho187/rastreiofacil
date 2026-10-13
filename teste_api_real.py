# -*- coding: utf-8 -*-
"""Teste completo CONTRA O SERVIDOR REAL (porta 3001): login, 4 cadastros,
edicoes, exclusao, busca, estatisticas, historico, logout. Uso: python teste_api_real.py"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:3001"
P = 0
F = 0

def check(nome, cond, detalhe=""):
    global P, F
    if cond:
        P += 1; print(f"PASS - {nome}", flush=True)
    else:
        F += 1; print(f"FAIL - {nome} {detalhe}", flush=True)

def req(metodo, caminho, dados=None, token=None):
    url = BASE + caminho
    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    r = urllib.request.Request(url, data=corpo, method=metodo)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"erro": str(e)}

def req_raw(metodo, caminho, token=None):
    """Requisicao bruta (nao interpreta JSON) — usada para baixar o backup .db."""
    r = urllib.request.Request(BASE + caminho, method=metodo)
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, len(resp.read()), resp.headers.get("Content-Disposition", "")
    except urllib.error.HTTPError as e:
        return e.code, 0, ""
    except Exception:
        return 0, 0, ""

def main():
    # 0. saude
    st, d = req("GET", "/api/health")
    check("servidor no ar", st == 200 and d.get("ok") is True, f"st={st}")
    st, d = req("GET", "/api/versao")
    check("versao 27", d.get("versao") == "27", str(d))

    # 1. login admin
    st, d = req("POST", "/api/auth/login", {"email": "admin@empresa.com", "senha": "admin12345"})
    check("login admin", st == 200 and "token" in d, f"st={st} {d}")
    tok = d.get("token", "")

    # 2. cadastra 4 pessoas
    pessoas = [
        {"destinatario": "Fulano Um", "codigo": "FU123456789BR", "celular": "(11) 98888-7777", "email": "fulano1@t.com", "descricao": "Pedido API 1", "status": "pendente"},
        {"destinatario": "Fulano Dois", "codigo": "FD223456789BR", "celular": "(21) 97777-6666", "email": "fulano2@t.com", "descricao": "Pedido API 2", "status": "pendente"},
        {"destinatario": "Fulano Tres", "codigo": "FT323456789BR", "celular": "(31) 96666-5555", "email": "fulano3@t.com", "descricao": "Pedido API 3", "status": "a_caminho"},
        {"destinatario": "Fulano Quatro", "codigo": "FQ423456789BR", "celular": "(41) 95555-4444", "email": "fulano4@t.com", "descricao": "Pedido API 4", "status": "pendente"},
    ]
    st, d = req("POST", "/api/envios", {"envios": pessoas}, tok)
    criados = d.get("envios", [])
    check("4 cadastros criados", st == 200 and len(criados) == 4, f"st={st} n={len(criados)} {d}")
    ids = {e.get("codigo"): e.get("_id") for e in criados}
    st, d = req("GET", "/api/envios", token=tok)
    total0 = d.get("total", 0)
    check("total apos cadastro = 4 + anteriores", total0 >= 4, str(total0))

    # 3. validacao: codigo invalido rejeitado
    st, d = req("POST", "/api/envios", {"destinatario": "X", "codigo": "XYZ", "email": "x@t.com"}, tok)
    check("codigo invalido rejeitado (422)", st == 422, f"st={st}")

    # 4. duplicado: mesmo codigo de novo
    st, d = req("POST", "/api/envios", {"envios": [{"destinatario": "Dup", "codigo": "FU123456789BR", "email": "dup@t.com"}]}, tok)
    check("codigo duplicado tratado", st in (200, 409) and (st == 409 or d.get("erros")), f"st={st} {d}")

    # 5. edita 2
    id1 = ids.get("FU123456789BR")
    st, d = req("PUT", f"/api/envios/{id1}", {"descricao": "Pedido API 1 EDITADO", "celular": "(11) 90000-1111"}, tok)
    check("edicao 1 (PUT)", st == 200 and "EDITADO" in str(d.get("descricao", "")), f"st={st} {d}")
    id2 = ids.get("FD223456789BR")
    st, d = req("PATCH", f"/api/envios/{id2}/status", {"status": "entregue"}, tok)
    check("edicao 2 (status -> entregue)", st == 200 and d.get("status") == "entregue", f"st={st} {d}")

    # 6. busca server-side
    st, d = req("GET", "/api/envios?q=Fulano%20Tres", token=tok)
    check("busca server-side", st == 200 and len(d.get("envios", [])) == 1, f"n={len(d.get('envios', []))}")

    # 7. paginacao
    st, d = req("GET", "/api/envios?limit=2&page=1", token=tok)
    check("paginacao limit=2", st == 200 and len(d.get("envios", [])) == 2 and d.get("total", 0) >= 4, f"{d.get('total')} / {len(d.get('envios', []))}")

    # 8. estatisticas
    st, d = req("GET", "/api/estatisticas", token=tok)
    check("estatisticas total coerente", st == 200 and d.get("total", 0) >= 4 and d.get("entregue", 0) >= 1, str(d))

    # 9. historico da edicao de status
    st, d = req("GET", f"/api/envios/{id2}/eventos", token=tok)
    check("historico gravado", st == 200 and len(d.get("eventos", [])) >= 1, str(d))

    # 10. exclui 1 (soft delete -> lixeira)
    id4 = ids.get("FQ423456789BR")
    st, d = req("DELETE", f"/api/envios/{id4}", token=tok)
    check("exclusao (soft delete)", st == 200 and d.get("message") == "Envio movido para lixeira", f"st={st} {d}")
    st, d = req("GET", "/api/envios", token=tok)
    check("total -1 apos exclusao (default exclui lixeira)", d.get("total") == total0 - 1, f"{d.get('total')} vs {total0 - 1}")
    st, d = req("GET", "/api/envios?status=excluido", token=tok)
    check("lixeira tem o item excluido", st == 200 and d.get("total") == 1 and d.get("envios", [])[0].get("_id") == id4, f"st={st} {d}")
    # restaurar
    st, d = req("POST", f"/api/envios/{id4}/restaurar", token=tok)
    check("restaurar da lixeira", st == 200 and d.get("message", "").startswith("Envio restaurado"), f"st={st} {d}")
    st, d = req("GET", "/api/envios", token=tok)
    check("total volta apos restaurar", d.get("total") == total0, f"{d.get('total')} vs {total0}")
    # soft delete novamente para poder purgar
    st, d = req("DELETE", f"/api/envios/{id4}", token=tok)
    check("exclusao novamente para purga", st == 200 and d.get("message") == "Envio movido para lixeira", f"st={st} {d}")
    # purge (hard delete) - apenas admin
    st, d = req("DELETE", f"/api/envios/{id4}/purga", token=tok)
    check("purga definitiva", st == 200 and d.get("message") == "Envio removido permanentemente", f"st={st} {d}")
    st, d = req("GET", "/api/envios", token=tok)
    check("total -1 apos purga", d.get("total") == total0 - 1, f"{d.get('total')} vs {total0 - 1}")

    # 11. usuarios
    st, d = req("GET", "/api/usuarios", token=tok)
    check("listar usuarios", st == 200 and len(d.get("usuarios", [])) >= 1, f"st={st}")

    # 12. sem token -> 401
    st, d = req("GET", "/api/usuarios")
    check("sem token bloqueado (401)", st == 401, f"st={st}")

    # 12b. melhorias v22: estado admin + backup do banco
    st, d = req("GET", "/api/auth/estado", token=tok)
    check("estado auth informa admin=true", st == 200 and d.get("admin") is True, f"st={st} {d}")
    st, d = req("GET", "/api/auth/estado")
    check("estado auth sem token: admin=false", st == 200 and d.get("admin") is False, f"st={st} {d}")
    st, n, cd = req_raw("GET", "/api/backup", token=tok)
    check("backup admin baixa arquivo", st == 200 and n > 0 and "backup-rastreio" in cd, f"st={st} n={n} cd={cd}")
    st, n, cd = req_raw("GET", "/api/backup")
    check("backup sem token bloqueado (401)", st == 401, f"st={st}")

    # 13. logout revoga token
    st, d = req("POST", "/api/auth/logout", {}, tok)
    check("logout", st == 200, f"st={st}")
    st, d = req("GET", "/api/estatisticas", token=tok)
    check("token revogado (401)", st == 401, f"st={st}")

    print(f"\nAPI REAL: {P} passou, {F} falhou", flush=True)
    return F

if __name__ == "__main__":
    import sys
    sys.exit(1 if main() else 0)
