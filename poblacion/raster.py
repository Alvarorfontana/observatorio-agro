"""Cruce local de GeoTIFF autorizado con ponderación de área de píxel.

No descarga Populace ni presupone su licencia. Paths solo desde configuración.
"""
import json
import math
import os
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds,Window
from shapely.geometry import shape,Polygon
from shapely import transform
from pyproj import Transformer
from .geometry import InputError,area_km2


def datasets():
    location=os.environ.get('DOTS_POPULATION_MANIFEST')
    if not location: return []
    path=Path(location).resolve()
    try: data=json.loads(path.read_text())
    except (OSError,ValueError): raise InputError('No se pudo leer el registro de datasets del servidor.') from None
    if not isinstance(data,list): raise InputError('El registro de datasets debe ser una lista.')
    results=[]
    for entry in data:
        if not isinstance(entry,dict) or entry.get('use_authorized') is not True: continue
        required=('id','path','provider','year','unit','source_url','license','group')
        if any(not entry.get(k) for k in required): continue
        if entry['unit'] not in ('people_per_pixel','people_per_km2'): continue
        item=dict(entry)
        if isinstance(item['year'],bool) or not isinstance(item['year'],int): continue
        file=(path.parent/item['path']).resolve()
        if file.is_file() and file.suffix.lower() in ('.tif','.tiff'):
            item['path']=str(file);results.append(item)
    return results


def public_dataset(entry):
    return {key:entry[key] for key in ('id','provider','year','unit','source_url','license','group')}


def estimate(prepared,entry,max_pixels=100000):
    aoi=shape(prepared['area'])
    hazard=shape(prepared['intersection']) if prepared['intersection'] else Polygon()
    pop_total=pop_exposed=valid_area=valid_exposed=0.0
    with rasterio.open(entry['path']) as ds:
        if ds.count!=1 or ds.crs is None or ds.transform.b!=0 or ds.transform.d!=0 or ds.transform.a<=0 or ds.transform.e>=0:
            raise InputError('Se requiere GeoTIFF monobanda, con CRS y grilla sin rotación.')
        to_native=Transformer.from_crs('EPSG:4326',ds.crs,always_xy=True).transform
        to_geo=Transformer.from_crs(ds.crs,'EPSG:4326',always_xy=True).transform
        native_aoi=transform(aoi,to_native,interleaved=False)
        w=from_bounds(*native_aoi.bounds,transform=ds.transform)
        c0=max(0,math.floor(w.col_off));r0=max(0,math.floor(w.row_off))
        c1=min(ds.width,math.ceil(w.col_off+w.width));r1=min(ds.height,math.ceil(w.row_off+w.height))
        n=max(0,c1-c0)*max(0,r1-r0)
        if n>max_pixels: raise InputError('El área supera el límite de 100000 píxeles. Dividí la zona o usá un worker.')
        if n:
            data=ds.read(1,window=Window(c0,r0,c1-c0,r1-r0),masked=True).astype(float)
            values=data.filled(np.nan)*ds.scales[0]+ds.offsets[0]
            for row,col in np.argwhere(np.isfinite(values)&(values>=0)):
                rr,cc=int(row)+r0,int(col)+c0
                def xy(x,y):return (ds.transform.c+ds.transform.a*x,ds.transform.f+ds.transform.e*y)
                native=Polygon([xy(cc,rr),xy(cc+1,rr),xy(cc+1,rr+1),xy(cc,rr+1)])
                cell=transform(native,to_geo,interleaved=False)
                in_aoi=cell.intersection(aoi)
                if in_aoi.is_empty or in_aoi.area==0: continue
                from .geometry import polygonal
                cell_area=area_km2(cell)
                if not cell_area: continue
                a=area_km2(polygonal(in_aoi))
                h=area_km2(polygonal(in_aoi.intersection(hazard))) if not hazard.is_empty else 0.0
                # Conteo por píxel != densidad por km².
                v=float(values[row,col])
                cell_population=v if entry['unit']=='people_per_pixel' else v*cell_area
                pop_total+=cell_population*min(1,a/cell_area)
                pop_exposed+=cell_population*min(1,h/cell_area)
                valid_area+=a;valid_exposed+=h
        resolution={'crs':str(ds.crs),'pixel_width_native':abs(ds.transform.a),'pixel_height_native':abs(ds.transform.e)}
    coverage=min(100,100*valid_area/prepared['area_km2'])
    exposed_coverage=(min(100,100*valid_exposed/prepared['hazard_in_area_km2']) if prepared['hazard_in_area_km2'] else 100)
    has_data=valid_area>0
    total=pop_total if has_data else None
    exposed=pop_exposed if has_data and (not prepared['intersection'] or valid_exposed>0) else None
    return {'status':'complete' if coverage>=99.9 and exposed_coverage>=99.9 else 'partial_coverage' if has_data else 'no_data',
            'population_total':total,'population_exposed':exposed,
            'exposed_percent':100*pop_exposed/pop_total if pop_total>0 and exposed is not None else None,
            'density_per_km2':pop_total/valid_area if has_data else None,
            'population_group':entry['group'],'source':public_dataset(entry),
            'coverage_percent':coverage,'exposed_coverage_percent':exposed_coverage,'resolution':resolution,
            'method':'Ponderación por fracción de superficie de píxel; distribución uniforme dentro de cada celda.',
            'coverage_status':'computed_from_valid_raster_cells',
            'interpretation':'Población residente estimada expuesta; no personas damnificadas registradas.',
            'notes':['Las estimaciones de cobertura parcial no se extrapolan al área faltante.',
                     'Con cobertura parcial, el porcentaje usa solo la población de celdas válidas.',
                     'Los conteos de población se ponderan, no se promedian ni remuestrean como densidades.',
                     'El cruce espacial no atribuye causalidad a ENOS.']}
