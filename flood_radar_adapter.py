"""Adaptador de series Sentinel-1 al panel de inundaciones.

Usa el conector existente radar.flooding; no afirma producir mapas de cambio
pixel-a-pixel. Las diferencias de superficie son estimaciones agregadas.
"""
import math
import radar


def summarize(polygon, days=60):
    result = radar.flooding(polygon, days=days, scenes=6)
    data = result.get("data") or {}
    scenes = data.get("series", [])
    valid = [x for x in scenes if x.get("status") == "válida"
             and x.get("water_fraction") is not None
             and math.isfinite(float(x["water_fraction"]))]
    if len(valid) < 2:
        return {"status": "sin dato", "error": "Se necesitan al menos dos pasadas válidas Sentinel-1",
                "source": "Sentinel-1 RTC / Microsoft Planetary Computer",
                "series": valid,
        "scenes_found": len(scenes), "scenes_valid": len(valid),
        "scenes_failed": len(scenes) - len(valid), "scenes_found": len(scenes),
                "scenes_valid": len(valid), "scenes_failed": len(scenes) - len(valid),
                "method": "Umbral VV Sentinel-1 RTC; resultados preliminares",
                "limitations": ["No se pudo calcular cambio entre dos fechas comparables"]}
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
