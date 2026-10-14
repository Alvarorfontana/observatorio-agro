import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import whisp_eudr as w


def test_sin_clave(monkeypatch):
    monkeypatch.delenv('WHISP_API_KEY', raising=False)
    r = w.check({'type': 'FeatureCollection', 'features': []})
    assert r['data']['status'] == 'requiere credencial' and 'WHISP_API_KEY' in r['data']['missing_env']


def test_resumen():
    s = w.summarize({'risk_acrop': 'low', 'EUFO_2020': 0, 'Ind_01_treecover': 'no', 'Ind_04_disturbance_after_2020': 'no'}, 'soja')
    assert s['risk'] == 'low' and 'riesgo bajo' in s['text'] and 'Ningún mapa' in s['text']
    s = w.summarize({'risk_acrop': 'high', 'EUFO_2020': 12.5, 'Area': 50, 'Ind_01_treecover': 'yes', 'Ind_04_disturbance_after_2020': 'yes'})
    assert s['risk'] == 'high' and '12.5 ha (25.0 % del lote)' in s['text'] and 'después de 2020' in s['text']


def test_flujo_async(monkeypatch):
    monkeypatch.setenv('WHISP_API_KEY', 'k')
    class R:
        def __init__(s, j, code=200): s._j, s.status_code, s.content, s.ok = j, code, b'x', code < 400
        def json(s): return s._j
    calls = []
    def post(u, json=None, headers=None, timeout=None):
        calls.append(('post', u, json['analysisOptions'], headers['X-API-KEY'])); return R({'code': 'analysis_queued', 'data': {'token': 't1'}}, 202)
    seq = [R({'code': 'analysis_processing'}), R({'code': 'analysis_completed', 'data': {'type': 'FeatureCollection', 'features': [{'properties': {'risk_acrop': 'low'}}]}})]
    monkeypatch.setattr(w.c.SESSION, 'post', post)
    monkeypatch.setattr(w.c.SESSION, 'get', lambda u, **k: seq.pop(0))
    monkeypatch.setattr('time.sleep', lambda s: None)
    r = w.check({'type': 'FeatureCollection', 'features': []}, product='soja')
    assert r['status'] == 'recibido' and r['data']['risk'] == 'low' and r['data']['token'] == 't1'
    assert calls[0][2]['async'] is True and calls[0][3] == 'k'
