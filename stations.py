"""stations v1.0 — estaciones meteorológicas de Brasil, Chile y Canadá.

Orden de fuentes por país (la primera que responde con datos):
  * Canadá  · ECCC MSC GeoMet, colección swob-realtime (OGC API, abierta, sin registro).
  * Chile   · DMC, servicio getDatosRecientesRedEma (requiere DMC_USUARIO = correo y DMC_TOKEN, registro gratuito
              en climatologia.meteochile.gob.cl). Sin clave → METAR.
  * Brasil  · INMET apitempo (requiere INMET_TOKEN, se solicita a INMET). Sin clave → METAR.
  * Respaldo· METAR de aeropuertos vía NOAA Aviation Weather Center: partes horarios oficiales de cada país,
              tiempo real, abierto, sin registro. (NOAA ISD se descartó: su lista de estaciones dejó de
              actualizarse en agosto de 2025 durante la migración de NCEI.)

Nunca se sustituye un país por otro: si el lote está fuera del país, se dice.
"""
import math, os
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


# ───────────────────────── METAR · NOAA Aviation Weather Center (respaldo sin registro) ─────────────────────────
# Partes horarios de aeropuertos que elabora el servicio meteorológico de cada país (en Brasil, el DECEA/REDEMET;
# en Chile, la DMC) y que se publican por la red de la OMM. Tiempo real, abierto, sin clave.
AWC = 'https://aviationweather.gov/api/data/metar'
SUFFIX = {'inmet': ', BR', 'dmc': ', CL', 'eccc': ', CA'}


def metar(key, lat, lon, n=3):
    name = COUNTRY[key][0]
    dlat = MAX_KM / 111.0
    dlon = MAX_KM / (111.0 * max(0.2, math.cos(math.radians(lat))))
    js = []
    for hours in (3, 8):   # el servicio responde vacío (sin cuerpo) cuando no hay partes en la ventana
        r = c._get(AWC, {'bbox': f'{lat - dlat:.2f},{lon - dlon:.2f},{lat + dlat:.2f},{lon + dlon:.2f}',
                         'format': 'json', 'hours': hours}, timeout=25)
        try:
            js = r.json() if (getattr(r, 'content', b'x') or b'').strip() else []
        except ValueError:
            js = []
        if js:
            break
    latest = {}
    for m in js if isinstance(js, list) else []:
        if not str(m.get('name') or '').endswith(SUFFIX[key]):
            continue                      # sólo aeropuertos del país elegido
        sid = m.get('icaoId')
        if sid and (sid not in latest or (m.get('obsTime') or 0) > (latest[sid].get('obsTime') or 0)):
            latest[sid] = m
    near = sorted(((c._km(lat, lon, m['lat'], m['lon']), m) for m in latest.values() if m.get('lat') is not None),
                  key=lambda x: x[0])
    near = [x for x in near if x[0] <= MAX_KM][:n]
    obs = []
    for d, m in near:
        when = m.get('reportTime') or m.get('receiptTime')
        st = f"{str(m.get('name', '')).rsplit(',', 2)[0]} ({m.get('icaoId')})"
        t, dew = m.get('temp'), m.get('dewp')
        rh = None
        if isinstance(t, (int, float)) and isinstance(dew, (int, float)):
            rh = round(100 * math.exp(17.625 * dew / (243.04 + dew)) / math.exp(17.625 * t / (243.04 + t)))
        ws = m.get('wspd')
        for var, v, u in (('Temperatura', t, '°C'), ('Punto de rocío', dew, '°C'), ('Humedad (calculada)', rh, '%'),
                          ('Viento', round(ws * 1.852, 1) if isinstance(ws, (int, float)) else None, 'km/h'),
                          ('Presión (QNH)', m.get('altim'), 'hPa')):
            if isinstance(v, (int, float)):
                obs.append(c._obs(var, st, d, v, u, when))
        if m.get('wxString'):
            obs.append(c._obs('Tiempo presente', st, d, m['wxString'], 'código METAR', when))
    return c.envelope({'agency': AGENCY[key], 'via': 'METAR · NOAA Aviation Weather Center', 'observations': obs,
                       'stations': [{'name': m.get('name'), 'id': m.get('icaoId'), 'distance_km': round(d, 1)} for d, m in near],
                       'scope': (f'Partes horarios de aeropuertos de {name} (servicio meteorológico nacional, red OMM), '
                                 f'3 más cercanos a menos de {MAX_KM} km. Tiempo real.')},
                      AWC, 'observación aeronáutica (METAR)', 'NOAA AWC · ' + AGENCY[key],
                      'recibido' if obs else 'sin dato', None if obs else f'No hay aeropuertos de {name} con parte reciente a menos de {MAX_KM} km')


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


DMC_RESUMEN = 'https://climatologia.meteochile.gob.cl/application/servicios/getEmaResumenDiario'
DMC_VARS = (('temperatura', 'Temperatura', '°C'), ('humedadRelativa', 'Humedad', '%'),
            ('fuerzaDelVientoPromedio10Minutos', 'Viento', 'kt'), ('aguaCaida24Horas', 'Lluvia 24 h', 'mm'),
            ('presionNivelDelMar', 'Presión a nivel del mar', 'hPa'), ('radiacionGlobalInst', 'Radiación', 'W/m²'))


def dmc_stations(js):
    """Normaliza las dos respuestas de la DMC → [(estación, últimos valores)].
    getEmaResumenDiario: {'estaciones': {código: {'datosEstacion', 'datosResumenEma': {'datos': {'valoresMasRecientes'}}}}}
    getDatosRecientesRedEma: {'datosEstaciones': [{'estacion', 'datos': [...]}]}"""
    out = []
    est = js.get('estaciones')
    if isinstance(est, dict):
        for e in est.values():
            info = e.get('datosEstacion') or {}
            last = (((e.get('datosResumenEma') or {}).get('datos') or {}).get('valoresMasRecientes')) or {}
            if last.get('fueraDeServicio') or last.get('desactualizada'):
                continue
            out.append((info, last))
    for e in js.get('datosEstaciones') or (est if isinstance(est, list) else []) or []:
        info = e.get('estacion') or e
        datos = e.get('datos') or []
        last = next((d for d in reversed(datos) if d.get('temperatura') not in (None, '')), datos[-1] if datos else {})
        out.append((info, last))
    return out


def dmc(lat, lon):
    user, token = os.environ.get('DMC_USUARIO'), os.environ.get('DMC_TOKEN')
    if not (user and token):
        raise PermissionError('requiere credencial: DMC_USUARIO, DMC_TOKEN')
    js, url = {}, DMC_RESUMEN
    for url in (DMC_RESUMEN, DMC):
        try:
            js = c._get(url, {'usuario': user.strip(), 'token': token.strip()}, timeout=30).json()
        except ValueError:
            js = {}
        if dmc_stations(js):
            break
    near = []
    for info, last in dmc_stations(js):
        try:
            d = c._km(lat, lon, float(info['latitud']), float(info['longitud']))
        except (KeyError, TypeError, ValueError):
            continue
        near.append((d, info, last))
    near = [x for x in sorted(near, key=lambda x: x[0]) if x[0] <= MAX_KM]
    obs = []
    for d, info, row in near[:3]:
        for k, label, unit in DMC_VARS:
            v = row.get(k)
            try:
                v = float(str(v).split()[0]) if v not in (None, '') else None
            except ValueError:
                v = None
            if v is not None:
                obs.append(c._obs(label, info.get('nombreEstacion'), d, v, unit, row.get('momento')))
    err = None
    if not obs:
        err = (f"La DMC respondió: {str(js.get('status') or js.get('mensaje') or js.get('error') or 'sin estaciones')[:160]}"
               if not dmc_stations(js) else 'Sin datos recientes cerca')
    return c.envelope({'agency': AGENCY['dmc'], 'observations': obs, 'scope': 'Red de estaciones automáticas (EMA) · 3 más cercanas'},
                      url, 'observación', 'DMC Chile', 'recibido' if obs else 'sin dato', err)


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
    """Fuente nativa del país; si falta la clave o no responde, partes METAR de aeropuertos del país.
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
    env = metar(key, lat, lon)
    env['data']['source_mode'] = 'respaldo METAR'
    env['data']['native_note'] = native_err
    return env
