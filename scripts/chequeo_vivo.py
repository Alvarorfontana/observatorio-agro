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
       'teleconexiones', 'estadistica', 'enso', 'suelo', 'serie', 'proyeccion', 'sustentabilidad', 'plataformas',
       'smn', 'inmet', 'nasa-power-30', 'landsat', 'radar', 'copernicus-stac', 'firms', 'ina']
POST = {
    'forraje': {'lat': LAT, 'lon': LON, 'polygon': LOT, 'kind': 'pastizal', 'use': 0.5, 'heads': 120},
    'alertas': {'lat': LAT, 'lon': LON, 'polygon': LOT},
    'costos': {'lat': LAT, 'lon': LON, 'destination': 'Corrientes, Argentina',
               'params': {'heads': 100, 'sale_kg': 400, 'price_kg': 2000, 'freight_km': 2500, 'truck_heads': 40, 'area_ha': 440}},
    'agentic': {'lat': LAT, 'lon': LON, 'prompt': 'Informe integral', 'polygon': LOT},
    'analizar': {'lat': LAT, 'lon': LON, 'polygon': LOT, 'nombre': 'Lote control'},
    'eudr/pdf': {'lot': {'name': 'Lote control', 'vertices': LOT}, 'establecimiento': 'Control'},
    'eudr/geojson': {'lot': {'name': 'Lote control', 'vertices': LOT}},
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

bad = {k: v for k, v in codes.items() if v >= 500}
out(f"{len(codes) - len(bad)} de {len(codes)} sin error de servidor." + (f" Fallan: {', '.join(bad)}" if bad else ''))
if os.environ.get('GITHUB_ACTIONS'):
    # la tabla también queda como anotación, legible por la API de GitHub
    print('::notice title=Chequeo en vivo::' + '%0A'.join(l.replace('%', '%25') for l in LINES))
sys.exit(1 if bad else 0)
