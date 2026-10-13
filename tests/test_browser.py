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
import time  # noqa: E402
from selenium.common.exceptions import StaleElementReferenceException  # noqa: E402
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


def _clique(browser, el):
    """Clique com fallback JS (evita ElementClickIntercepted por toast/overlay)."""
    try:
        el.click()
    except Exception:
        browser.execute_script("arguments[0].click();", el)


def _login(browser, live_server, w):
    # quando o servidor ja tem admin, o proprio app abre o modal de login
    # (pedirLogin) — so clicamos em "Entrar" se o modal ainda estiver fechado.
    if not browser.find_element(By.ID, "l-email").is_displayed():
        w.until(EC.element_to_be_clickable((By.ID, "btn-login"))).click()
    w.until(EC.visibility_of_element_located((By.ID, "l-email"))).send_keys(EMAIL)
    browser.find_element(By.ID, "l-senha").send_keys(SENHA)
    _clique(browser, browser.find_element(By.ID, "btn-do-login"))
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
    _clique(browser, browser.find_element(By.ID, "btn-add"))
    w.until(lambda d: "Cliente Selenium" in d.find_element(By.ID, "lista").text)

    campo = browser.find_element(By.ID, "f-busca")
    campo.clear()
    campo.send_keys("nao-existe-xyz")
    w.until(lambda d: "Cliente Selenium" not in d.find_element(By.ID, "lista").text)


def _acao(browser, texto, act, tentativas=15):
    """Clica num botao (data-act) do card que contem `texto`, tolerando re-render e overlay."""
    for _ in range(tentativas):
        alvo = None
        try:
            for it in browser.find_elements(By.CSS_SELECTOR, "#lista .item"):
                if texto in it.text:
                    alvo = it.find_element(By.CSS_SELECTOR, f'[data-act="{act}"]')
                    break
        except StaleElementReferenceException:
            alvo = None
        if alvo is not None:
            try:
                alvo.click()
                return True
            except Exception:
                try:
                    browser.execute_script("arguments[0].click();", alvo)
                    return True
                except Exception:
                    pass
        time.sleep(0.3)
    return False


def _tem_botao(browser, texto, act):
    try:
        for it in browser.find_elements(By.CSS_SELECTOR, "#lista .item"):
            if texto in it.text:
                return it.find_element(By.CSS_SELECTOR, f'[data-act="{act}"]').is_displayed()
    except StaleElementReferenceException:
        return False
    return False


def _filtro(browser, valor):
    for c in browser.find_elements(By.CSS_SELECTOR, f'.stat[data-filtro="{valor}"]'):
        try:
            c.click()
        except Exception:
            browser.execute_script("arguments[0].click();", c)
        return True
    return False


def _aceitar_alerta(browser, w):
    w.until(EC.alert_is_present())
    browser.switch_to.alert.accept()


def test_lixeira_exclui_e_restaura(browser, live_server, w):
    """Regressao v25: a lixeira precisa listar os excluidos (antes o card ficava vazio)."""
    _login(browser, live_server, w)
    nome, codigo = "Lixeira Selenium", "BB987654321BR"

    w.until(EC.visibility_of_element_located((By.ID, "f-nome"))).send_keys(nome)
    browser.find_element(By.ID, "f-codigo").send_keys(codigo)
    browser.find_element(By.ID, "f-email").send_keys("lixeira@teste.com")
    _clique(browser, browser.find_element(By.ID, "btn-add"))
    w.until(lambda d: nome in d.find_element(By.ID, "lista").text)

    # exclui -> vai para a lixeira (some da lista normal)
    assert _acao(browser, nome, "del")
    _aceitar_alerta(browser, w)
    w.until(lambda d: nome not in d.find_element(By.ID, "lista").text)

    # abre o card "Lixeira": o envio precisa aparecer e ter o botao Restaurar
    assert _filtro(browser, "excluido")
    w.until(lambda d: nome in d.find_element(By.ID, "lista").text)
    assert _tem_botao(browser, nome, "restaurar")

    # restaura -> sai da lixeira
    assert _acao(browser, nome, "restaurar")
    _aceitar_alerta(browser, w)
    w.until(lambda d: nome not in d.find_element(By.ID, "lista").text)

    # volta para "Todos" e confere que reapareceu entre os ativos
    assert _filtro(browser, "todos")
    w.until(lambda d: nome in d.find_element(By.ID, "lista").text)


def _abrir_usuarios(browser, w):
    btn = w.until(EC.element_to_be_clickable((By.ID, "btn-usuarios")))
    try:
        btn.click()
    except Exception:
        browser.execute_script("arguments[0].click();", btn)
    w.until(EC.visibility_of_element_located((By.ID, "us-lista")))


def _sair_e_entrar(browser, w, email, senha):
    # fecha qualquer modal aberto (a tela de Usuarios fica sobreposta ao login)
    browser.execute_script("document.querySelectorAll('.modal-ov').forEach(m=>{m.hidden=true;});")
    botao = browser.find_element(By.ID, "btn-logout")
    _clique(browser, botao)
    campo = w.until(EC.visibility_of_element_located((By.ID, "l-email")))
    campo.clear()
    campo.send_keys(email)
    senha_campo = browser.find_element(By.ID, "l-senha")
    senha_campo.clear()
    senha_campo.send_keys(senha)
    _clique(browser, browser.find_element(By.ID, "btn-do-login"))
    w.until(EC.invisibility_of_element_located((By.ID, "l-email")))


def test_cria_usuario_nao_admin_pelo_modal(browser, live_server, w):
    """v26: o admin cria um usuario COMUM pela tela de Usuarios (caixa 'admin' desmarcada)
    e esse usuario, ao entrar, nao enxerga a gestao de usuarios."""
    _login(browser, live_server, w)
    w.until(lambda d: d.find_element(By.ID, "btn-usuarios").is_displayed())
    _abrir_usuarios(browser, w)

    nome, email, senha = "Comum Selenium", "comum@teste.com", "comum12345"
    w.until(EC.visibility_of_element_located((By.ID, "us-nome"))).send_keys(nome)
    browser.find_element(By.ID, "us-email").send_keys(email)
    browser.find_element(By.ID, "us-senha").send_keys(senha)
    assert not browser.find_element(By.ID, "us-admin").is_selected()
    browser.find_element(By.ID, "btn-us-criar").click()

    # o novo usuario aparece na lista com o selo de usuario comum (nao admin)
    w.until(lambda d: email in d.find_element(By.ID, "us-lista").text)
    item = next((i for i in browser.find_elements(By.CSS_SELECTOR, "#us-lista .item")
                 if email in i.text), None)
    assert item is not None
    assert "usuário" in item.text

    # entra como o usuario comum: a gestao de usuarios some (nao e admin)
    _sair_e_entrar(browser, w, email, senha)
    w.until(lambda d: not d.find_element(By.ID, "btn-usuarios").is_displayed())
