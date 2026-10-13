# -*- coding: utf-8 -*-
"""Rastreio automatico: normalizacao da resposta do provedor + rota /api/envios/{id}/rastrear.
Usa banco temporario e provedor simulado (nao gasta cota da API nem toca no database.db)."""
import os, json, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "teste_rastreio.db")
os.environ["DATABASE_URL"] = ""
os.environ["RASTREIO_API_KEY"] = "chave-de-teste"

from fastapi.testclient import TestClient
import rastreio
import main

P = F = 0
def check(nome, cond, detalhe=""):
    global P, F
    if cond: P += 1; print(f"PASS - {nome}", flush=True)
    else: F += 1; print(f"FAIL - {nome} {detalhe}", flush=True)

def correios(*eventos):
    return {"carrier": "CARRIER_CORREIOS", "json": json.dumps({"codObjeto": "AA123456789BR", "eventos": list(eventos)})}

EV_POSTADO = {"descricao": "Objeto postado", "dtHrCriado": {"date": "2026-10-01 09:15:00.000000", "timezone": "America/Sao_Paulo"},
              "unidade": {"tipo": "Agência dos Correios", "endereco": {"cidade": "SAO PAULO", "uf": "SP"}}}
EV_TRANSITO = {"descricao": "Objeto em transferência - por favor aguarde", "dtHrCriado": "2026-10-02T14:30:00",
               "unidade": {"tipo": "Unidade de Tratamento", "endereco": {"cidade": "CAJAMAR", "uf": "SP"}},
               "unidadeDestino": {"tipo": "Unidade de Distribuição", "endereco": {"cidade": "RECIFE", "uf": "PE"}}}
EV_SAIU = {"descricao": "Objeto saiu para entrega ao destinatário", "dtHrCriado": "2026-10-04T08:00:00"}
EV_ENTREGUE = {"descricao": "Objeto entregue ao destinatário", "dtHrCriado": "2026-10-04T15:42:00"}

# ---- normalizacao ----
n = rastreio.normalizar(correios(EV_POSTADO, EV_TRANSITO))
check("normaliza: 2 eventos, mais recente primeiro", [e["descricao"] for e in n["eventos"]][0].startswith("Objeto em transfer"), str(n))
check("normaliza: data nos dois formatos", [e["data"] for e in n["eventos"]] == ["2026-10-02 14:30", "2026-10-01 09:15"], str(n["eventos"]))
check("normaliza: local e destino", n["eventos"][0]["local"] == "Unidade de Tratamento — CAJAMAR/SP" and n["eventos"][0]["destino"].endswith("RECIFE/PE"), str(n["eventos"][0]))
check("situacao em_transito", n["situacao"] == "em_transito")
check("'saiu para entrega' NAO e entregue", rastreio.normalizar(correios(EV_POSTADO, EV_SAIU))["situacao"] == "em_transito")
check("situacao entregue", rastreio.normalizar(correios(EV_POSTADO, EV_SAIU, EV_ENTREGUE))["situacao"] == "entregue")
check("sem eventos", rastreio.normalizar(correios())["situacao"] == "sem_eventos")
n = rastreio.normalizar({"json": json.dumps({"mensagem": "SRO-020: Objeto não encontrado na base de dados dos Correios."})})
check("objeto nao encontrado: mensagem repassada", n["situacao"] == "sem_eventos" and "SRO-020" in n["mensagem"])
n = rastreio.normalizar({"carrier": "CARRIER_CAINIAO", "json": json.dumps({"module": [{"status": "DELIVERED", "detailList": [
    {"timeStr": "2026-10-03 10:00:00", "standerdDesc": "Delivered"}]}]})})
check("cainiao: detailList + status DELIVERED", n["situacao"] == "entregue" and n["eventos"][0]["descricao"] == "Delivered", str(n))
check("resposta lixo nao quebra", rastreio.normalizar({"json": "nao-e-json"})["situacao"] == "sem_eventos"
      and rastreio.normalizar({})["eventos"] == [])

# ---- rota ----
chamadas = []
resposta = {"valor": None, "erro": None}
async def falso_consultar(codigo):
    chamadas.append(codigo)
    if resposta["erro"]:
        raise rastreio.RastreioErro(resposta["erro"])
    return rastreio.normalizar(resposta["valor"])
rastreio.consultar = falso_consultar

with TestClient(main.app) as c:
    r = c.post("/api/envios", json={"destinatario": "Rastreio Teste", "codigo": "AA123456789BR", "email": "r@t.com", "status": "a_caminho"})
    eid = r.json()["envios"][0]["_id"]
    check("health informa rastreio configurado", c.get("/api/health").json().get("rastreio") is True)

    resposta["erro"] = "Rastreio indisponivel no momento"
    r = c.post(f"/api/envios/{eid}/rastrear", json={})
    check("provedor fora + sem cache -> 502 com mensagem", r.status_code == 502 and "indisponivel" in r.json().get("detail", ""), r.text)

    resposta.update(erro=None, valor=correios(EV_POSTADO, EV_TRANSITO))
    r = c.post(f"/api/envios/{eid}/rastrear", json={}); d = r.json()
    check("1a consulta: eventos, sem cache", r.status_code == 200 and len(d["eventos"]) == 2 and d["cache"] is False and d["situacao"] == "em_transito", r.text)
    check("em transito nao mexe no status", d["status"] == "a_caminho" and d["status_atualizado"] is False)

    antes = len(chamadas)
    d = c.post(f"/api/envios/{eid}/rastrear", json={}).json()
    check("2a consulta vem do cache (nao gasta cota)", d["cache"] is True and len(chamadas) == antes and len(d["eventos"]) == 2)

    resposta["erro"] = "Rastreio indisponivel no momento"
    d = c.post(f"/api/envios/{eid}/rastrear", json={"forcar": True}).json()
    check("forcar com provedor fora -> devolve cache + aviso", d.get("cache") is True and "indisponivel" in d.get("aviso", "") and len(d["eventos"]) == 2, str(d))

    resposta.update(erro=None, valor=correios(EV_POSTADO, EV_TRANSITO, EV_SAIU, EV_ENTREGUE))
    d = c.post(f"/api/envios/{eid}/rastrear", json={"forcar": True}).json()
    check("entregue: status do envio atualizado sozinho", d["situacao"] == "entregue" and d["status"] == "entregue" and d["status_atualizado"] is True, str(d))
    lst = c.get("/api/envios").json()["envios"]
    check("envio aparece como entregue na listagem", next(e for e in lst if e["_id"] == eid)["status"] == "entregue")
    ev = c.get(f"/api/envios/{eid}/eventos").json()["eventos"]
    check("historico registra 'rastreio automatico'", any(e["detalhe"] == "rastreio automatico" and e["para_status"] == "entregue" for e in ev), str(ev))

    antes = len(chamadas)
    d = c.post(f"/api/envios/{eid}/rastrear", json={}).json()
    check("entregue fica em cache para sempre", d["cache"] is True and len(chamadas) == antes and d["status_atualizado"] is False)

    check("envio inexistente -> 404", c.post("/api/envios/999999/rastrear", json={}).status_code == 404)
    c.delete(f"/api/envios/{eid}")
    check("envio na lixeira -> 404", c.post(f"/api/envios/{eid}/rastrear", json={}).status_code == 404)

print(f"\n{P} passou, {F} falhou")
raise SystemExit(1 if F else 0)
