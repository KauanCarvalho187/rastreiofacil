# -*- coding: utf-8 -*-
"""Validação unificada — usada por main.py e importar_planilha.py.
Motivo: antes a mesma regra existia em 3 lugares (main.py, app.js,
importar_planilha.py) e divergia. Centralizar evita bug e facilita manutenção.
"""
import re

REGEX_CODIGO = re.compile(r"^[A-Za-z]{2}\d{9}BR$")
REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STATUS_VALIDOS = ("pendente", "a_caminho", "entregue")

def limpar_codigo(codigo: str) -> str:
    return (codigo or "").strip().upper()

def validar_codigo(codigo: str) -> str:
    codigo = limpar_codigo(codigo)
    if not REGEX_CODIGO.match(codigo):
        raise ValueError(f"código inválido '{codigo}' — use 2 letras + 9 números + BR")
    return codigo

def validar_email(email: str) -> str:
    email = (email or "").strip()
    if not email:
        return email
    if " " in email or not REGEX_EMAIL.match(email):
        raise ValueError(f"e-mail inválido '{email}'")
    return email

def normalizar_celular(valor: str) -> str:
    d = re.sub(r"\D", "", str(valor or ""))
    if d.startswith("0055"):
        d = "55" + d[4:]
    if d.startswith("0") and len(d) > 1:
        d = d[1:]
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if d and len(d) not in (10, 11):
        raise ValueError(f"celular inválido '{valor}' — use DDD + 8/9 dígitos")
    return d

def normalizar_status(status: str) -> str:
    s = (status or "pendente").strip().lower().replace(" ", "_")
    # aceita "a caminho", "em trânsito", etc.
    s = s.replace("ã", "a").replace("â", "a").replace("é", "e").replace("ê", "e")
    if "caminho" in s or "transito" in s or s in ("a_caminho", "acaminho"):
        return "a_caminho"
    if "entregue" in s or "entreg" in s:
        return "entregue"
    return "pendente"
