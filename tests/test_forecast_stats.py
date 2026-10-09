"""Estadística y pronóstico probabilístico con datos controlados."""
import os, sys, random
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import forecast_stats as fs


def era_rows(y0=1991, y1=2025, warming=0.08):
    random.seed(3); rows = []
    d = date(y0, 1, 1)
    import math
    while d <= date(y1, 12, 31):
        s = math.cos((d.timetuple().tm_yday - 15) / 365 * 2 * math.pi)
        tx = 26 + 9 * s + random.gauss(0, 2) + warming * (d.year - y0)
        tn = 13 + 8 * s + random.gauss(0, 3)
        pr = random.expovariate(1 / 15) if random.random() < 0.2 else 0.0
        rows.append((d, tx, tn, (tx + tn) / 2, pr)); d += timedelta(days=1)
    return rows


def test_quantile_and_mk():
    assert fs.quantile([1, 2, 3, 4], .5) == 2.5 and fs.quantile([], .5) is None
    s, z, p = fs.mann_kendall(list(range(20)))
    assert s > 0 and p < 0.001
    s, z, p = fs.mann_kendall([5, 3, 5, 3, 5, 3, 5, 3, 5, 3])
    assert p > 0.3
    assert fs.sen_slope(list(range(2000, 2010)), [2 * i for i in range(10)]) == 2


def test_climatology_and_trends():
    rows = era_rows()
    clim = fs.climatology(rows)
    jul = next(m for m in clim if m['month'] == 7); ene = next(m for m in clim if m['month'] == 1)
    assert jul['p_frost'] > ene['p_frost'] and ene['heat_days'] > jul['heat_days']
    assert jul['rain_p33'] <= jul['rain_med'] <= jul['rain_p67']
    tr = {t['key']: t for t in fs.trends(rows)}
    assert tr['tx']['per_decade'] > 0.5 and tr['tx']['significant']
    assert 'aumenta' in tr['tx']['reading']


def test_ensemble_probabilities(monkeypatch):
    t = [f'2026-10-{d:02d}' for d in range(10, 25)]
    daily = {'time': t}
    for m in range(10):
        sfx = '' if m == 0 else f'_member{m:02d}'
        daily['temperature_2m_min' + sfx] = [(-1 if m < 4 else 5) for _ in t]   # 40 % helada
        daily['temperature_2m_max' + sfx] = [(36 if m < 2 else 30) for _ in t]   # 20 % calor
        daily['precipitation_sum' + sfx] = [(12 if m < 5 else 0) for _ in t]     # 50 % lluvia ≥ 10
    monkeypatch.setattr(c, 'external', lambda url, params=None, **k: c.envelope({'daily': daily}, url, 's', 'o'))
    e = fs.ensemble_probs(-28.5, -59)
    d0 = e['days'][0]
    assert e['members'] == 10 and d0['p_frost'] == 40 and d0['p_heat35'] == 20 and d0['p_rain10'] == 50
    assert e['week_rain']['p_ge20'] == 50


def test_seasonal_terciles(monkeypatch):
    rows = era_rows()
    clim = fs.climatology(rows)
    monkeypatch.setattr(c, '_now', lambda: __import__('datetime').datetime(2026, 10, 9))
    t = []; d = date(2026, 10, 1)
    while d <= date(2027, 3, 31):
        t.append(d.isoformat()); d += timedelta(days=1)
    daily = {'time': t}
    for m in range(20):
        sfx = '' if m == 0 else f'_member{m:02d}'
        daily['precipitation_sum' + sfx] = [12.0 for _ in t]     # muy lluvioso
        daily['temperature_2m_mean' + sfx] = [10.0 for _ in t]    # muy fresco
    monkeypatch.setattr(c, 'external', lambda url, params=None, **k: c.envelope({'daily': daily}, url, 's', 'o'))
    out = fs.seasonal_outlook(-28.5, -59, clim)
    assert out[0]['period'] == 'nov 2026' and len(out) == 5
    assert out[0]['rain']['above'] == 100 and out[0]['rain_reading'] == 'más lluvioso que lo normal'
    assert out[0]['temp_reading'] == 'más fresco que lo normal'
