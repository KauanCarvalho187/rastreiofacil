# -*- coding: utf-8 -*-
"""Demonstracao E2E no Google Chrome (Selenium) — abre o navegador DE VERDADE.

Fluxo do dia a dia, todo clicado na interface:
  1. faz login do admin unico (admin@admin.com);
  2. cadastra varias pessoas de teste pelo formulario;
  3. muda o status de algumas clicando nos cards;
  4. apaga algumas (vao para a lixeira) e mostra a lixeira;
  5. exporta a lista para Excel (botao "Exportar Excel").

Salva um print de cada etapa em `evidencias/` e o Excel em `envios_teste.xlsx`.

Uso:
    python teste_navegador_demo.py
    python teste_navegador_demo.py --base http://127.0.0.1:3001
    python teste_navegador_demo.py --pausa 25      # deixa o Chrome aberto no fim
"""
import argparse
import glob
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

ROOT = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.join(ROOT, "evidencias")
ADMIN = {"email": "admin@admin.com", "senha": "admin12345"}

PESSOAS = [
    ("Maria Silva",    "QX100000001BR", "(11) 98765-4321", "maria.silva@teste.com",   "Pedido #1001"),
    ("Joao Souza",     "QX100000002BR", "(11) 99123-4567", "joao.souza@teste.com",    "Pedido #1002"),
    ("Ana Paula",      "QX100000003BR", "(21) 98888-7777", "ana.paula@teste.com",     "Pedido #1003"),
    ("Carlos Eduardo", "QX100000004BR", "(31) 97777-6666", "carlos.edu@teste.com",    "Presente"),
    ("Fernanda Lima",  "QX100000005BR", "(41) 96666-5555", "",                        "So WhatsApp"),
    ("Rafael Costa",   "QX100000006BR", "(51) 95555-4444", "rafael.costa@teste.com",  "Pedido #1006"),
    ("Beatriz Alves",  "QX100000007BR", "(61) 94444-3333", "bia.alves@teste.com",     "Pedido #1007"),
    ("Lucas Pereira",  "QX100000008BR", "(71) 93333-2222", "lucas.pereira@teste.com", "Pedido #1008"),
]

OK = FALHA = 0


def check(nome, cond, detalhe=""):
    global OK, FALHA
    if cond:
        OK += 1
        print(f"  PASS - {nome}")
    else:
        FALHA += 1
        print(f"  FAIL - {nome}  {detalhe}")
    return cond


def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _sobe_servidor():
    pasta = tempfile.mkdtemp(prefix="rastreio-demo-")
    porta = _porta_livre()
    env = os.environ.copy()
    env["DB_PATH"] = os.path.join(pasta, "demo.db")
    env["DATABASE_URL"] = ""
    env["RASTREIO_API_KEY"] = ""
    env["SMTP_USER"] = ""
    env["SMTP_PASS"] = ""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(porta)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{porta}"
    for _ in range(60):
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=3) as r:
                if r.status == 200:
                    return proc, base
        except Exception:
            time.sleep(0.5)
    proc.terminate()
    raise RuntimeError("servidor nao subiu")


def _cria_chrome(download_dir):
    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-infobars")
    opts.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "safebrowsing.enabled": True,
    })
    drv = webdriver.Chrome(options=opts)
    try:
        drv.maximize_window()
    except Exception:
        pass
    return drv


def _card(drv, codigo):
    try:
        itens = drv.find_elements(By.CSS_SELECTOR, "#lista .item")
    except StaleElementReferenceException:
        return None
    for it in itens:
        try:
            if codigo in it.text:
                return it
        except StaleElementReferenceException:
            continue
    return None


def _card_tem(drv, codigo, texto):
    c = _card(drv, codigo)
    if not c:
        return False
    try:
        return texto in c.text
    except StaleElementReferenceException:
        return False


def _clicar_card(drv, codigo, act, tentativas=15):
    """Clica num botao do card; tolera re-render (stale) e toast sobrepondo (clique via JS)."""
    for _ in range(tentativas):
        alvo = None
        c = _card(drv, codigo)
        if c:
            try:
                alvo = c.find_element(By.CSS_SELECTOR, f'[data-act="{act}"]')
            except Exception:
                alvo = None
        if alvo is not None:
            try:
                alvo.click()
                return True
            except Exception:
                # elemento coberto pelo toast "Desfazer" etc.: dispara o clique no elemento
                try:
                    drv.execute_script("arguments[0].click();", alvo)
                    return True
                except Exception:
                    pass
        time.sleep(0.3)
    raise RuntimeError(f"nao consegui clicar '{act}' no card {codigo}")


def _clicar_filtro(drv, valor):
    """Clica no card de estatistica (filtro), com fallback JS."""
    for _ in range(15):
        for stat in drv.find_elements(By.CSS_SELECTOR, ".stat[data-filtro]"):
            if stat.get_attribute("data-filtro") == valor:
                try:
                    stat.click()
                    return True
                except Exception:
                    try:
                        drv.execute_script("arguments[0].click();", stat)
                        return True
                    except Exception:
                        pass
        time.sleep(0.3)
    raise RuntimeError(f"nao consegui clicar no filtro '{valor}'")


def _total(drv):
    return int((drv.find_element(By.ID, "st-total").text or "0").strip() or 0)


def _lixeira(drv):
    return int((drv.find_element(By.ID, "st-lix").text or "0").strip() or 0)


def main():
    global OK, FALHA
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="", help="usa um servidor ja rodando")
    ap.add_argument("--pausa", type=int, default=0, help="segundos com o Chrome aberto no fim")
    ap.add_argument("--excel", default=os.path.join(ROOT, "envios_teste.xlsx"))
    args = ap.parse_args()

    os.makedirs(EVID, exist_ok=True)
    for f in glob.glob(os.path.join(EVID, "*.png")):
        os.remove(f)

    proc = None
    base = args.base.rstrip("/") if args.base else ""
    if not base:
        print("Subindo servidor de teste (banco temporario)...")
        proc, base = _sobe_servidor()
    print(f"Servidor: {base}")

    download_dir = tempfile.mkdtemp(prefix="rastreio-dl-")
    print("Abrindo o Google Chrome...\n")
    drv = _cria_chrome(download_dir)
    wait = WebDriverWait(drv, 25)
    n_shot = [0]

    def shot(nome):
        n_shot[0] += 1
        caminho = os.path.join(EVID, f"{n_shot[0]:02d}_{nome}.png")
        drv.save_screenshot(caminho)
        print(f"   print -> {os.path.relpath(caminho, ROOT)}")

    try:
        # ---- 1. tela inicial + login ---------------------------------------
        print("== 1. Abrir o sistema e fazer login ==")
        drv.get(base + "/")
        wait.until(EC.element_to_be_clickable((By.ID, "btn-login")))
        check("pagina abriu no Chrome", "Rastreio" in drv.title or "Rastreio" in drv.page_source)
        shot("tela_inicial")

        drv.find_element(By.ID, "btn-login").click()
        wait.until(EC.visibility_of_element_located((By.ID, "l-senha")))
        # v28: admin unico — o modal so pede a senha (admin@admin.com)
        drv.find_element(By.ID, "l-senha").send_keys(ADMIN["senha"])
        shot("login_preenchido")
        drv.find_element(By.ID, "btn-do-login").click()

        wait.until(lambda d: not d.find_element(By.ID, "modal-login").is_displayed())
        check("login efetuado com o admin unico", True)
        wait.until(lambda d: d.find_element(By.ID, "btn-backup").is_displayed())
        check("backup (admin) ficou visivel", True)
        shot("logado")

        # ---- 2. cadastrar as pessoas ---------------------------------------
        print("\n== 2. Cadastrar pessoas de teste pelo formulario ==")
        Select(drv.find_element(By.ID, "f-status")).select_by_value("pendente")
        for i, (nome, cod, fone, mail, desc) in enumerate(PESSOAS, start=1):
            wait.until(EC.visibility_of_element_located((By.ID, "f-nome"))).send_keys(nome)
            drv.find_element(By.ID, "f-codigo").send_keys(cod)
            if mail:
                drv.find_element(By.ID, "f-email").send_keys(mail)
            drv.find_element(By.ID, "f-fone").send_keys(fone)
            drv.find_element(By.ID, "f-desc").send_keys(desc)
            drv.find_element(By.ID, "btn-add").click()
            try:
                wait.until(lambda d, n=i: _total(d) == n)
                print(f"   + {nome} ({cod})")
            except Exception:
                print(f"   ! falha ao cadastrar {nome}")
        check(f"cadastrou as {len(PESSOAS)} pessoas", _total(drv) == len(PESSOAS), f"total={_total(drv)}")
        shot("cadastros")

        # ---- 3. mudar status clicando nos cards ----------------------------
        print("\n== 3. Mudar status pelos cards ==")
        for cod in ("QX100000002BR", "QX100000003BR"):
            wait.until(lambda d, k=cod: _card(d, k) is not None)
            _clicar_card(drv, cod, "a_caminho")
            wait.until(lambda d, k=cod: _card_tem(d, k, "a caminho"))
            print(f"   {cod} -> a caminho")
        wait.until(lambda d: _card(d, "QX100000004BR") is not None)
        _clicar_card(drv, "QX100000004BR", "entregue")
        wait.until(lambda d: _card_tem(d, "QX100000004BR", "entregue"))
        print("   QX100000004BR -> entregue")
        wait.until(lambda d: d.find_element(By.ID, "st-cam").text == "2" and d.find_element(By.ID, "st-ent").text == "1")
        check("status aplicado (a caminho=2, entregue=1)", True)
        shot("status_atualizado")

        # ---- 4. apagar alguns (lixeira) ------------------------------------
        print("\n== 4. Apagar algumas pessoas (vao para a lixeira) ==")
        restante = len(PESSOAS)
        for cod in ("QX100000005BR", "QX100000006BR", "QX100000007BR"):
            restante -= 1
            wait.until(lambda d, k=cod: _card(d, k) is not None)
            _clicar_card(drv, cod, "del")
            wait.until(EC.alert_is_present())
            drv.switch_to.alert.accept()  # confirma a exclusao
            wait.until(lambda d, n=restante: _total(d) == n)
            print(f"   apagou {cod} (restam {restante})")
        check("lista ativa caiu para 5", _total(drv) == 5, f"total={_total(drv)}")
        check("lixeira mostra 3", _lixeira(drv) == 3, f"lixeira={_lixeira(drv)}")
        shot("apos_apagar")

        # mostra a lixeira (clica no card "Lixeira")
        _clicar_filtro(drv, "excluido")
        wait.until(lambda d: d.find_element(By.ID, "list-count").text == "3")
        shot("lixeira")
        # volta para "Todos"
        _clicar_filtro(drv, "todos")
        wait.until(lambda d: d.find_element(By.ID, "list-count").text == "5")

        # ---- 5. exportar Excel ---------------------------------------------
        print("\n== 5. Exportar a lista para Excel ==")
        drv.find_element(By.ID, "btn-exp-xlsx").click()
        xlsx = None
        for _ in range(40):
            achados = [f for f in glob.glob(os.path.join(download_dir, "*.xlsx")) if not f.endswith(".crdownload")]
            if achados:
                xlsx = achados[0]
                break
            time.sleep(0.5)
        check("arquivo Excel baixado", bool(xlsx), "nada em " + download_dir)
        if xlsx:
            shutil.copyfile(xlsx, args.excel)
            check("Excel salvo como envios_teste.xlsx", os.path.exists(args.excel))
            print(f"   Excel: {args.excel}")
        shot("export_excel")

        if args.pausa:
            print(f"\n>> Chrome aberto por {args.pausa}s para voce conferir a tela...")
            time.sleep(args.pausa)
    except Exception as e:
        FALHA += 1
        print(f"\nERRO na demonstracao: {type(e).__name__}: {e}")
        try:
            shot("erro")
        except Exception:
            pass
    finally:
        try:
            drv.quit()
        except Exception:
            pass
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()

    print(f"\nPrints em: {os.path.relpath(EVID, ROOT)}\\")
    print(f"RESULTADO: {OK} passou, {FALHA} falhou")
    return 1 if FALHA else 0


if __name__ == "__main__":
    sys.exit(main())
