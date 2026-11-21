"""Población que vive cerca del río en cada localidad ribereña de DOTS (Google Earth Engine).

Recorre todas las estaciones de cuenca.STATIONS y guarda, para cada una, la población a 1, 2, 3, 5 y 10 m
sobre el curso de agua (MERIT Hydro HAND + WorldPop 2020, 15 km) y los escenarios a nivel de alerta y evacuación.
Es exposición estimada por relieve, no personas inundadas ni evacuadas.

Uso: python scripts/poblacion_expuesta.py data/poblacion_expuesta.json [id1,id2,...]
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cuenca as cc  # noqa: E402
from poblacion import crecida  # noqa: E402


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else 'data/poblacion_expuesta.json'
    only = set(filter(None, (sys.argv[2] if len(sys.argv) > 2 else '').split(',')))
    prev = {}
    if os.path.exists(out_path):
        try:
            prev = {p['id']: p for p in json.load(open(out_path)).get('places', [])}
        except (ValueError, KeyError):
            prev = {}
    places, fails = dict(prev), []
    for st in cc.STATIONS:
        sid = st['id']
        if only and sid not in only:
            continue
        try:
            env = crecida.at_station(sid)
        except Exception as exc:  # una localidad que falla no corta las demás
            fails.append(f'{sid}: {exc}'[:200])
            continue
        data = (env or {}).get('data')
        if not data:
            fails.append(f"{sid}: {(env or {}).get('error') or (env or {}).get('status') or 'sin dato'}"[:200])
            continue
        data.pop('method', None)
        places[sid] = data
        print(f"{st['place']}: {data.get('total')} personas en 15 km", flush=True)
        time.sleep(1)
    doc = {
        'updated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
        'source': 'MERIT Hydro HAND v1.0.1 (90 m) y WorldPop 2020 (100 m) vía Google Earth Engine',
        'nota': 'Exposición estimada por altura sobre el río en 15 km a la redonda. No es mancha de inundación ni conteo de evacuados.',
        'places': list(places.values()),
        'fallas': fails,
    }
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    json.dump(doc, open(out_path, 'w'), ensure_ascii=False, indent=1)
    print(f'{len(places)} localidades, {len(fails)} fallas', flush=True)
    if not places:
        sys.exit(1)


if __name__ == '__main__':
    main()
