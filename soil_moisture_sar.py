"""soil_moisture_sar v1.0 — humedad superficial del suelo con radar Sentinel-1 (banda C).

Segunda opinión de la humedad de suelo, pero de un sensor distinto: el radar. A diferencia de
los modelos (MERRA-2 de NASA POWER, ERA5-Land), el radar mide directamente cómo responde la
superficie y **ve con nubes y de noche**. Es lo que permite mirar un lote después de una lluvia
sin esperar a que se despeje.

Fuente: Sentinel-1 RTC (retrodispersión gamma0 lineal, 10 m) en Microsoft Planetary Computer,
abierta y sin clave. La humedad del suelo sube la retrodispersión VV; la vegetación densa la
tapa, por eso se informa también el RVI (Radar Vegetation Index = 4·VH/(VV+VH)) para saber
cuánto pesa el canopeo en la lectura.

Método (explícito, sin inventar nada): la humedad se informa como un **índice relativo 0-1**
que compara la VV de cada pasada con la referencia seca (percentil 10) y húmeda (percentil 90)
de las propias pasadas del lote en la ventana. NO es humedad volumétrica absoluta: es una
comparación del lote contra su propia historia reciente. Con pocas pasadas no hay referencia y
se responde sin dato en vez de inventarlo.
"""
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import research_connectors as c
import vegetation as veg

COLL = 'sentinel-1-rtc'
DRY_PCT = 10          # referencia seca: percentil 10 de la VV del propio lote
WET_PCT = 90          # referencia húmeda: percentil 90 de la VV del propio lote
MIN_SCENES = 5        # pasadas mínimas para poder normalizar contra la propia historia


def db(v):
    """gamma0 lineal → dB. Devuelve None si el valor no es válido."""
    return None if v is None or v <= 0 else round(10 * math.log10(v), 1)


def rvi(vv, vh):
    """Radar Vegetation Index (0-1) a partir de VV y VH lineales: 4·VH/(VV+VH)."""
    if not vv or not vh or (vv + vh) <= 0:
        return None
    return round(4 * vh / (vv + vh), 2)


def percentile(values, p):
    """Percentil p (0-100) por interpolación lineal; None si hay menos de MIN_SCENES valores."""
    s = sorted(v for v in values if v is not None)
    if len(s) < MIN_SCENES:
        return None
    k = (len(s) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return round(s[int(k)], 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 1)


def category(index):
    if index is None:
        return None
    if index < 0.2: return 'muy seco'
    if index < 0.4: return 'más seco que lo normal'
    if index <= 0.6: return 'normal'
    if index <= 0.8: return 'más húmedo que lo normal'
    return 'muy húmedo'


def surface_moisture(vv_db, dry, wet):
    """Índice relativo 0-1 entre la referencia seca y la húmeda; None si falta referencia."""
    if vv_db is None or dry is None or wet is None or wet <= dry:
        return None
    return round(min(1.0, max(0.0, (vv_db - dry) / (wet - dry))), 2)


def _stats(item_id, feature, asset):
    r = c.SESSION.post(f'{veg.PC_DATA}/item/statistics',
                       params={'collection': COLL, 'item': item_id, 'asset_as_band': 'true', 'assets': asset},
                       json=feature, timeout=40)
    r.raise_for_status()
    return veg._first_stats(r.json())


def _texture(pts):
    """Textura 0-5 cm (arcilla y arena) del punto medio del lote, como contexto del radar. Best-effort."""
    try:
        lat = sum(p[0] for p in pts) / len(pts)
        lon = sum(p[1] for p in pts) / len(pts)
        env = c.soilgrids(lat, lon, ['clay', 'sand'], ['0-5cm'], 'mean', 'textura superficial (contexto del radar)')
        out = {}
        for layer in ((env.get('data') or {}).get('properties') or {}).get('layers') or []:
            name = layer.get('name')
            f = (layer.get('unit_measure') or {}).get('d_factor') or 1
            for d in layer.get('depths') or []:
                v = (d.get('values') or {}).get('mean')
                if v is not None and name:
                    out[name] = round(v / f, 1)
        return out or None
    except Exception:
        return None


def analyze(polygon, days=60, scenes=8):
    pts = veg.require_polygon(polygon)
    geom = veg.geojson_polygon(pts)
    feature = {'type': 'Feature', 'properties': {}, 'geometry': geom}
    end = c._now(); start = end - timedelta(days=days)
    body = {'collections': [COLL], 'intersects': geom, 'limit': scenes * 2,
            'datetime': f'{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}',
            'sortby': [{'field': 'properties.datetime', 'direction': 'desc'}]}
    items = c._post(veg.PC_STAC + '/search', body, timeout=30).json().get('features', [])
    items = veg.best_tiles(items, pts)[:scenes]
    if not items:
        raise ValueError(f'Sin pasadas de Sentinel-1 sobre el lote en {days} días')
    area = veg.area_ha(pts)

    def one(it):
        row = {'item': it['id'], 'datetime': it['properties'].get('datetime'),
               'orbit': it['properties'].get('sat:orbit_state')}
        try:
            vv, vh = _stats(it['id'], feature, 'vv'), _stats(it['id'], feature, 'vh')
            vvl, vhl = vv.get('median'), vh.get('median')
            row.update(status='válida', vv_db=db(vvl), vh_db=db(vhl), rvi=rvi(vvl, vhl), pixels=vv.get('count'))
        except Exception as e:
            row.update(status='sin dato', error=type(e).__name__)
        return row
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = sorted(pool.map(one, items), key=lambda r: r['datetime'] or '')
    valid = [r for r in rows if r['status'] == 'válida']
    dry, wet = percentile([r['vv_db'] for r in valid], DRY_PCT), percentile([r['vv_db'] for r in valid], WET_PCT)
    for r in valid:
        r['smi'] = surface_moisture(r['vv_db'], dry, wet)
        r['category'] = category(r['smi'])
    latest = valid[-1] if valid else None
    trend = None
    if len(valid) >= 2 and valid[-1].get('smi') is not None and valid[0].get('smi') is not None:
        d = valid[-1]['smi'] - valid[0]['smi']
        trend = 'el suelo tiende a más húmedo' if d > 0.1 else 'el suelo tiende a más seco' if d < -0.1 else 'sin cambios marcados'
    return c.envelope({'capability': 'ANALYSIS', 'sensor': 'Sentinel-1 RTC (radar banda C, 10 m)', 'area_ha': area,
                       'series': rows, 'latest': latest, 'dry_ref_db': dry, 'wet_ref_db': wet,
                       'trend': trend, 'soil_texture': _texture(pts),
                       'method': ('Humedad superficial relativa: compara la retrodispersión VV de cada pasada con la referencia '
                                  'seca (percentil 10) y húmeda (percentil 90) de las propias pasadas del lote en la ventana; '
                                  'el índice 0-1 no es humedad volumétrica absoluta. El RVI (4·VH/(VV+VH)) dice cuánta vegetación '
                                  'hay: con RVI alto el radar lee el canopeo y pierde sensibilidad al suelo. El radar ve con nubes y de noche.')},
                      veg.PC_DATA + '/item/statistics', 'humedad superficial del suelo por radar',
                      'ESA Copernicus Sentinel-1 · Microsoft Planetary Computer',
                      'recibido' if valid else 'sin dato', None if valid else 'Las pasadas recientes no devolvieron estadística')
