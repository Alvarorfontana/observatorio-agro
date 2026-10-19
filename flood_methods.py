"""Métodos complementarios de clasificación SAR para DOTS.

Implementaciones originales y ligeras, inspiradas en prácticas públicas de
UN-SPIDER y literatura de cartografía SAR. No incorpora ni copia código AGPL.
Entrada: muestras VV gamma0 lineal. No produce mapas sin raster coregistrado.
"""
import math
from flood_sar_change import classify_water, compare_scenes


def otsu_threshold_db(values, bins=128, lower=-35.0, upper=0.0):
    """Umbral automático Otsu en dB; no usar si no hay bimodalidad."""
    db = [10 * math.log10(float(v)) for v in values
          if v is not None and isinstance(v, (float, int))
          and math.isfinite(v) and v > 0]
    if len(db) < 30:
        raise ValueError("Se requieren al menos 30 muestras válidas")
    counts = [0] * bins
    for v in db:
        j = max(0, min(bins - 1, int((v - lower) / (upper - lower) * bins)))
        counts[j] += 1
    total = sum(counts)
    sum_all = sum(i * n for i, n in enumerate(counts))
    weight_b = 0
    sum_b = 0
    best = -1.0
    threshold = 0
    for i, n in enumerate(counts):
        weight_b += n
        if not weight_b or weight_b == total:
            continue
        sum_b += i * n
        weight_f = total - weight_b
        between = (sum_all * weight_b - sum_b * total) ** 2 / (weight_b * weight_f)
        if between > best:
            best, threshold = between, i
    return round(lower + (threshold + 0.5) * (upper - lower) / bins, 2)


def adaptive_water_change(before, after, threshold_db=None, pixel_area_m2=100):
    """Clasificación VV Otsu o umbral fijado por operador, por píxel pareado."""
    before, after = list(before), list(after)
    threshold = otsu_threshold_db(before + after) if threshold_db is None else float(threshold_db)
    result = compare_scenes(before, after, pixel_area_m2, threshold)
    result["threshold_method"] = "otsu_pooled" if threshold_db is None else "operator_fixed"
    result["limitations"].append("Otsu exige histograma con agua y tierra bien representadas")
    return result


def reference_confusion(predicted, reference):
    """Métricas frente a máscaras independientes; None excluido."""
    pairs = [(bool(p), bool(r)) for p, r in zip(predicted, reference)
             if p is not None and r is not None]
    if not pairs or len(predicted) != len(reference):
        raise ValueError("Máscaras de referencia incompatibles o vacías")
    tp = sum(p and r for p, r in pairs)
    fp = sum(p and not r for p, r in pairs)
    fn = sum(not p and r for p, r in pairs)
    tn = sum(not p and not r for p, r in pairs)
    def ratio(n, d):
        return round(n / d, 4) if d else None
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "iou": ratio(tp, tp + fp + fn), "validated_pixels": len(pairs)}
