# -*- coding: utf-8 -*-
"""Consulta de rastreio na API do Site Rastreio (Wonca Labs) + normalizacao dos eventos.

A API devolve {"json": "<JSON em texto>", "carrier": "CARRIER_..."}; o JSON interno muda
conforme a transportadora (Correios: "eventos"; Cainiao: "module[].detailList").
Aqui tudo vira uma lista unica: [{data, descricao, detalhe, local, destino}].
A mesma regra existe em cloudflare/worker.js (deploy na Cloudflare) — altere os dois juntos.
"""
import json
import os

API_URL = os.getenv("RASTREIO_API_URL", "https://api-labs.wonca.com.br/wonca.labs.v1.LabsService/Track")
TIMEOUT_SEG = 25


class RastreioErro(Exception):
    """Falha ao consultar o provedor (mensagem pronta para mostrar na tela)."""


def api_key() -> str:
    return (os.getenv("RASTREIO_API_KEY") or "").strip()


def configurado() -> bool:
    return bool(api_key())


def _data(v) -> str:
    """dtHrCriado vem como '2024-01-02T10:20:30' ou {'date': '2024-01-02 10:20:30.000000', ...}."""
    if isinstance(v, dict):
        v = v.get("date") or ""
    return str(v or "").replace("T", " ")[:16]


def _unidade(u) -> str:
    if not isinstance(u, dict):
        return ""
    end = u.get("endereco") or {}
    cidade = "/".join(p for p in (str(end.get("cidade") or "").strip(), str(end.get("uf") or "").strip()) if p)
    nome = str(u.get("nome") or u.get("tipo") or "").strip()
    return " — ".join(p for p in (nome, cidade) if p)


def normalizar(resp: dict) -> dict:
    """Converte a resposta do provedor em {carrier, situacao, eventos, mensagem}."""
    bruto = resp.get("json") if isinstance(resp, dict) else None
    try:
        dados = json.loads(bruto) if isinstance(bruto, str) else (bruto or resp or {})
    except ValueError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    if isinstance(dados.get("objetos"), list) and dados["objetos"]:
        dados = dados["objetos"][0] or {}
    eventos = []
    for ev in dados.get("eventos") or []:
        if not isinstance(ev, dict):
            continue
        eventos.append({
            "data": _data(ev.get("dtHrCriado")),
            "descricao": str(ev.get("descricao") or "").strip(),
            "detalhe": str(ev.get("detalhe") or "").strip(),
            "local": _unidade(ev.get("unidade")),
            "destino": _unidade(ev.get("unidadeDestino")),
        })
    entregue = False
    for mod in dados.get("module") or []:
        if not isinstance(mod, dict):
            continue
        if str(mod.get("status") or "").upper() in ("DELIVERED", "SIGNIN"):
            entregue = True
        for ev in mod.get("detailList") or []:
            if not isinstance(ev, dict):
                continue
            eventos.append({
                "data": _data(ev.get("timeStr")),
                "descricao": str(ev.get("standerdDesc") or ev.get("desc") or "").strip(),
                "detalhe": "", "local": str(ev.get("group", {}).get("nodeDesc") or "").strip() if isinstance(ev.get("group"), dict) else "",
                "destino": "",
            })
    eventos = [e for e in eventos if e["descricao"]]
    eventos.sort(key=lambda e: e["data"], reverse=True)
    # "Objeto entregue ao destinatario/remetente"; nao confundir com "saiu para entrega" ou "nao entregue"
    if eventos and eventos[0]["descricao"].lower().startswith("objeto entregue"):
        entregue = True
    situacao = "entregue" if entregue else ("em_transito" if eventos else "sem_eventos")
    return {
        "carrier": str(resp.get("carrier") or "") if isinstance(resp, dict) else "",
        "situacao": situacao,
        "eventos": eventos,
        "mensagem": str(dados.get("mensagem") or "").strip(),
    }


async def consultar(codigo: str) -> dict:
    """Chama o provedor e devolve o resultado normalizado. Levanta RastreioErro em qualquer falha."""
    if not configurado():
        raise RastreioErro("Rastreio automatico nao configurado (defina RASTREIO_API_KEY no .env)")
    import httpx
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEG) as cli:
            r = await cli.post(API_URL, json={"code": codigo},
                               headers={"Authorization": f"Apikey {api_key()}"})
    except httpx.HTTPError:
        raise RastreioErro("Servico de rastreio nao respondeu — tente de novo em instantes")
    try:
        corpo = r.json()
    except ValueError:
        corpo = {}
    if r.status_code == 401:
        raise RastreioErro("Chave da API de rastreio invalida (RASTREIO_API_KEY)")
    if r.status_code == 429:
        raise RastreioErro("Limite de consultas da API de rastreio atingido")
    if r.status_code != 200:
        raise RastreioErro("Rastreio indisponivel no momento (provedor respondeu %s) — tente de novo em instantes" % r.status_code)
    return normalizar(corpo)
