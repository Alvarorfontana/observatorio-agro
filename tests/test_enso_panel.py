import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import enso_panel as ep

ONI = """SEAS  YR   TOTAL   ANOM
  AMJ 2026  28.74   0.95
  MJJ 2026  29.02   1.39
  JJA 2026  29.09   1.80
  JAS 2026  29.12   2.16
"""
RONI = """SEAS   YR  ANOM
AMJ  2026  0.49
MJJ  2026  0.97
JJA  2026  1.36
JAS  2026  1.69
"""
WEEKLY = """ Weekly SST data starts week centered on 3Jan1990

                Nino1+2      Nino3        Nino34        Nino4
 Week          SST SSTA     SST SSTA     SST SSTA     SST SSTA
 30SEP2026     21.1 1.4     26.0 1.9     28.9 2.0     29.7 1.0
 07OCT2026     20.9-0.4     25.9 1.6     28.6 2.1     29.6 1.0
"""
HTML = '<p><strong>ENSO Alert System Status:</strong> El Niño Advisory</p>'


def test_parsers_y_categorias():
    o = ep.parse_seasonal(ONI); r = ep.parse_seasonal(RONI); w = ep.parse_weekly(WEEKLY)
    assert o[-1]['anom'] == 2.16 and o[-1]['season_es'] == 'JAS' and r[-1]['anom'] == 1.69
    assert w[-1]['week'] == '07OCT2026' and w[-1]['nino34'] == 2.1 and w[-1]['nino12'] == -0.4
    assert ep.category(2.16) == {'phase': 'El Niño', 'strength': 'muy fuerte'}
    assert ep.category(1.69)['strength'] == 'fuerte'
    assert ep.category(-1.2) == {'phase': 'La Niña', 'strength': 'moderado'}
    assert ep.category(0.3) == {'phase': 'Neutro', 'strength': None}
    assert ep.parse_status(HTML) == {'en': 'El Niño Advisory', 'es': 'Advertencia de El Niño'}


def test_episodios():
    s = [{'season': x, 'season_es': x, 'year': 1997, 'anom': v} for x, v in zip(ep.SEASONS, [0, .4, .6, .9, 1.2, 1.6, 2.0, 2.4, 1.0, .2, 0, 0])]
    e = ep.episodes(s)
    assert len(e) == 1 and e[0]['peak'] == 2.4 and e[0]['strength'] == 'muy fuerte' and 'Paraná' in e[0]['region']


def test_panel(monkeypatch):
    class R:
        def __init__(s, t): s.text, s.ok, s.status_code = t, True, 200
    texts = {ep.ONI_URL: ONI, ep.RONI_URL: RONI, ep.WEEKLY_URL: WEEKLY, ep.DISC_URL: HTML}
    monkeypatch.setattr(ep.c, '_get', lambda u, *a, **k: R(texts[u]))
    d = ep.enso_panel()['data']
    assert d['roni']['strength'] == 'fuerte' and d['phase']['phase'] == 'El Niño' and d['status']['es'].startswith('Advertencia')
    assert d['weekly']['nino34'] == 2.1 and len(d['series']['oni']) == 4


def test_episodio_en_curso():
    s = [{'season': x, 'season_es': x, 'year': 2026, 'anom': v} for x, v in zip(ep.SEASONS[:8], [-.5, -.4, -.2, .1, .95, 1.39, 1.8, 2.16])]
    e = ep.episodes(s)
    assert len(e) == 1 and e[0]['ongoing'] and e[0]['peak'] == 2.16
