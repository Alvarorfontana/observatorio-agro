"""gfm — Copernicus Global Flood Monitoring (GFM): agua de crecida detectada por radar Sentinel-1.

GFM procesa cada pasada de Sentinel-1 apenas llega (unas 8 h después de la toma) con tres algoritmos y publica la
"extensión de inundación observada" a 20 m, separada del agua permanente (ríos, lagunas). Es abierto y sin clave:
  · Catálogo STAC de EODC (colección GFM): fecha de la última pasada sobre un recuadro y píxeles inundados.
  · WMS-T de EODC: el mapa de agua de crecida del día, como PNG transparente, para superponer y medir.
Los nombres de las capas se leen del propio servicio (GetCapabilities): si EODC los cambia, DOTS no se rompe.
"""
import re, time
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import research_connectors as c

STAC = 'https://stac.eodc.eu/api/v1'
WMS = 'https://geoserver.gfm.eodc.eu/geoserver/gfm/wms'
PORTAL = 'https://global-flood.emergency.copernicus.eu'
_CAPS = {'t': 0, 'v': None}


def _strip(tag):
    return tag.split('}', 1)[-1]


def parse_capabilities(xml_bytes):
    """{nombre: {'title', 'times'}} de un GetCapabilities WMS (1.1.1 o 1.3.0)."""
    root = ET.fromstring(xml_bytes)
    out = {}
    for el in root.iter():
        if _strip(el.tag) != 'Layer':
            continue
        name = title = None; times = ''
        for ch in el:
            t = _strip(ch.tag)
            if t == 'Name': name = (ch.text or '').strip()
            elif t == 'Title': title = (ch.text or '').strip()
            elif t in ('Dimension', 'Extent') and (ch.get('name') or '').lower() == 'time' and (ch.text or '').strip():
                times = ch.text.strip()
        if name:
            out[name] = {'title': title or name, 'times': times}
    return out


def latest_time(times, today=None):
    """Último día publicado según la dimensión TIME ('a,b,c' o 'inicio/fin/P1D'). None si no se puede leer."""
    if not times:
        return None
    today = (today or date.today()).isoformat()
    vals = []
    for part in times.split(','):
        part = part.strip()
        if '/' in part:
            part = part.split('/')[1]
        m = re.match(r'\d{4}-\d{2}-\d{2}', part)
        if m and m.group(0) <= today:
            vals.append(m.group(0))
    return max(vals) if vals else None


def pick_layers(caps):
    """Capa de agua de crecida observada y capa de agua de referencia (permanente)."""
    def find(*keys, avoid=('likelihood', 'uncertain', 'maximum', 'advisory', 'exclusion')):
        for k in keys:
            for n in caps:
                low = n.lower()
                if k in low and not any(a in low for a in avoid):
                    return n
        return None
    return {'flood': find('observed_flood_extent', 'ensemble_flood_extent', 'flood_extent', 'flood'),
            'reference': find('reference_water', 'permanent_water')}


def capabilities():
    if _CAPS['v'] and time.monotonic() - _CAPS['t'] < 12 * 3600:
        return _CAPS['v']
    r = c.SESSION.get(WMS, params={'service': 'WMS', 'request': 'GetCapabilities', 'version': '1.1.1'}, timeout=25)
    r.raise_for_status()
    caps = parse_capabilities(r.content)
    if not caps:
        raise ValueError('GFM no devolvió capas')
    _CAPS.update(t=time.monotonic(), v=caps)
    return caps


def last_pass(bbox, today=None, days=12):
    """Última pasada de Sentinel-1 procesada por GFM sobre el recuadro (lon/lat): fecha y si detectó inundación."""
    today = today or date.today()
    w, s, e, n = bbox
    body = {'collections': ['GFM'], 'bbox': [w, s, e, n], 'limit': 50,
            'datetime': f'{(today - timedelta(days=days)).isoformat()}T00:00:00Z/{today.isoformat()}T23:59:59Z'}
    feats = c._post(STAC + '/search', body, timeout=25).json().get('features', [])
    if not feats:
        return None
    def day(f):
        p = f.get('properties') or {}
        return str(p.get('sensing_date') or p.get('datetime') or '')[:10]
    last = max(day(f) for f in feats)
    same = [f for f in feats if day(f) == last]
    flooded = sum(int((f.get('properties') or {}).get('flooded_pixels') or 0) for f in same)
    return {'date': last, 'tiles': len(same), 'flooded_pixels_tiles': flooded, 'passes': len({day(f) for f in feats})}


def getmap(layer, bbox, day, width, height):
    """PNG transparente de una capa GFM para el recuadro y el día. None si el servicio no responde."""
    w, s, e, n = bbox
    r = c.SESSION.get(WMS, timeout=30, params={'service': 'WMS', 'request': 'GetMap', 'version': '1.1.1', 'layers': layer, 'styles': '',
                                               'srs': 'EPSG:4326', 'bbox': f'{w},{s},{e},{n}', 'width': width, 'height': height,
                                               'format': 'image/png', 'transparent': 'true', 'time': day})
    if r.ok and r.content[:8] == b'\x89PNG\r\n\x1a\n':
        return r.content
    return None


def covered(png):
    """Fracción de píxeles pintados (no transparentes) de un PNG de máscara."""
    from io import BytesIO
    from PIL import Image
    im = Image.open(BytesIO(png)).convert('RGBA')
    a = im.getchannel('A').tobytes()
    return sum(1 for v in a if v > 40) / max(1, len(a))


def area_km2(bbox):
    import math
    w, s, e, n = bbox
    lat = math.radians((s + n) / 2)
    return abs(e - w) * 111.32 * math.cos(lat) * abs(n - s) * 110.54


def flood_at(bbox, today=None, width=900, height=620):
    """Agua de crecida observada por GFM en el recuadro, en la última pasada de radar.
    Devuelve dict con fecha, km² inundados (fuera del agua permanente), km² de agua permanente y la máscara PNG."""
    today = today or date.today()
    caps = capabilities()
    lay = pick_layers(caps)
    if not lay['flood']:
        raise ValueError('GFM no publica la capa de agua de crecida')
    lp = None
    try:
        lp = last_pass(bbox, today)
    except Exception:
        pass
    day = (lp or {}).get('date') or latest_time(caps[lay['flood']]['times'], today) or (today - timedelta(days=1)).isoformat()
    mask = getmap(lay['flood'], bbox, day, width, height)
    if mask is None:
        raise ValueError('GFM no devolvió el mapa')
    ref = getmap(lay['reference'], bbox, day, width, height) if lay['reference'] else None
    total = area_km2(bbox)
    fl = covered(mask)
    return {'date': day, 'age': (today - date.fromisoformat(day)).days, 'layer': lay['flood'],
            'flood_km2': round(fl * total, 1), 'flood_pct': round(100 * fl, 1),
            'water_km2': round(covered(ref) * total, 1) if ref else None,
            'box_km2': round(total), 'mask': mask, 'passes': (lp or {}).get('passes'), 'bbox': bbox,
            'source': WMS, 'portal': PORTAL}


def overlay(base, mask, color=(217, 45, 32)):
    """Pinta la máscara de crecida (rojo, 65 %) sobre la foto base, ajustando tamaños. Devuelve PNG."""
    from io import BytesIO
    from PIL import Image
    b = Image.open(BytesIO(base)).convert('RGBA')
    m = Image.open(BytesIO(mask)).convert('RGBA').resize(b.size)
    alpha = m.getchannel('A').point(lambda v: 165 if v > 40 else 0)
    layer = Image.new('RGBA', b.size, color + (0,)); layer.putalpha(alpha)
    out = Image.alpha_composite(b, layer).convert('RGB')
    buf = BytesIO(); out.save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def web_layers(today=None):
    """Para el mapa de la web: capas WMS y último día publicado (el navegador las pide directo a EODC)."""
    caps = capabilities()
    lay = pick_layers(caps)
    return c.envelope({'wms': WMS, 'flood': lay['flood'], 'reference': lay['reference'],
                       'date': latest_time((caps.get(lay['flood']) or {}).get('times'), today) if lay['flood'] else None,
                       'portal': PORTAL},
                      WMS, 'agua de crecida observada', 'Copernicus GFM (Sentinel-1)',
                      'recibido' if lay['flood'] else 'sin dato', None if lay['flood'] else 'GFM no publica la capa')
