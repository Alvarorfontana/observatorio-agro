"""Heladas de la última noche por satélite GOES-19: temperatura mínima de la superficie (ABI LSTF, cada hora, cielo despejado).

Corre en GitHub Actions todas las mañanas. Toma los archivos de 04 a 10 UTC (1 a 7 de la mañana en Argentina), lee la
temperatura de la superficie en cada localidad del monitor y en una grilla de 0,5° del sur de Sudamérica, y guarda la
mínima de la noche en data/goes_heladas.json (rama datos). Donde hubo nubes toda la noche, no hay dato.
Uso: python scripts/goes_heladas.py [salida.json]
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import enso_sa  # noqa: E402
import focos  # noqa: E402
import goes  # noqa: E402

HOURS = range(4, 11)


def keys(day, hour):
    prefix = f"ABI-L2-LSTF/{day:%Y}/{day.timetuple().tm_yday:03d}/{hour:02d}/"
    r = requests.get(goes.BUCKET, params={'list-type': '2', 'prefix': prefix}, timeout=60)
    return re.findall(r'<Key>([^<]+)</Key>', r.text)


def sampler(nc):
    import numpy as np
    proj = nc.variables['goes_imager_projection']
    a, b = float(proj.semi_major_axis), float(proj.semi_minor_axis)
    H = float(proj.perspective_point_height) + a
    lon0 = float(proj.longitude_of_projection_origin)
    x = nc.variables['x'][:]; y = nc.variables['y'][:]
    lst = nc.variables['LST'][:]
    x0, dx, y0, dy = float(x[0]), float(x[1] - x[0]), float(y[0]), float(y[1] - y[0])

    def at(lat, lon):
        xy = goes.latlon_to_xy(lat, lon, lon0, H, a, b)
        if xy is None:
            return None
        i, j = goes.index_of(xy[1], y0, dy, len(y)), goes.index_of(xy[0], x0, dx, len(x))
        if i is None or j is None:
            return None
        v = lst[i, j]
        return None if np.ma.is_masked(v) or not np.isfinite(v) else float(v) - 273.15
    return at


def main(out):
    from netCDF4 import Dataset
    now = datetime.now(timezone.utc)
    day = now.date() if now.hour >= 11 else now.date() - timedelta(days=1)
    places = [p for p in enso_sa.PLACES if focos.BBOX[0] <= p[4] <= focos.BBOX[2] and focos.BBOX[1] <= p[3] <= focos.BBOX[3]]
    cells = goes.grid_cells(focos.BBOX, 0.5)
    pmin = {p[0]: (None, None) for p in places}
    gmin = {c: None for c in cells}
    used = []
    for h in HOURS:
        ks = keys(day, h)
        if not ks:
            continue
        r = requests.get(f'{goes.BUCKET}/{ks[0]}', timeout=120)
        if not r.ok:
            continue
        nc = Dataset('lst.nc', memory=r.content)
        at = sampler(nc)
        used.append(h)
        for p in places:
            v = at(p[3], p[4])
            if v is not None and (pmin[p[0]][0] is None or v < pmin[p[0]][0]):
                pmin[p[0]] = (round(v, 1), h)
        for c in cells:
            v = at(*c)
            if v is not None and (gmin[c] is None or v < gmin[c]):
                gmin[c] = round(v, 1)
        nc.close()
    rows = [{'id': p[0], 'name': p[1], 'country': p[2], 'lat': p[3], 'lon': p[4], 'lst_min_c': pmin[p[0]][0],
             'hour_utc': pmin[p[0]][1]} for p in places]
    grid = [[c[0], c[1], v] for c, v in gmin.items() if v is not None and focos.locate(*c)[0]]
    res = {'night': day.isoformat(), 'hours_utc': used, 'places': rows, 'grid': grid, 'grid_step': 0.5,
           'frost_places': [r['name'] for r in rows if r['lst_min_c'] is not None and r['lst_min_c'] <= 0],
           'frost_cells': sum(1 for g in grid if g[2] <= 0), 'cells': len(grid),
           'source': 'NOAA GOES-19 ABI, temperatura de la superficie terrestre (LSTF), datos abiertos en AWS',
           'method': __doc__.split('\n\n')[1].split('Uso:')[0].strip()}
    json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f"{day}: horas {used}, {len(grid)} celdas con dato, {res['frost_cells']} con helada; localidades con helada: {res['frost_places']}")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join('data', 'goes_heladas.json'))
