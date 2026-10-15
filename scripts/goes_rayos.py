"""Rayos de las últimas 3 horas por satélite GOES-19 (GLM), para el sur de Sudamérica.

Corre en GitHub Actions cada 30 minutos. Baja los archivos del GLM (uno cada 20 segundos) de los últimos 30 minutos,
se queda con los destellos dentro del recorte y los suma a los de las corridas anteriores, conservando 3 horas. Guarda
data/rayos.json en la rama `rayos` (un solo commit que se reemplaza, para no hacer crecer el repositorio).
Uso: python scripts/goes_rayos.py [salida.json]
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import enso_sa  # noqa: E402
import focos  # noqa: E402
import goes  # noqa: E402

WINDOW_MIN = 35
KEEP_H = 3


def keys(t):
    prefix = f"GLM-L2-LCFA/{t:%Y}/{t.timetuple().tm_yday:03d}/{t:%H}/"
    r = requests.get(goes.BUCKET, params={'list-type': '2', 'prefix': prefix}, timeout=60)
    return re.findall(r'<Key>([^<]+)</Key>', r.text)


def start_of(key):
    m = re.search(r'_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})', key)
    y, doy, hh, mm, ss = (int(g) for g in m.groups())
    return datetime(y, 1, 1, hh, mm, ss, tzinfo=timezone.utc) + timedelta(days=doy - 1)


def flashes(key):
    from netCDF4 import Dataset
    try:
        r = requests.get(f'{goes.BUCKET}/{key}', timeout=60)
        nc = Dataset('glm.nc', memory=r.content)
        lat = nc.variables['flash_lat'][:]; lon = nc.variables['flash_lon'][:]
        nc.close()
    except Exception:
        return []
    w, s, e, n = focos.BBOX
    t = start_of(key).strftime('%Y-%m-%dT%H:%M')
    return [[round(float(a), 3), round(float(o), 3), t] for a, o in zip(lat, lon) if s <= a <= n and w <= o <= e]


def main(out):
    now = datetime.now(timezone.utc)
    try:
        prev = json.load(open(out, encoding='utf-8'))
    except (OSError, ValueError):
        prev = {}
    last = prev.get('last_file_start')
    ks = []
    for h in sorted({(now - timedelta(minutes=m)).replace(minute=0, second=0, microsecond=0) for m in (0, WINDOW_MIN, 60)}):
        ks += keys(h)
    since = now - timedelta(minutes=WINDOW_MIN)
    ks = [k for k in ks if start_of(k) >= since and (not last or start_of(k).isoformat() > last)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        new = [f for fs in pool.map(flashes, ks) for f in fs]
    cut = (now - timedelta(hours=KEEP_H)).strftime('%Y-%m-%dT%H:%M')
    pts = [p for p in (prev.get('flashes') or []) if p[2] >= cut] + new
    one_h = (now - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
    places = []
    for p in enso_sa.PLACES:
        if not (focos.BBOX[0] <= p[4] <= focos.BBOX[2] and focos.BBOX[1] <= p[3] <= focos.BBOX[3]):
            continue
        near = [f for f in pts if abs(f[0] - p[3]) < 0.5 and abs(f[1] - p[4]) < 0.6 and goes.km((p[3], p[4]), (f[0], f[1])) <= 30]
        if near:
            places.append({'id': p[0], 'name': p[1], 'country': p[2], 'lat': p[3], 'lon': p[4], 'flashes_3h': len(near),
                           'flashes_1h': sum(1 for f in near if f[2] >= one_h), 'last': max(f[2] for f in near)})
    res = {'updated': now.strftime('%Y-%m-%dT%H:%M'), 'hours': KEEP_H, 'flashes': pts, 'count_3h': len(pts),
           'count_1h': sum(1 for f in pts if f[2] >= one_h), 'places': sorted(places, key=lambda x: -x['flashes_1h']),
           'last_file_start': max((start_of(k).isoformat() for k in ks), default=last),
           'source': 'NOAA GOES-19 GLM (Geostationary Lightning Mapper), datos abiertos en AWS',
           'method': __doc__.split('\n\n')[1].split('Uso:')[0].strip()}
    json.dump(res, open(out, 'w', encoding='utf-8'), separators=(',', ':'))
    print(f"{len(ks)} archivos nuevos, {len(new)} destellos nuevos, {len(pts)} en 3 horas, {len(places)} localidades con rayos a menos de 30 km")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join('data', 'rayos.json'))
