import json
import riesgo_hidrico as rh

POLY = [[-36.30, -58.42], [-36.30, -58.38], [-36.33, -58.38], [-36.33, -58.42]]


def test_grid_and_expression():
    pts, dlat, dlon, step = rh.grid_points(POLY)
    assert 100 < len(pts) <= rh.MAX_POINTS and step >= 30
    body = json.dumps(rh.expression(pts[:5]))
    assert 'COPERNICUS/DEM/GLO30' in body and 'JRC/GSW1_4/GlobalSurfaceWater' in body and 'sampleRegions' in body


def test_classify_and_summary():
    samples = [(0, i, float(i), 0, 2.0) for i in range(100)]
    samples[0] = (0, 0, 0.0, 10, 0.5)      # el más bajo con agua vista: anegable
    samples[50] = (0, 50, 50.0, 40, 1.0)   # agua frecuente: laguna
    cells, cuts = rh.classify(samples)
    kinds = {x[1]: x[2] for x in cells}
    assert kinds[0] == 'anegable' and kinds[50] == 'laguna' and kinds[10] == 'bajo' and kinds[90] == 'loma' and kinds[40] == 'plano'
    s = rh.summarize(cells, 100.0, cuts, [2.0] * 100, [x[3] for x in samples])
    assert abs(sum(z['pct'] for z in s['zones']) - 100) < 0.5 and 'desnivel' in s['reading']
