"""Chequeo en vivo del sitio publicado: recorre cada función con un lote de control en tierra (Corrientes)
y muestra código, tiempo y error. Sale con código 1 si alguna ruta falla del lado del servidor (5xx)."""
import json, os, sys, time
import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'https://observatorio-agro.vercel.app').rstrip('/')
LOT = [[-28.56, -58.71], [-28.56, -58.69], [-28.54, -58.69], [-28.54, -58.71]]
LAT, LON = -28.55, -58.70
Q = {'lat': LAT, 'lon': LON, 'polygon': json.dumps(LOT)}
S = requests.Session(); S.headers['User-Agent'] = 'DOTS-chequeo-vivo/1.0'

GET = ['variables', 'modelos', 'historico', 'escenas', 'rios', 'aire', 'elevacion', 'ndvi', 'ndvi-modis', 'indices',
       'enso-cadena', 'enso-lote', 'enso-tablero', 'enso-sudamerica', 'mapbiomas', 'pasto-historia', 'cobertura-reciente', 'cambios-lote', 'ndvi-anomalia', 'etr-lote', 'heladas-satelite', 'focos', 'rinde-agua', 'salud-sudamerica', 'avisos', 'caminos', 'emergencia', 'estacional', 'precios-hacienda', 'indices-espectrales', 'radar-agua', 'balance-agua', 'sentinel-hub-ndvi', 'openeo-ndvi', 'gee-ndvi', 'gee', 'teleconexiones', 'estadistica', 'enso', 'suelo', 'serie', 'proyeccion', 'sustentabilidad', 'plataformas',
       'smn', 'nasa-power-30', 'landsat', 'radar', 'copernicus-stac', 'firms', 'ina']
POST = {
    'forraje': {'lat': LAT, 'lon': LON, 'polygon': LOT, 'kind': 'pastizal', 'use': 0.5, 'heads': 120},
    'alertas': {'lat': LAT, 'lon': LON, 'polygon': LOT},
    'costos': {'lat': LAT, 'lon': LON, 'destination': 'Corrientes, Argentina',
               'params': {'heads': 100, 'sale_kg': 400, 'price_kg': 2000, 'freight_km': 2500, 'truck_heads': 40, 'area_ha': 440}},
    'agentic': {'lat': LAT, 'lon': LON, 'prompt': 'Informe integral', 'polygon': LOT},
    'analizar': {'lat': LAT, 'lon': LON, 'polygon': LOT, 'nombre': 'Lote control'},
    'eudr/pdf': {'lot': {'name': 'Lote control', 'vertices': LOT}, 'establecimiento': 'Control'},
    'eudr/geojson': {'lot': {'name': 'Lote control', 'vertices': LOT}},
    'eudr/whisp': {'lot': {'name': 'Lote control', 'vertices': LOT}, 'product': 'bovino'},
    'ganado': {'lat': LAT, 'lon': LON, 'vertices': LOT, 'herd': [{'cat': 'vaca', 'heads': 120, 'weight': 420}, {'cat': 'ternero', 'heads': 60}]},
}


LINES = []


def out(line):
    print(line); LINES.append(line)


def show(name, r, t0, extra=''):
    ms = round((time.monotonic() - t0) * 1000)
    kind = r.headers.get('Content-Type', '').split(';')[0]
    try:
        js = r.json() if 'json' in kind else {}
    except ValueError:
        js = {}
    err = js.get('error') if isinstance(js, dict) else None
    st = js.get('status') if isinstance(js, dict) else None
    out(f"{r.status_code:>3}  {ms:>6} ms  {name:<16} {kind:<22} {st or '':<22} {(str(err) if err else '')[:110]}{extra}")
    return r.status_code


codes = {}
print(f'Chequeo en vivo de {BASE}\n')
for name in GET:
    t0 = time.monotonic()
    try:
        r = S.get(f'{BASE}/api/fuentes/{name}', params=dict(Q, series='22') if name == 'ina' else Q, timeout=65)
        codes[name] = show(name, r, t0)
    except Exception as e:
        codes[name] = 599; out(f"ERR  {round((time.monotonic()-t0)*1000):>6} ms  {name:<16} {type(e).__name__}")
    time.sleep(1.5)   # respeta los límites de las fuentes (SoilGrids, Nominatim)
for name, la, lo in (('inmet', -30.03, -51.20), ('dmc', -33.45, -70.66), ('eccc', 45.40, -75.69), ('inmet@corrientes', LAT, LON)):
    t0 = time.monotonic(); route = name.split('@')[0]
    try:
        r = S.get(f'{BASE}/api/fuentes/{route}', params={'lat': la, 'lon': lo}, timeout=65)
        js = r.json() if r.headers.get('Content-Type', '').startswith('application/json') else {}
        d = js.get('data') or {}
        codes[name] = show(name, r, t0, f"  {len(d.get('observations') or [])} obs · {d.get('source_mode', '')} · estaciones del país en NOAA: {d.get('stations_in_country', '-')} · {[x.get('name') for x in d.get('stations') or []]}")
    except Exception as e:
        codes[name] = 599; out(f"ERR  {round((time.monotonic()-t0)*1000):>6} ms  {name:<16} {type(e).__name__}")
    time.sleep(1.5)
for name, body in POST.items():
    t0 = time.monotonic()
    try:
        r = S.post(f'{BASE}/api/fuentes/{name}', json=body, timeout=65)
        extra = f'  {len(r.content) // 1024} KB' if r.headers.get('Content-Type', '').startswith(('application/pdf', 'application/geo')) else ''
        codes[name] = show(name, r, t0, extra)
    except Exception as e:
        codes[name] = 599; out(f"ERR  {round((time.monotonic()-t0)*1000):>6} ms  {name:<16} {type(e).__name__}")
    time.sleep(1.5)
for path in ['/', '/observatorio', '/libre-deforestacion', '/que-es-dots']:
    t0 = time.monotonic(); r = S.get(BASE + path, timeout=30); codes[path] = show(path, r, t0)

# Capas del mapa: una tesela sobre Corrientes (z=8) por capa del catálogo
import math, re
from datetime import date, timedelta
try:
    src = open(os.path.join(os.path.dirname(__file__), '..', 'src', 'dashboard', 'openLayers.ts'), encoding='utf-8').read()
    layers = json.loads(src[src.index('OPEN_LAYERS: OpenLayer[] = ') + 27: src.index('];') + 1])
except Exception as e:
    layers = []; out(f'No se pudo leer el catálogo de capas: {e}')
bad_layers = []
for l in layers:
    z = min(8, l.get('maxNativeZoom') or 8)
    n = 2 ** z; x = int((LON + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(LAT)) + 1 / math.cos(math.radians(LAT))) / math.pi) / 2 * n)
    if l.get('tms'): y = n - 1 - y
    u = l['url'].replace('{time}', (date.today() - timedelta(days=2)).isoformat()).replace('{s}', (l.get('subdomains') or 'a')[0])   # NASA publica con 1-2 días de atraso
    u = u.replace('{z}', str(z)).replace('{x}', str(x)).replace('{y}', str(y))
    t0 = time.monotonic()
    try:
        r = S.get(u, timeout=25)
        ok = r.status_code == 200 and r.headers.get('Content-Type', '').startswith('image')
        code = r.status_code
    except Exception as e:
        ok, code = False, type(e).__name__
    if not ok: bad_layers.append(l['name'])
    out(f"{'OK ' if ok else 'MAL'}  {round((time.monotonic()-t0)*1000):>6} ms  capa · {l['name'][:60]}  ({code})")
out(f"Capas: {len(layers) - len(bad_layers)} de {len(layers)} devuelven imagen." + (f" Sin imagen: {', '.join(bad_layers)}" if bad_layers else ''))

bad = {k: v for k, v in codes.items() if v >= 500 and v != 503}   # 503 = fuente externa caída, se informa aparte
slow = {k: v for k, v in codes.items() if v in (429, 503)}
out(f"{len(codes) - len(bad)} de {len(codes)} sin error de DOTS." + (f" Fallan: {', '.join(bad)}" if bad else '')
    + (f" Fuente externa sin respuesta o con límite: {', '.join(slow)}" if slow else ''))
if os.environ.get('GITHUB_ACTIONS'):
    # la tabla también queda como anotación, legible por la API de GitHub
    rutas = [l for l in LINES if 'capa ·' not in l and not l.startswith('Capas:')]
    capas = [l for l in LINES if 'capa ·' in l or l.startswith('Capas:')]
    for title, part in (('Rutas', rutas), ('Capas del mapa', capas)):
        print(f'::notice title={title}::' + '%0A'.join(l.replace('%', '%25') for l in part))
sys.exit(1 if bad else 0)
