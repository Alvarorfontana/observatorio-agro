"""Cadena de El Niño con archivos en el formato real de NOAA CPC y PSL."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import research_connectors as c
import enso_chain as ec

CPAC = """850 MB TRADE WIND INDEX(175W-140W)5N 5S  CENTRAL PACIFIC
                    ORIGINAL        DATA
YEAR   JAN   FEB   MAR   APR   MAY   JUN   JUL   AUG   SEP   OCT   NOV   DEC
2026   9.0   9.1   9.2   8.0   7.0   6.0   5.0   4.0   3.0-999.9-999.9-999.9
                    STANDARDIZED    DATA
YEAR   JAN   FEB   MAR   APR   MAY   JUN   JUL   AUG   SEP   OCT   NOV   DEC
2026   0.4   1.0   0.6  -0.1  -0.6  -1.6  -2.4  -2.5  -3.0-999.9-999.9-999.9
2027-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9
"""
HEAT = """ YR MON  130E-80W  160E-80W  180W-100W
2026    8      2.19      2.77       3.23
2026    9      2.23      2.93       3.39
"""


def test_parse_cpc_fixed_width_and_sections():
    s = ec.parse_cpc(CPAC)
    assert s['STANDARDIZED'][-1] == (2026, 9, -3.0) and s['ORIGINAL'][0] == (2026, 1, 9.0)
    assert all(v > -999 for _, _, v in s['STANDARDIZED'])


def test_parse_heat():
    assert ec.parse_heat(HEAT)[-1] == (2026, 9, 3.39)


def test_phase():
    assert ec.phase(2.2) == 'El Niño muy fuerte' and ec.phase(0.2) == 'neutral' and ec.phase(-1.1) == 'La Niña moderada'


def test_chain(monkeypatch):
    class R:
        def __init__(self, t): self.text = t
    def get(url, params=None, headers=None, timeout=None):
        return R(HEAT if 'heat_content' in url else CPAC)
    monkeypatch.setattr(c, '_get', get)
    monkeypatch.setattr(ec, 'psl_series', lambda k: [(2026, 8, {'nino34': 2.5, 'oni': 2.0, 'nino12': 3.5, 'soi': -1.5, 'meiv2': 2.0}[k]),
                                                     (2026, 9, {'nino34': 3.0, 'oni': 2.2, 'nino12': 3.9, 'soi': -2.0, 'meiv2': 2.4}[k])])
    d = ec.chain()['data']
    assert [s['key'] for s in d['steps']] == ['alisios', 'calor', 'superficie', 'atmosfera']
    assert d['steps'][0]['value'] == -3.0 and d['steps'][1]['value'] == 3.39
    assert d['steps'][2]['phase'] == 'El Niño muy fuerte' and 'completa' in d['verdict']


def test_impact_from():
    mon = {}
    phases = {}
    for y in range(1991, 2025):
        strong = y in (1997, 2015, 2023)
        phases[y] = (2.0, 'El Niño muy fuerte') if strong else (0.0, 'neutral')
        for m in range(1, 13):
            mon[(y, m)] = 100
    for m in range(1, 13): mon[(2025, m)] = 100
    for y in (1997, 2015, 2023):
        for m in (10, 11, 12): mon[(y, m)] = 150
        for m in (1, 2, 3): mon[(y + 1, m)] = 150
    out = ec.impact_from(mon, phases)
    g = out['groups']['El Niño fuerte o muy fuerte']
    assert g['n'] == 3 and g['vs_neutral_pct'] == 50 and g['wetter_than_neutral'] == 3
    assert out['analog_seasons'] == ['1997-98', '2015-16', '2023-24'] and '+50 %' in out['reading']


def test_records_since():
    rows = [(1997, 11, 2.6), (2010, 1, 1.5), (2015, 12, 2.6), (2020, 1, 0.3), (2026, 9, 2.2)]
    r = ec.records(rows)
    assert r['max']['value'] == 2.6 and r['since'] == 'dic 2015' and 'desde dic 2015' in r['since_text']
    neg = ec.records([(2010, 1, -3.0), (2021, 1, -1.0), (2026, 9, -2.5)])
    assert neg['since'] == 'ene 2010' and 'más bajo' in neg['since_text']
