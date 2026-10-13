# -*- coding: utf-8 -*-
"""Rastreio automatico: normalizacao do provedor + rota /api/envios/{id}/rastrear."""
import json

import rastreio


def _resp_correios(*eventos):
    return {"carrier": "CARRIER_CORREIOS",
            "json": json.dumps({"codObjeto": "AA123456789BR", "eventos": list(eventos)})}


EV_POSTADO = {"descricao": "Objeto postado",
              "dtHrCriado": {"date": "2026-10-01 09:15:00.000000", "timezone": "America/Sao_Paulo"},
              "unidade": {"tipo": "Agência dos Correios",
                          "endereco": {"cidade": "SAO PAULO", "uf": "SP"}}}
EV_TRANSITO = {"descricao": "Objeto em transferência - por favor aguarde",
               "dtHrCriado": "2026-10-02T14:30:00",
               "unidade": {"tipo": "Unidade de Tratamento", "endereco": {"cidade": "CAJAMAR", "uf": "SP"}},
               "unidadeDestino": {"tipo": "Unidade de Distribuição",
                                  "endereco": {"cidade": "RECIFE", "uf": "PE"}}}
EV_ENTREGUE = {"descricao": "Objeto entregue ao destinatário", "dtHrCriado": "2026-10-04T10:00:00"}


def test_normaliza_ordena_mais_recente_primeiro():
    r = rastreio.normalizar(_resp_correios(EV_POSTADO, EV_ENTREGUE))
    assert r["situacao"] == "entregue"
    assert r["eventos"][0]["data"] == "2026-10-04 10:00"


def test_normaliza_local_e_destino():
    r = rastreio.normalizar(_resp_correios(EV_TRANSITO))
    ev = r["eventos"][0]
    assert ev["local"] == "Unidade de Tratamento — CAJAMAR/SP"
    assert ev["destino"] == "Unidade de Distribuição — RECIFE/PE"
    assert r["situacao"] == "em_transito"


def test_saiu_para_entrega_nao_e_entregue():
    r = rastreio.normalizar(_resp_correios(
        {"descricao": "Objeto saiu para entrega ao destinatário", "dtHrCriado": "2026-10-03T08:00:00"}))
    assert r["situacao"] == "em_transito"


def test_sem_eventos():
    assert rastreio.normalizar(_resp_correios())["situacao"] == "sem_eventos"


def test_resposta_invalida_nao_quebra():
    assert rastreio.normalizar("texto solto")["situacao"] == "sem_eventos"
    assert rastreio.normalizar({"json": "nao e json"})["situacao"] == "sem_eventos"


def test_cainiao_entregue():
    resp = {"carrier": "CARRIER_CAINIAO",
            "json": json.dumps({"module": [{"status": "DELIVERED", "detailList": [
                {"timeStr": "2026-10-05 10:00", "standerdDesc": "Entregue",
                 "group": {"nodeDesc": "CD Recife"}}]}]})}
    r = rastreio.normalizar(resp)
    assert r["situacao"] == "entregue"
    assert r["eventos"][0]["descricao"] == "Entregue"


def _envio(client, auth):
    d = client.post("/api/envios",
                    json={"destinatario": "X", "codigo": "AA123456789BR", "email": "x@t.com"},
                    headers=auth["H"]).json()
    return d["envios"][0]["_id"]


def test_rota_rastrear_atualiza_e_cacheia(client, auth, monkeypatch):
    eid = _envio(client, auth)
    chamadas = {"n": 0}

    async def fake(codigo):
        chamadas["n"] += 1
        return {"situacao": "entregue", "carrier": "CARRIER_CORREIOS", "mensagem": "",
                "eventos": [{"data": "2026-10-04 10:00", "descricao": "Objeto entregue",
                             "detalhe": "", "local": "X", "destino": ""}]}

    monkeypatch.setattr(rastreio, "consultar", fake)
    d = client.post(f"/api/envios/{eid}/rastrear", json={}, headers=auth["H"]).json()
    assert d["status_atualizado"] is True and d["cache"] is False
    assert chamadas["n"] == 1

    # 2a consulta cai no cache (nao chama o provedor de novo)
    d2 = client.post(f"/api/envios/{eid}/rastrear", json={}, headers=auth["H"]).json()
    assert d2["cache"] is True and chamadas["n"] == 1

    alvo = next(e for e in client.get("/api/envios", headers=auth["H"]).json()["envios"] if e["_id"] == eid)
    assert alvo["status"] == "entregue"


def test_rota_rastrear_fora_do_ar_sem_cache_503(client, auth, monkeypatch):
    eid = _envio(client, auth)

    async def fake(codigo):
        raise rastreio.RastreioErro("fora do ar")

    monkeypatch.setattr(rastreio, "consultar", fake)
    r = client.post(f"/api/envios/{eid}/rastrear", json={}, headers=auth["H"])
    assert r.status_code == 503
