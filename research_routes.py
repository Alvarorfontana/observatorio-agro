"""Additional research APIs: independent from the legacy dashboard and engine."""
import os, json
from flask import Blueprint, request, jsonify, Response
from urllib.parse import urlparse
from datetime import datetime, timezone
import research_connectors as c
import agentic_engine as agentic
import vegetation as veg
import climate_indices as ci

research_api=Blueprint('research_api',__name__,url_prefix='/api/fuentes')

def _int(args,key,default,lo,hi):
    try: v=int(args.get(key,default))
    except (TypeError,ValueError): raise ValueError(f'{key} inválido')
    if not lo<=v<=hi: raise ValueError(f'{key} fuera de rango ({lo}-{hi})')
    return v

VEGETATION={
  'ndvi':lambda p,a:veg.ndvi_open(p,_int(a,'days',120,15,365),_int(a,'scenes',6,1,10)),
  'ndvi-imagen':None,
  'sentinel-hub-ndvi':lambda p,a:veg.sentinel_hub_ndvi(p,_int(a,'days',180,15,730)),
  'openeo-ndvi':lambda p,a:veg.openeo_ndvi(p,_int(a,'days',120,15,365)),
  'gee-ndvi':lambda p,a:veg.gee_ndvi(p,_int(a,'ndvi_years',10,1,25)),
}

@research_api.get('/<name>')
def research_data(name):
    if name=='plataformas':
        return jsonify(c.platform_registry())
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
        if name in VEGETATION:
            if name=='ndvi-imagen':
                png,bounds=veg.ndvi_png(request.args.get('item',''),polygon,request.args.get('baseline'))
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
          'suelo':lambda:c.external('https://rest.isric.org/soilgrids/v2.0/properties/query',{'lat':lat,'lon':lon,'property':'nitrogen','depth':'0-5cm','value':'mean'}),
          'serie':lambda:c.external('https://archive-api.open-meteo.com/v1/archive',{'latitude':lat,'longitude':lon,'start_date':f'{endyear-years+1}-01-01','end_date':f'{endyear}-12-31','daily':'temperature_2m_mean,precipitation_sum','models':'era5','timezone':'UTC'}),
          'proyeccion':lambda:c.external('https://climate-api.open-meteo.com/v1/climate',{'latitude':lat,'longitude':lon,'start_date':'2031-01-01','end_date':'2040-12-31','models':'MPI_ESM1_2_XR','daily':'temperature_2m_mean,precipitation_sum'}),
          'indices':lambda:ci.agro_indices(lat,lon,_int(request.args,'index_years',10,3,30)),'teleconexiones':lambda:ci.psl_indices(),
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
    except Exception as e:return jsonify({'status':'sin dato','error':'La fuente no respondió válidamente','type':type(e).__name__}),502

@research_api.post('/analizar')
def report():
    """Único informe DOTS. Mantiene la ruta histórica, pero usa el mismo motor Agentic/PDF.
    Así la interfaz no puede generar dos informes con criterios diferentes.
    """
    try:
        d=request.get_json(silent=True) or {}
        lat,lon=c.coordinates({'lat':[d.get('lat')],'lon':[d.get('lon')]})
        result=agentic.analyze(lat,lon,str(d.get('prompt','Informe integral del lote')),d.get('polygon'),d.get('inaSeries'),d.get('waterAssets'),d.get('fieldMarkers'))
        pdf=agentic.pdf_bytes(result,str(d.get('nombre','Lote DOTS')))
        return Response(pdf,mimetype='application/pdf',headers={'Content-Disposition':'attachment; filename=DOTS-informe-territorial.pdf'})
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

@research_api.post('/agentic')
def agentic_analyze():
    try:
        d=request.get_json(silent=True) or {}
        lat,lon=c.coordinates({'lat':[d.get('lat')],'lon':[d.get('lon')]})
        result=agentic.analyze(lat,lon,str(d.get('prompt','')),d.get('polygon'),d.get('inaSeries'),d.get('waterAssets'),d.get('fieldMarkers'))
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
            result=agentic.analyze(lat,lon,str(d.get('prompt','')),d.get('polygon'),d.get('inaSeries'),d.get('waterAssets'),d.get('fieldMarkers'))
        pdf=agentic.pdf_bytes(result,str(d.get('nombre','Lote DOTS')))
        return Response(pdf,mimetype='application/pdf',headers={'Content-Disposition':'attachment; filename=DOTS-informe-agentic.pdf'})
    except ValueError as e:return jsonify({'error':str(e)}),400
    except Exception as e:return jsonify({'status':'sin dato','error':'No se pudo generar el informe Agentic','type':type(e).__name__}),502
