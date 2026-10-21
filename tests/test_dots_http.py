import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import dots_http  # noqa: E402


def _resp(url, status=200, kind='application/json', body=b'{}'):
    r = requests.Response()
    r.url, r.status_code, r._content = url, status, body
    r.headers['Content-Type'] = kind
    return r


def test_login_de_vercel_se_detecta():
    r = _resp('https://vercel.com/login', kind='text/html', body=b'<html>Login - Vercel</html>')
    assert dots_http.protegido(r)
    with pytest.raises(dots_http.SitioProtegido):
        dots_http.check(r)


def test_api_json_pasa():
    r = _resp(dots_http.SITE + '/api/fuentes/alertas-resumen')
    assert dots_http.check(r) is r


def test_html_donde_se_espera_json_falla():
    r = _resp(dots_http.SITE + '/api/fuentes/alertas-resumen', kind='text/html', body=b'<html></html>')
    with pytest.raises(ValueError):
        dots_http.check(r)


def test_newsletter_html_permitido():
    r = _resp(dots_http.SITE + '/api/fuentes/newsletter-temas', kind='text/html', body=b'<html></html>')
    assert dots_http.check(r, expect='html') is r


def test_secreto_de_bypass_va_en_el_encabezado(monkeypatch):
    monkeypatch.setattr(dots_http, 'BYPASS', 'abc')
    assert dots_http.session().headers['x-vercel-protection-bypass'] == 'abc'
