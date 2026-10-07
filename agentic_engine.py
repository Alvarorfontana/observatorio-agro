"""DOTS Agentic v0.2: deterministic orchestration over verified project connectors.
No LLM is required. Missing measurements remain explicitly unavailable.
"""
from datetime import datetime, timezone
import io, math
import research_connectors as c

QUICK = {
    'integral':'Informe integral del estado del campo',
    'pasturas':'Evaluá pasturas y vegetación',
    'agua':'Analizá agua, lluvia y disponibilidad hídrica',
    'ganado':'Analizá estrés térmico y entorno del ganado',
    'sequia':'Evaluá riesgo de sequía e incendio',
    'suelo':'Analizá humedad y condición del suelo',
    'clima':'Resumí clima actual y próximos 7 días',
}

def _num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def _intent(prompt):
    p=(prompt or '').lower()
    for key, words in {
        'pasturas':['pastura','vegetación','vegetacion','ndvi'],
        'agua':['agua','lluvia','hídr','hidri','precipita','bebedero'],
        'ganado':['ganado','vaca','bovino','thi','estrés','estres'],
        'sequia':['sequía','sequia','incendio','fuego'],
        'suelo':['suelo','humedad','nitrógeno','nitrogeno'],
        'clima':['clima','tiempo','temperatura','pronóstico','pronostico'],
    }.items():
        if any(w in p for w in words): return key
    return 'integral'

def _thi(t,rh):
    if t is None or rh is None:return None
    return 1.8*t+32-(0.55-0.0055*rh)*(1.8*t-26)

def _quality(source_count, warnings):
    score=min(95, 48+source_count*9-max(0,len(warnings)-1)*4)
    return max(20,score)

def analyze(lat,lon,prompt='',polygon=None,ina_id=None):
    intent=_intent(prompt)
    # Bundle is the verified common base. Add domain connectors only when useful.
    bundle=c.research_bundle(lat,lon,ina_id)
    extra={}
    jobs=[]
    if intent in ('integral','agua','sequia'): jobs.append(('rios',lambda:c.external('https://flood-api.open-meteo.com/v1/flood',{'latitude':lat,'longitude':lon,'daily':'river_discharge','forecast_days':7})))
    if intent in ('integral','suelo'): jobs.append(('suelo_nitrogeno',lambda:c.external('https://rest.isric.org/soilgrids/v2.0/properties/query',{'lat':lat,'lon':lon,'property':'nitrogen','depth':'0-5cm','value':'mean'})))
    if intent in ('integral','pasturas'): jobs.append(('escenas_sentinel',lambda:c.scenes(lat,lon)))
    for key,fn in jobs:
        try: extra[key]={'status':'recibido','payload':fn()}
        except Exception as e: extra[key]={'status':'sin dato','error':type(e).__name__}
    sources={**bundle['sources'],**extra}
    clima=sources.get('clima',{}).get('payload',{}).get('data',{})
    cur=clima.get('current',{})
    hourly=clima.get('hourly',{})
    daily=clima.get('daily',{})
    t=_num(cur.get('temperature_2m')); rh=_num(cur.get('relative_humidity_2m')); thi=_thi(t,rh)
    rain=[_num(x) or 0 for x in daily.get('precipitation_sum',[])[:7]]
    et=[_num(x) or 0 for x in daily.get('et0_fao_evapotranspiration',[])[:7]]
    soilvals=hourly.get('soil_moisture_0_to_1cm') or []
    soil=next((_num(v) for v in soilvals if _num(v) is not None),None)
    findings=[]; warnings=[]; recommendations=[]
    if t is not None: findings.append({'topic':'Clima','status':'medido/modelado','text':f'Temperatura actual {t:.1f} °C y humedad relativa {rh:.0f} %.' if rh is not None else f'Temperatura actual {t:.1f} °C.'})
    if rain: findings.append({'topic':'Agua','status':'pronóstico','text':f'Precipitación prevista a 7 días: {sum(rain):.1f} mm; ET₀ acumulada: {sum(et):.1f} mm.'})
    if soil is not None: findings.append({'topic':'Suelo','status':'modelado','text':f'Humedad superficial modelada: {soil:.3f} m³/m³.'})
    if thi is not None:
        level='bajo' if thi<72 else 'atención' if thi<79 else 'alto' if thi<84 else 'severo'
        findings.append({'topic':'Ganado','status':'derivado','text':f'Índice THI {thi:.1f}: nivel {level}. Se calcula con temperatura y humedad, no es diagnóstico veterinario.'})
        if thi>=79: recommendations.append('Priorizar sombra, agua disponible y observación del ganado durante las horas de mayor carga térmica.')
    if intent in ('integral','pasturas'):
        scenes=sources.get('escenas_sentinel',{}).get('payload',{}).get('data',{}).get('features',[])
        if scenes:
            cloud=_num(scenes[0].get('properties',{}).get('eo:cloud_cover'))
            findings.append({'topic':'Satélite','status':'catálogo','text':f'Hay escenas Sentinel-2 recientes disponibles'+(f'; nubosidad de escena más reciente {cloud:.1f} %.' if cloud is not None else '.')})
        warnings.append('NDVI/EVI y biomasa todavía no se calculan desde bandas raster; DOTS no calificará las pasturas hasta incorporar ese procesamiento.')
    if intent in ('integral','agua'):
        warnings.append('La lluvia y el caudal modelados no demuestran por sí solos la existencia ni el estado de bebederos dentro del lote.')
    if intent in ('integral','ganado'):
        warnings.append('No hay inventario ni sensores de animales conectados; no se infiere cantidad o ubicación de ganado desde la imagen base.')
    received=sum(1 for s in sources.values() if s.get('status')=='recibido')
    failed=[k for k,s in sources.items() if s.get('status')!='recibido']
    if failed:warnings.append('Fuentes sin respuesta en esta consulta: '+', '.join(failed)+'.')
    score=_quality(received,warnings)
    if sum(rain)<5 and sum(et)>15: recommendations.append('Seguir la evolución del balance lluvia–ET₀; el pronóstico muestra demanda atmosférica superior al aporte de lluvia.')
    if not recommendations: recommendations.append('Mantener seguimiento; no surge una recomendación operativa fuerte con las variables verificadas disponibles.')
    return {
      'version':'DOTS Agentic 0.2','generated_at':datetime.now(timezone.utc).isoformat(),'point':[lat,lon],
      'polygon':polygon or None,'prompt':prompt or QUICK['integral'],'intent':intent,
      'confidence':{'score':score,'label':'alta' if score>=80 else 'media' if score>=60 else 'limitada','received_sources':received,'failed_sources':len(failed)},
      'summary':f'Análisis {intent} construido con {received} fuentes recibidas. Confianza {score}/100.',
      'findings':findings,'recommendations':recommendations,'warnings':warnings,
      'evidence':[{'source':k,'status':v.get('status'),'consulted_at':v.get('payload',{}).get('consulted_at'),'source_url':v.get('payload',{}).get('source_url'),'scope':v.get('payload',{}).get('scope')} for k,v in sources.items()],
      'raw':sources
    }

def pdf_bytes(result,name='Lote'):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=16*mm,bottomMargin=16*mm)
    st=getSampleStyleSheet(); st.add(ParagraphStyle(name='Small2',parent=st['BodyText'],fontSize=8,leading=10,textColor=colors.HexColor('#455a64')))
    story=[Paragraph('DOTS / CAMPO — INFORME AGENTIC',st['Title']),Paragraph(name,st['Heading2']),Paragraph(f"Punto: {result['point'][0]:.5f}, {result['point'][1]:.5f} · Generado UTC: {result['generated_at']}",st['Small2']),Spacer(1,8),Paragraph(result['summary'],st['Heading3'])]
    story.append(Paragraph(f"Confianza: {result['confidence']['score']}/100 ({result['confidence']['label']}). No equivale a certeza estadística; resume disponibilidad y consistencia operativa de fuentes.",st['BodyText']))
    story.append(Spacer(1,8)); story.append(Paragraph('Hallazgos',st['Heading2']))
    for x in result['findings']:story.append(Paragraph(f"<b>{x['topic']} — {x['status']}:</b> {x['text']}",st['BodyText']))
    story.append(Spacer(1,8)); story.append(Paragraph('Recomendaciones',st['Heading2']))
    for x in result['recommendations']:story.append(Paragraph('• '+x,st['BodyText']))
    story.append(Spacer(1,8)); story.append(Paragraph('Límites y advertencias',st['Heading2']))
    for x in result['warnings']:story.append(Paragraph('• '+x,st['BodyText']))
    story.append(PageBreak()); story.append(Paragraph('Trazabilidad de fuentes',st['Heading2']))
    rows=[['Fuente','Estado','Consulta UTC','Procedencia']]
    for e in result['evidence']:rows.append([e['source'],e['status'],(e.get('consulted_at') or '')[:19],(e.get('source_url') or '').split('?')[0][:55]])
    table=Table(rows,repeatRows=1,colWidths=[30*mm,25*mm,38*mm,78*mm]);table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.25,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f1f2')),('FONTSIZE',(0,0),(-1,-1),7),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story.append(table);story.append(Spacer(1,8));story.append(Paragraph('DOTS conserva datos faltantes como faltantes. No infiere NDVI, animales, bebederos ni incendios sin una medición o fuente verificable.',st['Small2']))
    doc.build(story);return out.getvalue()
