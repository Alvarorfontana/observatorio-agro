"""DOTS proof-of-concept API. Public upstreams only; no embedded credentials."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from datetime import datetime, timezone, timedelta
import json, math, io, os, gzip, time
from email.utils import parsedate_to_datetime
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import csv


def coordinates(q):
    lat, lon = float(q.get('lat', ['-28.507'])[0]), float(q.get('lon', ['-59.043'])[0])
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('Coordenadas inválidas')
    return lat, lon

def external(base, params):
    url = base + ('?' + urlencode(params) if params else '')
    with urlopen(Request(url, headers={'User-Agent': 'DOTS-Campo/1.1 ' + os.environ.get('DOTS_CONTACT_URL','')}), timeout=22) as r:
        result = json.load(r)
    return {'source_url': url, 'consulted_at': datetime.now(timezone.utc).isoformat(), 'data': result}


def text_source(url):
    """Fetch a public text/HTML source preserving provenance; never turns a failure into a climate value."""
    with urlopen(Request(url, headers={'User-Agent':'DOTS-Campo/1.2 '+os.environ.get('DOTS_CONTACT_URL','')}), timeout=18) as r:
        body=r.read(350000).decode('utf-8','ignore')
    return {'source_url':url,'consulted_at':datetime.now(timezone.utc).isoformat(),'text':body}

def enso_multisource():
    """Independent ENSO authorities used as a consensus/evidence layer."""
    sources={
      'noaa_cpc':'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/probabilities.php',
      'columbia_iri':'https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/',
      'wmo':'https://wmo.int/publication-series/el-ninola-nina-updates',
      'jma':'https://www.data.jma.go.jp/tcc/tcc/products/elnino/outlook.html',
      'bom_australia':'https://www.bom.gov.au/climate/enso/',
    }
    out={}
    def one(k,u):
        try:
            r=text_source(u); low=r['text'].lower()
            state='El Niño' if 'el niño' in low or 'el nino' in low else ('La Niña' if 'la niña' in low or 'la nina' in low else 'sin clasificación automática')
            # Presence is evidence; interpretation remains conservative because page structures can change.
            return k,{'status':'recibido','source_url':u,'consulted_at':r['consulted_at'],'state_hint':state}
        except Exception as e:return k,{'status':'sin dato','source_url':u,'error':type(e).__name__}
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        for k,v in pool.map(lambda kv:one(*kv),sources.items()):out[k]=v
    return {'source_url':'multi-source ENSO','consulted_at':datetime.now(timezone.utc).isoformat(),'data':out}

def variables(lat, lon):
    return external('https://api.open-meteo.com/v1/forecast', {
        'latitude':lat,'longitude':lon,'current':'temperature_2m,relative_humidity_2m,wind_speed_10m,surface_pressure',
        'hourly':'temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,precipitation_probability,precipitation,rain,showers,snowfall,snow_depth,pressure_msl,surface_pressure,cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,visibility,evapotranspiration,et0_fao_evapotranspiration,vapour_pressure_deficit,wind_speed_10m,wind_direction_10m,wind_gusts_10m,soil_temperature_0cm,soil_temperature_6cm,soil_temperature_18cm,soil_temperature_54cm,soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm,soil_moisture_9_to_27cm,soil_moisture_27_to_81cm,shortwave_radiation,direct_radiation,diffuse_radiation,direct_normal_irradiance,terrestrial_radiation',
        'daily':'temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration,uv_index_max,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,shortwave_radiation_sum,sunshine_duration,sunrise,sunset',
        'timezone':'auto','forecast_days':7})

AGENCIES = {
    'smn': ('SMN Argentina','https://w2b.smn.gov.ar/oapi/collections/urn:wmo:md:ar-smn:slt0ci/items'),
    'inmet': ('INMET Brasil','https://wis2bra.inmet.gov.br/oapi/collections/urn:wmo:md:br-inmet:synop/items'),
    'dmc': ('DMC Chile','https://wischile.meteochile.gob.cl/oapi/collections/urn:wmo:md:cl-meteochile:synop-onehours/items'),
    'eccc': ('ECCC Canadá','https://api.weather.gc.ca/collections/climate-hourly/items'),
}
def distance_km(lat,lon,coords):
    if not coords or len(coords)<2:return None
    a,b=math.radians(lat),math.radians(coords[1]);dl=math.radians(coords[0]-lon)
    h=math.sin((b-a)/2)**2+math.cos(a)*math.cos(b)*math.sin(dl/2)**2
    return round(6371*2*math.asin(math.sqrt(min(1,max(0,h)))),1)

def national(agency,lat,lon):
    name,url=AGENCIES[agency]
    start=(datetime.now(timezone.utc)-timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    end=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    bbox=f'{max(-180,lon-2)},{max(-90,lat-2)},{min(180,lon+2)},{min(90,lat+2)}'
    response=external(url,{'f':'json','limit':50,'bbox':bbox,'datetime':start+'/'+end,'sortby':'-UTC_DATE' if agency=='eccc' else '-reportTime'})
    d=response['data'];obs=[]
    for feature in d.get('features',[]):
        props=feature.get('properties',{});coords=(feature.get('geometry') or {}).get('coordinates')
        common={'station':props.get('wigos_station_identifier') or props.get('STATION_NAME'),'observed_at':props.get('phenomenonTime') or props.get('UTC_DATE'),'reported_at':props.get('reportTime'),'coordinates':coords,'distance_km':distance_km(lat,lon,coords)}
        if agency=='eccc':
            # Units documented by ECCC; preserve quality flags and original values.
            for key,unit in [('TEMP','°C'),('RELATIVE_HUMIDITY','%'),('PRECIP_AMOUNT','mm'),('WIND_SPEED','km/h'),('STATION_PRESSURE','kPa')]:
                obs.append({**common,'variable':key,'value':props.get(key),'unit':unit,'quality':props.get(key+'_FLAG')})
        else:obs.append({**common,'variable':props.get('name'),'value':props.get('value'),'unit':props.get('units'),'quality':None})
    d['observations']=obs;d['agency']=name;d['kind']='observación de estación';d['query_window']={'bbox':bbox,'start':start,'end':end,'limit':50}
    d['scope']='Muestra de registros recientes en ventana ±2 grados. No garantiza estación más cercana ni medición del lote; no incluye todo el archivo. Revisar distancia y fecha.'
    return response

_MET_CACHE={}
def met_norway(lat,lon):
    url='https://api.met.no/weatherapi/locationforecast/2.0/compact?'+urlencode({'lat':f'{lat:.4f}','lon':f'{lon:.4f}'})
    cached=_MET_CACHE.get(url)
    if cached and time.time()<cached[0]:return cached[1]
    req=Request(url,headers={'User-Agent':'DOTS-Campo/1.1 '+os.environ.get('DOTS_CONTACT_URL',''),'Accept-Encoding':'gzip'})
    with urlopen(req,timeout=22) as r:
        raw=r.read();raw=gzip.decompress(raw) if r.headers.get('Content-Encoding')=='gzip' else raw
        result={'source_url':url,'consulted_at':datetime.now(timezone.utc).isoformat(),'data':json.loads(raw)}
        expires=r.headers.get('Expires');until=parsedate_to_datetime(expires).timestamp() if expires else time.time()+600
    if len(_MET_CACHE)>64:_MET_CACHE.clear()
    _MET_CACHE[url]=(max(time.time()+60,until),result)
    return result

def nws(lat,lon):
    point=external(f'https://api.weather.gov/points/{lat:.4f},{lon:.4f}',{})
    station_url=point['data'].get('properties',{}).get('observationStations','')
    parsed=urlparse(station_url)
    if parsed.scheme!='https' or parsed.netloc!='api.weather.gov' or not parsed.path.startswith('/gridpoints/'):raise ValueError('No hay estaciones NWS para este punto')
    stations=external(station_url,{})
    features=stations['data'].get('features',[])
    if not features:raise ValueError('NWS no devolvió estaciones')
    valid=[f for f in features if (f.get('geometry') or {}).get('coordinates')]
    if not valid:raise ValueError('NWS no devolvió coordenadas de estación')
    nearest=min(valid,key=lambda f:distance_km(lat,lon,f['geometry']['coordinates']))
    sid=nearest['properties'].get('stationIdentifier','')
    if not sid.isalnum() or len(sid)>12:raise ValueError('Estación NWS inválida')
    response=external(f'https://api.weather.gov/stations/{sid}/observations/latest',{})
    d=response['data'];p=d.get('properties',{});coords=(d.get('geometry') or {}).get('coordinates');obs=[]
    for key in ('temperature','dewpoint','relativeHumidity','windSpeed','windDirection','barometricPressure','visibility','precipitationLastHour'):
        v=p.get(key) or {};obs.append({'station':sid,'variable':key,'value':v.get('value'),'unit':v.get('unitCode'),'quality':v.get('qualityControl'),'observed_at':p.get('timestamp'),'coordinates':coords,'distance_km':distance_km(lat,lon,coords)})
    d['observations']=obs;d['agency']='NOAA / NWS Estados Unidos';d['scope']='Observación de la estación más cercana entre las devueltas por NWS; cobertura estadounidense, no del lote.'
    response['lookup_urls']=[point['source_url'],stations['source_url']]
    return response

def historical(lat, lon):
    end = datetime.now(timezone.utc).date() - timedelta(days=30)
    start = end - timedelta(days=29)
    return external('https://power.larc.nasa.gov/api/temporal/daily/point', {
        'parameters':'T2M,RH2M,PRECTOTCORR','community':'AG','latitude':lat,'longitude':lon,
        'start':start.strftime('%Y%m%d'),'end':end.strftime('%Y%m%d'),'format':'JSON'})

def scenes(lat, lon):
    # GET search returns newest scenes by default. No unsupported sortby parameter.
    return external('https://earth-search.aws.element84.com/v1/search', {
        'collections':'sentinel-2-l2a','bbox':f'{max(-180,lon-.03)},{max(-90,lat-.03)},{min(180,lon+.03)},{min(90,lat+.03)}','limit':5})

def air_quality(lat,lon):
    return external('https://air-quality-api.open-meteo.com/v1/air-quality',{'latitude':lat,'longitude':lon,'hourly':'pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,dust,aerosol_optical_depth,uv_index,ammonia','forecast_days':3,'timezone':'UTC'})
def elevation(lat,lon):
    return external('https://api.open-meteo.com/v1/elevation',{'latitude':lat,'longitude':lon})
def ina_series(series,days=30,years=None):
    series=int(series);days=int(days)
    if not 1<=series<=999999 or not 1<=days<=31:raise ValueError('Serie o período INA inválidos')
    end=datetime.now(timezone.utc).date()
    if years is not None:
        years=int(years)
        if years not in (20,30) or series!=25500:raise ValueError('Histórico largo habilitado sólo para altura mensual Bella Vista, serie 25500')
        start=end.replace(year=end.year-years,day=1)
    else:start=end-timedelta(days=days)
    # This legacy INA API embeds query parameters in the path, as documented by its GUI.
    url='https://alerta.ina.gob.ar/pub/datos/datos&'+urlencode({'timeStart':start.isoformat(),'timeEnd':(end+timedelta(days=1)).isoformat(),'seriesId':series,'format':'json'})
    with urlopen(Request(url,headers={'User-Agent':'DOTS-Campo/1.1'}),timeout=22)as r:d=json.load(r)
    if d.get('mensaje') or 'data' not in d:raise ValueError('INA no devolvió una serie válida')
    return {'source_url':url,'consulted_at':datetime.now(timezone.utc).isoformat(),'data':d,'scope':'Serie de estación elegida explícitamente, no medición del lote. Unidad y procedimiento según responseHeader.seriesmetadata; fechas según fuente.'}
def usgs_water(lat,lon,site=None):
    end=datetime.now(timezone.utc).date();start=end-timedelta(days=30)
    params={'f':'json','limit':50,'datetime':start.isoformat()+'/'+end.isoformat()}
    if site:
        if not site.startswith('USGS-') or not site[5:].isdigit() or len(site)>20:raise ValueError('Código USGS inválido')
        params['monitoring_location_id']=site
    else:params['bbox']=f'{max(-180,lon-2)},{max(-90,lat-2)},{min(180,lon+2)},{min(90,lat+2)}'
    return external('https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily/items',params)
def nasa_catalogue(lat,lon,product='MOD13Q1'):
    allowed={'MOD13Q1':'061','MOD11A2':'061','MOD16A2GF':'061','MCD15A3H':'061'}
    if product not in allowed:raise ValueError('Producto NASA no habilitado')
    result=external('https://cmr.earthdata.nasa.gov/search/granules.json',{'short_name':product,'version':allowed[product],'bounding_box':f'{max(-180,lon-.03)},{max(-90,lat-.03)},{min(180,lon+.03)},{min(90,lat+.03)}','page_size':3,'sort_key':'-start_date'})
    result['scope']='Metadatos de archivos disponibles, no extracción de NDVI, temperatura, ET o LAI del lote.'
    return result
def satellite_catalogue(lat,lon,radar=False):
    base='https://stac.dataspace.copernicus.eu/v1/search' if radar else 'https://planetarycomputer.microsoft.com/api/stac/v1/search'
    result=external(base,{'collections':'sentinel-1-grd' if radar else 'landsat-c2-l2','bbox':f'{max(-180,lon-.03)},{max(-90,lat-.03)},{min(180,lon+.03)},{min(90,lat+.03)}','limit':3})
    result['scope']='Escenas y enlaces a bandas; valores raster, máscara de calidad y estadísticas del lote aún no procesados.'
    return result
def firms(lat,lon):
    key=os.environ.get('FIRMS_MAP_KEY','').strip()
    if not key:raise ValueError('FIRMS requiere FIRMS_MAP_KEY: solicitar clave gratuita con tu correo')
    area=f'{max(-180,lon-.5)},{max(-90,lat-.5)},{min(180,lon+.5)},{min(90,lat+.5)}'
    base='https://firms.modaps.eosdis.nasa.gov/api/area/csv/'
    url=base+key+'/VIIRS_SNPP_NRT/'+area+'/3'
    with urlopen(Request(url,headers={'User-Agent':'DOTS-Campo/1.1'}),timeout=22)as r:raw=r.read().decode()
    reader=csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or 'latitude' not in reader.fieldnames:raise ValueError('Respuesta FIRMS inválida; no interpretar error como cero incendios')
    rows=list(reader)
    return {'source_url':base+'[REDACTED]/VIIRS_SNPP_NRT/'+area+'/3','consulted_at':datetime.now(timezone.utc).isoformat(),'data':{'detections':rows,'sensor':'VIIRS_SNPP_NRT','days':3,'bbox':area},'scope':'Detecciones térmicas en ventana, no inventario completo de incendios ni conteo de animales.'}
def research_bundle(lat,lon,ina_id=None):
    jobs={'clima':lambda:variables(lat,lon),'aire':lambda:air_quality(lat,lon),'elevacion':lambda:elevation(lat,lon)}
    if ina_id:jobs['ina']=lambda:ina_series(ina_id,days=2)
    def run(item):
        key,fn=item
        try:return key,{'status':'recibido','payload':fn()}
        except Exception as e:return key,{'status':'sin dato','error':type(e).__name__}
    with ThreadPoolExecutor(max_workers=4)as pool:results=dict(pool.map(run,jobs.items()))
    return {'consulted_at':datetime.now(timezone.utc).isoformat(),'point':[lat,lon],'sources':results,'scope':'Informe JSON multifuente; nulos y fallas conservados. NO2/amoniaco del aire no equivalen a nitrógeno del suelo o proteína del pasto.'}


def pdf_report(lat, lon, name, ina_id=None):
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pagesizes import A4
    bundle=research_bundle(lat,lon,ina_id)
    output=io.BytesIO();canvas=Canvas(output,pagesize=A4);y=790
    def line(text,size=10):
        nonlocal y
        if y<55:canvas.showPage();y=790
        canvas.setFont('Helvetica',size);canvas.drawString(42,y,str(text)[:112]);y-=19
    line('OBSERVATORIO GANADERO | INFORME MULTIFUENTE',16)
    line(name[:70],13);line(f'Punto: {lat:.5f}, {lon:.5f} | Consulta UTC: {bundle["consulted_at"]}')
    line('Modelos, estaciones y relieve se identifican por separado. Sin sustitucion de datos.',9)
    for key,source in bundle['sources'].items():
        line(key.upper()+' | '+source['status'],13)
        if source['status']!='recibido':line('Sin dato: '+source.get('error','sin respuesta'));continue
        response=source['payload'];data=response['data']
        line('Consulta UTC: '+response['consulted_at'],8)
        # URLs may exceed a line: preserve full provenance in the accompanying JSON export.
        line('Proveedor: '+response['source_url'].split('?')[0],8)
        if key=='clima':
            current=data.get('current',{});line('Hora valida: '+str(current.get('time','Sin dato'))+' | '+str(data.get('timezone','')))
            for k,v in current.items():
                if k not in ('time','interval'):line(f'{k}: {v if v is not None else "Sin dato"} {data.get("current_units",{}).get(k,"")}')
            daily=data.get('daily',{});line('Pronostico diario',11)
            for i,date in enumerate(daily.get('time',[])):
                def value(k):
                    a=daily.get(k,[]);return a[i] if i<len(a) and a[i] is not None else 'Sin dato'
                line(f'{date}: Tmin {value("temperature_2m_min")} C; Tmax {value("temperature_2m_max")} C; lluvia {value("precipitation_sum")} mm',9)
        elif key=='aire':
            line('CAMS / pronostico en grilla. Hora UTC mostrada: '+str(data.get('hourly',{}).get('time',['Sin dato'])[0]),9)
            for k,a in data.get('hourly',{}).items():
                if k!='time':line(f'{k}: {a[0] if a and a[0] is not None else "Sin dato"} {data.get("hourly_units",{}).get(k,"")}')
        elif key=='elevacion':line('Elevacion DEM: '+str(data.get('elevation',['Sin dato'])[0])+' m')
        elif key=='ina':
            header=data.get('responseHeader',{});records=data.get('data',[])
            line('Estacion elegida, no medicion del lote. Serie: '+str(header.get('seriesid','')))
            line('Registros recibidos: '+str(len(records)))
            for record in records[-8:]:line(str(record.get('timestart'))+': '+str(record.get('valor','Sin dato'))+' '+str(header.get('seriesmetadata',{}).get('unit_abrev','')))
    line('NO2 / amoniaco atmosfericos no equivalen a nitrogeno del suelo ni proteina del pasto.',9)
    line('Consulta puntual al centroide aproximado, no promedio espacial del lote.',9)
    line('NDVI, animales, incendios y bebederos no tienen mediciones verificadas en este informe.',9)
    line('Exportar JSON para conservar respuestas completas, fechas, unidades y URLs.',9)
    canvas.save();return output.getvalue()

@lru_cache(maxsize=96)
def image_bytes(url):
    with urlopen(Request(url,headers={'User-Agent':'DOTS-Field-Research/1.0'}),timeout=18) as r:
        data=r.read(3_000_001)
        if len(data)>3_000_000:raise ValueError('Imagen demasiado grande')
        return data



def stac_search(base, lat, lon, collection=None, limit=5):
    """Search an official STAC endpoint around the selected point; returns metadata only."""
    params={'bbox':f'{max(-180,lon-.03)},{max(-90,lat-.03)},{min(180,lon+.03)},{min(90,lat+.03)}','limit':int(limit)}
    if collection: params['collections']=collection
    return external(base.rstrip('/')+'/search', params)

def copernicus_stac(lat,lon):
    return stac_search('https://stac.dataspace.copernicus.eu/v1',lat,lon,'sentinel-2-l2a',5)

def cnes_stac(lat,lon):
    return stac_search('https://geodes-portal.cnes.fr/api/stac',lat,lon,None,5)

def dlr_stac(lat,lon):
    return stac_search('https://geoservice.dlr.de/eoc/ogc/stac/v1',lat,lon,None,5)

def deafrica_stac(lat,lon):
    if not (-40 <= lat <= 40 and -30 <= lon <= 60):
        raise ValueError('Digital Earth Africa: el punto seleccionado está fuera de la cobertura africana')
    return stac_search('https://explorer.digitalearth.africa/stac',lat,lon,None,5)
