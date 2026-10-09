"""report_typst v2.4 — informe PDF con diseño DOTS usando Typst (https://typst.app, Apache-2.0).

Typst compila la plantilla report/dots.typ con los datos ya formateados (JSON en sys.inputs).
Fuentes: IBM Plex Sans / Mono (SIL OFL) incluidas en report/fonts, porque Vercel no trae fuentes.
Si el paquete `typst` no está instalado o la compilación falla, se usa el PDF de ReportLab
de agentic_engine para no dejar al usuario sin informe.
"""
import json, math, os
from datetime import datetime, timezone

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report')
TEMPLATE = os.path.join(BASE, 'dots.typ')
FONTS = os.path.join(BASE, 'fonts')
MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def num(v, d=1):
    """Formato argentino: coma decimal, punto de miles."""
    if v is None or v == '':
        return '—'
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if not math.isfinite(v):
        return '—'
    s = f'{v:,.{d}f}'
    return s.replace(',', '§').replace('.', ',').replace('§', '.')


def _f(v):
    try:
        v = float(v)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def shape(polygon):
    """[[lat,lon]] → puntos normalizados 0..1 conservando proporción (x este, y sur)."""
    if not polygon or len(polygon) < 3:
        return []
    lat0 = sum(p[0] for p in polygon) / len(polygon)
    k = math.cos(math.radians(lat0))
    xs = [p[1] * k for p in polygon]; ys = [-p[0] for p in polygon]
    w = max(xs) - min(xs); h = max(ys) - min(ys); span = max(w, h) or 1
    pad = 0.08
    ox = (1 - 2 * pad - w / span * (1 - 2 * pad)) / 2
    oy = (1 - 2 * pad - h / span * (1 - 2 * pad)) / 2
    return [[round(pad + ox + (x - min(xs)) / span * (1 - 2 * pad), 4),
             round(pad + oy + (y - min(ys)) / span * (1 - 2 * pad), 4)] for x, y in zip(xs, ys)]


def _metric(result, name):
    return next((m for m in result.get('metrics', []) if m.get('variable') == name), None)


def build_data(result, name='Lote DOTS', extras=None):
    extras = extras or {}
    lot = extras.get('lot') or {}
    ndvi = extras.get('ndvi') or {}
    indices = extras.get('indices') or {}
    tele = extras.get('telecon') or {}
    poly = result.get('polygon') or lot.get('vertices') or []
    lat, lon = result.get('point') or [None, None]
    gen = result.get('generated_at') or datetime.now(timezone.utc).isoformat()
    try:
        g = datetime.fromisoformat(gen.replace('Z', '+00:00'))
        generated = f'{g.day:02d} {MONTHS[g.month - 1]} {g.year} · {g:%H:%M} UTC'
    except ValueError:
        generated = gen[:16]

    # ── KPIs
    nl = ndvi.get('latest') or {}
    t = _metric(result, 'Temperatura'); thi = _metric(result, 'THI bovino')
    rain = _metric(result, 'Lluvia 7 días'); et = _metric(result, 'ET₀ 7 días')
    nmean = _f(nl.get('ndvi_mean'))
    thiv = _f(thi and thi.get('value'))
    bal = (_f(rain and rain.get('value')) or 0) - (_f(et and et.get('value')) or 0) if rain else None
    kpis = [
        {'label': 'NDVI del lote', 'value': num(nmean, 2) if nmean is not None else '—', 'unit': '',
         'hint': f"Sentinel-2 · {str(nl.get('datetime', ''))[:10]}" if nmean is not None else 'Sin cálculo en esta sesión',
         'tone': 'idle' if nmean is None else 'ok' if nmean >= 0.5 else 'warn' if nmean >= 0.2 else 'risk'},
        {'label': 'Temperatura', 'value': num(t and t.get('value')), 'unit': '°C', 'hint': 'Open-Meteo · ahora',
         'tone': 'idle' if not t else 'risk' if (_f(t.get('value')) or 0) >= 35 else 'ok'},
        {'label': 'THI bovino', 'value': num(thiv), 'unit': '', 'hint': (thi or {}).get('reading', 'sin dato'),
         'tone': 'idle' if thiv is None else 'ok' if thiv < 72 else 'warn' if thiv < 79 else 'risk'},
        {'label': 'Balance lluvia − ET₀', 'value': num(bal), 'unit': 'mm', 'hint': 'Próximos 7 días',
         'tone': 'idle' if bal is None else 'warn' if bal < -15 else 'ok'},
    ]

    # ── ficha del lote
    facts = []
    if lot.get('areaHa') is not None:
        facts.append(['Superficie', f"{num(lot['areaHa'])} ha"])
    if lot.get('perimeterKm') is not None:
        facts.append(['Perímetro', f"{num(lot['perimeterKm'], 2)} km"])
    if lot.get('compactness') is not None:
        c = lot['compactness']
        facts.append(['Compacidad', f"{num(c, 2)} · {'compacto' if c >= 0.6 else 'intermedio' if c >= 0.4 else 'alargado'}"])
    if lat is not None:
        facts.append(['Centro', f'{lat:.5f}, {lon:.5f}'])
    ftw = lot.get('ftw') or {}
    if ftw:
        facts.append(['Confianza del límite', f"{num(ftw.get('confidence'), 0)} / 100"])
        nb = ftw.get('neighborhood') or {}
        if nb:
            facts.append(['Agricultura en 2 km', f"{num(nb.get('coverPct'))} % · {nb.get('count', 0)} lotes"])
    facts.append(['Fuentes recibidas', str(result.get('confidence', {}).get('received_sources', '—'))])
    origin = ('Límite tomado de Fields of the World 2025 (automático).' if ftw else
              'Límite dibujado por el usuario.' if poly else 'Consulta sobre un punto, sin lote delimitado.')

    # ── gráficos
    charts = []
    clima = (((result.get('raw') or {}).get('clima') or {}).get('payload') or {}).get('data') or {}
    if not clima.get('daily'):
        clima = extras.get('clima') or {}
    daily = clima.get('daily') or {}
    days = [d[8:10] + '/' + d[5:7] for d in (daily.get('time') or [])[:7]]
    if days and daily.get('precipitation_sum'):
        charts.append({'kind': 'bars', 'title': 'Lluvia y demanda atmosférica', 'subtitle': 'Pronóstico diario · mm',
                       'unit': 'mm', 'labels': days,
                       'series': [{'name': 'Lluvia', 'values': [_f(x) for x in daily['precipitation_sum'][:7]]},
                                  {'name': 'ET₀', 'values': [_f(x) for x in (daily.get('et0_fao_evapotranspiration') or [])[:7]]}]})
    if days and daily.get('temperature_2m_max'):
        charts.append({'kind': 'bars', 'title': 'Temperaturas próximos días', 'subtitle': 'Máxima y mínima · °C',
                       'unit': '°C', 'labels': days,
                       'series': [{'name': 'Máxima', 'values': [_f(x) for x in daily['temperature_2m_max'][:7]]},
                                  {'name': 'Mínima', 'values': [_f(x) for x in (daily.get('temperature_2m_min') or [])[:7]]}]})
    nser = [r for r in (ndvi.get('series') or []) if r.get('status') == 'válida' and r.get('ndvi_mean') is not None]
    if nser:
        charts.append({'kind': 'line', 'title': 'NDVI del lote', 'subtitle': f"{ndvi.get('sensor', 'Sentinel-2')} · media zonal",
                       'unit': '', 'labels': [str(r.get('datetime') or r.get('from'))[5:10][3:] + '/' + str(r.get('datetime') or r.get('from'))[5:7] for r in nser],
                       'series': [{'name': 'NDVI', 'values': [_f(r['ndvi_mean']) for r in nser]}], 'lo': 0, 'hi': 1})
    yrs = indices.get('years') or []
    if yrs:
        charts.append({'kind': 'bars', 'title': 'Lluvia anual', 'subtitle': f"ERA5 · {indices.get('period', ['', ''])[0]}–{indices.get('period', ['', ''])[1]} · mm",
                       'unit': 'mm', 'labels': [str(r['year'])[2:] for r in yrs],
                       'series': [{'name': 'Lluvia', 'values': [_f(r.get('prcptot')) for r in yrs]}]})

    # ── índices
    irows = []
    last = yrs[-1] if yrs else {}
    for k in indices.get('catalog') or []:
        key = k['key']; v = last.get(key)
        if k['unit'] == 'fecha':
            vv = f'{v[8:10]}/{v[5:7]}' if v else '—'; mean = ''; diff = ''; tn = 'idle'
        else:
            a = (indices.get('anomaly_last_year') or {}).get(key)
            dec = 0 if k['unit'] in ('días', 'eventos') or key in ('prcptot', 'gdd10') else 1
            vv = num(v, dec); mean = num((indices.get('mean') or {}).get(key), 0 if key in ('prcptot', 'gdd10') else 1)
            diff = '' if a is None else ('+' if a > 0 else '') + num(a, 0 if key in ('prcptot', 'gdd10') else 1)
            bad_up = key in ('tx30', 'tx35', 'heat_waves', 'tropical_nights', 'cdd', 'frost_days', 'r20mm', 'rx1day', 'rx5day')
            tn = 'idle' if not a else ('warn' if (a > 0) == bad_up else 'ok')
        irows.append({'label': k['label'], 'unit': k['unit'], 'last': vv, 'mean': mean, 'diff': diff, 'tone': tn})

    # ── teleconexiones
    tl = []
    for key, e in ((tele.get('indices') or {}).items()):
        if e.get('status') == 'recibido':
            dd = e['data']
            tl.append({'name': dd['name'], 'value': num(dd['value'], 2), 'phase': dd['phase'], 'period': dd['period']})
    enso_text = ''
    if tele.get('enso_consensus'):
        enso_text = (f"Consenso NOAA: {tele['enso_consensus']} ({tele.get('enso_agreement')} índices del Pacífico coinciden). "
                     'Interpretar junto al pronóstico estacional del SMN para la zona.')

    # ── lluvia observada CHIRPS
    lluvia = extras.get('lluvia') or {}
    spi_rows = []
    for k, lab in (('1', 'Último mes'), ('3', 'Últimos 3 meses'), ('6', 'Últimos 6 meses'), ('12', 'Últimos 12 meses')):
        x = (lluvia.get('spi') or {}).get(k) or {}
        if x.get('mm') is None:
            continue
        sv = x.get('spi')
        spi_rows.append({'label': lab, 'mm': num(x['mm'], 0), 'normal': num(x.get('normal'), 0),
                         'class': x.get('class', ''), 'spi': num(sv, 1) if sv is not None else '—',
                         'tone': 'idle' if sv is None else 'warn' if sv <= -1 else 'ok' if sv < 1 else 'idle'})
    rec = lluvia.get('recent') or []
    if rec:
        charts.append({'kind': 'bars', 'title': 'Lluvia observada vs. normal', 'subtitle': 'CHIRPS · últimos 12 meses · mm',
                       'unit': 'mm', 'labels': [r['period'][5:7] + '/' + r['period'][2:4] for r in rec],
                       'series': [{'name': 'Observada', 'values': [_f(r.get('mm')) for r in rec]},
                                  {'name': 'Normal', 'values': [_f(r.get('normal')) for r in rec]}]})
    # ── estadística
    st = extras.get('estadistica') or {}
    prob = [{'day': d['date'][8:10] + '/' + d['date'][5:7], 'frost': f"{d.get('p_frost', 0)} %", 'heat': f"{d.get('p_heat35', 0)} %",
             'rain': f"{d.get('p_rain10', 0)} %", 'temps': f"{num(d.get('tmin_med'), 0)}° / {num(d.get('tmax_med'), 0)}°"}
            for d in ((st.get('ensemble') or {}).get('days') or [])[:10]]
    seas = [{'period': m['period'], 'rain': m['rain_reading'], 'temp': m['temp_reading'],
             'split': f"{m['rain']['below']} / {m['rain']['normal']} / {m['rain']['above']}" if m.get('rain') else '—'}
            for m in (st.get('seasonal') or [])]
    trd = [{'label': t['label'], 'value': ('+' if t['per_decade'] > 0 else '') + num(t['per_decade'], 2 if t['key'] == 'tx' else 1) + f" {t['unit']}/década",
            'reading': t['reading'], 'tone': 'warn' if t['significant'] else 'idle'} for t in (st.get('trends') or [])]
    wr = (st.get('ensemble') or {}).get('week_rain') or {}
    stat_note = (f"Pronóstico por conjunto ({(st.get('ensemble') or {}).get('members', '—')} pronósticos ECMWF y NOAA): "
                 f"lluvia probable en 7 días {num(wr.get('p10'), 0)}–{num(wr.get('p90'), 0)} mm, mediana {num(wr.get('median'), 0)} mm.") if wr else ''
    ev = result.get('evidence') or []
    ok = sum(1 for e in ev if e.get('status') == 'recibido')
    return {
        'title': f'DOTS · Informe territorial · {lot.get("name") or name}',
        'generated': generated,
        'place': extras.get('place') or (f'{lat:.4f}, {lon:.4f}' if lat is not None else ''),
        'lot': {'name': lot.get('name') or name, 'shape': shape(poly), 'facts': facts, 'origin': origin},
        'kpis': kpis,
        'confidence': {'score': str(result.get('confidence', {}).get('score', '—')),
                       'label': str(result.get('confidence', {}).get('label', ''))},
        'summary': result.get('summary', ''),
        'recommendations': result.get('recommendations') or [],
        'findings': [{'topic': f.get('topic', ''), 'status': f.get('status', ''), 'text': f.get('text', '')}
                     for f in result.get('findings') or []],
        'metrics': [{'variable': m.get('variable', ''), 'value': f"{num(m.get('value'), 3 if 'm³' in str(m.get('unit')) else 1)} {m.get('unit', '')}".strip(),
                     'reference': str(m.get('reference', '')), 'reading': str(m.get('reading', ''))}
                    for m in result.get('metrics') or []],
        'charts': charts,
        'indices': irows,
        'indices_head': ['Índice', str(indices.get('last_year', 'Último año')), 'Promedio', 'Diferencia'],
        'indices_note': (f"ERA5 diario en el punto del lote, {indices.get('period', ['', ''])[0]}–{indices.get('period', ['', ''])[1]}. "
                         'Definiciones xclim / ETCCDI. Grilla de ~25 km: describe la zona, no microclimas.') if irows else '',
        'telecon': tl,
        'spi': spi_rows,
        'prob': prob, 'seasonal': seas, 'trends': trd, 'stat_note': stat_note,
        'spi_note': (f"CHIRPS v2 (~5 km), promedio sobre el lote. Último mes completo: {lluvia.get('last_month', '')}. Normal: mediana 1991-2020. SPI menor a −1 indica sequía.") if spi_rows else '',
        'enso_text': enso_text,
        'warnings': result.get('warnings') or [],
        'evidence': [{'source': str(e.get('source', '')), 'status': str(e.get('status', '')),
                      'scope': str(e.get('scope') or ''), 'when': (e.get('consulted_at') or '')[:16].replace('T', ' ')}
                     for e in ev],
        'evidence_note': f'{len(ev)} fuentes consultadas · {ok} con respuesta válida · {len(ev) - ok} sin dato. Ningún faltante se reemplaza por valores supuestos.',
        'attributions': ('Datos: Open-Meteo / ERA5 (Copernicus), NASA POWER, ISRIC SoilGrids, ESA Sentinel-2 vía Microsoft Planetary Computer, '
                         'NOAA PSL y CPC, NASA FIRMS, conjuntos ECMWF IFS y GFS y ECMWF SEAS5 vía Open-Meteo, CHIRPS (Climate Hazards Center, UCSB) vía ClimateSERV'
                         + ('; límites de lote: Fields of the World / PRUE (Robinson et al. 2026), CC-BY-4.0' if ftw else '')
                         + '. Tipografía IBM Plex (SIL OFL). Documento compuesto con Typst.'),
    }


def pdf(result, name='Lote DOTS', extras=None):
    """PDF con diseño DOTS. Devuelve (bytes, motor)."""
    try:
        import typst
        data = json.dumps(build_data(result, name, extras), ensure_ascii=False, default=str)
        out = typst.compile(TEMPLATE, root=BASE, font_paths=[FONTS], ignore_system_fonts=True,
                            sys_inputs={'data': data})
        if out[:5] == b'%PDF-':
            return out, 'typst'
    except Exception:
        pass
    import agentic_engine as agentic
    return agentic.pdf_bytes(result, name), 'reportlab'
