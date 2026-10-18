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


def frame_bbox(polygon, pad=0.08):
    """Caja (oeste, sur, este, norte) del cuadro cuadrado que usa shape(), para pedir la imagen satelital."""
    if not polygon or len(polygon) < 3:
        return None
    lat0 = sum(p[0] for p in polygon) / len(polygon)
    k = math.cos(math.radians(lat0))
    xs = [p[1] * k for p in polygon]; ys = [-p[0] for p in polygon]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1e-6
    full = span / (1 - 2 * pad)
    cx = (max(xs) + min(xs)) / 2; cy = (max(ys) + min(ys)) / 2
    x0, x1 = cx - full / 2, cx + full / 2; y0, y1 = cy - full / 2, cy + full / 2
    return (x0 / k, -y1, x1 / k, -y0)


IMAGERY = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export'


def satellite_thumb(polygon, size=560, timeout=6):
    """JPEG del lote desde Esri World Imagery (una sola petición). None si no responde: el informe sigue sin imagen."""
    if os.environ.get('DOTS_REPORT_IMAGERY', '1') == '0':
        return None
    box = frame_bbox(polygon)
    if not box:
        return None
    try:
        import requests
        r = requests.get(IMAGERY, timeout=timeout, params={
            'bbox': ','.join(f'{v:.6f}' for v in box), 'bboxSR': 4326, 'imageSR': 3857,
            'size': f'{size},{size}', 'format': 'jpg', 'f': 'image'})
        if r.ok and r.content[:3] == b'\xff\xd8\xff' and len(r.content) > 2000:
            return r.content
    except Exception:
        pass
    return None


GIBS = 'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi'


def thematic_thumb(polygon, layer='MODIS_Terra_NDVI_8Day', size=560, timeout=6):
    """PNG temático (NDVI) del lote desde NASA GIBS (WMS, sin clave). None si no responde: el informe sigue igual."""
    if os.environ.get('DOTS_REPORT_IMAGERY', '1') == '0':
        return None
    box = frame_bbox(polygon)
    if not box:
        return None
    try:
        import requests
        r = requests.get(GIBS, timeout=timeout, params={
            'service': 'WMS', 'version': '1.1.1', 'request': 'GetMap', 'layers': layer, 'styles': '',
            'srs': 'EPSG:4326', 'bbox': ','.join(f'{v:.6f}' for v in box), 'width': size, 'height': size, 'format': 'image/png'})
        if r.ok and r.content[:4] == b'\x89PNG' and len(r.content) > 2000:
            return r.content
    except Exception:
        pass
    return None


def metric_tone(m):
    """Tono de una variable a partir de umbrales conocidos o de su lectura declarada."""
    name = str(m.get('variable', '')).lower(); v = _f(m.get('value'))
    if 'thi' in name and v is not None:
        return 'ok' if v < 72 else 'warn' if v < 79 else 'risk'
    if name.startswith('temperatura') and v is not None:
        return 'risk' if v >= 35 else 'warn' if v >= 32 else 'ok'
    r = str(m.get('reading', '')).lower()
    if any(w in r for w in ('peligro', 'extremo', 'severo', 'crítico', 'critico', 'emergencia', 'muy alto')):
        return 'risk'
    if any(w in r for w in ('alerta', 'moderad', 'déficit', 'deficit', 'escas', 'seco', 'alta', 'alto', 'atención')):
        return 'warn'
    if any(w in r for w in ('normal', 'sin riesgo', 'confort', 'adecuad', 'bueno', 'óptimo')):
        return 'ok'
    return 'idle'


def week_outlook(nmean, nser, bal, rain, et, thiv, forage):
    """Semáforo de la semana: agua, pasto y calor. Sin dato se declara, no se supone."""
    agua = {'key': 'Agua', 'tone': 'idle', 'head': 'Sin dato', 'value': '—', 'hint': 'Falta el pronóstico de lluvia'}
    if bal is not None:
        agua.update(tone='risk' if bal < -30 else 'warn' if bal < -15 else 'ok',
                    head='Déficit marcado' if bal < -30 else 'Balance negativo' if bal < -15 else 'Equilibrado' if bal < 10 else 'Excedente',
                    value=f'{"+" if bal > 0 else ""}{num(bal, 0)} mm',
                    hint=f'Lluvia {num(rain, 0)} mm · evapotranspiración {num(et, 0)} mm en 7 días')
    pasto = {'key': 'Pasto', 'tone': 'idle', 'head': 'Sin dato', 'value': '—', 'hint': 'Calcular NDVI del lote'}
    if nmean is not None:
        trend = ''
        if len(nser) >= 2:
            d = (_f(nser[-1].get('ndvi_mean')) or 0) - (_f(nser[-2].get('ndvi_mean')) or 0)
            trend = 'en ascenso' if d > 0.02 else 'en descenso' if d < -0.02 else 'estable'
        g = (forage or {}).get('growth_rate_30d')
        pasto.update(tone='ok' if nmean >= 0.5 else 'warn' if nmean >= 0.3 else 'risk',
                     head=('Vigor alto' if nmean >= 0.5 else 'Vigor medio' if nmean >= 0.3 else 'Vigor bajo') + (f', {trend}' if trend else ''),
                     value=f'NDVI {num(nmean, 2)}',
                     hint=(f'Crece {num(g, 0)} kg MS/ha/día · ' if g is not None else '') + 'Sentinel-2, nubes excluidas')
    calor = {'key': 'Calor y rodeo', 'tone': 'idle', 'head': 'Sin dato', 'value': '—', 'hint': 'Falta temperatura y humedad'}
    if thiv is not None:
        calor.update(tone='ok' if thiv < 72 else 'warn' if thiv < 79 else 'risk',
                     head='Sin estrés' if thiv < 72 else 'Alerta' if thiv < 79 else 'Peligro',
                     value=f'THI {num(thiv)}', hint='Umbrales 72 alerta · 79 peligro')
    return [agua, pasto, calor]


def _metric(result, name):
    return next((m for m in result.get('metrics', []) if m.get('variable') == name), None)



def _dm(d):
    d = str(d or '')
    return f'{d[8:10]}/{d[5:7]}' if len(d) >= 10 else '—'


def more_cards(extras):
    """Lecturas del lote calculadas en el panel con Earth Engine y el perfil de suelo: cada una entra solo si vino con dato."""
    out = []
    rh = extras.get('riesgo') or {}
    if rh.get('zones'):
        out.append({'title': 'Lomas, planos y bajos', 'facts': [[z['name'], f"{num(z.get('pct'), 0)} % · {num(z.get('ha'), 0)} ha"] for z in rh['zones'] if (_f(z.get('pct')) or 0) >= 0.5]
                    + [['Desnivel', f"{num(rh.get('relief_m'))} m"], ['Agua vista desde 1984', f"{num(rh.get('water_seen_ha'), 0)} ha"]],
                    'note': str(rh.get('reading') or '') + ' Copernicus GLO-30, JRC Global Surface Water y MERIT Hydro vía Earth Engine.',
                    'credit': 'lomas y bajos: Copernicus GLO-30, JRC Global Surface Water (EC JRC/Google), MERIT Hydro'})
    sb = extras.get('suelos50') or {}
    if sb.get('units'):
        out.append({'title': 'Suelos · INTA 1:50.000', 'facts': [[f"{u.get('symbol')} · cap. {u.get('capability') or '—'}", f"{num(u.get('pct'), 0)} %"] for u in sb['units'][:6]],
                    'note': str(sb.get('reading') or '') + ' ' + str(sb.get('source') or 'INTA, CC BY 4.0'),
                    'credit': 'suelos: Carta de suelos 1:50.000 de Buenos Aires (INTA, CC BY 4.0)'})
    pf = (extras.get('perfil') or {}).get('profile') or {}
    av = pf.get('available') or {}
    if pf.get('layers'):
        facts = [[str(l.get('layer') or l.get('label')), f"{num(l.get('mm'), 0)} mm · {l.get('class') or '—'}"] for l in pf['layers'][:4]]
        if av.get('pct') is not None:
            facts.append(['Agua útil hasta 2 m', f"{num(av.get('pct'), 0)} % · {av.get('class') or ''}".strip()])
        out.append({'title': 'Agua en el perfil del suelo', 'facts': facts, 'note': str(pf.get('reading') or '') + ' ERA5-Land (~9 km) y SoilGrids; modelo, no medición en el lote.',
                    'credit': 'perfil de suelo: ERA5-Land (Copernicus) vía Open-Meteo e ISRIC SoilGrids'})
    an = extras.get('anomalia') or {}
    if an.get('series'):
        r = an['series'][-1]
        out.append({'title': 'Vegetación contra otros años', 'facts': [['Último compuesto', _dm(r.get('date'))], ['NDVI', num(r.get('ndvi'), 2)], ['Normal de la época', num(r.get('normal'), 2)],
                    ['Diferencia', (('+' if (_f(r.get('diff')) or 0) > 0 else '') + num(r.get('diff'), 2)) if r.get('diff') is not None else '—'], ['VCI', num(r.get('vci'), 0)]],
                    'note': str(an.get('reading') or '') + ' NASA MODIS MOD13Q1 (250 m) desde 2001.', 'credit': 'anomalía de NDVI: NASA MODIS MOD13Q1'})
    et = extras.get('etr') or {}
    if (et.get('latest') or {}).get('mm_day') is not None:
        lt = et['latest']
        out.append({'title': 'Consumo de agua del cultivo', 'facts': [['Últimos 8 días', f"{num(lt.get('mm_day'))} mm/día"],
                    ['Contra lo normal', (('+' if (_f(lt.get('diff_pct')) or 0) > 0 else '') + num(lt.get('diff_pct'), 0) + ' %') if lt.get('diff_pct') is not None else '—'], ['Percentil', num(lt.get('percentile'), 0)]],
                    'note': str(et.get('reading') or '') + ' NASA MODIS MOD16A2 (500 m, 8 días).', 'credit': 'evapotranspiración: NASA MODIS MOD16A2'})
    fr = extras.get('heladas_sat') or {}
    if fr.get('frost_nights_30d') is not None:
        cd = fr.get('coldest') or {}
        out.append({'title': 'Heladas por satélite', 'facts': [['Noches con helada (30 días)', num(fr.get('frost_nights_30d'), 0)], ['Noche más fría', f"{num(cd.get('lst_c'))} °C · {_dm(cd.get('date'))}"]],
                    'note': str(fr.get('reading') or '') + ' NASA MODIS Aqua MYD11A1 (1 km): temperatura de la superficie en noches despejadas.', 'credit': 'heladas: NASA MODIS Aqua MYD11A1'})
    return out

def advisor_block(asesor):
    """Envelope del asesor (/api/fuentes/asesor) → tarjetas y gráficos para el informe. None si no hay datos."""
    if not isinstance(asesor, dict):
        return None
    data = asesor.get('data') if isinstance(asesor.get('data'), dict) else asesor
    agua, nitro, aire = data.get('agua'), data.get('nitrogeno'), data.get('aire')
    pulv, enfer = data.get('pulverizacion'), data.get('enfermedad')
    if not any((agua, nitro, aire, pulv, enfer)):
        return None
    cards, charts = [], []
    if agua:
        cards.append({'title': 'Riego (FAO-56)', 'label': 'Necesidad neta de riego', 'value': num(agua.get('net_irrigation_mm'), 1), 'unit': 'mm',
                      'scale': '', 'facts': [['ETc de la ventana', f"{num(agua.get('etc_total_mm'), 1)} mm"],
                                ['Lluvia esperada', f"{num(agua.get('rain_total_mm'), 1)} mm"],
                                ['Riego bruto (75 % de eficiencia)', f"{num(agua.get('gross_irrigation_mm'), 1)} mm"],
                                ['Agua útil del perfil', f"{num(agua.get('taw_mm'), 0)} mm"],
                                ['Riego fácil (RAW)', f"{num(agua.get('raw_mm'), 0)} mm"]],
                      'note': str(agua.get('reading') or '')})
        if agua.get('days'):
            charts.append({'kind': 'balance', 'group': 'asesor', 'title': 'Agua de la ventana pronosticada',
                           'subtitle': 'Lluvia esperada hacia arriba · ETc del cultivo hacia abajo · mm', 'unit': 'mm',
                           'labels': [str(i + 1) for i in range(len(agua['days']))],
                           'series': [{'name': 'Lluvia', 'values': [_f(x.get('rain_mm')) for x in agua['days']]},
                                      {'name': 'ETc', 'values': [_f(x.get('etc_mm')) for x in agua['days']]}]})
    if nitro:
        cards.append({'title': 'Nitrógeno (DSSAT / RothC)', 'label': 'Dosis sugerida', 'value': num(nitro.get('dose_kg_ha'), 0), 'unit': 'kg N/ha',
                      'scale': '', 'facts': [['Demanda del cultivo', f"{num(nitro.get('demand_kg_ha'), 0)} kg N/ha"],
                                ['Aporte del suelo', f"{num(nitro.get('supply_from_soil_kg_ha'), 0)} kg N/ha"],
                                ['Crédito cultivo previo', f"{num(nitro.get('prev_crop_credit_kg_ha'), 0)} kg N/ha"],
                                ['Equivalente en urea', f"{num(nitro.get('urea_kg_ha'), 0)} kg/ha"]],
                      'note': str(nitro.get('reading') or '') + ' Orientativo: no reemplaza un análisis de nitrato 0-60 cm.'})
    if aire and aire.get('index') is not None:
        sc = aire.get('scale') or {}
        facts = [[p.get('label', k), f"{num(p.get('value'), 1)} µg/m³ · índice {num(p.get('sub_index'), 0)}"]
                 for k, p in (aire.get('per_pollutant') or {}).items() if p.get('value') is not None]
        cards.append({'title': 'Aire (CAMS)', 'label': 'Índice europeo de calidad', 'value': num(aire.get('index'), 0), 'unit': str(aire.get('category') or ''),
                      'scale': 'Escala 0 a 500 · buena ≤ 20 · mala ≥ 60', 'facts': facts, 'note': str(aire.get('reading') or '')})
    if pulv and pulv.get('rows'):
        best = pulv.get('best')
        val = f"{best['from']}–{best['to']}" if best else 'sin ventana'
        cards.append({'title': 'Ventana de pulverización', 'label': 'Mejor franja diurna', 'value': val, 'unit': '',
                      'scale': 'Aptitud 0 a 100 · apta ≥ 70 · viento 3–11 km/h · Delta T 2–8 °C',
                      'facts': [['Horas evaluadas', num(pulv.get('hours', 0), 0)],
                                ['Horas aptas (≥ 70)', num(len([r for r in pulv['rows'] if r['index'] >= 70]), 0)],
                                ['Día de la mejor franja', (best or {}).get('date', '—')],
                                ['Aptitud de la franja', num((best or {}).get('index'), 0)]],
                      'note': str(pulv.get('reading') or '')})
    if enfer and enfer.get('rows'):
        sc = enfer.get('scale') or {}
        top = max(enfer['rows'], key=lambda r: r['risk'])
        cards.append({'title': f"Enfermedad por clima · {enfer.get('name', '')}", 'label': 'Riesgo máximo', 'value': num(enfer.get('risk_max'), 0), 'unit': '/100',
                      'scale': 'Escala 0 a 100 · bajo < 20 · alto ≥ 40',
                      'facts': [['Día de mayor riesgo', str(enfer.get('risk_max_date', ''))],
                                ['Horas de mojado en franja', f"{num(top.get('wet_hours_in_range'), 0)} h (pide {num(enfer.get('wet_hours_required'), 0)})"],
                                ['Franja de temperatura', '–'.join(str(x) for x in (enfer.get('temperature_range_c') or [])) + ' °C'],
                                ['Banda', str((top.get('band') or {}).get('label', '—'))]],
                      'note': str(enfer.get('reading') or '')})
        charts.append({'kind': 'bars', 'group': 'asesor', 'title': f"Riesgo de enfermedad · {enfer.get('name', '')}",
                       'subtitle': 'Índice 0 a 100 por día de pronóstico', 'unit': '/100',
                       'labels': [str(r['date'])[8:10] + '/' + str(r['date'])[5:7] for r in enfer['rows']],
                       'series': [{'name': 'Riesgo', 'values': [_f(r.get('risk')) for r in enfer['rows']]}]})
    return {'cards': cards, 'charts': charts, 'lectura': str(data.get('lectura') or '')}


def exec_summary(d):
    """Resumen en prosa (reglas, sin modelo de lenguaje) del estado del lote para abrir el informe."""
    parts = []
    week = {w['key']: w for w in (d.get('week') or [])}
    for key, nombre in (('Agua', 'Agua'), ('Pasto', 'Pasto'), ('Calor y rodeo', 'Calor')):
        w = week.get(key)
        if w and w.get('tone') != 'idle':
            parts.append(f"{nombre}: {str(w['head']).lower()} ({w['value']}).")
    alerts = d.get('alerts') or []
    if alerts:
        hi = sum(1 for a in alerts if a.get('level') == 'alta')
        parts.append(f"{len(alerts)} alerta(s) activa(s)" + (f", {hi} de nivel alto" if hi else '') + '.')
    if d.get('spi'):
        s = d['spi'][0]
        parts.append(f"Lluvia del {str(s['label']).lower()}: {s['class']} (SPI {s['spi']}).")
    if d.get('enso_text'):
        parts.append(d['enso_text'])
    recs = d.get('recommendations') or []
    if recs:
        texts = [r['text'] if isinstance(r, dict) else str(r) for r in recs[:2]]
        parts.append('Prioridad: ' + ' '.join(texts))
    return ' '.join(parts)


SECTIONS = [
    {'id': 'resumen', 'title': 'Resumen ejecutivo', 'group': 'Síntesis', 'desc': 'Párrafo de apertura con el estado del lote en una lectura.'},
    {'id': 'alertas', 'title': 'Alertas activas', 'group': 'Síntesis', 'desc': 'Reglas disparadas (helada, calor, lluvia, sequía, fuego, vegetación).'},
    {'id': 'hallazgos', 'title': 'Hallazgos por dimensión', 'group': 'Síntesis', 'desc': 'Conclusiones por tema con su estado.'},
    {'id': 'variables', 'title': 'Variables del lote', 'group': 'Síntesis', 'desc': 'Tabla de variables medidas con su tono.'},
    {'id': 'clima', 'title': 'Clima de la semana', 'group': 'Ambiente', 'desc': 'Balance de agua y temperaturas del pronóstico.'},
    {'id': 'vegetacion', 'title': 'Vegetación y pasto', 'group': 'Ambiente', 'desc': 'NDVI del lote y producción de forraje.'},
    {'id': 'lluvia', 'title': 'Lluvia observada y sequía', 'group': 'Ambiente', 'desc': 'SPI y lluvia acumulada contra lo normal.'},
    {'id': 'relieve', 'title': 'Relieve y anegamiento', 'group': 'Ambiente', 'desc': 'Posición en el paisaje y propensión a anegarse.'},
    {'id': 'agua', 'title': 'Agua detectada por satélite', 'group': 'Ambiente', 'desc': 'Superficie con agua vista por Sentinel-2.'},
    {'id': 'suelo', 'title': 'Humedad del suelo y entorno', 'group': 'Ambiente', 'desc': 'Humedad contra lo normal y entorno del lote.'},
    {'id': 'asesor', 'title': 'Asesor agronómico integrado', 'group': 'Decisión', 'desc': 'Riego, nitrógeno, aire, pulverización y enfermedad, con su escala.'},
    {'id': 'terreno', 'title': 'Terreno, suelos y satélite', 'group': 'Decisión', 'desc': 'Lomas y bajos, carta de suelos INTA, perfil y anomalía.'},
    {'id': 'indices', 'title': 'Índices agroclimáticos', 'group': 'Clima largo', 'desc': 'Índices ETCCDI y lluvia anual.'},
    {'id': 'probabilidades', 'title': 'Probabilidades y tendencias', 'group': 'Clima largo', 'desc': 'Conjuntos ECMWF, estacional y tendencias Mann-Kendall.'},
    {'id': 'enso', 'title': 'El Niño y teleconexiones', 'group': 'Clima largo', 'desc': 'Fase del Pacífico y su efecto esperado.'},
    {'id': 'costos', 'title': 'Costos y logística', 'group': 'Gestión', 'desc': 'Fletes, dólar y costos de referencia.'},
    {'id': 'sustentabilidad', 'title': 'Sustentabilidad', 'group': 'Gestión', 'desc': 'Cobertura, deforestación y huella.'},
    {'id': 'limites', 'title': 'Límites de la lectura', 'group': 'Transparencia', 'desc': 'Advertencias y supuestos.'},
    {'id': 'trazabilidad', 'title': 'Trazabilidad de fuentes', 'group': 'Transparencia', 'desc': 'Fuentes consultadas, estado y atribuciones.'},
]


def section_ids():
    return [s['id'] for s in SECTIONS]


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
        charts.append({'kind': 'balance', 'group': 'clima', 'title': 'Balance de agua de la semana', 'subtitle': 'Lluvia hacia arriba, evapotranspiración hacia abajo · línea: balance acumulado · mm',
                       'unit': 'mm', 'labels': days,
                       'series': [{'name': 'Lluvia', 'values': [_f(x) for x in daily['precipitation_sum'][:7]]},
                                  {'name': 'Evapotranspiración', 'values': [_f(x) for x in (daily.get('et0_fao_evapotranspiration') or [])[:7]]}]})
    if days and daily.get('temperature_2m_max'):
        charts.append({'kind': 'band', 'group': 'clima', 'title': 'Temperaturas de la semana', 'subtitle': 'Rango entre mínima y máxima · °C · naranja: 35 °C o más',
                       'unit': '°C', 'labels': days,
                       'series': [{'name': 'Máxima', 'values': [_f(x) for x in daily['temperature_2m_max'][:7]]},
                                  {'name': 'Mínima', 'values': [_f(x) for x in (daily.get('temperature_2m_min') or [])[:7]]}]})
    nser = [r for r in (ndvi.get('series') or []) if r.get('status') == 'válida' and r.get('ndvi_mean') is not None]
    if nser:
        charts.append({'kind': 'line', 'group': 'veg', 'title': 'NDVI del lote', 'subtitle': f"{ndvi.get('sensor', 'Sentinel-2')} · media zonal",
                       'unit': '', 'labels': [str(r.get('datetime') or r.get('from'))[5:10][3:] + '/' + str(r.get('datetime') or r.get('from'))[5:7] for r in nser],
                       'series': [{'name': 'NDVI', 'values': [_f(r['ndvi_mean']) for r in nser]}], 'lo': 0, 'hi': 1})
    yrs = indices.get('years') or []
    if yrs:
        charts.append({'kind': 'bars', 'group': 'indices', 'title': 'Lluvia anual', 'subtitle': f"ERA5 · {indices.get('period', ['', ''])[0]}–{indices.get('period', ['', ''])[1]} · mm",
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
        charts.append({'kind': 'bars', 'group': 'lluvia', 'title': 'Lluvia observada vs. normal', 'subtitle': 'CHIRPS · últimos 12 meses · mm',
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
    al = extras.get('alertas') or {}
    alerts_rows = [{'title': a['title'], 'detail': a['detail'], 'action': a['action'], 'source': a['source'],
                    'tone': 'risk' if a['level'] == 'alta' else 'warn' if a['level'] == 'media' else 'idle', 'level': a['level']}
                   for a in (al.get('alerts') or [])]
    alerts_note = al.get('summary', '') if al else ''
    fo = extras.get('forraje') or {}
    forage_cards = []
    if fo.get('growth_rate_30d') is not None:
        forage_cards = [{'label': 'Crecimiento 30 días', 'value': num(fo['growth_rate_30d'], 0), 'unit': 'kg MS/ha/día'},
                        {'label': 'Carga que sostiene', 'value': num(fo.get('ev_ha'), 2), 'unit': 'EV/ha'},
                        {'label': 'En todo el lote', 'value': num(fo.get('ev_lot'), 0), 'unit': 'EV'},
                        {'label': f"Acumulado {fo.get('accumulated_days', '')} días", 'value': num(fo.get('accumulated'), 0), 'unit': 'kg MS/ha'}]
        if fo.get('daily'):
            charts.append({'kind': 'line', 'group': 'veg', 'title': 'Crecimiento diario del pasto', 'subtitle': f"{fo.get('kind_label', '')} · kg MS/ha/día",
                           'unit': '', 'labels': [x['date'][8:10] + '/' + x['date'][5:7] for x in fo['daily']],
                           'series': [{'name': 'Crecimiento', 'values': [_f(x['ppna']) for x in fo['daily']]}]})
    forage_note = (' · '.join((fo.get('assumptions') or {}).values()) + '. ' + fo.get('note', '')
                   + (f" Carga actual {num(fo.get('current_load_ev_ha'), 2)} EV/ha: {fo.get('load_balance')}." if fo.get('current_load_ev_ha') is not None else '')) if forage_cards else ''
    su = extras.get('sustentabilidad') or {}
    de = su.get('deforestation') or {}; cb = su.get('carbon') or {}
    sust = []
    if de.get('verdict'):
        sust.append({'label': f"Libre de deforestación (corte {de.get('cutoff')})", 'value': de['verdict'],
                     'detail': f"Pérdida estimada {num(de.get('tree_loss_ha'), 1)} ha · cambio {num(de.get('tree_change_pp'), 1)} puntos de cobertura arbórea ({de.get('baseline_year')}→{de.get('last_year')})",
                     'tone': 'ok' if str(de['verdict']).startswith('sin pérdida') else 'warn'})
    if cb.get('soc_t_ha') is not None:
        sust.append({'label': 'Carbono orgánico del suelo 0-30 cm', 'value': f"{num(cb['soc_t_ha'], 1)} t C/ha",
                     'detail': (f"Total del lote {num(cb.get('soc_total_t'), 0)} t C ({num(cb.get('soc_total_tco2e'), 0)} t CO₂e)" if cb.get('soc_total_t') else 'SoilGrids, modelo global 250 m'), 'tone': 'idle'})
    if cb.get('herd'):
        h = cb['herd']
        sust.append({'label': f"Emisiones del rodeo · {h['heads']} cabezas", 'value': f"{num(h['co2e_t_year'], 0)} t CO₂e/año",
                     'detail': f"{num(h['ch4_t_year'], 1)} t CH₄/año · {h['method']}", 'tone': 'idle'})
    co = extras.get('costos') or {}
    cm, cl = co.get('margin') or {}, co.get('logistics') or {}
    costs_cards, costs_lines = [], []
    if cl.get('km') is not None:
        costs_cards.append({'label': 'Distancia al destino', 'value': num(cl['km'], 0), 'unit': 'km'})
        if cl.get('hours') is not None:
            costs_cards.append({'label': 'Tiempo de viaje', 'value': num(cl['hours'], 1), 'unit': 'h'})
    if cm.get('freight') is not None:
        costs_cards.append({'label': f"Flete · {cm.get('trips')} viajes", 'value': '$ ' + num(cm['freight'], 0), 'unit': ''})
    if cm.get('net') is not None:
        costs_cards.append({'label': 'Margen bruto', 'value': ('− $ ' if cm['net'] < 0 else '$ ') + num(abs(cm['net']), 0),
                            'unit': f"US$ {num(cm.get('net_ha_usd'), 1)}/ha" if cm.get('net_ha_usd') is not None else ''})
    if cm.get('breakeven_price_kg') is not None:
        costs_cards.append({'label': 'Precio de equilibrio', 'value': '$ ' + num(cm['breakeven_price_kg'], 0), 'unit': '/kg'})
    costs_lines = [{'label': l['label'], 'value': ('− $ ' if l['value'] < 0 else '$ ') + num(abs(l['value']), 0)} for l in cm.get('lines') or []]
    fx = co.get('exchange') or {}
    costs_note = ((f"Destino: {(cl.get('destination') or {}).get('name', '')} · {cl.get('method', '')}. " if cl else '')
                  + (f"Dólar oficial $ {num(fx.get('oficial_venta'), 2)} ({fx.get('source')}). " if fx.get('oficial_venta') else '')
                  + 'Precios y costos cargados por el productor. ' + str(co.get('method') or '')) if costs_cards else ''
    rl = extras.get('relieve') or {}
    relief = None
    if rl.get('riskPct'):
        rp = rl['riskPct']
        relief = {'position': str(rl.get('positionLabel', '')).capitalize(), 'position_n': str(rl.get('position', '—')),
                  'tone': 'warn' if (_f(rp.get('alto')) or 0) >= 15 else 'ok',
                  'facts': [['Desnivel en el lote', f"{num(rl.get('relief'))} m"], ['Pendiente media', f"{num(rl.get('slopeMeanPct'), 2)} %"],
                            ['Bajos cerrados ≥ 10 cm', f"{num(rl.get('depressionHa'))} ha · {num(rl.get('depressionPct'), 0)} %"],
                            ['Agua que retienen', f"{num((_f(rl.get('storageM3')) or 0) / 1000)} mil m³"],
                            ['Vías de escurrimiento', f"{num(rl.get('drainageHa'))} ha"], ['Cota media / entorno', f"{num(rl.get('elevMean'))} / {num(rl.get('envMean'))} m"]],
                  'risk': [{'label': 'Baja', 'pct': _f(rp.get('bajo')) or 0, 'tone': 'ok'}, {'label': 'Media', 'pct': _f(rp.get('medio')) or 0, 'tone': 'warn'},
                           {'label': 'Alta', 'pct': _f(rp.get('alto')) or 0, 'tone': 'risk'}],
                  'note': f"Copernicus DEM GLO-30, celdas de {rl.get('cellM', 30)} m. Relleno de depresiones, flujo D8 e índice topográfico de humedad. "
                          'Modelo de superficie: montes y construcciones suman altura. Indicador relativo, no cota de inundación.'}
    ag = extras.get('agua') or {}
    water = None
    if ag.get('water_ha') is not None:
        hs = [h for h in (ag.get('history') or []) if h.get('water_ha') is not None][-12:]
        sc = ag.get('scene') or {}
        water = {'facts': [['Agua dentro del lote', f"{num(ag.get('water_ha'))} ha"], ['Cuerpos de agua', num(ag.get('water_bodies'), 0)],
                           ['Parte del lote', f"{num(ag.get('water_pct'))} %"], ['Imagen Sentinel-2', f"{str(sc.get('date', ''))[8:10]}/{str(sc.get('date', ''))[5:7]}/{str(sc.get('date', ''))[:4]} · nubes {num(sc.get('cloud_pct'), 0)} %"]],
                 'labels': [str(h.get('scene_date', ''))[8:10] + '/' + str(h.get('scene_date', ''))[5:7] for h in hs],
                 'values': [_f(h.get('water_ha')) for h in hs],
                 'note': 'Procesamiento semanal: Sentinel-2 L2A (Earth Search), detección de agua con geoai y el modelo preentrenado OmniWaterMask, recortada al lote.'
                         + (' Resultado de una semana anterior: la última imagen no tuvo dato válido.' if ag.get('stale') else '')}
    sw = extras.get('humedad') or {}
    soil_nasa = None
    if sw.get('root_pct') is not None:
        soil_nasa = {'facts': [['Zona de raíces (0-100 cm)', f"{num(sw.get('root_pct'), 0)} %"], ['Normal del mes', f"{num(sw.get('normal_pct'), 0)} %"],
                               ['Estado', str(sw.get('category') or '—')], ['Percentil', f"{num(sw.get('percentile'), 0)} de 100"],
                               ['Cambio en 30 días', (('+' if (sw.get('change_30d_pts') or 0) > 0 else '') + num(sw.get('change_30d_pts'), 0) + ' pts') if sw.get('change_30d_pts') is not None else '—']],
                     'note': f"NASA POWER (MERRA-2), % de saturación; último dato {str(sw.get('date', ''))[8:10]}/{str(sw.get('date', ''))[5:7]}. Normal: mismo mes, {sw.get('years', '—')} años. Segunda opinión, independiente de Open-Meteo."}
    en = (extras.get('agua') or {}).get('entorno') or extras.get('entorno') or {}
    surroundings = None
    if en:
        kmf = lambda m: '—' if m is None else ('pasa por el lote' if m == 0 else f"{num(m, 0)} m" if m < 1000 else f"{num(m / 1000)} km")
        ck = en.get('caminos_km') or {}
        surroundings = {'facts': [['Ubicación', ', '.join(x for x in (en.get('departamento'), en.get('provincia')) if x) or '—'],
                                  ['Camino más cercano', kmf(en.get('camino_mas_cercano_m'))], ['Ruta más cercana', kmf(en.get('ruta_mas_cercana_m')) if en.get('ruta_mas_cercana_m') is not None else 'más de 6 km'],
                                  ['Caminos dentro del lote', f"{num((ck.get('caminos_lote') or 0) + (ck.get('rutas_lote') or 0))} km"],
                                  ['Construcciones en el lote', num(en.get('construcciones_lote'), 0)], ['Construcciones a 2 km', num(en.get('construcciones_2km'), 0)]],
                        'note': f"Overture Maps (OpenStreetMap, Microsoft, Google y otros), versión {en.get('release', '—')}. Pueden faltar caminos internos o galpones nuevos."}
    lot_more = more_cards(extras)
    nl_series = [r for r in (ndvi.get('series') or []) if r.get('status') == 'válida' and r.get('ndvi_mean') is not None]
    week = week_outlook(nmean, nl_series, bal, _f(rain and rain.get('value')), _f(et and et.get('value')), thiv, fo)
    thumb = extras.get('_thumb') if '_thumb' in extras else satellite_thumb(poly)
    conf = result.get('confidence', {}) or {}
    ev = result.get('evidence') or []
    ok = sum(1 for e in ev if e.get('status') == 'recibido')
    advisor = advisor_block(extras.get('asesor'))
    for ch in (advisor or {}).get('charts') or []:
        charts.append(ch)
    exec_text = exec_summary({'week': week, 'alerts': alerts_rows, 'spi': spi_rows,
                              'enso_text': enso_text, 'recommendations': result.get('recommendations') or []})
    return {
        'week': week, 'lot_more': lot_more, 'relief': relief, 'water': water, 'soil_nasa': soil_nasa, 'surroundings': surroundings,
        'confidence_line': f"Confianza de la lectura {conf.get('score', '—')}/100 ({conf.get('label', 's/d')}) · {ok} de {len(ev)} fuentes con respuesta válida",
        'title': f'DOTS · Informe territorial · {lot.get("name") or name}',
        'generated': generated,
        'place': extras.get('place') or (f'{lat:.4f}, {lon:.4f}' if lat is not None else ''),
        'lot': {'name': lot.get('name') or name, 'shape': shape(poly), 'facts': facts, 'origin': origin,
                'image': list(thumb) if thumb else None, 'image_credit': 'Imagen: Esri World Imagery (Maxar, Earthstar Geographics). Fecha de toma no homogénea.' if thumb else ''},
        'kpis': kpis,
        'sections': SECTIONS,
        'selected': [s for s in (extras.get('secciones') or extras.get('temas') or []) if s in section_ids()] or None,
        'confidence': {'score': str(result.get('confidence', {}).get('score', '—')),
                       'label': str(result.get('confidence', {}).get('label', ''))},
        'summary': result.get('summary', ''),
        'recommendations': result.get('recommendations') or [],
        'findings': [{'topic': f.get('topic', ''), 'status': f.get('status', ''), 'text': f.get('text', '')}
                     for f in result.get('findings') or []],
        'metrics': [{'variable': m.get('variable', ''), 'value': f"{num(m.get('value'), 3 if 'm³' in str(m.get('unit')) else 1)} {m.get('unit', '')}".strip(),
                     'reference': str(m.get('reference', '')), 'reading': str(m.get('reading', '')), 'tone': metric_tone(m)}
                    for m in result.get('metrics') or []],
        'charts': charts,
        'advisor': advisor, 'exec_summary': exec_text,
        'indices': irows,
        'indices_head': ['Índice', str(indices.get('last_year', 'Último año')), 'Promedio', 'Diferencia'],
        'indices_note': (f"ERA5 diario en el punto del lote, {indices.get('period', ['', ''])[0]}–{indices.get('period', ['', ''])[1]}. "
                         'Definiciones xclim / ETCCDI. Grilla de ~25 km: describe la zona, no microclimas.') if irows else '',
        'telecon': tl,
        'spi': spi_rows,
        'forage': forage_cards, 'forage_note': forage_note, 'sust': sust,
        'costs': costs_cards, 'costs_lines': costs_lines, 'costs_note': costs_note,
        'alerts': alerts_rows, 'alerts_note': alerts_note,
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
                         + ('; cobertura: Impact Observatory y ESA WorldCover vía Microsoft Planetary Computer (CC-BY 4.0)' if sust else '')
                         + ('; rutas: OSRM con datos OpenStreetMap (ODbL); dólar: DolarAPI' if costs_cards else '')
                         + ('; relieve: Copernicus DEM GLO-30 © DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH 2014-2018, provisto bajo COPERNICUS por la UE y la ESA' if relief else '')
                         + ('; imagen satelital: Esri World Imagery' if thumb else '')
                         + ('; agua: Sentinel-2 (ESA/Copernicus) procesado con geoai (opengeos, MIT) y OmniWaterMask' if water else '')
                         + ('; humedad: NASA POWER (MERRA-2)' if soil_nasa else '')
                         + ('; entorno: Overture Maps Foundation (ODbL y CDLA)' if surroundings else '')
                         + ('; ' + '; '.join(c['credit'] for c in lot_more) if lot_more else '')
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


# ───────────────────────────── informe de libre de deforestación ─────────────────────────────
EUDR_TEMPLATE = os.path.join(BASE, 'eudr.typ')


def _segments_cross(a, b, c, d):
    def o(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


def eudr_ring(vertices):
    """Anillo lon/lat con 6 decimales, sin puntos repetidos y cerrado. Error si no es un polígono válido para TRACES."""
    ring = []
    for la, lo in vertices:
        p = [round(float(lo), 6), round(float(la), 6)]
        if not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90):
            raise ValueError('Coordenada fuera de rango')
        if not ring or ring[-1] != p:
            ring.append(p)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring.pop()
    if len({tuple(p) for p in ring}) < 3:
        raise ValueError('El lote necesita al menos tres vértices distintos')
    n = len(ring)
    for i in range(n):
        for j in range(i + 1, n):
            if abs(i - j) in (1, n - 1):
                continue
            if _segments_cross(ring[i], ring[(i + 1) % n], ring[j], ring[(j + 1) % n]):
                raise ValueError('El contorno del lote se cruza a sí mismo: TRACES lo rechaza. Redibujalo sin cruces.')
    return ring + [ring[0]]


def geojson_lot(vertices, name='Lote', area_ha=None, country='AR'):
    """GeoJSON para el sistema de información EUDR (TRACES): WGS84, lon/lat, 6 decimales, un Feature por parcela,
    propiedades ProductionPlace, ProducerCountry (ISO2) y Area en hectáreas como número."""
    ring = eudr_ring(vertices)
    props = {'ProductionPlace': str(name)[:80], 'ProducerCountry': country}
    if area_ha is not None:
        props['Area'] = round(float(area_ha), 2)
    return {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': props, 'geometry': {'type': 'Polygon', 'coordinates': [ring]}}]}


def lot_centroid(ring):
    pts = ring[:-1]
    return [round(sum(p[0] for p in pts) / len(pts), 6), round(sum(p[1] for p in pts) / len(pts), 6)]


def readiness_block(r, de, area):
    """Lista para el comprador: lo que mide DOTS más lo que declara el productor (enviado por la web)."""
    r = r if isinstance(r, dict) else {}
    verdict = str(de.get('verdict') or 'sin dato')
    forest = 'ok' if verdict.startswith('sin pérdida') else 'warn' if verdict.startswith('pérdida menor') else 'risk' if verdict.startswith('pérdida de cobertura') else 'idle'
    auto = [{'label': 'Geolocalización del lote', 'tone': 'ok' if area else 'idle',
             'detail': f'Polígono de {num(area, 1)} ha en formato TRACES.' if area else 'Sin polígono.'},
            {'label': 'Libre de deforestación desde el 31/12/2020', 'tone': forest, 'detail': verdict},
            {'label': 'Riesgo país', 'tone': 'warn', 'detail': 'Argentina: riesgo estándar. Debida diligencia completa; controles sobre el 3 % de los operadores.'}]
    w = r.get('whisp') if isinstance(r.get('whisp'), dict) else None
    if w and w.get('risk'):
        auto.append({'label': 'Segunda opinión · Whisp (FAO)', 'tone': {'low': 'ok', 'high': 'risk'}.get(w['risk'], 'warn'),
                     'detail': str(w.get('text') or '')[:300]})
    declared = []
    for x in (r.get('declared') or [])[:20]:
        if isinstance(x, dict) and x.get('text'):
            declared.append({'text': str(x['text'])[:200], 'done': bool(x.get('done'))})
    res = r.get('result') if isinstance(r.get('result'), dict) else {}
    return {'product': str(r.get('product') or '')[:80], 'in_scope': r.get('in_scope', True) is not False,
            'title': str(res.get('title') or '')[:120], 'text': str(res.get('text') or '')[:400],
            'tone': {'ok': 'ok', 'warn': 'warn'}.get(res.get('tone'), 'idle'), 'auto': auto, 'declared': declared}


def _movements(rows):
    out = []
    for r in (rows or [])[:60]:
        if not isinstance(r, dict):
            continue
        out.append({'date': str(r.get('date') or '')[:10], 'kind': str(r.get('kind') or '')[:20], 'cat': str(r.get('cat') or '')[:30],
                    'heads': str(r.get('heads') or ''), 'note': str(r.get('note') or '')[:80]})
    return out


def _mapbiomas_block(mb):
    if not mb or not mb.get('years'):
        return None
    rows = mb['years']
    by = {r['year']: r for r in rows}
    pick = []
    for y in (rows[0]['year'], 2000, 2010, 2020, rows[-1]['year']):
        if y in by and y not in pick:
            pick.append(y)
    g = mb.get('eudr') or {}
    return {'country': (mb.get('country') or '').capitalize(), 'period': f"{rows[0]['year']}-{rows[-1]['year']}",
            'verdict': g.get('verdict') or '', 'forest_cutoff': num(g.get('forest_cutoff_ha'), 1), 'forest_last': num(g.get('forest_last_ha'), 1),
            'last_year': str(g.get('forest_last_year') or rows[-1]['year']),
            'rows': [{'year': str(y), 'cut': y == 2020, 'bosque': num(by[y]['groups_ha']['bosque'], 1), 'natural': num(by[y]['groups_ha']['natural'], 1),
                      'plantacion': num(by[y]['groups_ha']['plantacion'], 1), 'uso': num(by[y]['groups_ha']['uso'], 1),
                      'agua': num(by[y]['groups_ha']['agua'], 1)} for y in pick],
            'reading': mb.get('reading') or ''}


def eudr_data(lot, establishment, sust, generated=None, readiness=None):
    import hashlib
    vertices = lot.get('vertices') or []
    if len(vertices) < 3:
        raise ValueError('El informe necesita el polígono del lote')
    de = (sust or {}).get('deforestation') or {}
    cb = (sust or {}).get('carbon') or {}
    area = lot.get('areaHa') or de.get('area_ha')
    g = datetime.now(timezone.utc)
    gen = generated or f'{g.day:02d} {MONTHS[g.month - 1]} {g.year} · {g:%H:%M} UTC'
    gj = geojson_lot(vertices, lot.get('name') or 'Lote', area)
    gtxt = json.dumps(gj, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    ring = gj['features'][0]['geometry']['coordinates'][0]
    cen = lot_centroid(ring)
    verdict = str(de.get('verdict') or 'sin dato')
    vt = 'ok' if verdict.startswith('sin pérdida') else 'idle' if verdict == 'sin dato' else 'warn'
    base_y, last_y = de.get('baseline_year'), de.get('last_year')
    ser = de.get('series') or []
    tb = next((r for r in ser if r.get('year') == base_y), {}); tl = next((r for r in ser if r.get('year') == last_y), {})
    pct = lambda v: '—' if v is None else num(v * 100, 1) + ' %'
    detail = (f"Árboles en el lote: {pct(tb.get('trees'))} en {base_y} y {pct(tl.get('trees'))} en {last_y}. "
              f"Pérdida estimada {num(de.get('tree_loss_ha'), 2)} ha ({num(de.get('tree_change_pp'), 1)} puntos de cobertura)."
              + (f" Variación interanual del mapa antes de 2020: ±{num(de['map_noise_pp'], 1)} puntos." if de.get('map_noise_pp') is not None else '')
              + (' La pérdida se sostiene en los dos últimos años.' if de.get('loss_persistent') else '')) if ser else \
             'No hubo datos de cobertura suficientes para evaluar el lote.'
    series = [{'year': r['year'], 'cut': r['year'] == 2020, 'trees': pct(r.get('trees')),
               'trees_ha': num((r.get('trees') or 0) * (area or 0), 1) if r.get('trees') is not None and area else '—',
               'rangeland': pct(r.get('rangeland')), 'crops': pct(r.get('crops')), 'water': pct(r.get('water'))} for r in ser]
    wc = ''
    if de.get('worldcover_tree_2020') is not None:
        wc = (f"ESA WorldCover (otro sensor y otro modelo de clasificación) da {pct(de['worldcover_tree_2020'])} de cobertura arbórea en 2020 "
              f"y {pct(de.get('worldcover_tree_2021'))} en 2021 para el mismo polígono.")
    carbon = []
    if cb.get('soc_t_ha') is not None:
        carbon.append({'label': 'Carbono orgánico del suelo · 0-30 cm', 'value': f"{num(cb['soc_t_ha'], 1)} t C/ha",
                       'detail': f"Rango probable {num((cb.get('soc_t_ha_range') or [None])[0], 0)}–{num((cb.get('soc_t_ha_range') or [None, None])[1], 0)} t C/ha (SoilGrids, percentiles 5 y 95)"
                                 + (f" · punto {cb['point_used']['note']}" if (cb.get('point_used') or {}).get('note') else '')})
    if cb.get('soc_total_t'):
        carbon.append({'label': 'Stock del lote', 'value': f"{num(cb['soc_total_t'], 0)} t C",
                       'detail': f"Equivale a {num(cb.get('soc_total_tco2e'), 0)} t CO₂e (factor 44/12)"})
    if cb.get('herd'):
        h = cb['herd']
        carbon.append({'label': f"Emisiones del rodeo · {h['heads']} cabezas", 'value': f"{num(h['co2e_t_year'], 0)} t CO₂e/año",
                       'detail': f"{num(h['ch4_t_year'], 1)} t CH₄/año · {num(h['ef_kg_ch4_head'], 0)} kg CH₄/cabeza/año · GWP {num(h['gwp'], 0)}"})
        if h.get('years_equiv_soc'):
            carbon.append({'label': 'Relación stock / emisiones', 'value': f"{num(h['years_equiv_soc'], 0)} años",
                           'detail': 'Años de emisiones del rodeo equivalentes al carbono que guarda el suelo del lote (referencia, no balance).'})
    coords = []
    pairs = ring[:-1]
    half = (len(pairs) + 1) // 2
    for i in range(half):
        a = pairs[i]; b = pairs[i + half] if i + half < len(pairs) else None
        coords += [str(i + 1), f'{a[1]:.6f}', f'{a[0]:.6f}']
        coords += [str(i + half + 1), f'{b[1]:.6f}', f'{b[0]:.6f}'] if b else ['', '', '']
    return {
        'title': f"DOTS · Verificación de libre de deforestación · {lot.get('name') or 'Lote'}",
        'generated': gen, 'establishment': establishment or 'Establecimiento sin nombre declarado',
        'cutoff': '31/12/2020',
        'verdict': {'text': verdict, 'tone': vt, 'detail': detail},
        'lot': {'name': lot.get('name') or 'Lote', 'shape': shape(vertices), 'facts': [
            ['Superficie', f"{num(area, 2)} ha" if area else '—'],
            ['Perímetro', f"{num(lot.get('perimeterKm'), 2)} km" if lot.get('perimeterKm') else '—'],
            ['Centroide (lat, lon)', f'{cen[1]:.6f}, {cen[0]:.6f}'],
            ['Vértices del polígono', str(len(pairs))],
            ['Sistema de referencia', 'WGS84 (EPSG:4326)'],
            ['Origen del límite', 'Fields of the World (automático)' if lot.get('ftw') else 'Dibujado por el usuario'],
        ]},
        'series': series,
        'series_note': ('Porcentaje del polígono en cada clase según Impact Observatory 10 m (Sentinel-2). '
                        'La fila resaltada es el año de corte (2020).'),
        'worldcover': wc,
        'mapbiomas': _mapbiomas_block((sust or {}).get('mapbiomas')),
        'movements': _movements(lot.get('movements')),
        'criteria': [
            ['Sin pérdida detectada', 'Pérdida estimada menor a 0,5 ha o variación de cobertura arbórea mayor a −1 punto entre 2020 y el último año.'],
            ['Pérdida menor · revisar', 'Pérdida estimada entre 0,5 y 5 ha, o mayor pero dentro del doble de la variación interanual del mapa, o que no se sostiene en los dos últimos años: puede ser poda, sombra, error de clasificación o desmonte puntual.'],
            ['Requiere verificación', 'Pérdida de 5 ha o más, mayor que el doble de la variación interanual del mapa antes de 2020 y sostenida en los dos últimos años: se recomienda revisar imágenes de alta resolución y la documentación del establecimiento.'],
        ],
        'carbon': carbon,
        'carbon_note': ('El stock de carbono proviene de un modelo global a 250 m (ISRIC SoilGrids) y sirve como línea de base; un proyecto de bonos '
                        'de carbono requiere muestreo de suelo. Emisiones: IPCC 2006 Nivel 1 (fermentación entérica, otros bovinos, Latinoamérica), GWP100 de IPCC AR6.'),
        'framework': [
            'El Reglamento (UE) 2023/1115 sobre productos libres de deforestación alcanza, entre otros, al ganado bovino y la carne vacuna; el acto delegado de julio de 2026 dejó fuera del alcance a los cueros. '
            'Exige que los productos no provengan de tierras deforestadas después del 31 de diciembre de 2020, que se hayan producido conforme a la '
            'legislación del país de origen y que estén cubiertos por una declaración de debida diligencia.',
            'Tras las modificaciones de 2025, las obligaciones se aplican desde el 30 de diciembre de 2026 para operadores grandes y medianos, y desde '
            'el 30 de junio de 2027 para microempresas y personas humanas. La geolocalización debe expresarse con al menos seis decimales; para el ganado '
            'se admite la ubicación de cada establecimiento donde se crió el animal. DOTS entrega además el polígono completo del lote como evidencia más sólida.',
            'Este documento aporta evidencia técnica de teledetección para esa debida diligencia. La evaluación de legalidad, la trazabilidad de los animales '
            'y la declaración ante el sistema de información de la Unión Europea corresponden al operador.',
        ],
        'sources': [
            ['Impact Observatory 10 m Annual LULC v2', 'Clasificación anual 2017-2023 a partir de Sentinel-2; clase 2 = árboles. Licencia CC-BY 4.0. Vía Microsoft Planetary Computer.'],
            ['ESA WorldCover 10 m', 'Clasificación 2020 y 2021 (Sentinel-1 y Sentinel-2); clase 10 = cobertura arbórea. Licencia CC-BY 4.0.'],
            ['Cálculo DOTS', 'Fracción de píxeles de cada clase dentro del polígono (estadística zonal en el servidor de datos) × superficie del lote.'],
            ['MapBiomas', 'Clasificación anual de uso y cobertura del suelo desde 1985 a partir de Landsat (30 m), hecha por la red MapBiomas de cada país. Licencia CC BY 4.0. Vía Google Earth Engine.'],
            ['ISRIC SoilGrids', 'Stock de carbono orgánico 0-30 cm, 250 m, media y percentiles 5 y 95.'],
            ['IPCC', 'Directrices 2006, Vol. 4, Cap. 10, cuadro 10.11 (56 kg CH₄/cabeza/año) y AR6 (GWP100 del metano = 27).'],
        ],
        'limits': [
            'Los mapas de 10 m pueden confundir monte abierto con pastizal arbolado o sombra; un cambio pequeño no implica desmonte.',
            'Los mapas anuales reflejan el estado de cada año, no la fecha exacta de un cambio dentro del año.',
            'La verificación cubre el polígono declarado; animales que pasaron por otros establecimientos requieren la geolocalización de cada uno.',
            'No reemplaza la verificación documental ni, cuando haya alertas, la revisión con imágenes de mayor resolución o la visita a campo.',
        ],
        'readiness': readiness_block(readiness, de, area) if readiness else None,
        'coords': coords,
        'geo_note': 'Vértices del polígono en orden. El mismo polígono se entrega en un archivo GeoJSON con el formato del sistema de información de la UE (TRACES): WGS84, longitud y latitud, 6 decimales, propiedades ProductionPlace, ProducerCountry y Area.',
        'geo_hash': hashlib.sha256(gtxt.encode()).hexdigest(),
        'geojson': gj,
        'attributions': ('Datos: Impact Observatory, Esri y Microsoft (10 m Annual LULC, CC-BY 4.0); ESA WorldCover (CC-BY 4.0); ISRIC SoilGrids; '
                         'IPCC. Procesamiento: Microsoft Planetary Computer. Tipografía IBM Plex (SIL OFL). Documento compuesto con Typst.'),
    }


def eudr_pdf(lot, establishment, sust, readiness=None):
    import typst
    data = eudr_data(lot, establishment, sust, readiness=readiness)
    gj = data.pop('geojson')
    out = typst.compile(EUDR_TEMPLATE, root=BASE, font_paths=[FONTS], ignore_system_fonts=True,
                        sys_inputs={'data': json.dumps(data, ensure_ascii=False, default=str)})
    return out, gj, data['geo_hash']
