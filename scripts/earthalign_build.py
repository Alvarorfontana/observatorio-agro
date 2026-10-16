"""Banco de descripciones del estado atmosférico (EarthAlign · MBZUAI/ADIA Lab/UC San Diego)

Corre en GitHub Actions (gratis) y guarda data/earthalign.json en la rama `datos`; la web sólo lee ese archivo.

Qué hace: baja los registros del DATASET liberado (record_json) y guarda, para cada muestra, su posición, su fecha,
sus categorías de evento y sus cuatro descripciones (captions). Nada de texto propio: son las descripciones ya
alineadas del dataset. La web elige la muestra más cercana al lote por distancia (y la fecha desempata).

Esta es la fase verificable, sin placa ni modelo. La fase siguiente (que sí necesita PyTorch) es correr MeteoLIP
sobre el recorte ERA5 de cada lote para describir cualquier punto y fecha; queda documentada en
DOTS-v2.7-EARTHALIGN.md y en el PENDING de earthalign.py.

Uso: python scripts/earthalign_build.py [salida.json]
"""
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import earthalign  # noqa: E402

BASE = 'https://huggingface.co/datasets/MBZUAI/EarthAlign/resolve/main/EarthAlign/data/record_json'
SOURCES = ['negsamp', 'emdat']        # clima normal (más útil para el campo) + catástrofe declarada
# Sur de Sudamérica: el área de trabajo de DOTS (litoral, pampa, patagonia norte).
REGION = (-76.0, -55.0, -44.0, -20.0)  # (min_lon, min_lat, max_lon, max_lat)
LIMIT = 6000
UA = 'DOTS-Campo/1.7 (observatorio agroambiental; descripciones EarthAlign)'


def _captions(v):
    """Normaliza el campo CAPTIONS del dataset a {estilo: texto}."""
    if isinstance(v, dict):
        return {str(k): str(t) for k, t in v.items() if t}
    out = {}
    if isinstance(v, list):
        for i, item in enumerate(v):
            if isinstance(item, dict):
                style = item.get('style') or item.get('name') or item.get('type')
                text = item.get('caption') or item.get('text') or item.get('value')
                if text:
                    out[str(style or (earthalign.CAPTION_STYLES[i] if i < len(earthalign.CAPTION_STYLES) else i))] = str(text)
            elif isinstance(item, str) and item:
                out[earthalign.CAPTION_STYLES[i] if i < len(earthalign.CAPTION_STYLES) else str(i)] = item
    return out


def bbox_center(bb):
    """Centro (lat, lon) de un bbox del dataset: [W, S, E, N] o [min_lon, min_lat, max_lon, max_lat]."""
    try:
        w, s, e, n = (float(x) for x in bb[:4])
    except (TypeError, ValueError, IndexError):
        return None
    return (round((s + n) / 2, 2), round((w + e) / 2, 2))


def extract(records, region=REGION, limit=LIMIT):
    """De los registros crudos a las muestras del banco (dentro de region, con posición y fecha)."""
    min_lon, min_lat, max_lon, max_lat = region
    out = []
    for r in records or []:
        if not isinstance(r, dict):
            continue
        c = bbox_center(r.get('ERA5_SNAPSHOT_BBOX'))
        if not c:
            continue
        lat, lon = c
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            continue
        caps = _captions(r.get('CAPTIONS'))
        if not caps:
            continue
        cats = r.get('EVENT_CATEGORIES')
        if isinstance(cats, str):
            cats = [cats]
        out.append({'lat': lat, 'lon': lon, 'time': str(r.get('ERA5_SNAPSHOT_TIME') or '')[:10],
                    'event': ', '.join(str(x) for x in (cats or [])) or None,
                    'classification': cats or None, 'captions': caps})
        if len(out) >= limit:
            break
    return out


def fetch(name, session):
    r = session.get(f'{BASE}/data_{name}.json', timeout=180)
    r.raise_for_status()
    return r.json()


def main(out, sources=SOURCES):
    session = requests.Session()
    session.headers.update({'User-Agent': UA})
    samples = []
    for name in sources:
        try:
            records = fetch(name, session)
        except Exception as e:
            print(f'{name}: no se pudo bajar ({e})', flush=True)
            continue
        got = extract(records, limit=LIMIT - len(samples))
        print(f'{name}: {len(got)} muestras en la región (de {len(records)})', flush=True)
        samples.extend(got)
        if len(samples) >= LIMIT:
            break
    res = {'generated_at': _now(), 'source': earthalign.CODE, 'dataset': earthalign.DATASET,
           'region': list(REGION), 'caption_styles': earthalign.CAPTION_STYLES, 'samples': samples}
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(samples)} muestras guardadas en {out}')


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join('data', 'earthalign.json'))
