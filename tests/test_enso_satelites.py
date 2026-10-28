import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import enso_satelites as es


def test_meses():
    m = es.meses(2025, date(2026, 2, 10))
    assert m[0] == (2025, 1) and m[-1] == (2026, 2) and len(m) == 14


def test_anomalias_pct_y_dif():
    serie = {f'{y}-03': 100.0 for y in range(2001, 2021)}
    serie['2026-03'] = 150.0
    serie['2026-04'] = 80.0                        # abril sin normal: anomalía None, no inventada
    filas, normal = es.anomalias(serie, (2001, 2020), 'pct')
    assert normal[3] == 100.0 and normal[4] is None
    assert filas[-2] == ['2026-03', 150.0, 100.0, 50.0]
    assert filas[-1] == ['2026-04', 80.0, None, None]
    f2, _ = es.anomalias({'2016-05': 0.30, '2017-05': 0.32, '2018-05': 0.28, '2026-05': 0.36}, (2016, 2025), 'dif')
    assert f2[-1][3] == 0.06


def test_pocos_anios_no_dan_normal():
    filas, normal = es.anomalias({'2016-01': 1.0, '2017-01': 2.0}, (2016, 2025), 'pct')
    assert normal[1] is None and all(f[3] is None for f in filas)


def test_productos_y_regiones():
    assert set(es.PRODUCTOS) == {'clorofila', 'humedad', 'lluvia'}
    assert all(p['colecciones'] for p in es.PRODUCTOS.values())
    assert {r[0] for r in es.TIERRA} >= {'nea', 'sur-brasil', 'uruguay'}
    assert es.ultimo([]) is None and es.ultimo([['2026-01', 1, 1, 0]])['mes'] == '2026-01'
