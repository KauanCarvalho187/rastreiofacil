# -*- coding: utf-8 -*-
"""Testes de navegador (Selenium + Chrome headless).

NAO rodam por padrao. Para executar (precisa de Chrome instalado):

    pip install -r requirements-dev.txt
    pytest --browser

Os testes sobem um servidor uvicorn real (fixture live_server, banco temporario)
e dirigem a interface em http://127.0.0.1:<porta-livre>.
"""
import pytest

# Sem selenium instalado o modulo e' pulado (nao quebra a coleta).
pytest.importorskip("selenium", reason="instale com: pip install -r requirements-dev.txt")
from selenium.webdriver.common.by import By  # noqa: E402
from selenium.webdriver.support import expected_conditions as EC  # noqa: E402
from selenium.webdriver.support.ui import WebDriverWait  # noqa: E402

pytestmark = pytest.mark.browser

EMAIL = "admin@teste.com"
SENHA = "admin12345"


@pytest.fixture
def w(browser, live_server):
    browser.get(live_server + "/")
    yield WebDriverWait(browser, 20)


def _login(browser, live_server, w):
    w.until(EC.element_to_be_clickable((By.ID, "btn-login"))).click()
    w.until(EC.visibility_of_element_located((By.ID, "l-email"))).send_keys(EMAIL)
    browser.find_element(By.ID, "l-senha").send_keys(SENHA)
    browser.find_element(By.ID, "btn-do-login").click()
    w.until(EC.invisibility_of_element_located((By.ID, "l-email")))


def test_pagina_abre(browser, live_server, w):
    assert "Rastreio" in browser.title
    assert browser.find_element(By.ID, "btn-login").is_displayed()


def test_login_e_logout(browser, live_server, w):
    _login(browser, live_server, w)
    w.until(EC.element_to_be_clickable((By.ID, "btn-logout"))).click()
    w.until(EC.element_to_be_clickable((By.ID, "btn-login")))


def test_cadastra_e_busca(browser, live_server, w):
    _login(browser, live_server, w)
    w.until(EC.visibility_of_element_located((By.ID, "f-nome"))).send_keys("Cliente Selenium")
    browser.find_element(By.ID, "f-codigo").send_keys("AA123456789BR")
    browser.find_element(By.ID, "f-email").send_keys("selenium@teste.com")
    browser.find_element(By.ID, "btn-add").click()
    w.until(lambda d: "Cliente Selenium" in d.find_element(By.ID, "lista").text)

    campo = browser.find_element(By.ID, "f-busca")
    campo.clear()
    campo.send_keys("nao-existe-xyz")
    w.until(lambda d: "Cliente Selenium" not in d.find_element(By.ID, "lista").text)
