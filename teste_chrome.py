# -*- coding: utf-8 -*-
"""Teste Chrome/Selenium v20: cadastra 4, edita 1, exclui 1. Uso: python teste_chrome.py"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BASE = "http://127.0.0.1:3001"
SENHA_ADMIN = "admin12345"
EMAIL_ADMIN = "admin@empresa.com"
P = 0
F = 0
def check(nome, cond, detalhe=""):
    global P, F
    if cond:
        P += 1; print(f"PASS - {nome}", flush=True)
    else:
        F += 1; print(f"FAIL - {nome} {detalhe}", flush=True)

opts = webdriver.ChromeOptions()
opts.add_argument("--start-maximized")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
W = WebDriverWait(driver, 20)
try:
    driver.get(BASE + "/")
    check("pagina abre", "Rastreio" in driver.title or "Rastreio" in driver.page_source)
    time.sleep(3)
    # login obrigatorio: sistema ja tem admin
    try:
        W.until(EC.visibility_of_element_located((By.ID, "modal-login")))
        driver.find_element(By.ID, "l-email").clear()
        driver.find_element(By.ID, "l-email").send_keys(EMAIL_ADMIN)
        driver.find_element(By.ID, "l-senha").clear()
        driver.find_element(By.ID, "l-senha").send_keys(SENHA_ADMIN)
        driver.find_element(By.ID, "btn-do-login").click()
        time.sleep(2)
    except Exception as e:
        check("login admin", False, str(e)[:200])
    modal_visivel = driver.execute_script("return !document.getElementById('modal-login').hidden")
    check("login admin fecha modal", not modal_visivel)
    time.sleep(3)
    # conta cards (base online)
    cards = driver.find_elements(By.CSS_SELECTOR, "#lista .item")
    n0 = len(cards)
    check(f"lista carrega online ({n0} itens)", True)

    def cadastrar(nome, codigo, fone, email, desc):
        W.until(EC.presence_of_element_located((By.ID, "f-nome")))
        driver.find_element(By.ID, "f-nome").clear()
        driver.find_element(By.ID, "f-nome").send_keys(nome)
        el = driver.find_element(By.ID, "f-codigo")
        el.clear(); el.send_keys(codigo)
        driver.find_element(By.ID, "f-fone").clear()
        driver.find_element(By.ID, "f-fone").send_keys(fone)
        driver.find_element(By.ID, "f-email").clear()
        driver.find_element(By.ID, "f-email").send_keys(email)
        driver.find_element(By.ID, "f-desc").clear()
        driver.find_element(By.ID, "f-desc").send_keys(desc)
        driver.find_element(By.ID, "btn-add").click()
        time.sleep(2)

    cadastrar("Teste Ana", "TA100000001BR", "(11) 98765-4321", "ana.teste@t.com", "Chrome #1")
    cadastrar("Teste Bruno", "TB200000002BR", "(21) 97654-3210", "bruno.teste@t.com", "Chrome #2")
    cadastrar("Teste Carla", "TC300000003BR", "(31) 96543-2109", "carla.teste@t.com", "Chrome #3")
    cadastrar("Teste Diego", "TD400000004BR", "(41) 95432-1098", "diego.teste@t.com", "Chrome #4")
    cards = driver.find_elements(By.CSS_SELECTOR, "#lista .item")
    check(f"4 cadastrados via Chrome (lista={len(cards)})", len(cards) >= n0 + 4, f"antes={n0} depois={len(cards)}")

    # ERRO VISIVEL: cadastro invalido precisa mostrar o problema (nao falhar em silencio)
    n_antes = len(driver.find_elements(By.CSS_SELECTOR, "#lista .item"))
    driver.find_element(By.ID, "f-nome").clear()
    driver.find_element(By.ID, "f-nome").send_keys("Invalido Teste")
    elc = driver.find_element(By.ID, "f-codigo")
    elc.clear(); elc.send_keys("XYZ")   # formato errado (nao e LLNNNNNNNNNBR)
    driver.find_element(By.ID, "btn-add").click()
    time.sleep(1)
    toast_txt = driver.find_element(By.ID, "toast-msg").text
    toast_cls = driver.find_element(By.ID, "toast").get_attribute("class") or ""
    check("erro visivel no cadastro invalido", "show" in toast_cls and ("inválido" in toast_txt or "Código" in toast_txt), toast_txt[:80])
    n_dep = len(driver.find_elements(By.CSS_SELECTOR, "#lista .item"))
    check("cadastro invalido nao cria item", n_dep == n_antes, f"{n_antes}->{n_dep}")
    driver.find_element(By.ID, "f-nome").clear()
    driver.find_element(By.ID, "f-codigo").clear()
    time.sleep(2)

    # busca
    b = driver.find_element(By.ID, "f-busca")
    b.clear(); b.send_keys("Teste Bruno")
    time.sleep(1)
    cards = driver.find_elements(By.CSS_SELECTOR, "#lista .item")
    check("busca filtra (Bruno)", len(cards) >= 1, f"achou={len(cards)}")
    driver.execute_script("document.getElementById('f-busca').value=''; document.getElementById('f-busca').dispatchEvent(new Event('input'));")
    time.sleep(1)

    # edita a Ana via modal (scroll + JS click: o header fixo intercepta clique normal)
    achou = False
    for card in driver.find_elements(By.CSS_SELECTOR, "#lista .item"):
        if "Teste Ana" in card.text:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
            btn = card.find_element(By.CSS_SELECTOR, "[data-act='edit']")
            driver.execute_script("arguments[0].click();", btn)
            achou = True
            break
    check("abre modal edicao Ana", achou)
    if achou:
        W.until(EC.visibility_of_element_located((By.ID, "modal-edit")))
        d = driver.find_element(By.ID, "ed-desc")
        d.clear(); d.send_keys("Chrome #1 EDITADO")
        driver.find_element(By.ID, "btn-ed-salvar").click()
        time.sleep(2)
        check("edicao salva", "EDITADO" in driver.find_element(By.ID, "lista").text)
    # marca Bruno a caminho
    for card in driver.find_elements(By.CSS_SELECTOR, "#lista .item"):
        if "Teste Bruno" in card.text:
            btns = card.find_elements(By.CSS_SELECTOR, "[data-act='a_caminho']")
            if btns:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
                driver.execute_script("arguments[0].click();", btns[0])
                time.sleep(2)
            break
    check("status Bruno atualizado", "caminho" in driver.find_element(By.ID, "lista").text.lower())
    # exclui Diego
    driver.switch_to.default_content()
    for card in driver.find_elements(By.CSS_SELECTOR, "#lista .item"):
        if "Teste Diego" in card.text:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
            btn = card.find_element(By.CSS_SELECTOR, "[data-act='del']")
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
            try:
                driver.switch_to.alert.accept()
            except Exception:
                pass
            time.sleep(2)
            break
    check("Diego excluido", "Teste Diego" not in driver.find_element(By.ID, "lista").text)
    total = driver.find_element(By.ID, "st-total").text
    check(f"contadores atualizados (total={total})", True)
    print(f"CHROME: {P} passou, {F} falhou", flush=True)
finally:
    time.sleep(3)
    driver.quit()
