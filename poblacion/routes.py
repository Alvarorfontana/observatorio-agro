import os
from datetime import datetime,timezone
from pathlib import Path
from flask import Blueprint,request,jsonify,current_app,send_from_directory
from itsdangerous import URLSafeTimedSerializer,BadSignature,SignatureExpired
from .geometry import prepare,InputError
from . import worldpop

bp=Blueprint('population',__name__)
WEB=Path(__file__).resolve().parents[1]/'public'/'poblacion'


def _signing_key():
    """Clave propia si está cargada; si no, una derivada (HMAC) de un secreto que el servidor ya tiene, para no pedir otra variable."""
    key=current_app.config.get('POPULATION_SIGNING_KEY') or os.environ.get('DOTS_POPULATION_SIGNING_KEY')
    if key: return key
    import hashlib,hmac
    for name in ('GOOGLE_APPLICATION_CREDENTIALS_JSON','CDSE_CLIENT_SECRET','SENTINEL_HUB_CLIENT_SECRET','DMC_TOKEN','WHISP_API_KEY'):
        base=os.environ.get(name)
        if base and len(base)>=16:
            return hmac.new(base.encode(),b'dots-population-signing-v1',hashlib.sha256).hexdigest()
    return None


def signer():
    key=_signing_key()
    if not key:
        raise RuntimeError('Configurar DOTS_POPULATION_SIGNING_KEY en el servidor.')
    return URLSafeTimedSerializer(key,salt='dots-population-v1')


@bp.get('/poblacion')
def page():
    return send_from_directory(WEB,'index.html')


@bp.get('/poblacion/assets/<path:name>')
def assets(name):
    return send_from_directory(WEB/'assets',name)


@bp.get('/api/poblacion/estado')
def state():
    configured=bool(_signing_key())
    return jsonify(module='Población y riesgo climático',worldpop='ready' if configured else 'configuration_required',
                   populace='licensed_raster_import',method='polygon_intersection',
                   population_type='estimated_resident_population',supports=['Polygon','MultiPolygon'],
                   attribution='WorldPop, University of Southampton — CC BY 4.0; verificar ficha del producto.',
                   page='/poblacion')


@bp.get('/api/poblacion/datasets')
def available_datasets():
    base=[{'id':'worldpop-api','provider':'WorldPop','group':'Población total','unit':'people','years':[2015,2030]}]
    if not os.environ.get('DOTS_POPULATION_MANIFEST'):
        return jsonify(datasets=base)
    try:
        from .raster import datasets,public_dataset
    except ImportError:
        return jsonify(datasets=base,note='Lector GeoTIFF no instalado en este servidor.')
    try:
        return jsonify(datasets=[{'id':'worldpop-api','provider':'WorldPop','group':'Población total',
                                   'unit':'people','years':[2015,2030]}]+[public_dataset(e) for e in datasets()])
    except InputError as exc: return jsonify(error=str(exc)),503


@bp.post('/api/poblacion/exposicion')
def exposure():
    try:
        payload=request.get_json(silent=True)
        prepared=prepare(payload)
        dataset=payload.get('dataset','worldpop-api')
        if dataset!='worldpop-api':
            from .raster import datasets,estimate
            from rasterio.errors import RasterioError
            entry=next((e for e in datasets() if e['id']==dataset),None)
            if entry is None: raise InputError('Dataset local no configurado o no autorizado.')
            prepared['year']=entry['year']
            try:
                calculation=estimate(prepared,entry)
            except (RasterioError,OSError):
                return jsonify(error='No se pudo leer el dataset configurado. Revisá su formato y acceso en el servidor.'),503
            return jsonify(**prepared,**calculation,calculated_at=datetime.now(timezone.utc).isoformat())
        signed=signer()
        total_task=worldpop.submit(prepared['area'],prepared['year'])
        exposure_task=None
        if prepared['intersection']:
            exposure_task=worldpop.submit(prepared['intersection'],prepared['year'])
        token=signed.dumps({'context':prepared,'total_task':total_task,'exposure_task':exposure_task})
        return jsonify(status='pending',token=token,poll_after_seconds=3),202
    except InputError as exc: return jsonify(error=str(exc)),400
    except RuntimeError as exc:
        if isinstance(exc,worldpop.UpstreamError): return jsonify(error=str(exc)),502
        return jsonify(error='Falta configurar la clave de firma del módulo en el servidor.'),503


@bp.post('/api/poblacion/resultado')
def result():
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('token'),str):
        return jsonify(error='Se requiere el token del cálculo.'),400
    try:
        job=signer().loads(data['token'],max_age=7200)
        context=job['context']
        total=worldpop.poll(job['total_task'])
        given=context.get('hazard_given',True)
        exposed=worldpop.poll(job['exposure_task']) if job['exposure_task'] else {'status':'complete','population':0.0 if given else None}
        if total['status']!='complete' or exposed['status']!='complete':
            return jsonify(status='pending',poll_after_seconds=3),202
        p,e=total['population'],exposed['population']
        # No ocultar discrepancias de los agregados de un proveedor.
        if e is not None and e>p+max(1e-6,p*1e-6):
            return jsonify(error='Los agregados del proveedor no son consistentes: exposición mayor que total.'),502
        percent=100*e/p if (e is not None and p>0) else None
        return jsonify(status='complete',population_total=p,population_exposed=e,
                       exposed_percent=percent,density_per_km2=p/context['area_km2'],
                       population_group='Población total',
                       **context,source={'provider':'WorldPop','api':worldpop.BASE,'resolution_requested':'100m',
                                        'year':context['year'],'attribution':'WorldPop, University of Southampton',
                                        'license_reference':'https://www.worldpop.org/faq/'},
                       calculated_at=datetime.now(timezone.utc).isoformat(),
                       method='WorldPop total_population en zona e intersección geométrica con amenaza.',
                       interpretation='Población residente estimada expuesta; no personas damnificadas registradas.',
                       coverage_status='not_reported_by_aggregation_api',
                       notes=['La API de agregación no informa aquí la cobertura válida del ráster.',
                              'El año de población puede diferir de la fecha de amenaza.',
                              'La fase ENOS es contexto declarado; el cruce no atribuye causalidad.',
                              'Los totales pueden ser fraccionarios por el modelo y su agregación.'])
    except (BadSignature,SignatureExpired): return jsonify(error='Consulta vencida o token inválido. Iniciá un nuevo cálculo.'),400
    except worldpop.UpstreamError as exc: return jsonify(error=str(exc)),502
    except RuntimeError: return jsonify(error='Configuración de firma no disponible.'),503


@bp.post('/api/poblacion/informe')
def report_pdf():
    from flask import Response
    from . import report
    try:
        out=report.pdf(request.get_json(silent=True))
        name='DOTS-poblacion-expuesta-'+datetime.now(timezone.utc).strftime('%Y-%m-%d')+'.pdf'
        return Response(out,mimetype='application/pdf',headers={'Content-Disposition':f'attachment; filename="{name}"','Cache-Control':'no-store'})
    except InputError as exc: return jsonify(error=str(exc)),400
    except Exception: return jsonify(error='No se pudo generar el informe PDF.'),500


@bp.post('/api/poblacion/crecida/informe')
def flood_report_pdf():
    from flask import Response
    from . import flood_report
    payload=request.get_json(silent=True)
    try:
        out=flood_report.pdf(payload)
        filename='DOTS-poblacion-ribereña-'+datetime.now(timezone.utc).strftime('%Y-%m-%d')+'.pdf'
        return Response(out,mimetype='application/pdf',
                        headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})
    except ValueError as exc:
        return jsonify(error=str(exc)),400
    except Exception:
        current_app.logger.exception('Error al generar PDF de población ribereña')
        return jsonify(error='No se pudo generar el PDF de población ribereña.'),500


@bp.get('/api/poblacion/localidades')
def riverside_places():
    import cuenca as cc
    r=jsonify(places=[{'id':s['id'],'place':s['place'],'river':s['river'],'lat':s.get('lat'),'lon':s.get('lon')} for s in cc.STATIONS])
    r.headers['Cache-Control']='public, s-maxage=86400'
    return r


@bp.get('/api/poblacion/crecida')
def flood_people():
    from . import crecida
    try:
        out=crecida.at_station(request.args.get('id',''))
        r=jsonify(out)
        if out.get('status')=='recibido': r.headers['Cache-Control']='public, s-maxage=604800'
        return r
    except LookupError as exc: return jsonify(error=str(exc)),404
    except PermissionError: return jsonify(error='Earth Engine sin credencial en el servidor.'),503
    except Exception as exc: return jsonify(error=f'No se pudo calcular ({type(exc).__name__}).'),502


@bp.get('/api/poblacion/barrios')
def informal_settlements():
    """Barrios populares detectados por radar (calculado por la tarea «Barrios populares por radar»)."""
    import datastore
    data=datastore.load('barrios_radar.json')
    ren=datastore.load('renabap_localidades.json')
    if data and not any(p.get('informal_ha') is not None for p in data.get('places') or []):
        data=dict(data,places=[])          # corrida sin mapa (cuota agotada o cortada): se muestra solo la evaluación
    from . import barrios_variables as bv
    variables={'entradas':bv.lista(((data or {}).get('model') or {}).get('capas_mas_utiles')),'salidas':bv.salidas()}
    if not data:
        return jsonify(data=None,renabap=ren,variables=variables,error='El mapa del modelo todavía no está calculado: correr la tarea «Barrios populares por radar» en GitHub Actions.'),200
    r=jsonify(data=data,renabap=ren,variables=variables,image_base='/api/poblacion/barrios/')
    r.headers['Cache-Control']='public, s-maxage=3600'
    return r


def _pdf_response(content, filename):
    from flask import Response
    return Response(content, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"', 'Cache-Control': 'no-store'})


def _slug(text):
    import unicodedata
    t = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode()
    return ''.join(ch if ch.isalnum() else '-' for ch in t).strip('-')


@bp.get('/api/poblacion/barrios/informe')
def informal_settlements_report():
    """Informe PDF de barrios populares de una localidad (RENABAP, río, población por altura y mapa de radar)."""
    from . import barrios_report
    sid = request.args.get('id', '')
    try:
        out, place = barrios_report.local_pdf(sid)
        return _pdf_response(out, f"DOTS-barrios-populares-{_slug(place)}-{datetime.now(timezone.utc):%Y-%m-%d}.pdf")
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        current_app.logger.exception('Error al generar el informe de barrios populares')
        return jsonify(error='No se pudo generar el informe de barrios populares.'), 500


@bp.get('/api/poblacion/barrios/informe-regional')
def informal_settlements_regional_report():
    """Informe PDF con todas las localidades ribereñas: barrios, familias y estado del río."""
    from . import barrios_report
    try:
        out = barrios_report.regional_pdf()
        return _pdf_response(out, f"DOTS-barrios-populares-Cuenca-del-Plata-{datetime.now(timezone.utc):%Y-%m-%d}.pdf")
    except Exception:
        current_app.logger.exception('Error al generar el informe regional de barrios populares')
        return jsonify(error='No se pudo generar el informe regional.'), 500


@bp.post('/api/poblacion/barrios/en-area')
def informal_settlements_in_area():
    """Barrios del RENABAP dentro del área dibujada en el mapa."""
    from . import barrios_area
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(barrios_area.en_area(payload.get('area')))
    except (InputError, ValueError) as exc:
        return jsonify(error=str(exc)), 400
    except LookupError as exc:
        return jsonify(error=str(exc)), 503
    except Exception:
        current_app.logger.exception('Error al cruzar barrios con el área')
        return jsonify(error='No se pudieron consultar los barrios del área.'), 500


@bp.post('/api/poblacion/barrios/informe-area')
def informal_settlements_area_report():
    """Informe PDF de los barrios populares dentro del área dibujada."""
    from . import barrios_area
    payload = request.get_json(silent=True) or {}
    try:
        res = barrios_area.en_area(payload.get('area'))
        pob = payload.get('poblacion') if isinstance(payload.get('poblacion'), dict) else None
        return _pdf_response(barrios_area.pdf(res, pob), f"DOTS-barrios-populares-area-{datetime.now(timezone.utc):%Y-%m-%d}.pdf")
    except (InputError, ValueError) as exc:
        return jsonify(error=str(exc)), 400
    except LookupError as exc:
        return jsonify(error=str(exc)), 503
    except Exception:
        current_app.logger.exception('Error al generar el informe de barrios del área')
        return jsonify(error='No se pudo generar el informe de barrios del área.'), 500


@bp.get('/api/poblacion/barrios/barrios_radar/<name>')
def informal_settlements_image(name):
    """Imagen de una localidad, leída de la rama de datos (sirve aunque el repositorio sea privado)."""
    import re
    import datastore
    from flask import Response
    if not re.fullmatch(r'[a-z0-9-]{1,60}\.png',name):
        return jsonify(error='Imagen inválida'),400
    png=datastore.fetch_bytes('barrios_radar/'+name)
    if not png or not png.startswith(b'\x89PNG'):
        return jsonify(error='Imagen no disponible'),404
    return Response(png,mimetype='image/png',headers={'Cache-Control':'public, s-maxage=86400'})
