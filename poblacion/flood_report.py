"""Informe PDF de exposición ribereña con datos ya calculados y trazables."""
import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape


def pdf(data):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    if not isinstance(data, dict) or not data.get('place') or not isinstance(data.get('bands'), list):
        raise ValueError('Faltan datos de localidad y franjas de población.')
    if len(data['bands']) > 20:
        raise ValueError('Demasiadas franjas.')
    name = str(data['place'])[:120]
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, topMargin=23*mm, bottomMargin=21*mm,
                            leftMargin=16*mm, rightMargin=16*mm,
                            title='DOTS · Población potencialmente expuesta · '+name)
    sty = getSampleStyleSheet()
    sty.add(ParagraphStyle(name='DOTSTitle', parent=sty['Title'], fontSize=17, leading=21,
                           textColor=colors.HexColor('#0b2b33'), spaceAfter=9))
    sty.add(ParagraphStyle(name='DOTSNote', parent=sty['BodyText'], fontSize=8, leading=12,
                           textColor=colors.HexColor('#526a73')))
    safe = lambda value: escape(str(value if value is not None else 'Sin dato'))
    def number(value):
        try:
            n = float(value)
            if not (0 <= n < 1e12): return 'Sin dato'
            return f'{n:,.0f}'.replace(',', '.')
        except (TypeError, ValueError): return 'Sin dato'
    story = [Paragraph('Exposición poblacional ribereña',sty['DOTSTitle']),
             Paragraph('<b>Localidad:</b> '+safe(name)+' · <b>Río:</b> '+safe(data.get('river')),sty['BodyText']),
             Paragraph('<b>Área de análisis:</b> radio de '+safe(data.get('radius_km'))+' km · <b>Población de referencia:</b> WorldPop 2020',sty['BodyText']),
             Spacer(1,9), Paragraph('Resumen ejecutivo',sty['Heading2']),
             Paragraph('Población residente estimada en el área: <b>'+number(data.get('total'))+'</b>. Las cifras por franja describen exposición potencial según altura sobre la red de drenaje; no son personas inundadas ni evacuadas.',sty['BodyText']),
             Spacer(1,8),Paragraph('Población por altura sobre el drenaje',sty['Heading2'])]
    rows = [['Franja HAND','Personas','Menores de 5','Mayores de 65']]
    for b in data['bands']:
        if not isinstance(b,dict): continue
        rows.append([safe(b.get('up_to_m'))+' m',number(b.get('people')),number(b.get('under5')),number(b.get('over65'))])
    t=Table(rows,colWidths=[43*mm,40*mm,45*mm,45*mm],repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0b2b33')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#c4d1d5')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.append(t)
    if data.get('scenarios'):
        story += [Spacer(1,9),Paragraph('Escenarios de crecida',sty['Heading2'])]
        for sc in data['scenarios'][:8]:
            story.append(Paragraph('<b>'+safe(sc.get('label'))+'</b>: '+number(sc.get('people'))+' personas potencialmente expuestas hasta '+safe(sc.get('band_m'))+' m HAND.',sty['BodyText']))
    story += [Spacer(1,12),Paragraph('Metodología, fuentes y limitaciones',sty['Heading2']),
        Paragraph('Fuentes: WorldPop 2020 (población y edades), MERIT Hydro HAND (altura relativa al drenaje); niveles hidrométricos cuando se dispone de referencias oficiales. El método no modela propagación hidráulica, defensas, terraplenes, profundidad real del agua ni evacuaciones efectivas.',sty['DOTSNote']),
        Paragraph('Informe generado '+datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')+'. Las estimaciones no sustituyen las alertas de INA, Prefectura o Defensa Civil.',sty['DOTSNote'])]
    def page(canvas, document):
        canvas.saveState()
        w,h=A4
        canvas.setFillColor(colors.HexColor('#0b2b33'))
        canvas.rect(0,h-14*mm,w,14*mm,stroke=0,fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold',9)
        canvas.drawString(16*mm,h-9*mm,'DOTS / INTELIGENCIA TERRITORIAL')
        canvas.setStrokeColor(colors.HexColor('#c4d1d5'))
        canvas.line(16*mm,16*mm,w-16*mm,16*mm)
        canvas.setFillColor(colors.HexColor('#526a73'))
        canvas.setFont('Helvetica',7)
        canvas.drawString(16*mm,11*mm,'DOTS · Dirección: Álvaro Fontana')
        canvas.drawRightString(w-16*mm,11*mm,'Página '+str(document.page))
        canvas.restoreState()
    doc.build(story,onFirstPage=page,onLaterPages=page)
    return out.getvalue()
