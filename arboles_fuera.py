"""arboles_fuera v1.0 — árboles fuera del bosque: cortinas, árboles sueltos y montes dentro del lote (Earth Engine REST).

Árboles: clase «árboles» de ESA WorldCover 2021 (10 m, Sentinel-1 y Sentinel-2, CC BY 4.0).
Bosque: mapa de bosques 2020 del JRC (GFC2020 v2), el que la Comisión Europea usa como referencia del EUDR.
Árboles fuera del bosque: píxeles con árboles que ese mapa no considera bosque. Se separan por tamaño del parche:
  · menos de 0,5 ha: cortinas forestales, árboles sueltos, sombra para la hacienda y bordes de caminos;
  · 0,5 ha o más: montes y bosquecillos. Si además superan 5 m de altura y 10 % de cobertura, podrían cumplir la
    definición de bosque de la FAO que usa el EUDR aunque el mapa de referencia no los marque: conviene revisarlos.
Es una medición satelital a 10 m: una cortina angosta puede quedar subestimada y un parche de pastizal alto, confundido.
"""
import json

import research_connectors as c
import vegetation as veg

GEE = veg.GEE
WC = 'ESA/WorldCover/v200'
JRC = 'JRC/GFC2020/V2'
SMALL_PX = 50          # 50 píxeles de 10 m = 0,5 ha, umbral de superficie de la definición de bosque de la FAO
PNG_PX = 512
COLORS = {'forest': '1b5e20', 'small': 'f2a900', 'large': '7cb342'}


def _f(name, **args):
    return {'functionInvocationValue': {'functionName': name, 'arguments': args}}


def _k(v):
    return {'constantValue': v}


def _const(v):
    return _f('Image.constant', value=_k(v))


def _geom(pts):
    return _f('GeometryConstructors.Polygon', coordinates=_k(veg.geojson_polygon(pts)['coordinates']), geodesic=_k(False))


def layers():
    """Máscaras 0/1: bosque 2020 (JRC), árboles dentro del bosque, árboles fuera en parches chicos y en parches grandes."""
    wc = _f('Image.select', input=_f('Collection.first', collection=_f('ImageCollection.load', id=_k(WC))), bandSelectors=_k(['Map']))
    tree = _f('Image.eq', image1=wc, image2=_const(10))
    jrc = _f('Image.select', input=_f('ImageCollection.mosaic', collection=_f('ImageCollection.load', id=_k(JRC))), bandSelectors=_k([0]))
    forest = _f('Image.unmask', input=_f('Image.eq', image1=jrc, image2=_const(1)), value=_k(0))
    outside = _f('Image.and', image1=tree, image2=_f('Image.not', value=forest))
    size = _f('Image.unmask', input=_f('Image.connectedPixelCount', input=_f('Image.selfMask', image=outside),
                                       maxSize=_k(SMALL_PX + 1), eightConnected=_k(True)), value=_k(0))
    small = _f('Image.and', image1=outside, image2=_f('Image.lt', image1=size, image2=_const(SMALL_PX)))
    large = _f('Image.and', image1=outside, image2=_f('Image.gte', image1=size, image2=_const(SMALL_PX)))
    inside = _f('Image.and', image1=tree, image2=forest)
    return {'forest': forest, 'inside': inside, 'small': small, 'large': large}


def expression(pts):
    ly = layers()
    ha = _f('Image.divide', image1=_f('Image.pixelArea'), image2=_const(10000))
    img = None
    for name in ('forest', 'inside', 'small', 'large'):
        band = _f('Image.rename', input=_f('Image.multiply', image1=ly[name], image2=ha), names=_k([name]))
        img = band if img is None else _f('Image.addBands', dstImg=img, srcImg=band)
    out = _f('Image.reduceRegion', image=img, reducer=_f('Reducer.sum'), geometry={'valueReference': 'g'},
             scale=_k(10), maxPixels=_k(1e9), tileScale=_k(4))
    return {'expression': {'result': 'out', 'values': {'g': _geom(pts), 'out': out}}}


def bbox(pts, pad=0.08):
    lats = [p[0] for p in pts]; lons = [p[1] for p in pts]
    s, n, w, e = min(lats), max(lats), min(lons), max(lons)
    dy, dx = max((n - s) * pad, 0.001), max((e - w) * pad, 0.001)
    return w - dx, s - dy, e + dx, n + dy


def png_expression(pts):
    """Imagen del lote: bosque 2020 (verde oscuro), cortinas y árboles sueltos (ámbar), montes fuera del bosque (verde claro)."""
    ly = layers()
    g = _geom(pts)
    vis = []
    for name, key in (('forest', 'forest'), ('small', 'small'), ('large', 'large')):
        vis.append(_f('Image.visualize', image=_f('Image.clip', input=_f('Image.selfMask', image=ly[name]), geometry=g),
                      palette=_k([COLORS[key]]), opacity=_k(0.45 if name == 'forest' else 0.95)))
    outline = _f('Image.visualize', image=_f('Image.paint', image=_f('Image.byte', value=_const(0)), featureCollection=
                                           _f('Collection', features={'arrayValue': {'values': [_f('Feature', geometry=g)]}}),
                                           color=_k(1), width=_k(2)),
                 palette=_k(['ffffff']), min=_k(0), max=_k(1))
    outline = _f('Image.selfMask', image=outline)
    out = _f('ImageCollection.mosaic', collection=_f('ImageCollection.fromImages', images={'arrayValue': {'values': vis + [outline]}}))
    w, s, e, n = bbox(pts)
    width = PNG_PX
    height = max(96, min(1024, round(width * (n - s) / max(e - w, 1e-9) / max(__import__('math').cos(__import__('math').radians((n + s) / 2)), 0.2))))
    grid = {'dimensions': {'width': width, 'height': height},
            'affineTransform': {'scaleX': (e - w) / width, 'shearX': 0, 'translateX': w, 'shearY': 0, 'scaleY': -(n - s) / height, 'translateY': n},
            'crsCode': 'EPSG:4326'}
    return {'expression': {'result': 'out', 'values': {'out': out}}, 'fileFormat': 'PNG', 'grid': grid}, [s, w, n, e]


def _post(path, body, raw=False):
    proj, tok = veg.gee_token()
    r = c.SESSION.post(f'{GEE}/projects/{proj}/{path}', json=body, headers={'Authorization': f'Bearer {tok}'}, timeout=55)
    if r.status_code >= 400:
        try:
            msg = (r.json().get('error') or {}).get('message', '')
        except ValueError:
            msg = r.text[:200]
        raise RuntimeError(f'Earth Engine HTTP {r.status_code}: {msg[:160]}')
    return r.content if raw else r.json().get('result')


def _n(x):
    return f'{x:,.1f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def summarize(raw, lot_ha):
    r = {k: round(float((raw or {}).get(k) or 0), 2) for k in ('forest', 'inside', 'small', 'large')}
    trees = r['inside'] + r['small'] + r['large']
    outside = r['small'] + r['large']
    pct = lambda x: round(100 * x / lot_ha, 1) if lot_ha else None
    out = {'lot_ha': round(lot_ha, 1), 'forest_2020_ha': r['forest'], 'trees_ha': round(trees, 2), 'trees_pct': pct(trees),
           'in_forest_ha': r['inside'], 'outside_ha': round(outside, 2), 'outside_pct': pct(outside),
           'small_ha': r['small'], 'large_ha': r['large'],
           'outside_share': round(100 * outside / trees, 0) if trees else None}
    if trees < 0.05:
        reading = 'El mapa no registra árboles en el lote.'
    elif outside < 0.05:
        reading = f"Todos los árboles del lote ({_n(trees)} ha) están dentro del bosque 2020 de referencia de la UE."
    else:
        reading = (f"Hay {_n(outside)} ha de árboles fuera del bosque de referencia de la UE ({_n(pct(outside))} % del lote): "
                   f"{_n(r['small'])} ha en cortinas y árboles sueltos y {_n(r['large'])} ha en montes de 0,5 ha o más.")
    if r['large'] >= 0.5:
        reading += (' Los montes de 0,5 ha o más podrían contar como bosque para el EUDR si superan 5 m de altura: '
                    'antes de talarlos conviene verificarlos y consultar el ordenamiento provincial (Ley 26.331).')
    out['reading'] = reading
    out['ranges'] = [['Cortinas y árboles sueltos', 'parches de menos de 0,5 ha fuera del bosque 2020'],
                     ['Montes', 'parches de 0,5 ha o más fuera del bosque 2020: revisar altura y cobertura'],
                     ['Bosque 2020', 'lo que el mapa del JRC marca como bosque: cualquier pérdida posterior cuenta para el EUDR']]
    return out


def analyze(polygon):
    pts = veg.require_polygon(polygon)
    lot = veg.area_ha(pts)
    try:
        raw = _post('value:compute', expression(pts))
    except RuntimeError as e:
        return c.envelope(None, GEE, 'árboles fuera del bosque · lote', 'ESA WorldCover · JRC vía Google Earth Engine', 'sin dato', str(e)[:300])
    data = summarize(raw, lot)
    data['method'] = __doc__.split('\n\n', 1)[1].strip()
    data['sources'] = ['ESA WorldCover 10 m 2021 v200 (Zanaga et al., 2022) · CC BY 4.0',
                       'JRC Global Forest Cover 2020 v2 (Bourgoin et al., 2024) · referencia del EUDR']
    return c.envelope(data, GEE, 'árboles fuera del bosque · lote', 'ESA WorldCover · JRC vía Google Earth Engine')


def png(polygon):
    pts = veg.require_polygon(polygon)
    body, bounds = png_expression(pts)
    content = _post('image:computePixels', body, raw=True)
    if not content.startswith(b'\x89PNG'):
        raise RuntimeError('Earth Engine no devolvió una imagen')
    return content, bounds
