# -*- coding: utf-8 -*-
"""E2E dos 3 canais no navegador: Rastrear (link Correios), WhatsApp (wa.me) e E-mail (SMTP/mailto)."""
import time, urllib.request, json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

BASE = "http://127.0.0.1:3001"
P = F = 0
def check(nome, cond, detalhe=""):
    global P, F
    if cond: P += 1; print(f"PASS - {nome}", flush=True)
    else: F += 1; print(f"FAIL - {nome} {detalhe}", flush=True)

def api(metodo, caminho, corpo=None, token=""):
    req = urllib.request.Request(BASE + caminho, method=metodo,
        data=json.dumps(corpo).encode() if corpo is not None else None)
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")

st, tok_d = api("POST", "/api/auth/login", {"email": "admin@empresa.com", "senha": "admin12345"})
tok = tok_d.get("token", "")
check("login api", bool(tok))
st, env = api("POST", "/api/envios", {"destinatario": "Canal Teste", "codigo": "CT987654321BR",
    "celular": "11988887777", "email": "canal@t.com", "descricao": "teste canais"}, tok)
id_env = env.get("_id") or ((env.get("envios") or [{}])[0].get("_id")) if isinstance(env.get("envios"), list) else None
check("cria envio de teste", st in (200, 201) and id_env, f"st={st} id={id_env}")

st, lst = api("GET", "/api/envios", None, tok)
alvo = next((e for e in lst.get("envios", []) if str(e.get("codigo")) == "CT987654321BR"), None)
check("link de rastreio correto",
      alvo is not None and alvo.get("link") == "https://rastreamento.correios.com.br/app/index.php?objeto=CT987654321BR",
      str(alvo and alvo.get("link")))

opts = webdriver.ChromeOptions(); opts.add_argument("--start-maximized")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
W = WebDriverWait(driver, 20)
try:
    driver.get(BASE + "/"); time.sleep(3)
    modal_aberto = driver.execute_script("return !document.getElementById('modal-login').hidden")
    if modal_aberto:
        driver.find_element(By.ID, "l-email").send_keys("admin@empresa.com")
        driver.find_element(By.ID, "l-senha").send_keys("admin12345")
        driver.find_element(By.ID, "btn-do-login").click(); time.sleep(2)
        modal_aberto = driver.execute_script("return !document.getElementById('modal-login').hidden")
    check("login UI", modal_aberto is False)
    driver.execute_script("window.__ab=[]; window.open=function(u){ window.__ab.push(String(u)); };")
    card = None
    for it in driver.find_elements(By.CSS_SELECTOR, "#lista .item"):
        if "CT987654321BR" in it.text or "Canal Teste" in it.text:
            card = it; break
    check("card do envio na tela", card is not None)
    if card is None: raise SystemExit(1)
    def achar_card():
        for it in driver.find_elements(By.CSS_SELECTOR, "#lista .item"):
            if "CT987654321BR" in it.text:
                return it
        return None

    # 1) RASTREAR
    achar_card().find_element(By.CSS_SELECTOR, '[data-act="track"]').click(); time.sleep(0.6)
    abertos = driver.execute_script("return window.__ab;")
    check("Rastrear abre link dos Correios",
          bool(abertos) and abertos[-1] == "https://rastreamento.correios.com.br/app/index.php?objeto=CT987654321BR",
          str(abertos))

    # 2) WHATSAPP
    driver.execute_script("window.__ab=[];")
    card = achar_card()
    card.find_element(By.CSS_SELECTOR, '[data-act="wa"]').click(); time.sleep(0.6)
    wa_vis = driver.execute_script("return !document.getElementById('modal-wa').hidden")
    msg = driver.execute_script("return document.getElementById('wa-msg').value")
    check("modal WhatsApp abre", wa_vis)
    check("mensagem WhatsApp tem codigo", "CT987654321BR" in (msg or ""), (msg or "")[:80])
    check("mensagem WhatsApp tem link Correios", "rastreamento.correios.com.br/app" in (msg or ""), "")
    check("mensagem WhatsApp tem equipe", "Rastreio" in (msg or ""), "")
    ctx_fone = driver.execute_script("return (window._waCtx||{}).fone")
    check("fone normalizado 11 digitos", ctx_fone == "11988887777", str(ctx_fone))
    driver.find_element(By.ID, "btn-wa-enviar").click(); time.sleep(0.8)
    abertos = driver.execute_script("return window.__ab;")
    check("abre wa.me com 55 + DDD",
          bool(abertos) and abertos[-1] == "https://wa.me/5511988887777", str(abertos))
    check("modal WhatsApp fecha apos enviar",
          driver.execute_script("return document.getElementById('modal-wa').hidden") is True)

    # 3) E-MAIL (SMTP do .env e placeholder -> servidor responde fallback -> front abre mailto)
    driver.execute_script("window.__ab=[];")
    card = achar_card()
    card.find_element(By.CSS_SELECTOR, '[data-act="mail"]').click(); time.sleep(3)
    abertos = driver.execute_script("return window.__ab;")
    check("E-mail: fallback abre mailto (ou envia de verdade)",
          bool(abertos) and abertos[-1].startswith("mailto:canal@t.com"), str(abertos))
    if abertos:
        check("mailto com assunto de rastreio", "Correios" in abertos[-1] and "CT987654321BR" in abertos[-1], abertos[-1][:140])

    # API de notificacao (o que o botao chama por baixo)
    st, d = api("POST", "/api/notificacoes", {"codigo": "CT987654321BR", "canal": "email", "mensagem": ""}, tok)
    check("POST /notificacoes respondeu", st == 200 and ("success" in d), str(d))
    st, d = api("POST", "/api/notificacoes", {"codigo": "CT987654321BR", "canal": "whatsapp"}, tok)
    check("canal whatsapp devolve fallback wa.me", st == 200 and d.get("fallback") is True, str(d))
finally:
    try:
        api("DELETE", f"/api/envios/{id_env}", None, tok)
        print(f"cleanup: envio {id_env} removido", flush=True)
    except Exception as e:
        print("cleanup falhou:", e, flush=True)
    driver.quit()

print(f"\nCANAIS: {P} passou, {F} falhou")

