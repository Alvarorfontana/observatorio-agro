"""yield_forecast: rendimiento esperado por agua (FAO-33) — balance, fuentes, ensamblado, escalas, tema y endpoint."""
import os, sys
from datetime import date, datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import scales, temas, yield_forecast as yf

TODAY = datetime(2026, 10, 19, tzinfo=timezone.utc)


class R:
    def __init__(self, data=None, status=200):
        self._d, self.status_code = data, status
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        return self._d


def daily(start, end, et0, rain):
    """daily de Open-Meteo para [start, end] con ET0 y lluvia constantes."""
    n = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    return {'time': [(date.fromisoformat(start) + timedelta(days=i)).isoformat() for i in range(n)],
            'et0_fao_evapotranspiration': [et0] * n, 'precipitation_sum': [rain] * n}


def soil_env(fc=0.32, wp=0.14):
    def layer(name, val):
        return {'name': name, 'unit_measure': {'d_factor': 1},
                'depths': [{'label': '0-5cm', 'values': {'mean': val}}, {'label': '5-15cm', 'values': {'mean': val}}]}
    return {'status': 'recibido', 'data': {'properties': {'layers': [layer('wv0033', fc), layer('wv1500', wp)]}}}


def season(crop, et0, rain):
    return [{'date': f'2026-01-{i + 1:02d}', 'et0': et0, 'rain': rain, 'source': 'observado'}
            for i in range(yf.season_days(crop))]


@pytest.fixture
def client(monkeypatch):
    from api.index import app
    return app.test_client()


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(c, '_now', lambda: TODAY)


# ── parámetros del cultivo ──
def test_ky_and_season():
    assert yf.ky_for('maiz') == 1.25 and yf.ky_for('soja') == 0.85
    assert yf.ky_for('cultivo_desconocido') == 1.0
    assert yf.season_days('maiz') == 130 and yf.season_days('pastura') == 365


# ── balance hídrico y FAO-33 ──
def test_balance_with_plenty_of_water_reaches_potential():
    bal = yf.water_balance('maiz', season('maiz', 5.0, 20.0), 0.32, 0.14)
    assert bal['relative_yield_pct'] == 100.0 and bal['water_deficit_mm'] == 0.0
    assert bal['taw_mm'] == 180 and bal['ky'] == 1.25


def test_balance_dry_lowers_yield():
    wet = yf.water_balance('maiz', season('maiz', 5.0, 8.0), 0.32, 0.14)
    dry = yf.water_balance('maiz', season('maiz', 5.0, 0.0), 0.32, 0.14)
    assert wet['relative_yield_pct'] == 100.0
    assert dry['relative_yield_pct'] < wet['relative_yield_pct'] and dry['water_deficit_mm'] > 0


def test_balance_without_soil_raises():
    with pytest.raises(ValueError):
        yf.water_balance('maiz', season('maiz', 5.0, 1.0), None, None)


# ── ensamblado de la serie diaria (observado / pronóstico / climatología) ──
def test_assemble_days_sources():
    obs = {d.isoformat(): (5.0, 1.0) for d in (date(2026, 10, 1) + timedelta(days=i) for i in range(13))}
    fc = {d.isoformat(): (4.0, 2.0) for d in (date(2026, 10, 14) + timedelta(days=i) for i in range(6))}
    days = yf.assemble_days(date(2026, 10, 1), 20, obs, fc, {}, TODAY)
    by = {d['date']: d for d in days}
    assert by['2026-10-05']['source'] == 'observado' and by['2026-10-05']['et0'] == 5.0
    assert by['2026-10-15']['source'] == 'pronostico' and by['2026-10-15']['et0'] == 4.0
    assert by['2026-10-20']['source'] == 'climatologia' and by['2026-10-20']['et0'] == 0.0


# ── analyze ──
def test_analyze_without_sowing_sin_dato(frozen, monkeypatch):
    monkeypatch.setattr(c, 'soil_full', lambda lat, lon: soil_env())
    out = yf.analyze(-28.5, -59.0, 'maiz', None)
    assert out['status'] == 'sin dato' and 'siembra' in out['error']


def test_analyze_without_soil_sin_dato(frozen, monkeypatch):
    monkeypatch.setattr(c, 'soil_full', lambda lat, lon: {'status': 'sin dato', 'data': None})
    out = yf.analyze(-28.5, -59.0, 'maiz', '2026-06-01')
    assert out['status'] == 'sin dato' and 'SoilGrids' in out['error']


def test_analyze_past_season_uses_observed(frozen, monkeypatch):
    monkeypatch.setattr(c, 'soil_full', lambda lat, lon: soil_env())
    monkeypatch.setattr(yf, '_archive', lambda lat, lon, start, end: daily(start, end, 5.0, 8.0))
    monkeypatch.setattr(yf, '_forecast', lambda lat, lon: {})
    monkeypatch.setattr(yf, '_climatology', lambda lat, lon, today: {})
    out = yf.analyze(-28.5, -59.0, 'maiz', '2026-06-01', 5.0)
    d = out['data']
    assert out['status'] == 'recibido' and d['crop_name'] == 'Maíz'
    assert d['relative_yield_pct'] == 100.0 and d['expected_t_ha'] == 5.0
    assert d['scale']['tone'] == 'ok' and '% del potencial' in d['reading']
    assert all(x['source'] == 'observado' for x in d['days'])


def test_analyze_future_season_uses_climatology(frozen, monkeypatch):
    monkeypatch.setattr(c, 'soil_full', lambda lat, lon: soil_env())
    monkeypatch.setattr(yf, '_archive', lambda lat, lon, start, end: daily(start, end, 5.0, 8.0))
    monkeypatch.setattr(yf, '_forecast', lambda lat, lon: daily('2026-10-13', '2026-10-28', 5.0, 8.0))
    monkeypatch.setattr(yf, '_climatology', lambda lat, lon, today: {d: (5.0, 8.0) for d in range(1, 367)})
    out = yf.analyze(-28.5, -59.0, 'maiz', '2026-10-01')
    d = out['data']
    assert out['status'] == 'recibido' and d['relative_yield_pct'] == 100.0
    assert any(x['source'] == 'climatologia' for x in d['days'])


# ── escalas y tema ──
def test_yield_scale_and_theme():
    assert 'yield_pct' in scales.ids() and scales.describe('yield_pct')['max'] == 100.0
    assert scales.band('yield_pct', 40)['tone'] == 'risk'
    assert scales.band('yield_pct', 60)['tone'] == 'warn'
    assert scales.band('yield_pct', 80)['tone'] == 'ok'
    assert 'rendimiento' in temas.ids()
    rend = next(t for t in temas.catalog() if t['id'] == 'rendimiento')
    assert rend['group'] == 'Cultivo' and rend['scope'] == 'punto' and rend['scale'] == 'yield_pct'


def test_tema_rendimiento_needs_sowing():
    out = temas.resolve('rendimiento', -31.0, -60.0, {})
    assert out['status'] == 'sin dato' and 'siembra' in out['error']


def test_tema_rendimiento_resolves(monkeypatch):
    monkeypatch.setattr(yf, 'analyze', lambda lat, lon, crop, sow, pot: c.envelope({'relative_yield_pct': 80}, 'u', 's', 'o'))
    out = temas.resolve('rendimiento', -31.0, -60.0, {'crop': 'soja', 'sowing': '2026-06-01'})
    assert out['status'] == 'recibido' and out['data']['relative_yield_pct'] == 80
    assert out['id'] == 'rendimiento' and out['scale'] == 'yield_pct'


# ── endpoint ──
def test_rendimiento_endpoint(client, monkeypatch):
    monkeypatch.setattr(yf, 'analyze', lambda lat, lon, crop, sow, pot: c.envelope({'relative_yield_pct': 75}, 'u', 's', 'o'))
    r = client.get('/api/fuentes/rendimiento?lat=-31&lon=-60&crop=soja&sowing=2026-06-01')
    assert r.status_code == 200 and r.get_json()['data']['relative_yield_pct'] == 75


def test_rendimiento_endpoint_bad_coords(client):
    assert client.get('/api/fuentes/rendimiento').status_code == 400
