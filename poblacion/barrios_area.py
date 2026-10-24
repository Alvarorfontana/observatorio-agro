"""Barrios populares del RENABAP dentro de un área dibujada en el mapa.

Lee data/renabap_barrios.geojson (todos los barrios del país, simplificados; lo genera la tarea «RENABAP por
localidad») y cruza cada barrio con el polígono del usuario: cuenta los barrios que tocan el área, la parte de su
superficie que queda adentro y estima las familias en proporción a esa parte.
"""
from .geometry import Geom, intersection, polygon, area_km2

MAX_AREA_KM2 = 25000          # un área más grande que una provincia chica no tiene sentido para esta consulta
MAX_DEVUELTOS = 600           # polígonos que se mandan al mapa


def _geom_de(feature):
    g = feature.get('geometry') or {}
    if g.get('type') == 'Polygon':
        return Geom([g['coordinates']])
    if g.get('type') == 'MultiPolygon':
        return Geom(g['coordinates'])
    return Geom([])


def _cargar():
    import datastore
    data = datastore.load('renabap_barrios.geojson', ttl=86400)
    if not data or not data.get('features'):
        raise LookupError('Todavía no está cargado el mapa de barrios del RENABAP: correr la tarea «RENABAP por localidad».')
    return data


def en_area(area_geojson):
    aoi = polygon(area_geojson, 'zona de estudio')
    sup = area_km2(aoi)
    if sup > MAX_AREA_KM2:
        raise ValueError(f'El área dibujada tiene {sup:,.0f} km²; para barrios populares usá una zona de hasta '
                         f'{MAX_AREA_KM2:,} km² (una ciudad o un departamento).'.replace(',', '.'))
    x0, y0, x1, y1 = aoi.bounds
    data = _cargar()
    barrios, total_fam, total_ha = [], 0.0, 0.0
    for f in data['features']:
        p = f.get('properties') or {}
        b = p.get('bbox')
        if b and (b[2] < x0 or b[0] > x1 or b[3] < y0 or b[1] > y1):
            continue
        g = _geom_de(f)
        if g.is_empty:
            continue
        try:
            inter = intersection(aoi, g)
        except Exception:
            continue
        if inter.is_empty:
            continue
        ha_dentro = area_km2(inter) * 100
        ha_total = p.get('ha') or (area_km2(g) * 100) or ha_dentro
        frac = max(0.0, min(1.0, ha_dentro / ha_total)) if ha_total else 1.0
        fam = p.get('familias')
        fam_dentro = fam * frac if fam is not None else None
        total_ha += ha_dentro
        total_fam += fam_dentro or 0
        barrios.append({'nombre': p.get('nombre'), 'familias': fam, 'familias_en_area': round(fam_dentro) if fam_dentro is not None else None,
                        'ha': round(ha_total, 2), 'ha_en_area': round(ha_dentro, 2), 'parte_en_area': round(frac, 3),
                        'provincia': p.get('provincia'), 'localidad': p.get('localidad'),
                        'lat': p.get('lat'), 'lon': p.get('lon'), 'geometry': f.get('geometry')})
    barrios.sort(key=lambda x: -(x['familias_en_area'] or 0))
    return {'area_km2': round(sup, 2), 'barrios': len(barrios), 'familias': round(total_fam), 'superficie_ha': round(total_ha, 1),
            'completos': sum(1 for x in barrios if x['parte_en_area'] >= .99),
            'lista': barrios[:MAX_DEVUELTOS], 'recortado': len(barrios) > MAX_DEVUELTOS,
            'fuente': data.get('source') or 'RENABAP 2023',
            'nota': ('Cuando un barrio queda cortado por el área, las familias se reparten en proporción a la superficie '
                     'que queda adentro. Los barrios posteriores al último relevamiento del registro no figuran. '
                     'Fuera de Argentina no hay RENABAP.')}


def pdf(resultado, poblacion=None):
    """Informe PDF de los barrios del área dibujada (y, si viene, la población WorldPop de esa misma área)."""
    import io
    from datetime import datetime, timedelta, timezone
    from reportlab.platypus import Paragraph, Spacer
    from . import barrios_report as br
    r = resultado
    sty = br._estilos()
    out = io.BytesIO()
    doc = br._doc(out, 'DOTS · Barrios populares en el área dibujada')
    W = doc.width
    hoy = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')
    story = [Paragraph('BARRIOS POPULARES · ÁREA DELIMITADA', sty['Kicker']),
             Paragraph('Barrios populares en el área dibujada', sty['T']),
             Paragraph(f"Área de {br._n(r['area_km2'], 1)} km² · informe generado el {hoy} (hora argentina)", sty['Sub'])]
    cards = [(br._n(r['barrios']), 'barrios del RENABAP que tocan el área', None),
             (br._n(r['familias']), 'familias estimadas dentro del área', br.AMBER),
             (br._n(r['superficie_ha']) + ' ha', 'superficie de barrios dentro del área', None)]
    if poblacion and poblacion.get('population_total') is not None:
        cards.append((br._n(poblacion['population_total']), f"personas en toda el área (WorldPop {poblacion.get('year', '')})", None))
    story += [br._tarjetas(sty, cards, W), Paragraph('Lectura', sty['H'])]
    if r['barrios']:
        top = [b for b in r['lista'] if b.get('familias_en_area')][:3]
        story.append(Paragraph(
            f"Dentro del área hay <b>{br._n(r['barrios'])} barrios populares</b> registrados ({br._n(r['completos'])} enteros y el resto "
            f"cortados por el borde), con unas <b>{br._n(r['familias'])} familias</b>. "
            + ('Los de más familias: ' + ', '.join(f"{br._safe(b['nombre'])} ({br._n(b['familias_en_area'])})" for b in top) + '.' if top else ''),
            sty['B']))
        if poblacion and poblacion.get('population_total'):
            story.append(Paragraph('Para comparar: WorldPop estima ' + br._n(poblacion['population_total']) + ' personas en toda el área'
                                   + (f", y {br._n(poblacion.get('population_exposed'))} en la zona de amenaza dibujada" if poblacion.get('population_exposed') is not None and poblacion.get('hazard_given') is not False else '')
                                   + '.', sty['B']))
        filas = [['Barrio', 'Localidad', 'Familias', 'En el área', 'Superficie']]
        for b in r['lista'][:120]:
            filas.append([br._safe(b['nombre']), br._safe(b.get('localidad') or ''), br._n(b['familias']) if b['familias'] is not None else '—',
                          (br._n(100 * b['parte_en_area']) + ' %'), br._n(b['ha_en_area'], 1) + ' ha'])
        story += [Paragraph('Barrios dentro del área', sty['H']),
                  br._tabla(filas, [W * .34, W * .24, W * .13, W * .14, W * .15], alinear_der=(2, 3, 4))]
        if len(r['lista']) > 120:
            story.append(Paragraph(f"Se muestran los 120 barrios con más familias de {br._n(r['barrios'])}.", sty['Nota']))
    else:
        story.append(Paragraph('El RENABAP no registra barrios populares dentro del área dibujada.', sty['B']))
    story += [Spacer(1, 6), Paragraph(r['nota'], sty['Nota']),
              Paragraph('Para qué sirve y qué no dice', sty['H']),
              Paragraph('Sirve para dimensionar refugios, agua, traslados y prioridades antes de una emergencia en esa zona. '
                        'No identifica viviendas ni personas. Ante una evacuación, manda Defensa Civil.', sty['B']),
              Spacer(1, 8), Paragraph('Fuente: ' + br._safe(r['fuente']) + '. Elaboración: DOTS.', sty['Nota'])]
    pg = br._pagina('Barrios populares · área dibujada')
    doc.build(story, onFirstPage=pg, onLaterPages=pg)
    return out.getvalue()
