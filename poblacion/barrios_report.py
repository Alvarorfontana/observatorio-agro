"""Informes PDF de barrios populares en las localidades ribereñas (por localidad y resumen regional).

Junta lo que DOTS ya tiene calculado, sin inventar lo que falta:
  - RENABAP (Registro Nacional de Barrios Populares, versión 2023-12-06): barrios, familias, superficie y los
    barrios más grandes a 15 km de cada localidad (tarea «RENABAP por localidad», rama de datos).
  - Modelo de radar Sentinel-1 + Sentinel-2 (tarea «Barrios populares por radar»): superficie con firma de barrio
    popular, zonas a verificar y mapa, cuando esa localidad ya está calculada.
  - Estado del río: altura y nivel oficial del INA (escalas de Prefectura).
  - Personas por altura sobre el río (WorldPop 2020 + MERIT Hydro vía Earth Engine), si responde a tiempo.
Cada bloque dice de dónde sale; si una fuente no responde, el informe lo declara.
"""
import io
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

INK, TEAL, MUTED, LINE, RED, AMBER = '#0b2b33', '#0f9fa6', '#526a73', '#c4d1d5', '#b42318', '#b54708'
NIVEL_COLOR = {'Evacuación': '#b42318', 'Alerta': '#d9480f', 'Atención': '#b54708', 'Normal': '#2f7d4f'}


def _ar_now():
    return (datetime.now(timezone.utc) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')


def _n(v, dec=0):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 'Sin dato'
    s = f'{x:,.{dec}f}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def _safe(v):
    return escape(str(v if v is not None else 'Sin dato'))


# ───────────────────────────── recolección de datos ─────────────────────────────
def _datos():
    import datastore
    ren = datastore.load('renabap_localidades.json') or {}
    rad = datastore.load('barrios_radar.json') or {}
    return ren, rad


def _rio():
    """Estado del río por localidad (INA). Devuelve {id: fila} o {} si el INA no responde."""
    try:
        import cuenca as cca
        res = cca.resumen()
        rows = ((res or {}).get('data') or {}).get('stations') or []
        return {r['id']: r for r in rows}
    except Exception:
        return {}


def _poblacion_rio(sid, limite=40):
    """Personas por altura sobre el río (Earth Engine). None si no responde a tiempo."""
    try:
        from . import crecida
        with ThreadPoolExecutor(max_workers=1) as ex:
            env = ex.submit(crecida.at_station, sid).result(timeout=limite)
        return env.get('data') if env and env.get('status') == 'recibido' else None
    except (FutTimeout, Exception):
        return None


def _imagen_radar(rel):
    if not rel:
        return None
    try:
        import datastore
        png = datastore.fetch_bytes(rel)
        return png if png and png.startswith(b'\x89PNG') else None
    except Exception:
        return None


# ───────────────────────────── maqueta común ─────────────────────────────
def _estilos():
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name='Kicker', parent=s['BodyText'], fontName='Helvetica-Bold', fontSize=8.5, leading=11,
                         textColor=colors.HexColor(TEAL), spaceAfter=2))
    s.add(ParagraphStyle(name='T', parent=s['Title'], alignment=0, fontSize=20, leading=24,
                         textColor=colors.HexColor(INK), spaceAfter=4))
    s.add(ParagraphStyle(name='Sub', parent=s['BodyText'], fontSize=10, leading=14, textColor=colors.HexColor(MUTED), spaceAfter=8))
    s.add(ParagraphStyle(name='H', parent=s['Heading2'], fontSize=12.5, leading=16, textColor=colors.HexColor(INK),
                         spaceBefore=12, spaceAfter=5))
    s.add(ParagraphStyle(name='B', parent=s['BodyText'], fontSize=9.6, leading=13.6, textColor=colors.HexColor('#1d2b30')))
    s.add(ParagraphStyle(name='Nota', parent=s['BodyText'], fontSize=8, leading=11.5, textColor=colors.HexColor(MUTED)))
    s.add(ParagraphStyle(name='Cifra', parent=s['BodyText'], fontName='Helvetica-Bold', fontSize=17, leading=20,
                         textColor=colors.HexColor(INK)))
    s.add(ParagraphStyle(name='CifraEt', parent=s['BodyText'], fontSize=7.8, leading=10, textColor=colors.HexColor(MUTED)))
    return s


def _tarjetas(sty, items, ancho):
    """Fila de cifras grandes: [(valor, etiqueta, color)]."""
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle
    celdas = []
    for val, et, col in items:
        st = sty['Cifra'].clone('c') if col else sty['Cifra']
        if col:
            st.textColor = colors.HexColor(col)
        celdas.append([Paragraph(val, st), Paragraph(et, sty['CifraEt'])])
    t = Table([celdas], colWidths=[ancho / len(items)] * len(items))
    t.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), .4, colors.HexColor(LINE)),
                           ('INNERGRID', (0, 0), (-1, -1), .4, colors.HexColor(LINE)),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 7),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 8), ('LEFTPADDING', (0, 0), (-1, -1), 8)]))
    return t


def _tabla(filas, anchos, cabecera_color=INK, alinear_der=()):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    t = Table(filas, colWidths=anchos, repeatRows=1)
    st = [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(cabecera_color)), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
          ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 8.6),
          ('LINEBELOW', (0, 1), (-1, -1), .3, colors.HexColor(LINE)), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
          ('TOPPADDING', (0, 0), (-1, -1), 4.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
          ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f4f8f9')])]
    for c in alinear_der:
        st.append(('ALIGN', (c, 0), (c, -1), 'RIGHT'))
    t.setStyle(TableStyle(st))
    return t


def _pagina(titulo_corto):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    def page(canvas, document):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(colors.HexColor(INK))
        canvas.rect(0, h - 14 * mm, w, 14 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawString(16 * mm, h - 9 * mm, 'DOTS / INTELIGENCIA TERRITORIAL')
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(w - 16 * mm, h - 9 * mm, titulo_corto)
        canvas.setStrokeColor(colors.HexColor(LINE))
        canvas.line(16 * mm, 16 * mm, w - 16 * mm, 16 * mm)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.setFont('Helvetica', 7)
        canvas.drawString(16 * mm, 11 * mm, 'DOTS · Datos · Observación · Territorio · Satélite · observatorio-agro.vercel.app')
        canvas.drawRightString(w - 16 * mm, 11 * mm, 'Página ' + str(document.page))
        canvas.restoreState()
    return page


def _doc(out, titulo):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    return SimpleDocTemplate(out, pagesize=A4, topMargin=22 * mm, bottomMargin=21 * mm,
                             leftMargin=16 * mm, rightMargin=16 * mm, title=titulo, author='DOTS')


def _barras_h(nombres, valores, color, ancho, fmt=lambda v: _n(v)):
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import HorizontalBarChart
    from reportlab.lib import colors
    alto = 22 * len(valores) + 30
    d = Drawing(ancho, alto)
    ch = HorizontalBarChart()
    ch.x, ch.y, ch.width, ch.height = 120, 10, ancho - 190, alto - 20
    ch.data = [list(reversed(valores))]
    ch.categoryAxis.categoryNames = list(reversed(nombres))
    ch.categoryAxis.labels.fontSize = 8
    ch.categoryAxis.labels.fontName = 'Helvetica'
    ch.categoryAxis.strokeColor = colors.HexColor(LINE)
    ch.valueAxis.visible = False
    ch.valueAxis.valueMin = 0
    ch.valueAxis.valueMax = (max(valores) or 1) * 1.05
    ch.bars[0].fillColor = colors.HexColor(color)
    ch.bars[0].strokeColor = None
    ch.barSpacing = 3
    d.add(ch)
    paso = ch.height / max(1, len(valores))
    vmax = ch.valueAxis.valueMax
    for i, v in enumerate(reversed(valores)):
        x = ch.x + ch.width * (v / vmax) + 4
        y = ch.y + paso * i + paso / 2 - 3
        d.add(String(x, y, fmt(v), fontName='Helvetica-Bold', fontSize=8, fillColor=colors.HexColor(INK)))
    return d


# ───────────────────────────── informe por localidad ─────────────────────────────
def local_pdf(sid):
    import cuenca as cca
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Image, KeepTogether
    st = next((s for s in cca.STATIONS if s['id'] == sid), None)
    if not st:
        raise ValueError('Localidad desconocida.')
    ren, rad = _datos()
    r = next((p for p in (ren.get('places') or []) if p.get('id') == sid), None)
    m = next((p for p in (rad.get('places') or []) if p.get('id') == sid), None)
    if m and m.get('informal_ha') is None:
        m = None
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_rio, f_pob = ex.submit(_rio), ex.submit(_poblacion_rio, sid)
        rio = f_rio.result().get(sid)
        pob = f_pob.result()

    sty = _estilos()
    out = io.BytesIO()
    doc = _doc(out, 'DOTS · Barrios populares · ' + st['place'])
    W = doc.width
    story = [Paragraph('BARRIOS POPULARES Y RIESGO DE CRECIDA', sty['Kicker']),
             Paragraph(_safe(st['place']), sty['T']),
             Paragraph(f"Río {_safe(st['river'])} · radio de análisis de 15 km · informe generado el {_ar_now()} (hora argentina)", sty['Sub'])]

    # cifras principales
    nivel = (rio or {}).get('level')
    cards = [(_n(r.get('barrios')) if r else 'Sin dato', 'barrios populares registrados (RENABAP)', None),
             (_n(r.get('familias')) if r else 'Sin dato', 'familias según el registro', AMBER),
             (_n(r.get('superficie_ha'), 0) + ' ha' if r else 'Sin dato', 'superficie de los barrios', None),
             (nivel or 'Sin dato', 'estado del río hoy (INA)', NIVEL_COLOR.get(nivel))]
    story += [_tarjetas(sty, cards, W), Spacer(1, 4)]

    # lectura
    story.append(Paragraph('Lectura', sty['H']))
    lineas = []
    if r and r.get('barrios'):
        lineas.append(f"A 15 km o menos de {_safe(st['place'])} el RENABAP registra <b>{_n(r['barrios'])} barrios populares</b>, "
                      f"donde viven unas <b>{_n(r['familias'])} familias</b>. Son los lugares donde una crecida golpea primero: "
                      "construcciones precarias, muchas veces en zonas bajas y sin desagües.")
    elif r:
        lineas.append(f"El RENABAP no registra barrios populares a 15 km de {_safe(st['place'])}.")
    else:
        lineas.append('Esta localidad está fuera de Argentina: el RENABAP no la cubre. '
                      'Para conocer sus barrios hay que recurrir al registro del país vecino.')
    if rio:
        h, a, e = rio.get('height'), rio.get('alert'), rio.get('evac')
        txt = f"El río marca <b>{_n(h, 2)} m</b> ({_safe(rio.get('date'))})"
        if a:
            txt += f"; el nivel de alerta es {_n(a, 2)} m" + (f" y el de evacuación {_n(e, 2)} m" if e else '')
        tr = rio.get('trend_m_day')
        if tr is not None:
            txt += f". Tendencia: {('sube' if tr > .01 else 'baja' if tr < -.01 else 'estable')} ({_n(tr * 100, 0)} cm por día)"
        if rio.get('days_to_alert'):
            txt += f". Al ritmo actual llegaría al nivel de alerta en unos {_n(rio['days_to_alert'])} días"
        lineas.append(txt + '.')
    else:
        lineas.append('No hay altura del INA para esta localidad en este momento.')
    for l in lineas:
        story.append(Paragraph(l, sty['B']))

    # barrios más grandes
    if r and r.get('mayores'):
        story.append(Paragraph('Los barrios más grandes', sty['H']))
        filas = [['Barrio', 'Familias']] + [[_safe(b.get('nombre')), _n(b.get('familias'))] for b in r['mayores']]
        story.append(_tabla(filas, [W * .72, W * .28], alinear_der=(1,)))
        story.append(Paragraph('Familias según estima el registro. Los barrios posteriores al último relevamiento no figuran.', sty['Nota']))

    # población por altura sobre el río
    story.append(Paragraph('Cuánta gente vive cerca del nivel del río', sty['H']))
    if pob and pob.get('bands'):
        story.append(Paragraph(
            f"En el radio de 15 km viven unas <b>{_n(pob.get('total'))} personas</b> (WorldPop 2020). Esta es la gente que vive "
            "a pocos metros por encima del curso de agua más cercano: la primera en verse afectada si el río sube.", sty['B']))
        filas = [['Hasta … m sobre el río', 'Personas', 'Menores de 5', 'Mayores de 65']]
        for b in pob['bands']:
            filas.append([f"{b.get('up_to_m')} m", _n(b.get('people')), _n(b.get('under5')), _n(b.get('over65'))])
        story.append(_tabla(filas, [W * .31, W * .23, W * .23, W * .23], cabecera_color=TEAL, alinear_der=(1, 2, 3)))
        story.append(Paragraph('Franjas acumuladas: la de 5 m incluye a la de 1, 2 y 3 m. No sumarlas.', sty['Nota']))
        for sc in pob.get('scenarios') or []:
            story.append(Paragraph(f"<b>{_safe(sc.get('label'))} ({_n(sc.get('level_m'), 2)} m):</b> el río subiría unos "
                                   f"{_n(sc.get('rise_m'), 1)} m sobre aguas bajas; viven <b>{_n(sc.get('people'))} personas</b> "
                                   f"hasta {sc.get('band_m')} m sobre el río.", sty['B']))
    else:
        story.append(Paragraph('El cálculo de población por altura (Google Earth Engine) no respondió a tiempo. '
                               'Se puede consultar en la página de Población de DOTS, sección «Zona baja».', sty['B']))

    # modelo de radar
    story.append(Paragraph('Mapa de barrios por radar', sty['H']))
    if m:
        story.append(_tarjetas(sty, [(_n(m.get('informal_ha'), 0) + ' ha', 'superficie con firma de barrio popular', None),
                                     (_n(m.get('a_verificar_ha'), 0) + ' ha', 'zonas a verificar fuera del RENABAP', AMBER),
                                     ((_n(100 * m['renabap_detectado'], 0) + ' %') if m.get('renabap_detectado') is not None else 'Sin dato',
                                      'de los barrios RENABAP que el modelo reconoce', None)], W))
        png = _imagen_radar(m.get('imagen'))
        if png:
            story += [Spacer(1, 6), Image(io.BytesIO(png), width=W * .78, height=W * .78),
                      Paragraph('Rojo: firma de barrio popular según el modelo. Amarillo: barrios del RENABAP. '
                                f"Fondo: Sentinel-2 en color natural, {rad.get('year', '')}.", sty['Nota'])]
        story.append(Paragraph('Las zonas a verificar pueden ser barrios nuevos o no relevados, o falsos positivos: '
                               'hay que confirmarlas en terreno.', sty['Nota']))
    else:
        story.append(Paragraph('El modelo de radar todavía no calculó esta localidad. Cuando lo haga, este informe va a '
                               'sumar el mapa y las zonas a verificar fuera del registro.', sty['B']))

    # variables del modelo
    from . import barrios_variables as bv
    from reportlab.platypus import PageBreak
    pesos = (rad.get('model') or {}).get('capas_mas_utiles')
    story += [PageBreak(), Paragraph('Variables que analiza el modelo', sty['H']),
              Paragraph('Para cada píxel de 10 m el modelo mira estas 30 variables y decide si tiene la firma de un barrio '
                        'popular. El peso indica cuánto influye cada una en la decisión.', sty['B'])]
    filas, grupo = [['Variable', 'Qué mide', 'Peso']], ''
    estilos_g = []
    for v in bv.lista(pesos):
        if v['grupo'] != grupo:
            grupo = v['grupo']; filas.append([grupo, '', '']); estilos_g.append(len(filas) - 1)
        filas.append([Paragraph(f"<b>{_safe(v['nombre'])}</b>", sty['Nota']), Paragraph(_safe(v['mide']), sty['Nota']),
                      (_n(100 * v['peso'], 1) + ' %') if v['peso'] is not None else '—'])
    t = _tabla(filas, [W * .30, W * .56, W * .14], alinear_der=(2,))
    from reportlab.platypus import TableStyle
    t.setStyle(TableStyle([st for i in estilos_g for st in (
        ('SPAN', (0, i), (-1, i)), ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#e3f3f4')),
        ('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'), ('TEXTCOLOR', (0, i), (-1, i), colors.HexColor(INK)))]))
    story.append(t)
    story.append(Paragraph('Resultados que calcula por localidad: ' + '; '.join(
        f"{x['nombre'].lower()} ({x['unidad']})" for x in bv.salidas()) + '.', sty['Nota']))

    # uso y método
    story.append(Paragraph('Para qué sirve y qué no dice', sty['H']))
    for t in ['Sirve para planificar con anticipación: refugios, agua potable, traslado de personas mayores y chicos, y '
              'prioridades de Defensa Civil y municipios.',
              'No identifica viviendas ni personas, y no es un pronóstico de inundación. Ante una evacuación, '
              'manda Defensa Civil.']:
        story.append(Paragraph('• ' + t, sty['B']))
    story += [Spacer(1, 8), Paragraph(
        'Fuentes: RENABAP, Secretaría de Integración Socio-Urbana, versión 2023-12-06 · INA y escalas de Prefectura Naval · '
        'WorldPop 2020 (CC BY 4.0) · MERIT Hydro (Yamazaki et al., 2019) · Copernicus Sentinel-1 y Sentinel-2 vía Google '
        'Earth Engine. Elaboración: DOTS.', sty['Nota'])]

    doc.build(story, onFirstPage=_pagina('Barrios populares · ' + st['place']), onLaterPages=_pagina('Barrios populares · ' + st['place']))
    return out.getvalue(), st['place']


# ───────────────────────────── resumen regional ─────────────────────────────
def regional_pdf():
    import cuenca as cca
    from reportlab.platypus import Paragraph, Spacer, PageBreak
    ren, rad = _datos()
    rio = _rio()
    por_id = {p['id']: p for p in (ren.get('places') or [])}
    radar = {p['id']: p for p in (rad.get('places') or []) if p.get('informal_ha') is not None}
    filas = []
    for s in cca.STATIONS:
        if s['id'] not in por_id and s['id'] not in rio:
            continue
        p = por_id.get(s['id'], {})
        filas.append({'id': s['id'], 'place': s['place'], 'river': s['river'], 'barrios': p.get('barrios'),
                      'familias': p.get('familias'), 'ha': p.get('superficie_ha'),
                      'nivel': (rio.get(s['id']) or {}).get('level'), 'altura': (rio.get(s['id']) or {}).get('height'),
                      'radar': s['id'] in radar})
    filas.sort(key=lambda f: -(f['familias'] or 0))
    con = [f for f in filas if f['barrios']]
    tot_b = sum(f['barrios'] or 0 for f in con)
    tot_f = sum(f['familias'] or 0 for f in con)
    orden = {'Evacuación': 0, 'Alerta': 1, 'Atención': 2}
    riesgo = sorted([f for f in con if f['nivel'] in orden], key=lambda f: (orden[f['nivel']], -(f['familias'] or 0)))

    sty = _estilos()
    out = io.BytesIO()
    doc = _doc(out, 'DOTS · Barrios populares en la Cuenca del Plata')
    W = doc.width
    story = [Paragraph('BARRIOS POPULARES Y RIESGO DE CRECIDA', sty['Kicker']),
             Paragraph('Las localidades ribereñas de la Cuenca del Plata', sty['T']),
             Paragraph(f'{len(filas)} localidades sobre el Paraná, el Uruguay, el Paraguay y el Iguazú · '
                       f'radio de 15 km · informe generado el {_ar_now()} (hora argentina)', sty['Sub']),
             _tarjetas(sty, [(_n(tot_b), 'barrios populares registrados', None),
                             (_n(tot_f), 'familias que viven en ellos', AMBER),
                             ((_n(len(riesgo)) if rio else 'Sin dato'), 'localidades con barrios y el río en atención o más',
                              RED if riesgo else None)], W),
             Paragraph('Lectura', sty['H']),
             Paragraph(f'En las localidades ribereñas que sigue DOTS, el RENABAP registra <b>{_n(tot_b)} barrios populares</b> '
                       f'con unas <b>{_n(tot_f)} familias</b>. Las cinco con más familias son '
                       + ', '.join(f"{_safe(f['place'])} ({_n(f['familias'])})" for f in con[:5]) + '.', sty['B'])]
    if riesgo:
        story.append(Paragraph('Hoy el río está en atención, alerta o evacuación en: ' + '; '.join(
            f"<b>{_safe(f['place'])}</b> ({_safe(f['nivel']).lower()}, {_n(f['familias'])} familias en barrios populares)"
            for f in riesgo) + '. Son las prioridades para prevención y asistencia.', sty['B']))
    elif rio:
        story.append(Paragraph('Hoy ninguna de estas localidades tiene el río en atención, alerta o evacuación según el INA.', sty['B']))
    else:
        story.append(Paragraph('El INA no respondió: este informe no incluye el estado actual de los ríos.', sty['B']))

    top = con[:12]
    if top:
        story += [Paragraph('Familias en barrios populares, por localidad', sty['H']),
                  _barras_h([f['place'] for f in top], [f['familias'] or 0 for f in top], AMBER, W),
                  Paragraph('Las 12 localidades con más familias. Fuente: RENABAP 2023.', sty['Nota'])]

    story += [PageBreak(), Paragraph('Todas las localidades', sty['H'])]
    tab = [['Localidad', 'Río', 'Barrios', 'Familias', 'Superficie', 'Río hoy']]
    for f in filas:
        tab.append([_safe(f['place']), _safe(f['river']), _n(f['barrios']) if f['barrios'] is not None else 'Fuera de RENABAP',
                    _n(f['familias']) if f['familias'] is not None else '—', (_n(f['ha']) + ' ha') if f['ha'] is not None else '—',
                    f['nivel'] or '—'])
    t = _tabla(tab, [W * .27, W * .13, W * .15, W * .14, W * .15, W * .16], alinear_der=(2, 3, 4))
    from reportlab.lib import colors
    estilos = []
    for i, f in enumerate(filas, start=1):
        if f['nivel'] in NIVEL_COLOR and f['nivel'] != 'Normal':
            estilos += [('TEXTCOLOR', (5, i), (5, i), colors.HexColor(NIVEL_COLOR[f['nivel']])), ('FONTNAME', (5, i), (5, i), 'Helvetica-Bold')]
    if estilos:
        from reportlab.platypus import TableStyle
        t.setStyle(TableStyle(estilos))
    story += [t, Paragraph('En las localidades de frontera (por ejemplo Asunción, frente a Clorinda) se cuentan sólo los barrios '
                           'del lado argentino: el RENABAP no cubre Paraguay ni Uruguay. '
                           f"Mapa por radar disponible en {len(radar)} de {len(filas)} localidades.", sty['Nota'])]
    story += [Paragraph('Para qué sirve y qué no dice', sty['H']),
              Paragraph('Sirve para priorizar dónde preparar refugios, agua y traslados antes de una crecida. No identifica '
                        'viviendas ni personas, y no es un pronóstico. Ante una evacuación, manda Defensa Civil.', sty['B']),
              Spacer(1, 8),
              Paragraph('Fuentes: RENABAP, Secretaría de Integración Socio-Urbana, versión 2023-12-06 (barrios a 15 km del '
                        'centro de cada localidad) · INA y escalas de Prefectura Naval. Elaboración: DOTS. '
                        'Informe por localidad, con mapa y población por altura: página Población de DOTS.', sty['Nota'])]
    pg = _pagina('Barrios populares · Cuenca del Plata')
    doc.build(story, onFirstPage=pg, onLaterPages=pg)
    return out.getvalue()
