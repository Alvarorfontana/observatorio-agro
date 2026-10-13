"""Procesamiento semanal de los lotes DOTS (GitHub Actions, gratuito).

Para cada lote guardado en el repositorio privado de datos:
  1. Busca la escena Sentinel-2 L2A más reciente y despejada (Earth Search, STAC abierto).
  2. Recorta las bandas B2, B3, B4, B8, B11 y B12 al lote más un margen y arma un GeoTIFF de 6 bandas.
  3. Detecta agua con geoai.segment_water (modelo preentrenado OmniWaterMask, corre en CPU).
  4. Calcula dentro del lote: hectáreas de agua, cantidad de cuerpos de agua y NDVI medio.
  5. Entorno del lote con Overture Maps (caminos, construcciones, departamento), una vez por versión.
  6. Guarda resultados/<id>.json con historial semanal, para la web y el informe.

Privacidad: el repositorio de código es público y sus registros también. Este script no imprime
nombres ni coordenadas de lotes, solo conteos. Los datos viven en un repositorio privado.

Uso:  python scripts/procesar_lotes.py <carpeta_del_repo_de_datos>
      DOTS_SEGMENTER=fake  -> prueba sin geoai (detecta agua por umbral de NDWI, solo para tests)
"""
import json, math, os, sys, tempfile, time
from datetime import datetime, timedelta, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STAC = "https://earth-search.aws.element84.com/v1"
BANDS = ["blue", "green", "red", "nir", "swir16", "swir22"]   # B2 B3 B4 B8 B11 B12 = preset "sentinel2" de geoai
MAX_CLOUD = 30
LOOKBACK_DAYS = 45
MARGIN_M = 300
HISTORY_MAX = 104   # dos años de semanas


def log(msg):
    print(f"[dots] {msg}", flush=True)


def lot_bbox(vertices, margin_m=MARGIN_M):
    lats = [p[0] for p in vertices]; lons = [p[1] for p in vertices]
    lat0 = sum(lats) / len(lats)
    dlat = margin_m / 110540; dlon = margin_m / (111320 * math.cos(math.radians(lat0)))
    return (min(lons) - dlon, min(lats) - dlat, max(lons) + dlon, max(lats) + dlat)


def lot_polygon(vertices):
    from shapely.geometry import Polygon
    ring = [(lon, lat) for lat, lon in vertices]
    return Polygon(ring).buffer(0)


def area_ha(geom_lonlat):
    """Área geodésica aproximada en hectáreas (proyección local)."""
    import shapely
    c = geom_lonlat.centroid
    k = math.cos(math.radians(c.y))
    g = shapely.transform(geom_lonlat, lambda xy: xy * np.array([111320 * k, 110540]))
    return g.area / 10000


def find_scene(bbox, today=None):
    from pystac_client import Client
    today = today or datetime.now(timezone.utc)
    start = (today - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    search = Client.open(STAC).search(
        collections=["sentinel-2-l2a"], bbox=bbox, datetime=f"{start}/{today:%Y-%m-%d}",
        query={"eo:cloud_cover": {"lt": MAX_CLOUD}}, max_items=30)
    items = list(search.items())
    if not items:
        return None
    # la más reciente entre las menos nubladas
    items.sort(key=lambda it: (round((it.properties.get("eo:cloud_cover") or 100) / 10), -datetime.fromisoformat(it.properties["datetime"].replace("Z", "+00:00")).timestamp()))
    return items[0]


def read_stack(item, bbox, out_path):
    """Recorta las 6 bandas al bbox, todo a 10 m, en la grilla de B4. Devuelve el perfil."""
    import rasterio
    from rasterio.warp import transform_bounds, reproject, Resampling
    from rasterio.windows import from_bounds
    offset = 0.0
    props = item.properties
    if str(props.get("s2:processing_baseline", "0")) >= "04.00" and not props.get("earthsearch:boa_offset_applied", False):
        offset = -1000.0  # desde la línea base 04.00 las reflectancias traen +1000
    ref = item.assets["red"].href
    with rasterio.open(ref) as src:
        b = transform_bounds("EPSG:4326", src.crs, *bbox)
        win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
        transform = src.window_transform(win)
        h, w = int(win.height), int(win.width)
        crs = src.crs
    if h < 4 or w < 4:
        raise ValueError("Recorte demasiado chico")
    stack = np.zeros((len(BANDS), h, w), dtype="float32")
    for i, name in enumerate(BANDS):
        with rasterio.open(item.assets[name].href) as src:
            if src.res[0] <= 10.5:
                bw = from_bounds(*rasterio.transform.array_bounds(h, w, transform), transform=src.transform).round_offsets().round_lengths()
                arr = src.read(1, window=bw, out_shape=(h, w), resampling=Resampling.bilinear).astype("float32")
            else:
                arr = np.zeros((h, w), dtype="float32")
                reproject(rasterio.band(src, 1), arr, src_transform=src.transform, src_crs=src.crs,
                          dst_transform=transform, dst_crs=crs, resampling=Resampling.bilinear)
        stack[i] = np.clip(arr + offset, 0, None)
    profile = {"driver": "GTiff", "height": h, "width": w, "count": len(BANDS), "dtype": "float32",
               "crs": crs, "transform": transform, "nodata": 0, "compress": "deflate"}
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(stack)
    return profile


def segment(stack_path, out_dir):
    """Agua con geoai (OmniWaterMask). Devuelve la ruta del GeoJSON de polígonos en EPSG:4326 o None."""
    vec = os.path.join(out_dir, "agua.geojson")
    if os.environ.get("DOTS_SEGMENTER") == "fake":
        return fake_segment(stack_path, vec)
    import geoai
    gdf = geoai.segment_water(stack_path, band_order="sentinel2",
                              output_raster=os.path.join(out_dir, "agua.tif"),
                              output_vector=vec, smooth=True, smooth_iterations=3, min_size=100)
    if gdf is None or len(gdf) == 0:
        return None
    gdf.to_crs("EPSG:4326").to_file(vec, driver="GeoJSON")
    return vec


def fake_segment(stack_path, vec):
    """Solo para pruebas sin geoai: agua donde NDWI > 0,2 (no se usa en producción)."""
    import rasterio
    from rasterio.features import shapes
    from shapely.geometry import shape, mapping
    from shapely.ops import transform as stransform
    from pyproj import Transformer
    with rasterio.open(stack_path) as src:
        g, n = src.read(2), src.read(4)
        ndwi = (g - n) / np.maximum(g + n, 1)
        mask = (ndwi > 0.2).astype("uint8")
        tr = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
        feats = [{"type": "Feature", "properties": {}, "geometry": mapping(stransform(tr.transform, shape(s)))}
                 for s, v in shapes(mask, mask=mask == 1, transform=src.transform) if v == 1]
    if not feats:
        return None
    json.dump({"type": "FeatureCollection", "features": feats}, open(vec, "w"))
    return vec


def ndvi_mean(stack_path, lot_geom):
    import rasterio
    from rasterio.mask import mask as rmask
    from shapely.geometry import mapping
    from shapely.ops import transform as stransform
    from pyproj import Transformer
    with rasterio.open(stack_path) as src:
        tr = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        g = stransform(tr.transform, lot_geom)
        arr, _ = rmask(src, [mapping(g)], crop=True, indexes=[3, 4], nodata=0, filled=True)
    red, nir = arr[0], arr[1]
    ok = (red > 0) & (nir > 0)
    if ok.sum() < 4:
        return None
    v = (nir[ok] - red[ok]) / (nir[ok] + red[ok])
    return round(float(np.nanmean(v)), 3)


def water_in_lot(vec_path, lot_geom):
    from shapely.geometry import shape, mapping
    if not vec_path:
        return 0.0, 0, []
    fc = json.load(open(vec_path))
    parts = []
    for f in fc.get("features", []):
        g = shape(f["geometry"]).buffer(0).intersection(lot_geom)
        if not g.is_empty and area_ha(g) >= 0.05:   # 500 m² mínimo
            parts.append(g)
    total = sum(area_ha(g) for g in parts)
    simplified = [mapping(g.simplify(0.00003, preserve_topology=True)) for g in parts]
    return round(total, 2), len(parts), simplified


def process_lot(lot, out_dir, today=None):
    vertices = lot["vertices"]
    geom = lot_polygon(vertices)
    bbox = lot_bbox(vertices)
    item = find_scene(bbox, today)
    if item is None:
        return {"status": "sin dato", "reason": f"Sin escenas Sentinel-2 con menos de {MAX_CLOUD} % de nubes en {LOOKBACK_DAYS} días"}
    with tempfile.TemporaryDirectory() as tmp:
        stack = os.path.join(tmp, "s2.tif")
        read_stack(item, bbox, stack)
        vec = segment(stack, tmp)
        water_ha, count, polys = water_in_lot(vec, geom)
        nd = ndvi_mean(stack, geom)
    lot_ha = area_ha(geom)
    return {"status": "recibido", "scene": {"id": item.id, "date": item.properties["datetime"][:10],
                                            "cloud_pct": round(item.properties.get("eo:cloud_cover") or 0, 1)},
            "water_ha": water_ha, "water_pct": round(water_ha / lot_ha * 100, 2) if lot_ha else None,
            "water_bodies": count, "water_geojson": {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": g} for g in polys]},
            "ndvi_mean": nd, "lot_ha": round(lot_ha, 1)}


def merge_history(prev, res, run_date):
    hist = list((prev or {}).get("history") or [])
    if res.get("status") == "recibido":
        row = {"run": run_date, "scene_date": res["scene"]["date"], "water_ha": res["water_ha"], "ndvi": res["ndvi_mean"]}
        hist = [h for h in hist if h.get("scene_date") != row["scene_date"]] + [row]
    return hist[-HISTORY_MAX:]


def entorno(lot, prev, state):
    """Overture: se recalcula sólo cuando sale una versión nueva. DOTS_OVERTURE=0 lo apaga."""
    if os.environ.get("DOTS_OVERTURE") == "0":
        return (prev or {}).get("entorno")
    try:
        import overture_lote as ov
        if "reader" not in state:
            state["reader"] = ov.Reader(ov.latest_release())
        reader = state["reader"]
        old = (prev or {}).get("entorno")
        if old and old.get("release") == reader.release:
            return old
        return ov.lot_context(lot_polygon(lot["vertices"]), reader)
    except Exception as e:
        state.setdefault("errors", 0); state["errors"] += 1
        state["last_error"] = type(e).__name__
        return (prev or {}).get("entorno")


def main(data_dir):
    lots_path = os.path.join(data_dir, "lotes.json")
    if not os.path.exists(lots_path):
        log("No hay lotes guardados todavía.")
        return 0
    lots = json.load(open(lots_path)).get("lotes", [])
    out_dir = os.path.join(data_dir, "resultados"); os.makedirs(out_dir, exist_ok=True)
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ok = fail = 0
    index = {}
    ov_state = {}
    for lot in lots:
        lid = str(lot.get("id", ""))
        if not lid or not isinstance(lot.get("vertices"), list) or len(lot["vertices"]) < 3:
            continue
        path = os.path.join(out_dir, f"{lid}.json")
        prev = json.load(open(path)) if os.path.exists(path) else None
        try:
            res = process_lot(lot, out_dir)
        except Exception as e:  # una falla no detiene al resto
            res = {"status": "sin dato", "reason": type(e).__name__}
        res["history"] = merge_history(prev, res, run_date)
        if res["status"] != "recibido" and prev and prev.get("status") == "recibido":
            # se conserva el último resultado válido, marcado como anterior
            keep = {k: prev[k] for k in ("scene", "water_ha", "water_pct", "water_bodies", "water_geojson", "ndvi_mean", "lot_ha") if k in prev}
            res.update(keep); res["stale"] = True
        env = entorno(lot, prev, ov_state)
        if env:
            res["entorno"] = env
        res.update({"id": lid, "updated": run_date, "method": "Sentinel-2 L2A (Earth Search) · geoai.segment_water (OmniWaterMask) · NDVI medio en el lote"})
        json.dump(res, open(path, "w"), ensure_ascii=False)
        index[lid] = {"updated": run_date, "status": res["status"], "water_ha": res.get("water_ha"), "scene_date": (res.get("scene") or {}).get("date")}
        ok += res["status"] == "recibido"; fail += res["status"] != "recibido"
        time.sleep(0.5)
    json.dump({"updated": run_date, "lotes": index}, open(os.path.join(out_dir, "index.json"), "w"), ensure_ascii=False)
    log(f"Lotes procesados: {ok} con resultado, {fail} sin dato.")
    if ov_state.get("errors"):
        log(f"Overture: {ov_state['errors']} lotes sin entorno ({ov_state.get('last_error')}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "datos"))
