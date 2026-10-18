"""Asesor agronómico integrado: módulos puros y endpoints con red simulada."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import crop_water, nitrogen, air, cap, notify


class R:
    def __init__(self, data=None, text=None, status=200):
        self._d, self.text, self.status_code = data, text if text is not None else json.dumps(data), status
        self.headers = {'Content-Type': 'application/json'}
        self.content = self.text.encode()
    @property
    def ok(self): return self.status_code < 400
    def json(self): return self._d
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests; raise requests.HTTPError(str(self.status_code))


def _layer(name, value, d_factor=1):
    return {'name': name, 'unit_measure': {'d_factor': d_factor, 'target_units': 'x'},
            'depths': [{'label': '0-5cm', 'values': {'mean': value}}]}


def fake_get(url, params=None, headers=None, timeout=None, **kw):
    if 'open-meteo.com/v1/forecast' in url:
        return R({'daily': {'time': [f'2026-10-{d:02d}' for d in range(10, 20)],
                            'et0_fao_evapotranspiration': [5.0] * 10,
                            'precipitation_sum': [0, 0, 20, 0, 0, 0, 0, 5, 0, 0]}})
    if 'soilgrids' in url:
        return R({'properties': {'layers': [_layer('wv0033', 3200, 100), _layer('wv1500', 1500, 100),
                                            _layer('soc', 150, 10), _layer('nitrogen', 15, 10)]}})
    if 'air-quality' in url:
        return R({'hourly': {'pm2_5': [35] * 24, 'pm10': [60] * 24, 'ozone': [120] * 24,
                             'nitrogen_dioxide': [30] * 24, 'carbon_monoxide': [200] * 24, 'sulphur_dioxide': [10] * 24}})
    if 'oni.ascii' in url:
        return R(text='SEAS YR TOTAL ANOM\nDJF 2026 26.1 0.2\nSON 2026 27.0 0.7\n', status=200)
    if 'RONI.ascii' in url:
        return R(text='SEAS YR ANOM\nSON 2026 0.6\n', status=200)
    if 'wksst9120' in url:
        return R(text=' 07OCT2026     20.9 0.4     25.9 1.6     28.6 2.1     29.6 1.0\n', status=200)
    if 'ensodisc' in url:
        return R(text='ENSO Alert System Status: El Niño Advisory', status=200)
    return R({}, status=404)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(c.SESSION, 'get', fake_get)
    monkeypatch.delenv('NTFY_TOPIC', raising=False)
    from api.index import app
    return app.test_client()


def test_kc_and_taw():
    assert crop_water.kc_for_day('maiz', 0) == 0.30
    assert crop_water.kc_for_day('maiz', 60) == 1.20
    assert crop_water.stage('maiz', 0)['name'] == 'inicial'
    assert crop_water.taw_mm(32, 15, 1.0) == 170


def test_crop_water_advise():
    a = crop_water.advise('maiz', '2026-09-01', [5.0] * 7, [0] * 7, theta_fc=32, theta_wp=15)
    assert a['etc_total_mm'] > 0 and a['net_irrigation_mm'] == round(a['etc_total_mm'], 1)
    assert a['taw_mm'] == 170 and a['raw_mm'] == round(0.55 * 170)


def test_nitrogen_recommend():
    assert nitrogen.organic_n_kg_ha(15) == 5850
    assert nitrogen.mineralization(15) == 103
    r = nitrogen.recommend('maiz', 8, soc_gkg=15, prev_crop='soja')
    assert r['demand_kg_ha'] == 200 and r['dose_kg_ha'] == 122 and r['urea_kg_ha'] == 265
    leg = nitrogen.recommend('soja', 4)
    assert leg['dose_kg_ha'] == 0 and 'fija nitrógeno' in leg['reading']


def test_air_evaluate():
    a = air.evaluate({'pm2_5': 35, 'pm10': 60, 'ozone': 120, 'nitrogen_dioxide': 30,
                      'carbon_monoxide': 200, 'sulphur_dioxide': 10})
    assert a['index'] == 68 and a['category'] == 'mala'
    assert 'part' in a['reading']
    o = air.evaluate({'ozone': 130})
    assert o['index'] == 60 and o['category'] == 'moderada' and 'ozono' in o['reading']
    assert air.sub_index(0, air.BREAKPOINTS['pm2_5']) == 0


def test_cap_xml():
    alerts = [{'key': 'helada', 'level': 'alta', 'title': 'Helada probable', 'detail': 'mínima bajo 0 °C',
               'source': 'Conjuntos ECMWF', 'action': 'Proteger aguadas', 'when': '2026-10-12'}]
    xml = cap.to_xml(alerts, -28.5, -59.0)
    assert xml.startswith('<?xml') and '<alert' in xml and '<severity>Severe</severity>' in xml and 'urn:oasis' in xml
    assert 'Fire' == cap.alert_to_info({'key': 'fuego', 'level': 'media'})['category']


def test_notify_requires_topic(monkeypatch):
    monkeypatch.delenv('NTFY_TOPIC', raising=False)
    with pytest.raises(ValueError):
        notify.ntfy('t', 'm')


def test_notify_sends(monkeypatch):
    monkeypatch.setenv('NTFY_TOPIC', 'dots-test')
    seen = {}
    def post(url, data=None, headers=None, timeout=None, **kw):
        seen['url'], seen['headers'] = url, headers
        return R({}, status=200)
    monkeypatch.setattr(c.SESSION, 'post', post)
    out = notify.ntfy('Aviso', 'helada mañana', priority=4, tags=['snowflake'])
    assert out['status'] == 'enviado' and seen['url'].endswith('/dots-test') and seen['headers']['Priority'] == '4'


def test_advisor_endpoint(client):
    r = client.post('/api/fuentes/asesor', json={'lat': -28.507, 'lon': -59.043, 'crop': 'maiz',
                                                 'sowing': '2026-09-01', 'yield_t_ha': 8, 'prev_crop': 'soja'})
    assert r.status_code == 200
    d = r.get_json()
    assert d['status'] == 'recibido'
    assert d['data']['agua']['net_irrigation_mm'] is not None
    assert d['data']['nitrogeno']['dose_kg_ha'] is not None
    assert d['data']['aire']['index'] is not None
    assert d['data']['enso']['phase'] == 'El Niño'
    assert d['data']['lectura']


def test_alerts_cap_endpoint(client):
    r = client.post('/api/fuentes/alertas/cap', json={'lat': -28.5, 'lon': -59.0,
                    'alerts': [{'key': 'lluvia', 'level': 'alta', 'title': 'Lluvia intensa', 'detail': '80 mm',
                                'source': 'Open-Meteo', 'action': 'Mover hacienda'}]})
    assert r.status_code == 200 and r.mimetype == 'application/cap+xml'
    assert b'<alert' in r.data and b'Severe' in r.data


def test_notify_endpoint(client):
    assert client.post('/api/fuentes/notificar', json={'title': 'x', 'message': 'y'}).status_code == 409
