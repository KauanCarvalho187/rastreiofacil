# -*- coding: utf-8 -*-
"""Inspecao somente-leitura do banco real (nao altera nada)."""
import sqlite3
DB = "C:/Users/kauan/Downloads/rastreio-asistema1_1/database.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
print("== usuarios ==")
for r in cur.execute("SELECT id,nome,email,admin,ativo FROM usuarios"):
    print(dict(r))
print("== total envios ==")
print(cur.execute("SELECT COUNT(*) FROM envios").fetchone()[0])
print("== ultimos 10 envios ==")
for r in cur.execute("SELECT id,destinatario,codigo,status FROM envios ORDER BY id DESC LIMIT 10"):
    print(dict(r))
con.close()
