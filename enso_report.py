"""El Niño para un lote: resumen para el tablero (board) e informe PDF (Typst).

Junta la cadena del Pacífico (enso_chain.chain), la historia del punto en cada fase (enso_chain.lot_impact),
la lluvia de los últimos 90 días y los próximos 16 en el lote (enso_sa.point_now) y el monitor de Sudamérica
(enso_sa.live). Las recomendaciones son reglas declaradas sobre esos números, no un modelo.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import research_connectors as c
import enso_chain as ec
import enso_sa

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report')
TEMPLATE = os.path.join(BASE, 'enso.typ')
FONTS = os.path.join(BASE, 'fonts')
MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def _data(env):
    return (env or {}).get('data') or {}


def advice(phase, expected, now90, next16):
    """Reglas simples y declaradas. expected: % de lluvia con El Niño fuerte vs neutral en el punto."""
    out = []
    nino = bool(phase) and phase.startswith('El Niño')
    nina = bool(phase) and phase.startswith('La Niña')
    if nino and expected is not None and expected >= 20:
        out += ['Revisar drenajes, canales y alcantarillas antes de diciembre: en este punto los Niño fuertes trajeron bastante más lluvia.',
                'Planificar accesos y caminos internos para la cosecha y el movimiento de hacienda con suelo saturado.',
                'Tener identificados lotes altos o de reserva para la hacienda si se anegan los bajos.',
                'En agricultura: considerar el riesgo de piso para siembras y aplicaciones; seguir el pronóstico semanal.']
    elif nino and expected is not None and expected <= -15:
        out += ['En este punto El Niño suele traer menos lluvia: cuidar la reserva de agua y forraje.',
                'Ajustar la carga animal y la fecha de siembra al agua disponible.']
    elif nina and expected is not None:
        out += ['La Niña suele traer menos lluvia en gran parte del Litoral y la Pampa: priorizar reservas de agua y forraje.']
    elif nino:
        out += ['En este punto El Niño no cambió mucho la lluvia de temporada en el pasado: seguir el pronóstico de corto plazo.']
    if now90 is not None and expected is not None and abs(expected) >= 10:
        if (now90 > 0) == (expected > 0) and abs(now90) >= 15:
            out.append(f'La señal ya se ve: los últimos 90 días van {now90:+d} % respecto de lo normal.')
        elif abs(now90) >= 15:
            out.append(f'Por ahora la lluvia va al revés de lo esperado ({now90:+d} % en 90 días); la señal de El Niño suele llegar con la primavera y el verano.')
        else:
            out.append('Los últimos 90 días estuvieron cerca de lo normal: la señal todavía no se nota en el lote.')
    if next16 is not None and next16 >= 50:
        out.append(f'Próximas dos semanas: se pronostican {next16:+d} % de lluvia respecto de lo normal.')
    out.append('Ver la perspectiva trimestral oficial (SMN, INMET, DMC según el país) antes de decidir.')
    return out


def board(lat, lon):
    with ThreadPoolExecutor(max_workers=2) as pool:
        fc = pool.submit(ec.chain)
        fi = pool.submit(ec.lot_impact, lat, lon)
        errors = {}
        try:
            chain = _data(fc.result())
        except Exception as e:
            chain = {}; errors['cadena'] = type(e).__name__
        try:
            impact = _data(fi.result())
        except Exception as e:
            impact = {}; errors['historia'] = type(e).__name__
    try:
        now = enso_sa.point_now(lat, lon, impact.get('normals'))
    except Exception as e:
        now = {}; errors['ahora'] = type(e).__name__
    sup = next((s for s in chain.get('steps') or [] if s.get('key') == 'superficie'), {})
    g = (impact.get('groups') or {})
    strong = g.get('El Niño fuerte o muy fuerte') or g.get('El Niño') or {}
    out = {'verdict': chain.get('verdict'), 'phase': sup.get('phase'), 'oni': sup.get('oni'),
           'steps': [{k: s.get(k) for k in ('n', 'key', 'title', 'value', 'unit', 'date', 'signal', 'reading', 'records', 'oni', 'phase', 'nino12', 'mei', 'olr')}
                     for s in chain.get('steps') or []],
           'extras': chain.get('extras') or [],
           'impact': {k: impact.get(k) for k in ('groups', 'seasons', 'neutral_base_mm', 'wettest', 'driest', 'analog_seasons', 'reading', 'method')},
           'expected_pct': strong.get('vs_neutral_pct'), 'expected_n': strong.get('n'), 'expected_wetter': strong.get('wetter_than_neutral'),
           'now': now, 'errors': errors}
    out['advice'] = advice(out['phase'], out['expected_pct'], now.get('now90_pct'), now.get('next16_pct'))
    ok = bool(chain or impact)
    return c.envelope(out, 'multi', 'El Niño en el lote', 'NOAA CPC · NOAA PSL · NOAA PMEL · Copernicus ERA5',
                      'recibido' if ok else 'sin dato', None if ok else 'No respondieron las fuentes')


def _num(v, d=0):
    if v is None:
        return '—'
    s = f'{float(v):,.{d}f}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def _sign(v, unit=' %'):
    return '—' if v is None else ('+' if v > 0 else '') + _num(v) + unit


def report_data(lat, lon, place, today=None):
    today = today or datetime.now(timezone.utc).date()
    with ThreadPoolExecutor(max_workers=2) as pool:
        fb = pool.submit(board, lat, lon)
        fs = pool.submit(enso_sa.live)
        b = _data(fb.result())
        try:
            sa = _data(fs.result(timeout=45))
        except Exception:
            sa = {}
    now = b.get('now') or {}
    steps = []
    for s in b.get('steps') or []:
        r = s.get('records') or {}
        val = '—' if s.get('value') is None else f"{_num(s['value'], 2 if abs(s['value']) < 10 else 1)} {s.get('unit') or ''}"
        steps.append({'n': s.get('n'), 'title': s.get('title') or '', 'value': val, 'date': s.get('date') or '',
                      'signal': s.get('signal') or '', 'reading': s.get('reading') or '', 'record': r.get('since_text') or ''})
    extras = [{'name': e.get('name') or '', 'value': '—' if e.get('value') is None else f"{_num(e['value'], 2)} {e.get('unit') or ''}",
               'date': e.get('date') or '', 'reading': e.get('reading') or ''} for e in b.get('extras') or []]
    imp = b.get('impact') or {}
    groups = [{'name': k, 'n': v.get('n'), 'median': _num(v.get('median_mm')), 'vs': _sign(v.get('vs_neutral_pct')),
               'wetter': f"{v.get('wetter_than_neutral')} de {v.get('n')}"} for k, v in (imp.get('groups') or {}).items()]
    seasons = [{'season': s['season'], 'pct': s.get('anomaly_pct'), 'phase': s.get('phase')} for s in imp.get('seasons') or [] if s.get('anomaly_pct') is not None]
    sa_rows = []
    for r in sa.get('places') or []:
        sa_rows.append({'name': r['name'], 'country': r['country'], 'now': _sign(r.get('now90_pct')), 'now_v': r.get('now90_pct'),
                        'exp': _sign(r.get('expected_pct')), 'exp_v': r.get('expected_pct'), 'next': '—' if r.get('next16_mm') is None else _num(r['next16_mm']) + ' mm',
                        'signal': r.get('signal') or ''})
    phase = b.get('phase') or 'sin dato'
    summary = []
    if b.get('verdict'):
        summary.append(b['verdict'] + (f" Fase oficial: {phase} (ONI {_num(b.get('oni'), 2)})." if b.get('oni') is not None else ''))
    if b.get('expected_pct') is not None:
        summary.append(f"En {place}, las temporadas de octubre a marzo con El Niño fuerte llovieron en la mediana {_sign(b['expected_pct'])} respecto de los años neutrales "
                       f"({b.get('expected_wetter')} de {b.get('expected_n')} por encima).")
    if now.get('obs90_mm') is not None:
        summary.append(f"Últimos 90 días: {_num(now['obs90_mm'])} mm, " + (f"{_sign(now.get('now90_pct'))} respecto de lo normal ({_num(now.get('normal90_mm'))} mm)." if now.get('now90_pct') is not None else 'sin normal para comparar.'))
    if now.get('next16_mm') is not None:
        summary.append(f"Próximos 16 días: {_num(now['next16_mm'])} mm pronosticados" + (f" ({_sign(now.get('next16_pct'))} respecto de lo normal)." if now.get('next16_pct') is not None else '.'))
    counts = sa.get('counts') or {}
    if counts:
        summary.append(f"En Sudamérica: en {counts.get('ya se nota', 0)} de {len(sa_rows)} localidades la lluvia ya va en el sentido que suele traer El Niño; "
                       f"en {counts.get('por ahora va al revés', 0)} va al revés.")
    return {'title': f'El Niño · {place}', 'place': place, 'lat': _num(lat, 3), 'lon': _num(lon, 3),
            'generated': f'{today.day} de {MONTHS[today.month - 1]} de {today.year}', 'url': 'observatorio-agro.vercel.app/el-nino',
            'phase': phase, 'oni': _num(b.get('oni'), 2), 'nino': phase.startswith('El Niño'), 'nina': phase.startswith('La Niña'),
            'summary': summary, 'steps': steps, 'extras': extras, 'groups': groups, 'seasons': seasons,
            'analogs': ', '.join(imp.get('analog_seasons') or []) or '—',
            'wettest': ', '.join(f"{s['season']} ({_num(s['rain_mm'])} mm)" for s in imp.get('wettest') or []) or '—',
            'driest': ', '.join(f"{s['season']} ({_num(s['rain_mm'])} mm)" for s in imp.get('driest') or []) or '—',
            'base': _num(imp.get('neutral_base_mm')),
            'expected': _sign(b.get('expected_pct')), 'now90': _sign(now.get('now90_pct')), 'obs90': _num(now.get('obs90_mm')),
            'next16': '—' if now.get('next16_mm') is None else _num(now['next16_mm']) + ' mm', 'next16pct': _sign(now.get('next16_pct')),
            'window': f"{(now.get('window') or {}).get('from', '')[8:10]}/{(now.get('window') or {}).get('from', '')[5:7]} al {(now.get('window') or {}).get('to', '')[8:10]}/{(now.get('window') or {}).get('to', '')[5:7]}" if now.get('window') else '',
            'advice': b.get('advice') or [], 'sa': sa_rows, 'sa_season': sa.get('season') or 'octubre a marzo',
            'sa_ref': bool((sa.get('reference') or {}).get('available')),
            'errors': ', '.join(f'{k}: {v}' for k, v in (b.get('errors') or {}).items())}


def pdf(lat, lon, place, today=None):
    import typst
    data = json.dumps(report_data(lat, lon, place, today), ensure_ascii=False, default=str)
    out = typst.compile(TEMPLATE, root=BASE, font_paths=[FONTS], ignore_system_fonts=True, sys_inputs={'data': data})
    if out[:5] != b'%PDF-':
        raise RuntimeError('Typst no generó el PDF')
    return out
