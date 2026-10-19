"""DOTS Radar: procesamiento REAL de dos rasters Sentinel-1 VV coregistrados.

Ejecutar fuera de Vercel (GitHub Actions/servidor raster). Requiere rasterio,
numpy, requests y planetary-computer. No inventa píxeles ni superficies.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import planetary_computer
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.warp import reproject
from rasterio.windows import from_bounds, transform as window_transform
import requests


STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"


def search(polygon, days=180):
    ring = [[float(lon), float(lat)] for lat, lon in polygon]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    geom = {"type": "Polygon", "coordinates": [ring]}
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    query = {"collections": ["sentinel-1-rtc"], "intersects": geom,
             "datetime": start.isoformat().replace("+00:00", "Z") + "/" + now.isoformat().replace("+00:00", "Z"),
             "limit": 60}
    response = requests.post(STAC, json=query, timeout=40)
    response.raise_for_status()
    scenes = sorted(response.json().get("features", []), key=lambda f: f["properties"].get("datetime", ""))
    # Compare the same orbit direction AND relative orbit number where available.
    groups = {}
    for s in scenes:
        props = s.get("properties", {})
        orbit = props.get("sat:orbit_state")
        relative = props.get("sat:relative_orbit")
        if orbit in ("ascending", "descending") and relative is not None and "vv" in s.get("assets", {}):
            groups.setdefault((orbit, relative), []).append(s)
    candidates = [v for v in groups.values() if len(v) >= 2]
    if candidates:
        subset = max(candidates, key=lambda v: (v[-1]["properties"].get("datetime", ""), len(v)))
        props = subset[0]["properties"]
        return subset[0], subset[-1], geom, str(props["sat:orbit_state"]) + "/" + str(props["sat:relative_orbit"])
    raise ValueError("No se encontraron dos escenas VV de la misma órbita relativa")


def raster_pair(before, after, geom, resolution=10):
    from rasterio.crs import CRS
    from rasterio.warp import transform_geom, calculate_default_transform
    import rasterio.windows
    signed_before = planetary_computer.sign(before)
    signed_after = planetary_computer.sign(after)
    with rasterio.open(signed_before["assets"]["vv"]["href"]) as src:
        projected_geom = transform_geom("EPSG:4326", src.crs, geom)
        ring = projected_geom["coordinates"][0]
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        bounds = (min(xs), min(ys), max(xs), max(ys))
        win = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
        win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        transform = window_transform(win, src.transform)
        width, height = int(win.width), int(win.height)
        if width * height > 4_000_000:
            raise ValueError("Lote demasiado grande para procesamiento de prueba")
        b = src.read(1, window=win, masked=True).filled(np.nan).astype("float32")
        src_crs = src.crs
    with rasterio.open(signed_after["assets"]["vv"]["href"]) as src:
        a = np.full((height, width), np.nan, dtype="float32")
        reproject(source=rasterio.band(src, 1), destination=a, src_transform=src.transform,
                  src_crs=src.crs, src_nodata=src.nodata, dst_transform=transform,
                  dst_crs=src_crs, dst_nodata=np.nan, resampling=Resampling.nearest)
    inside = geometry_mask([projected_geom], out_shape=b.shape, transform=transform, invert=True)
    valid = inside & np.isfinite(b) & np.isfinite(a) & (b > 0) & (a > 0)
    if valid.sum() < 30:
        raise ValueError("No hay suficientes píxeles coincidentes y válidos")
    return b, a, valid, transform, src_crs, int(inside.sum())


def analyze(polygon, days=180, threshold_db=-18):
    before, after, geom, orbit = search(polygon, days)
    b, a, valid, transform, crs, inside_count = raster_pair(before, after, geom)
    threshold = 10 ** (threshold_db / 10)
    bw = b < threshold; aw = a < threshold
    classes = np.zeros(b.shape, dtype="uint8")  # 0 = sin datos
    classes[valid & ~bw & ~aw] = 1  # tierra persistente
    classes[valid & bw & aw] = 2    # agua persistente
    classes[valid & ~bw & aw] = 3   # agua nueva
    classes[valid & bw & ~aw] = 4   # agua retirada
    # Area in source projected CRS: use determinant, not a hardcoded 100 m².
    pixel_m2 = abs(transform.a * transform.e - transform.b * transform.d)
    if not crs.is_projected:
        raise ValueError("El raster no está en CRS proyectado: superficie no calculable")
    counts = {name: int(np.sum(classes == value)) for name, value in
              (("persistent_land", 1), ("persistent_water", 2), ("new_water", 3), ("receded_water", 4))}
    return {"before": before["properties"].get("datetime"),
            "after": after["properties"].get("datetime"), "orbit": orbit,
            "status": "ESTIMATE_NOT_VALIDATED", "threshold_db": threshold_db,
            "paired_valid_pixels": int(valid.sum()),
            "coverage_fraction": round(float(valid.sum()) / inside_count, 4),
            "area_ha": {k: round(v * pixel_m2 / 10000, 3) for k, v in counts.items()},
            "counts": counts,
            "method": "Sentinel-1 RTC VV, escenas reproyectadas a la misma grilla, umbral fijo",
            "limitations": ["No validado con datos de campo", "No detecta agua bajo vegetación",
                            "No determina profundidad", "Puede confundir sombra radar con agua"]}, classes, transform, crs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--polygon", required=True, help="Archivo JSON con vértices [[lat,lon],...]")
    parser.add_argument("--output", default="radar_result")
    parser.add_argument("--days", type=int, default=180)
    args = parser.parse_args()
    polygon = json.loads(Path(args.polygon).read_text(encoding="utf-8"))
    if len(polygon) < 3:
        raise ValueError("El polígono necesita tres o más vértices")
    report, classes, transform, crs = analyze(polygon, args.days)
    base = Path(args.output)
    base.parent.mkdir(parents=True, exist_ok=True)
    base.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with rasterio.open(base.with_suffix(".tif"), "w", driver="GTiff",
                       height=classes.shape[0], width=classes.shape[1],
                       count=1, dtype="uint8", crs=crs, transform=transform,
                       nodata=0, compress="deflate") as dst:
        dst.write(classes, 1)
        dst.write_colormap(1, {0: (0,0,0,0), 1: (55,74,66,255),
                               2: (40,110,220,255), 3: (0,230,245,255),
                               4: (235,160,45,255)})
    print(json.dumps({"report": str(base.with_suffix(".json")), "raster": str(base.with_suffix(".tif"))}))


if __name__ == "__main__":
    main()
