"""radar v1.0 — agua y anegamiento en el lote con radar Sentinel-1 (ve a través de las nubes).

Fuente: Sentinel-1 RTC (retrodispersión corregida por terreno, gamma0 lineal, 10 m) en Microsoft Planetary Computer,
abierta y sin clave. El agua libre refleja el radar lejos del satélite y aparece muy oscura en VV:
se cuenta como agua todo píxel con VV < 0,0158 (−18 dB), un umbral habitual para aguas abiertas.
La vegetación inundada puede verse brillante (doble rebote) y no se cuenta: es una estimación conservadora.
"""
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import research_connectors as c
import vegetation as veg

COLL = 'sentinel-1-rtc'
WATER_VV = 0.0158   # −18 dB


def _stats(item_id, feature, expression=None, asset=None):
    params = {'collection': COLL, 'item': item_id, 'asset_as_band': 'true'}
    if expression:
        params['expression'] = expression
    else:
        params['assets'] = asset
    r = c.SESSION.post(f'{veg.PC_DATA}/item/statistics', params=params, json=feature, timeout=40)
    r.raise_for_status()
    return veg._first_stats(r.json())


def db(v):
    return None if not v or v <= 0 else round(10 * math.log10(v), 1)


def flooding(polygon, days=60, scenes=6):
    pts = veg.require_polygon(polygon)
    geom = veg.geojson_polygon(pts)
    feature = {'type': 'Feature', 'properties': {}, 'geometry': geom}
    end = c._now(); start = end - timedelta(days=days)
    body = {'collections': [COLL], 'intersects': geom, 'limit': scenes * 2,
            'datetime': f'{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}',
            'sortby': [{'field': 'properties.datetime', 'direction': 'desc'}]}
    items = c._post(veg.PC_STAC + '/search', body, timeout=30).json().get('features', [])
    # una pasada por fecha: la que mejor cubre el lote
    items = veg.best_tiles(items, pts)[:scenes]
    if not items:
        raise ValueError(f'Sin pasadas de Sentinel-1 sobre el lote en {days} días')
    area = veg.area_ha(pts)

    def one(it):
        row = {'item': it['id'], 'datetime': it['properties'].get('datetime'),
               'orbit': it['properties'].get('sat:orbit_state')}
        try:
            w = _stats(it['id'], feature, f'where(vv<{WATER_VV},1,0)')
            vv = _stats(it['id'], feature, asset='vv')
            frac = float(w.get('mean') or 0)
            row.update(status='válida', water_fraction=round(frac, 4), water_ha=round(frac * area, 1),
                       vv_db_median=db(vv.get('median')), pixels=vv.get('count'))
        except Exception as e:
            row.update(status='sin dato', error=type(e).__name__)
        return row
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = sorted(pool.map(one, items), key=lambda r: r['datetime'] or '')
    valid = [r for r in rows if r['status'] == 'válida']
    latest = valid[-1] if valid else None
    trend = None
    if len(valid) >= 2:
        d = valid[-1]['water_fraction'] - valid[0]['water_fraction']
        trend = 'el agua en el lote aumenta' if d > 0.02 else 'el agua en el lote disminuye' if d < -0.02 else 'sin cambios marcados'
    return c.envelope({'capability': 'ANALYSIS', 'sensor': 'Sentinel-1 RTC (radar banda C, 10 m)', 'area_ha': area,
                       'series': rows, 'latest': latest, 'trend': trend, 'threshold_db': -18,
                       'method': ('Agua = píxeles con retrodispersión VV menor a −18 dB dentro del lote. El radar ve con nubes y de noche. '
                                  'La vegetación inundada puede no contarse (estimación conservadora).')},
                      veg.PC_DATA + '/item/statistics', 'agua y anegamiento por radar', 'ESA Copernicus Sentinel-1 · Microsoft Planetary Computer',
                      'recibido' if valid else 'sin dato', None if valid else 'Las pasadas recientes no devolvieron estadística')
