"""Prepara las Cartas de Suelos 1:50.000 de Buenos Aires (INTA, CC BY 4.0) para consultarlas por campo.

Lee el shapefile de Zenodo (doi:10.5281/zenodo.7837681), simplifica los bordes a ~15 m, y guarda recuadros de 0,25°
(data/suelos_ba/<lat>_<lon>.json) y la tabla de unidades (data/suelos_ba/unidades.json). Corre en GitHub Actions.
Uso: python scripts/suelos_ba_tiles.py ruta/al/shapefile.shp salida/
"""
import json
import math
import os
import sys

import geopandas as gpd
from shapely.geometry import box, mapping

STEP = 0.25


def clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    v = str(v).strip()
    return v or None


def main(shp, out):
    g = gpd.read_file(shp).to_crs(4326)
    g['geometry'] = g.geometry.buffer(0).simplify(0.00015, preserve_topology=True)
    os.makedirs(out, exist_ok=True)
    units, key_of = {}, {}
    for _, r in g.iterrows():
        sym = clean(r.get('SIMBC')) or '—'
        comp = ', '.join(f"{clean(r.get(f'SERIE{i}'))} {int(r.get(f'PORC{i}') or 0)} %" for i in range(1, 7)
                         if clean(r.get(f'SERIE{i}')) and (r.get(f'PORC{i}') or 0) > 0)
        rec = {'s': sym, 'n': clean(r.get('Nombre_UC')), 'comp': comp or None, 'cap': clean(r.get('CAP_USO')),
               'tax': ' · '.join(t for t in (clean(r.get('taxo_ppal')), clean(r.get('taxo_2rio'))) if t) or None,
               'pai': clean(r.get('PAISAJE'))}
        k = json.dumps(rec, sort_keys=True, ensure_ascii=False)
        if k not in key_of:
            key_of[k] = len(units)
            units[str(key_of[k])] = rec
    g['uid'] = [key_of[json.dumps({'s': clean(r.get('SIMBC')) or '—', 'n': clean(r.get('Nombre_UC')),
                                    'comp': (', '.join(f"{clean(r.get(f'SERIE{i}'))} {int(r.get(f'PORC{i}') or 0)} %" for i in range(1, 7)
                                                       if clean(r.get(f'SERIE{i}')) and (r.get(f'PORC{i}') or 0) > 0) or None),
                                    'cap': clean(r.get('CAP_USO')),
                                    'tax': ' · '.join(t for t in (clean(r.get('taxo_ppal')), clean(r.get('taxo_2rio'))) if t) or None,
                                    'pai': clean(r.get('PAISAJE'))}, sort_keys=True, ensure_ascii=False)] for _, r in g.iterrows()]
    w, s, e, n = g.total_bounds
    tiles = 0
    y = math.floor(s / STEP) * STEP
    while y < n:
        x = math.floor(w / STEP) * STEP
        while x < e:
            cell = box(x, y, x + STEP, y + STEP)
            sub = g[g.intersects(cell)]
            feats = []
            for _, r in sub.iterrows():
                geom = r.geometry.intersection(cell)
                if geom.is_empty:
                    continue
                polys = [geom] if geom.geom_type == 'Polygon' else [p for p in getattr(geom, 'geoms', []) if p.geom_type == 'Polygon']
                for p in polys:
                    rings = [[[round(a, 5), round(b, 5)] for a, b in p.exterior.coords]] + \
                            [[[round(a, 5), round(b, 5)] for a, b in h.coords] for h in p.interiors]
                    bx = p.bounds
                    feats.append([int(r['uid']), [round(v, 5) for v in bx], rings])
            if feats:
                json.dump({'f': feats}, open(os.path.join(out, f'{y:.2f}_{x:.2f}.json'), 'w'), separators=(',', ':'))
                tiles += 1
            x += STEP
        y += STEP
    json.dump(units, open(os.path.join(out, 'unidades.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f'{len(g)} polígonos, {len(units)} unidades distintas, {tiles} recuadros')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
