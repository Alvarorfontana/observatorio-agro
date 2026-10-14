import importlib.util, os

spec = importlib.util.spec_from_file_location('avisos', os.path.join(os.path.dirname(__file__), '..', 'scripts', 'avisos.py'))
av = importlib.util.module_from_spec(spec); spec.loader.exec_module(av)


def test_changes_and_text():
    prev = {'parana-goya': {'level': 'Atención'}, 'parana-corrientes': {'level': 'Normal'}}
    st = [{'id': 'parana-goya', 'place': 'Goya', 'river': 'Paraná', 'level': 'Alerta', 'height': 5.31, 'alert': 5.2, 'evac': 5.7, 'date': '2026-10-14', 'trend_m_day': 0.04},
          {'id': 'parana-corrientes', 'place': 'Corrientes', 'river': 'Paraná', 'level': 'Normal', 'height': 3.1},
          {'id': 'nuevo', 'place': 'X', 'river': 'Y', 'level': 'Alerta'}]
    ch = av.changes(prev, st)
    assert len(ch) == 1 and ch[0]['to'] == 'Alerta' and ch[0]['up']
    t = av.text(ch[0])
    assert 'Goya (río Paraná): el nivel sube de Atención a Alerta' in t and '5,31 m' in t and '+0,04' in t


def test_unconfigured_channels(monkeypatch):
    for k in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'RESEND_API_KEY', 'RESEND_AUDIENCE_ID'):
        monkeypatch.delenv(k, raising=False)
    assert av.telegram(['x']) == 'sin configurar' and av.email(['x'], 'y') == 'sin configurar'


def test_feed_rss_and_subscribe(monkeypatch, tmp_path):
    import json, avisos_web as aw
    f = tmp_path / 'a.json'
    f.write_text(json.dumps({'updated': 'x', 'items': [{'id': 'parana-goya', 'place': 'Goya', 'to': 'Alerta', 'text': 'Goya <sube>', 'at': '2026-10-14T18:00'}]}))
    monkeypatch.setattr(aw, 'FEED', str(f))
    d = aw.feed()
    assert d['items'][0]['place'] == 'Goya' and aw.feed('otra')['items'] == []
    x = aw.rss(d)
    assert '<title>Goya: Alerta</title>' in x and '&lt;sube&gt;' in x
    monkeypatch.delenv('RESEND_API_KEY', raising=False)
    assert aw.subscribe({'email': 'a@b.com'})['status'] == 'sin configurar'
    import pytest
    with pytest.raises(ValueError):
        aw.subscribe({'email': 'malo'})
