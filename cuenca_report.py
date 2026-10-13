"""Informe PDF de la Cuenca del Plata (Typst): El Niño, alertas por lluvia en cabeceras, imágenes, ríos y represas.

Estructura fija: 1 portada y resumen · 2 El Niño · 3 alertas por cuenca · 4 imágenes de la zona ·
5 lluvia por subcuenca · 6 represas y ríos · 7 tiempos de traslado · 8 fuentes oficiales y alcances.
"""
import json, os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import cuenca as cc

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report')
TEMPLATE = os.path.join(BASE, 'cuenca.typ')
FONTS = os.path.join(BASE, 'fonts')
MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
TONE = {'Normal': 'ok', 'Atención': 'warn', 'Alerta': 'alert', 'Peligro': 'risk'}


def num(v, d=0):
    if v is None:
        return '—'
    try:
        s = f'{float(v):,.{d}f}'
    except (TypeError, ValueError):
        return '—'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def dm(iso):
    return f'{iso[8:10]}/{iso[5:7]}' if iso and len(iso) >= 10 else '—'


def sign(v, d=1):
    return '—' if v is None else ('+' if v > 0 else '') + num(v, d)


MONTHS_SHORT = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def my(iso):
    return f"{MONTHS_SHORT[int(iso[5:7]) - 1]} {iso[:4]}" if iso and len(iso) >= 7 else ''


def m2(v):
    return '—' if v is None else f'{num(v, 2)} m'


def pred_text(p):
    if not p:
        return ''
    if p.get('kind') == 'altura':
        ref = f" (alerta {num(p.get('alert_m'), 2)} m, evacuación {num(p.get('evac_m'), 2)} m)" if p.get('alert_m') is not None else ''
        return (f"Con {num(p.get('rain10_mm'))} mm en 10 días, el río en {p.get('place')} podría subir unos {num(p.get('rise_m'), 1)} m: "
                f"de {num(p.get('from_m'), 2)} a {num(p.get('to_m'), 2)} m{ref}.")
    return (f"Con {num(p.get('rain10_mm'))} mm en 10 días, el caudal en {p.get('place')} podría subir unos {num(p.get('rise_q'))} m³/s: "
            f"de {num(p.get('from_q'))} a {num(p.get('to_q'))} m³/s.")


def pred_basis(p):
    if not p:
        return ''
    per = f"{num(p.get('per10mm_m'), 2)} m" if p.get('kind') == 'altura' else f"{num(p.get('per10mm_q'))} m³/s"
    out = f"{per} por cada 10 mm · {p.get('cases')} episodios en 20 años"
    if p.get('rain_alert_mm'):
        out += f" · en el pasado, con ~{num(p['rain_alert_mm'])} mm pasó el nivel de alerta"
    if p.get('rain_evac_mm'):
        out += f" y con ~{num(p['rain_evac_mm'])} mm el de evacuación"
    return out + '.'


def _image(urls, timeout=12):
    """Primer URL que devuelva una imagen válida (PNG o JPEG). None si ninguna responde."""
    if os.environ.get('DOTS_REPORT_IMAGERY', '1') == '0':
        return None
    import requests
    for u in [u for u in (urls or []) if u]:
        try:
            r = requests.get(u, timeout=timeout, headers={'User-Agent': 'DOTS-Campo'})
            if r.ok and (r.content[:8] == b'\x89PNG\r\n\x1a\n' or r.content[:3] == b'\xff\xd8\xff') and len(r.content) > 1500:
                return r.content
        except Exception:
            continue
    return None


def fetch_images(maps):
    jobs = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for k, m in (maps or {}).items():
            jobs[(k, 'main')] = pool.submit(_image, m.get('layers'))
            if m.get('overlay'):
                jobs[(k, 'overlay')] = pool.submit(_image, [m['overlay']])
            if m.get('base'):
                jobs[(k, 'base')] = pool.submit(_image, [m['base']])
        return {key: f.result() for key, f in jobs.items()}


def _ref_row(s):
    i = s.get('ina') or {}
    fc = (i.get('forecast') or [])[-1:] or [None]
    fc = fc[0]
    lvl = s.get('danger') or s.get('peak_danger')
    rec = s.get('height_record')
    th = s.get('thresholds') or {}
    def m2(v):
        return '—' if v is None else num(v, 2)
    return {'place': s['place'], 'h': m2(i.get('height')), 'h_date': dm(i.get('date')) if i.get('date') else '',
            'd7': sign(i.get('change_7d'), 2) if i.get('change_7d') is not None else '—',
            'low': m2(i.get('low')), 'alert': m2(i.get('alert')), 'evac': m2(i.get('evac')),
            'to_alert': ('superado' if i.get('to_alert') is not None and i['to_alert'] <= 0 else
                         m2(i.get('to_alert')) + (f" · ~{i['days_to_alert']} d" if i.get('days_to_alert') else '')),
            'fc': (f"{num(fc['central'], 2)} · {dm(fc['date'])}") if fc else '—',
            'record': (f"{num(rec['value'], 2)} m · {my(rec['date'])}") if rec else ((f"{num(th['max'])} m³/s · {my(th.get('max_date'))}") if th.get('max') else 'en cálculo'),
            'q': (f"{num(s.get('discharge'))} · {num(s.get('ratio'), 1)}×" if s.get('ratio') is not None else num(s.get('discharge'))) if s.get('status') == 'recibido' else '—',
            'level': lvl or '—', 'tone': TONE.get({'Evacuación': 'Peligro'}.get(lvl, lvl) or '', 'idle')}


def build_data(d, images=None, today=None):
    today = today or date.today()
    images = images or {}
    nino, hw, rv, dams, alerts = d.get('nino') or {}, d.get('headwaters') or {}, d.get('rivers') or {}, d.get('dams') or {}, d.get('alerts') or []
    active = [a for a in alerts if a.get('level') not in (None, 'Normal')]
    worst = active[0]['level'] if active else 'Normal'
    # resumen en tres líneas
    lines = []
    if nino.get('phase'):
        n34 = next((r for r in nino.get('regions', []) if r['id'] == 'nino34'), {})
        n12 = next((r for r in nino.get('regions', []) if r['id'] == 'nino12'), {})
        lines.append(f"El Pacífico sigue en {nino['phase'].lower()}: Niño 3.4 en {sign(n34.get('anom'))} °C y Niño costero en {sign(n12.get('anom'))} °C (semana del {dm(nino.get('week'))}).")
    if active:
        a = active[0]
        win = next((x['window'] for x in a.get('arrivals') or [] if x.get('window')), None)
        lines.append(f"{a['level']} por lluvia en {a['name']}: {num(a.get('median_mm'))} mm esperados en 15 días"
                     + (f"; repunte en {a['arrivals'][0]['place']} entre el {dm(win[0])} y el {dm(win[1])}." if win else '.'))
        if len(active) > 1:
            lines.append('Otras cuencas con aviso: ' + ', '.join(f"{x['name']} ({x['level'].lower()})" for x in active[1:5]) + '.')
    else:
        lines.append('Sin alertas por lluvia en las cabeceras para los próximos 15 días.')
    high = [s for s in rv.get('stations') or [] if (s.get('ina') or {}).get('level') in ('Atención', 'Alerta', 'Evacuación')]
    if high and len(lines) < 3:
        lines.append('Puertos cerca o sobre el nivel de alerta: ' + ', '.join(f"{s['place']} {num((s.get('ina') or {}).get('height'), 2)} m ({(s.get('ina') or {}).get('level', '').lower()})" for s in high[:4]) + '.')

    def img(key, part='main'):
        b = images.get((key, part))
        return list(b) if b else None

    maps = d.get('maps') or {}
    pics = []
    for k in ('sst', 'zone', 'rain'):
        m = maps.get(k)
        if not m:
            continue
        main = img(k)
        if not main and not img(k, 'base'):
            continue
        pics.append({'key': k, 'title': m['title'], 'date': dm(m.get('date')) + '/' + str(m.get('date', ''))[:4], 'caption': m['caption'],
                     'image': main, 'overlay': img(k, 'overlay'), 'base': img(k, 'base')})

    groups = []
    lv = {a['basin']: a['level'] for a in alerts}
    for g in ['Iguazú', 'Uruguay', 'Paraná', 'Paraguay', 'Bermejo y Pilcomayo']:
        rows = [b for b in hw.get('basins') or [] if b.get('group') == g]
        if rows:
            groups.append({'name': g, 'rows': [{'name': b['name'], 'where': b['where'],
                                                'mm': num(b.get('median_mm')) if b.get('status') == 'recibido' else '—',
                                                'range': f"{num(b.get('p10_mm'))}–{num(b.get('p90_mm'))}" if b.get('status') == 'recibido' else '—',
                                                'normal': f"{num(b.get('ratio'), 1)}×" if b.get('ratio') is not None else '—',
                                                'p100': f"{num(b.get('p_ge100'))} %" if b.get('p_ge100') is not None else '—',
                                                'level': lv.get(b['id']) or 'Normal', 'tone': TONE.get(lv.get(b['id']) or 'Normal')} for b in rows]})

    return {
        'title': 'DOTS · Informe de la Cuenca del Plata',
        'generated': f'{today.day} de {MONTHS[today.month - 1]} de {today.year}',
        'worst': worst, 'worst_tone': TONE.get(worst, 'ok'), 'summary': lines[:3],
        'active_count': len(active),
        'nino': {'week': dm(nino.get('week')), 'phase': nino.get('phase') or '—', 'coastal': nino.get('coastal') or '—',
                 'rows': [{'name': r['name'], 'sst': num(r.get('sst'), 1), 'anom': sign(r.get('anom')), 'phase': r.get('phase') or '—',
                           'change': sign(r.get('change_4w')) if r.get('change_4w') is not None else '—'} for r in nino.get('regions') or []],
                 'series34': nino.get('series', {}).get('nino34') or [], 'series12': nino.get('series', {}).get('nino12') or [],
                 'weeks': [dm(w) for w in nino.get('series', {}).get('weeks') or []]} if nino else None,
        'alerts': [{'name': a['name'], 'where': a['where'], 'level': a['level'], 'tone': TONE.get(a['level']),
                    'rain': (f"{num(a.get('median_mm'))} mm en 15 días" + (f" · lluvia fuerte del {dm(a.get('rain_from'))} al {dm(a.get('rain_to'))}" if a.get('rain_from') else '')),
                    'why': a.get('why') or [], 'actions': a.get('actions') or [],
                    'prediction': pred_text(a.get('prediction')), 'basis': pred_basis(a.get('prediction')),
                    'arrivals': [{'place': x['place'], 'window': f"{dm(x['window'][0])} al {dm(x['window'][1])}" if x.get('window') else '—'} for x in a.get('arrivals') or []]}
                   for a in active],
        'calm': [a['name'] for a in alerts if a.get('level') == 'Normal'],
        'pictures': pics,
        'groups': groups, 'models': hw.get('models') or 'ECMWF + GFS',
        'dams': [{'name': x['name'], 'river': x['river'], 'out': num(x.get('outflow')), 'in': num(x.get('inflow')),
                  'change': f"{sign(x.get('change_7d_pct'), 0)} %" if x.get('change_7d_pct') is not None else '—',
                  'ratio': f"{num(x.get('ratio'), 1)}×" if x.get('ratio') is not None else '—', 'level': x.get('level') or '—',
                  'date': dm(x.get('date'))} for x in dams.get('dams') or [] if x.get('status') == 'recibido'],
        'rivers': [{'name': rn, 'rows': [_ref_row(s) for s in rv.get('stations') or [] if s.get('river') == rn]}
                   for rn in ['Iguazú', 'Paraná', 'Paraguay', 'Bermejo', 'Uruguay'] if any(s.get('river') == rn for s in rv.get('stations') or [])],
        'ina_issued': dm(rv.get('ina_forecast_issued')),
        'travel': [{'name': ch['name'], 'rows': [{'place': r['place'], 'days': ('cabecera' if i == 0 else f"+{num(r['days_from_head'])} días" if r.get('days_from_head') is not None else 'en cálculo'),
                                                 'arrival': dm(r.get('arrival')) if r.get('arrival') else '—'} for i, r in enumerate(ch['rows'])]}
                   for ch in rv.get('travel') or []],
        'actions': rv.get('actions') or cc.ACTIONS,
        'official': [['Argentina', 'INA · Sistema de Alerta (ina.gob.ar/alerta) · Prefectura Naval: alturas por puerto con niveles de alerta y evacuación'],
                     ['Brasil', 'ANA · Sala de Situação Iguaçu-Uruguai · SGB · alertas SACE · ONS · caudales de represas (datos abiertos)'],
                     ['Paraguay', 'DMH · Dirección de Meteorología e Hidrología: niveles del río Paraguay'],
                     ['Bolivia', 'SENAMHI · pronóstico hidrológico del Pilcomayo y el Bermejo'],
                     ['Uruguay', 'INUMET · CTM Salto Grande: caudales y operación de la represa'],
                     ['Regional', 'CIC Plata · GloFAS (Copernicus) · Hydroweb (CNES) y SWOT (NASA-CNES): altura de ríos por satélite']],
        'sources': 'NOAA CPC (Niño semanal, OISST) · ECMWF IFS y NOAA GFS por conjunto vía Open-Meteo · Copernicus GloFAS vía Open-Meteo · '
                   'ONS Brasil (CC-BY 4.0) · NASA GIBS: GHRSST MUR, VIIRS y GPM IMERG · NASA POWER (normales de lluvia).',
        'errors': d.get('errors') or {},
    }


def pdf(d, today=None):
    import typst
    images = fetch_images(d.get('maps'))
    data = json.dumps(build_data(d, images, today), ensure_ascii=False, default=str)
    out = typst.compile(TEMPLATE, root=BASE, font_paths=[FONTS], ignore_system_fonts=True, sys_inputs={'data': data})
    if out[:5] != b'%PDF-':
        raise RuntimeError('Typst no generó el PDF')
    return out


# ───────────────────────────── informe de una localidad ─────────────────────────────
LOCAL_TEMPLATE = os.path.join(BASE, 'localidad.typ')
TONE_H = {'Normal': 'ok', 'Atención': 'warn', 'Alerta': 'alert', 'Evacuación': 'risk', 'Peligro': 'risk'}
PHONES = {'Argentina': [['103', 'Defensa Civil'], ['106', 'Prefectura Naval'], ['911', 'Emergencias'], ['100', 'Bomberos'], ['107', 'SAME']],
          'Paraguay': [['911', 'Emergencias']], 'Uruguay': [['911', 'Emergencias']]}


def _country(sid):
    return 'Paraguay' if sid in ('paraguay-bahianegra', 'paraguay-concepcion') else 'Uruguay' if sid == 'uruguay-fraybentos' else 'Argentina'


def _graph():
    """Tramos río abajo (u → dn) de todas las cadenas, con el desfase medio de 20 años cuando es firme."""
    lags = {k: v for k, v in ((cc.load_normals().get('lags')) or {}).items() if (v.get('corr') or 0) >= 0.3}
    edges = {}
    for ch in cc.CHAINS:
        for u, dn in zip(ch['stations'], ch['stations'][1:]):
            edges.setdefault(u, set()).add(dn)
    return edges, lags


def downstream_days(src, edges=None, lags=None):
    """{localidad: días desde src} para todo lo que está río abajo de src (None si falta algún tramo)."""
    if edges is None:
        edges, lags = _graph()
    out, stack = {src: 0.0}, [src]
    while stack:
        u = stack.pop()
        for dn in edges.get(u, ()):
            if dn in out:
                continue
            lg = (lags or {}).get(f'{u}>{dn}')
            out[dn] = (out[u] + lg['days']) if (lg and out[u] is not None) else None
            stack.append(dn)
    return out


def _trend_txt(t, short=False):
    if t is None:
        return '—'
    if abs(t) <= 0.005:
        return 'estable'
    return f"{'sube' if t > 0 else 'baja'} {num(abs(t) * 100)} cm{'/día' if short else ' por día'}"


def _days_txt(x):
    return 'en cálculo' if x is None else 'el mismo día' if x < 0.5 else f'~{num(x)} días'


def _litoral_nino(phase):
    p = (phase or '').lower()
    if 'niño' in p:
        return ('Con El Niño, la primavera y el verano suelen traer más lluvia de lo normal en el sur de Brasil, el Litoral y el NEA: '
                'aumenta la chance de crecidas en el Paraná, el Iguazú y el Uruguay.')
    if 'niña' in p:
        return 'Con La Niña suele llover menos de lo normal en la región: las bajantes son más probables que las crecidas.'
    return 'Pacífico neutral: no hay una señal climática fuerte que empuje la lluvia de la región para arriba ni para abajo.'


def local_data(d, sid, today=None):
    """Informe de una localidad: altura y niveles, tendencia y pronóstico, de dónde viene el agua (cabeceras, represas y
    río arriba), adónde va (río abajo), caudal contra la historia, El Niño, qué hacer y fuentes."""
    today = today or date.today()
    rv = d.get('rivers') or {}
    st = {s['id']: s for s in rv.get('stations') or []}
    s = st.get(sid)
    if not s:
        raise ValueError('Localidad desconocida')
    i = s.get('ina') or {}
    lvl = i.get('level') or s.get('danger') or 'Sin dato'
    act_key = {'Evacuación': 'Peligro'}.get(lvl, lvl)
    actions = (rv.get('actions') or cc.ACTIONS).get(act_key) or cc.ACTIONS['Normal']
    edges, lags = _graph()
    norm_st = (cc.load_normals().get('stations') or {}).get(sid) or {}

    # ── crecida en camino (alertas activas que llegan acá)
    arrivals = []
    for a in d.get('alerts') or []:
        if a.get('level') in (None, 'Normal'):
            continue
        for x in a.get('arrivals') or []:
            if x.get('place') == s['place'] and x.get('window'):
                arrivals.append({'basin': a['name'], 'level': a['level'], 'tone': TONE_H.get(a['level'], 'warn'),
                                 'window': f"{dm(x['window'][0])} al {dm(x['window'][1])}", 'mm': num(a.get('median_mm')),
                                 'why': '; '.join(a.get('why') or []),
                                 'prediction': pred_text(a.get('prediction')) if (a.get('prediction') or {}).get('place') == s['place'] else ''})

    # ── de dónde viene el agua: todas las cabeceras que drenan hasta esta localidad
    alert_lv = {a['basin']: a for a in d.get('alerts') or []}
    hw = {b['id']: b for b in (d.get('headwaters') or {}).get('basins') or []}
    basins = []
    for cfg in cc.BASINS:
        reach = downstream_days(cfg['outlet'], edges, lags)
        if sid not in reach:
            continue
        b = hw.get(cfg['id']) or {}
        lag = reach[sid]
        lo, hi = cfg['response']
        lv = (alert_lv.get(cfg['id']) or {}).get('level') or (cc.rain_level(b)[0] if b else None) or ('Normal' if b.get('status') == 'recibido' else '—')
        start = b.get('rain_center') or b.get('rain_from')
        win = (f"{dm(cc._add_days(start, lo + lag))} al {dm(cc._add_days(start, hi + lag))}" if (start and lag is not None) else '')
        basins.append({'name': cfg['name'], 'group': cfg['group'], 'where': cfg['where'],
                       'travel': (f"{num(lo + lag)}–{num(hi + lag)} días" if lag is not None else f"{num(lo)}–{num(hi)} días a {(st.get(cfg['outlet']) or {}).get('place', '')} + tramo en cálculo"),
                       'lo': lo + (lag or 0),
                       'mm': num(b.get('median_mm')) if b.get('status') == 'recibido' else '—',
                       'range': f"{num(b.get('p10_mm'))}–{num(b.get('p90_mm'))}" if b.get('status') == 'recibido' else '—',
                       'ratio': f"{num(b.get('ratio'), 1)}×" if b.get('ratio') is not None else '—', 'ratio_v': b.get('ratio'),
                       'p100': f"{num(b.get('p_ge100'))} %" if b.get('p_ge100') is not None else '—',
                       'heavy': (f"{dm(b['rain_from'])} al {dm(b['rain_to'])}" if b.get('rain_from') else ''),
                       'window': win, 'level': lv, 'tone': TONE_H.get(lv, 'idle'), 'median': b.get('median_mm'), 'known': lag is not None})
    basins.sort(key=lambda x: (not x['known'], x['lo']))

    # ── represas río arriba (ONS, medido)
    dams = []
    for x in (d.get('dams') or {}).get('dams') or []:
        if x.get('status') != 'recibido' or not x.get('outlet'):
            continue
        reach = downstream_days(x['outlet'], edges, lags)
        if sid in reach:
            dams.append({'name': x['name'], 'river': x['river'], 'out': num(x.get('outflow')), 'in': num(x.get('inflow')),
                         'change': f"{sign(x.get('change_7d_pct'), 0)} %" if x.get('change_7d_pct') is not None else '—',
                         'ratio': f"{num(x.get('ratio'), 1)}×" if x.get('ratio') is not None else '—', 'level': x.get('level') or '—',
                         'date': dm(x.get('date')), 'note': x.get('note') or '', 'days': _days_txt(reach[sid])})

    # ── río arriba y río abajo, con los días que tarda el agua
    def row(oid, days):
        o = st.get(oid) or {}
        oi = o.get('ina') or {}
        lv = oi.get('level') or o.get('danger') or '—'
        return {'place': o.get('place') or oid, 'river': o.get('river') or '', 'h': m2(oi.get('height')),
                'pct': f"{num(100 * oi['height'] / oi['alert'])} %" if oi.get('height') is not None and oi.get('alert') else '—',
                'level': lv, 'tone': TONE_H.get(lv, 'idle'), 'trend': _trend_txt(oi.get('trend_m_day'), True),
                'q': (f"{num(o.get('ratio'), 1)}×" if o.get('ratio') is not None else '—'), 'days': _days_txt(days)}
    ups = []
    for u in st:
        if u == sid:
            continue
        reach = downstream_days(u, edges, lags)
        if sid in reach:
            ups.append((reach[sid], u))
    ups.sort(key=lambda t: (t[0] is None, t[0] or 0))
    upstream = [row(u, dd) for dd, u in reversed(ups[:8])]
    down = sorted(((v, k) for k, v in downstream_days(sid, edges, lags).items() if k != sid), key=lambda t: (t[0] is None, t[0] or 0))
    downstream = [row(k, v) for v, k in down[:5]]

    # ── caudal contra la historia (GloFAS)
    th = s.get('thresholds') or {}
    flow = None
    if s.get('status') == 'recibido':
        flow = {'now': num(s.get('discharge')), 'normal': num(s.get('normal')), 'ratio': f"{num(s.get('ratio'), 1)}×" if s.get('ratio') is not None else '—',
                'pct': f"percentil {s['percentile']}" if s.get('percentile') is not None else '—', 'level': s.get('level') or '—',
                'change': f"{sign(s.get('change_7d_pct'), 0)} %" if s.get('change_7d_pct') is not None else '—',
                'peak': (f"{num(s.get('peak'))} m³/s el {dm(s.get('peak_date'))}" + (f" ({s['peak_level']})" if s.get('peak_level') else '')) if s.get('peak') else '—',
                'q2': num(th.get('q2')), 'q5': num(th.get('q5')), 'q20': num(th.get('q20')),
                'max': (f"{num(th['max'])} m³/s · {my(th.get('max_date'))}") if th.get('max') else '—',
                'danger': s.get('danger') or '—', 'peak_danger': s.get('peak_danger') or '—'}

    # ── El Niño
    nino = d.get('nino') or {}
    nino_out = None
    if nino.get('phase'):
        n34 = next((r for r in nino.get('regions', []) if r['id'] == 'nino34'), {})
        n12 = next((r for r in nino.get('regions', []) if r['id'] == 'nino12'), {})
        nino_out = {'week': dm(nino.get('week')), 'phase': nino['phase'], 'coastal': nino.get('coastal') or '—',
                    'n34': sign(n34.get('anom')), 'n12': sign(n12.get('anom')), 'effect': _litoral_nino(nino['phase'])}

    # ── resumen en palabras
    summary = []
    if i.get('height') is not None:
        line = f"El río {s['river']} en {s['place']} marca {m2(i['height'])} ({dm(i.get('date'))})"
        if i.get('alert') is not None:
            line += (f", {m2(-i['to_alert'])} por encima del nivel de alerta ({m2(i['alert'])})" if i['to_alert'] <= 0
                     else f", {m2(i['to_alert'])} por debajo del nivel de alerta ({m2(i['alert'])})")
        summary.append(line + f". Nivel: {lvl.lower()}.")
        t2 = []
        if i.get('trend_m_day') is not None:
            t2.append(f"En la última semana {_trend_txt(i['trend_m_day'])}" + (f"; a ese ritmo llegaría a la alerta en ~{i['days_to_alert']} días" if i.get('days_to_alert') else ''))
        fc = i.get('forecast') or []
        if fc:
            t2.append(f"el INA pronostica {m2(fc[-1]['central'])} al {dm(fc[-1]['date'])}")
        if t2:
            summary.append('; '.join(t2) + '.')
    elif s.get('discharge') is not None:
        summary.append(f"Sin escala oficial en {s['place']}: el caudal estimado es {num(s['discharge'])} m³/s" + (f", {num(s['ratio'], 1)} veces lo normal para la fecha." if s.get('ratio') is not None else '.'))
    wet = [b for b in basins if (b.get('ratio_v') or 0) >= 1.3]
    if basins:
        if wet:
            top = max(wet, key=lambda b: b['ratio_v'])
            summary.append(f"De las {len(basins)} cabeceras que aportan agua hasta acá, {len(wet)} esperan más lluvia que lo normal en 15 días; la más cargada es {top['name']} ({top['mm']} mm, {top['ratio']} lo normal), " + (f"que tarda {top['travel']} en llegar." if top['known'] else "cuyo tiempo de llegada hasta acá todavía está en cálculo."))
        else:
            summary.append(f"Ninguna de las {len(basins)} cabeceras que aportan agua hasta acá espera lluvia muy por encima de lo normal en los próximos 15 días.")
    if arrivals:
        summary.append(f"Hay {len(arrivals)} {'aviso' if len(arrivals) == 1 else 'avisos'} de crecida en camino: " + '; '.join(f"{a['basin']}, del {a['window']}" for a in arrivals[:3]) + '.')
    if flow and s.get('ratio') is not None:
        summary.append(f"El caudal estimado (GloFAS) es {flow['now']} m³/s, {flow['ratio']} lo normal para la época ({flow['level']}).")
    if nino_out:
        summary.append(f"Pacífico en {nino_out['phase'].lower()} (Niño 3.4 {nino_out['n34']} °C). {nino_out['effect']}")

    rec = s.get('height_record') or norm_st.get('height_record') or {}
    fc = i.get('forecast') or []
    return {
        'title': f"DOTS · Alerta de crecidas · {s['place']}", 'generated': f'{today.day} de {MONTHS[today.month - 1]} de {today.year}',
        'place': s['place'], 'river': s['river'], 'gauge': i.get('gauge') or '', 'level': lvl, 'tone': TONE_H.get(lvl, 'idle'),
        'summary': summary,
        'has_h': i.get('height') is not None,
        'h': i.get('height'), 'h_txt': m2(i.get('height')), 'date': dm(i.get('date')), 'alert': i.get('alert'), 'evac': i.get('evac'), 'low': i.get('low'),
        'alert_txt': m2(i.get('alert')), 'evac_txt': m2(i.get('evac')), 'low_txt': m2(i.get('low')),
        'to_alert': ('superado' if i.get('to_alert') is not None and i['to_alert'] <= 0 else m2(i.get('to_alert'))),
        'change7': (sign(i.get('change_7d'), 2) + ' m') if i.get('change_7d') is not None else '—',
        'pct_alert': f"{num(100 * i['height'] / i['alert'])} %" if i.get('height') is not None and i.get('alert') else '—',
        'trend': (f"{'sube' if i['trend_m_day'] > 0.005 else 'baja' if i['trend_m_day'] < -0.005 else 'estable'} {num(abs(i['trend_m_day']) * 100)} cm por día") if i.get('trend_m_day') is not None else '—',
        'days_alert': (f"a este ritmo llegaría a la alerta en ~{i['days_to_alert']} días" if i.get('days_to_alert') else ''),
        'days_evac': (f"y a la evacuación en ~{i['days_to_evac']} días" if i.get('days_to_evac') else ''),
        'series': [{'d': dm(x['date']), 'v': x['h']} for x in i.get('series') or [] if x.get('h') is not None],
        'forecast': [{'d': dm(f['date']), 'c': f['central'], 'lo': f['min'], 'hi': f['max']} for f in fc],
        'fc_rows': [{'d': dm(f['date']), 'c': m2(f['central']), 'r': f"{num(f['min'], 2)}–{num(f['max'], 2)} m",
                     'lv': cc.height_level(f['central'], {'alert': i.get('alert'), 'evac': i.get('evac')}, s.get('river')) or '—'} for f in fc],
        'fc_txt': (f"{num(fc[-1]['central'], 2)} m al {dm(fc[-1]['date'])} (entre {num(fc[-1]['min'], 2)} y {num(fc[-1]['max'], 2)} m)") if fc else '',
        'fc_issued': dm(rv.get('ina_forecast_issued')),
        'record': (f"{m2(rec['value'])} en {my(rec['date'])}") if rec.get('value') else '',
        'discharge': (f"{num(s.get('discharge'))} m³/s" + (f" · {num(s.get('ratio'), 1)} veces lo normal para la fecha" if s.get('ratio') is not None else '')) if s.get('discharge') is not None else '',
        'arrivals': arrivals, 'basins': basins, 'dams': dams, 'upstream': upstream, 'downstream': downstream,
        'flow': flow, 'nino': nino_out, 'actions': actions,
        'country': _country(sid), 'phones': PHONES[_country(sid)],
        'lags_period': (cc.load_normals().get('lags_period') or '20 años'),
        'picture': None,
        'url': 'observatorio-agro.vercel.app/alertas',
    }


def local_picture(s, today=None):
    """Imagen VIIRS color real del día anterior alrededor de la localidad (NASA GIBS). None si no hay."""
    today = today or date.today()
    day = (today - timedelta(days=1)).isoformat()
    bbox = (round(s['lon'] - 0.9, 2), round(s['lat'] - 0.6, 2), round(s['lon'] + 0.9, 2), round(s['lat'] + 0.6, 2))
    main = _image([cc.gibs_url('VIIRS_SNPP_CorrectedReflectance_TrueColor', bbox, day, 900, 600, 'image/jpeg'),
                   cc.gibs_url('MODIS_Terra_CorrectedReflectance_TrueColor', bbox, day, 900, 600, 'image/jpeg')])
    if not main:
        return None
    return {'image': list(main), 'date': dm(day), 'caption': 'VIIRS (Suomi NPP) color real, NASA GIBS, ~1,8 × 1,2 grados alrededor de la localidad. '
                                                            'Con cielo despejado se ve el cauce y el agua fuera de él; con nubes, sólo la cobertura nubosa.'}


def local_pdf(d, sid, today=None):
    import typst
    ld = local_data(d, sid, today)
    s = next((x for x in cc.STATIONS if x['id'] == sid), None)
    try:
        ld['picture'] = local_picture(s, today) if s else None
    except Exception:
        ld['picture'] = None
    data = json.dumps(ld, ensure_ascii=False, default=str)
    out = typst.compile(LOCAL_TEMPLATE, root=BASE, font_paths=[FONTS], ignore_system_fonts=True, sys_inputs={'data': data})
    if out[:5] != b'%PDF-':
        raise RuntimeError('Typst no generó el PDF')
    return out
