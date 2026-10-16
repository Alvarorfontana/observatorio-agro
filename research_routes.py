"""Additional research APIs: independent from the legacy dashboard and engine."""
import os, json
from flask import Blueprint, request, jsonify, Response
from urllib.parse import urlparse
from datetime import datetime, timezone
import research_connectors as c
import agentic_engine as agentic
import vegetation as veg
import climate_indices as ci
import report_typst as rt
import rainfall as rain
import forecast_stats as fst
import contact
import alerts as alr
import sustainability as sus
import forage as fgr
import costs as cst
import spectral
import radar as rdr
import water_balance as wbal
import enso_chain as enso
import enso_sa
import mapbiomas as mbx
import cobertura_ee as cee
import herd as hrd
import pasture_gpw as gpw
import avisos_web as avw
import salud as sld
import caminos as cmn
import emergencia as emg
import enso_report
import monitor as mon
import soil_wetness as sw
import cuenca as cca
import cuenca_report as ccr
import earthalign as eal
import soil_moisture_sar as sms
import ina_a5

research_api=Blueprint('research_api',__name__,url_prefix='/api/fuentes')

def _upstream_error(e):
    """Error de una fuente externa explicado: límite de consultas (429), fuente caída (503) o respuesta inválida (502)."""
    code=getattr(getattr(e,'response',None),'status_code',None)
    if code==429:
        return jsonify({'status':'sin dato','error':'La fuente llegó a su límite de consultas. Probá de nuevo en un minuto.','upstream':429}),429
    if code in (500,502,503,504) or type(e).__name__ in ('ConnectTimeout','ReadTimeout','ConnectionError','Timeout'):
        return jsonify({'status':'sin dato','error':'La fuente externa no está respondiendo ahora. Probá de nuevo en unos minutos.','upstream':code,'type':type(e).__name__}),503
    return jsonify({'status':'sin dato','error':'La fuente no respondió válidamente','upstream':code,'type':type(e).__name__}),502

def _int(args,key,default,lo,hi):
    try: v=int(args.get(key,default))
    except (TypeError,ValueError): raise ValueError(f'{key} inválido')
    if not lo<=v<=hi: raise ValueError(f'{key} fuera de rango ({lo}-{hi})')
    return v

VEGETATION={
  'ndvi':lambda p,a:veg.ndvi_best(p,_int(a,'days',120,15,365),_int(a,'scenes',6,1,10)),
  'ndvi-modis':lambda p,a:veg.ndvi_modis(p,_int(a,'days',120,30,760)),
  'ndvi-zonas':lambda p,a:veg.ndvi_zones(p,_int(a,'days',60,15,180)),
  'ndvi-zonas-imagen':None,
  'ndvi-imagen':None,
  'sentinel-hub-ndvi':lambda p,a:veg.sentinel_hub_ndvi(p,_int(a,'days',180,15,730)),
  'openeo-ndvi':lambda p,a:veg.openeo_ndvi(p,_int(a,'days',120,15,365)),
  'gee-ndvi':lambda p,a:veg.gee_ndvi(p,_int(a,'ndvi_years',10,1,25)),
  'indices-espectrales':lambda p,a:spectral.compute(p,[x.strip() for x in a.get('indices','').split(',') if x.strip()] or None,_int(a,'days',120,15,365)),
  'radar-agua':lambda p,a:rdr.flooding(p,_int(a,'days',60,12,365)),
  'humedad-sar':lambda p,a:sms.analyze(p,_int(a,'days',60,12,365),_int(a,'scenes',8,2,12)),
  'nivel-rio':lambda p,a:ina_a5.analyze(p,_int(a,'days',30,3,365)),
  'mapbiomas':lambda p,a:mbx.history(p),
  'cobertura-reciente':lambda p,a:cee.dynamic_world(p),
  'cambios-lote':lambda p,a:cee.changes(p),
  'riesgo-hidrico':lambda p,a:__import__('riesgo_hidrico').analyze(p),
  'suelos-50mil':lambda p,a:__import__('suelos_ba').analyze(p),
  'ndvi-anomalia':lambda p,a:__import__('perfil_suelo').ndvi_anomaly(p),
  'etr-lote':lambda p,a:__import__('perfil_suelo').et_real(p),
  'heladas-satelite':lambda p,a:__import__('perfil_suelo').frost_satellite(p),
  'pasto-historia':lambda p,a:gpw.history(p),
}

@research_api.get('/monitor')
def sources_monitor():
    if request.args.get('rutas'):
        from flask import current_app
        try: return jsonify(mon.routes(current_app._get_current_object(),request.args['rutas']))
        except ValueError as e: return jsonify({'error':str(e)}),400
    if request.args.get('suelo'):
        try: lat,lon=(float(x) for x in request.args['suelo'].split(','))
        except ValueError: return jsonify({'error':'suelo=lat,lon'}),400
        c.coordinates({'lat':[lat],'lon':[lon]})
        return jsonify(mon.soil_trace(lat,lon))
    return jsonify(mon.check())

@research_api.get('/contacto/canal')
def contact_channel():
    return jsonify(contact.channel())

@research_api.get('/earthalign')
def clima_descripcion():
    """Descripción en lenguaje natural del estado atmosférico (EarthAlign / MeteoLIP) del punto más cercano."""
    try:
        lat,lon=c.coordinates({'lat':[request.args.get('lat')],'lon':[request.args.get('lon')]})
        return jsonify(eal.describe(lat,lon,request.args.get('fecha')))
    except ValueError as e: return jsonify({'status':'sin dato','error':str(e)}),400
    except Exception as e: return jsonify({'status':'sin dato','error':'No se pudo leer la descripción del estado atmosférico','type':type(e).__name__}),502

@research_api.get('/earthalign/estado')
def clima_descripcion_estado():
    """Diagnóstico del conector: cuántos recortes hay y qué falta para activarlo."""
    return jsonify(eal.status())

@research_api.post('/forraje')
def lot_forage():
    try:
        d=request.get_json(silent=True) or {}
        lat,lon=c.coordinates({'lat':[d.get('lat')],'lon':[d.get('lon')]})
        heads=d.get('heads'); heads=int(heads) if isinstance(heads,(int,float)) and 0<heads<=200000 else None
        return jsonify(fgr.forage(lat,lon,d.get('polygon'),d.get('ndvi') if isinstance(d.get('ndvi'),dict) else None,
                                  str(d.get('kind') or 'pastizal'),float(d.get('use') or fgr.DEFAULT_USE),heads))
    except ValueError as e: return jsonify({'status':'sin dato','error':str(e)}),400
    except Exception as e: return jsonify({'status':'sin dato','error':'No se pudo estimar la producción de pasto','type':type(e).__name__}),502

@research_api.post('/costos')
def lot_costs():
    try:
        d=request.get_json(silent=True) or {}
        lat,lon=c.coordinates({'lat':[d.get('lat')],'lon':[d.get('lon')]})
        return jsonify(cst.analyze(lat,lon,d.get('destination'),d.get('dest_lat'),d.get('dest_lon'),
                                   d.get('params') if isinstance(d.get('params'),dict) else {}))
    except ValueError as e: return jsonify({'status':'sin dato','error':str(e)}),400
    except Exception as e: return jsonify({'status':'sin dato','error':'No se pudieron calcular costos y logística','type':type(e).__name__}),502

@research_api.post('/avisos/suscribir')
def avisos_subscribe():
    try: return jsonify(avw.subscribe(request.get_json(silent=True) or {}))
    except ValueError as e: return jsonify({'status':'rechazado','error':str(e)}),400
    except Exception: return jsonify({'status':'error','error':'No se pudo registrar el correo.'}),502

@research_api.post('/ganado')
def herd_analysis():
    try:
        d=request.get_json(silent=True) or {}
        lat,lon=c.coordinates({'lat':[d.get('lat')],'lon':[d.get('lon')]})
        verts=d.get('vertices') or []
        area=float(d['area_ha']) if d.get('area_ha') else (veg.area_ha(verts) if len(verts)>=3 else None)
        forage=d.get('forage') if isinstance(d.get('forage'),dict) and d['forage'].get('growth_rate_30d') is not None else None
        err=None
        if not forage and len(verts)>=3:
            try: forage=fgr.forage(lat,lon,verts,kind=d.get('kind') or 'pastizal')['data']
            except Exception as e: err=f'Pasto del lote: {str(e)[:140] or type(e).__name__}'
        out=hrd.analyze(lat,lon,d.get('herd') or [],area,forage)
        if err: out['data']['errors']['pasto']=err
        return jsonify(out)
    except ValueError as e: return jsonify({'status':'sin dato','error':str(e)}),400
    except Exception as e: return jsonify({'status':'sin dato','error':'No se pudo analizar el rodeo','type':type(e).__name__}),502

@research_api.post('/eudr/pdf')
def eudr_pdf():
    try:
        d=request.get_json(silent=True) or {}
        lot=d.get('lot') if isinstance(d.get('lot'),dict) else {}
        verts=lot.get('vertices') or []
        veg.require_polygon(verts)
        sust=d.get('sustentabilidad') if isinstance(d.get('sustentabilidad'),dict) else None
        if not sust or not sust.get('deforestation'):
            cen=[sum(v[0] for v in verts)/len(verts),sum(v[1] for v in verts)/len(verts)]
            sust={'deforestation':sus.deforestation(verts)['data'],'carbon':sus.carbon(cen[0],cen[1],veg.area_ha(verts),d.get('heads') or None)['data']}
        pdf,gj,h=rt.eudr_pdf(lot,str(d.get('establecimiento') or '')[:160],sust,d.get('readiness') if isinstance(d.get('readiness'),dict) else None)
        return Response(pdf,mimetype='application/pdf',headers={'Content-Disposition':'attachment; filename=DOTS-libre-de-deforestacion.pdf','X-DOTS-GeoJSON-SHA256':h})
    except ValueError as e: return jsonify({'error':str(e)}),400
    except Exception as e: return jsonify({'status':'sin dato','error':'No se pudo generar la verificación','type':type(e).__name__}),502

@research_api.post('/eudr/geojson')
def eudr_geojson():
    try:
        d=request.get_json(silent=True) or {}
        lot=d.get('lot') if isinstance(d.get('lot'),dict) else {}
        verts=lot.get('vertices') or []
        veg.require_polygon(verts)
        gj=rt.geojson_lot(verts,str(lot.get('name') or 'Lote')[:80],lot.get('areaHa'))
        return Response(json.dumps(gj,ensure_ascii=False,indent=2),mimetype='application/geo+json',headers={'Content-Disposition':'attachment; filename=DOTS-lote-geolocalizacion.geojson'})
    except ValueError as e: return jsonify({'error':str(e)}),400

@research_api.post('/eudr/whisp')
def eudr_whisp():
    import whisp_eudr
    try:
        d=request.get_json(silent=True) or {}
        product=str(d.get('product') or 'bovino')[:20]
        token=str(d.get('token') or '')[:80] or None
        gj=None
        if not token:
            lot=d.get('lot') if isinstance(d.get('lot'),dict) else {}
            verts=lot.get('vertices') or []
            veg.require_polygon(verts)
            gj=rt.geojson_lot(verts,str(lot.get('name') or 'Lote')[:80],lot.get('areaHa'))
        return jsonify(whisp_eudr.check(gj,token,product))
    except ValueError as e: return jsonify({'status':'sin dato','error':str(e)}),400
    except Exception as e: return jsonify({'status':'sin dato','error':'Whisp no respondió','type':type(e).__name__}),502

@research_api.post('/alertas')
def lot_alerts():
    try:
        d=request.get_json(silent=True) or {}
        lat,lon=c.coordinates({'lat':[d.get('lat')],'lon':[d.get('lon')]})
        return jsonify(alr.evaluate(lat,lon,d.get('polygon'),d.get('known') if isinstance(d.get('known'),dict) else None))
    except ValueError as e: return jsonify({'status':'sin dato','error':str(e)}),400
    except Exception as e: return jsonify({'status':'sin dato','error':'No se pudieron evaluar las alertas','type':type(e).__name__}),502

@research_api.post('/contacto')
def contact_send():
    try:
        return jsonify(contact.send(request.get_json(silent=True) or {}))
    except PermissionError as e: return jsonify({'status':'sin canal','error':str(e)}),409
    except ValueError as e: return jsonify({'status':'inválido','error':str(e)}),400
    except Exception as e: return jsonify({'status':'error','error':'No se pudo enviar la consulta. Probá de nuevo en unos minutos.'}),502

@research_api.get('/<name>')
def research_data(name):
    if name=='plataformas':
        return jsonify(c.platform_registry())
    if name=='cuenca':
        try: return jsonify(cca.analyze())
        except Exception as e: return _upstream_error(e)
    if name=='eventos-extremos':
        try:
            import eventos
            lat=float(request.args.get('lat','-28.5')); lon=float(request.args.get('lon','-59'))
            return jsonify(eventos.extremos(lat,lon))
        except ValueError: return jsonify({'status':'sin dato','error':'Coordenadas inválidas'}),400
        except Exception as e: return _upstream_error(e)
    if name=='transito-crecida':
        a=request.args.get('desde',''); b=request.args.get('hasta','')
        ids={x['id']:x for x in cca.STATIONS}
        if a not in ids or b not in ids: return jsonify({'status':'sin dato','error':'Localidad desconocida'}),400
        reach=ccr.downstream_days(a)
        if b not in reach: return jsonify({'status':'sin dato','error':f"{ids[b]['place']} no está río abajo de {ids[a]['place']}"}),200
        edges,lags=ccr._graph()
        # camino tramo por tramo
        path=[b]
        while path[-1]!=a:
            prev=next((u for u,ds in edges.items() if path[-1] in ds and u in reach),None)
            if prev is None: break
            path.append(prev)
        path=path[::-1]
        tramos=[{'desde':ids[u]['place'],'hasta':ids[v]['place'],'dias':(lags.get(f'{u}>{v}') or {}).get('days'),'corr':(lags.get(f'{u}>{v}') or {}).get('corr')} for u,v in zip(path,path[1:])]
        return jsonify({'status':'recibido','data':{'desde':ids[a]['place'],'hasta':ids[b]['place'],'dias':reach[b],'tramos':tramos,
                        'periodo':cca.load_normals().get('lags_period')}})
    if name=='carbono-suelo':
        try:
            lat=float(request.args.get('lat','')); lon=float(request.args.get('lon',''))
            if not (-60<=lat<=15 and -90<=lon<=-30): return jsonify({'status':'sin dato','error':'Fuera de Sudamérica'}),400
            return jsonify(sus.carbon(lat,lon))
        except ValueError: return jsonify({'status':'sin dato','error':'Coordenadas inválidas'}),400
        except Exception as e: return _upstream_error(e)
    if name=='salud-sudamerica':
        try:
            r=jsonify(sld.live()); r.headers['Cache-Control']='public, s-maxage=10800'
            return r
        except Exception as e: return _upstream_error(e)
    if name=='avisos':
        data=avw.feed(request.args.get('localidad') or None)
        if request.args.get('formato')=='rss':
            return Response(avw.rss(data),mimetype='application/rss+xml',headers={'Cache-Control':'public, s-maxage=600','Access-Control-Allow-Origin':'*'})
        r=jsonify(c.envelope(data,'data/avisos.json','avisos de crecidas','DOTS · INA · Prefectura'))
        r.headers['Cache-Control']='public, s-maxage=600'; r.headers['Access-Control-Allow-Origin']='*'
        return r
    if name=='precios-hacienda':
        try:
            r=jsonify(c.envelope(cst.mag_prices(),cst.MAG,'precios de hacienda de referencia','Mercado Agroganadero de Cañuelas'))
            r.headers['Cache-Control']='public, s-maxage=3600'
            return r
        except Exception as e: return _upstream_error(e)
    if name=='catastro-parcela':
        import catastro
        try: plat=float(request.args.get('lat','')); plon=float(request.args.get('lon',''))
        except ValueError: return jsonify({'status':'sin dato','error':'Coordenadas inválidas'}),400
        try: return jsonify(catastro.parcel_at(plat,plon))
        except Exception as e: return _upstream_error(e)
    if name in ('rayos','goes-heladas'):
        import datastore
        d=datastore.load('rayos.json',branch='rayos',ttl=300) if name=='rayos' else datastore.load('goes_heladas.json')
        if not d: return jsonify({'status':'sin dato','error':'Todavía no hay datos del satélite GOES-19: la tarea automática se está poniendo en marcha.'}),404
        r=jsonify(c.envelope(d,'https://registry.opendata.aws/noaa-goes/','rayos en las últimas 3 horas' if name=='rayos' else 'heladas de la última noche','NOAA GOES-19'))
        r.headers['Cache-Control']='public, s-maxage=300' if name=='rayos' else 'public, s-maxage=1800'
        return r
    if name in ('focos','focos-csv'):
        import focos as fz
        try: env=fz.analyze(_int(request.args,'dias',2,1,5))
        except PermissionError: return jsonify({'status':'pendiente de credencial','error':'Falta la clave gratuita de NASA FIRMS (FIRMS_MAP_KEY) en Vercel.'}),409
        except Exception as e: return _upstream_error(e)
        if name=='focos-csv':
            rows=(env.get('data') or {}).get('points') or []
            return Response(fz.to_csv(rows),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="DOTS-focos-{datetime.now(timezone.utc).strftime("%Y-%m-%d")}.csv"','Cache-Control':'public, s-maxage=900'})
        r=jsonify(env); r.headers['Cache-Control']='public, s-maxage=900, stale-while-revalidate=1800'
        return r
    if name=='rinde-agua':
        import datastore
        d=datastore.load('rinde_agua.json')
        if not d or not d.get('places'):
            return jsonify({'status':'sin dato','error':'La simulación de rinde por agua todavía no corrió. Se actualiza los lunes, de septiembre a abril.'}),404
        r=jsonify(c.envelope(d,'https://github.com/aquacropos/aquacrop','rinde por agua de maíz y soja (AquaCrop)','AquaCrop-OSPy (FAO) · ERA5 / Open-Meteo'))
        r.headers['Cache-Control']='public, s-maxage=3600'
        return r
    if name=='enso-sudamerica':
        try:
            out=enso_sa.live()
            r=jsonify(out)
            r.headers['Cache-Control']='public, s-maxage=600' if (out.get('data') or {}).get('live_error') else 'public, s-maxage=10800, stale-while-revalidate=86400'
            return r
        except Exception as e: return _upstream_error(e)
    if name=='enso-localidad':
        try:
            r=jsonify(enso_sa.place_detail(request.args.get('id','')))
            r.headers['Cache-Control']='public, s-maxage=86400'
            return r
        except LookupError as e: return jsonify({'status':'sin dato','error':str(e)}),404
        except Exception as e: return _upstream_error(e)
    if name=='enso-informe':
        try:
            lat=float(request.args.get('lat','')); lon=float(request.args.get('lon',''))
            if not (-60<=lat<=15 and -90<=lon<=-30): return jsonify({'status':'sin dato','error':'Fuera de Sudamérica'}),400
            place=(request.args.get('nombre') or 'Mi lote')[:60]
            out=enso_report.pdf(lat,lon,place)
            safe=''.join(ch if ch.isalnum() else '-' for ch in place.encode('ascii','ignore').decode()).strip('-') or 'lote'
            fname=f"DOTS-El-Nino-{safe}-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.pdf"
            return Response(out,mimetype='application/pdf',headers={'Content-Disposition':f'attachment; filename="{fname}"','Cache-Control':'no-store'})
        except ValueError: return jsonify({'status':'sin dato','error':'Coordenadas inválidas'}),400
        except Exception as e: return _upstream_error(e)
    if name=='gfm-capas':
        try:
            import gfm
            return jsonify(gfm.web_layers())
        except Exception as e: return _upstream_error(e)
    if name=='alertas-resumen':
        try: return jsonify(cca.resumen())
        except Exception as e: return _upstream_error(e)
    if name=='localidad-informe':
        sid=request.args.get('id','')
        if sid not in {x['id'] for x in cca.STATIONS}:return jsonify({'status':'sin dato','error':'Localidad desconocida'}),400
        try:
            res=cca.analyze()
            if res.get('status')!='recibido':return jsonify({'status':'sin dato','error':res.get('error') or 'Sin datos de la cuenca'}),502
            out=ccr.local_pdf(res['data'],sid)
            place=next(x['place'] for x in cca.STATIONS if x['id']==sid)
            safe=''.join(ch if ch.isalnum() else '-' for ch in place.encode('ascii','ignore').decode()).strip('-')
            fname=f"DOTS-Alerta-{safe}-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.pdf"
            return Response(out,mimetype='application/pdf',headers={'Content-Disposition':f'attachment; filename="{fname}"','Cache-Control':'no-store'})
        except Exception as e: return _upstream_error(e)
    if name=='cuenca-informe':
        try:
            res=cca.analyze()
            if res.get('status')!='recibido':return jsonify({'status':'sin dato','error':res.get('error') or 'Sin datos de la cuenca'}),502
            out=ccr.pdf(res['data'])
            fname=f"DOTS-Cuenca-del-Plata-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.pdf"
            return Response(out,mimetype='application/pdf',headers={'Content-Disposition':f'attachment; filename="{fname}"','Cache-Control':'no-store'})
        except Exception as e: return _upstream_error(e)
    if name=='inta-suelos-wms':
        try: return jsonify(c.ogc_capabilities('inta-suelos-wms'))
        except Exception as e: return jsonify({'status':'sin dato','error':'INTA WMS no respondió válidamente','type':type(e).__name__}),502
    if name=='estado':
        return jsonify({'public_adapters':['smn','inmet','dmc','eccc','nws','metnorway','aire','elevacion','ina','usgs','nasa-catalogo','productos-nasa','landsat','radar','copernicus-stac','cnes-stac','dlr-stac','deafrica-stac'], 'new_open_stac':['Copernicus Data Space','CNES GEODES','DLR EOC','Digital Earth Africa'], 'firms': 'credencial configurada' if os.environ.get('FIRMS_MAP_KEY') else 'pendiente de clave gratuita', 'protocol':'botón → conector → API → dato → procesamiento → visualización → informe', 'scope':'Catálogo, raster y variable procesada se informan como estados distintos; nunca se sustituyen faltantes.'})
    try:
        q={key:[value] for key,value in request.args.items()}
        if name=='tile':
            z,x,y=(int(request.args.get(k,'-1')) for k in ('z','x','y'))
            if not 0<=z<=19 or not 0<=x<2**z or not 0<=y<2**z:raise ValueError('Tesela inválida')
            return Response(c.image_bytes(f'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'),mimetype='image/jpeg')
        if name=='foto':
            url=request.args.get('asset','');p=urlparse(url)
            if p.scheme!='https' or p.netloc!='sentinel-cogs.s3.us-west-2.amazonaws.com' or not p.path.startswith('/sentinel-s2-l2a-cogs/') or not p.path.endswith('/preview.jpg') or p.query:raise ValueError('Fotografía inválida')
            return Response(c.image_bytes(url),mimetype='image/jpeg')
        lat,lon=c.coordinates(q)
        polygon=None
        if request.args.get('polygon'):
            try: polygon=json.loads(request.args.get('polygon','null'))
            except Exception: raise ValueError('Polígono inválido')
        if name=='lluvia':
            if request.args.get('job'):
                return jsonify(rain.result(request.args.get('job','')))
            return jsonify(rain.start(polygon if polygon else [[lat-0.01,lon-0.01],[lat-0.01,lon+0.01],[lat+0.01,lon+0.01],[lat+0.01,lon-0.01]]))
        if name=='cobertura-imagen':
            png,bounds=sus.cover_png(request.args.get('item',''),polygon)
            return Response(png,mimetype='image/png',headers={'X-DOTS-Bounds':json.dumps(bounds),'Cache-Control':'public, max-age=604800'})
        if name=='sustentabilidad':
            heads=_int(request.args,'heads',0,0,200000)
            def _both():
                out={'deforestation':None,'carbon':None,'mapbiomas':None,'recent_cover':None,'changes':None,'errors':{}}
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=5) as pool:
                    fm=pool.submit(mbx.history,polygon) if polygon else None
                    extra={k:pool.submit(fn,polygon) for k,fn in (('recent_cover',cee.dynamic_world),('changes',cee.changes))} if polygon else {}
                    fd=pool.submit(sus.deforestation,polygon) if polygon else None
                    fc=pool.submit(sus.carbon,lat,lon,veg.area_ha(polygon) if polygon else None,heads or None)
                    try: out['carbon']=fc.result()['data']
                    except Exception as e: out['errors']['carbono']=type(e).__name__
                    if fd:
                        try: out['deforestation']=fd.result()['data']
                        except Exception as e: out['errors']['deforestación']=type(e).__name__
                    else: out['errors']['deforestación']='Dibujá un lote para verificar cobertura arbórea'
                    if fm:
                        try:
                            rm=fm.result(timeout=50)
                            out['mapbiomas']=rm.get('data')
                            if not out['mapbiomas']: out['errors']['mapbiomas']=rm.get('error') or 'sin dato'
                        except PermissionError: out['errors']['mapbiomas']='Earth Engine sin credencial'
                        except Exception as e: out['errors']['mapbiomas']=type(e).__name__
                    for k,fut in extra.items():
                        try:
                            rr=fut.result(timeout=50); out[k]=rr.get('data')
                            if not out[k]: out['errors'][k]=rr.get('error') or 'sin dato'
                        except PermissionError: out['errors'][k]='Earth Engine sin credencial'
                        except Exception as e: out['errors'][k]=type(e).__name__
                ok=out['carbon'] or out['deforestation'] or out['mapbiomas']
                return c.envelope(out,'multi','deforestación, carbono y emisiones','Impact Observatory · ESA · ISRIC · IPCC','recibido' if ok else 'sin dato',None if ok else 'Sin datos')
            return jsonify(_both())
        if name in VEGETATION:
            if name=='ndvi-zonas-imagen':
                png,bounds=veg.zones_png(request.args.get('item',''),polygon,request.args.get('cuts','').split(','),request.args.get('baseline'))
                return Response(png,mimetype='image/png',headers={'X-DOTS-Bounds':json.dumps(bounds),'Cache-Control':'public, max-age=86400'})
            if name=='ndvi-imagen':
                png,bounds=veg.ndvi_png(request.args.get('item',''),polygon,request.args.get('baseline'),'rgb' if request.args.get('mode')=='rgb' else 'ndvi')
                return Response(png,mimetype='image/png',headers={'X-DOTS-Bounds':json.dumps(bounds),'Cache-Control':'public, max-age=86400'})
            return jsonify(VEGETATION[name](polygon,request.args))
        years=int(request.args.get('years','30'))
        if years not in (20,30):raise ValueError('Seleccioná 20 o 30 años')
        endyear=datetime.now(timezone.utc).year-1
        jobs={key:lambda key=key:c.national(key,lat,lon) for key in c.AGENCIES}
        jobs.update({
          'variables':lambda:c.variables(lat,lon),'historico':lambda:c.historical(lat,lon),'escenas':lambda:c.scenes(lat,lon,polygon),
          'modelos':lambda:c.external('https://api.open-meteo.com/v1/forecast',{'latitude':lat,'longitude':lon,'hourly':'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m','models':'gfs_global,ecmwf_ifs025,icon_global,gem_global,jma_gsm,cma_grapes_global,meteofrance_arpege_world','forecast_days':3,'timezone':'auto'}),
          'rios':lambda:c.external('https://flood-api.open-meteo.com/v1/flood',{'latitude':lat,'longitude':lon,'daily':'river_discharge','forecast_days':7}),
          'suelo':lambda:c.soil_full(lat,lon),'balance-agua':lambda:wbal.water_balance(lat,lon),'enso-cadena':lambda:enso.chain(),'enso-lote':lambda:enso.lot_impact(lat,lon),'enso-tablero':lambda:enso_report.board(lat,lon),'caminos':lambda:cmn.analyze(lat,lon),'emergencia':lambda:emg.analyze(lat,lon,polygon),'catalogo-indices':lambda:c.envelope(spectral.catalog_summary(),'','catálogo de índices','awesome-spectral-indices'),
          'serie':lambda:c.external('https://archive-api.open-meteo.com/v1/archive',{'latitude':lat,'longitude':lon,'start_date':f'{endyear-years+1}-01-01','end_date':f'{endyear}-12-31','daily':'temperature_2m_mean,precipitation_sum','models':'era5','timezone':'UTC'}),
          'proyeccion':lambda:c.projection(lat,lon),
          'estadistica':lambda:fst.analyze(lat,lon),'estacional':lambda:fst.analyze(lat,lon),'humedad-nasa':lambda:sw.analyze(lat,lon),
          'indices':lambda:ci.agro_indices(lat,lon,_int(request.args,'index_years',10,3,30)),'teleconexiones':lambda:ci.psl_indices(),'el-nino':lambda:__import__('enso_panel').enso_panel(),
          'nws':lambda:c.nws(lat,lon),'metnorway':lambda:c.met_norway(lat,lon),
          'aire':lambda:c.air_quality(lat,lon),'elevacion':lambda:c.elevation(lat,lon),
          'ina':lambda:c.ina_series(request.args.get('series',''),request.args.get('days','30'),request.args.get('years') if request.args.get('series')=='25500' else None),
          'usgs':lambda:c.usgs_water(lat,lon,request.args.get('site')),
          'nasa-catalogo':lambda:c.nasa_catalogue(lat,lon,request.args.get('product','MOD13Q1')),
          'productos-nasa':lambda:c.external('https://appeears.earthdatacloud.nasa.gov/api/product',{}),
          'landsat':lambda:c.satellite_catalogue(lat,lon),'radar':lambda:c.satellite_catalogue(lat,lon,True),
          'gibs':lambda:c.nasa_gibs_capabilities(),'copernicus-stac':lambda:c.stac_search('https://stac.dataspace.copernicus.eu/v1',lat,lon,'sentinel-2-l2a',5,polygon),'cnes-stac':lambda:c.cnes_stac(lat,lon),'dlr-stac':lambda:c.dlr_stac(lat,lon),'deafrica-stac':lambda:c.deafrica_stac(lat,lon),'firms':lambda:c.firms(lat,lon,polygon),'nasa-power-30':lambda:c.nasa_power_long(lat,lon,years),'enso':lambda:c.enso_multisource(),**{k:(lambda k=k:c.credential_status(k)) for k in ['era5-cds','sentinel-hub','noaa-cdo','usgs-m2m','nasa-earthdata','copernicus-marine','gee','openaq','gfw','aemet','eumetsat','jaxa','mosdac','kma','fengyun']},'informe':lambda:c.research_bundle(lat,lon,request.args.get('inaSeries')),
        })
        if name not in jobs:return jsonify({'error':'Fuente no habilitada'}),404
        if name=='firms' and not os.environ.get('FIRMS_MAP_KEY'):return jsonify({'status':'pendiente de credencial','error':'Solicitar MAP_KEY gratuita de NASA FIRMS y cargar FIRMS_MAP_KEY en Vercel. No hay conteo disponible.'}),409
        return jsonify(jobs[name]())
    except PermissionError as e:return jsonify({'status':'requiere credencial','error':str(e)}),409
    except ValueError as e:return jsonify({'status':'sin dato','error':str(e)}),400
    except Exception as e:return _upstream_error(e)

@research_api.post('/campo-pdf')
def campo_pdf():
    """Informe de campo: lomas, planos y bajos, suelos y código QR del mapa para el celular (funciona sin señal)."""
    try:
        d=request.get_json(silent=True) or {}
        polygon=d.get('polygon')
        if not isinstance(polygon,list) or len(polygon)<3: return jsonify({'error':'Dibujá el límite del campo'}),400
        import campo_offline
        name=str(d.get('nombre') or 'Mi campo')[:60]
        out,url=campo_offline.pdf(name,polygon,d.get('lat'),d.get('lon'))
        safe=''.join(ch if ch.isalnum() else '-' for ch in name.encode('ascii','ignore').decode()).strip('-') or 'campo'
        return Response(out,mimetype='application/pdf',headers={'Content-Disposition':f'attachment; filename="DOTS-informe-de-campo-{safe}.pdf"','Cache-Control':'no-store'})
    except PermissionError: return jsonify({'error':'Earth Engine no está configurado'}),409
    except ValueError as e: return jsonify({'error':str(e)}),400
    except Exception as e: return jsonify({'status':'sin dato','error':f'No se pudo generar el informe de campo ({type(e).__name__}): {str(e)[:160]}'}),502


@research_api.post('/analizar')
def report():
    """Único informe DOTS. Mantiene la ruta histórica, pero usa el mismo motor Agentic/PDF.
    Así la interfaz no puede generar dos informes con criterios diferentes.
    """
    try:
        d=request.get_json(silent=True) or {}
        lat,lon=c.coordinates({'lat':[d.get('lat')],'lon':[d.get('lon')]})
        result=agentic.analyze(lat,lon,str(d.get('prompt','Informe integral del lote')),d.get('polygon'),d.get('inaSeries'),d.get('waterAssets'),d.get('fieldMarkers'),_known(d))
        pdf,engine=rt.pdf(result,str(d.get('nombre','Lote DOTS')),d.get('extras') if isinstance(d.get('extras'),dict) else None)
        return Response(pdf,mimetype='application/pdf',headers={'Content-Disposition':'attachment; filename=DOTS-informe-territorial.pdf','X-DOTS-Report-Engine':engine})
    except ValueError as e:return jsonify({'error':str(e)}),400
    except Exception as e:return jsonify({'status':'sin dato','error':'No se pudo generar el informe DOTS','type':type(e).__name__}),502




@research_api.get('/geocode')
def geocode():
    try:
        q=(request.args.get('q') or '').strip()
        if len(q)<2:return jsonify({'error':'Escribí una localidad, paraje o región'}),400
        data=c.external('https://nominatim.openstreetmap.org/search',{'q':q,'format':'jsonv2','limit':5,'addressdetails':1})
        rows=data.get('data',[]) if isinstance(data,dict) else []
        return jsonify({'results':[{'lat':x.get('lat'),'lon':x.get('lon'),'display_name':x.get('display_name'),'type':x.get('type'),'address':x.get('address',{})} for x in rows[:5]],'source':'OpenStreetMap Nominatim'})
    except Exception as e:return jsonify({'error':'El buscador geográfico no respondió','type':type(e).__name__}),502

@research_api.get('/agentic/status')
def agentic_status():
    """Inventario operativo: distingue fuentes sin credencial, públicas y capacidades aún no implementadas."""
    return jsonify({
      'engine':'DOTS Agentic', 'version':'0.5',
      'publicas':['Open-Meteo','Open-Meteo Flood','ERA5/Open-Meteo Archive','SoilGrids','SMN','INMET','DMC','ECCC','NWS','MET Norway','INA','USGS','NASA CMR','Landsat STAC','Sentinel catálogo'],
      'credenciales':{
        'NASA FIRMS': 'configurada' if os.environ.get('FIRMS_MAP_KEY') else 'requiere FIRMS_MAP_KEY',
      },
      'procesamiento':{'NDVI Sentinel-2 por lote':'abierto · Planetary Computer','NDVI Sentinel Hub':'requiere CDSE','NDVI openEO':'requiere CDSE','NDVI MODIS histórico':'requiere Earth Engine'},
      'procesamiento_pendiente':['EVI/NDWI','biomasa/pastura','detección satelital validada de cuerpos de agua','sensores de ganado'], 'enso':['NOAA CPC/RONI','Columbia IRI','WMO','JMA','BOM Australia'],
      'regla':'Una fuente caída se reporta como faltante y no impide que las demás produzcan el análisis.'
    })

def _known(d):
    """Resultados de módulos que el panel ya calculó (extras/known): el motor los lee y los cruza."""
    k=d.get('known') if isinstance(d.get('known'),dict) else d.get('extras') if isinstance(d.get('extras'),dict) else {}
    return {key:k[key] for key in ('ndvi','forraje','lluvia','estadistica','alertas','sustentabilidad','costos','lot') if isinstance(k.get(key),dict)}

@research_api.post('/agentic')
def agentic_analyze():
    try:
        d=request.get_json(silent=True) or {}
        lat,lon=c.coordinates({'lat':[d.get('lat')],'lon':[d.get('lon')]})
        result=agentic.analyze(lat,lon,str(d.get('prompt','')),d.get('polygon'),d.get('inaSeries'),d.get('waterAssets'),d.get('fieldMarkers'),_known(d))
        # Raw payloads remain available through existing endpoints; keep conversational response compact.
        if not d.get('include_raw'):
            result.pop('raw',None)
        return jsonify(result)
    except ValueError as e:return jsonify({'error':str(e)}),400
    except Exception as e:return jsonify({'status':'sin dato','error':'No se pudo completar el análisis Agentic','type':type(e).__name__}),502

@research_api.post('/agentic/pdf')
def agentic_pdf():
    try:
        d=request.get_json(silent=True) or {}
        lat,lon=c.coordinates({'lat':[d.get('lat')],'lon':[d.get('lon')]})
        supplied=d.get('analysis')
        if isinstance(supplied,dict) and supplied.get('findings') is not None and supplied.get('point'):
            result=supplied
        else:
            result=agentic.analyze(lat,lon,str(d.get('prompt','')),d.get('polygon'),d.get('inaSeries'),d.get('waterAssets'),d.get('fieldMarkers'),_known(d))
        pdf,engine=rt.pdf(result,str(d.get('nombre','Lote DOTS')),d.get('extras') if isinstance(d.get('extras'),dict) else None)
        return Response(pdf,mimetype='application/pdf',headers={'Content-Disposition':'attachment; filename=DOTS-informe-agentic.pdf','X-DOTS-Report-Engine':engine})
    except ValueError as e:return jsonify({'error':str(e)}),400
    except Exception as e:return jsonify({'status':'sin dato','error':'No se pudo generar el informe Agentic','type':type(e).__name__}),502
