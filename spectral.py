"""spectral v1.0 — índices satelitales a pedido sobre Sentinel-2 L2A.

Catálogo: awesome-spectral-indices (github.com/awesome-spectral-indices/awesome-spectral-indices, licencia MIT),
filtrado a los índices que se calculan sólo con bandas de Sentinel-2 y constantes con valor por defecto
(228 de 280; ver spectral_indices.json). Cada fórmula se traduce a una expresión de reflectancia y se calcula
con la estadística zonal de Planetary Computer (TiTiler) dentro del polígono, en la última escena despejada.
"""
import json, os, re
from concurrent.futures import ThreadPoolExecutor

import research_connectors as c
import vegetation as veg

_HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = json.load(open(os.path.join(_HERE, 'spectral_indices.json'), encoding='utf-8'))['indices']
S2 = {'B': 'B02', 'G': 'B03', 'R': 'B04', 'RE1': 'B05', 'RE2': 'B06', 'RE3': 'B07', 'N': 'B08', 'N2': 'B8A', 'S1': 'B11', 'S2': 'B12'}
FUNCS = {'sqrt', 'log', 'exp', 'abs', 'arctan', 'sin', 'cos', 'tan', 'arcsin', 'arccos', 'where'}
DOMAIN_ES = {'vegetation': 'vegetación', 'water': 'agua', 'soil': 'suelo', 'burn': 'quemas', 'urban': 'construido',
             'snow': 'nieve', 'clouds': 'nubes'}

# Grupo base para el campo, con explicación en castellano
DEFAULT = {
    'NDVI': 'Vigor general de la vegetación.',
    'EVI': 'Vigor en pasturas densas; no se satura como el NDVI.',
    'MSAVI': 'Vigor con pasto ralo, corrigiendo el suelo desnudo.',
    'GNDVI': 'Clorofila y nitrógeno del canopeo.',
    'NDREI': 'Borde rojo: estado de nitrógeno y estrés antes de que se vea en el NDVI.',
    'CIRE': 'Clorofila por borde rojo; sensible a cambios finos de verdor.',
    'NIRv': 'Productividad: aproxima la fotosíntesis del lote.',
    'NDMI': 'Humedad del follaje; bajo anticipa estrés hídrico.',
    'MNDWI': 'Agua libre en superficie, también con turbidez.',
    'NBR': 'Quemas: valores bajos indican área quemada.',
    'NBR2': 'Quemas y humedad del suelo.',
    'BI': 'Suelo desnudo: alto indica falta de cobertura o sobrepastoreo.',
}


def expression(name, item):
    """Fórmula del catálogo → expresión TiTiler con reflectancias (offset −1000 desde baseline 04.00)."""
    ix = CATALOG.get(name)
    if not ix:
        raise ValueError(f'Índice desconocido: {name}')
    pb = str((item.get('properties') or {}).get('s2:processing_baseline') or '0')
    try:
        off = float(pb) >= 4.0
    except ValueError:
        off = False

    def sub(m):
        t = m.group(0)
        if t in S2:
            return veg._refl(S2[t], off)
        if t in ix['constants']:
            return repr(float(ix['constants'][t]))
        if t in FUNCS:
            return t
        raise ValueError(f'Símbolo no soportado en {name}: {t}')
    return re.sub(r'[A-Za-z_][A-Za-z0-9_]*', sub, ix['formula'])


def catalog_summary():
    from collections import Counter
    cnt = Counter(DOMAIN_ES.get(v['domain'], v['domain']) for v in CATALOG.values())
    return {'total': len(CATALOG), 'by_domain': dict(cnt),
            'default': list(DEFAULT), 'all': sorted(CATALOG)}


def compute(polygon, names=None, days=120):
    """Índices sobre la última escena Sentinel-2 despejada del lote."""
    pts = veg.require_polygon(polygon)
    names = [n for n in (names or list(DEFAULT)) if n in CATALOG][:30]
    if not names:
        raise ValueError('Elegí al menos un índice del catálogo')
    feature = {'type': 'Feature', 'properties': {}, 'geometry': veg.geojson_polygon(pts)}
    items = veg.best_tiles(veg.search_s2(pts, days=days, limit=18), pts)
    scene = None
    for it in items[:6]:
        row = veg.scene_ndvi(it, feature)
        if row.get('status') == 'válida':
            scene = (it, row); break
    if not scene:
        return c.envelope({'indices': [], 'catalog': catalog_summary()}, veg.PC_DATA, 'índices satelitales del lote',
                          'Planetary Computer · ESA Sentinel-2', 'sin dato', f'Sin escena Sentinel-2 despejada en {days} días')
    it, row = scene

    def one(n):
        ix = CATALOG[n]
        out = {'name': n, 'long_name': ix['long_name'], 'domain': DOMAIN_ES.get(ix['domain'], ix['domain']),
               'meaning': DEFAULT.get(n, ''), 'formula': ix['formula'], 'reference': ix.get('reference')}
        try:
            st = veg._pc_stats(it['id'], feature, expression(n, it))
            out.update(mean=veg._r(st.get('mean')), p2=veg._r(st.get('percentile_2')), p98=veg._r(st.get('percentile_98')))
        except Exception as e:
            out.update(mean=None, error=type(e).__name__)
        return out
    with ThreadPoolExecutor(max_workers=6) as pool:
        res = list(pool.map(one, names))
    return c.envelope({'capability': 'ANALYSIS', 'scene': row.get('item'), 'datetime': row.get('datetime'),
                       'clear_fraction_lot': row.get('clear_fraction_lot'), 'indices': res, 'catalog': catalog_summary(),
                       'source': 'Fórmulas: awesome-spectral-indices (MIT). Imagen: ESA Sentinel-2 L2A vía Microsoft Planetary Computer.'},
                      veg.PC_DATA + '/item/statistics', 'índices satelitales del lote', 'Planetary Computer · ESA Sentinel-2 · awesome-spectral-indices')
