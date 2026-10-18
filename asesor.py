"""asesor v1.0 — asesor agronómico integrado del lote.

Combina en una sola respuesta, con sus fuentes declaradas:
  agua       crop_water (FAO-56 / pyfao56): Kc, ETc, agua útil y necesidad de riego
  nitrogeno  nitrogen (DSSAT / RothC): demanda, aporte del suelo y dosis sugerida
  aire       air (OpenAQ / CAMS): índice de calidad de aire y lectura agronómica
  enso       fase actual (NOAA CPC) con nota agronómica para el Cono Sur
Cada bloque sin dato lo informa como faltante; ninguno sustituye a otro.
"""
from concurrent.futures import ThreadPoolExecutor

import research_connectors as c
import crop_water
import nitrogen
import air as air_mod
import spray_window
import disease as disease_mod
import scales

FORECAST = 'https://api.open-meteo.com/v1/forecast'

# Nota agronómica de la fase del Pacífico para el Cono Sur (orientativa, no pronóstico local).
ENSO_NOTE = {
    'El Niño': 'El Niño suele traer lluvias por encima de lo normal en el Litoral y el sur de Brasil: mayor riesgo de anegamiento y crecidas.',
    'La Niña': 'La Niña suele traer lluvias por debajo de lo normal en el Litoral y el centro: mayor riesgo de déficit hídrico.',
    'Neutro': 'Fase neutra del Pacífico: manda la variabilidad local.',
}


def soil_values(env):
    """SoilGrids → {propiedad: {profundidad: valor}} aplicando el factor de escala de cada capa."""
    by = {}
    for layer in ((env or {}).get('data') or {}).get('properties', {}).get('layers', []) or []:
        f = (layer.get('unit_measure') or {}).get('d_factor') or 1
        by[layer.get('name')] = {d.get('label'): (None if (d.get('values') or {}).get('mean') is None else d['values']['mean'] / f)
                                 for d in layer.get('depths') or []}
    return by


def _avg(by):
    xs = [v for v in (by or {}).values() if v is not None]
    return sum(xs) / len(xs) if xs else None


def _forecast(lat, lon):
    return c.external(FORECAST, {'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 10,
                                 'daily': 'et0_fao_evapotranspiration,precipitation_sum'})['data'] or {}


def _hourly(lat, lon):
    return c.external(FORECAST, {'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 7,
                                 'hourly': 'temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation'})['data'] or {}


def _enso():
    import enso_panel
    data = enso_panel.enso_panel().get('data') or {}
    phase = (data.get('phase') or {}).get('phase')
    if not phase:
        return None
    return {'phase': phase, 'oni': (data.get('oni') or {}).get('anom'), 'note': ENSO_NOTE.get(phase, ''), 'source': 'NOAA CPC'}


def advise(lat, lon, crop='maiz', sowing=None, yield_t_ha=None, prev_crop=None):
    jobs, got, errors = {}, {}, {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {'forecast': pool.submit(_forecast, lat, lon), 'hourly': pool.submit(_hourly, lat, lon),
                'soil': pool.submit(c.soil_full, lat, lon), 'air': pool.submit(c.air_quality, lat, lon),
                'enso': pool.submit(_enso)}
        for k, f in jobs.items():
            try:
                got[k] = f.result()
            except Exception as e:
                errors[k] = type(e).__name__

    soil = soil_values(got.get('soil'))
    daily = (got.get('forecast') or {}).get('daily') or {}
    hourly = (got.get('hourly') or {}).get('hourly') or {}
    et0 = daily.get('et0_fao_evapotranspiration') or []
    rain = daily.get('precipitation_sum') or []

    agua = nitrogeno = aire = pulverizacion = enfermedad = None
    if et0:
        try:
            agua = crop_water.advise(crop, sowing, et0, rain, _avg(soil.get('wv0033')), _avg(soil.get('wv1500')))
        except Exception as e:
            errors['agua'] = type(e).__name__
    try:
        nitrogeno = nitrogen.recommend(crop, yield_t_ha, soc_gkg=_avg(soil.get('soc')), prev_crop=prev_crop)
    except Exception as e:
        errors['nitrogeno'] = type(e).__name__
    try:
        aq = (got.get('air') or {}).get('data') or {}
        aire = air_mod.evaluate(air_mod.from_open_meteo(aq.get('hourly') or {}))
        if aire and aire.get('index') is not None:
            aire['scale'] = scales.band('eaqi', aire['index'])
    except Exception as e:
        errors['aire'] = type(e).__name__
    if hourly:
        try:
            pulverizacion = spray_window.evaluate(hourly, 5)
        except Exception as e:
            errors['pulverizacion'] = type(e).__name__
        key = (disease_mod.BY_CROP.get(crop) or [None])[0]
        if key:
            try:
                enfermedad = disease_mod.evaluate(hourly, key, 7)
            except Exception as e:
                errors['enfermedad'] = type(e).__name__
    enso = got.get('enso')

    lectura = [b['reading'] for b in (agua, nitrogeno, aire) if b and b.get('reading')]
    if pulverizacion:
        lectura.append(pulverizacion['reading'])
    if enfermedad:
        lectura.append(enfermedad['reading'])
    if enso:
        lectura.append(f"Pacífico en fase {enso['phase']} (ONI {enso['oni']}). {enso['note']}")
    data = {'point': {'lat': lat, 'lon': lon}, 'crop': crop, 'sowing': sowing, 'agua': agua,
            'nitrogeno': nitrogeno, 'aire': aire, 'pulverizacion': pulverizacion, 'enfermedad': enfermedad,
            'enso': enso, 'errors': errors, 'lectura': ' '.join(lectura)}
    ok = bool(agua or nitrogeno or aire or pulverizacion or enfermedad or enso)
    return c.envelope(data, 'multi', 'asesor agronómico integrado',
                      'FAO-56 · ISRIC SoilGrids · Open-Meteo/CAMS · NOAA CPC · umbrales de aspersión e infección',
                      'recibido' if ok else 'sin dato', None if ok else 'Ninguna fuente respondió')
