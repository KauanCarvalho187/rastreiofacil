# -*- coding: utf-8 -*-
"""Demonstracao E2E no Brave (Selenium) — cria um usuario SEM ser admin, passo a passo.

O que este script faz, todo clicado na interface (nada de chamar a API na mao):
  1. abre o sistema no Brave;
  2. cria o admin (1o uso) e faz login;
  3. abre a tela "Usuarios" (botao 👥);
  4. preenche o formulario e cria um usuario COMUM (caixa "Administrador" desmarcada);
  5. confere que o novo usuario aparece com o selo "usuario";
  6. sai e entra com o usuario comum para provar que ele NAO ve a gestao de usuarios.

Salva um print de cada etapa em `evidencias_usuarios/`.

Uso:
    python teste_usuarios_brave.py                  # usa o Brave (se instalado) ou o Chrome
    python teste_usuarios_brave.py --chrome         # forca o Google Chrome
    python teste_usuarios_brave.py --base http://127.0.0.1:3000   # usa um servidor ja rodando
    python teste_usuarios_brave.py --pausa 30       # deixa o navegador aberto no fim
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
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.join(ROOT, "evidencias_usuarios")

ADMIN = {"nome": "Admin Bravo", "email": "admin@bravo.com", "senha": "admin12345"}
COMUM = {"nome": "Operador Bravo", "email": "operador@bravo.com", "senha": "operador123"}

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


def _achar_brave():
    candidatos = [
        os.environ.get("BRAVE_PATH", ""),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     r"BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     r"BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     r"BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    for c in candidatos:
        if c and os.path.exists(c):
            return c
    return ""


def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _sobe_servidor():
    pasta = tempfile.mkdtemp(prefix="rastreio-brave-")
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


def _cria_navegador(binario, download_dir):
    opts = webdriver.ChromeOptions()
    if binario:
        opts.binary_location = binario
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-infobars")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    })
    drv = webdriver.Chrome(options=opts)
    try:
        drv.maximize_window()
    except Exception:
        pass
    return drv


def _clicar(drv, el):
    """Clique com fallback JS (toast/overlay as vezes cobre o botao)."""
    try:
        el.click()
    except Exception:
        drv.execute_script("arguments[0].click();", el)


def _digitar(drv, el_id, texto):
    """Limpa o campo antes de digitar (o modal de login guarda o texto anterior)."""
    el = drv.find_element(By.ID, el_id)
    try:
        el.clear()
    except Exception:
        drv.execute_script("arguments[0].value='';", el)
    el.send_keys(texto)
    return el


def main():
    global OK, FALHA
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="", help="usa um servidor ja rodando (ex.: http://127.0.0.1:3000)")
    ap.add_argument("--pausa", type=int, default=0, help="segundos com o navegador aberto no fim")
    ap.add_argument("--chrome", action="store_true", help="forca o Google Chrome em vez do Brave")
    args = ap.parse_args()

    os.makedirs(EVID, exist_ok=True)
    for f in glob.glob(os.path.join(EVID, "*.png")):
        os.remove(f)

    binario = ""
    if not args.chrome:
        binario = _achar_brave()
        if not binario:
            print("! Brave nao encontrado — usando o Chrome.")
    nome_nav = "Chrome" if (args.chrome or not binario) else "Brave"
    if binario:
        print(f"Navegador: {nome_nav} ({binario})")

    proc = None
    base = args.base.rstrip("/") if args.base else ""
    if not base:
        print("Subindo servidor de teste (banco temporario)...")
        proc, base = _sobe_servidor()
    print(f"Servidor: {base}\n")

    download_dir = tempfile.mkdtemp(prefix="rastreio-dl-brave-")
    print(f"Abrindo o {nome_nav}...\n")
    drv = _cria_navegador(binario, download_dir)
    wait = WebDriverWait(drv, 25)
    n_shot = [0]

    def shot(nome):
        n_shot[0] += 1
        caminho = os.path.join(EVID, f"{n_shot[0]:02d}_{nome}.png")
        drv.save_screenshot(caminho)
        print(f"   print -> {os.path.relpath(caminho, ROOT)}")

    try:
        # ---- 1. abrir o sistema --------------------------------------------
        print("== 1. Abrir o sistema ==")
        drv.get(base + "/")
        wait.until(EC.element_to_be_clickable((By.ID, "btn-login")))
        check("pagina abriu", "Rastreio" in drv.title or "Rastreio" in drv.page_source)
        shot("tela_inicial")

        # ---- 2. criar admin (1o uso) e entrar ------------------------------
        print("\n== 2. Criar o admin (1o uso) e entrar ==")
        _clicar(drv, drv.find_element(By.ID, "btn-login"))
        wait.until(EC.visibility_of_element_located((By.ID, "l-email")))
        _clicar(drv, drv.find_element(By.ID, "btn-do-reg"))  # revela o campo Nome
        wait.until(EC.visibility_of_element_located((By.ID, "l-nome")))
        drv.find_element(By.ID, "l-nome").send_keys(ADMIN["nome"])
        _digitar(drv, "l-email", ADMIN["email"])
        _digitar(drv, "l-senha", ADMIN["senha"])
        shot("login_preenchido")
        _clicar(drv, drv.find_element(By.ID, "btn-do-reg"))
        wait.until(EC.invisibility_of_element_located((By.ID, "l-email")))
        wait.until(lambda d: d.find_element(By.ID, "btn-usuarios").is_displayed())
        check("admin criado, logado e botao Usuarios visivel", True)
        shot("logado_admin")

        # ---- 3. abrir a tela de usuarios -----------------------------------
        print("\n== 3. Abrir a tela 'Usuarios' (botao de pessoas) ==")
        _clicar(drv, drv.find_element(By.ID, "btn-usuarios"))
        wait.until(EC.visibility_of_element_located((By.ID, "us-lista")))
        wait.until(EC.visibility_of_element_located((By.ID, "us-nome")))
        check("tela de usuarios abriu", True)
        shot("tela_usuarios")

        # ---- 4. criar o usuario COMUM --------------------------------------
        print("\n== 4. Criar um usuario SEM ser admin ==")
        drv.find_element(By.ID, "us-nome").send_keys(COMUM["nome"])
        _digitar(drv, "us-email", COMUM["email"])
        _digitar(drv, "us-senha", COMUM["senha"])
        check("caixa 'Administrador' desmarcada", not drv.find_element(By.ID, "us-admin").is_selected())
        shot("form_preenchido")
        _clicar(drv, drv.find_element(By.ID, "btn-us-criar"))

        wait.until(lambda d: COMUM["email"] in d.find_element(By.ID, "us-lista").text)
        item = next((i for i in drv.find_elements(By.CSS_SELECTOR, "#us-lista .item")
                     if COMUM["email"] in i.text), None)
        check("usuario comum aparece na lista", item is not None)
        check("selo 'usuario' (nao admin)", bool(item) and "usuário" in item.text,
              (item.text if item else "sem item"))
        shot("usuario_criado")

        # ---- 5. provar que o comum nao ve gestao de usuarios ---------------
        print("\n== 5. Entrar como o usuario comum e conferir as permissoes ==")
        # fecha a tela de Usuarios antes de sair (ela fica sobre o modal de login)
        _clicar(drv, drv.find_element(By.CSS_SELECTOR, "#modal-usuarios [data-close]"))
        wait.until(EC.invisibility_of_element_located((By.ID, "us-lista")))
        out = drv.find_element(By.ID, "btn-logout")
        _clicar(drv, out)
        wait.until(EC.visibility_of_element_located((By.ID, "l-email")))
        _digitar(drv, "l-email", COMUM["email"])
        _digitar(drv, "l-senha", COMUM["senha"])
        _clicar(drv, drv.find_element(By.ID, "btn-do-login"))
        wait.until(EC.invisibility_of_element_located((By.ID, "l-email")))
        wait.until(lambda d: not d.find_element(By.ID, "btn-usuarios").is_displayed())
        check("usuario comum NAO ve o botao Usuarios", True)
        check("usuario comum NAO ve o Backup", not drv.find_element(By.ID, "btn-backup").is_displayed())
        shot("logado_usuario_comum")

        if args.pausa:
            print(f"\n>> {nome_nav} aberto por {args.pausa}s para voce conferir a tela...")
            time.sleep(args.pausa)
    except Exception as e:
        FALHA += 1
        print(f"\nERRO na demonstracao: {type(e).__name__}: {e}")
        try:
            diag = {}
            for i in ("btn-usuarios", "btn-backup", "l-email", "l-err", "modal-usuarios", "us-lista"):
                try:
                    el = drv.find_element(By.ID, i)
                    diag[i] = f"displayed={el.is_displayed()}"
                except Exception as ex:
                    diag[i] = f"<{type(ex).__name__}>"
            print("   DIAG:", diag)
            try:
                print("   l-err texto:", drv.find_element(By.ID, "l-err").text)
            except Exception:
                pass
            print("   url:", drv.current_url)
        except Exception:
            pass
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
