"""ina_a5 v1.0 — alturas y caudales observados del INA (API pública A5 / DSIyAH).

Dato **observado y oficial** de los ríos de la Cuenca del Plata: lo que hoy falta entre el
pronóstico (GloFAS / Open-Meteo) y la observación satelital (Copernicus GFM, Sentinel-1).
El Instituto Nacional del Agua publica sus redes hidrométricas (alturas_bdhi, etc.) en la API
A5, abierta y sin clave.

Endpoints (probados 2026-10):
  GET /obs/puntual/series?var_id=2&geom=minlon,minlat,maxlon,maxlat  → series de altura con metadatos y geometría
  GET /obs/puntual/series?var_id=4&geom=minlon,minlat,maxlon,maxlat  → series de caudal
  GET /obs/puntual/series/{id}?timestart=..&timeend=..               → observaciones de la serie
var_id: 2 = altura hidrométrica (m), 4 = caudal (m³/s).

Método (explícito, sin inventar nada): se buscan las series de altura y caudal cuya estación cae
dentro del recuadro del lote, se ordenan por cercanía al centro, se piden sus observaciones del
período y se informa la última lectura, mínimos, máximos y tendencia. Es una **estación del río**
cercana, no una descripción de la inundación del lote: para eso hacen falta relieve, umbrales y
la delimitación de la cuenca (que DOTS resuelve en otros módulos).
"""
from datetime import datetime, timedelta, timezone

import research_connectors as c
import vegetation as veg

BASE = 'https://alerta.ina.gob.ar/a5'
VAR_ALTURA = 2          # altura hidrométrica (m)
VAR_CAUDAL = 4          # caudal (m³/s)
MAX_STATIONS = 4        # estaciones más cercanas que se informan
MAX_POINTS = 120        # observaciones por estación (las últimas)
_ART = timezone(timedelta(hours=-3))


def _bbox(polygon):
    """Polígono [[lat,lon],...] → 'minlon,minlat,maxlon,maxlat' (el filtro geom de la API A5)."""
    minlon, minlat, maxlon, maxlat = c.polygon_bbox(polygon)
    return f'{minlon:.5f},{minlat:.5f},{maxlon:.5f},{maxlat:.5f}'


def _series_in_box(polygon, var_id):
    js = c._get(f'{BASE}/obs/puntual/series', {'var_id': var_id, 'geom': _bbox(polygon)}).json()
    return js.get('rows') or []


def _observaciones(series_id, start, end):
    js = c._get(f'{BASE}/obs/puntual/series/{series_id}',
                {'timestart': start.isoformat(), 'timeend': end.isoformat(), 'no_metadata': 'true'}).json()
    return js.get('observaciones') or []


def _score(row):
    """Prefiere la medición directa y, entre iguales, la serie con datos más recientes."""
    proc = ((row.get('procedimiento') or {}).get('abrev') or '') == 'medicion'
    dr = row.get('date_range') or {}
    return (1 if proc else 0, dr.get('timeend') or '', dr.get('count') or 0)


def _pick(rows):
    """Una serie por estación y variable: la de mejor puntaje (medición directa / más reciente)."""
    best = {}
    for r in rows:
        est = (r.get('estacion') or {}).get('id')
        var = (r.get('var') or {}).get('id')
        if est is None or var is None:
            continue
        key = (est, var)
        if key not in best or _score(r) > _score(best[key]):
            best[key] = r
    return list(best.values())


def _local(iso):
    """Timestamp UTC de la API ('...Z') → hora argentina, legible."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(_ART).strftime('%Y-%m-%d %H:%M')
    except ValueError:
        return iso


def _points(observations):
    out = []
    for o in observations:
        v = o.get('valor')
        if v is None:
            continue
        out.append({'datetime': _local(o.get('timestart')), 'valor': round(float(v), 2)})
    out.sort(key=lambda p: p['datetime'] or '')
    return out[-MAX_POINTS:]


def _summary(points, alert=None, evacuation=None):
    if not points:
        return {}
    vals = [p['valor'] for p in points]
    last = points[-1]
    trend = None
    if len(vals) >= 3:
        base = sum(vals[:-1]) / (len(vals) - 1)
        d = last['valor'] - base
        thr = 0.03 * (abs(base) or 1)
        trend = 'subiendo' if d > thr else 'bajando' if d < -thr else 'estable'
    state = None
    if evacuation is not None and last['valor'] >= evacuation:
        state = 'nivel de evacuación'
    elif alert is not None and last['valor'] >= alert:
        state = 'nivel de alerta'
    elif alert is not None and last['valor'] >= alert - 0.5:
        state = 'cerca del nivel de alerta'
    return {'last_value': last['valor'], 'last_time': last['datetime'],
            'min': min(vals), 'max': max(vals), 'trend': trend, 'level_state': state}


def _centroid(pts):
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def analyze(polygon, days=30):
    """Estaciones del INA dentro del recuadro del lote: última altura/caudal, rango y tendencia.

    `polygon`: [[lat,lon],...]. `days`: ventana de observaciones (3 a 365).
    Devuelve el envelope DOTS; si no hay estaciones o no tienen datos, responde 'sin dato'.
    """
    pts = veg.require_polygon(polygon)
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ValueError('Período inválido')
    if not 3 <= days <= 365:
        raise ValueError('El período debe estar entre 3 y 365 días')
    end = c._now()
    start = end - timedelta(days=days)
    lat0, lon0 = _centroid(pts)

    rows = _pick(_series_in_box(polygon, VAR_ALTURA) + _series_in_box(polygon, VAR_CAUDAL))
    if not rows:
        return c.envelope({'capability': 'OBSERVATION', 'period_days': days, 'stations': [],
                           'reference': None, 'series': []},
                          BASE + '/obs/puntual/series', 'alturas y caudales observados del INA',
                          'INA · DSIyAH (Argentina)', 'sin dato',
                          'No hay estaciones hidrométricas públicas del INA en el recuadro del lote')

    def distance(row):
        coord = ((row['estacion'].get('geom') or {}).get('coordinates')) or [lon0, lat0]
        return c._km(lat0, lon0, coord[1], coord[0])

    rows.sort(key=distance)
    stations = []
    for r in rows[:MAX_STATIONS]:
        est = r.get('estacion') or {}
        coord = (est.get('geom') or {}).get('coordinates') or [None, None]
        alert, evacuation = est.get('nivel_alerta'), est.get('nivel_evacuacion')
        s = {'series_id': r.get('id'), 'station': est.get('nombre'),
             'river': (est.get('rio') or '').title() or None, 'locality': est.get('localidad'),
             'lat': coord[1], 'lon': coord[0], 'distance_km': round(distance(r), 1),
             'variable': (r.get('var') or {}).get('nombre'), 'unit': (r.get('unidades') or {}).get('abrev'),
             'alert_level': alert, 'evacuation_level': evacuation}
        try:
            points = _points(_observaciones(r.get('id'), start, end))
        except Exception as e:
            s['status'], s['points'], s['error'] = 'sin dato', [], type(e).__name__
        else:
            s['points'] = points
            s['status'] = 'válida' if points else 'sin dato'
            s.update(_summary(points, alert, evacuation))
        stations.append(s)

    ref = next((s for s in stations if s.get('points')), None)
    ref_clean = ({k: ref.get(k) for k in ('station', 'river', 'locality', 'distance_km', 'variable',
                                          'unit', 'alert_level', 'evacuation_level', 'last_value',
                                          'last_time', 'min', 'max', 'trend', 'level_state')}
                 if ref else None)
    return c.envelope({
        'capability': 'OBSERVATION',
        'period_days': days,
        'from': _local(start.isoformat()), 'to': _local(end.isoformat()),
        'reference': ref_clean,
        'series': ref.get('points') if ref else [],
        'stations': stations,
        'method': ('Lecturas observadas de las estaciones hidrométricas del INA (redes BDHI) más cercanas '
                   'al lote, ordenadas por distancia al centro. La altura (m) y el caudal (m³/s) son de la '
                   'estación sobre el río, no del lote: describen el contexto de crecida. Para estimar qué '
                   'se inunda hace falta cruzar con relieve, umbrales y límites de cuenca (otros módulos DOTS).')},
        BASE + '/obs/puntual/series', 'alturas y caudales observados del INA en el área',
        'INA · DSIyAH (Argentina)', 'recibido' if ref else 'sin dato',
        None if ref else 'Las estaciones del área no tienen observaciones en el período')
