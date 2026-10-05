# -*- coding: utf-8 -*-
import sqlite3, hashlib, secrets
DB = r"C:\Users\kauan\Downloads\rastreio-asistema1_1\database.db"
sal = secrets.token_hex(16)
h = hashlib.pbkdf2_hmac("sha256", "admin12345".encode(), bytes.fromhex(sal), 100000).hex()
con = sqlite3.connect(DB)
con.execute("UPDATE usuarios SET senha_hash=? WHERE email=?", (sal + "$" + h, "admin@empresa.com"))
con.commit()
print("SENHA_RESET_OK admin@empresa.com / admin12345")
