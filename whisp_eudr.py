"""whisp_eudr v1.0 — segunda opinión de deforestación con Whisp (FAO · Forest Data Partnership).

Whisp ("What is in that plot?") cruza decenas de mapas públicos, entre ellos el mapa de bosques 2020 del
JRC que la Comisión Europea publica como referencia para el EUDR (EUFO_2020), y devuelve un riesgo por
tipo de producto: risk_acrop (cultivos anuales, como soja), risk_pcrop (perennes) y risk_timber (madera).
Código MIT: https://github.com/forestdatapartnership/whisp · API: https://whisp.openforis.org/api/docs

La API es gratuita pero pide una clave personal (X-API-KEY) que se genera al iniciar sesión en
whisp.openforis.org. DOTS la lee de la variable de entorno WHISP_API_KEY en Vercel; sin ella el módulo
informa que falta la credencial y no inventa resultados.
"""
import os

import research_connectors as c

BASE = os.environ.get('WHISP_API_URL', 'https://whisp.openforis.org/api')
DONE, RUNNING = 'analysis_completed', ('analysis_queued', 'analysis_processing')
# Para ganado no hay árbol propio: se usa el de cultivos anuales (pasturas sin bosque en 2020 y sin pérdida posterior).
RISK_FIELD = {'soja': 'risk_acrop', 'bovino': 'risk_acrop', 'madera': 'risk_timber'}
RISK_ES = {'low': 'riesgo bajo', 'high': 'riesgo alto', 'more_info_needed': 'hace falta más información'}


def _yes(v):
    return str(v).strip().lower() in ('yes', 'true', '1')


def summarize(props, product='bovino'):
    field = RISK_FIELD.get(product, 'risk_acrop')
    risk = props.get(field)
    jrc = props.get('EUFO_2020')
    trees = _yes(props.get('Ind_01_treecover'))
    after = _yes(props.get('Ind_04_disturbance_after_2020'))
    parts = []
    pct = None
    if jrc is not None:
        # Whisp informa superficies en hectáreas (salvo que se pida en porcentaje); el % sale del área del lote.
        try:
            ha = float(jrc)
            area = float(props.get('Area') or props.get('Plot_area_ha') or 0)
            pct = round(ha / area * 100, 1) if area > 0 else None
            parts.append(f"Mapa de bosques 2020 de la UE (JRC): {ha:.1f} ha" + (f" ({pct:.1f} % del lote)." if pct is not None else '.'))
        except (TypeError, ValueError):
            parts.append(f"Mapa de bosques 2020 de la UE (JRC): {jrc}.")
    parts.append('Algún mapa marca árboles en 2020.' if trees else 'Ningún mapa marca bosque en 2020.')
    if trees:
        parts.append('Hay alteraciones después de 2020.' if after else 'Sin alteraciones después de 2020.')
    return {'risk': risk, 'risk_es': RISK_ES.get(risk, risk), 'field': field, 'jrc_forest_2020_ha': jrc, 'jrc_forest_2020_pct': pct,
            'treecover_2020': trees, 'disturbance_after_2020': after,
            'text': f"Whisp: {RISK_ES.get(risk, 'sin resultado')}. " + ' '.join(parts)}


def _fc(gj):
    feats = (gj or {}).get('features') or []
    return feats[0].get('properties') if feats else None


def check(geojson=None, token=None, product='bovino', wait=40):
    """Envía el lote (o consulta un trabajo ya enviado) y espera hasta `wait` segundos. Siempre devuelve un sobre."""
    key = os.environ.get('WHISP_API_KEY')
    if not key:
        return c.envelope({'status': 'requiere credencial', 'missing_env': ['WHISP_API_KEY'],
                           'how': 'Crear cuenta gratis en whisp.openforis.org, generar la clave en la cuenta y cargarla en Vercel como WHISP_API_KEY.'},
                          'https://whisp.openforis.org/', 'Whisp · segunda opinión EUDR', 'FAO · Forest Data Partnership', 'sin dato',
                          'Falta la clave gratuita WHISP_API_KEY')
    import time
    h = {'X-API-KEY': key, 'Content-Type': 'application/json'}
    if not token:
        body = dict(geojson or {}); body['analysisOptions'] = {'async': True, 'nationalCodes': ['ar']}
        r = c.SESSION.post(f'{BASE}/submit/geojson', json=body, headers=h, timeout=25)
        j = r.json() if r.content else {}
        if r.status_code >= 400:
            raise ValueError(j.get('message') or f'Whisp respondió {r.status_code}')
        if j.get('code') == DONE and _fc(j.get('data')):
            return _ok(_fc(j['data']), product, None)
        token = (j.get('data') or {}).get('token') or (j.get('context') or {}).get('token')
        if not token:
            raise ValueError('Whisp no devolvió un número de trabajo')
    t0 = time.monotonic()
    while True:
        r = c.SESSION.get(f'{BASE}/status/{token}', headers=h, timeout=20)
        j = r.json() if r.content else {}
        code = j.get('code')
        if code == DONE:
            props = _fc(j.get('data'))
            if not props:
                g = c.SESSION.get(f'{BASE}/generate-geojson/{token}', timeout=20)
                props = _fc(g.json() if g.ok else None)
            if not props:
                raise ValueError('Whisp terminó pero no devolvió resultados')
            return _ok(props, product, token)
        if code not in RUNNING:
            raise ValueError(j.get('message') or f'Whisp: {code}')
        if time.monotonic() - t0 > wait:
            return c.envelope({'status': 'en proceso', 'token': token, 'percent': (j.get('data') or {}).get('percent')},
                              f'{BASE}/status/{token}', 'Whisp · segunda opinión EUDR', 'FAO · Forest Data Partnership', 'en proceso')
        time.sleep(3)


def _ok(props, product, token):
    return c.envelope({**summarize(props, product), 'token': token},
                      'https://whisp.openforis.org/', 'Whisp · convergencia de evidencia (JRC, Hansen, TMF, ESA y otros)',
                      'FAO · Forest Data Partnership')
