"""Adaptador de series Sentinel-1 al panel de inundaciones.

Usa el conector existente radar.flooding; no afirma producir mapas de cambio
pixel-a-pixel. Las diferencias de superficie son estimaciones agregadas.
"""
import math
import radar
import vegetation as veg
import research_connectors as c
from datetime import timedelta


def scene_previews(polygon, days=60):
    """Find actual Sentinel-1 RTC STAC assets. URLs are source imagery, not flood classifications."""
    pts = veg.require_polygon(polygon)
    geom = veg.geojson_polygon(pts)
    end = c._now()
    start = end - timedelta(days=days)
    query = {'collections':['sentinel-1-rtc'],'intersects':geom,'limit':30,
             'datetime':f'{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}',
             'sortby':[{'field':'properties.datetime','direction':'desc'}]}
    items = c._post(veg.PC_STAC+'/search',query,timeout=25).json().get('features',[])
    selected = veg.best_tiles(items,pts)
    previews = []
    for item in selected:
        assets = item.get('assets') or {}
        image = None
        for key in ('rendered_preview','preview','thumbnail','visual'):
            candidate = assets.get(key) or {}
            href = candidate.get('href')
            if href and href.startswith('https://'):
                image = href
                break
        previews.append({'id':item.get('id'),'datetime':(item.get('properties') or {}).get('datetime'),
            'orbit':(item.get('properties') or {}).get('sat:orbit_state'),
            'preview_url':image,'stac_item_url':(item.get('links') or [{}])[0].get('href'),
            'available_assets':list(assets.keys())[:15]})
        if len(previews)>=8:break
    return {'status':'recibido' if previews else 'sin dato','source':'Sentinel-1 RTC · Microsoft Planetary Computer STAC',
        'sensor':'Sentinel-1 RTC','kind':'CATALOG_METADATA_NOT_PIXEL_CHANGE',
        'scenes':previews,'limitations':['Las miniaturas son imágenes de origen, no mapas de inundación',
        'El catálogo puede no ofrecer vista previa visible; en ese caso se informa sin inventarla',
        'Las fechas y órbitas deben ser comparables para inferir cambios']}
    

def summarize(polygon, days=60):
    result = radar.flooding(polygon, days=days, scenes=6)
    data = result.get("data") or {}
    valid = [x for x in data.get("series", []) if x.get("status") == "válida"
             and x.get("water_fraction") is not None
             and math.isfinite(float(x["water_fraction"]))]
    if len(valid) < 2:
        return {"status": "sin dato", "error": "Se necesitan al menos dos pasadas válidas Sentinel-1",
                "source": "Sentinel-1 RTC / Microsoft Planetary Computer",
                "series": valid}
    first, last = valid[0], valid[-1]
    area = float(data.get("area_ha") or 0)
    delta = float(last["water_fraction"]) - float(first["water_fraction"])
    return {
        "status": "AGGREGATE_CHANGE_UNVALIDATED",
        "method": "Diferencia de fracción de agua por lote; NO transición píxel a píxel",
        "source": "Sentinel-1 RTC / Microsoft Planetary Computer",
        "before_date": first.get("datetime"),
        "after_date": last.get("datetime"),
        "total_lot_area_ha": area,
        "estimated_net_water_change_ha": round(delta * area, 2),
        "before_water_ha": round(float(first["water_fraction"]) * area, 2),
        "after_water_ha": round(float(last["water_fraction"]) * area, 2),
        "series": valid,
        "image_before_url": None, "image_after_url": None, "change_map_url": None,
        "limitations": [
            "No distingue agua nueva y retirada en el mismo lote",
            "No identifica agua bajo vegetación",
            "Las escenas pueden diferir en cobertura y geometría de observación",
            "No usar para alertas oficiales ni evacuaciones",
        ],
    }
