"""temporales — avisos meteorológicos dentro del sistema de alertas de la Cuenca del Plata.

  · Para cada una de las 34 localidades: caídas de presión (3 h y 24 h), frentes fríos (caída de la máxima de un día
    al otro), ráfagas y calor extremo sostenido, sobre el pronóstico horario de Open-Meteo (ECMWF, GFS y otros).
  · Sudestada en el Río de la Plata: viento persistente del este al sur en el centro del estuario, que sube el agua en la
    costa y frena la bajada del Paraná y el Uruguay. Agrava el nivel de las localidades del Delta y el Uruguay inferior.
Reglas declaradas, las mismas que usa el sitio (src/site/frentes.ts). Orientativo: los avisos oficiales son del SMN y
la altura del agua en el estuario la pronostica el Servicio de Hidrografía Naval.
"""
import time
from datetime import datetime, timedelta, timezone

import research_connectors as c

URL = 'https://api.open-meteo.com/v1/forecast'
HOURLY = 'pressure_msl,temperature_2m,wind_speed_10m,wind_gusts_10m,wind_direction_10m,precipitation'
DAILY = 'temperature_2m_max,temperature_2m_min,wind_gusts_10m_max,precipitation_sum'
UMB = {'caida3h': (3, 5), 'caida24h': 14, 'frente': (8, 12), 'rafaga': (60, 80), 'calor': {'tmax': 35, 'tmin': 22, 'dias': 3}}
SUDESTADA = {'punto': (-34.85, -57.4), 'dir': (80, 190), 'viento': (30, 45), 'horas': 12, 'rafaga': 70}
ESTUARIO = ('parana-zarate', 'parana-sanpedro', 'uruguay-fraybentos', 'uruguay-cdeluruguay')   # donde pega la sudestada
ORD = ['Normal', 'Atención', 'Alerta']
TTL = 3 * 3600
_CACHE = {}


def _now_ar():
    return (datetime.now(timezone.utc) - timedelta(hours=3)).strftime('%Y-%m-%dT%H')


def dm(iso):
    return f'{iso[8:10]}/{iso[5:7]}'


def hm(iso):
    return f'{dm(iso)} {iso[11:16]}'


def _f(v, d=1):
    return f'{v:.{d}f}'.replace('.', ',')


def peor(a, b):
    return a if ORD.index(a) >= ORD.index(b) else b


def frentes(d, hoy=None):
    hoy = hoy or _now_ar()
    h, dd = d['hourly'], d['daily']
    t, P = h['time'], h['pressure_msl']
    k0 = next((i for i, x in enumerate(t) if x[:13] >= hoy), 0)
    ev = []
    c3, i3, c24, i24 = 0.0, -1, 0.0, -1
    for i in range(max(3, k0), len(t)):
        if P[i] is not None and P[i - 3] is not None and P[i - 3] - P[i] > c3:
            c3, i3 = P[i - 3] - P[i], i
        if i >= 24 and P[i] is not None and P[i - 24] is not None and P[i - 24] - P[i] > c24:
            c24, i24 = P[i - 24] - P[i], i
    fut = [(p, i) for i, p in enumerate(P) if i >= k0 and p is not None]
    pmin, imin = min(fut) if fut else (None, -1)
    if c24 >= UMB['caida24h']:
        ev.append({'nivel': 'Alerta', 'tipo': 'Ciclogénesis', 'cuando': hm(t[i24]),
                   'texto': f'La presión cae {_f(c24)} hPa en 24 h: posible ciclón extratropical intenso, con temporal de viento y lluvia.'})
    if c3 >= UMB['caida3h'][0]:
        ev.append({'nivel': 'Alerta' if c3 >= UMB['caida3h'][1] else 'Atención', 'tipo': 'Caída de presión', 'cuando': hm(t[i3]),
                   'texto': f'Baja {_f(c3)} hPa en 3 horas: se acerca un frente o una baja; ráfagas y tormentas probables.'})
    dt, tx, tn, gx = dd['time'], dd['temperature_2m_max'], dd['temperature_2m_min'], dd['wind_gusts_10m_max']
    kd = max(1, next((i for i, x in enumerate(dt) if x >= hoy[:10]), 1))
    fr, ifr = 0.0, -1
    for i in range(kd, len(dt)):
        if tx[i - 1] is not None and tx[i] is not None and tx[i - 1] - tx[i] > fr:
            fr, ifr = tx[i - 1] - tx[i], i
    if fr >= UMB['frente'][0]:
        ev.append({'nivel': 'Alerta' if fr >= UMB['frente'][1] else 'Atención', 'tipo': 'Frente frío', 'cuando': dm(dt[ifr]),
                   'texto': f'La máxima baja {round(fr)} °C de un día al otro (de {round(tx[ifr - 1])} a {round(tx[ifr])} °C): cambio brusco de tiempo.'})
    gs = [(g, i) for i, g in enumerate(gx) if i >= kd - 1 and g is not None]
    gmax, ig = max(gs) if gs else (0, -1)
    if gmax >= UMB['rafaga'][0]:
        ev.append({'nivel': 'Alerta' if gmax >= UMB['rafaga'][1] else 'Atención', 'tipo': 'Ráfagas', 'cuando': dm(dt[ig]),
                   'texto': f'Ráfagas de hasta {round(gmax)} km/h.'})
    run, ini, calor = 0, -1, None
    for i in range(kd - 1, len(dt)):
        if tx[i] is not None and tn[i] is not None and tx[i] >= UMB['calor']['tmax'] and tn[i] >= UMB['calor']['tmin']:
            if not run:
                ini = i
            run += 1
            if run >= UMB['calor']['dias']:
                calor = (ini, i)
        else:
            run = 0
    if calor:
        ev.append({'nivel': 'Alerta', 'tipo': 'Calor extremo', 'cuando': f'{dm(dt[calor[0]])} al {dm(dt[calor[1]])}',
                   'texto': f"{calor[1] - calor[0] + 1} días seguidos con máximas de {UMB['calor']['tmax']} °C o más y mínimas de {UMB['calor']['tmin']} °C o más."})
    nivel = 'Normal'
    for e in ev:
        nivel = peor(nivel, e['nivel'])
    return {'nivel': nivel, 'eventos': ev, 'pmin': pmin, 'pmin_cuando': hm(t[imin]) if imin >= 0 else '',
            'caida3h': round(c3, 1), 'caida24h': round(c24, 1), 'frente': round(fr, 1), 'rafaga': gmax}


def sudestada(d, hoy=None):
    hoy = hoy or _now_ar()
    h = d['hourly']
    t, v, g, r = h['time'], h['wind_speed_10m'], h['wind_direction_10m'], h.get('wind_gusts_10m') or []
    k0 = next((i for i, x in enumerate(t) if x[:13] >= hoy), 0)
    lo, hi = SUDESTADA['dir']

    def dentro(i, lim):
        return g[i] is not None and v[i] is not None and lo <= g[i] <= hi and v[i] >= lim

    def racha(lim):
        best, n, ini = (0, -1, -1), 0, -1
        for i in range(k0, len(t)):
            if dentro(i, lim):
                if not n:
                    ini = i
                n += 1
                if n > best[0]:
                    best = (n, ini, i)
            else:
                n = 0
        return best

    fuerte, mod = racha(SUDESTADA['viento'][1]), racha(SUDESTADA['viento'][0])
    n, i0, i1 = fuerte if fuerte[0] >= SUDESTADA['horas'] else mod
    gmax = max([x for x in r[i0:i1 + 1] if x is not None] or [0]) if n else 0
    vmax = max(v[i0:i1 + 1]) if n else 0
    if fuerte[0] >= SUDESTADA['horas'] or (mod[0] >= SUDESTADA['horas'] and gmax >= SUDESTADA['rafaga']):
        nivel = 'Alerta'
    elif mod[0] >= SUDESTADA['horas']:
        nivel = 'Atención'
    else:
        nivel = 'Normal'
    if nivel == 'Normal':
        texto = 'Sin viento persistente del sudeste sobre el Río de la Plata en los próximos días.'
    else:
        rumbo = ['este', 'sudeste', 'sur'][min(2, max(0, round((g[i0] - 90) / 45)))]
        texto = (f"Viento del {rumbo} durante {n} horas seguidas, con máximas de {round(vmax)} km/h"
                 f"{f' y ráfagas de {round(gmax)} km/h' if gmax else ''}: el agua puede subir en la costa del Delta, San Fernando, "
                 'Buenos Aires y Quilmes, y frenar la bajada del Paraná y el Uruguay.')
    return {'nivel': nivel, 'texto': texto, 'horas': n, 'desde': hm(t[i0]) if n else '', 'hasta': hm(t[i1]) if n else '',
            'vmax': vmax, 'gmax': gmax}


def temporales(stations):
    """Una sola consulta a Open-Meteo para todas las localidades más el centro del estuario. Se guarda 3 horas."""
    hit = _CACHE.get('t')
    if hit and time.monotonic() - hit[0] < TTL:
        return hit[1]
    st = [s for s in stations if s.get('lat') is not None]
    lats = [s['lat'] for s in st] + [SUDESTADA['punto'][0]]
    lons = [s['lon'] for s in st] + [SUDESTADA['punto'][1]]
    r = c.SESSION.get(URL, params={'latitude': ','.join(map(str, lats)), 'longitude': ','.join(map(str, lons)), 'past_days': 1,
                                   'forecast_days': 5, 'timezone': 'America/Argentina/Buenos_Aires', 'hourly': HOURLY, 'daily': DAILY}, timeout=40)
    r.raise_for_status()
    arr = r.json()
    arr = arr if isinstance(arr, list) else [arr]
    out = {'stations': {}, 'sudestada': None, 'errors': {}}
    for s, d in zip(st, arr):
        try:
            out['stations'][s['id']] = {'id': s['id'], 'place': s['place'], 'river': s['river'], **frentes(d)}
        except Exception as e:
            out['errors'][s['id']] = type(e).__name__
    try:
        out['sudestada'] = sudestada(arr[len(st)])
    except Exception as e:
        out['errors']['sudestada'] = type(e).__name__
    sd = out['sudestada'] or {}
    if sd.get('nivel') in ('Atención', 'Alerta'):   # la sudestada se suma a las localidades del estuario
        for sid in ESTUARIO:
            w = out['stations'].get(sid)
            if w:
                w['eventos'].append({'nivel': sd['nivel'], 'tipo': 'Sudestada', 'cuando': f"{sd['desde']} a {sd['hasta']}", 'texto': sd['texto']})
                w['nivel'] = peor(w['nivel'], sd['nivel'])
    lv = [w['nivel'] for w in out['stations'].values()]
    out['counts'] = {k: lv.count(k) for k in ORD}
    out['umbrales'] = {**UMB, 'sudestada': SUDESTADA}
    _CACHE['t'] = (time.monotonic(), out)
    return out
