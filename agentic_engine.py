"""DOTS Agentic v0.7 - Motor corregido y ejecutable.
Respeta arquitectura v1.5: lote como unidad de contexto, no inventar datos,
trazabilidad completa, fuentes protegidas marcadas como 'requiere credencial'.
"""
from datetime import datetime, timezone
import io, math
from concurrent.futures import ThreadPoolExecutor, as_completed
import research_connectors as c

QUICK = {
    'integral': 'Informe integral del estado del campo',
    'pasturas': 'Evaluá pasturas y vegetación',
    'agua': 'Analizá agua, lluvia y disponibilidad hídrica',
    'ganado': 'Analizá estrés térmico y entorno del ganado',
    'sequia': 'Evaluá riesgo de sequía e incendio',
    'suelo': 'Analizá humedad y condición del suelo',
    'clima': 'Resumí clima actual y próximos 7 días',
}

def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None

def _intent(prompt):
    p = (prompt or '').lower()
    for key, words in {
        'pasturas': ['pastura', 'vegetación', 'vegetacion', 'ndvi'],
        'agua': ['agua', 'lluvia', 'hídr', 'hidri', 'precipita', 'bebedero'],
        'ganado': ['ganado', 'vaca', 'bovino', 'thi', 'estrés', 'estres'],
        'sequia': ['sequía', 'sequia', 'incendio', 'fuego'],
        'suelo': ['suelo', 'humedad', 'nitrógeno', 'nitrogeno'],
        'clima': ['clima', 'tiempo', 'temperatura', 'pronóstico', 'pronostico'],
    }.items():
        if any(w in p for w in words):
            return key
    return 'integral'

def _thi(t, rh):
    """Temperature-Humidity Index para ganado bovino (NRC, 1971)."""
    if t is None or rh is None:
        return None
    return 1.8 * t + 32 - (0.55 - 0.0055 * rh) * (1.8 * t - 26)

def _quality(source_count, warnings):
    score = min(95, 48 + source_count * 9 - max(0, len(warnings) - 1) * 4)
    return max(20, score)

def analyze(lat, lon, prompt='', polygon=None, ina_id=None, water_assets=None):
    intent = _intent(prompt)
    bundle = c.research_bundle(lat, lon, ina_id)
    extra = {}
    jobs = []

    if intent in ('integral', 'agua', 'sequia'):
        jobs.append(('rios', lambda: c.external(
            'https://flood-api.open-meteo.com/v1/flood',
            {'latitude': lat, 'longitude': lon, 'daily': 'river_discharge', 'forecast_days': 7}
        )))
    if intent in ('integral', 'suelo'):
        jobs.append(('suelo_nitrogeno', lambda: c.external(
            'https://rest.isric.org/soilgrids/v2.0/properties/query',
            {'lat': lat, 'lon': lon, 'property': 'nitrogen', 'depth': '0-5cm', 'value': 'mean'}
        )))
    if intent in ('integral', 'pasturas'):
        jobs.append(('escenas_sentinel', lambda: c.scenes(lat, lon)))
    if intent in ('integral', 'sequia'):
        jobs.append(('nasa_firms', lambda: c.firms(lat, lon)))
    if intent in ('integral', 'clima'):
        jobs.append(('enso_global', lambda: c.enso_multisource()))

    if jobs:
        with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as pool:
            futures = {pool.submit(fn): key for key, fn in jobs}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    extra[key] = {'status': 'recibido', 'payload': future.result()}
                except Exception as e:
                    extra[key] = {'status': 'sin dato', 'error': type(e).__name__}

    sources = {**bundle['sources'], **extra}
    clima = sources.get('clima', {}).get('payload', {}).get('data', {})
    cur = clima.get('current', {})
    hourly = clima.get('hourly', {})
    daily = clima.get('daily', {})

    t = _num(cur.get('temperature_2m'))
    rh = _num(cur.get('relative_humidity_2m'))
    thi = _thi(t, rh)
    rain = [_num(x) or 0 for x in daily.get('precipitation_sum', [])[:7]]
    et = [_num(x) or 0 for x in daily.get('et0_fao_evapotranspiration', [])[:7]]
    soilvals = hourly.get('soil_moisture_0_to_1cm') or []
    soil = next((_num(v) for v in soilvals if _num(v) is not None), None)

    findings = []
    warnings = []
    recommendations = []
    water_assets = water_assets or []

    if water_assets:
        kinds = {}
        for a in water_assets:
            kinds[a.get('type', 'otro')] = kinds.get(a.get('type', 'otro'), 0) + 1
        findings.append({
            'topic': 'Agua / infraestructura',
            'status': 'inventario declarado',
            'text': f'{len(water_assets)} elementos registrados en el lote: '
                    + ', '.join(f'{v} {k}' for k, v in kinds.items())
                    + '. Se consideran infraestructura declarada, no detección satelital.'
        })

    if t is not None:
        findings.append({
            'topic': 'Clima',
            'status': 'medido/modelado',
            'text': f'Temperatura actual {t:.1f} °C y humedad relativa {rh:.0f} %.'
                    if rh is not None
                    else f'Temperatura actual {t:.1f} °C.'
        })

    if rain:
        findings.append({
            'topic': 'Agua',
            'status': 'pronóstico',
            'text': f'Precipitación prevista a 7 días: {sum(rain):.1f} mm; ET₀ acumulada: {sum(et):.1f} mm.'
        })

    if soil is not None:
        findings.append({
            'topic': 'Suelo',
            'status': 'modelado',
            'text': f'Humedad superficial modelada: {soil:.3f} m³/m³.'
        })

    if thi is not None:
        level = ('bajo' if thi < 72
                 else 'atención' if thi < 79
                 else 'alto' if thi < 84
                 else 'severo')
        findings.append({
            'topic': 'Ganado',
            'status': 'derivado',
            'text': f'Índice THI {thi:.1f}: nivel {level}. Se calcula con temperatura y humedad, no es diagnóstico veterinario.'
        })
        if thi >= 79:
            recommendations.append(
                'Priorizar sombra, agua disponible y observación del ganado durante las horas de mayor carga térmica.'
            )

    if intent in ('integral', 'pasturas'):
        scenes = sources.get('escenas_sentinel', {}).get('payload', {}).get('data', {}).get('features', [])
        if scenes:
            cloud = _num(scenes[0].get('properties', {}).get('eo:cloud_cover'))
            findings.append({
                'topic': 'Satélite',
                'status': 'catálogo',
                'text': f'Hay escenas Sentinel-2 recientes disponibles'
                        + (f'; nubosidad de escena más reciente {cloud:.1f} %.' if cloud is not None else '.')
            })
        warnings.append(
            'NDVI/EVI y biomasa todavía no se calculan desde bandas raster; '
            'DOTS no calificará las pasturas hasta incorporar ese procesamiento.'
        )

    if intent in ('integral', 'agua'):
        warnings.append(
            'La lluvia y el caudal modelados no demuestran por sí solos la existencia '
            'ni el estado de bebederos dentro del lote.'
        )

    if intent in ('integral', 'ganado'):
        warnings.append(
            'No hay inventario ni sensores de animales conectados; '
            'no se infiere cantidad o ubicación de ganado desde la imagen base.'
        )

    enso_src = sources.get('enso_global', {})
    if intent in ('integral', 'clima'):
        ed = (enso_src.get('payload', {}).get('data', {})
              if enso_src.get('status') == 'recibido' else {})
        received_enso = [k for k, v in ed.items() if v.get('status') == 'recibido']
        if received_enso:
            findings.append({
                'topic': 'ENSO global',
                'status': 'consenso multifuente',
                'text': f'Consulta ENSO contrastada en {len(received_enso)} centros: '
                        + ', '.join(received_enso)
                        + '. DOTS conserva cada fuente por separado y no convierte una discrepancia en falsa certeza.'
            })
        else:
            warnings.append('Las fuentes ENSO internacionales no respondieron en esta consulta; el informe no inventa un estado ENSO.')

    firms_src = sources.get('nasa_firms', {})
    if intent in ('integral', 'sequia'):
        if firms_src.get('status') == 'recibido':
            fd = firms_src.get('payload', {}).get('data', {})
            det = fd.get('detections', []) or []
            nearest = None
            for r in det:
                try:
                    la, lo = float(r.get('latitude')), float(r.get('longitude'))
                    dy = (la - lat) * 111.32
                    dx = (lo - lon) * 111.32 * math.cos(math.radians(lat))
                    dist = math.hypot(dx, dy)
                    nearest = dist if nearest is None or dist < nearest else nearest
                except (TypeError, ValueError):
                    pass
            extra_txt = (f' La detección más próxima está a aproximadamente {nearest:.1f} km del centro de análisis.'
                         if nearest is not None else '')
            findings.append({
                'topic': 'Incendios / NASA FIRMS',
                'status': 'observado por sensor',
                'text': (f"NASA FIRMS / {fd.get('sensor', 'VIIRS')} devolvió {len(det)} detecciones térmicas "
                         f"en la ventana consultada de {fd.get('days', 3)} días.{extra_txt} "
                         f"Cero detecciones no equivale a riesgo de incendio nulo.")
            })
            if det:
                recommendations.append(
                    'Revisar las detecciones térmicas FIRMS y su distancia al lote; '
                    'confirmar en terreno o con autoridades antes de atribuirlas a un incendio activo.'
                )
        else:
            warnings.append('NASA FIRMS no respondió en esta consulta; no se interpreta la falla como ausencia de focos térmicos.')

    metrics = []
    if t is not None:
        metrics.append({
            'variable': 'Temperatura', 'value': round(t, 1), 'unit': '°C',
            'reference': 'Contextual: estación, raza y categoría animal',
            'reading': 'Usar junto con humedad, radiación y THI',
            'kind': 'observado/modelado'
        })
    if rh is not None:
        metrics.append({
            'variable': 'Humedad relativa', 'value': round(rh, 0), 'unit': '%',
            'reference': 'Contextual; no se interpreta aislada',
            'reading': 'Componente del estrés térmico',
            'kind': 'observado/modelado'
        })
    if thi is not None:
        r = 'Confort <72 | atención 72-78 | alto 79-83 | severo >=84'
        metrics.append({
            'variable': 'THI bovino', 'value': round(thi, 1), 'unit': 'índice',
            'reference': r,
            'reading': ('bajo' if thi < 72
                        else 'atención' if thi < 79
                        else 'alto' if thi < 84
                        else 'severo'),
            'kind': 'derivado'
        })
    if rain:
        bal = sum(rain) - sum(et)
        metrics.append({
            'variable': 'Lluvia 7 días', 'value': round(sum(rain), 1), 'unit': 'mm',
            'reference': 'Comparar con ET₀, histórico local y necesidad de la pastura',
            'reading': f'Balance lluvia-ET₀ {bal:+.1f} mm',
            'kind': 'pronóstico'
        })
        metrics.append({
            'variable': 'ET₀ 7 días', 'value': round(sum(et), 1), 'unit': 'mm',
            'reference': 'Demanda atmosférica; comparar con lluvia y agua del suelo',
            'reading': 'demanda acumulada',
            'kind': 'pronóstico'
        })
    if soil is not None:
        metrics.append({
            'variable': 'Humedad suelo 0-1 cm', 'value': round(soil, 3), 'unit': 'm³/m³',
            'reference': 'Rango útil depende de textura, capacidad de campo y punto de marchitez',
            'reading': 'No clasificar como buena/mala sin propiedades hidráulicas del suelo',
            'kind': 'modelado'
        })

    ns = sources.get('suelo_nitrogeno', {}).get('payload', {}).get('data', {})
    try:
        layers = ns.get('properties', {}).get('layers', [])
        vals = []
        for layer in layers:
            for depth in layer.get('depths', []):
                v = depth.get('values', {}).get('mean')
                if v is not None:
                    vals.append(float(v))
        if vals:
            nv = vals[0]
            metrics.append({
                'variable': 'Nitrógeno total SoilGrids', 'value': round(nv, 1),
                'unit': 'cg/kg (fuente)',
                'reference': 'Sin umbral universal: calibrar por suelo, pastura y análisis de laboratorio',
                'reading': 'Estimación modelada; no equivale a N disponible para la pastura',
                'kind': 'modelado'
            })
            findings.append({
                'topic': 'Suelo / nitrógeno', 'status': 'modelado',
                'text': (f'Nitrógeno total SoilGrids: {nv:.1f} cg/kg (unidad de la fuente, '
                         f'profundidad consultada 0-5 cm). Requiere contraste con análisis de laboratorio; '
                         f'no se interpreta como nitrógeno disponible.')
            })
    except Exception:
        pass

    if intent in ('integral', 'pasturas'):
        scenes = sources.get('escenas_sentinel', {}).get('payload', {}).get('data', {}).get('features', [])
        if scenes:
            cc = _num(scenes[0].get('properties', {}).get('eo:cloud_cover'))
            if cc is not None:
                metrics.append({
                    'variable': 'Nubosidad Sentinel-2', 'value': round(cc, 1), 'unit': '%',
                    'reference': 'Preferible <20% para análisis visual; máscara por píxel obligatoria para índices',
                    'reading': ('favorable' if cc < 20
                                else 'usable con máscara' if cc < 50
                                else 'limitante'),
                    'kind': 'observado por sensor'
                })

    received = sum(1 for s in sources.values() if s.get('status') == 'recibido')
    failed = [k for k, s in sources.items() if s.get('status') != 'recibido']
    if failed:
        warnings.append('Fuentes sin respuesta en esta consulta: ' + ', '.join(failed) + '.')

    score = _quality(received, warnings)

    if sum(rain) < 5 and sum(et) > 15:
        recommendations.append(
            'Seguir la evolución del balance lluvia–ET₀; el pronóstico muestra demanda atmosférica superior al aporte de lluvia.'
        )
    if not recommendations:
        recommendations.append('Mantener seguimiento; no surge una recomendación operativa fuerte con las variables verificadas disponibles.')

    return {
        'version': 'DOTS Agentic 0.7',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'point': [lat, lon],
        'polygon': polygon or None,
        'prompt': prompt or QUICK['integral'],
        'intent': intent,
        'confidence': {
            'score': score,
            'label': 'alta' if score >= 80 else 'media' if score >= 60 else 'limitada',
            'received_sources': received,
            'failed_sources': len(failed)
        },
        'summary': f'Análisis {intent} construido con {received} fuentes recibidas. Confianza {score}/100.',
        'findings': findings,
        'metrics': metrics,
        'recommendations': recommendations,
        'warnings': warnings,
        'evidence': [
            {
                'source': k,
                'status': v.get('status'),
                'consulted_at': v.get('payload', {}).get('consulted_at'),
                'source_url': v.get('payload', {}).get('source_url'),
                'scope': v.get('payload', {}).get('scope')
            }
            for k, v in sources.items()
        ],
        'raw': sources
    }


def pdf_bytes(result, name='Lote'):
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, PageBreak)
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.graphics.shapes import Drawing, PolyLine, String, Rect

    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=landscape(A4),
        rightMargin=12*mm, leftMargin=12*mm,
        topMargin=12*mm, bottomMargin=12*mm,
        title='DOTS / CAMPO — Informe técnico agroambiental'
    )
    st = getSampleStyleSheet()
    cyan = colors.HexColor('#16b9c4')
    navy = colors.HexColor('#10232d')
    muted = colors.HexColor('#526a73')

    st.add(ParagraphStyle(name='Cover', parent=st['Title'],
                          fontSize=22, leading=26, textColor=navy, spaceAfter=5))
    st.add(ParagraphStyle(name='Kicker', parent=st['BodyText'],
                          fontSize=9, leading=11, textColor=cyan,
                          fontName='Helvetica-Bold', spaceAfter=4))
    st.add(ParagraphStyle(name='Small2', parent=st['BodyText'],
                          fontSize=8, leading=10, textColor=muted, wordWrap='LTR'))
    st.add(ParagraphStyle(name='Section', parent=st['Heading2'],
                          fontSize=14, leading=17, textColor=navy,
                          spaceBefore=10, spaceAfter=6))
    st.add(ParagraphStyle(name='CellSmall', parent=st['BodyText'],
                          fontSize=7, leading=9, wordWrap='LTR'))

    point = result['point']
    poly = result.get('polygon') or []
    story = [
        Paragraph('DOTS / CAMPO', st['Kicker']),
        Paragraph('Informe técnico agroambiental', st['Cover']),
        Paragraph(name, st['Heading2']),
        Spacer(1, 6)
    ]

    meta = [
        ['Coordenada', f'{point[0]:.5f}, {point[1]:.5f}'],
        ['Generado', result.get('generated_at', '')[:19] + ' UTC'],
        ['Motor', result.get('version', 'DOTS Agentic')],
        ['Fuentes recibidas', str(result.get('confidence', {}).get('received_sources', '—'))],
        ['Confianza', f"{result.get('confidence', {}).get('score', '—')}/100"]
    ]

    if poly:
        lat0 = sum(x[0] for x in poly) / len(poly) * math.pi / 180
        R = 6378137
        xy = [(R * x[1] * math.pi / 180 * math.cos(lat0),
               R * x[0] * math.pi / 180) for x in poly]
        area = abs(sum(xy[i][0] * xy[(i+1) % len(xy)][1]
                       - xy[(i+1) % len(xy)][0] * xy[i][1]
                       for i in range(len(xy))) / 2) / 10000
        meta.append(['Lote', f'{len(poly)} vértices · {area:.1f} ha'])

    t = Table(meta, colWidths=[55*mm, 200*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4f5')),
        ('TEXTCOLOR', (0, 0), (0, -1), navy),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), .25, colors.HexColor('#b9c9ce')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 5)
    ]))
    story += [t, Spacer(1, 10)]

    story += [
        Paragraph('Resumen ejecutivo', st['Section']),
        Paragraph(result.get('summary', ''), st['BodyText']),
        Spacer(1, 6)
    ]

    story.append(Paragraph('Indicadores', st['Section']))
    mrows = [['Variable', 'Valor', 'Referencia', 'Lectura']]
    for m in result.get('metrics', []):
        val = f"{m.get('value', '—')} {m.get('unit', '')}".strip()
        mrows.append([
            Paragraph(str(m.get('variable', '')), st['CellSmall']),
            Paragraph(val, st['CellSmall']),
            Paragraph(str(m.get('reference', '')), st['CellSmall']),
            Paragraph(str(m.get('reading', '')), st['CellSmall'])
        ])

    if len(mrows) > 1:
        mt = Table(mrows, repeatRows=1, colWidths=[45*mm, 30*mm, 120*mm, 60*mm])
        mt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), navy),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), .25, colors.HexColor('#c4d1d5')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f9f9')])
        ]))
        story += [mt, Spacer(1, 8)]

    story.append(Paragraph('Hallazgos', st['Section']))
    rows = [['Dimensión', 'Tipo', 'Resultado']]
    for x in result.get('findings', []):
        rows.append([
            Paragraph(str(x.get('topic', '')), st['CellSmall']),
            Paragraph(str(x.get('status', '')), st['CellSmall']),
            Paragraph(str(x.get('text', '')), st['CellSmall'])
        ])
    tb = Table(rows, repeatRows=1, colWidths=[40*mm, 35*mm, 180*mm])
    tb.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), .25, colors.HexColor('#c4d1d5')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f9f9')])
    ]))
    story += [tb, Spacer(1, 7)]

    story.append(Paragraph('Recomendaciones', st['Section']))
    for x in result.get('recommendations', []):
        story.append(Paragraph('• ' + x, st['BodyText']))

    story.append(Paragraph('Advertencias', st['Section']))
    for x in result.get('warnings', []):
        story.append(Paragraph('• ' + x, st['BodyText']))

    story += [PageBreak(), Paragraph('Trazabilidad de APIs', st['Section'])]
    ev = result.get('evidence', [])
    ok = sum(1 for e in ev if e.get('status') == 'recibido')
    story.append(Paragraph(
        f'<b>{len(ev)} fuentes · {ok} recibidas · {len(ev)-ok} sin dato.</b>',
        st['BodyText']
    ))

    rows = [['Fuente', 'Estado', 'Consulta UTC']]
    for e in ev:
        rows.append([
            Paragraph(str(e.get('source', '')), st['CellSmall']),
            Paragraph(str(e.get('status', '')), st['CellSmall']),
            Paragraph((e.get('consulted_at') or '')[:19], st['CellSmall'])
        ])
    table = Table(rows, repeatRows=1, colWidths=[60*mm, 40*mm, 155*mm])
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), .25, colors.HexColor('#b8c7cc')),
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f9f9')])
    ]))
    story.append(table)

    doc.build(story)
    return out.getvalue()
