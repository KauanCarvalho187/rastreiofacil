# -*- coding: utf-8 -*-
"""Limpa envios de teste (Teste */TA*/TB*/TC*/TD*). Uso: python limpar_teste.py"""
import sqlite3
DB = r"C:\Users\kauan\Downloads\rastreio-asistema1_1\database.db"
con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("DELETE FROM envios WHERE destinatario LIKE 'Teste %' OR destinatario LIKE '%QA' OR destinatario LIKE 'Fulano %' OR codigo IN ('TA100000001BR','TB200000002BR','TC300000003BR','TD400000004BR','QA111111111BR','QB222222222BR','QC333333333BR','QD444444444BR','FU123456789BR','FD223456789BR','FT323456789BR','FQ423456789BR')")
print("removidos:", cur.rowcount)
con.commit()
print("total agora:", list(con.execute("SELECT COUNT(*) FROM envios"))[0][0])
