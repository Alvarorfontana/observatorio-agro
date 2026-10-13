"""Cuenca del Plata: Niño semanal, lluvia en cabeceras, caudales y normales (fuentes simuladas)."""
import os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts'))
import cuenca as cc
import research_connectors as c

CPC = """ Weekly SST data starts week centered on 3Jan1990

                Nino1+2      Nino3        Nino34        Nino4
 Week          SST SSTA     SST SSTA     SST SSTA     SST SSTA
 03JAN1990     23.4-0.4     25.1-0.3     26.6 0.0     28.6 0.3
 09SEP2026     22.0 2.1     26.0 1.5     28.0 1.4     29.4 0.8
 16SEP2026     22.3 2.3     26.1 1.6     28.1 1.5     29.5 0.9
 23SEP2026     22.4 2.4     26.2 1.7     28.2 1.6     29.5 0.9
 30SEP2026     22.6 2.6     26.4 1.8     28.3 1.7     29.6 1.0
 07OCT2026     22.9 2.8     26.6 2.0     28.5 1.9     29.6 1.0
"""


def test_parse_cpc_y_fases():
    w = cc.parse_cpc_weekly(CPC)
    assert w[0]['nino12'] == {'sst': 23.4, 'anom': -0.4} and w[-1]['week'] == '2026-10-07'
    assert w[-1]['nino34']['anom'] == 1.9 and len(w) == 6
    assert [cc.phase(v) for v in (2.1, 1.6, 1.2, 0.6, 0.0, -0.7, -1.2, -2)] == \
        ['Niño muy fuerte', 'Niño fuerte', 'Niño moderado', 'Niño débil', 'neutral', 'Niña débil', 'Niña moderada', 'Niña fuerte']


def test_nino_semanal(monkeypatch):
    class R: text = CPC
    monkeypatch.setattr(c, '_get', lambda *a, **k: R())
    out = cc.nino_weekly()
    by = {r['id']: r for r in out['regions']}
    assert out['phase'] == 'Niño fuerte' and out['coastal'] == 'Niño muy fuerte'
    assert by['nino34']['change_4w'] == 0.5 and out['series']['nino12'][-1] == 2.8


def _ens(per_member):
    """Respuesta de un punto con 3 miembros: lluvia diaria constante por miembro."""
    return {'daily': {'time': [f'd{i}' for i in range(16)],
                      **{('precipitation_sum' if j == 0 else f'precipitation_sum_member{j:02d}'): [v] * 16 for j, v in enumerate(per_member)}}}


def test_lluvia_en_cabeceras_promedia_puntos_y_miembros():
    basin = [{'id': 'b', 'name': 'B', 'where': 'w', 'travel': 't', 'points': [(0, 0), (1, 1)]}]
    resp = [_ens([2, 5, 10]), _ens([4, 5, 10])]            # 15 días: miembros 45, 75, 150 mm
    out = cc.basin_rain(resp, basin, normals={'b': {'rain15_by_month': {str(date.today().month): 50}}})[0]
    assert out['members'] == 3 and out['median_mm'] == 75 and out['p_ge50'] == 67 and out['p_ge100'] == 33
    assert out['normal_mm'] == 50 and out['ratio'] == 1.5


def test_percentil_y_nivel_del_rio():
    q = {'min': 500, 'p10': 800, 'p25': 1000, 'p50': 1500, 'p75': 2200, 'p90': 3500, 'p97': 6000, 'max': 20000}
    assert cc.percentile_in(1500, q) == 50 and cc.percentile_in(300, q) == 0 and cc.percentile_in(30000, q) == 99
    assert 90 < cc.percentile_in(4500, q) < 97
    assert [cc.river_level(p) for p in (5, 20, 50, 80, 95, 99)] == ['muy bajo', 'bajo', 'normal', 'alto', 'muy alto', 'extraordinario']


def test_resumen_de_rios_con_normales():
    today = date(2026, 10, 13)
    t = [(today + timedelta(days=i - 7)).isoformat() for i in range(37)]
    q = [1500.0] * 7 + [4500.0] + [5000.0 + 100 * i for i in range(29)]
    resp = [{'daily': {'time': t, 'river_discharge': q, 'river_discharge_median': q}}] + [{}] * (len(cc.STATIONS) - 1)
    clim = {'min': 500, 'p10': 800, 'p25': 1000, 'p50': 1500, 'p75': 2200, 'p90': 3500, 'p97': 6000, 'max': 20000}
    normals = {'iguazu-cataratas': {'doy': {'10-10': clim, '11-10': clim}}}
    out = cc.rivers_summary(resp, normals, today)
    ig = out[0]
    assert ig['discharge'] == 4500 and ig['ratio'] == 3.0 and ig['level'] == 'muy alto'
    assert ig['change_7d_pct'] == 200 and ig['peak'] == 7800 and ig['peak_date'] == t[-1] and ig['peak_level'] == 'muy alto'
    assert out[1]['status'] == 'sin dato'


def test_normales_por_ventana():
    import normales_cuenca as nc
    t, v = [], []
    for y in range(2001, 2021):
        d = date(y, 1, 1)
        while d.year == y:
            t.append(d.isoformat()); v.append(1000.0 + (y - 2001) * 10); d += timedelta(days=1)
    out = nc.doy_percentiles(t, v)
    assert '10-10' in out and out['10-10']['min'] == 1000 and out['10-10']['max'] == 1190
    assert out['10-10']['p50'] == 1095 and len(out) >= 72


def test_ruta_cuenca_tolera_fallas(monkeypatch):
    from api.index import app
    cc._CACHE.clear()
    monkeypatch.setattr(cc, 'nino_weekly', lambda: {'phase': 'Niño fuerte'})
    monkeypatch.setattr(cc, 'headwaters', lambda: (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setattr(cc, 'rivers', lambda: {'stations': []})
    monkeypatch.setattr(cc, 'dams', lambda: {'dams': []})
    j = app.test_client().get('/api/fuentes/cuenca').get_json()
    assert j['status'] == 'recibido' and j['data']['nino']['phase'] == 'Niño fuerte'
    assert j['data']['errors'] == {'headwaters': 'TimeoutError'}
    cc._CACHE.clear()


def test_desfase_y_crecidas_de_retorno():
    import math, random
    import normales_cuenca as nc
    random.seed(1)
    n = 3000
    up = [1000 + 800 * math.sin(i / 9) + 300 * math.sin(i / 2.3) + random.gauss(0, 20) for i in range(n)]
    down = [2000 + 1.5 * up[i - 6] if i >= 6 else 2000.0 for i in range(n)]   # la onda llega 6 días después
    r = nc.lag_days(up, down)
    assert r['days'] == 6 and r['corr'] > 0.9
    t = [f'{2001 + i // 365}-01-01' for i in range(20 * 365)]
    v = [1000 + 100 * (i // 365) for i in range(20 * 365)]
    rp = nc.gumbel(t, v)
    assert rp['q2'] < rp['q5'] < rp['q20'] and rp['years'] == 20
    assert cc.danger(rp['q5'] + 1, rp) == 'Alerta' and cc.danger(0, rp) == 'Normal' and cc.danger(None, rp) is None


def test_tiempo_de_traslado_y_llegada():
    st = [{'id': 'iguazu-cataratas', 'place': 'Cataratas', 'river': 'Iguazú', 'peak_date': '2026-10-20', 'peak_danger': 'Alerta'},
          {'id': 'parana-posadas', 'place': 'Posadas', 'river': 'Paraná'},
          {'id': 'parana-corrientes', 'place': 'Corrientes', 'river': 'Paraná', 'danger': 'Atención'}]
    normals = {'lags': {'iguazu-cataratas>parana-posadas': {'days': 2, 'corr': 0.7},
                        'parana-posadas>parana-corrientes': {'days': 4, 'corr': 0.8}}}
    ch = cc.travel(st, normals)[0]
    rows = {r['id']: r for r in ch['rows']}
    assert rows['parana-corrientes']['days_from_head'] == 6 and rows['parana-corrientes']['arrival'] == '2026-10-26'
    assert rows['parana-goya']['days_from_head'] is None and ch['head_level'] == 'Alerta'


def test_represas_ons():
    csv = ["id_subsistema;nom_reservatorio;din_instante;val_nivelmontante;val_vazaoafluente;val_vazaodefluente",
           "S;SALTO CAXIAS;2026-10-01;325,1;3000,5;2900",
           "S;SALTO CAXIAS;2026-10-08;325,4;9000;8800",
           "S;ITA;2026-10-08;370;4000;3900",
           "S;ITAPEBI;2026-10-08;100;10;10",
           "S;ITAIPU;2026-10-08;219;20000;19500"]
    s = cc.parse_ons(csv)
    assert set(s) == {'salto-caxias', 'ita', 'itaipu'} and s['salto-caxias'][-1] == ('2026-10-08', 9000.0, 8800.0)
    clim = {'min': 300, 'p10': 500, 'p25': 800, 'p50': 1200, 'p75': 2000, 'p90': 3500, 'p97': 7000, 'max': 20000}
    out = {d['id']: d for d in cc.dams_summary(s, {'salto-caxias': {'doy': {'10-05': clim}}})}
    sc = out['salto-caxias']
    assert sc['outflow'] == 8800 and sc['change_7d_pct'] == 203 and sc['ratio'] == 7.33 and sc['level'] == 'muy alto'
    assert out['foz-chapeco']['status'] == 'sin dato' and out['ita']['normal'] is None


def test_alerta_temprana_por_lluvia_en_cabeceras():
    basins = [{'id': 'alto-iguazu', 'name': 'Alto Iguazú', 'where': 'w', 'status': 'recibido', 'p_ge100': 75, 'p_ge200': 10, 'ratio': 1.6,
               'median_mm': 140, 'rain_center': '2026-10-17', 'rain_from': '2026-10-15', 'rain_to': '2026-10-19'},
              {'id': 'cuiaba', 'name': 'Cuiabá', 'where': 'w', 'status': 'recibido', 'p_ge100': 5, 'p_ge200': 0, 'ratio': 0.8}]
    stations = [{'id': 'iguazu-cataratas', 'place': 'Cataratas', 'river': 'Iguazú', 'level': 'alto'},
                {'id': 'parana-posadas', 'place': 'Posadas', 'river': 'Paraná'}, {'id': 'parana-corrientes', 'place': 'Corrientes', 'river': 'Paraná'}]
    dams = [{'name': 'Salto Caxias', 'river': 'Iguazú', 'level': 'normal'}]
    normals = {'lags': {'iguazu-cataratas>parana-posadas': {'days': 2, 'corr': .7}, 'parana-posadas>parana-corrientes': {'days': 4, 'corr': .8}}}
    al = cc.early_warning(basins, stations, dams, normals)
    ig = al[0]
    assert ig['basin'] == 'alto-iguazu' and ig['level'] == 'Peligro'           # Alerta por lluvia + río ya alto
    assert any('ya viene alto' in w for w in ig['why'])
    w = {a['place']: a['window'] for a in ig['arrivals']}
    assert w['Cataratas'] == ['2026-10-20', '2026-10-23'] and w['Corrientes'] == ['2026-10-26', '2026-10-29']
    assert al[-1]['level'] == 'Normal' and al[-1]['arrivals'] == []
    assert cc.rain_level({'status': 'recibido', 'p_ge100': 45, 'p_ge200': 0})[0] == 'Atención'


def test_lluvia_diaria_y_centro_de_la_lluvia():
    basin = [{'id': 'b', 'name': 'B', 'where': 'w', 'travel': 't', 'points': [(0, 0)]}]
    resp = {'daily': {'time': [f'2026-10-{13 + i:02d}' for i in range(16)],
                      'precipitation_sum': [0, 0, 30, 40, 0] + [0] * 11, 'precipitation_sum_member01': [0, 0, 30, 40, 0] + [0] * 11}}
    out = cc.basin_rain([resp], basin)[0]
    assert out['rain_from'] == '2026-10-15' and out['rain_to'] == '2026-10-16' and out['rain_center'] == '2026-10-16'
    assert out['daily_median'][3] == 40


def test_informe_pdf_de_la_cuenca(monkeypatch):
    import pytest
    pytest.importorskip("typst")
    import cuenca_report as cr
    from api.index import app
    cc._CACHE.clear()
    class R: text = CPC
    monkeypatch.setattr(c, '_get', lambda *a, **k: R())
    nino = cc.nino_weekly()
    fake = {'status': 'recibido', 'data': {'nino': nino, 'headwaters': None, 'rivers': None, 'dams': None,
            'alerts': [{'basin': 'alto-iguazu', 'group': 'Iguazú', 'name': 'Alto Iguazú', 'where': 'w', 'level': 'Alerta', 'why': ['x'],
                        'median_mm': 120, 'arrivals': [{'place': 'Cataratas', 'window': ['2026-10-20', '2026-10-23']}], 'actions': ['a']}],
            'maps': cc.maps(), 'errors': {}}}
    monkeypatch.setattr(cc, 'analyze', lambda: fake)
    r = app.test_client().get('/api/fuentes/cuenca-informe')
    assert r.status_code == 200 and r.data[:5] == b'%PDF-' and 'attachment' in r.headers['Content-Disposition']
    d = cr.build_data(fake['data'])
    assert d['worst'] == 'Alerta' and 'Alto Iguazú' in d['summary'][1] and d['pictures'] == []
