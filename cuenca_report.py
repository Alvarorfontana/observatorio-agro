"""Informe PDF de la Cuenca del Plata (Typst): El Niño, alertas por lluvia en cabeceras, imágenes, ríos y represas.

Estructura fija: 1 portada y resumen · 2 El Niño · 3 alertas por cuenca · 4 imágenes de la zona ·
5 lluvia por subcuenca · 6 represas y ríos · 7 tiempos de traslado · 8 fuentes oficiales y alcances.
"""
import json, os
from concurrent.futures import ThreadPoolExecutor
from datetime import date

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
            'to_alert': ('superado' if i.get('to_alert') is not None and i['to_alert'] <= 0 else m2(i.get('to_alert'))),
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
