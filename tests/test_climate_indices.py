"""Índices agroclimáticos y teleconexiones NOAA PSL con datos controlados."""
import json, os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import climate_indices as ci


def days_of(year, tx=25.0, tn=12.0, pr=0.0, overrides=None):
    d0 = date(year, 1, 1); out = []
    n = 366 if year % 4 == 0 else 365
    for i in range(n):
        d = d0 + timedelta(days=i)
        row = {'date': d.isoformat(), 'tx': tx, 'tn': tn, 'tg': (tx + tn) / 2, 'pr': pr}
        if overrides and d.isoformat() in overrides:
            row.update(overrides[d.isoformat()])
        out.append(row)
    return out


def test_year_indices_definitions():
    o = {}
    # 3 heladas en invierno austral
    for dd in ('2023-06-10', '2023-07-02', '2023-08-20'):
        o[dd] = {'tn': -2.0}
    # ola de calor de 4 días + un día suelto de 36
    for dd in ('2023-01-10', '2023-01-11', '2023-01-12', '2023-01-13', '2023-02-01'):
        o[dd] = {'tx': 36.0, 'tn': 22.0}
    # lluvias: 5 días seguidos de 10 mm y un día de 40 mm
    for k in range(5):
        o[f'2023-03-{10 + k:02d}'] = {'pr': 10.0}
    o['2023-04-01'] = {'pr': 40.0}
    ix = ci.year_indices(days_of(2023, overrides=o))
    assert ix['frost_days'] == 3 and ix['first_frost'] == '2023-06-10' and ix['last_frost'] == '2023-08-20'
    assert ix['tx35'] == 5 and ix['tx30'] == 5 and ix['heat_waves'] == 1
    assert ix['tropical_nights'] == 5
    assert ix['prcptot'] == 90.0 and ix['wetdays'] == 6 and ix['r20mm'] == 1
    assert ix['rx1day'] == 40.0 and ix['rx5day'] == 50.0
    assert ix['cwd'] == 5 and ix['sdii'] == 15.0
    # racha seca más larga: del 2 de abril al 31 de diciembre
    assert ix['cdd'] == (date(2023, 12, 31) - date(2023, 4, 2)).days + 1
    # GDD base 10 con media 18.5 la mayor parte del año
    assert ix['gdd10'] > 3000


def test_agro_indices_anomaly(monkeypatch):
    def fake_external(url, params=None, **kw):
        assert params['models'] == 'era5'
        t, tx, tn, tg, pr = [], [], [], [], []
        for y in (2022, 2023, 2024, 2025):
            for d in days_of(y, pr=2.0 if y < 2025 else 0.0):
                t.append(d['date']); tx.append(d['tx']); tn.append(d['tn']); tg.append(d['tg']); pr.append(d['pr'])
        return c.envelope({'daily': {'time': t, 'temperature_2m_max': tx, 'temperature_2m_min': tn,
                                     'temperature_2m_mean': tg, 'precipitation_sum': pr}}, url, 's', 'o')
    monkeypatch.setattr(c, 'external', fake_external)
    monkeypatch.setattr(c, '_now', lambda: __import__('datetime').datetime(2026, 10, 9))
    d = ci.agro_indices(-28.5, -59.0, 4)['data']
    assert d['period'] == [2022, 2025] and d['last_year'] == 2025
    assert d['years'][-1]['prcptot'] == 0 and d['anomaly_last_year']['prcptot'] < -500
    assert {x['key'] for x in d['catalog']} >= {'frost_days', 'rx5day', 'cdd'}
    with pytest.raises(ValueError):
        ci.agro_indices(-28.5, -59.0, 50)


PSL_TXT = """ 2024 2026
 2024  1.80  1.50  1.10  0.70  0.20 -0.10 -0.20 -0.30 -0.40 -0.50 -0.60 -0.70
 2025 -0.70 -0.60 -0.40 -0.20  0.00  0.10  0.20  0.30  0.40  0.50  0.60  0.80
 2026  0.90  0.95  1.00  1.10 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99
  -99.99
  Nino 3.4 SST anomaly
"""


def test_parse_psl_skips_missing():
    s = ci.parse_psl(PSL_TXT)
    assert s[-1] == (2026, 4, 1.10) and len(s) == 28


def test_phases():
    assert ci.phase('nino34', 1.1) == 'Niño' and ci.phase('oni', -0.6) == 'Niña' and ci.phase('meiv2', 0.2) == 'Neutro'
    assert ci.phase('soi', -1.2) == 'tipo Niño' and ci.phase('aao', -0.3) == 'negativo'


def test_psl_indices_consensus(monkeypatch):
    class R:
        def __init__(self, t): self.text = t
    def get(url, params=None, headers=None, timeout=20):
        if 'pdo' in url:
            raise RuntimeError('caída')
        return R(PSL_TXT)
    monkeypatch.setattr(c, '_get', get)
    env = ci.psl_indices()
    d = env['data']
    assert env['status'] == 'recibido' and d['enso_consensus'] == 'Niño' and d['enso_agreement'] == '3/3'
    assert d['indices']['pdo']['status'] == 'sin dato'
    assert d['indices']['nino34']['data']['period'] == 'abr 2026'
    assert len(d['indices']['aao']['data']['last12']) == 12
