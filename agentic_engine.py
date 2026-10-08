"""DOTS Agentic v0.2: deterministic orchestration over verified project connectors.
No LLM is required. Missing measurements remain explicitly unavailable.
"""
from datetime import datetime, timezone, timedelta
import io, math
from concurrent.futures import ThreadPoolExecutor, as_completed
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

def analyze(lat,lon,prompt='',polygon=None,ina_id=None,water_assets=None,field_markers=None):
    intent=_intent(prompt)
    # Bundle is the verified common base. Add domain connectors only when useful.
    bundle=c.research_bundle(lat,lon,ina_id)
    extra={}
    jobs=[]
    if intent in ('integral','agua','sequia'): jobs.append(('rios',lambda:c.external('https://flood-api.open-meteo.com/v1/flood',{'latitude':lat,'longitude':lon,'daily':'river_discharge','forecast_days':7})))
    if intent in ('integral','suelo'): jobs.append(('suelo_nitrogeno',lambda:c.external('https://rest.isric.org/soilgrids/v2.0/properties/query',{'lat':lat,'lon':lon,'property':'nitrogen','depth':'0-5cm','value':'mean'})))
    if intent in ('integral','pasturas'): jobs.append(('escenas_sentinel',lambda:c.scenes(lat,lon,polygon)))
    if intent in ('integral','sequia'): jobs.append(('nasa_firms',lambda:c.firms(lat,lon,polygon)))
    if intent in ('integral','clima'): jobs.append(('enso_global',lambda:c.enso_multisource()))
    # Consultas de dominio en paralelo: una API lenta no debe bloquear todo el informe.
    if jobs:
        with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as pool:
            futures={pool.submit(fn): key for key,fn in jobs}
            for future in as_completed(futures):
                key=futures[future]
                try: extra[key]={'status':'recibido','payload':future.result()}
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
    water_assets=water_assets or []
    field_markers=field_markers or []
    if water_assets:
        kinds={}
        for a in water_assets:kinds[a.get('type','otro')]=kinds.get(a.get('type','otro'),0)+1
        findings.append({'topic':'Agua / infraestructura','status':'inventario declarado','text':f'{len(water_assets)} elementos registrados en el lote: '+', '.join(f'{v} {k}' for k,v in kinds.items())+'. Se consideran infraestructura declarada, no detección satelital.'})
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
    enso_src=sources.get('enso_global',{})
    if intent in ('integral','clima'):
        ed=(enso_src.get('payload',{}).get('data',{}) if enso_src.get('status')=='recibido' else {})
        received_enso=[k for k,v in ed.items() if v.get('status')=='recibido']
        if received_enso:
            findings.append({'topic':'ENSO global','status':'consenso multifuente','text':f'Consulta ENSO contrastada en {len(received_enso)} centros: '+', '.join(received_enso)+'. DOTS conserva cada fuente por separado y no convierte una discrepancia en falsa certeza.'})
        else: warnings.append('Las fuentes ENSO internacionales no respondieron en esta consulta; el informe no inventa un estado ENSO.')
    firms_src=sources.get('nasa_firms',{})
    if intent in ('integral','sequia'):
        if firms_src.get('status')=='recibido':
            fd=firms_src.get('payload',{}).get('data',{}); det=fd.get('detections',[]) or []
            nearest=None
            for r in det:
                try:
                    la,lo=float(r.get('latitude')),float(r.get('longitude')); dy=(la-lat)*111.32; dx=(lo-lon)*111.32*math.cos(math.radians(lat)); dist=math.hypot(dx,dy); nearest=dist if nearest is None or dist<nearest else nearest
                except (TypeError,ValueError): pass
            extra_txt=f' La detección más próxima está a aproximadamente {nearest:.1f} km del centro de análisis.' if nearest is not None else ''
            findings.append({'topic':'Incendios / NASA FIRMS','status':'observado por sensor','text':f"NASA FIRMS / {fd.get('sensor','VIIRS')} devolvió {len(det)} detecciones térmicas en la ventana consultada de {fd.get('days',3)} días.{extra_txt} Cero detecciones no equivale a riesgo de incendio nulo."})
            if det: recommendations.append('Revisar las detecciones térmicas FIRMS y su distancia al lote; confirmar en terreno o con autoridades antes de atribuirlas a un incendio activo.')
        else: warnings.append('NASA FIRMS no respondió en esta consulta; no se interpreta la falla como ausencia de focos térmicos.')
    # Indicadores normalizados para informe: valor + unidad + referencia + lectura.
    metrics=[]
    if t is not None:
        metrics.append({'variable':'Temperatura','value':round(t,1),'unit':'°C','reference':'Contextual: estación, raza y categoría animal','reading':'Usar junto con humedad, radiación y THI','kind':'observado/modelado'})
    if rh is not None:
        metrics.append({'variable':'Humedad relativa','value':round(rh,0),'unit':'%','reference':'Contextual; no se interpreta aislada','reading':'Componente del estrés térmico','kind':'observado/modelado'})
    if thi is not None:
        r='Confort <72 | atención 72-78 | alto 79-83 | severo >=84'
        metrics.append({'variable':'THI bovino','value':round(thi,1),'unit':'índice','reference':r,'reading':'bajo' if thi<72 else 'atención' if thi<79 else 'alto' if thi<84 else 'severo','kind':'derivado'})
    if rain:
        bal=sum(rain)-sum(et)
        metrics.append({'variable':'Lluvia 7 días','value':round(sum(rain),1),'unit':'mm','reference':'Comparar con ET₀, histórico local y necesidad de la pastura','reading':f'Balance lluvia-ET₀ {bal:+.1f} mm','kind':'pronóstico'})
        metrics.append({'variable':'ET₀ 7 días','value':round(sum(et),1),'unit':'mm','reference':'Demanda atmosférica; comparar con lluvia y agua del suelo','reading':'demanda acumulada','kind':'pronóstico'})
    if soil is not None:
        metrics.append({'variable':'Humedad suelo 0-1 cm','value':round(soil,3),'unit':'m³/m³','reference':'Rango útil depende de textura, capacidad de campo y punto de marchitez','reading':'No clasificar como buena/mala sin propiedades hidráulicas del suelo','kind':'modelado'})
    # SoilGrids nitrogen is modelled total N; keep units/source semantics explicit and avoid universal agronomic thresholds.
    ns=sources.get('suelo_nitrogeno',{}).get('payload',{}).get('data',{})
    try:
        layers=ns.get('properties',{}).get('layers',[])
        vals=[]
        for layer in layers:
            for depth in layer.get('depths',[]):
                v=depth.get('values',{}).get('mean')
                if v is not None: vals.append(float(v))
        if vals:
            nv=vals[0]
            metrics.append({'variable':'Nitrógeno total SoilGrids','value':round(nv,1),'unit':'cg/kg (fuente)','reference':'Sin umbral universal: calibrar por suelo, pastura y análisis de laboratorio','reading':'Estimación modelada; no equivale a N disponible para la pastura','kind':'modelado'})
            findings.append({'topic':'Suelo / nitrógeno','status':'modelado','text':f'Nitrógeno total SoilGrids: {nv:.1f} cg/kg (unidad de la fuente, profundidad consultada 0-5 cm). Requiere contraste con análisis de laboratorio; no se interpreta como nitrógeno disponible.'})
    except Exception:
        pass
    if intent in ('integral','pasturas'):
        scenes=sources.get('escenas_sentinel',{}).get('payload',{}).get('data',{}).get('features',[])
        if scenes:
            cc=_num(scenes[0].get('properties',{}).get('eo:cloud_cover'))
            if cc is not None:
                metrics.append({'variable':'Nubosidad Sentinel-2','value':round(cc,1),'unit':'%','reference':'Preferible <20% para análisis visual; máscara por píxel obligatoria para índices','reading':'favorable' if cc<20 else 'usable con máscara' if cc<50 else 'limitante','kind':'observado por sensor'})

    received=sum(1 for s in sources.values() if s.get('status')=='recibido')
    failed=[k for k,s in sources.items() if s.get('status')!='recibido']
    if failed:warnings.append('Fuentes sin respuesta en esta consulta: '+', '.join(failed)+'.')
    score=_quality(received,warnings)
    if sum(rain)<5 and sum(et)>15: recommendations.append('Seguir la evolución del balance lluvia–ET₀; el pronóstico muestra demanda atmosférica superior al aporte de lluvia.')
    if not recommendations: recommendations.append('Mantener seguimiento; no surge una recomendación operativa fuerte con las variables verificadas disponibles.')
    return {
      'version':'DOTS Agentic 0.6','generated_at':datetime.now(timezone.utc).isoformat(),'point':[lat,lon],
      'polygon':polygon or None,'field_markers':field_markers,'prompt':prompt or QUICK['integral'],'intent':intent,
      'confidence':{'score':score,'label':'alta' if score>=80 else 'media' if score>=60 else 'limitada','received_sources':received,'failed_sources':len(failed)},
      'summary':f'Análisis {intent} construido con {received} fuentes recibidas. Confianza {score}/100.',
      'findings':findings,'metrics':metrics,'recommendations':recommendations,'warnings':warnings,
      'evidence':[{'source':k,'status':v.get('status'),'consulted_at':v.get('payload',{}).get('consulted_at'),'source_url':v.get('payload',{}).get('source_url'),'scope':v.get('payload',{}).get('scope')} for k,v in sources.items()],
      'raw':sources
    }

def _satellite_snapshot(result):
    """Build a real NASA GIBS MODIS image for the lot and overlay polygon/markers. Returns PNG bytes or None."""
    poly=result.get('polygon') or []
    if len(poly)<3:return None
    try:
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg
        xs=[float(x[1]) for x in poly]; ys=[float(x[0]) for x in poly]
        dx=max(max(xs)-min(xs),0.002); dy=max(max(ys)-min(ys),0.002); padx=dx*.18; pady=dy*.18
        bbox=(min(xs)-padx,min(ys)-pady,max(xs)+padx,max(ys)+pady)
        day=(datetime.now(timezone.utc).date()-timedelta(days=2)).isoformat()
        params={'SERVICE':'WMS','REQUEST':'GetMap','VERSION':'1.1.1','LAYERS':'MODIS_Terra_CorrectedReflectance_TrueColor','STYLES':'','FORMAT':'image/jpeg','TRANSPARENT':'FALSE','SRS':'EPSG:4326','BBOX':','.join(map(str,bbox)),'WIDTH':'1200','HEIGHT':'800','TIME':day}
        url='https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?'+urlencode(params)
        with urlopen(Request(url,headers={'User-Agent':'DOTS-Campo/1.7'}),timeout=20) as r: raw=r.read(6_000_000)
        if not raw.startswith((b'\xff\xd8',b'\x89PNG')):return None
        img=mpimg.imread(io.BytesIO(raw),format='jpg' if raw.startswith(b'\xff\xd8') else 'png')
        fig,ax=plt.subplots(figsize=(9,6),dpi=150); ax.imshow(img,extent=bbox,origin='upper')
        ring=poly+[poly[0]]; ax.plot([x[1] for x in ring],[x[0] for x in ring],linewidth=2.2)
        for m in result.get('field_markers',[]):
            try: ax.scatter([float(m['lon'])],[float(m['lat'])],s=28,marker='o'); ax.annotate(str(m.get('type','marca'))[:18],(float(m['lon']),float(m['lat'])),fontsize=6,xytext=(3,3),textcoords='offset points')
            except Exception: pass
        ax.set_xlim(bbox[0],bbox[2]);ax.set_ylim(bbox[1],bbox[3]);ax.set_xlabel('Longitud');ax.set_ylabel('Latitud');ax.set_title('NASA GIBS / MODIS Terra · '+day+' · lote y marcas DOTS',fontsize=9)
        out=io.BytesIO();fig.tight_layout();fig.savefig(out,format='png',bbox_inches='tight');plt.close(fig);out.seek(0);return out.getvalue()
    except Exception:return None

def pdf_bytes(result,name='Lote'):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether,Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.graphics.shapes import Drawing, PolyLine, String, Rect
    out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=15*mm,leftMargin=15*mm,topMargin=15*mm,bottomMargin=15*mm,title='DOTS / CAMPO — Informe técnico agroambiental')
    st=getSampleStyleSheet(); cyan=colors.HexColor('#16b9c4'); navy=colors.HexColor('#10232d'); muted=colors.HexColor('#526a73')
    st.add(ParagraphStyle(name='Cover',parent=st['Title'],fontSize=24,leading=27,textColor=navy,spaceAfter=5))
    st.add(ParagraphStyle(name='Kicker',parent=st['BodyText'],fontSize=8,leading=10,textColor=cyan,fontName='Helvetica-Bold',spaceAfter=4))
    st.add(ParagraphStyle(name='Small2',parent=st['BodyText'],fontSize=8,leading=10,textColor=muted))
    st.add(ParagraphStyle(name='Section',parent=st['Heading2'],fontSize=14,leading=17,textColor=navy,spaceBefore=8,spaceAfter=6))
    point=result['point']; poly=result.get('polygon') or []
    story=[Paragraph('DOTS / CAMPO',st['Kicker']),Paragraph('Informe técnico agroambiental',st['Cover']),Paragraph(name,st['Heading2']),Spacer(1,4)]
    meta=[['Coordenada de análisis',f'{point[0]:.5f}, {point[1]:.5f}'],['Fecha de generación',result.get('generated_at','')[:19]+' UTC'],['Motor',result.get('version','DOTS Agentic')],['Fuentes recibidas',str(result.get('confidence',{}).get('received_sources','—'))],['Confianza operativa',f"{result.get('confidence',{}).get('score','—')}/100 · {result.get('confidence',{}).get('label','')}" ]]
    if poly:
        # simple local planar metrics
        lat0=sum(x[0] for x in poly)/len(poly)*math.pi/180; R=6378137
        xy=[(R*x[1]*math.pi/180*math.cos(lat0),R*x[0]*math.pi/180) for x in poly]
        area=abs(sum(xy[i][0]*xy[(i+1)%len(xy)][1]-xy[(i+1)%len(xy)][0]*xy[i][1] for i in range(len(xy)))/2)/10000
        
        per=0.0
        for i in range(len(poly)):
            a,b=poly[i],poly[(i+1)%len(poly)]
            p1,p2=math.radians(a[0]),math.radians(b[0]); dp=math.radians(b[0]-a[0]); dl=math.radians(b[1]-a[1])
            hv=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
            per += 2*6371*math.asin(min(1,math.sqrt(hv)))
        meta.append(['Lote delimitado',f'{len(poly)} vértices · {area:.1f} ha · perímetro {per:.2f} km'])
    t=Table(meta,colWidths=[48*mm,120*mm]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#e8f4f5')),('TEXTCOLOR',(0,0),(0,-1),navy),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#b9c9ce')),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),5)]));story+=[t,Spacer(1,10)]
    if poly:
        snap=_satellite_snapshot(result)
        if snap:
            story += [Paragraph('Imagen satelital del lote',st['Section']),Image(io.BytesIO(snap),width=165*mm,height=110*mm),Paragraph('NASA GIBS / MODIS Terra. Polígono y marcas DOTS superpuestos. La resolución de MODIS no permite identificar animales ni infraestructura pequeña.',st['Small2']),Spacer(1,7)]
        else:
            story += [Paragraph('Imagen satelital del lote',st['Section']),Paragraph('NASA GIBS no devolvió una imagen válida durante la generación. El informe conserva el polígono y las marcas sin sustituir la imagen por datos ficticios.',st['Small2']),Spacer(1,5)]
        xs=[x[1] for x in poly];ys=[x[0] for x in poly]; minx,maxx=min(xs),max(xs);miny,maxy=min(ys),max(ys); w,h=155*mm,60*mm; d=Drawing(w,h);d.add(Rect(0,0,w,h,fillColor=colors.HexColor('#f4f8f8'),strokeColor=colors.HexColor('#cbdadd')))
        pts=[]
        for la,lo in poly:
            px=8*mm+(lo-minx)/(maxx-minx or 1)*(w-16*mm); py=8*mm+(la-miny)/(maxy-miny or 1)*(h-16*mm);pts.extend([px,py])
        pts.extend(pts[:2]);d.add(PolyLine(pts,strokeColor=cyan,strokeWidth=2))
        for m in result.get('field_markers',[]):
            try:
                la,lo=float(m.get('lat')),float(m.get('lon')); px=8*mm+(lo-minx)/(maxx-minx or 1)*(w-16*mm); py=8*mm+(la-miny)/(maxy-miny or 1)*(h-16*mm)
                if 0<=px<=w and 0<=py<=h:
                    col=colors.HexColor('#d9534f') if m.get('type')=='incendio' else colors.HexColor('#159a78'); d.add(Rect(px-1.5*mm,py-1.5*mm,3*mm,3*mm,fillColor=col,strokeColor=colors.white))
            except (TypeError,ValueError): pass
        d.add(String(5*mm,h-6*mm,'Polígono DOTS · marcas territoriales incluidas · no sustituye plano catastral',fontSize=7,fillColor=muted));story+=[d,Spacer(1,8)]
    story += [Paragraph('Resumen ejecutivo',st['Section']),Paragraph(result.get('summary',''),st['BodyText']),Paragraph(f"<b>Confianza {result['confidence']['score']}/100:</b> indicador operativo de disponibilidad de fuentes; no equivale a certeza estadística.",st['Small2']),Spacer(1,6)]
    story.append(Paragraph('Indicadores, rangos de referencia e interpretación',st['Section']))
    mrows=[['Variable','Valor','Rango / referencia','Lectura']]
    for m in result.get('metrics',[]):
        val=f"{m.get('value','—')} {m.get('unit','')}".strip()
        mrows.append([m.get('variable',''),val,m.get('reference',''),m.get('reading','')])
    if len(mrows)>1:
        mt=Table(mrows,repeatRows=1,colWidths=[32*mm,25*mm,70*mm,42*mm]); mt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#c4d1d5')),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f9f9')])]))
        story += [mt,Spacer(1,8)]
    # Gráfico operativo: lluvia vs ET0 de 7 días. No inventa datos: usa la serie recibida.
    clima_raw=result.get('raw',{}).get('clima',{}).get('payload',{}).get('data',{})
    dd=clima_raw.get('daily',{}) if isinstance(clima_raw,dict) else {}
    dates=(dd.get('time') or [])[:7]; rr=(dd.get('precipitation_sum') or [])[:7]; ee=(dd.get('et0_fao_evapotranspiration') or [])[:7]
    if dates and rr:
        story.append(Paragraph('Gráfico - lluvia y demanda atmosférica',st['Section']))
        cw,ch=165*mm,58*mm; d=Drawing(cw,ch); d.add(Rect(0,0,cw,ch,fillColor=colors.HexColor('#f7faf9'),strokeColor=colors.HexColor('#d5e0e2')))
        vals=[float(x or 0) for x in rr]+[float(x or 0) for x in ee]; vmax=max(vals+[1]); n=max(1,len(dates)); base=10*mm; top=48*mm; usable=top-base; group=(cw-16*mm)/n
        for i,day in enumerate(dates):
            x=8*mm+i*group; rv=float(rr[i] or 0) if i<len(rr) else 0; ev=float(ee[i] or 0) if i<len(ee) else 0
            rh=usable*rv/vmax; eh=usable*ev/vmax
            d.add(Rect(x,base,group*.32,rh,fillColor=cyan,strokeColor=None)); d.add(Rect(x+group*.38,base,group*.32,eh,fillColor=colors.HexColor('#d8a43b'),strokeColor=None))
            d.add(String(x,3*mm,str(day)[5:10],fontSize=6,fillColor=muted))
        d.add(String(8*mm,ch-6*mm,'Lluvia',fontSize=7,fillColor=cyan)); d.add(String(30*mm,ch-6*mm,'ET0',fontSize=7,fillColor=colors.HexColor('#9a6a12')))
        story += [d,Paragraph('Las barras comparan aporte previsto de lluvia y demanda atmosférica ET0. La lectura hídrica final debe considerar almacenamiento y propiedades del suelo.',st['Small2']),Spacer(1,7)]

    story.append(Paragraph('Hallazgos por dimensión',st['Section']))
    rows=[['Dimensión','Tipo','Resultado']]+[[x.get('topic',''),x.get('status',''),x.get('text','')] for x in result.get('findings',[])]
    tb=Table(rows,repeatRows=1,colWidths=[34*mm,30*mm,105*mm]);tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#c4d1d5')),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f9f9')])])) ;story+=[tb,Spacer(1,7)]
    enso=[x for x in result.get('findings',[]) if x.get('topic')=='ENSO global']
    if enso:
        story.append(Paragraph('Contexto climático global — ENSO',st['Section']))
        for x in enso: story.append(Paragraph(x.get('text',''),st['BodyText']))
        story.append(Paragraph('ENSO se utiliza como contexto climático y no como pronóstico puntual del establecimiento. DOTS lo cruza con observaciones y pronósticos regionales.',st['Small2']))
    water=[x for x in result.get('findings',[]) if x.get('topic')=='Agua / infraestructura']
    if water:
        story.append(Paragraph('Agua e infraestructura rural',st['Section']))
        for x in water: story.append(Paragraph(x.get('text',''),st['BodyText']))
    story.append(Paragraph('Recomendaciones operativas',st['Section']))
    for x in result.get('recommendations',[]):story.append(Paragraph('• '+x,st['BodyText']))
    story.append(Paragraph('Límites y advertencias',st['Section']))
    for x in result.get('warnings',[]):story.append(Paragraph('• '+x,st['BodyText']))
    story += [PageBreak(),Paragraph('APIs, evidencia y trazabilidad',st['Kicker']),Paragraph('Fuentes utilizadas en esta consulta',st['Section'])]
    ev=result.get('evidence',[]); ok=sum(1 for e in ev if e.get('status')=='recibido');story.append(Paragraph(f'<b>{len(ev)} fuentes intentadas · {ok} recibidas · {len(ev)-ok} sin dato.</b> Las fallas se conservan y no se transforman en ceros.',st['BodyText']))
    rows=[['Fuente/API','Estado','Consulta UTC','Procedencia']]
    for e in ev:rows.append([e.get('source',''),e.get('status',''),(e.get('consulted_at') or '')[:19],(e.get('source_url') or '').split('?')[0][:58]])
    table=Table(rows,repeatRows=1,colWidths=[34*mm,23*mm,38*mm,74*mm]);table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.25,colors.HexColor('#b8c7cc')),('BACKGROUND',(0,0),(-1,0),navy),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,-1),7),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f9f9')])]))
    story += [table,Spacer(1,8),Paragraph('<b>Clasificación:</b> observado = proviene de sensor/fuente; modelado/pronóstico = salida de modelo; derivado = cálculo DOTS; interpretación = conclusión operativa. DOTS no infiere NDVI, animales o bebederos sin medición verificable.',st['Small2'])]
    doc.build(story);return out.getvalue()
