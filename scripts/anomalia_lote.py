"""Alerta temprana de estrés hídrico por lote (idea tomada de quantag; código propio).

Compara el NDVI (verdor) y el LSWI (agua en la hoja, NIR contra SWIR 1,6 µm) de la escena de esta semana
con la misma época (±15 días) de los últimos años, en el mismo lote. Si el lote está muy por debajo de su
propia historia, avisa. El LSWI suele bajar antes que el NDVI cuando falta agua, por eso adelanta semanas.

La línea de base se calcula una sola vez por semana del año y queda guardada en el resultado del lote,
así el costo baja con el tiempo. Es orientativo: no está validado en el terreno.
"""
import math, os, tempfile
from datetime import datetime, timedelta

import numpy as np

BASE_YEARS = int(os.environ.get("DOTS_BASE_YEARS", "5"))
WINDOW_DAYS = 15
MIN_YEARS = 3
STD_FLOOR = 0.03     # evita alarmas por historias demasiado parejas

# Rangos de lectura (z = desvíos respecto de la misma época de otros años)
RANGOS = [
    (-1.5, "fuerte", "Muy por debajo de lo normal para la época: revisar el lote."),
    (-0.75, "moderada", "Algo por debajo de lo normal para la época."),
    (math.inf, "normal", "Dentro de lo habitual para la época."),
]


def indices(stack_path, lot_geom):
    """NDVI y LSWI medios dentro del lote, desde el GeoTIFF de 6 bandas de procesar_lotes."""
    import rasterio
    from rasterio.mask import mask as rmask
    from shapely.geometry import mapping
    from shapely.ops import transform as stransform
    from pyproj import Transformer
    with rasterio.open(stack_path) as src:
        tr = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        g = stransform(tr.transform, lot_geom)
        arr, _ = rmask(src, [mapping(g)], crop=True, indexes=[3, 4, 5], nodata=0, filled=True)
    red, nir, swir = arr
    ok = (red > 0) & (nir > 0) & (swir > 0)
    if ok.sum() < 4:
        return None, None
    ndvi = (nir[ok] - red[ok]) / (nir[ok] + red[ok])
    lswi = (nir[ok] - swir[ok]) / (nir[ok] + swir[ok])
    return round(float(np.nanmean(ndvi)), 3), round(float(np.nanmean(lswi)), 3)


def week_key(date_str):
    return "S%02d" % datetime.fromisoformat(date_str[:10]).isocalendar()[1]


def baseline(lot_geom, bbox, scene_date, find, read_stack):
    """Una escena por año anterior en la misma ventana. find(bbox, today, lookback) devuelve un item STAC."""
    d = datetime.fromisoformat(scene_date[:10])
    rows = []
    for k in range(1, BASE_YEARS + 1):
        try:
            center = d.replace(year=d.year - k)
        except ValueError:            # 29 de febrero
            center = d.replace(year=d.year - k, day=28)
        try:
            item = find(bbox, center + timedelta(days=WINDOW_DAYS), 2 * WINDOW_DAYS)
            if item is None:
                continue
            with tempfile.TemporaryDirectory() as tmp:
                p = os.path.join(tmp, "b.tif")
                read_stack(item, bbox, p)
                nd, lw = indices(p, lot_geom)
            if nd is not None:
                rows.append({"year": center.year, "date": item.properties["datetime"][:10], "ndvi": nd, "lswi": lw})
        except Exception:
            continue                  # un año que falla no invalida el resto
    return rows


def _z(value, values):
    if value is None or len(values) < MIN_YEARS:
        return None, None
    m = float(np.mean(values)); s = max(float(np.std(values, ddof=1)), STD_FLOOR)
    return round((value - m) / s, 2), round(m, 3)


def nivel(z):
    if z is None:
        return None
    for lim, name, txt in RANGOS:
        if z < lim:
            return {"nivel": name, "texto": txt}


def evaluate(ndvi, lswi, base_rows):
    zn, mn = _z(ndvi, [r["ndvi"] for r in base_rows])
    zl, ml = _z(lswi, [r["lswi"] for r in base_rows if r.get("lswi") is not None])
    if zn is None and zl is None:
        return {"status": "sin base", "reason": f"Hacen falta al menos {MIN_YEARS} años despejados en la misma época; hay {len(base_rows)}.",
                "years": len(base_rows)}
    worst = min(z for z in (zn, zl) if z is not None)
    out = {"status": "recibido", "years": len(base_rows),
           "ndvi": ndvi, "ndvi_normal": mn, "z_ndvi": zn,
           "lswi": lswi, "lswi_normal": ml, "z_lswi": zl,
           "z": worst, **nivel(worst),
           "adelanto": bool(zl is not None and zl < -0.75 and (zn is None or zn >= -0.75)),
           "rangos": [{"desde": None if i == 0 else RANGOS[i - 1][0], "hasta": None if lim == math.inf else lim, "nivel": n}
                      for i, (lim, n, _) in enumerate(RANGOS)],
           "orientativo": True}
    if out["adelanto"]:
        out["texto"] += " El agua en la hoja (LSWI) ya bajó aunque el verdor todavía no: es la señal temprana."
    return out


def run(lot_geom, bbox, stack_path, scene_date, prev, find, read_stack):
    """Devuelve (anomalia, cache_de_bases). prev es el resultado anterior del lote (o None)."""
    ndvi, lswi = indices(stack_path, lot_geom)
    cache = dict((prev or {}).get("bases") or {})
    key = week_key(scene_date)
    if key not in cache:
        cache[key] = baseline(lot_geom, bbox, scene_date, find, read_stack)
    res = evaluate(ndvi, lswi, cache[key])
    res.update({"semana": key, "escena": scene_date,
                "metodo": f"Sentinel-2 L2A · NDVI y LSWI del lote contra la misma época (±{WINDOW_DAYS} días) de hasta {BASE_YEARS} años anteriores"})
    return res, cache
