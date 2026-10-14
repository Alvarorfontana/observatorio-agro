"""vegetation v1.9 — NDVI real por lote.

Cuatro vías, todas livianas (sólo `requests`; google-auth opcional para GEE):

  1. ndvi_open()        Planetary Computer Data API (TiTiler/rio-tiler del lado del servidor).
                        Abierta, sin credencial. Estadística zonal + máscara SCL dentro del lote.
  2. ndvi_png()         Misma API: PNG NDVI recortado al polígono para el mapa.
  3. sentinel_hub_ndvi() CDSE Sentinel Hub Statistical API (OAuth2 client credentials).
  4. openeo_ndvi()      CDSE openEO, grafo de procesos JSON síncrono.
  5. gee_ndvi()         Google Earth Engine REST value:compute, MODIS MOD13Q1.

Contrato igual a research_connectors: envelope o excepción. Nunca se inventan datos.
Todas exigen polígono [[lat,lon],...]; no hay promedio zonal sobre un punto.
"""
import json, os, time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import research_connectors as c

PC_STAC = 'https://planetarycomputer.microsoft.com/api/stac/v1'
PC_DATA = 'https://planetarycomputer.microsoft.com/api/data/v1'
CDSE_TOKEN = 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'
CDSE_STATS = 'https://sh.dataspace.copernicus.eu/api/v1/statistics'
OPENEO = 'https://openeo.dataspace.copernicus.eu/openeo/1.2'
GEE = 'https://earthengine.googleapis.com/v1'

MIN_CLEAR = 0.6          # fracción mínima de píxeles despejados dentro del lote
SCL_CLEAR = (4, 5)       # 4 vegetación, 5 suelo desnudo
NDVI_RESCALE = '-0.2,0.9'


# ───────────────────────────── geometría ─────────────────────────────
def require_polygon(polygon):
    if not polygon:
        raise ValueError('Dibujá un lote: el NDVI zonal necesita polígono, no un punto')
    return c._poly(polygon)


def geojson_polygon(polygon):
    """[[lat,lon],...] → GeoJSON Polygon (lon,lat) cerrado."""
    pts = require_polygon(polygon)
    ring = [[lon, lat] for lat, lon in pts]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {'type': 'Polygon', 'coordinates': [ring]}


def area_ha(polygon):
    """Área geodésica aproximada (proyección equirectangular local), suficiente para conteo de píxeles."""
    import math
    pts = require_polygon(polygon)
    lat0 = sum(p[0] for p in pts) / len(pts) * math.pi / 180
    xy = [(p[1] * 111320 * math.cos(lat0), p[0] * 110540) for p in pts]
    s = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]; x2, y2 = xy[(i + 1) % len(xy)]
        s += x1 * y2 - x2 * y1
    return round(abs(s) / 2 / 10000, 2)


# ───────────────────────────── 1. Planetary Computer (abierto) ─────────────────────────────
def ndvi_expression(item):
    """Sentinel-2 L2A baseline >= 04.00 trae BOA_ADD_OFFSET = -1000 en los DN."""
    pb = str((item.get('properties') or {}).get('s2:processing_baseline') or '0')
    try:
        offset = float(pb) >= 4.0
    except ValueError:
        offset = False
    return '(B08-B04)/(B08+B04-2000)' if offset else '(B08-B04)/(B08+B04)'


def _first_stats(resp):
    """TiTiler devuelve Feature con properties.statistics {<banda|expresión>: {...}}."""
    if isinstance(resp, dict) and resp.get('type') == 'FeatureCollection':
        resp = (resp.get('features') or [{}])[0]
    stats = ((resp or {}).get('properties') or {}).get('statistics') or {}
    if not stats:
        raise ValueError('La API raster no devolvió estadísticas')
    return next(iter(stats.values()))


def _pc_stats(item_id, feature, expression):
    r = c.SESSION.post(f'{PC_DATA}/item/statistics',
                       params={'collection': 'sentinel-2-l2a', 'item': item_id,
                               'expression': expression, 'asset_as_band': 'true'},
                       json=feature, timeout=40)
    r.raise_for_status()
    return _first_stats(r.json())


def search_s2(polygon, days=120, limit=8, max_cloud=60):
    geom = geojson_polygon(polygon)
    end = c._now(); start = end - timedelta(days=days)
    body = {'collections': ['sentinel-2-l2a'], 'intersects': geom, 'limit': limit,
            'datetime': f'{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}',
            'query': {'eo:cloud_cover': {'lt': max_cloud}},
            'sortby': [{'field': 'properties.datetime', 'direction': 'desc'}]}
    return c._post(PC_STAC + '/search', body, timeout=30).json().get('features', [])


def scene_ndvi(item, feature):
    """NDVI + fracción despejada SCL dentro del lote para UNA escena."""
    expr = ndvi_expression(item)
    clear_expr = 'where(' + '|'.join(f'(SCL=={v})' for v in SCL_CLEAR) + ',1,0)'
    clear = _pc_stats(item['id'], feature, clear_expr)
    clear_frac = float(clear.get('mean') or 0)
    row = {'item': item['id'], 'datetime': item['properties'].get('datetime'),
           'scene_cloud_pct': item['properties'].get('eo:cloud_cover'),
           'clear_fraction_lot': round(clear_frac, 3), 'expression': expr, 'tile_coverage': item.get('_coverage'),
           'processing_baseline': item['properties'].get('s2:processing_baseline')}
    if clear_frac < MIN_CLEAR:
        row.update(status='nublada', note=f'Sólo {clear_frac:.0%} del lote despejado; no se interpreta')
        return row
    s = _pc_stats(item['id'], feature, expr)
    row.update(status='válida',
               ndvi_mean=_r(s.get('mean')), ndvi_median=_r(s.get('median')),
               ndvi_p2=_r(s.get('percentile_2')), ndvi_p98=_r(s.get('percentile_98')),
               ndvi_std=_r(s.get('std')), pixels=s.get('valid_pixels') or s.get('count'))
    return row


def _r(v):
    return None if v is None else round(float(v), 4)


def _refl(band, offset):
    """Reflectancia 0-1 a partir del DN de Sentinel-2 L2A (escala 10000, offset -1000 desde baseline 04.00)."""
    return f'(({band}-1000)/10000)' if offset else f'({band}/10000)'


def index_expressions(item):
    pb = str((item.get('properties') or {}).get('s2:processing_baseline') or '0')
    try:
        off = float(pb) >= 4.0
    except ValueError:
        off = False
    B2, B3, B4, B8, B11 = (_refl(b, off) for b in ('B02', 'B03', 'B04', 'B08', 'B11'))
    return {
        'evi': f'2.5*({B8}-{B4})/({B8}+6*{B4}-7.5*{B2}+1)',
        'savi': f'1.5*({B8}-{B4})/({B8}+{B4}+0.5)',
        'ndmi': f'({B8}-{B11})/({B8}+{B11})',
        'ndwi': f'({B3}-{B8})/({B3}+{B8})',
    }


INDEX_INFO = {
    'evi': ('EVI', 'Vigor en pasturas densas; no se satura como el NDVI.'),
    'savi': ('SAVI', 'Vigor corrigiendo el suelo desnudo; útil con pasto ralo.'),
    'ndmi': ('NDMI', 'Humedad del follaje: valores bajos anticipan estrés hídrico.'),
    'ndwi': ('NDWI', 'Agua en superficie: positivo indica agua libre o anegamiento.'),
}


def extra_indices(item, feature):
    exprs = index_expressions(item)
    out = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {k: pool.submit(_pc_stats, item['id'], feature, e) for k, e in exprs.items()}
        for k, f in futs.items():
            try:
                st = f.result()
                out[k] = {'name': INDEX_INFO[k][0], 'mean': _r(st.get('mean')), 'p2': _r(st.get('percentile_2')),
                          'p98': _r(st.get('percentile_98')), 'meaning': INDEX_INFO[k][1]}
            except Exception as e:
                out[k] = {'name': INDEX_INFO[k][0], 'mean': None, 'error': type(e).__name__, 'meaning': INDEX_INFO[k][1]}
    # superficie con agua libre estimada: fracción de píxeles con NDWI > 0
    try:
        w = _pc_stats(item['id'], feature, f"where({exprs['ndwi']}>0,1,0)")
        out['water_fraction'] = _r(w.get('mean'))
    except Exception:
        out['water_fraction'] = None
    return out


def _in_ring(x, y, ring):
    inside = False
    for i in range(len(ring)):
        x1, y1 = ring[i][:2]; x2, y2 = ring[i - 1][:2]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            inside = not inside
    return inside


def footprint_coverage(item, pts):
    """Fracción de puntos de muestra del lote (vértices, puntos medios y centro) dentro de la huella de la escena."""
    g = item.get('geometry') or {}
    polys = [g.get('coordinates')] if g.get('type') == 'Polygon' else (g.get('coordinates') or []) if g.get('type') == 'MultiPolygon' else []
    if not polys:
        return 1.0
    sample = list(pts) + [((pts[i][0] + pts[i - 1][0]) / 2, (pts[i][1] + pts[i - 1][1]) / 2) for i in range(len(pts))]
    sample.append((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)))
    hit = sum(1 for lat, lon in sample if any(_in_ring(lon, lat, poly[0]) for poly in polys if poly))
    return hit / len(sample)


def best_tiles(items, pts):
    """Una escena por fecha de toma: la tesela que mejor cubre el lote. Evita promediar píxeles fuera de la tesela."""
    best = {}
    for it in items:
        pr = it.get('properties') or {}
        key = (str(pr.get('datetime') or '')[:10], pr.get('platform') or it['id'][:3])
        cov = footprint_coverage(it, pts)
        if key not in best or cov > best[key][0]:
            best[key] = (cov, it)
    out = [(cov, it) for cov, it in best.values() if cov >= 0.5]
    out.sort(key=lambda x: (x[1].get('properties') or {}).get('datetime') or '', reverse=True)
    return [it | {'_coverage': round(cov, 2)} for cov, it in out]


def ndvi_open(polygon, days=120, scenes=6):
    pts = require_polygon(polygon)
    feature = {'type': 'Feature', 'properties': {}, 'geometry': geojson_polygon(pts)}
    items = best_tiles(search_s2(pts, days=days, limit=min(max(scenes, 1) * 3, 30)), pts)[:scenes]
    if not items:
        raise ValueError(f'Sin escenas Sentinel-2 con <60 % de nubes en {days} días')
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(scene_ndvi, it, feature) for it in items]
        for it, f in zip(items, futs):
            try:
                rows.append(f.result())
            except Exception as e:
                rows.append({'item': it['id'], 'datetime': it['properties'].get('datetime'),
                             'status': 'sin dato', 'error': type(e).__name__})
    rows.sort(key=lambda r: r.get('datetime') or '')
    valid = [r for r in rows if r.get('status') == 'válida']
    latest = valid[-1] if valid else None
    if latest:
        try:
            item = next(it for it in items if it['id'] == latest['item'])
            latest['indices'] = extra_indices(item, feature)
        except Exception:
            latest['indices'] = None
    return c.envelope({
        'capability': 'ANALYSIS', 'index': 'NDVI', 'sensor': 'Sentinel-2 L2A (10 m)',
        'area_ha': area_ha(pts), 'min_clear_fraction': MIN_CLEAR,
        'latest': latest, 'series': rows, 'valid_scenes': len(valid),
        'interpretation_scope': 'Estadística zonal dentro del polígono. Nubes/sombras excluidas por SCL.'},
        PC_DATA + '/item/statistics', 'NDVI zonal Sentinel-2 por lote',
        'Microsoft Planetary Computer · ESA Copernicus',
        'recibido' if valid else 'sin dato',
        None if valid else 'Ninguna escena con el lote suficientemente despejado')


ORNL_MODIS = 'https://modis.ornl.gov/rst/api/v1/MOD13Q1/subset'


def ndvi_modis(polygon, days=120):
    """Respaldo sin credencial y de otro proveedor: NDVI MODIS MOD13Q1 (250 m, compuestos de 16 días)
    del servicio web de NASA ORNL DAAC. Promedia los píxeles de una ventana centrada en el lote,
    de tamaño menor o igual al lote. Más grueso que Sentinel-2 pero independiente de Planetary Computer."""
    import math
    pts = require_polygon(polygon)
    lat = sum(p[0] for p in pts) / len(pts); lon = sum(p[1] for p in pts) / len(pts)
    h_km = (max(p[0] for p in pts) - min(p[0] for p in pts)) * 110.54
    w_km = (max(p[1] for p in pts) - min(p[1] for p in pts)) * 111.32 * math.cos(math.radians(lat))
    k = max(0, min(2, int((min(h_km, w_km) - 1) / 2)))   # ventana de 2k+1 km que entra en el lote
    end = c._now().date(); start = end - timedelta(days=days)
    # el servicio de ORNL devuelve hasta 10 compuestos por pedido: se pide de a 150 días, en paralelo
    tramos, a = [], start
    while a <= end:
        b = min(end, a + timedelta(days=149)); tramos.append((a, b)); a = b + timedelta(days=1)
    def pedir(t):
        a, b = t
        return c._get(ORNL_MODIS, {'latitude': round(lat, 5), 'longitude': round(lon, 5), 'band': '250m_16_days_NDVI',
                                   'startDate': f'A{a.year}{a.timetuple().tm_yday:03d}', 'endDate': f'A{b.year}{b.timetuple().tm_yday:03d}',
                                   'kmAboveBelow': k, 'kmLeftRight': k}, headers={'Accept': 'application/json'}, timeout=40).json()
    with ThreadPoolExecutor(max_workers=4) as pool:
        partes = list(pool.map(pedir, tramos))
    js = partes[0] if partes else {}
    scale = float(js.get('scale') or 0.0001)
    rows, vistos = [], set()
    for sub in [x for p in partes for x in (p.get('subset') or [])]:
        if sub.get('calendar_date') in vistos:
            continue
        vistos.add(sub.get('calendar_date'))
        vals = [v * scale for v in sub.get('data') or [] if v is not None and -2000 <= v <= 10000]
        row = {'item': f"MOD13Q1 {sub.get('modis_date')}", 'datetime': f"{sub.get('calendar_date')}T00:00:00Z", 'pixels': len(vals)}
        if vals:
            row.update(status='válida', ndvi_mean=_r(sum(vals) / len(vals)), ndvi_p2=_r(min(vals)), ndvi_p98=_r(max(vals)))
        else:
            row.update(status='sin dato', note='Sin píxeles válidos en el compuesto')
        rows.append(row)
    rows.sort(key=lambda r: r['datetime'])
    valid = [r for r in rows if r['status'] == 'válida']
    return c.envelope({
        'capability': 'ANALYSIS', 'index': 'NDVI', 'sensor': 'MODIS Terra MOD13Q1 (250 m, 16 días)',
        'area_ha': area_ha(pts), 'latest': valid[-1] if valid else None, 'series': rows, 'valid_scenes': len(valid),
        'fallback': True, 'window_km': 2 * k + 1 if k else 0.25,
        'interpretation_scope': ('Respaldo: ' + (f'promedio de píxeles MODIS de 250 m en una ventana de {2 * k + 1} km centrada en el lote.' if k
                                 else 'píxel MODIS de 250 m del centro del lote.'))},
        ORNL_MODIS, 'NDVI MODIS por lote (respaldo)', 'NASA ORNL DAAC · MODIS',
        'recibido' if valid else 'sin dato', None if valid else 'MODIS no devolvió compuestos válidos')


def ndvi_best(polygon, days=120, scenes=6):
    """Sentinel-2 por Planetary Computer; si falla o no hay escenas despejadas, MODIS de NASA ORNL."""
    reason = None
    try:
        env = ndvi_open(polygon, days, scenes)
        if env['data'].get('valid_scenes'):
            return env
        reason = 'Sentinel-2 sin escenas despejadas'
    except ValueError as e:
        if 'Dibujá' in str(e) or 'polígono' in str(e).lower():
            raise
        reason = str(e)
    except Exception as e:
        reason = f'Planetary Computer no respondió ({type(e).__name__})'
    env = ndvi_modis(polygon, max(days, 64))
    env['data']['fallback_reason'] = reason
    return env


def ndvi_png(item_id, polygon, processing_baseline=None, mode='ndvi'):
    """Devuelve (png_bytes, bounds) con el NDVI o el color real (TCI) recortado al lote."""
    pts = require_polygon(polygon)
    if not isinstance(item_id, str) or not item_id.startswith('S2') or len(item_id) > 80 \
            or not all(ch.isalnum() or ch in '_.' for ch in item_id):
        raise ValueError('Escena inválida')
    feature = {'type': 'Feature', 'properties': {}, 'geometry': geojson_polygon(pts)}
    if mode == 'rgb':   # imagen en color real de Sentinel-2 (asset TCI 'visual', 8 bits)
        params = {'collection': 'sentinel-2-l2a', 'item': item_id, 'assets': 'visual',
                  'asset_bidx': 'visual|1,2,3', 'nodata': 0, 'max_size': 768}
    else:
        expr = ndvi_expression({'properties': {'s2:processing_baseline': processing_baseline}})
        params = {'collection': 'sentinel-2-l2a', 'item': item_id, 'expression': expr,
                  'asset_as_band': 'true', 'rescale': NDVI_RESCALE, 'colormap_name': 'rdylgn', 'max_size': 512}
    r = c.SESSION.post(f'{PC_DATA}/item/feature.png', params=params, json=feature, timeout=40)
    r.raise_for_status()
    if not r.headers.get('Content-Type', '').startswith('image/png'):
        raise ValueError('La API raster no devolvió PNG')
    w, s, e, n = c.polygon_bbox(pts)
    return r.content, [[s, w], [n, e]]


# ───────────────────────────── CDSE (Sentinel Hub + openEO) ─────────────────────────────
_TOKEN = {'value': None, 'exp': 0}


def cdse_token():
    cid, sec = os.environ.get('CDSE_CLIENT_ID'), os.environ.get('CDSE_CLIENT_SECRET')
    if not cid or not sec:
        raise PermissionError('requiere credencial: CDSE_CLIENT_ID, CDSE_CLIENT_SECRET')
    if _TOKEN['value'] and _TOKEN['exp'] > time.time() + 30:
        return _TOKEN['value']
    r = c.SESSION.post(CDSE_TOKEN, data={'grant_type': 'client_credentials',
                                         'client_id': cid, 'client_secret': sec}, timeout=20)
    r.raise_for_status()
    d = r.json()
    _TOKEN.update(value=d['access_token'], exp=time.time() + int(d.get('expires_in', 300)))
    return _TOKEN['value']


EVALSCRIPT = """//VERSION=3
function setup(){return{input:[{bands:["B04","B08","SCL","dataMask"]}],
 output:[{id:"ndvi",bands:1,sampleType:"FLOAT32"},{id:"dataMask",bands:1}]};}
function evaluatePixel(s){
 var clear=(s.SCL==4||s.SCL==5)?1:0;
 return{ndvi:[(s.B08-s.B04)/(s.B08+s.B04)],dataMask:[s.dataMask*clear]};}"""


def sentinel_hub_ndvi(polygon, days=180):
    pts = require_polygon(polygon)
    tok = cdse_token()
    end = c._now(); start = end - timedelta(days=days)
    body = {'input': {'bounds': {'geometry': geojson_polygon(pts),
                                 'properties': {'crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'}},
                      'data': [{'type': 'sentinel-2-l2a', 'dataFilter': {'maxCloudCoverage': 80}}]},
            'aggregation': {'timeRange': {'from': f'{start:%Y-%m-%dT00:00:00Z}', 'to': f'{end:%Y-%m-%dT23:59:59Z}'},
                            'aggregationInterval': {'of': 'P5D'}, 'evalscript': EVALSCRIPT,
                            'resx': 0.0001, 'resy': 0.0001}}
    r = c.SESSION.post(CDSE_STATS, json=body, headers={'Authorization': f'Bearer {tok}'}, timeout=50)
    r.raise_for_status()
    rows = []
    for x in r.json().get('data', []):
        st = (((x.get('outputs') or {}).get('ndvi') or {}).get('bands') or {}).get('B0', {}).get('stats', {})
        total = st.get('sampleCount') or 0; nod = st.get('noDataCount') or 0
        clear = (total - nod) / total if total else 0
        if not total or st.get('mean') in (None, 'NaN'):
            continue
        rows.append({'from': x['interval']['from'], 'to': x['interval']['to'],
                     'clear_fraction_lot': round(clear, 3),
                     'status': 'válida' if clear >= MIN_CLEAR else 'nublada',
                     'ndvi_mean': _r(st.get('mean')), 'ndvi_p50': _r((st.get('percentiles') or {}).get('50.0')),
                     'ndvi_std': _r(st.get('stDev'))})
    valid = [x for x in rows if x['status'] == 'válida']
    return c.envelope({'capability': 'ANALYSIS', 'index': 'NDVI', 'sensor': 'Sentinel-2 L2A',
                       'area_ha': area_ha(pts), 'series': rows, 'valid_scenes': len(valid),
                       'latest': valid[-1] if valid else None},
                      CDSE_STATS, 'NDVI zonal · Sentinel Hub Statistical API', 'Copernicus Data Space',
                      'recibido' if valid else 'sin dato', None if valid else 'Sin intervalos despejados')


def openeo_graph(polygon, start, end):
    geom = geojson_polygon(polygon)
    w, s, e, n = c.polygon_bbox(polygon)
    return {'process_graph': {
        'load': {'process_id': 'load_collection', 'arguments': {
            'id': 'SENTINEL2_L2A', 'spatial_extent': {'west': w, 'south': s, 'east': e, 'north': n},
            'temporal_extent': [start, end], 'bands': ['B04', 'B08', 'SCL']}},
        'mask': {'process_id': 'reduce_dimension', 'arguments': {
            'data': {'from_node': 'load'}, 'dimension': 'bands', 'reducer': {'process_graph': {
                'scl': {'process_id': 'array_element', 'arguments': {'data': {'from_parameter': 'data'}, 'label': 'SCL'}},
                'v': {'process_id': 'eq', 'arguments': {'x': {'from_node': 'scl'}, 'y': 4}},
                'b': {'process_id': 'eq', 'arguments': {'x': {'from_node': 'scl'}, 'y': 5}},
                'ok': {'process_id': 'or', 'arguments': {'x': {'from_node': 'v'}, 'y': {'from_node': 'b'}}},
                'cloud': {'process_id': 'not', 'arguments': {'x': {'from_node': 'ok'}}, 'result': True}}}}},
        'ndvi': {'process_id': 'ndvi', 'arguments': {'data': {'from_node': 'load'}, 'nir': 'B08', 'red': 'B04'}},
        'masked': {'process_id': 'mask', 'arguments': {'data': {'from_node': 'ndvi'}, 'mask': {'from_node': 'mask'}}},
        'agg': {'process_id': 'aggregate_spatial', 'arguments': {
            'data': {'from_node': 'masked'}, 'geometries': geom,
            'reducer': {'process_graph': {'m': {'process_id': 'mean', 'arguments': {'data': {'from_parameter': 'data'}}, 'result': True}}}}},
        'save': {'process_id': 'save_result', 'arguments': {'data': {'from_node': 'agg'}, 'format': 'JSON'}, 'result': True}}}


def openeo_ndvi(polygon, days=120):
    pts = require_polygon(polygon)
    tok = cdse_token()
    end = c._now(); start = end - timedelta(days=days)
    r = c.SESSION.post(OPENEO + '/result', json=openeo_graph(pts, f'{start:%Y-%m-%d}', f'{end:%Y-%m-%d}'),
                       headers={'Authorization': f'Bearer oidc/CDSE/{tok}'}, timeout=55)
    if r.status_code >= 400:
        try:
            e = r.json(); msg = f"{e.get('code', '')}: {e.get('message', '')}"[:300]
        except ValueError:
            msg = r.text[:200]
        hint = (' La clave de Sentinel Hub no habilita openEO; no hace falta: el NDVI de Copernicus ya llega por Sentinel Hub.'
                if r.status_code in (401, 403) else '')
        return c.envelope(None, OPENEO + '/result', 'NDVI zonal · openEO', 'Copernicus Data Space openEO', 'sin dato',
                          f'openEO respondió HTTP {r.status_code} · {msg}.{hint}')
    raw = r.json()
    rows = []
    for date, vals in sorted((raw or {}).items()):
        v = vals[0][0] if vals and isinstance(vals[0], list) and vals[0] else None
        if v is not None:
            rows.append({'datetime': date, 'ndvi_mean': _r(v), 'status': 'válida'})
    return c.envelope({'capability': 'ANALYSIS', 'index': 'NDVI', 'sensor': 'Sentinel-2 L2A',
                       'area_ha': area_ha(pts), 'series': rows, 'valid_scenes': len(rows),
                       'latest': rows[-1] if rows else None,
                       'note': 'openEO excluye píxeles nublados por SCL; fechas sin píxeles válidos no aparecen'},
                      OPENEO + '/result', 'NDVI zonal · openEO', 'Copernicus Data Space openEO',
                      'recibido' if rows else 'sin dato', None if rows else 'openEO no devolvió fechas válidas')


# ───────────────────────────── Google Earth Engine (REST) ─────────────────────────────
def _k(v):
    return {'constantValue': v}


def _f(name, **args):
    return {'functionInvocationValue': {'functionName': name, 'arguments': args}}


def gee_expression(polygon, years=10):
    """Serie MODIS MOD13Q1 NDVI (escala 0.0001) promediada sobre el lote, formato Cloud API."""
    pts = require_polygon(polygon)
    ring = geojson_polygon(pts)['coordinates']
    end = c._now(); start = end.replace(year=end.year - int(years))
    geom = _f('GeometryConstructors.Polygon', coordinates=_k(ring), geodesic=_k(False))
    coll = _f('Collection.filter',
              collection=_f('ImageCollection.load', id=_k('MODIS/061/MOD13Q1')),
              filter=_f('Filter.dateRangeContains',
                        leftValue=_f('DateRange', start=_k(f'{start:%Y-%m-%d}'), end=_k(f'{end:%Y-%m-%d}')),
                        rightField=_k('system:time_start')))
    img = {'argumentReference': '_MAPPING_VAR_0_0'}
    stats = _f('Image.reduceRegion', image=_f('Image.select', input=img, bandSelectors=_k(['NDVI'])),
               reducer=_f('Reducer.mean'), geometry={'valueReference': 'g'}, scale=_k(250), maxPixels=_k(1e8))
    body = _f('Feature', geometry=_k(None), metadata={'dictionaryValue': {'values': {
        't': _f('Element.get', object=img, property=_k('system:time_start')),
        'ndvi': _f('Dictionary.get', dictionary=stats, key=_k('NDVI'))}}})
    mapped = _f('Collection.map', collection=coll,
                baseAlgorithm={'functionDefinitionValue': {'argumentNames': ['_MAPPING_VAR_0_0'], 'body': 'body'}})
    return {'expression': {'result': 'out', 'values': {'g': geom, 'body': body, 'out': mapped}}}


def gee_token():
    proj, js = os.environ.get('GOOGLE_CLOUD_PROJECT'), os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    if not proj or not js:
        raise PermissionError('requiere credencial: GOOGLE_CLOUD_PROJECT, GOOGLE_APPLICATION_CREDENTIALS_JSON')
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError:
        raise PermissionError('falta la librería google-auth en requirements.txt')
    cred = service_account.Credentials.from_service_account_info(
        json.loads(js), scopes=['https://www.googleapis.com/auth/earthengine.readonly'])
    cred.refresh(Request())
    return proj, cred.token


def gee_ndvi(polygon, years=10):
    pts = require_polygon(polygon)
    years = int(years)
    if not 1 <= years <= 25:
        raise ValueError('Años fuera de rango (1-25)')
    def fail(msg):
        return c.envelope(None, GEE, f'NDVI histórico {years} años · Earth Engine', 'Google Earth Engine', 'sin dato', msg[:300])
    try:
        proj, tok = gee_token()
    except PermissionError:
        raise
    except json.JSONDecodeError:
        return fail('GOOGLE_APPLICATION_CREDENTIALS_JSON no es un JSON válido: hay que pegar el contenido completo del archivo, desde { hasta }.')
    except Exception as e:
        return fail(f'Google no aceptó la cuenta de servicio ({type(e).__name__}): {str(e)[:160]}')
    url = f'{GEE}/projects/{proj}/value:compute'
    r = c.SESSION.post(url, json=gee_expression(pts, years),
                       headers={'Authorization': f'Bearer {tok}'}, timeout=55)
    if r.status_code >= 400:
        try:
            msg = (r.json().get('error') or {}).get('message', '')
        except ValueError:
            msg = r.text[:200]
        return fail(f'Earth Engine respondió HTTP {r.status_code}: {msg}')
    feats = (r.json().get('result') or {}).get('features') or []
    rows = []
    for f in feats:
        p = f.get('properties') or {}
        if p.get('ndvi') is None or p.get('t') is None:
            continue
        from datetime import datetime, timezone
        rows.append({'datetime': datetime.fromtimestamp(p['t'] / 1000, timezone.utc).date().isoformat(),
                     'ndvi_mean': _r(p['ndvi'] * 0.0001), 'status': 'válida'})
    rows.sort(key=lambda x: x['datetime'])
    return c.envelope({'capability': 'ANALYSIS', 'index': 'NDVI', 'sensor': 'MODIS Terra MOD13Q1 (250 m, 16 días)',
                       'area_ha': area_ha(pts), 'years': years, 'series': rows, 'valid_scenes': len(rows),
                       'latest': rows[-1] if rows else None,
                       'note': 'Compuesto 16 días ya filtrado por calidad MODIS; lotes < 25 ha tienen muy pocos píxeles de 250 m'},
                      url.replace(proj, '{PROJECT}'), f'NDVI histórico {years} años · Earth Engine',
                      'Google Earth Engine · NASA MODIS', 'recibido' if rows else 'sin dato',
                      None if rows else 'Earth Engine no devolvió valores')


# ───────────────────────────── zonificación del lote por vigor ─────────────────────────────
ZONE_COLORS = {1: [217, 45, 32, 200], 2: [240, 160, 32, 200], 3: [25, 185, 138, 200]}
ZONE_NAMES = {1: 'Vigor bajo', 2: 'Vigor medio', 3: 'Vigor alto'}


def kmeans_1d(centros, pesos, k=3, iters=40):
    """k-medias en una dimensión sobre los centros del histograma, ponderado por la cantidad de píxeles."""
    pares = [(x, w) for x, w in zip(centros, pesos) if w > 0]
    if len(pares) < k:
        raise ValueError('Muy pocos píxeles con NDVI para zonificar')
    xs = sorted(x for x, _ in pares)
    cs = [xs[int((i + 0.5) * len(xs) / k)] for i in range(k)]
    for _ in range(iters):
        grupos = [[] for _ in range(k)]
        for x, w in pares:
            grupos[min(range(k), key=lambda j: abs(x - cs[j]))].append((x, w))
        nuevos = [sum(x * w for x, w in g) / sum(w for _, w in g) if g else cs[j] for j, g in enumerate(grupos)]
        if max(abs(a - b) for a, b in zip(nuevos, cs)) < 1e-4:
            break
        cs = nuevos
    cs.sort()
    return cs, [(cs[i] + cs[i + 1]) / 2 for i in range(k - 1)]


def _zone_expr(ndvi, cortes):
    t1, t2 = cortes
    return f'where(({ndvi})<{t1:.4f},1,where(({ndvi})<{t2:.4f},2,3))'


def ndvi_zones(polygon, days=60):
    """Tres zonas de vigor del lote con la escena Sentinel-2 despejada más reciente: cortes por k-medias del
    histograma de NDVI, superficie de cada zona y la expresión para dibujarlas."""
    pts = require_polygon(polygon)
    feature = {'type': 'Feature', 'properties': {}, 'geometry': geojson_polygon(pts)}
    items = best_tiles(search_s2(pts, days=days, limit=12, max_cloud=60), pts)
    ha = area_ha(pts)
    for it in items[:5]:
        row = scene_ndvi(it, feature)
        if row.get('status') != 'válida':
            continue
        r = c.SESSION.post(f'{PC_DATA}/item/statistics', json=feature, timeout=40,
                           params={'collection': 'sentinel-2-l2a', 'item': it['id'], 'expression': row['expression'],
                                   'asset_as_band': 'true', 'histogram_bins': 60, 'histogram_range': '-0.2,1'})
        r.raise_for_status()
        hist = _first_stats(r.json()).get('histogram') or [[], []]
        counts, edges = hist[0], hist[1]
        centros = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]
        cs, cortes = kmeans_1d(centros, counts)
        tot = sum(counts) or 1
        zonas = []
        for z, (lo, hi) in enumerate(zip([-1] + cortes, cortes + [2]), start=1):
            n = sum(w for x, w in zip(centros, counts) if lo <= x < hi)
            zonas.append({'zone': z, 'name': ZONE_NAMES[z], 'ndvi_center': round(cs[z - 1], 3), 'from': None if z == 1 else round(lo, 3),
                          'to': None if z == 3 else round(hi, 3), 'pct': round(100 * n / tot, 1), 'ha': round(ha * n / tot, 1),
                          'color': '#%02x%02x%02x' % tuple(ZONE_COLORS[z][:3])})
        return c.envelope({'item': it['id'], 'datetime': row['datetime'], 'clear_fraction_lot': row['clear_fraction_lot'],
                           'ndvi_mean': row.get('ndvi_mean'), 'cuts': [round(x, 4) for x in cortes], 'zones': zonas, 'area_ha': ha,
                           'processing_baseline': row.get('processing_baseline'),
                           'method': 'Sentinel-2 L2A (10 m) · NDVI · k-medias (3 grupos) sobre el histograma del lote'},
                          PC_STAC, 'zonas de vigor del lote', 'Copernicus Sentinel-2 · Microsoft Planetary Computer')
    return c.envelope(None, PC_STAC, 'zonas de vigor del lote', 'Copernicus Sentinel-2', 'sin dato',
                      f'No hubo una escena Sentinel-2 despejada sobre el lote en los últimos {days} días')


def zones_png(item_id, polygon, cuts, processing_baseline=None):
    """PNG de las tres zonas de vigor recortado al lote, para superponer en el mapa."""
    pts = require_polygon(polygon)
    if not isinstance(item_id, str) or not item_id.startswith('S2') or len(item_id) > 80 or not all(ch.isalnum() or ch in '_.' for ch in item_id):
        raise ValueError('Escena inválida')
    t1, t2 = (float(x) for x in cuts)
    if not (-1 <= t1 < t2 <= 1):
        raise ValueError('Cortes inválidos')
    expr = _zone_expr(ndvi_expression({'properties': {'s2:processing_baseline': processing_baseline}}), (t1, t2))
    feature = {'type': 'Feature', 'properties': {}, 'geometry': geojson_polygon(pts)}
    r = c.SESSION.post(f'{PC_DATA}/item/feature.png', json=feature, timeout=40,
                       params={'collection': 'sentinel-2-l2a', 'item': item_id, 'expression': expr, 'asset_as_band': 'true',
                               'colormap': json.dumps({str(k): v for k, v in ZONE_COLORS.items()}), 'max_size': 512})
    r.raise_for_status()
    if not r.headers.get('Content-Type', '').startswith('image/png'):
        raise ValueError('La API raster no devolvió PNG')
    w, s_, e, n = c.polygon_bbox(pts)
    return r.content, [[s_, w], [n, e]]
