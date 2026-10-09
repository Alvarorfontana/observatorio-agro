"""Producción de pasto (Monteith) y carga."""
import os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import forage as fg

SER = [{'status': 'válida', 'ndvi_mean': 0.6, 'datetime': '2026-08-01T13:00:00Z'},
       {'status': 'nublada'},
       {'status': 'válida', 'ndvi_mean': 0.7, 'datetime': '2026-09-30T13:00:00Z'}]
RAD = {date(2026, 8, 1) + timedelta(days=i): 20.0 for i in range(70)}


def test_fpar_bounds():
    assert fg.fpar(0) == 0 and fg.fpar(0.9) == 0.95 and abs(fg.fpar(0.5) - 0.6) < 1e-9


def test_interpolation():
    d = fg.interpolate([(date(2026, 1, 1), 0.2), (date(2026, 1, 11), 0.4)], [date(2026, 1, 6), date(2026, 1, 20)])
    assert abs(d[date(2026, 1, 6)] - 0.3) < 1e-9 and d[date(2026, 1, 20)] == 0.4


def test_estimate_math():
    e = fg.estimate(SER, RAD, area_ha=100, kind='pastizal', use=0.5, heads=60)
    # al final NDVI 0,7 → fPAR 0,85; RFA 9,6; EUR 0,4 → 32,6 kg MS/ha/día
    assert abs(e['daily'][-1]['ppna'] - 32.6) < 0.1
    assert 25 < e['growth_rate_30d'] < 33
    assert e['ev_ha'] == round(e['growth_rate_30d'] * 0.5 / 10, 2)
    assert e['current_load_ev_ha'] == 0.6 and 'carga' in e['load_balance']
    assert e['monthly'][0]['month'] == '2026-08'


def test_errors():
    with pytest.raises(ValueError): fg.estimate(SER[:1], RAD, 10)
    with pytest.raises(ValueError): fg.estimate(SER, RAD, 10, kind='x')
    with pytest.raises(ValueError): fg.estimate(SER, RAD, 10, use=0.95)
    with pytest.raises(ValueError): fg.estimate(SER, {}, 10)
