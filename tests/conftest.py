# -*- coding: utf-8 -*-
"""Configuracao comum dos testes (pytest).

- Testes de API: rodam in-process com o TestClient do FastAPI e um banco SQLite
  temporario por teste (nao precisam de servidor nem de rede).
- Testes de navegador: marcados com @pytest.mark.browser; sobem um uvicorn real
  e usam Selenium. Nao rodam por padrao — use `pytest --browser` (precisa de Chrome).
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)  # main.py serve static/ relativo ao CWD

# Modo SQLite + sem credenciais externas ANTES de importar o app.
# (os.environ vence o load_dotenv do main.py, que nao sobrescreve variaveis ja definidas)
os.environ["DATABASE_URL"] = ""
os.environ["RASTREIO_API_KEY"] = ""
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASS"] = ""


# ---------------------------------------------------------------- fixtures API

@pytest.fixture
def client(tmp_path):
    """TestClient do FastAPI com banco SQLite isolado (recriado a cada teste)."""
    import db
    caminho = str(tmp_path / "teste.db")
    db.DB_PATH = caminho
    os.environ["DB_PATH"] = caminho
    from fastapi.testclient import TestClient
    import main
    main.DB_PATH = caminho  # usado pela rota /api/backup
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(autouse=True)
def _limpa_rate_limit():
    """Zera o rate-limit de login entre os testes (memoria do processo)."""
    import main
    main._LOGIN_TENTATIVAS.clear()
    yield


def _login(client, email, senha):
    r = client.post("/api/auth/login", json={"email": email, "senha": senha})
    return r.json().get("token", "")


@pytest.fixture
def auth(client):
    """Admin unico (admin@admin.com) — criado automaticamente no boot do app."""
    adm = _login(client, "admin@admin.com", "admin12345")
    H = {"Authorization": "Bearer " + adm}
    return {"token": adm, "H": H}


# ------------------------------------------------------- fixtures navegador

def pytest_addoption(parser):
    parser.addoption("--browser", action="store_true", default=False,
                     help="roda tambem os testes de navegador (Selenium/Chrome)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--browser"):
        return
    pular = pytest.mark.skip(reason="teste de navegador — rode com: pytest --browser")
    for item in items:
        if "browser" in item.keywords:
            item.add_marker(pular)


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def _post_json(url, dados):
    import json
    req = urllib.request.Request(url, method="POST", data=json.dumps(dados).encode())
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


@pytest.fixture(scope="session")
def live_server():
    """Sobe um uvicorn real em porta livre com banco temporario e admin semeado."""
    pytest.importorskip("selenium")
    import db  # noqa: F401  (garante import do pacote)
    pasta = tempfile.mkdtemp(prefix="rastreio-live-")
    porta = _porta_livre()
    base = f"http://127.0.0.1:{porta}"
    env = os.environ.copy()
    env["DB_PATH"] = os.path.join(pasta, "live.db")
    env["DATABASE_URL"] = ""
    env["RASTREIO_API_KEY"] = ""
    env["SMTP_USER"] = ""
    env["SMTP_PASS"] = ""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(porta)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                if _get(base + "/api/health")[0] == 200:
                    break
            except Exception:
                time.sleep(0.5)
        else:
            proc.terminate()
            pytest.skip("servidor de teste nao subiu")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


@pytest.fixture(scope="session")
def browser(live_server):
    """Chrome headless (Selenium 4 usa o Selenium Manager para o driver)."""
    opts = None
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        opts = Options()
        for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
                    "--window-size=1400,1000", "--disable-gpu"):
            opts.add_argument(arg)
        driver = webdriver.Chrome(options=opts)
    except Exception as e:  # Chrome/driver ausente
        pytest.skip(f"Chrome/ChromeDriver indisponivel: {e}")
    yield driver
    try:
        driver.quit()
    except Exception:
        pass
