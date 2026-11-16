#!/usr/bin/env python3
"""Evaluación reproducible de máscaras de agua contra una referencia independiente.

Convención por defecto: predicción > 0 = agua; referencia == 1 = agua;
referencia == 0 = no agua; nodata/255 = píxel excluido.
Requiere numpy y rasterio (dependencias opcionales; no modifica el pipeline DOTS).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def calcular_metricas(prediccion, referencia, valido=None, area_pixel_m2=None):
    """Calcula métricas de clasificación sobre píxeles válidos."""
    import numpy as np

    pred = np.asarray(prediccion, dtype=bool)
    ref = np.asarray(referencia, dtype=bool)
    if pred.shape != ref.shape:
        raise ValueError("Las máscaras deben tener la misma forma")
    mask = np.ones(pred.shape, dtype=bool) if valido is None else np.asarray(valido, dtype=bool)
    if mask.shape != pred.shape:
        raise ValueError("La máscara de validez debe tener la misma forma")
    tp = int(np.count_nonzero(mask & pred & ref))
    fp = int(np.count_nonzero(mask & pred & ~ref))
    fn = int(np.count_nonzero(mask & ~pred & ref))
    tn = int(np.count_nonzero(mask & ~pred & ~ref))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else (0.0 if precision == 0 or recall == 0 else None)
    union = tp + fp + fn
    iou = tp / union if union else None
    dice = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    pred_area = (tp + fp) * area_pixel_m2 if area_pixel_m2 is not None else None
    ref_area = (tp + fn) * area_pixel_m2 if area_pixel_m2 is not None else None
    abs_error = abs(pred_area - ref_area) if pred_area is not None else None
    rel_error = abs_error / ref_area if ref_area else None
    return {
        "confusion": {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn},
        "metrics": {"precision": precision, "recall": recall, "f1": f1, "iou": iou, "dice": dice,
                    "predicted_water_area_m2": pred_area, "reference_water_area_m2": ref_area,
                    "absolute_area_error_m2": abs_error, "relative_area_error": rel_error},
        "coverage": {"valid_pixels": int(mask.sum()), "total_pixels": int(mask.size),
                     "valid_fraction": float(mask.sum() / mask.size) if mask.size else 0.0},
    }


def _leer_raster(path):
    import numpy as np
    import rasterio

    with rasterio.open(path) as ds:
        arr = ds.read(1)
        return arr, ds.profile.copy(), ds.nodata, ds.transform, ds.crs


def evaluar_archivos(pred_path, ref_path, water_value=1, ignore_value=255):
    import numpy as np

    pred, pp, pred_nodata, pred_transform, pred_crs = _leer_raster(pred_path)
    ref, rp, ref_nodata, ref_transform, ref_crs = _leer_raster(ref_path)
    if pred.shape != ref.shape:
        raise ValueError(f"Dimensiones diferentes: predicción {pred.shape}, referencia {ref.shape}")
    if pred_crs != ref_crs:
        raise ValueError(f"CRS diferentes: {pred_crs} != {ref_crs}; reproyecte antes de evaluar")
    if pred_transform != ref_transform:
        raise ValueError("Transformaciones/extent diferentes; alinee los rasters antes de evaluar")
    valid = np.isfinite(pred) & np.isfinite(ref)
    if pred_nodata is not None:
        valid &= pred != pred_nodata
    if ref_nodata is not None:
        valid &= ref != ref_nodata
    if ignore_value is not None:
        valid &= ref != ignore_value
    predicted_water = pred > 0
    reference_water = ref == water_value

    area = None
    if pred_crs is not None and pred_crs.is_projected:
        units = [axis.unit_name.lower() for axis in pred_crs.axis_info[:2] if axis.unit_name]
        if len(units) == 2 and all("metre" in unit or "meter" in unit for unit in units):
            area = abs(pred_transform.a * pred_transform.e - pred_transform.b * pred_transform.d)
    result = calcular_metricas(predicted_water, reference_water, valid, area)
    result["inputs"] = {
        "prediction": str(Path(pred_path)), "reference": str(Path(ref_path)),
        "prediction_crs": str(pred_crs), "reference_water_value": water_value,
        "reference_ignore_value": ignore_value, "pixel_area_m2": area,
        "area_note": None if area is not None else "Área omitida: CRS no proyectado en metros o metadatos insuficientes",
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction", required=True, help="GeoTIFF de detección; valores > 0 indican agua")
    parser.add_argument("--reference", required=True, help="GeoTIFF independiente: 1 agua, 0 no agua, 255 incierto")
    parser.add_argument("--event-id", required=True, help="Identificador estable del evento evaluado")
    parser.add_argument("--water-value", type=int, default=1)
    parser.add_argument("--ignore-value", type=int, default=255)
    parser.add_argument("--output", required=True, help="Ruta JSON de resultados")
    args = parser.parse_args()

    result = evaluar_archivos(args.prediction, args.reference, args.water_value, args.ignore_value)
    result["event_id"] = args.event_id
    result["evaluated_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["validation_status"] = "computed_metrics_not_scientific_approval"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
