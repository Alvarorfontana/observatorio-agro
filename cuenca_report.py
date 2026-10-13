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
        lines.append(f"{a['level']} por lluvia en {a['name']}: {num(a.get('median_mm'))} mm esperados en {(d.get('headwaters') or {}).get('days', 15)} días"
                     + (f"; repunte en {a['arrivals'][0]['place']} entre el {dm(win[0])} y el {dm(win[1])}." if win else '.'))
        if len(active) > 1:
            lines.append('Otras cuencas con aviso: ' + ', '.join(f"{x['name']} ({x['level'].lower()})" for x in active[1:5]) + '.')
    else:
        lines.append(f"Sin alertas por lluvia en las cabeceras para los próximos {(d.get('headwaters') or {}).get('days', 15)} días.")
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
                    'rain': (f"{num(a.get('median_mm'))} mm en {hw.get('days', 15)} días" + (f" · lluvia fuerte del {dm(a.get('rain_from'))} al {dm(a.get('rain_to'))}" if a.get('rain_from') else '')),
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
    H = (d.get('headwaters') or {}).get('days', 15)
    wet = [b for b in basins if (b.get('ratio_v') or 0) >= 1.3]
    if basins:
        if wet:
            top = max(wet, key=lambda b: (b['known'], b['ratio_v']))
            summary.append(f"De las {len(basins)} cabeceras que aportan agua hasta acá, {len(wet)} esperan más lluvia que lo normal en los próximos {H} días; la más cargada es {top['name']} ({top['mm']} mm, {top['ratio']} lo normal), " + (f"que tarda {top['travel']} en llegar." if top['known'] else "cuyo tiempo de llegada hasta acá todavía está en cálculo."))
        else:
            summary.append(f"Ninguna de las {len(basins)} cabeceras que aportan agua hasta acá espera lluvia muy por encima de lo normal en los próximos {H} días.")
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
        'rain_days': (d.get('headwaters') or {}).get('days', 15),
        'arrivals': arrivals, 'basins': basins, 'dams': dams, 'upstream': upstream, 'downstream': downstream,
        'flow': flow, 'nino': nino_out, 'actions': actions,
        'country': _country(sid), 'phones': PHONES[_country(sid)],
        'lags_period': (cc.load_normals().get('lags_period') or '20 años'),
        'picture': None, 'flood': None,
        'url': 'observatorio-agro.vercel.app/alertas',
    }


# ───────────────────────────── foto satelital de la localidad ─────────────────────────────
# Cadena obligatoria, siempre lo más fresco posible:
#   1) óptico de alta resolución despejado de los últimos 10 días: Sentinel-2 (10 m) o Landsat 8/9 (30 m);
#   2) radar Sentinel-1 de los últimos 12 días (10 m, ve a través de las nubes; el agua se ve oscura);
#   3) VIIRS/MODIS del día menos nublado de los últimos 5 (250-375 m);
#   4) si nada responde, el informe lo dice. Todo abierto y sin clave.
S2_BOX = (0.16, 0.11)          # medio ancho en grados (lon, lat): ~33 × 24 km, se ve la ciudad, el cauce y la planicie
WIDE_BOX = (0.9, 0.6)          # ~180 × 130 km para VIIRS/MODIS
OPTICAL_DAYS, RADAR_DAYS, DAILY_DAYS = 10, 12, 5
S2_BAD = (0, 1, 3, 8, 9, 10)   # SCL: sin dato, saturado, sombra de nube, nube media, nube alta, cirro
DAILY = [('VIIRS_SNPP_CorrectedReflectance_TrueColor', 'VIIRS (Suomi NPP)'), ('VIIRS_NOAA20_CorrectedReflectance_TrueColor', 'VIIRS (NOAA-20)'),
         ('MODIS_Terra_CorrectedReflectance_TrueColor', 'MODIS (Terra)'), ('MODIS_Aqua_CorrectedReflectance_TrueColor', 'MODIS (Aqua)')]
BOX_TXT = '~33 × 24 km centrado en la localidad'


def _box(s, half):
    return (round(s['lon'] - half[0], 3), round(s['lat'] - half[1], 3), round(s['lon'] + half[0], 3), round(s['lat'] + half[1], 3))


def _box_poly(b):
    w, so, e, n = b
    return [[so, w], [so, e], [n, e], [n, w]]


def _pc_search(collection, feat, pts, today, days, query=None, min_cov=0.99):
    import vegetation as veg
    from datetime import datetime, time as dtime
    end = datetime.combine(today, dtime(23, 59)); start = end - timedelta(days=days)
    body = {'collections': [collection], 'intersects': feat['geometry'], 'limit': 20,
            'datetime': f'{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}',
            'sortby': [{'field': 'properties.datetime', 'direction': 'desc'}]}
    if query:
        body['query'] = query
    out = []
    for it in veg.c._post(veg.PC_STAC + '/search', body, timeout=25).json().get('features', []):
        cov = veg.footprint_coverage(it, pts)
        if cov >= min_cov:
            out.append(it | {'_cov': cov})
    return out


def _pc_png(collection, item_id, feat, params):
    """PNG recortado al recuadro, en lat/lon (EPSG:4326) para que la máscara de GFM calce exacta; si la API no acepta la
    reproyección, se pide en la proyección nativa."""
    import vegetation as veg
    base = {'collection': collection, 'item': item_id, 'max_size': 1024, **params}
    for extra in ({'dst_crs': 'epsg:4326'}, {}):
        r = veg.c.SESSION.post(f'{veg.PC_DATA}/item/feature.png', json=feat, timeout=40, params={**base, **extra})
        if r.ok and r.content[:8] == b'\x89PNG\r\n\x1a\n' and len(r.content) > 5000:
            return r.content
    return None


def _pic(png, day, today, sensor, clear, caption, bbox=None):
    return {'image': list(png), 'date': dm(day) + '/' + day[:4], 'sensor': sensor, 'clear': clear,
            'age': (today - date.fromisoformat(day)).days, 'caption': caption, 'bbox': bbox}


def optical_picture(s, today=None, days=OPTICAL_DAYS, tries=4):
    """La escena óptica despejada más reciente: Sentinel-2 (≥85 % sin nubes por máscara SCL) o Landsat 8/9 (<15 % de nubes)."""
    import vegetation as veg
    today = today or date.today()
    pts = _box_poly(_box(s, S2_BOX))
    feat = {'type': 'Feature', 'properties': {}, 'geometry': veg.geojson_polygon(pts)}
    cands = []
    try:
        cands += [('s2', it) for it in _pc_search('sentinel-2-l2a', feat, pts, today, days, {'eo:cloud_cover': {'lt': 95}})[:tries]]
    except Exception:
        pass
    try:
        cands += [('ls', it) for it in _pc_search('landsat-c2-l2', feat, pts, today, days,
                                                  {'eo:cloud_cover': {'lt': 15}, 'platform': {'in': ['landsat-8', 'landsat-9']}})[:2]]
    except Exception:
        pass
    cands.sort(key=lambda x: str(x[1]['properties'].get('datetime', '')), reverse=True)   # la más nueva primero
    clear_expr = 'where(' + '|'.join(f'(SCL=={v})' for v in S2_BAD) + ',0,1)'
    for kind, it in cands:
        day = str(it['properties'].get('datetime', ''))[:10]
        try:
            if kind == 's2':
                clear = float(veg._pc_stats(it['id'], feat, clear_expr).get('mean') or 0)
                if clear < 0.85:
                    continue
                png = _pc_png('sentinel-2-l2a', it['id'], feat, {'assets': 'visual', 'asset_bidx': 'visual|1,2,3', 'nodata': 0})
                if png:
                    return _pic(png, day, today, 'Sentinel-2 (ESA · Copernicus), 10 m', round(100 * clear),
                                f'Sentinel-2 L2A en color real, {round(100 * clear)} % del recuadro sin nubes (máscara SCL). Recuadro de {BOX_TXT}.', _box(s, S2_BOX))
            else:
                png = _pc_png('landsat-c2-l2', it['id'], feat, {'assets': ['red', 'green', 'blue'], 'nodata': 0,
                                                               'color_formula': 'gamma RGB 2.7, saturation 1.5, sigmoidal RGB 15 0.55'})
                if png:
                    clear = round(100 - float(it['properties'].get('eo:cloud_cover') or 0))
                    sat = it['properties'].get('platform', 'landsat').replace('landsat-', 'Landsat ')
                    return _pic(png, day, today, f'{sat} (USGS · NASA), 30 m', clear,
                                f'{sat} Collection 2 en color real; nubosidad de la escena {100 - clear} %. Recuadro de {BOX_TXT}.', _box(s, S2_BOX))
        except Exception:
            continue
    return None


def _grid_cov(items, w, so, e, n, k=6):
    """Fracción del recuadro cubierta por la unión de las huellas (grilla de k × k puntos)."""
    import vegetation as veg
    polys = []
    for it in items:
        g = it.get('geometry') or {}
        polys += [g['coordinates']] if g.get('type') == 'Polygon' else (g.get('coordinates') or []) if g.get('type') == 'MultiPolygon' else []
    if not polys:
        return 1.0
    pts = [(so + (n - so) * (i + .5) / k, w + (e - w) * (j + .5) / k) for i in range(k) for j in range(k)]
    return sum(1 for lat, lon in pts if any(veg._in_ring(lon, lat, p[0]) for p in polys if p)) / len(pts)


def radar_picture(s, today=None, days=RADAR_DAYS):
    """Sentinel-1 RTC (VV, en dB) de la pasada más reciente que cubra al menos el 60 % del recuadro, uniendo los tramos
    de esa misma pasada. No depende de las nubes: el agua quieta y lo anegado se ven negros."""
    import vegetation as veg, pngmini
    today = today or date.today()
    box = _box(s, S2_BOX); pts = _box_poly(box)
    feat = {'type': 'Feature', 'properties': {}, 'geometry': veg.geojson_polygon(pts)}
    items = _pc_search('sentinel-1-rtc', feat, pts, today, days, min_cov=0.1)
    by_day = {}
    for it in items:
        by_day.setdefault(str(it['properties'].get('datetime', ''))[:10], []).append(it)
    for day in sorted(by_day, reverse=True):
        group = sorted(by_day[day], key=lambda it: -it['_cov'])[:3]
        cov = _grid_cov(group, *box)
        if cov < 0.6:
            continue
        params = {'expression': '10*log10(vv)', 'asset_as_band': 'true', 'rescale': '-24,0', 'nodata': 0, 'max_size': 800}
        pngs = [p for p in (_pc_png('sentinel-1-rtc', it['id'], feat, params) for it in group) if p]
        if not pngs:
            continue
        png = pngs[0]
        if len(pngs) > 1:
            try:
                dec = [pngmini.decode(p) for p in pngs]
                w, h = dec[0][0], dec[0][1]
                rows = [list(r) for r in dec[0][2]]
                for (w2, h2, r2) in dec[1:]:
                    if (w2, h2) != (w, h):
                        continue
                    for y in range(h):
                        row, other = rows[y], r2[y]
                        for x in range(w):
                            if row[x][3] == 0 and other[x][3]:
                                row[x] = other[x]
                png = pngmini.encode_rgba(w, h, rows)
            except Exception:
                png = pngs[0]
        return _pic(png, day, today, 'Sentinel-1 radar (ESA · Copernicus), 10 m', 100,
                    f'Radar Sentinel-1 (VV, corregido por terreno): atraviesa las nubes. El agua quieta y las zonas anegadas se ven negras; '
                    f'ciudades y monte, claros. Se usó porque no hubo toma óptica despejada en los últimos {OPTICAL_DAYS} días. Recuadro de {BOX_TXT}'
                    + ('.' if cov >= 0.95 else f'; la pasada cubre el {round(100 * cov)} % del recuadro (el resto queda en blanco).'), box)
    return None


def cloud_fraction(png):
    """Fracción de píxeles blancos y poco saturados (nube) en una miniatura PNG color real. None si no se puede leer."""
    import pngmini
    try:
        w, h, rows = pngmini.decode(png)
    except Exception:
        return None
    px = [p for row in rows for p in row]
    data = [p for p in px if p[3] > 0 and max(p[:3]) > 8]   # descarta franjas sin dato
    if len(data) < 0.6 * len(px):
        return 1.0                                           # más de 40 % sin dato: como si estuviera tapado
    cloudy = sum(1 for r, g, b, _ in data if min(r, g, b) > 165 and max(r, g, b) - min(r, g, b) < 35)
    return cloudy / len(data)


def daily_picture(s, today=None, days=DAILY_DAYS):
    """VIIRS/MODIS del día menos nublado de los últimos `days`; se queda con el primero bajo 25 % de nubes."""
    today = today or date.today()
    box = _box(s, WIDE_BOX)
    best = None
    for start in range(0, days + 1, 2):                  # de a dos días (empieza por hoy), todos los sensores en paralelo
        jobs = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            for k in range(start, min(start + 2, days + 1)):
                day = (today - timedelta(days=k)).isoformat()
                for layer, name in DAILY:
                    jobs.append((day, (layer, name), pool.submit(_image, [cc.gibs_url(layer, box, day, 150, 100, 'image/png')])))
            got = [(day, name, f.result()) for day, name, f in jobs]
        for day, ln, thumb in got:
            if not thumb:
                continue
            cf = cloud_fraction(thumb)
            score = 1.0 if cf is None else cf
            if best is None or score < best[0] or (score == best[0] and day > best[1]):
                best = (score, day, ln)
        if best and best[0] < 0.25:
            break
    if not best:
        return None
    score, day, (layer, name) = best
    img = _image([cc.gibs_url(layer, box, day, 900, 600, 'image/jpeg')], timeout=20)
    if not img:
        return None
    pct = round(100 * (1 - score))
    note = ('' if score < 0.25 else f" Ningún día de los últimos {days} estuvo despejado: esta es la toma con menos nubes ({pct} % del recuadro visible).")
    return {'image': list(img), 'date': dm(day) + '/' + day[:4], 'sensor': f'{name}, 250-375 m', 'clear': pct, 'bbox': box,
            'age': (today - date.fromisoformat(day)).days,
            'caption': f"{name} en color real vía NASA GIBS, ~180 × 130 km alrededor de la localidad. Con cielo despejado se ve el cauce "
                       f"y el agua fuera de él." + note}


def local_picture(s, today=None):
    """Foto obligatoria: siempre devuelve un dict. Si no hay imagen, 'image' es None y 'missing' explica por qué."""
    if os.environ.get('DOTS_REPORT_IMAGERY', '1') == '0':
        return {'image': None, 'missing': 'Imágenes satelitales desactivadas en esta instalación.'}
    tried = []
    for fn, label in ((optical_picture, f'Sentinel-2 y Landsat ({OPTICAL_DAYS} días)'), (radar_picture, f'radar Sentinel-1 ({RADAR_DAYS} días)'),
                      (daily_picture, f'VIIRS/MODIS ({DAILY_DAYS} días)')):
        try:
            p = fn(s, today)
            if p:
                return p
            tried.append(f'{label}: sin toma despejada')
        except Exception as e:
            tried.append(f'{label}: {type(e).__name__}')
    return {'image': None, 'missing': 'No se pudo obtener imagen satelital al generar el informe (' + '; '.join(tried) + '). '
                                      'Volvé a descargarlo en unos minutos o consultá worldview.earthdata.nasa.gov.'}


def local_flood(s, picture=None, today=None, f=None):
    """Agua de crecida de Copernicus GFM en el recuadro local (~33 × 24 km). Si la foto es de otro recuadro, se pide la
    máscara para ese recuadro. Siempre devuelve un dict."""
    import gfm
    if os.environ.get('DOTS_REPORT_IMAGERY', '1') == '0':
        return {'ok': False, 'missing': 'Imágenes satelitales desactivadas en esta instalación.'}
    pic = picture or {}
    local = _box(s, S2_BOX)
    try:
        f = f or gfm.flood_at(local, today)
    except Exception as e:
        return {'ok': False, 'missing': f'Copernicus GFM no respondió al generar el informe ({type(e).__name__}). '
                                        f'Se puede consultar en global-flood.emergency.copernicus.eu.'}
    out = {'ok': True, 'missing': '', 'date': dm(f['date']) + '/' + f['date'][:4], 'age': f['age'], 'flood_km2': num(f['flood_km2'], 1),
           'flood_pct': num(f['flood_pct'], 1), 'water_km2': num(f['water_km2'], 1) if f['water_km2'] is not None else '—',
           'box_km2': num(f['box_km2']), 'has_flood': f['flood_km2'] >= 0.5, 'overlaid': False, 'mask': None}
    try:
        pb = tuple(pic['bbox']) if pic.get('image') and pic.get('bbox') else None
        out['mask'] = list(gfm.recolor(f['mask']) if (pb is None or pb == tuple(local)) else gfm.mask_for(f['layer'], pb, f['date']))
        out['overlaid'] = bool(pic.get('image'))
    except Exception:
        out['mask'] = None
    out['summary'] = ((f"Copernicus GFM detectó agua de crecida en {out['flood_km2']} km² alrededor de la localidad "
                       f"({out['flood_pct']} % del recuadro de {out['box_km2']} km², fuera del cauce normal), con el radar del {dm(f['date'])}.")
                      if out['has_flood'] else
                      f"Copernicus GFM no detectó agua fuera del cauce alrededor de la localidad en la última pasada de radar ({dm(f['date'])}).")
    return out


def local_pdf(d, sid, today=None):
    import typst
    ld = local_data(d, sid, today)
    s = next((x for x in cc.STATIONS if x['id'] == sid), None)
    # foto y GFM en paralelo: el informe tiene que entrar en los 60 s de Vercel
    import gfm
    with ThreadPoolExecutor(max_workers=2) as pool:
        jp = pool.submit(local_picture, s, today) if s else None
        jf = pool.submit(gfm.flood_at, _box(s, S2_BOX), today) if s and os.environ.get('DOTS_REPORT_IMAGERY', '1') != '0' else None
        try:
            ld['picture'] = jp.result(timeout=40) if jp else None
        except Exception as e:
            ld['picture'] = {'image': None, 'missing': f'No se pudo obtener imagen satelital ({type(e).__name__}).'}
        try:
            fres = jf.result(timeout=30) if jf else None
        except Exception:
            fres = None
    if not s:
        ld['flood'] = None
    elif jf and fres is None:
        ld['flood'] = {'ok': False, 'missing': 'Copernicus GFM no respondió a tiempo al generar el informe. Se puede consultar en global-flood.emergency.copernicus.eu.'}
    else:
        ld['flood'] = local_flood(s, ld['picture'], today, fres)
    if (ld['picture'] or {}).get('image'):
        import pngmini
        wh = pngmini.size(bytes(ld['picture']['image'])) or (3, 2)
        ld['picture']['ratio'] = round(wh[1] / wh[0], 4)
    if (ld['flood'] or {}).get('summary'):
        ld['summary'].insert(min(2, len(ld['summary'])), ld['flood']['summary'])
    data = json.dumps(ld, ensure_ascii=False, default=str)
    out = typst.compile(LOCAL_TEMPLATE, root=BASE, font_paths=[FONTS], ignore_system_fonts=True, sys_inputs={'data': data})
    if out[:5] != b'%PDF-':
        raise RuntimeError('Typst no generó el PDF')
    return out
