from datetime import date, timedelta
import perfil_suelo as ps


def _daily(last_wet=0.30):
    t, cols = [], {k: [] for k, *_ in ps.LAYERS}
    d = date(1991, 1, 1)
    while d <= date(2026, 10, 8):
        t.append(d.isoformat())
        base = 0.25 + 0.05 * ((d.year * 7) % 5) / 4      # años más secos y más húmedos
        for k, *_ in ps.LAYERS:
            cols[k].append(round(last_wet if d.year == 2026 and d.month >= 9 else base, 3))
        d += timedelta(days=1)
    return {'time': t, **cols}


def test_profile_dry_and_wet():
    dry = ps.analyze_profile(_daily(0.18))
    assert dry['to_1m']['class'] == 'muy seco' and dry['to_2_5m']['diff_mm'] < 0
    assert [l['layer'] for l in dry['layers']] == ['0-7 cm', '7-28 cm', '28-100 cm', '100-255 cm']
    assert dry['to_2_5m']['mm'] == round(0.18 * 2550) and len(dry['recent_90d']) == 90
    wet = ps.analyze_profile(_daily(0.40))
    assert wet['to_1m']['class'] == 'muy húmedo' and 'percentil' in wet['reading']


def test_ndvi_anomaly():
    rows = []
    for y in range(2001, 2027):
        for m in range(1, 13):
            v = 0.6 if not (y == 2026 and m >= 9) else 0.35
            rows.append({'datetime': f'{y}-{m:02d}-01T00:00:00Z', 'ndvi_mean': v + 0.01 * (y % 3)})
    out = ps.analyze_ndvi([r for r in rows if r['datetime'] < '2026-10-02'])
    assert out['latest']['percentile'] == 0 and out['latest']['diff'] < -0.2 and 'por debajo' in out['reading']
    assert out['latest']['vci'] == 0 and out['latest']['vci_class'] == 'sequía extrema'
    assert out['persistence']['composites'] == 2 and 'días seguidos' in out['reading']


def test_pclass():
    assert [ps.pclass(p) for p in (5, 20, 50, 80, 95, None)] == ['muy seco', 'seco', 'normal', 'húmedo', 'muy húmedo', 'sin dato']


def test_et_and_frost():
    import json
    pts = []
    d = date(2001, 1, 1)
    while d < date(2026, 10, 1):
        v = 30 if not (d.year == 2026 and d.month >= 8) else 12
        pts.append((d, v)); d += timedelta(days=8)
    et = ps.analyze_et(pts)
    assert et['latest']['diff_pct'] == -60 and 'por debajo' in et['reading']
    night = [(date(2026, 9, 1) + timedelta(days=i), t) for i, t in enumerate([3, -1, -4, 2, 5, 0.5, -0.2])]
    fr = ps.analyze_frost(night)
    assert fr['frost_nights_30d'] == 3 and fr['strong_frost_nights_30d'] == 1 and fr['coldest']['lst_c'] == -4
    body = json.dumps(ps.modis_expression([[-28.5, -59.0], [-28.5, -58.9], [-28.6, -58.9]], 'MODIS/061/MYD11A1', 'LST_Night_1km', '2026-08-01', '2026-10-01', 1000))
    assert 'MYD11A1' in body and 'LST_Night_1km' in body
