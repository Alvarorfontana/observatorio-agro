"""Historia mensual de focos de calor por provincia (sur de Sudamérica) y por departamento (Argentina), desde 2001.

Corre en GitHub Actions (la web sólo lee data/focos_historia.json). Usa NASA FIRMS MODIS (1 km, Terra y Aqua), la serie
más larga y homogénea: la versión científica (SP) donde existe y la casi en tiempo real (NRT) para los últimos meses.
Cada foco se asigna a su provincia o estado (Natural Earth, data/provincias_sur.json) y, en Argentina, a su
departamento (geoBoundaries, CC BY 4.0). Retoma lo que falte si se corta. Requiere el secreto FIRMS_MAP_KEY.
Uso: python scripts/focos_historia.py [salida.json]
"""
import json
import os
import sys
import time
from datetime import date, timedelta

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import focos  # noqa: E402

PAUSE = float(os.environ.get('FOCOS_PAUSE', '1.5'))
GB_API = 'https://www.geoboundaries.org/api/current/gbOpen/ARG/ADM2/'
START = date(2001, 1, 1)


def departments():
    """[(nombre, provincia, polígonos, caja)] de Argentina; vacío si geoBoundaries no responde."""
    try:
        meta = requests.get(GB_API, timeout=60).json()
        gj = requests.get(meta['simplifiedGeometryGeoJSON'], timeout=180).json()
    except Exception as e:
        print(f'geoBoundaries no respondió ({type(e).__name__}): sin departamentos', flush=True)
        return []
    out = []
    for f in gj.get('features') or []:
        g = f.get('geometry') or {}
        polys = [g['coordinates']] if g.get('type') == 'Polygon' else g.get('coordinates') or []
        if not polys:
            continue
        xs = [x for p in polys for x, _ in p[0]]; ys = [y for p in polys for _, y in p[0]]
        out.append(((f.get('properties') or {}).get('shapeName'), polys, (min(xs), min(ys), max(xs), max(ys))))
    print(f'{len(out)} departamentos de Argentina', flush=True)
    return out


def dept_of(lat, lon, deps):
    for name, polys, (w, s, e, n) in deps:
        if w <= lon <= e and s <= lat <= n:
            for poly in polys:
                if focos._in_ring(lon, lat, poly[0]):
                    return name
    return None


def fetch(key, source, day):
    bbox = ','.join(str(v) for v in focos.BBOX)
    url = f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/10/{day.isoformat()}'
    for i in range(5):
        try:
            r = requests.get(url, timeout=120)
        except requests.RequestException:
            time.sleep(30); continue
        if r.status_code == 429 or r.status_code >= 500 or 'Exceeding allowed transaction limit' in r.text[:200]:
            time.sleep(120 * (i + 1)); continue
        if r.ok and r.text.startswith('latitude'):
            return focos.parse_csv(r.text, source)
        return None
    return None


def main(out):
    key = os.environ.get('FIRMS_MAP_KEY')
    if not key:
        sys.exit('Falta el secreto FIRMS_MAP_KEY en GitHub (Settings → Secrets → Actions).')
    cache = os.path.join(HERE, 'cache', 'focos_bloques.json')
    try:
        res = json.load(open(cache, encoding='utf-8'))
    except (OSError, ValueError):
        res = {}
    done = set(res.get('done_blocks') or [])
    deps = departments()
    today = date.today()
    recent = today - timedelta(days=120)           # los últimos meses se rehacen con NRT hasta que haya SP
    day = START
    calls = 0
    while day <= today:
        tag = day.isoformat()
        sp = day < recent
        if sp and tag in done:
            day += timedelta(days=10); continue
        rows = fetch(key, 'MODIS_SP' if sp else 'MODIS_NRT', day)
        if rows is None and sp:
            rows = fetch(key, 'MODIS_NRT', day)
        calls += 1
        if rows is not None:
            # se descuentan los conteos previos de este bloque (si se rehace) guardando por bloque
            blk = res.setdefault('blocks', {})
            counts = {}
            for r in rows:
                d = date.fromisoformat(r['date'])
                if not (day <= d < day + timedelta(days=10)):
                    continue
                cty, prov = focos.locate(r['lat'], r['lon'])
                if not cty:
                    continue
                m = r['date'][:7]
                c = counts.setdefault(m, {'prov': {}, 'dep': {}})
                kp = f'{cty}|{prov}'
                c['prov'][kp] = c['prov'].get(kp, 0) + 1
                if cty == 'Argentina' and deps:
                    dn = dept_of(r['lat'], r['lon'], deps)
                    if dn:
                        kd = f'{prov}|{dn}'
                        c['dep'][kd] = c['dep'].get(kd, 0) + 1
            blk[tag] = counts
            if sp:
                done.add(tag)
        if calls % 20 == 0 or day + timedelta(days=10) > today:
            # reconstruye los totales mensuales desde los bloques
            months = {}
            for counts in (res.get('blocks') or {}).values():
                for m, c in counts.items():
                    mm = months.setdefault(m, {'prov': {}, 'dep': {}})
                    for kind in ('prov', 'dep'):
                        for k, v in c[kind].items():
                            mm[kind][k] = mm[kind].get(k, 0) + v
            res['done_blocks'] = sorted(done)
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            json.dump(res, open(cache, 'w', encoding='utf-8'), separators=(',', ':'))
            json.dump({'months': dict(sorted(months.items())), 'updated': today.isoformat(),
                       'source': 'NASA FIRMS MODIS (SP y NRT), 1 km · Natural Earth · geoBoundaries',
                       'method': __doc__.split('\n\n')[1].strip()},
                      open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            print(f'{tag}: {len(months)} meses', flush=True)
        day += timedelta(days=10)
        time.sleep(PAUSE)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join('data', 'focos_historia.json'))
