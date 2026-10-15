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
