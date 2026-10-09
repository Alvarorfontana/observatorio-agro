"""Formulario de contacto: validación, canal y envío simulado por Resend."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import contact

OK = {'nombre': 'Juan Pérez', 'correo': 'juan@campo.com.ar', 'mensaje': 'Quiero ver el NDVI de mis potreros.', 'tema': 'demo'}


def test_validation():
    with pytest.raises(ValueError): contact.validate({**OK, 'correo': 'x@'})
    with pytest.raises(ValueError): contact.validate({**OK, 'mensaje': 'corto'})
    with pytest.raises(ValueError): contact.validate({**OK, 'website': 'spam'})
    assert contact.validate({**OK, 'tema': 'raro'})['tema'] == 'consulta'


def test_channel_hides_destination(monkeypatch):
    monkeypatch.setenv('RESEND_API_KEY', 'k'); monkeypatch.setenv('CONTACT_TO', 'yo@dots.ar'); monkeypatch.setenv('CONTACT_WHATSAPP', '+54 9 379 400-0000')
    ch = contact.channel()
    assert ch['email_enabled'] and ch['whatsapp'] == '5493794000000' and 'yo@dots.ar' not in str(ch)


def test_send(monkeypatch):
    monkeypatch.delenv('RESEND_API_KEY', raising=False)
    with pytest.raises(PermissionError): contact.send(OK)
    monkeypatch.setenv('RESEND_API_KEY', 'k'); monkeypatch.setenv('CONTACT_TO', 'yo@dots.ar')
    sent = {}
    class R:
        def raise_for_status(self): pass
        def json(self): return {'id': 'e1'}
    def post(url, json=None, headers=None, timeout=None):
        sent.update(json=json, headers=headers, url=url); return R()
    monkeypatch.setattr(c.SESSION, 'post', post)
    assert contact.send(OK)['status'] == 'enviado'
    assert sent['json']['reply_to'] == OK['correo'] and sent['json']['to'] == ['yo@dots.ar']
    assert 'Pedido de demostración' in sent['json']['subject'] and sent['headers']['Authorization'] == 'Bearer k'


def test_routes(monkeypatch):
    monkeypatch.delenv('RESEND_API_KEY', raising=False)
    from api.index import app
    cl = app.test_client()
    assert cl.get('/api/fuentes/contacto/canal').json['email_enabled'] is False
    assert cl.post('/api/fuentes/contacto', json=OK).status_code == 409
    assert cl.post('/api/fuentes/contacto', json={**OK, 'correo': 'mal'}).status_code == 400
