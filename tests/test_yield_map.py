"""yield_map: mapa de rinde del lote (pacu "simple": limpieza por σ + IDW) — validación, limpieza, escala y endpoint."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import scales
import yield_map as ym

# Cuadrado de lote en [lat, lon] con puntos del monitor dentro.
SQUARE = [[-31.00, -60.00], [-31.00, -59.99], [-31.01, -59.99], [-31.01, -60.00]]
GRID = [[-31.000, -60.000], [-31.000, -59.995], [-31.000, -59.990],
        [-31.005, -60.000], [-31.005, -59.995], [-31.005, -59.990],
        [-31.010, -60.000], [-31.010, -59.995], [-31.010, -59.990]]


@pytest.fixture
def client():
    from api.index import app
    return app.test_client()


# ── validación de entradas ──
def test_points_need_minimum_and_valid():
    with pytest.raises(ValueError):
        ym._points([[0, 0], [0, 1], [1, 0], [1, 1]])          # menos de 5
    with pytest.raises(ValueError):
        ym._points([[999, 0], [0, 1], [1, 0], [1, 1], [0, 0]])  # lat fuera de rango


def test_values_must_match_points():
    with pytest.raises(ValueError):
        ym._values([1, 2], 3)
    with pytest.raises(ValueError):
        ym._values([1, 'x', 3], 3)


# ── limpieza ──
def test_clean_removes_zeros_and_outliers():
    pts = [(0.0, 0.0)] * 11
    vals = [10.0] * 10 + [100.0]     # 100 es atípico (fuera de media ± 3σ)
    kept_p, kept_v, removed = ym.clean(pts, vals)
    assert len(kept_v) == 10 and 100.0 not in kept_v
    assert removed['atipicos'] == 1 and removed['nulos'] == 0 and removed['total'] == 1
    kept_p, kept_v, removed = ym.clean(pts, [10.0] * 10 + [0.0])
    assert removed['nulos'] == 1 and len(kept_v) == 10


# ── interpolación ──
def test_idw_on_a_point_returns_its_value():
    pts = [(p[0], p[1]) for p in GRID]
    vals = [float(i + 1) for i in range(len(pts))]
    assert ym.idw(pts[3][0], pts[3][1], pts, vals) == vals[3]


def test_grid_index_is_relative_to_mean():
    pts = [(p[0], p[1]) for p in GRID]
    vals = [10.0] * len(pts)         # lote parejo: todo ~ 100
    cells, cell_m = ym.grid(pts, vals, cell_m=100.0, boundary=SQUARE)
    assert cells and cell_m == 100.0
    assert all(abs(cel['index'] - 100.0) < 0.5 for cel in cells)
    assert all(SQUARE[0][0] - 0.02 <= cel['lat'] <= SQUARE[2][0] + 0.02 for cel in cells)


# ── escala ──
def test_yield_index_scale():
    assert 'yield_index' in scales.ids() and scales.describe('yield_index')['max'] == 200.0
    assert scales.band('yield_index', 50)['tone'] == 'risk'
    assert scales.band('yield_index', 90)['tone'] == 'ok'


# ── analyze ──
def test_analyze_builds_map():
    out = ym.analyze({'points': GRID, 'values': [10.0] * len(GRID), 'boundary': SQUARE, 'cell_m': 100})
    assert out['status'] == 'recibido'
    d = out['data']
    assert d['n_used'] == len(GRID) and d['n_cells'] > 0 and d['area_ha'] and d['area_ha'] > 0
    assert d['mean'] == 10.0 and d['scale']['scale'] == 'yield_index'
    assert 'media del lote' in d['reading']


def test_analyze_without_points_raises():
    with pytest.raises(ValueError):
        ym.analyze({'values': [1, 2, 3, 4, 5]})


def test_analyze_too_few_after_clean_sin_dato():
    vals = [0.0, 0.0, 0.0, 0.0, 0.0, 10.0]      # casi todo nulo: quedan menos de 5
    out = ym.analyze({'points': GRID[:6], 'values': vals})
    assert out['status'] == 'sin dato' and 'hacen falta' in out['error']


# ── endpoint ──
def test_mapa_rinde_endpoint(client):
    r = client.post('/api/fuentes/mapa-rinde', json={'points': GRID, 'values': [10.0] * len(GRID), 'cell_m': 100})
    assert r.status_code == 200 and r.get_json()['data']['n_cells'] > 0


def test_mapa_rinde_endpoint_bad_input(client):
    assert client.post('/api/fuentes/mapa-rinde', json={'points': [[0, 0]]}).status_code == 400
