"""stations v1.0 — estaciones meteorológicas de Brasil, Chile y Canadá.

Orden de fuentes por país (la primera que responde con datos):
  * Canadá  · ECCC MSC GeoMet, colección swob-realtime (OGC API, abierta, sin registro).
  * Chile   · DMC, servicio getDatosRecientesRedEma (requiere DMC_USUARIO = correo y DMC_TOKEN, registro gratuito
              en climatologia.meteochile.gob.cl). Sin clave → NOAA ISD.
  * Brasil  · INMET apitempo (requiere INMET_TOKEN, se solicita a INMET). Sin clave → NOAA ISD.
  * Respaldo· NOAA NCEI Global Hourly (ISD): observaciones SYNOP/METAR oficiales que los propios servicios
              nacionales transmiten por la red de la OMM. Abierto, sin registro, con 1-2 días de demora.

Nunca se sustituye un país por otro: si el lote está fuera del país, se dice.
"""
import csv, io, os, time
from datetime import timedelta

import research_connectors as c

COUNTRY_BOX = {   # (lat_min, lat_max, lon_min, lon_max) aproximados, para no consultar un país equivocado
    'inmet': (-34.0, 5.5, -74.5, -34.0),
    'dmc': (-56.5, -17.0, -76.0, -66.0),
    'eccc': (41.5, 83.5, -141.5, -52.0),
}
COUNTRY = {'inmet': ('Brasil', 'BR'), 'dmc': ('Chile', 'CI'), 'eccc': ('Canadá', 'CA')}
AGENCY = {'inmet': 'Instituto Nacional de Meteorologia (Brasil)', 'dmc': 'Dirección Meteorológica de Chile',
          'eccc': 'Environment and Climate Change Canada · MSC'}

ISD_HISTORY = 'https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv'
ISD_DATA = 'https://www.ncei.noaa.gov/access/services/data/v1'
_ISD = {'t': 0, 'rows': []}


MAX_KM = 300


def inside(key, lat, lon):
    """Descarta sólo lo que está lejos del país (recuadro ampliado ~3°); la distancia real a la estación decide después."""
    a, b, x, y = COUNTRY_BOX[key]
    return a - 3 <= lat <= b + 3 and x - 3 <= lon <= y + 3


def _outside(key):
    name = COUNTRY[key][0]
    return c.envelope({'agency': AGENCY[key], 'observations': [],
                       'scope': f'La ubicación está fuera de {name}; no se sustituye por datos de otro país.'},
                      '', 'observación', AGENCY[key])


# ───────────────────────── NOAA ISD (respaldo mundial sin registro) ─────────────────────────
def isd_stations(cc):
    """Estaciones ISD activas del país (lista oficial de NCEI, se guarda un día en memoria)."""
    if not _ISD['rows'] or time.monotonic() - _ISD['t'] > 86400:
        txt = c._get(ISD_HISTORY, timeout=40).text
        recent = (c._now() - timedelta(days=30)).strftime('%Y%m%d')
        rows = []
        for r in csv.DictReader(io.StringIO(txt)):
            try:
                if r['END'] < recent or not r['LAT'] or not r['LON']:
                    continue
                rows.append({'id': r['USAF'] + r['WBAN'], 'name': r['STATION NAME'].title(), 'cc': r['CTRY'],
                             'lat': float(r['LAT']), 'lon': float(r['LON']), 'elev': r['ELEV(M)']})
            except (KeyError, ValueError):
                continue
        _ISD.update(t=time.monotonic(), rows=rows)
    return [r for r in _ISD['rows'] if r['cc'] == cc]


def _isd_val(raw, scale=10, missing=('+9999', '9999', '99999', '+99999')):
    """Campos ISD tipo '+0251,1' → 25.1. Devuelve None si falta o la calidad es dudosa."""
    if not raw:
        return None
    parts = str(raw).split(',')
    v = parts[0]
    if v in missing or (len(parts) > 1 and parts[-1] in ('3', '7')):   # 3/7 = dato erróneo según ISD
        return None
    try:
        return round(int(v) / scale, 1)
    except ValueError:
        return None


def isd(key, lat, lon, n=3):
    name, cc = COUNTRY[key]
    st = isd_stations(cc)
    near = [x for x in sorted(((c._km(lat, lon, s['lat'], s['lon']), s) for s in st), key=lambda x: x[0])[:n] if x[0] <= MAX_KM]
    if not near:
        return c.envelope({'agency': AGENCY[key], 'observations': [], 'scope': f'Sin estaciones activas de {name} a menos de {MAX_KM} km'},
                          ISD_DATA, 'observación', 'NOAA NCEI', 'sin dato', f'No hay estaciones de {name} a menos de {MAX_KM} km del lote')
    end = c._now().date(); start = end - timedelta(days=4)
    r = c._get(ISD_DATA, {'dataset': 'global-hourly', 'stations': ','.join(s['id'] for _, s in near),
                          'startDate': start.isoformat(), 'endDate': end.isoformat(),
                          'dataTypes': 'TMP,DEW,SLP,WND', 'format': 'json', 'units': 'metric'}, timeout=40)
    data = r.json() if r.content else []
    obs, last = [], {}
    for row in data if isinstance(data, list) else []:
        sid = row.get('STATION')
        if sid and (sid not in last or row.get('DATE', '') > last[sid].get('DATE', '')):
            last[sid] = row
    for d, s in near:
        row = last.get(s['id'])
        if not row:
            continue
        when = row.get('DATE')
        t, dew, slp = _isd_val(row.get('TMP')), _isd_val(row.get('DEW')), _isd_val(row.get('SLP'))
        wnd = str(row.get('WND') or '').split(',')
        ws = None if len(wnd) < 4 or wnd[3] == '9999' else round(int(wnd[3]) / 10 * 3.6, 1)
        rh = None
        if t is not None and dew is not None:
            import math
            rh = round(100 * math.exp(17.625 * dew / (243.04 + dew)) / math.exp(17.625 * t / (243.04 + t)))
        for var, v, u in (('Temperatura', t, '°C'), ('Punto de rocío', dew, '°C'), ('Humedad (calculada)', rh, '%'),
                          ('Viento', ws, 'km/h'), ('Presión a nivel del mar', slp, 'hPa')):
            if v is not None:
                obs.append(c._obs(var, s['name'], d, v, u, when))
    return c.envelope({'agency': AGENCY[key], 'via': 'NOAA NCEI Global Hourly (ISD)', 'observations': obs,
                       'stations': [{'name': s['name'], 'id': s['id'], 'distance_km': round(d, 1)} for d, s in near],
                       'scope': (f'Observaciones oficiales de estaciones de {name} retransmitidas por la red de la OMM y '
                                 'archivadas por NOAA. Demora habitual de 1 a 2 días.')},
                      ISD_DATA, 'observación (respaldo mundial)', 'NOAA NCEI · ' + AGENCY[key],
                      'recibido' if obs else 'sin dato', None if obs else 'Las estaciones cercanas no publicaron datos recientes')


# ───────────────────────── Canadá · ECCC GeoMet (abierto) ─────────────────────────
ECCC = 'https://api.weather.gc.ca/collections/swob-realtime/items'
ECCC_VARS = (('air_temp', 'Temperatura', '°C'), ('rel_hum', 'Humedad', '%'), ('avg_wnd_spd_10m_pst10mts', 'Viento', 'km/h'),
             ('mslp', 'Presión a nivel del mar', 'hPa'), ('pcpn_amt_pst1hr', 'Lluvia última hora', 'mm'))


def eccc(lat, lon):
    since = (c._now() - timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
    js = c._get(ECCC, {'f': 'json', 'bbox': f'{lon - 0.8},{lat - 0.6},{lon + 0.8},{lat + 0.6}', 'limit': 300,
                       'datetime': f'{since}/..'}, timeout=30).json()
    by = {}
    for f in js.get('features') or []:
        p = f.get('properties') or {}
        g = (f.get('geometry') or {}).get('coordinates') or [None, None]
        name = p.get('stn_nam-value') or p.get('stn_nam') or 'Estación'
        when = p.get('date_tm-value') or p.get('obs_date_tm')
        if name not in by or (when or '') > (by[name][1] or ''):
            by[name] = (g, when, p)
    obs = []
    for name, (g, when, p) in sorted(by.items(), key=lambda kv: c._km(lat, lon, kv[1][0][1], kv[1][0][0]) if kv[1][0][0] is not None else 1e9)[:3]:
        d = c._km(lat, lon, g[1], g[0]) if g[0] is not None else 0
        for k, label, unit in ECCC_VARS:
            v = p.get(k) if p.get(k) is not None else p.get(f'{k}-value')
            if isinstance(v, (int, float)):
                obs.append(c._obs(label, name, d, round(v, 1), unit, when))
    return c.envelope({'agency': AGENCY['eccc'], 'observations': obs,
                       'scope': 'Observaciones en superficie en tiempo real (SWOB) de las 3 estaciones más cercanas'},
                      ECCC, 'observación', 'ECCC MSC GeoMet', 'recibido' if obs else 'sin dato',
                      None if obs else 'Sin estaciones con datos en las últimas 3 horas a menos de ~70 km')


# ───────────────────────── Chile · DMC (registro gratuito) ─────────────────────────
DMC = 'https://climatologia.meteochile.gob.cl/application/servicios/getDatosRecientesRedEma'


def dmc(lat, lon):
    user, token = os.environ.get('DMC_USUARIO'), os.environ.get('DMC_TOKEN')
    if not (user and token):
        raise PermissionError('requiere credencial: DMC_USUARIO, DMC_TOKEN')
    js = c._get(DMC, {'usuario': user, 'token': token}, timeout=30).json()
    near = []
    for e in js.get('datosEstaciones') or js.get('estaciones') or []:
        est = e.get('estacion') or e
        try:
            d = c._km(lat, lon, float(est['latitud']), float(est['longitud']))
        except (KeyError, TypeError, ValueError):
            continue
        near.append((d, est, e.get('datos') or []))
    near = [x for x in sorted(near, key=lambda x: x[0]) if x[0] <= MAX_KM]
    obs = []
    for d, est, datos in near[:3]:
        row = datos[-1] if datos else {}
        for k, label, unit in (('temperatura', 'Temperatura', '°C'), ('humedadRelativa', 'Humedad', '%'),
                               ('fuerzaDelVientoPromedio10Minutos', 'Viento', 'kt'), ('aguaCaida24Horas', 'Lluvia 24 h', 'mm'),
                               ('presionNivelDelMar', 'Presión a nivel del mar', 'hPa'), ('radiacionGlobalInst', 'Radiación', 'W/m²')):
            v = row.get(k)
            try:
                v = float(str(v).split()[0]) if v not in (None, '') else None
            except ValueError:
                v = None
            if v is not None:
                obs.append(c._obs(label, est.get('nombreEstacion'), d, v, unit, row.get('momento')))
    return c.envelope({'agency': AGENCY['dmc'], 'observations': obs, 'scope': 'Red de estaciones automáticas (EMA) · 3 más cercanas'},
                      DMC, 'observación', 'DMC Chile', 'recibido' if obs else 'sin dato', None if obs else 'Sin datos recientes cerca')


# ───────────────────────── Brasil · INMET (token a solicitar) ─────────────────────────
INMET = 'https://apitempo.inmet.gov.br'


def inmet(lat, lon):
    token = os.environ.get('INMET_TOKEN')
    if not token:
        raise PermissionError('requiere credencial: INMET_TOKEN')
    st = c._get(f'{INMET}/estacoes/T', timeout=30).json()
    near = sorted(((c._km(lat, lon, float(s['VL_LATITUDE']), float(s['VL_LONGITUDE'])), s) for s in st
                   if s.get('VL_LATITUDE') and s.get('CD_SITUACAO', 'Operante') == 'Operante'), key=lambda x: x[0])[:3]
    near = [x for x in near if x[0] <= MAX_KM]
    day = c._now().date()
    obs = []
    for d, s in near:
        rows = c._get(f"{INMET}/token/estacao/{day - timedelta(days=1)}/{day}/{s['CD_ESTACAO']}/{token}", timeout=30).json() or []
        row = next((r for r in reversed(rows) if r.get('TEM_INS') not in (None, '')), None)
        if not row:
            continue
        when = f"{row.get('DT_MEDICAO')}T{str(row.get('HR_MEDICAO', '0000'))[:2]}:00:00Z"
        for k, label, unit, f in (('TEM_INS', 'Temperatura', '°C', 1), ('UMD_INS', 'Humedad', '%', 1),
                                  ('VEN_VEL', 'Viento', 'km/h', 3.6), ('CHUVA', 'Lluvia última hora', 'mm', 1),
                                  ('PRE_INS', 'Presión', 'hPa', 1), ('RAD_GLO', 'Radiación', 'kJ/m²', 1)):
            try:
                v = round(float(row[k]) * f, 1)
            except (KeyError, TypeError, ValueError):
                continue
            obs.append(c._obs(label, s.get('DC_NOME', '').title(), d, v, unit, when))
    return c.envelope({'agency': AGENCY['inmet'], 'observations': obs, 'scope': 'Estaciones automáticas · 3 más cercanas'},
                      INMET, 'observación', 'INMET Brasil', 'recibido' if obs else 'sin dato', None if obs else 'Sin datos recientes cerca')


NATIVE = {'eccc': eccc, 'dmc': dmc, 'inmet': inmet}


def national(key, lat, lon):
    """Fuente nativa del país; si falta la clave o no responde, observaciones oficiales vía NOAA ISD.
    Sólo estaciones a menos de MAX_KM: cerca de una frontera se ven las del país vecino, con su distancia."""
    if not inside(key, lat, lon):
        return _outside(key)
    native_err = None
    try:
        env = NATIVE[key](lat, lon)
        if env['data'].get('observations'):
            env['data']['source_mode'] = 'nativa'
            return env
        native_err = env.get('error')
    except PermissionError as e:
        native_err = f'Fuente nativa sin clave cargada ({e})'
    except Exception as e:
        native_err = f'Fuente nativa sin respuesta ({type(e).__name__})'
    env = isd(key, lat, lon)
    env['data']['source_mode'] = 'respaldo NOAA'
    env['data']['native_note'] = native_err
    return env
