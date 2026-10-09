"""CHIRPS por ClimateSERV (red simulada) y SPI empírico."""
import os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import rainfall as rain

LOT = [[-28.51, -59.05], [-28.51, -59.03], [-28.49, -59.03], [-28.49, -59.05]]


def synthetic(last_year_factor=0.3, years=(1991, 2025)):
    """Lluvia diaria: 3 mm/día salvo el último año (más seco)."""
    out = {}
    d = date(years[0], 1, 1)
    while d <= date(years[1], 12, 31):
        base = 3.0 + (d.year % 7) * 0.2
        out[d] = base * (last_year_factor if d.year == years[1] else 1.0)
        d += timedelta(days=1)
    return out


def test_parse_series_formats():
    p = {'data': [{'date': '01/02/2024', 'value': {'avg': 4.2}}, {'date': '01/03/2024', 'value': {'avg': -9999}},
                  {'date': '2024-01-04', 'value': 1.5}, {'date': 'x', 'value': 2}]}
    s = rain.parse_series(p)
    assert s == {date(2024, 1, 2): 4.2, date(2024, 1, 4): 1.5}


def test_spi_dry_year_detected():
    a = rain.analyze(synthetic())
    assert a['last_month'] == '2025-12'
    s12 = a['spi']['12']
    assert s12['spi'] < -1.5 and 'sequía' in s12['class']
    assert len(a['recent']) == 12 and a['recent'][-1]['anomaly'] < 0
    assert a['annual'][-1]['year'] == 2025


def test_spi_normal_and_wet():
    a = rain.analyze(synthetic(1.0))
    assert a['spi']['3']['class'] in ('normal', 'húmedo', 'muy húmedo')
    w = rain.analyze(synthetic(2.0))
    assert w['spi']['12']['spi'] > 1.5


def test_spi_class_thresholds():
    assert rain.spi_class(-2.1) == 'sequía extrema' and rain.spi_class(-1.2) == 'sequía moderada'
    assert rain.spi_class(0.2) == 'normal' and rain.spi_class(1.7) == 'muy húmedo'
    assert abs(rain._spi_from_p(0.5)) < 1e-6 and rain._spi_from_p(0.16) < -0.9


def test_job_flow(monkeypatch):
    calls = []
    class R:
        def __init__(self, text=None, data=None): self.text = text; self._d = data
        def json(self): return self._d
    daily = synthetic()
    payload = {'data': [{'date': d.strftime('%m/%d/%Y'), 'value': {'avg': v}} for d, v in daily.items()]}
    state = {'p': 40}
    def get(url, params=None, headers=None, timeout=20):
        calls.append(url)
        if url.endswith('/submitDataRequest/'):
            assert '"Polygon"' in params['geometry'] and params['datatype'] == 0
            return R(text='["abc-123"]')
        if url.endswith('/getDataRequestProgress/'):
            return R(text=f"[{state['p']}]")
        return R(data=payload)
    monkeypatch.setattr(c, '_get', get)
    assert rain.start(LOT)['data']['job'] == 'abc-123'
    assert rain.result('abc-123')['data']['progress'] == 40
    state['p'] = 100
    d = rain.result('abc-123')['data']
    assert d['status'] == 'listo' and d['spi']['12']['class'].startswith('sequía')
    with pytest.raises(ValueError):
        rain.result('../x')
