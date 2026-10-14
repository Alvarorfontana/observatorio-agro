"""Umbrales de ola de calor por localidad (corre en GitHub Actions; ver salud.py).

Percentil 90 de la máxima y de la mínima diaria de octubre a marzo, 2001-2020, ERA5 vía Open-Meteo, para las
80 localidades del monitor de Sudamérica. Retoma las que falten si se corta (Open-Meteo gratis limita por hora).
Uso: python scripts/calor_p90.py [salida.json]
"""
import json, os, sys, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import enso_sa  # noqa: E402

PAUSE = float(os.environ.get('CALOR_PAUSE', '80'))


def p90(vals):
    v = sorted(x for x in vals if x is not None)
    if len(v) < 300:
        return None
    k = 0.9 * (len(v) - 1); lo = int(k)
    return round(v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * (k - lo), 1)


def main(out):
    try:
        res = json.load(open(out, encoding='utf-8'))
    except (OSError, ValueError):
        res = {'places': {}}
    places = res.get('places') or {}
    for pid, name, country, lat, lon in enso_sa.PLACES:
        if pid in places:
            continue
        r = None
        for i in range(5):
            try:
                r = requests.get('https://archive-api.open-meteo.com/v1/archive', timeout=120, params={
                'latitude': lat, 'longitude': lon, 'start_date': '2001-01-01', 'end_date': '2020-12-31',
                'daily': 'temperature_2m_max,temperature_2m_min', 'models': 'era5', 'timezone': 'UTC'})
            except requests.RequestException:
                time.sleep(60); continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(120 * (i + 1)); continue
            break
        if r is None or not r.ok:
            print(f"{name}: sin respuesta ({getattr(r, 'status_code', 'error de red')})", flush=True); continue
        d = r.json().get('daily') or {}
        warm = [i for i, t in enumerate(d.get('time') or []) if int(t[5:7]) in (10, 11, 12, 1, 2, 3)]
        tx = p90([d['temperature_2m_max'][i] for i in warm]); tn = p90([d['temperature_2m_min'][i] for i in warm])
        if tx is not None and tn is not None:
            places[pid] = {'tx90': tx, 'tn90': tn}
            print(f'{name}: máx {tx} °C · mín {tn} °C', flush=True)
        res = {'period': '2001-2020, octubre a marzo', 'source': 'Copernicus ERA5 vía Open-Meteo', 'places': places}
        json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        time.sleep(PAUSE)
    print(f'{len(places)} localidades con umbral.')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join('data', 'calor_p90.json'))
