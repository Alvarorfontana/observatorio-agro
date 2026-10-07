"""Additional research APIs: independent from the legacy dashboard and engine."""
import os
from flask import Blueprint, request, jsonify, Response
from urllib.parse import urlparse
from datetime import datetime, timezone
import research_connectors as c

research_api=Blueprint('research_api',__name__,url_prefix='/api/fuentes')

@research_api.get('/<name>')
def research_data(name):
    if name=='estado':
        return jsonify({'public_adapters':['smn','inmet','dmc','eccc','nws','metnorway','aire','elevacion','ina','usgs','nasa-catalogo','productos-nasa','landsat','radar'], 'firms': 'credencial configurada, validar consulta' if os.environ.get('FIRMS_MAP_KEY') else 'pendiente de clave gratuita', 'scope':'Catálogos satelitales no son valores raster extraídos. Las restantes fuentes de la matriz siguen pendientes.'})
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
        years=int(request.args.get('years','30'))
        if years not in (20,30):raise ValueError('Seleccioná 20 o 30 años')
        endyear=datetime.now(timezone.utc).year-1
        jobs={key:lambda key=key:c.national(key,lat,lon) for key in c.AGENCIES}
        jobs.update({
          'variables':lambda:c.variables(lat,lon),'historico':lambda:c.historical(lat,lon),'escenas':lambda:c.scenes(lat,lon),
          'modelos':lambda:c.external('https://api.open-meteo.com/v1/forecast',{'latitude':lat,'longitude':lon,'hourly':'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m','models':'gfs_global,ecmwf_ifs025,icon_global,gem_global,jma_gsm,cma_grapes_global,meteofrance_arpege_world','forecast_days':3,'timezone':'auto'}),
          'rios':lambda:c.external('https://flood-api.open-meteo.com/v1/flood',{'latitude':lat,'longitude':lon,'daily':'river_discharge','forecast_days':7}),
          'suelo':lambda:c.external('https://rest.isric.org/soilgrids/v2.0/properties/query',{'lat':lat,'lon':lon,'property':'nitrogen','depth':'0-5cm','value':'mean'}),
          'serie':lambda:c.external('https://archive-api.open-meteo.com/v1/archive',{'latitude':lat,'longitude':lon,'start_date':f'{endyear-years+1}-01-01','end_date':f'{endyear}-12-31','daily':'temperature_2m_mean,precipitation_sum','models':'era5','timezone':'UTC'}),
          'proyeccion':lambda:c.external('https://climate-api.open-meteo.com/v1/climate',{'latitude':lat,'longitude':lon,'start_date':'2031-01-01','end_date':'2040-12-31','models':'MPI_ESM1_2_XR','daily':'temperature_2m_mean,precipitation_sum'}),
          'nws':lambda:c.nws(lat,lon),'metnorway':lambda:c.met_norway(lat,lon),
          'aire':lambda:c.air_quality(lat,lon),'elevacion':lambda:c.elevation(lat,lon),
          'ina':lambda:c.ina_series(request.args.get('series',''),request.args.get('days','30'),request.args.get('years') if request.args.get('series')=='25500' else None),
          'usgs':lambda:c.usgs_water(lat,lon,request.args.get('site')),
          'nasa-catalogo':lambda:c.nasa_catalogue(lat,lon,request.args.get('product','MOD13Q1')),
          'productos-nasa':lambda:c.external('https://appeears.earthdatacloud.nasa.gov/api/product',{}),
          'landsat':lambda:c.satellite_catalogue(lat,lon),'radar':lambda:c.satellite_catalogue(lat,lon,True),
          'firms':lambda:c.firms(lat,lon),'informe':lambda:c.research_bundle(lat,lon,request.args.get('inaSeries')),
        })
        if name not in jobs:return jsonify({'error':'Fuente no habilitada'}),404
        if name=='firms' and not os.environ.get('FIRMS_MAP_KEY'):return jsonify({'status':'pendiente de credencial','error':'Solicitar MAP_KEY gratuita de NASA FIRMS y cargar FIRMS_MAP_KEY en Vercel. No hay conteo disponible.'}),409
        return jsonify(jobs[name]())
    except ValueError as e:return jsonify({'status':'sin dato','error':str(e)}),400
    except Exception as e:return jsonify({'status':'sin dato','error':'La fuente no respondió válidamente','type':type(e).__name__}),502

@research_api.post('/analizar')
def report():
    try:
        d=request.get_json();lat,lon=c.coordinates({'lat':[d.get('lat')],'lon':[d.get('lon')]})
        return Response(c.pdf_report(lat,lon,str(d.get('nombre','Lote')),d.get('inaSeries')),mimetype='application/pdf',headers={'Content-Disposition':'attachment; filename=informe_campo.pdf'})
    except ValueError as e:return jsonify({'error':str(e)}),400
    except Exception as e:return jsonify({'status':'sin dato','error':'No se pudo generar el informe','type':type(e).__name__}),502
