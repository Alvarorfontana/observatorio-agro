"""campo_offline v1.0 — informe de campo con mapa para el celular que funciona sin señal (código QR).

El mapa del campo (límite, zonas de riesgo hídrico y un resumen) viaja comprimido dentro del enlace, después del "#":
esa parte no se envía a ningún servidor, así que el campo no queda guardado en DOTS. Al abrir el enlace una vez con
señal, la página /campo guarda en el teléfono el programa y las imágenes satelitales del campo; después funciona sin
conexión y, con el GPS, dice en qué zona del campo está parado el usuario.
"""
import base64
import json
import os
import zlib
from datetime import datetime, timezone

import research_connectors as c

SITE = 'https://observatorio-agro.vercel.app'
CHARS = {'loma': 'L', 'plano': 'P', 'bajo': 'B', 'anegable': 'A', 'laguna': 'W'}
MAX_HASH = 1150          # caracteres del enlace comprimido: QR legible impreso a ~5 cm
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report')
TEMPLATE = os.path.join(BASE, 'campo.typ')
FONTS = os.path.join(BASE, 'fonts')


def _b64(data):
    co = zlib.compressobj(9, zlib.DEFLATED, -15)          # deflate "crudo": lo abre DecompressionStream('deflate-raw')
    raw = co.compress(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()) + co.flush()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def decode(token):
    raw = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))
    return json.loads(zlib.decompress(raw, -15))


def simplify(poly, n=60):
    if len(poly) <= n:
        return poly
    step = len(poly) / n
    return [poly[int(i * step)] for i in range(n)]


def grid_string(cells, dlat, dlon, factor=1):
    """Celdas [lat, lon, clase] → origen, paso, filas, columnas y una letra por celda ('.' fuera del campo)."""
    s = min(x[0] for x in cells); w = min(x[1] for x in cells)
    dla, dlo = dlat * factor, dlon * factor
    rows = int(round((max(x[0] for x in cells) - s) / dla)) + 1
    cols = int(round((max(x[1] for x in cells) - w) / dlo)) + 1
    votes = {}
    for la, lo, k in cells:
        key = (int(round((la - s) / dla)), int(round((lo - w) / dlo)))
        v = votes.setdefault(key, {})
        v[k] = v.get(k, 0) + 1
    g = ['.'] * (rows * cols)
    for (i, j), v in votes.items():
        if 0 <= i < rows and 0 <= j < cols:
            g[i * cols + j] = CHARS[max(v, key=v.get)]
    return {'o': [round(s, 6), round(w, 6)], 'd': [round(dla, 7), round(dlo, 7)], 'r': rows, 'c': cols, 'g': ''.join(g)}


def payload(name, polygon, risk, extra_lines=None):
    """Arma el enlace del mapa sin señal; achica la grilla hasta que entre en un QR legible."""
    lines = [[z['name'], f"{z['pct']:.0f} % · {z['ha']:.0f} ha"] for z in risk['zones'] if z['pct'] >= 0.5]
    lines += (extra_lines or [])[:5]
    base = {'v': 1, 'n': name[:60], 'f': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'p': [[round(a, 5), round(b, 5)] for a, b in simplify(polygon)], 's': lines}
    g = risk['grid']
    for factor in (1, 2, 3, 4, 6, 8):
        tok = _b64({**base, 'z': grid_string(g['cells'], g['dlat'], g['dlon'], factor)})
        if len(tok) <= MAX_HASH:
            return f'{SITE}/campo#d={tok}', factor
    return f"{SITE}/campo#d={_b64(base)}", None


def qr_svg(url):
    import segno
    q = segno.make(url, error='l', micro=False)
    import io
    buf = io.BytesIO()
    q.save(buf, kind='svg', scale=4, border=2, dark='#0b2b33', xmldecl=False, svgns=True)
    return buf.getvalue().decode()


def zones_svg(risk, polygon, width=520):
    """Mapa simple de las zonas del campo en SVG (para el PDF)."""
    g = risk['grid']; cells = g['cells']
    lats = [p[0] for p in polygon]; lons = [p[1] for p in polygon]
    s, n, w, e = min(lats), max(lats), min(lons), max(lons)
    import math
    kx = math.cos(math.radians((s + n) / 2))
    W = (e - w) * kx; H = (n - s)
    sc = width / max(W, H * 1.0)
    height = H * sc
    X = lambda lo: (lo - w) * kx * sc
    Y = lambda la: (n - la) * sc
    col = {k: col for k, _, col in [(z['key'], z['name'], z['color']) for z in risk['zones']]}
    cw, ch = g['dlon'] * kx * sc + 0.6, g['dlat'] * sc + 0.6
    rects = ''.join(f'<rect x="{X(lo) - cw / 2:.1f}" y="{Y(la) - ch / 2:.1f}" width="{cw:.1f}" height="{ch:.1f}" fill="{col.get(k, "#ccc")}"/>'
                    for la, lo, k in cells)
    pts = ' '.join(f'{X(lo):.1f},{Y(la):.1f}' for la, lo in polygon)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">'
            f'{rects}<polygon points="{pts}" fill="none" stroke="#111" stroke-width="2"/></svg>')


def build(name, polygon, risk, extra_lines=None):
    url, factor = payload(name, polygon, risk, extra_lines)
    return {'name': name, 'date': datetime.now(timezone.utc).strftime('%d/%m/%Y'), 'area_ha': risk.get('area_ha'),
            'risk': {k: risk.get(k) for k in ('zones', 'cuts', 'relief_m', 'water_seen_ha', 'hand_median_m', 'reading', 'method')},
            'extra': extra_lines or [], 'map_svg': zones_svg(risk, polygon), 'qr_svg': qr_svg(url), 'url': url,
            'grid_factor': factor}


def pdf(name, polygon, lat, lon):
    import riesgo_hidrico as rh
    import typst
    env = rh.analyze(polygon)
    if env.get('status') != 'recibido':
        raise RuntimeError(env.get('error') or 'Sin datos de relieve')
    risk = env['data']
    extra = []
    try:
        import suelos_ba
        su = suelos_ba.at_polygon(polygon)
        if su and su.get('units'):
            u = su['units'][0]
            extra.append(['Suelo principal', f"{u.get('symbol') or u.get('name')} · {u['pct']:.0f} %"])
    except Exception:
        su = None
    data = build(name, polygon, risk, extra)
    data['soils'] = su
    out = typst.compile(TEMPLATE, root=BASE, font_paths=[FONTS], ignore_system_fonts=True,
                        sys_inputs={'data': json.dumps(data, ensure_ascii=False)})
    if out[:5] != b'%PDF-':
        raise RuntimeError('Typst no generó el PDF')
    return out, data['url']
