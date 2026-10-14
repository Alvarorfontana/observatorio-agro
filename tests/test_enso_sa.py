import json
from datetime import date, datetime, timedelta, timezone

import pytest

import enso_sa as sa
import enso_report as er
import enso_chain as ec


def _daily(start, days, val):
    return {'time': [(start + timedelta(days=i)).isoformat() for i in range(days)], 'precipitation_sum': [val] * days}


def test_monthly_and_normals():
    d = _daily(date(1991, 1, 1), 365 * 31 + 8, 2.0)
    mon = sa.monthly_totals(d)
    assert mon[(1991, 1)] == pytest.approx(62)
    n = sa.normals_from(mon)
    assert n[0] == pytest.approx(62) and n[1] == pytest.approx(56.5, abs=1)


def test_window_normal_and_pct():
    normals = [31.0] * 12
    assert sa.window_normal(normals, date(2026, 1, 1), 31) == pytest.approx(31)
    assert sa.pct(150, 100) == 50
    assert sa.pct(3, 2) is None          # normal casi nula: no se informa %


def test_classify():
    assert sa.classify(None, 10) == 'sin referencia'
    assert sa.classify(5, 50) == 'El Niño no cambia mucho acá'
    assert sa.classify(40, 30) == 'ya se nota'
    assert sa.classify(40, -30) == 'por ahora va al revés'
    assert sa.classify(-30, 5) == 'todavía no se nota'


class _R:
    def __init__(self, data): self._d = data
    def json(self): return self._d


def test_live_uses_reference(monkeypatch, tmp_path):
    ref = {'built': '2026-10-08', 'period': '1991-01 a 2026-09',
           'places': {'corrientes': {'normals': [100.0] * 12, 'warm': {'groups': {'El Niño fuerte o muy fuerte': {'n': 5, 'vs_neutral_pct': 57, 'wetter_than_neutral': 5}}},
                                     'cold': {'groups': {}}}}}
    p = tmp_path / 'ref.json'; p.write_text(json.dumps(ref))
    monkeypatch.setattr(sa, 'REF_PATH', str(p))
    monkeypatch.setattr(sa, '_LIVE', {})
    monkeypatch.setattr(sa, '_phase_now', lambda: {'oni': 2.1, 'phase': 'El Niño muy fuerte', 'period': 'sep 2026'})
    monkeypatch.setattr(sa.c, '_now', lambda: datetime(2026, 10, 14, tzinfo=timezone.utc))
    n = len(sa.PLACES)

    def fake_get(url, params=None, timeout=None, **k):
        if 'archive' in url:
            return _R([{'daily': {'precipitation_sum': [5.0] * 90}} for _ in range(n)])
        return _R([{'daily': {'precipitation_sum': [1.0] * 16}} for _ in range(n)])
    monkeypatch.setattr(sa.c, '_get', fake_get)

    class _S:
        def get(self, url, params=None, timeout=None):
            r = fake_get(url, params)
            r.raise_for_status = lambda: None
            return r
    monkeypatch.setattr(sa.c, 'SESSION', _S())
    out = sa.live()['data']
    cor = next(r for r in out['places'] if r['id'] == 'corrientes')
    assert cor['obs90_mm'] == 450 and cor['expected_pct'] == 57
    assert cor['now90_pct'] > 0 and cor['signal'] == 'ya se nota'
    assert cor['next16_mm'] == 16
    assert out['season'] == 'octubre a marzo' and out['reference']['available']
    other = next(r for r in out['places'] if r['id'] == 'lima')
    assert other['signal'] == 'sin referencia' and other['now90_pct'] is None


def test_report_pdf_compiles(monkeypatch):
    steps = [{'n': 1, 'key': 'alisios', 'title': 'Los alisios se debilitan', 'value': -3.0, 'unit': 'desvíos', 'date': 'sep 2026', 'signal': 'Niño',
              'reading': 'Muy debilitados.', 'records': {'since_text': 'el más bajo desde nov 1997'}},
             {'n': 3, 'key': 'superficie', 'title': 'El mar se calienta', 'value': 2.1, 'unit': '°C', 'date': 'sep 2026', 'signal': 'Niño',
              'oni': 2.16, 'phase': 'El Niño muy fuerte', 'reading': '', 'records': {}}]
    monkeypatch.setattr(ec, 'chain', lambda: {'data': {'steps': steps, 'verdict': 'Cadena completa.', 'extras': [{'name': 'Niño 4', 'value': 1.33, 'unit': '°C', 'date': 'sep 2026', 'reading': 'x'}]}})
    seasons = [{'season': f'{y}-{str(y + 1)[2:]}', 'phase': 'El Niño fuerte' if y % 5 == 0 else 'neutral', 'rain_mm': 900 + y, 'anomaly_pct': (y % 7) * 10 - 30} for y in range(1991, 2025)]
    monkeypatch.setattr(ec, 'lot_impact', lambda la, lo: {'data': {'groups': {'El Niño fuerte o muy fuerte': {'n': 6, 'median_mm': 1300, 'vs_neutral_pct': 57, 'wetter_than_neutral': 6},
                                                                          'Neutral': {'n': 15, 'median_mm': 830, 'vs_neutral_pct': 0, 'wetter_than_neutral': 7}},
                                                                'seasons': seasons, 'neutral_base_mm': 830, 'wettest': seasons[:3], 'driest': seasons[-3:],
                                                                'analog_seasons': ['1997-98', '2015-16'], 'reading': 'r', 'method': 'm', 'normals': [100.0] * 12}})
    monkeypatch.setattr(sa, 'point_now', lambda la, lo, n: {'obs90_mm': 380, 'normal90_mm': 300, 'now90_pct': 27, 'obs30_mm': 120, 'normal30_mm': 100, 'now30_pct': 20,
                                                            'next16_mm': 80, 'normal16_mm': 50, 'next16_pct': 60, 'window': {'from': '2026-07-10', 'to': '2026-10-08'}})
    monkeypatch.setattr(sa, 'live', lambda: {'data': {'places': [{'name': p[1], 'country': p[2], 'now90_pct': 10, 'expected_pct': 30, 'next16_mm': 20, 'signal': 'todavía no se nota'} for p in sa.PLACES],
                                                       'counts': {'todavía no se nota': len(sa.PLACES)}, 'season': 'octubre a marzo', 'reference': {'available': True}}})
    d = er.report_data(-27.47, -58.83, 'Corrientes', date(2026, 10, 14))
    assert d['phase'] == 'El Niño muy fuerte' and d['expected'] == '+57 %'
    assert any('drenajes' in a for a in d['advice']) and any('ya se ve' in a for a in d['advice'])
    pdf = er.pdf(-27.47, -58.83, 'Corrientes', date(2026, 10, 14))
    assert pdf[:5] == b'%PDF-'
    open('/tmp/claude-0/-home-claude-observatorio-agro/7430de8f-4cd8-57d3-a5ea-bf5e24ee75bb/scratchpad/enso.pdf', 'wb').write(pdf) if __import__('os').path.isdir('/tmp/claude-0/-home-claude-observatorio-agro/7430de8f-4cd8-57d3-a5ea-bf5e24ee75bb/scratchpad') else None
