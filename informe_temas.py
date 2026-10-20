"""informe_temas v1.0 — informe y newsletter genéricos por tema.

Toma una lista de temas (``temas.py``), resuelve cada uno con su procedencia (de dónde viene y
cómo se obtuvo) y arma un documento que sale como **PDF** (ReportLab) o como **HTML** para la
newsletter. Es genérico: sirve para crecidas, inundaciones, cultivos, NDVI, suelo, ganado…
Un tema sin fuente responde 'sin dato' con su motivo; nunca se inventa.
"""
import io
from datetime import datetime, timezone

import temas as tm


def build(ids, lat=None, lon=None, params=None, name='DOTS'):
    poly = (params or {}).get('poligono') or (params or {}).get('polygon')
    zone = None
    if isinstance(poly, list) and poly:
        pts = [(float(x[0]), float(x[1])) for x in poly if isinstance(x, (list, tuple)) and len(x) >= 2]
        if pts:
            c = [sum(a for a, _ in pts) / len(pts), sum(b for _, b in pts) / len(pts)]
            zone = {'vertices': len(pts), 'centroid': [round(c[0], 4), round(c[1], 4)]}
            if lat is None or lon is None:
                lat, lon = c
    blocks = []
    for tid in ids:
        try:
            blocks.append(tm.resolve(tid, lat, lon, params))
        except KeyError:
            blocks.append({'id': tid, 'title': tid, 'status': 'sin dato',
                           'error': f'Tema desconocido: {tid}', 'how': '', 'organism': '', 'source_url': ''})
        except Exception as e:
            t = tm.TEMAS.get(tid, {})
            blocks.append({'id': tid, 'title': t.get('title', tid), 'organism': t.get('organism', ''),
                           'how': t.get('how', ''), 'source_url': t.get('source_url', ''),
                           'status': 'sin dato', 'data': None, 'error': f'La fuente no respondió ({type(e).__name__}).'})
    got = sum(1 for b in blocks if b.get('status') == 'recibido')
    return {'engine': 'DOTS temas', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'name': name, 'point': [lat, lon] if lat is not None else None, 'zone': zone,
            'temas': ids, 'received': got, 'total': len(blocks), 'blocks': blocks}


# ───────────────────────────── resúmenes por tema ─────────────────────────────

def _num(v, d=0):
    try:
        return f'{float(v):.{d}f}'
    except (TypeError, ValueError):
        return None


def summary(block):
    """Líneas legibles del dato de un tema. Si no hay formato específico, lista las claves."""
    tid, d = block.get('id'), block.get('data')
    if block.get('status') != 'recibido' or d is None:
        return [block.get('error') or 'Sin dato disponible.']
    try:
        if tid == 'nino':
            ph = d.get('phase') or {}
            out = [f"Fase: {ph.get('es') or ph.get('en') or 'sin dato'}"]
            for k, lab in (('oni', 'ONI'), ('roni', 'RONI'), ('weekly', 'Niño 3.4 semanal')):
                v = d.get(k) or {}
                an = v.get('anom', v.get('nino34'))
                if an is not None:
                    out.append(f'{lab}: {_num(an, 2)}')
            st = (d.get('status') or {})
            if st.get('es'):
                out.append(f'Aviso CPC: {st["es"]}')
            return out
        if tid == 'crecidas':
            sts = [s for s in d.get('stations') or [] if s.get('status') == 'recibido']
            lv = {}
            for s in sts:
                k = (s.get('ina') or {}).get('level') or s.get('level') or 'sin nivel'
                lv[k] = lv.get(k, 0) + 1
            out = [f'{len(sts)} puertos con dato. Niveles: ' + ', '.join(f'{v} {k}' for k, v in sorted(lv.items())) if sts else 'Sin dato de caudal.']
            top = sorted([s for s in sts if (s.get('ina') or {}).get('height') is not None],
                         key=lambda s: -((s.get('ina') or {}).get('height') or 0))[:5]
            for s in top:
                i = s.get('ina') or {}
                out.append(f"{s['place']}: {_num(i.get('height'), 2)} m ({i.get('level') or 'sin nivel'}), "
                           f"tendencia {_num(i.get('trend_m_day'), 2)} m/día")
            return out
        if tid == 'crecidas':
            stations = d.get('stations') or []
            out = [f"Estaciones incluidas: {len(stations)}. Cuencas y ríos: Paraná, Uruguay, Paraguay y tributarios según cobertura disponible."]
            for stn in stations:
                ina = stn.get('ina') or {}
                level = ina.get('level') or stn.get('level') or 'sin nivel'
                height = ina.get('height', stn.get('height'))
                trend = ina.get('trend_m_day', stn.get('trend_m_day'))
                out.append(f"{stn.get('place', 'Estación')} (río {stn.get('river', 'sin dato')}): altura {_num(height, 2) or 'sin dato'} m; nivel {level}; tendencia {_num(trend, 2) or 'sin dato'} m/día.")
            travels = d.get('travel') or []
            valid = 0
            for chain in travels if isinstance(travels, list) else []:
                if not isinstance(chain, dict):
                    continue
                out.append(f"Propagación: {chain.get('name') or 'tramo sin nombre'}; pico en cabecera: {chain.get('head_peak') or 'sin dato'}.")
                for row in chain.get('rows') or []:
                    if row.get('days_from_head') is not None and row.get('arrival'):
                        valid += 1
                        out.append(f"Llegada orientativa a {row.get('place')}: {row['arrival']} (desfase acumulado {row['days_from_head']} días; estimación basada en correlación histórica).")
            if not valid:
                out.append('Tiempo de llegada: sin estimación respaldada por desfases históricos y fecha de pico disponible.')
            out.append('Las fechas de llegada son orientativas, no horarios de evacuación ni pronósticos oficiales.')
            return out
        if tid == 'amenaza':
            out = [d.get('reading')] if d.get('reading') else []
            for x in d.get('return_periods') or []:
                if x.get('depth_m') is not None:
                    out.append(f"RP {x['rp_years']} años: {_num(x['depth_m'], 2)} m de agua")
            for e in d.get('exposed') or []:
                if e.get('people'):
                    out.append(f"RP {e['rp_years']} años: ~{e['people']} personas expuestas en {_num(d.get('radius_km'))} km")
            h = d.get('history') or {}
            if h.get('events') is not None:
                per = h.get('period') or []
                out.append(f"Histórico {per[0]}-{per[1]}: {h['events']} eventos de crecida en la zona")
            return out or ['Sin dato de amenaza de crecida.']
        if tid == 'poblaciones':
            out = [f"Localidad: {d.get('place') or 'sin dato'} · río {d.get('river') or 'sin dato'}",
                   f"Radio de estudio: {d.get('radius_km', 15)} km",
                   f"Población total estimada: {d.get('total') if d.get('total') is not None else 'sin dato'} personas",
                   f"Menores de 5 años: {d.get('under5_total') if d.get('under5_total') is not None else 'sin dato'}",
                   f"Mayores de 65 años: {d.get('over65_total') if d.get('over65_total') is not None else 'sin dato'}"]
            for b in d.get('bands') or []:
                out.append(f"HAND hasta {b.get('up_to_m')} m: {b.get('people') if b.get('people') is not None else 'sin dato'} personas; menores de 5: {b.get('under5') if b.get('under5') is not None else 'sin dato'}; mayores de 65: {b.get('over65') if b.get('over65') is not None else 'sin dato'}")
            for sc in d.get('scenarios') or []:
                out.append(f"{sc.get('label')}: {sc.get('people') if sc.get('people') is not None else 'sin dato'} personas (subida {sc.get('rise_m')} m; menores de 5: {sc.get('under5')}; mayores de 65: {sc.get('over65')})")
            out.append("Fuente: MERIT Hydro HAND v1.0.1 y WorldPop 2020. Estimación de exposición, no pronóstico hidráulico ni conteo de evacuados.")
            return out
        if tid == 'clima':
            cur = d.get('current') or {}
            return [f"Ahora: {_num(cur.get('temperature_2m'), 1)} °C, HR {_num(cur.get('relative_humidity_2m'))} %",
                    f"Lluvia 7 días: {_num(sum(x for x in (d.get('daily') or {}).get('precipitation_sum') or [] if x is not None), 1)} mm"]
        if tid == 'suelo':
            return [f'{len(d.get("layers") or d.get("properties", {}).get("layers") or [])} capas de suelo recibidas']
        if tid == 'enso_sudamerica':
            return [f'{len(d.get("places") or d.get("localidades") or [])} localidades de referencia']
    except Exception:
        pass
    return [f'{len(d)} campos recibidos' if isinstance(d, (dict, list)) else 'Dato recibido']


# ───────────────────────────── PDF (ReportLab) ─────────────────────────────

def pdf(doc):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    from xml.sax.saxutils import escape
    out = io.BytesIO()
    d = SimpleDocTemplate(out, pagesize=landscape(A4), rightMargin=12 * mm, leftMargin=12 * mm,
                          topMargin=12 * mm, bottomMargin=12 * mm,
                          title=f'DOTS — Informe de temas ({doc.get("name", "DOTS")})')
    st = getSampleStyleSheet()
    cyan, navy, muted = colors.HexColor('#16b9c4'), colors.HexColor('#10232d'), colors.HexColor('#526a73')
    st.add(ParagraphStyle(name='Cover', parent=st['Title'], fontSize=20, leading=24, textColor=navy, spaceAfter=5))
    st.add(ParagraphStyle(name='Kicker', parent=st['BodyText'], fontSize=9, leading=11, textColor=cyan, fontName='Helvetica-Bold', spaceAfter=4))
    st.add(ParagraphStyle(name='Section', parent=st['Heading2'], fontSize=14, leading=17, textColor=navy, spaceBefore=10, spaceAfter=6))
    st.add(ParagraphStyle(name='Small2', parent=st['BodyText'], fontSize=8, leading=10, textColor=muted, wordWrap='LTR'))

    story = [Paragraph('DOTS / INTELIGENCIA TERRITORIAL', st['Kicker']), Paragraph('Informe técnico territorial y ambiental', st['Cover']),
             Paragraph(f'{doc.get("name", "DOTS")} · {doc.get("received")}/{doc.get("total")} temas con dato', st['Heading2']),
             Paragraph('Generado ' + doc.get('generated_at', '')[:19] + ' UTC', st['Small2'])]
    if doc.get('zone'):
        z = doc['zone']
        story.append(Paragraph(f'Zona delimitada: {z["vertices"]} vértices · centroide {z["centroid"][0]}, {z["centroid"][1]}', st['Small2']))
    story += [
        Spacer(1, 7),
        Paragraph('DOTS | Sistema de Inteligencia Territorial, Ambiental y Climática', st['Section']),
        Paragraph('<b>Datos · Observación · Territorio · Sistemas.</b> DOTS integra observación satelital, '
                  'telemetría hidrometeorológica de redes disponibles, información geoespacial y modelos '
                  'ambientales para analizar el territorio, las cuencas y la exposición a amenazas. '
                  'No se limita a recopilar mediciones: combina fuentes trazables para elaborar escenarios '
                  'e informes de apoyo a la prevención y la toma de decisiones.', st['BodyText']),
        Spacer(1, 5),
        Paragraph('<b>Telemetría y fuentes.</b> Las alturas de ríos, caudales, precipitaciones y demás '
                  'mediciones se atribuyen a los organismos y redes que las suministran. '
                  'Su integración no implica que DOTS sea propietario u operador de esas estaciones. '
                  'Los datos satelitales y demográficos se identifican en cada sección.', st['BodyText']),
        Spacer(1, 5),
        Paragraph('<b>Interpretación.</b> Los escenarios y la población potencialmente expuesta son '
                  'estimaciones sujetas a resolución, fecha y supuestos de cada modelo; no equivalen '
                  'a personas efectivamente inundadas o evacuadas. Las instrucciones de emergencia '
                  'corresponden a las autoridades competentes.', st['BodyText']),
        Spacer(1, 6),
        Paragraph('<b>Dirección institucional:</b> Álvaro Fontana · DOTS', st['Small2']),
    ]
    story.append(Spacer(1, 8))

    for b in doc.get('blocks', []):
        story.append(Paragraph(f"{b.get('title', b.get('id'))}  <font size=8 color='#526a73'>({b.get('organism') or 'sin organismo'})</font>", st['Section']))
        rows = [['Dato', 'Valor']] + [[k, v] for k, v in zip(('estado', 'procedencia'), (b.get('status'), b.get('how') or '—'))]
        t = Table(rows, colWidths=[60 * mm, 200 * mm])
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), navy), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                               ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 8),
                               ('GRID', (0, 0), (-1, -1), .25, colors.HexColor('#c4d1d5')), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story += [t, Spacer(1, 4)]
        for line in summary(b):
            story.append(Paragraph('• ' + line, st['BodyText']))
        if b.get('source_url'):
            story.append(Paragraph('Fuente: ' + str(b['source_url']), st['Small2']))
        story.append(Spacer(1, 6))

    # Gráficos generados solo con cifras presentes en las fuentes consultadas.
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    for b in doc.get('blocks', []):
        data = b.get('data') or {}
        if b.get('status') != 'recibido' or not isinstance(data, dict):
            continue
        vals, labels, title = [], [], None
        if b.get('id') == 'poblaciones':
            for band in data.get('bands') or []:
                try:
                    val = float(band.get('people'))
                    if val >= 0:
                        vals.append(val); labels.append(str(band.get('up_to_m')) + ' m')
                except (TypeError, ValueError):
                    continue
            title = 'Población potencialmente expuesta por franja HAND'
        elif b.get('id') == 'crecidas':
            for station in data.get('stations') or []:
                try:
                    val = float((station.get('ina') or {}).get('height'))
                    if val >= 0:
                        vals.append(val); labels.append(str(station.get('place') or '')[:14])
                except (TypeError, ValueError):
                    continue
            title = 'Alturas hidrométricas disponibles (m) — no comparables como riesgo entre puertos'
        if not vals:
            continue
        vals, labels = vals[:12], labels[:12]
        drawing = Drawing(700, 245)
        chart = VerticalBarChart()
        chart.x, chart.y, chart.width, chart.height = 48, 55, 615, 150
        chart.data = [vals]
        chart.categoryAxis.categoryNames = labels
        chart.categoryAxis.labels.fontSize = 7
        chart.categoryAxis.labels.angle = 25
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max(vals) * 1.15 if max(vals) else 1
        chart.bars[0].fillColor = cyan
        drawing.add(chart)
        story.append(Paragraph(title, st['Section']))
        story.append(drawing)
        story.append(Paragraph('Fuente y fecha de consulta: ver sección de trazabilidad. Valores sujetos a cobertura y disponibilidad.', st['Small2']))

    story += [PageBreak(), Paragraph('Trazabilidad', st['Section'])]
    rows = [['Tema', 'Organismo', 'Estado', 'Consultado (UTC)', 'URL']]
    for b in doc.get('blocks', []):
        rows.append([Paragraph(str(b.get('title', '')), st['Small2']), Paragraph(str(b.get('organism', '')), st['Small2']),
                     b.get('status', ''), (b.get('consulted_at') or b.get('requested_at') or '')[:19],
                     Paragraph(str(b.get('source_url', ''))[:70], st['Small2'])])
    tt = Table(rows, repeatRows=1, colWidths=[50 * mm, 45 * mm, 22 * mm, 35 * mm, 108 * mm])
    tt.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), navy), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                            ('FONTSIZE', (0, 0), (-1, -1), 7), ('GRID', (0, 0), (-1, -1), .25, colors.HexColor('#c4d1d5')),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(tt)
    def institutional_page(canvas, document):
        canvas.saveState()
        width, height = landscape(A4)
        canvas.setFillColor(navy)
        canvas.rect(0, height - 15 * mm, width, 15 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 10)
        canvas.drawString(12 * mm, height - 9.5 * mm, 'DOTS  /  INTELIGENCIA TERRITORIAL')
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(width - 12 * mm, height - 9.5 * mm, 'INFORME TÉCNICO')
        canvas.setStrokeColor(colors.HexColor('#c4d1d5'))
        canvas.line(12 * mm, 13 * mm, width - 12 * mm, 13 * mm)
        canvas.setFillColor(muted)
        canvas.setFont('Helvetica', 7)
        canvas.drawString(12 * mm, 8 * mm, 'DOTS · Dirección: Álvaro Fontana · Fuentes y limitaciones en el documento')
        canvas.drawRightString(width - 12 * mm, 8 * mm, f'Página {document.page}')
        canvas.restoreState()
    d.topMargin = 21 * mm
    d.bottomMargin = 19 * mm
    d.build(story, onFirstPage=institutional_page, onLaterPages=institutional_page)
    return out.getvalue()


# ───────────────────────────── HTML (newsletter) ─────────────────────────────

def html(doc, site='https://observatorio-agro.vercel.app'):
    cols = {'ok': '#1b7f4b', 'warn': '#b26a00', 'risk': '#b42318', 'idle': '#526a73'}
    parts = [f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>DOTS — {doc.get('name','Newsletter')}</title></head>
<body style="margin:0;background:#eef2f3;font-family:Segoe UI,Arial,sans-serif;color:#10232d">
<div style="max-width:640px;margin:0 auto;background:#fff">
<div style="background:#10232d;padding:20px 24px"><div style="color:#16b9c4;font-size:12px;letter-spacing:.14em;font-weight:700">DOTS / INTELIGENCIA TERRITORIAL</div>
<div style="color:#fff;font-size:22px;font-weight:800;margin-top:4px">{doc.get('name','Informe')}</div>
<div style="color:#9fb4bb;font-size:12px;margin-top:4px">{doc.get('received')}/{doc.get('total')} temas con dato · {doc.get('generated_at','')[:16]} UTC{' · zona '+str(doc['zone']['vertices'])+' vértices' if doc.get('zone') else ''}</div></div>
<div style="padding:20px 24px">"""]

    for b in doc.get('blocks', []):
        tone = 'ok' if b.get('status') == 'recibido' else 'idle'
        parts.append(f"""<div style="margin-bottom:22px;border-top:3px solid {cols.get(tone,'#526a73')};padding-top:10px">
<div style="font-size:17px;font-weight:700">{b.get('title', b.get('id'))}</div>
<div style="font-size:12px;color:#526a73;margin:2px 0 8px">{b.get('organism') or ''} · {b.get('status')}</div>
<ul style="margin:0 0 8px 18px;padding:0;font-size:14px;line-height:1.5">{''.join(f'<li>{line}</li>' for line in summary(b))}</ul>
<div style="font-size:12px;color:#526a73">{b.get('how') or ''}</div>
<div style="font-size:11px;color:#93a6ad;margin-top:4px">Fuente: {b.get('source_url') or ''}</div></div>""")

    parts.append(f"""</div>
<div style="background:#10232d;color:#9fb4bb;font-size:11px;padding:16px 24px;line-height:1.5">
DOTS — Sistema de Inteligencia Territorial, Ambiental y Climática. Observación satelital, telemetría y análisis geoespacial. Dirección: Álvaro Fontana. Cada dato viaja con su organismo, método y hora de consulta.
Un tema sin fuente se marca "sin dato"; no se estima.<br><a href="{site}" style="color:#16b9c4">{site}</a></div>
</div></body></html>""")
    return ''.join(parts)
