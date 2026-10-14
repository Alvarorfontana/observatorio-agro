import math
from datetime import date
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

R_AUTHALIC = 6371007.181   # m, radio de la esfera de igual área que el elipsoide WGS84


def _ring_area_m2(coords):
    """Área esférica de un anillo [lon, lat] (fórmula de Chamberlain y Duquette, NASA JPL 2007)."""
    total = 0.0
    n = len(coords)
    for i in range(n - 1):
        lon1, lat1 = coords[i][:2]
        lon2, lat2 = coords[i + 1][:2]
        total += math.radians(lon2 - lon1) * (2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    return abs(total * R_AUTHALIC * R_AUTHALIC / 2)


class InputError(ValueError):
    pass


def polygon(value, label='geometría'):
    if not isinstance(value, dict) or value.get('type') not in ('Polygon','MultiPolygon'):
        raise InputError(f'{label}: se requiere Polygon o MultiPolygon GeoJSON en EPSG:4326.')
    coords = value.get('coordinates')
    count = 0
    def check(values,depth=0):
        nonlocal count
        if depth>4: raise InputError(f'{label}: estructura de coordenadas inválida.')
        if not isinstance(values,list) or not values:
            raise InputError(f'{label}: coordenadas inválidas.')
        if isinstance(values[0],(int,float)):
            if len(values)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
                raise InputError(f'{label}: usá puntos [longitud, latitud] finitos.')
            if not -180<=values[0]<=180 or not -85<=values[1]<=85:
                raise InputError(f'{label}: coordenadas fuera de rango (-85 a 85° de latitud).')
            count+=1
            if count>2000: raise InputError('Máximo 2000 vértices por geometría.')
        else:
            for part in values: check(part,depth+1)
    check(coords)
    parts = coords if value['type']=='MultiPolygon' else [coords]
    for rings in parts:
        for ring in rings:
            if len(ring)<4 or ring[0]!=ring[-1]:
                raise InputError(f'{label}: todos los anillos deben estar cerrados.')
    try: result=shape(value)
    except Exception: raise InputError(f'{label}: geometría no interpretable.') from None
    if result.is_empty or not result.is_valid or result.area<=0:
        raise InputError(f'{label}: geometría vacía, degenerada o con cruces.')
    w,s,e,n=result.bounds
    if e-w>10 or n-s>10:
        raise InputError('Reducí el área: esta versión admite hasta 10° por eje y no cruza el antimeridiano.')
    return result


def area_km2(geom):
    """Superficie en km² sobre la esfera de igual área (error menor a 0,5 % frente al elipsoide)."""
    if geom.is_empty: return 0.0
    parts=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]
    total=0.0
    for g in parts:
        total+=_ring_area_m2(list(g.exterior.coords))
        for hole in g.interiors: total-=_ring_area_m2(list(hole.coords))
    return max(0.0,total)/1e6


def polygonal(geom):
    if geom.geom_type in ('Polygon','MultiPolygon'): return geom
    if geom.geom_type=='GeometryCollection':
        return unary_union([g for g in geom.geoms if g.geom_type in ('Polygon','MultiPolygon')])
    from shapely.geometry import Polygon
    return Polygon()


def prepare(data):
    if not isinstance(data,dict): raise InputError('Se requiere JSON.')
    aoi=polygon(data.get('area'),'zona de estudio')
    hazard=polygon(data.get('hazard'),'área de amenaza')
    intersection=polygonal(aoi.intersection(hazard))
    year=data.get('year',2025)
    if isinstance(year,bool) or not isinstance(year,int) or not 2015<=year<=2030:
        raise InputError('WorldPop Global2: usá un año entre 2015 y 2030.')
    event=data.get('event',{})
    if not isinstance(event,dict): raise InputError('event debe ser un objeto.')
    allowed=('inundacion','sequia','incendio','crecida','calor','otro')
    kind=event.get('kind','inundacion')
    if kind not in allowed: raise InputError('Tipo de amenaza no admitido.')
    category=event.get('category','escenario_usuario')
    if category not in ('observado','pronosticado','escenario_usuario'):
        raise InputError('Categoría: observado, pronosticado o escenario_usuario.')
    source=event.get('source','Área definida por el usuario')
    if not isinstance(source,str) or not 1<=len(source.strip())<=250:
        raise InputError('Indicá una fuente de amenaza de 1 a 250 caracteres.')
    when=event.get('date')
    try: when=date.fromisoformat(when).isoformat()
    except (TypeError,ValueError): raise InputError('Indicá la fecha del evento en YYYY-MM-DD.') from None
    enso=event.get('enso','sin_especificar')
    if enso not in ('el_nino','la_nina','neutral','sin_especificar'):
        raise InputError('Fase ENOS inválida.')
    return {'area':mapping(aoi),'intersection':mapping(intersection) if not intersection.is_empty else None,
            'year':year,'area_km2':area_km2(aoi),'hazard_in_area_km2':area_km2(intersection),
            'event':{'kind':kind,'category':category,'source':source.strip(),'date':when,'enso':enso}}
