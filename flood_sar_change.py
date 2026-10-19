"""DOTS Flood AI: métricas de cambio de agua SAR por lote.

Núcleo puro (sin red, GDAL ni dependencias pesadas) para complementar radar.py.
Inspirado en metodologías de comparación multitemporal SAR; no copia código
de repositorios externos. La detección de vegetación inundada requiere
calibración VV/VH y datos de referencia y NO se infiere aquí.
"""
from datetime import datetime
from math import isfinite, log10

DEFAULT_THRESHOLD_DB = -18.0


def linear_to_db(value):
    """Gamma0 lineal > 0 a dB."""
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError("Retrodispersión inválida")
    return 10.0 * log10(value)


def classify_water(vv_linear, threshold_db=DEFAULT_THRESHOLD_DB, nodata=None):
    """Devuelve True/False o None para píxel no válido."""
    if vv_linear is None or vv_linear == nodata:
        return None
    try:
        v = float(vv_linear)
        if not isfinite(v) or v <= 0:
            return None
        return linear_to_db(v) < float(threshold_db)
    except (TypeError, ValueError, OverflowError):
        return None


def _fraction(mask):
    valid = [v for v in mask if v is not None]
    if not valid:
        raise ValueError("No hay píxeles válidos")
    return sum(valid) / len(valid), len(valid)


def compare_scenes(before, after, pixel_area_m2=100.0, threshold_db=DEFAULT_THRESHOLD_DB,
                   nodata=None):
    """Comparación píxel a píxel de dos escenas ya alineadas.

    No admite escenas de distinta grilla. Solo píxeles válidos en ambas
    fechas. La superficie representa píxeles de la grilla, no hectáreas
    catastrales exactas. Devuelve agua persistente, nueva y retirada.
    """
    before, after = list(before), list(after)
    if not before or len(before) != len(after):
        raise ValueError("Las escenas deben tener la misma grilla no vacía")
    pixel_area_m2 = float(pixel_area_m2)
    if not isfinite(pixel_area_m2) or pixel_area_m2 <= 0:
        raise ValueError("Área de píxel inválida")
    b = [classify_water(x, threshold_db, nodata) for x in before]
    a = [classify_water(x, threshold_db, nodata) for x in after]
    pairs = [(x, y) for x, y in zip(b, a) if x is not None and y is not None]
    if not pairs:
        raise ValueError("No hay píxeles válidos en ambas fechas")
    counts = {
        "persistent_water": sum(x and y for x, y in pairs),
        "new_water": sum(not x and y for x, y in pairs),
        "receded_water": sum(x and not y for x, y in pairs),
        "persistent_land": sum(not x and not y for x, y in pairs),
    }
    total = len(pairs)
    return {
        "method": "Sentinel-1 VV gamma0, umbral fijo; cambio temporal",
        "threshold_db": float(threshold_db),
        "paired_valid_pixels": total,
        "coverage_fraction": round(total / len(before), 4),
        "pixel_area_m2": pixel_area_m2,
        "counts": counts,
        "area_ha": {k: round(v * pixel_area_m2 / 10000, 4) for k, v in counts.items()},
        "before_water_fraction": round((counts["persistent_water"] + counts["receded_water"]) / total, 4),
        "after_water_fraction": round((counts["persistent_water"] + counts["new_water"]) / total, 4),
        "new_water_fraction": round(counts["new_water"] / total, 4),
        "status": "ESTIMATE_NOT_VALIDATED",
        "limitations": [
            "Requiere escenas coregistradas y con geometría comparable",
            "El umbral fijo puede confundir sombra radar y agua",
            "No identifica agua bajo vegetación ni determina profundidad",
            "Validar contra GFM, observaciones locales y terreno antes de emitir alertas",
        ],
    }


def quality_gate(result, min_coverage=0.8):
    """Apto para revisión, nunca para alertas automáticas."""
    coverage = result.get("coverage_fraction", 0)
    return {"reviewable": coverage >= min_coverage,
            "automatic_alert_allowed": False,
            "reason": "Requiere validación geoespacial y contraste con observaciones"}
