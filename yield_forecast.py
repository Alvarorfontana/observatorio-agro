"""yield_forecast v1.0 — rendimiento esperado por agua (FAO-33).

Estima qué fracción del potencial rinde la campaña por agua disponible: Ya/Ym = 1 − Ky·(1 − ETa/ETm)
(Doorenbos y Kassam, 1979). ETm es la demanda máxima (Σ Kc·ET0) y ETa el consumo real limitado por el
agua (Σ Ks·Kc·ET0), con el balance hídrico diario FAO-56 de secano:

    Dr,i = Dr,i−1 − P_i + ETc,aj,i     (Dr < 0 → percolación, Dr = 0)

Reutiliza los Kc y las etapas de `crop_water`. La ET0 y la lluvia salen de Open-Meteo: ERA5 observado
hasta ~6 días atrás, pronóstico a 10 días y, para el resto de la campaña, climatología ERA5 del mismo
día del año. El agua útil del suelo (TAW) sale de SoilGrids. Nunca se inventan datos: si falta la
siembra, el suelo o la ET0, el resultado queda en 'sin dato'.

Es una estimación por agua, no un pronóstico de cosecha. Asume secano (sin riego).
"""
from datetime import date, timedelta

import research_connectors as c
import crop_water
import scales

ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
FORECAST = 'https://api.open-meteo.com/v1/forecast'
DAILY = 'et0_fao_evapotranspiration,precipitation_sum'

OBS_LAG_DAYS = 6        # la observación ERA5 llega hasta ~6 días atrás
FORECAST_DAYS = 10      # pronóstico de ET0/lluvia
CLIM_YEARS = 10         # años de ERA5 para la climatología por día del año

# Coeficiente de sensibilidad al agua Ky por cultivo (FAO-33).
KY = {'maiz': 1.25, 'soja': 0.85, 'trigo': 1.15, 'girasol': 0.95, 'sorgo': 0.90, 'alfalfa': 1.10, 'pastura': 1.00}

FAO33 = 'FAO-33 (Doorenbos y Kassam, 1979)'
SOURCE = 'https://open-meteo.com'
METHOD = ('FAO-33: Ya/Ym = 1 − Ky·(1 − ETa/ETm), con balance hídrico FAO-56 de secano '
          '(ETm = Σ Kc·ET0, ETa = Σ Ks·Kc·ET0).')
SOURCES = ('ET0 y lluvia: Open-Meteo (ERA5 observado, pronóstico y climatología); '
           'agua útil del suelo: ISRIC SoilGrids; Kc y etapas: FAO-56.')
CAVEAT = ('Estimación por agua (no pronóstico de cosecha). Asume secano y sin otros factores de estrés; '
          'la parte de la campaña que falta se rellena con climatología ERA5.')


# ───────────────────────────── parámetros del cultivo ─────────────────────────────
def ky_for(crop):
    """Coeficiente Ky del cultivo; 1.0 si no está tabulado."""
    return KY.get(crop, 1.0)


def season_days(crop):
    """Duración de la campaña en días (suma de las etapas de `crop_water`)."""
    cw = crop_water.CROPS.get(crop) or crop_water.CROPS['maiz']
    return sum(cw['stages'])


def _crop(crop):
    return crop if crop in crop_water.CROPS else 'maiz'


# ───────────────────────────── fuentes de ET0 y lluvia ─────────────────────────────
def _rows(daily):
    """daily de Open-Meteo → [(fecha, et0, lluvia)]."""
    d = daily or {}
    dates = d.get('time') or []
    et0 = d.get('et0_fao_evapotranspiration') or []
    rain = d.get('precipitation_sum') or []
    return [(str(ds), et0[i] if i < len(et0) else None, rain[i] if i < len(rain) else None)
            for i, ds in enumerate(dates)]


def _by_date(daily):
    return {ds: (float(e or 0.0), float(r or 0.0)) for ds, e, r in _rows(daily)}


def _by_doy(daily):
    """Promedio de ET0 y lluvia por día del año (para rellenar la campaña con climatología)."""
    acc = {}
    for ds, e, r in _rows(daily):
        try:
            doy = date.fromisoformat(ds).timetuple().tm_yday
        except ValueError:
            continue
        a = acc.setdefault(doy, [0.0, 0.0, 0])
        a[0] += float(e or 0.0); a[1] += float(r or 0.0); a[2] += 1
    return {doy: (round(v[0] / v[2], 2), round(v[1] / v[2], 2)) for doy, v in acc.items() if v[2]}


def _archive(lat, lon, start, end):
    return c.external(ARCHIVE, {'latitude': lat, 'longitude': lon, 'start_date': start, 'end_date': end,
                                'daily': DAILY, 'models': 'era5', 'timezone': 'UTC'}).get('data') or {}


def _forecast(lat, lon):
    return c.external(FORECAST, {'latitude': lat, 'longitude': lon, 'daily': DAILY, 'timezone': 'UTC',
                                 'past_days': OBS_LAG_DAYS, 'forecast_days': FORECAST_DAYS}).get('data') or {}


def _climatology(lat, lon, today):
    y = today.year
    return _by_doy(_archive(lat, lon, f'{y - CLIM_YEARS}-01-01', f'{y - 1}-12-31'))


def _weather(lat, lon, sowing, today, season_end):
    """Observado (ERA5), pronóstico y climatología, cada uno sólo si la campaña lo necesita."""
    obs_end = today - timedelta(days=OBS_LAG_DAYS)
    observed = _by_date(_archive(lat, lon, sowing.isoformat(), min(obs_end, season_end).isoformat())) if sowing <= obs_end else {}
    forecast = _by_date(_forecast(lat, lon)) if season_end >= obs_end else {}
    clim = _climatology(lat, lon, today) if season_end > today + timedelta(days=FORECAST_DAYS - 1) else {}
    return observed, forecast, clim


def assemble_days(sowing, total, observed, forecast, clim, today):
    """Serie diaria de la campaña: observado hasta ~6 días atrás, pronóstico a 10 días y el resto climatología."""
    obs_end = today - timedelta(days=OBS_LAG_DAYS)
    out = []
    for i in range(total):
        d = sowing + timedelta(days=i)
        key = d.isoformat()
        if d <= obs_end and key in observed:
            source, (et0, rain) = 'observado', observed[key]
        elif key in forecast:
            source, (et0, rain) = 'pronostico', forecast[key]
        else:
            source = 'climatologia'
            et0, rain = (clim or {}).get(d.timetuple().tm_yday, (0.0, 0.0))
        out.append({'date': key, 'et0': float(et0 or 0.0), 'rain': float(rain or 0.0), 'source': source})
    return out


# ───────────────────────────── balance hídrico y FAO-33 ─────────────────────────────
def water_balance(crop, days, theta_fc, theta_wp):
    """Balance FAO-56 día a día (secano) y rendimiento relativo FAO-33. `days[0]` es el día de siembra."""
    cw = crop_water.CROPS.get(crop) or crop_water.CROPS['maiz']
    if not days:
        raise ValueError('Sin días de campaña para el balance')
    taw = crop_water.taw_mm(theta_fc, theta_wp, cw['zr'])
    if not taw:
        raise ValueError('Sin agua útil del suelo (SoilGrids) para el balance')
    raw = cw['p'] * taw
    ky = ky_for(crop)
    dr = 0.0; dp_total = 0.0; etm_total = 0.0; eta_total = 0.0
    rows = []
    for i, day in enumerate(days):
        kc = crop_water.kc_for_day(crop, i)
        et0 = float(day.get('et0') or 0.0)
        p = float(day.get('rain') or 0.0)
        ks = 1.0 if dr <= raw else max(0.0, (taw - dr) / (taw - raw))
        etc_max = kc * et0
        etc_actual = ks * etc_max
        dr = dr - p + etc_actual
        dp = 0.0
        if dr < 0:
            dp = -dr; dr = 0.0
        dp_total += dp; etm_total += etc_max; eta_total += etc_actual
        rows.append({**day, 'stage': crop_water.stage(crop, i)['name'], 'kc': round(kc, 3), 'ks': round(ks, 3),
                     'etc_max_mm': round(etc_max, 1), 'etc_actual_mm': round(etc_actual, 1),
                     'dr_mm': round(dr, 1), 'dp_mm': round(dp, 1)})
    ratio = (eta_total / etm_total) if etm_total > 0 else None
    rel = None if ratio is None else max(0.0, min(1.0, 1 - ky * (1 - ratio)))
    return {'taw_mm': taw, 'raw_mm': round(raw, 1), 'ky': ky,
            'etc_max_mm': round(etm_total, 1), 'etc_actual_mm': round(eta_total, 1),
            'water_deficit_mm': round(etm_total - eta_total, 1), 'dp_total_mm': round(dp_total, 1),
            'relative_yield_pct': None if rel is None else round(100 * rel, 1), 'days': rows}


# ───────────────────────────── suelo ─────────────────────────────
def _soil_values(env):
    """SoilGrids → {propiedad: [valores por profundidad]} aplicando el factor de escala de cada capa."""
    by = {}
    for layer in ((env or {}).get('data') or {}).get('properties', {}).get('layers', []) or []:
        f = (layer.get('unit_measure') or {}).get('d_factor') or 1
        by[layer.get('name')] = [None if (d.get('values') or {}).get('mean') is None else d['values']['mean'] / f
                                 for d in layer.get('depths') or []]
    return by


def _avg(xs):
    xs = [v for v in (xs or []) if v is not None]
    return sum(xs) / len(xs) if xs else None


def _num(v):
    try:
        return float(v) if v not in (None, '') else None
    except (TypeError, ValueError):
        return None


# ───────────────────────────── análisis ─────────────────────────────
def _sin_dato(msg):
    return c.envelope(None, SOURCE, 'rendimiento esperado por agua (FAO-33)',
                      f'{FAO33} · Open-Meteo ERA5 · ISRIC SoilGrids', 'sin dato', msg)


def _reading(d):
    return (f"{d['crop_name']}: {d['etc_actual_mm']} mm de agua efectiva sobre {d['etc_max_mm']} mm de demanda "
            f"(Ky {d['ky']}). Rinde esperado {d['relative_yield_pct']} % del potencial"
            + (f", unas {d['expected_t_ha']} t/ha." if d.get('expected_t_ha') is not None else '.')
            + ' Estimación por agua (FAO-33), no pronóstico de cosecha.')


def analyze(lat, lon, crop='maiz', sowing=None, potencial_t_ha=None):
    """Rendimiento relativo de la campaña por agua disponible. Envelope o excepción."""
    today = c._now().date()
    if not sowing:
        return _sin_dato('Indicá la fecha de siembra (YYYY-MM-DD) para estimar el rendimiento por agua.')
    try:
        sow = date.fromisoformat(str(sowing)[:10])
    except ValueError:
        raise ValueError('Fecha de siembra inválida: se espera YYYY-MM-DD')
    if sow > today:
        return _sin_dato('La siembra todavía no ocurrió: no hay campaña para evaluar.')

    cname = _crop(crop)
    cw = crop_water.CROPS[cname]
    total = season_days(cname)
    season_end = sow + timedelta(days=total - 1)

    by = _soil_values(c.soil_full(lat, lon))
    theta_fc, theta_wp = _avg(by.get('wv0033')), _avg(by.get('wv1500'))
    if theta_fc is None or theta_wp is None:
        return _sin_dato('Sin agua útil del suelo (SoilGrids) para el balance hídrico.')

    observed, forecast, clim = _weather(lat, lon, sow, today, season_end)
    days = assemble_days(sow, total, observed, forecast, clim, today)
    try:
        bal = water_balance(cname, days, theta_fc, theta_wp)
    except ValueError as e:
        return _sin_dato(str(e))

    rel = bal['relative_yield_pct']
    pot = _num(potencial_t_ha)
    data = {'crop': cname, 'crop_name': cw['name'], 'sowing': sow.isoformat(), 'today': today.isoformat(),
            'season_days': total, 'season_end': season_end.isoformat(), 'root_depth_m': cw['zr'],
            'taw_mm': bal['taw_mm'], 'raw_mm': bal['raw_mm'], 'ky': bal['ky'],
            'etc_max_mm': bal['etc_max_mm'], 'etc_actual_mm': bal['etc_actual_mm'],
            'water_deficit_mm': bal['water_deficit_mm'], 'dp_total_mm': bal['dp_total_mm'],
            'relative_yield_pct': rel, 'scale': scales.band('yield_pct', rel),
            'potential_t_ha': pot,
            'expected_t_ha': round(pot * rel / 100, 2) if (pot is not None and rel is not None) else None,
            'method': METHOD, 'sources': SOURCES, 'caveat': CAVEAT, 'days': bal['days']}
    ok = rel is not None
    data['reading'] = _reading(data) if ok else 'El balance no cerró: falta ET0 en la campaña.'
    return c.envelope(data, SOURCE, 'rendimiento esperado por agua (FAO-33)',
                      f'{FAO33} · Open-Meteo ERA5 · ISRIC SoilGrids',
                      'recibido' if ok else 'sin dato',
                      None if ok else 'No se pudo estimar el rendimiento por agua.')
