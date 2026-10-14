"""Referencia de El Niño para ~80 localidades de Sudamérica (corre en GitHub Actions, gratis).

Para cada localidad baja la lluvia diaria ERA5 desde 1991 (Open-Meteo, sin clave) y calcula con enso_sa.reference_for:
lluvia normal de cada mes y lluvia de cada temporada según fase ENSO (ONI de NOAA PSL).
Open-Meteo gratis: 5.000 consultas por hora y 10.000 por día; cada serie de 35 años pesa ~90, así que el script
espera entre localidades y guarda lo bajado en scripts/cache/enso_sa/ para retomar si se corta.

Uso: python scripts/enso_sudamerica.py [salida.json]
"""
import gzip, json, os, sys, time
from datetime import date

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import enso_sa  # noqa: E402
import climate_indices as ci  # noqa: E402
import enso_chain as ec  # noqa: E402

CACHE = os.path.join(HERE, 'cache', 'enso_sa')
PAUSE = float(os.environ.get('ENSO_SA_PAUSE', '70'))


def fetch(pid, lat, lon, end):
    path = os.path.join(CACHE, f'{pid}-{end}.json.gz')
    if os.path.exists(path):
        with gzip.open(path, 'rt') as f:
            return json.load(f), True
    for i in range(6):
        r = requests.get('https://archive-api.open-meteo.com/v1/archive', timeout=120, params={
            'latitude': lat, 'longitude': lon, 'start_date': '1991-01-01', 'end_date': end,
            'daily': 'precipitation_sum', 'models': 'era5', 'timezone': 'UTC'})
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(90 * (i + 1)); continue
        r.raise_for_status()
        d = r.json().get('daily') or {}
        os.makedirs(CACHE, exist_ok=True)
        for old in os.listdir(CACHE):
            if old.startswith(pid + '-'):
                os.remove(os.path.join(CACHE, old))
        with gzip.open(path, 'wt') as f:
            json.dump(d, f)
        return d, False
    raise RuntimeError(f'Open-Meteo no respondió para {pid}')


def main(out):
    today = date.today()
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    import calendar
    end = f'{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}'
    oni = ci.parse_psl(requests.get(ci.PSL['oni'][1], timeout=60).text)
    phases = ec.season_phase(oni)
    try:
        with open(out, encoding='utf-8') as f:
            old = json.load(f)
    except (OSError, ValueError):
        old = {}
    places = old.get('places') or {}
    same_month = str(old.get('period', '')).endswith(end[:7])
    for pid, name, country, lat, lon in enso_sa.PLACES:
        if same_month and pid in places:      # ya calculada este mes: no gastar consultas
            continue
        try:
            d, cached = fetch(pid, lat, lon, end)
        except Exception as e:
            print(f'{name}: {e}', flush=True); continue
        mon = enso_sa.monthly_totals(d)
        places[pid] = enso_sa.reference_for(mon, phases)
        g = places[pid]['warm']['groups'].get('El Niño fuerte o muy fuerte') or {}
        print(f"{name}: oct-mar con Niño fuerte {g.get('vs_neutral_pct')} % ({'caché' if cached else 'bajado'})", flush=True)
        save(out, today, end, places)
        if not cached:
            time.sleep(PAUSE)
    save(out, today, end, places)
    print(f'{len(places)} localidades guardadas en {out}')


def save(out, today, end, places):
    res = {'built': today.isoformat(), 'period': f'1991-01 a {end[:7]}', 'source': 'Copernicus ERA5 vía Open-Meteo · ONI NOAA PSL',
           'places': places}
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join('data', 'enso_sudamerica.json'))
