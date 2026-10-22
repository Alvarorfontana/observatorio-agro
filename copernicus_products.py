"""Productos temáticos Copernicus procesados con Sentinel Hub (CDSE).

- Cambio de NDVI entre dos períodos (Sentinel-2 L2A, nubes enmascaradas con SCL)
- Agua por radar (Sentinel-1 GRD, VV en dB)
- Temperatura superficial diurna (Sentinel-3 SLSTR L2 LST, 1 km, vista regional)
- Monóxido de carbono, dióxido de nitrógeno y aerosoles (Sentinel-5P L2, ~5 km, vista regional)

Todo sale de píxeles reales: si el servicio no responde, se informa el error.
"""
import math
from datetime import datetime, timedelta

import requests

import pngmini
from copernicus_interpret import MAP_CLASSES

PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
STAC = "https://stac.dataspace.copernicus.eu/v1"
CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

# Productos regionales: el píxel es más grande que un lote, así que se muestra la zona
# alrededor (semilado en grados) y se marca el lote encima.
REGIONAL_HALF = {"lst": 0.3, "co": 1.0, "no2": 1.0, "aerosol": 1.0}


class ProductError(Exception):
    def __init__(self, message, status=502, detail=""):
        super().__init__(message)
        self.status, self.detail = status, detail


def _bbox(points):
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    return min(lons), min(lats), max(lons), max(lats)


def _size(west, south, east, north, longest=512):
    aspect = (east - west) * math.cos(math.radians((north + south) / 2)) / (north - south)
    if aspect >= 1:
        return longest, max(64, round(longest / aspect))
    return max(64, round(longest * aspect)), longest


def _threshold_script(bands, value_js, kind, mosaic_orbit=False, valid_js="true"):
    """Evalscript que pinta cada píxel con el color exacto de su clase."""
    classes = MAP_CLASSES[kind]["classes"]
    cuts = MAP_CLASSES[kind]["cuts"]
    cols = [list(c[0]) + [255] for c in classes]
    chain = "".join(f"v<{cut}?{cols[i]}:" for i, cut in enumerate(cuts)) + str(cols[-1])
    band_list = ",".join(f'"{b}"' for b in bands + ["dataMask"])
    if mosaic_orbit:
        return f"""//VERSION=3
function setup(){{return {{input:[{{bands:[{band_list}]}}],output:{{bands:4,sampleType:"UINT8"}},mosaicking:"ORBIT"}}}}
function evaluatePixel(samples){{var sum=0,n=0;for(var i=0;i<samples.length;i++){{var s=samples[i];if(s.dataMask&&({valid_js})){{sum+=({value_js});n++}}}}if(!n)return [0,0,0,0];var v=sum/n;return {chain}}}
"""
    return f"""//VERSION=3
function setup(){{return {{input:[{{bands:[{band_list}]}}],output:{{bands:4,sampleType:"UINT8"}}}}}}
function evaluatePixel(s){{if(!s.dataMask||!({valid_js}))return [0,0,0,0];var v={value_js};return {chain}}}
"""


NDVI_ENCODED = """//VERSION=3
function setup(){return {input:[{bands:["B04","B08","SCL","dataMask"]}],output:{bands:4,sampleType:"UINT8"}}}
function evaluatePixel(s){var ok=s.dataMask&&(s.SCL==4||s.SCL==5||s.SCL==6||s.SCL==7);if(!ok)return [0,0,0,0];
var v=(s.B08-s.B04)/(s.B08+s.B04+0.00001);v=Math.max(-1,Math.min(1,v));var e=Math.round((v+1)*127.5);return [e,e,e,255]}
"""


def _process(token, bounds, data, script, width, height):
    payload = {"input": {"bounds": bounds, "data": data},
               "output": {"width": width, "height": height,
                          "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
               "evalscript": script}
    try:
        r = requests.post(PROCESS_URL, json=payload, headers={"Authorization": "Bearer " + token}, timeout=55)
    except requests.RequestException as exc:
        raise ProductError("No hubo conexión con el procesamiento de Copernicus", 502, str(exc)[:250])
    if not r.ok:
        raise ProductError("Copernicus rechazó el procesamiento", 502, f"HTTP {r.status_code}: {r.text[:350]}")
    return r.content


def _range(start, end):
    return {"from": start + "T00:00:00Z", "to": end + "T23:59:59Z"}


def _polygon_bounds(points):
    ring = [[lon, lat] for lat, lon in points]
    ring.append(ring[0])
    return {"geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": {"crs": CRS84}}


# ─────────────────────────── geometría sobre la imagen ───────────────────────────

def _to_px(lat, lon, box, w, h):
    west, south, east, north = box
    return (lon - west) / (east - west) * (w - 1), (north - lat) / (north - south) * (h - 1)


def _inside(x, y, poly):
    hit = False
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            hit = not hit
    return hit


def _draw_outline(rows, poly_px, w, h):
    def put(x, y, col):
        if 0 <= x < w and 0 <= y < h:
            rows[y][x] = col
    for i in range(len(poly_px)):
        (x0, y0), (x1, y1) = poly_px[i - 1], poly_px[i]
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for k in range(steps + 1):
            x = round(x0 + (x1 - x0) * k / steps)
            y = round(y0 + (y1 - y0) * k / steps)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                put(x + dx, y + dy, (20, 20, 20, 255))
    for i in range(len(poly_px)):
        (x0, y0), (x1, y1) = poly_px[i - 1], poly_px[i]
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for k in range(steps + 1):
            put(round(x0 + (x1 - x0) * k / steps), round(y0 + (y1 - y0) * k / steps), (255, 255, 255, 255))


def _class_of(rgba, kind):
    palette = [c[0] for c in MAP_CLASSES[kind]["classes"]]
    best, dist = None, None
    for i, c in enumerate(palette):
        d = sum((a - b) ** 2 for a, b in zip(rgba[:3], c))
        if dist is None or d < dist:
            best, dist = i, d
    return best if rgba[3] and dist <= 300 else None


def _parcel_class(rows, poly_px, kind, w, h):
    """Clase dominante dentro del lote; si el lote es menor que un píxel, la del píxel central."""
    xs, ys = [p[0] for p in poly_px], [p[1] for p in poly_px]
    counts = {}
    for y in range(max(0, int(min(ys))), min(h, int(max(ys)) + 1)):
        for x in range(max(0, int(min(xs))), min(w, int(max(xs)) + 1)):
            if _inside(x, y, poly_px):
                k = _class_of(rows[y][x], kind)
                if k is not None:
                    counts[k] = counts.get(k, 0) + 1
    if not counts:
        cx, cy = round(sum(xs) / len(xs)), round(sum(ys) / len(ys))
        k = _class_of(rows[min(h - 1, max(0, cy))][min(w - 1, max(0, cx))], kind)
        if k is None:
            return None
        counts[k] = 1
    k = max(counts, key=counts.get)
    c = MAP_CLASSES[kind]["classes"][k]
    return {"range": c[1], "label": c[2]}


# ─────────────────────────────── productos ───────────────────────────────

def ndvi_change(token, points, before, after):
    """Diferencia de NDVI (después − antes) píxel a píxel, solo donde ambas fechas están despejadas."""
    west, south, east, north = _bbox(points)
    w, h = _size(west, south, east, north)
    bounds = _polygon_bounds(points)
    images = []
    for start, end in (before, after):
        data = [{"type": "sentinel-2-l2a", "dataFilter": {"timeRange": _range(start, end), "mosaickingOrder": "leastCC"}}]
        images.append(pngmini.decode(_process(token, bounds, data, NDVI_ENCODED, w, h)))
    (w1, h1, a), (w2, h2, b) = images
    if (w1, h1) != (w2, h2):
        raise ProductError("Las dos imágenes no tienen el mismo tamaño", 502)
    spec = MAP_CLASSES["ndvi_change"]
    cuts, cols = spec["cuts"], [c[0] for c in spec["classes"]]
    out, s1, s2, n = [], 0.0, 0.0, 0
    for ra, rb in zip(a, b):
        row = []
        for pa, pb in zip(ra, rb):
            if pa[3] == 0 or pb[3] == 0:
                row.append((0, 0, 0, 0))
                continue
            v1, v2 = pa[0] / 127.5 - 1, pb[0] / 127.5 - 1
            s1 += v1; s2 += v2; n += 1
            d = v2 - v1
            k = next((i for i, cut in enumerate(cuts) if d < cut), len(cuts))
            row.append(tuple(cols[k]) + (255,))
        out.append(row)
    extra = {"before": f"{before[0]} a {before[1]}", "after": f"{after[0]} a {after[1]}"}
    if n:
        extra.update(mean_before=round(s1 / n, 3), mean_after=round(s2 / n, 3))
    return pngmini.encode_rgba(w1, h1, out), extra, "Copernicus Sentinel-2 L2A · dos períodos"


def _latest_s1_date(points, start, end):
    west, south, east, north = _bbox(points)
    try:
        r = requests.post(STAC + "/search", json={"bbox": [west, south, east, north], "collections": ["sentinel-1-grd"],
                                                 "datetime": _range(start, end)["from"] + "/" + _range(start, end)["to"],
                                                 "limit": 100}, timeout=15)
        r.raise_for_status()
        dates = sorted(str(f.get("properties", {}).get("datetime", ""))[:10] for f in r.json().get("features", []))
        dates = [d for d in dates if len(d) == 10]
        return dates[-1] if dates else None
    except (requests.RequestException, ValueError):
        return None


def s1_water(token, points, start, end):
    west, south, east, north = _bbox(points)
    w, h = _size(west, south, east, north)
    day = _latest_s1_date(points, start, end)
    rng = _range(day, day) if day else _range(start, end)
    data = [{"type": "sentinel-1-grd",
             "dataFilter": {"timeRange": rng, "acquisitionMode": "IW", "polarization": "DV",
                            "resolution": "HIGH", "mosaickingOrder": "mostRecent"},
             "processing": {"orthorectify": True, "backCoeff": "GAMMA0_TERRAIN",
                            "speckleFilter": {"type": "LEE", "windowSizeX": 3, "windowSizeY": 3}}}]
    script = _threshold_script(["VV"], "10*Math.log(s.VV)/Math.LN10", "s1_water", valid_js="s.VV>0")
    png = _process(token, _polygon_bounds(points), data, script, w, h)
    return png, ({"acquired": day} if day else {}), "Copernicus Sentinel-1 GRD · VV"


def regional(token, points, kind, start, end):
    west, south, east, north = _bbox(points)
    cx, cy, half = (west + east) / 2, (south + north) / 2, REGIONAL_HALF[kind]
    box = (cx - half / math.cos(math.radians(cy)), cy - half, cx + half / math.cos(math.radians(cy)), cy + half)
    w, h = _size(*box, longest=360)
    bounds = {"bbox": list(box), "properties": {"crs": CRS84}}
    if kind == "lst":
        data = [{"type": "sentinel-3-slstr-l2",
                 "dataFilter": {"timeRange": _range(start, end), "orbitDirection": "DESCENDING",
                                "mosaickingOrder": "leastCC", "maxCloudCoverage": 40}}]
        script = _threshold_script(["LST"], "s.LST-273.15", "lst", valid_js="s.LST>230&&s.LST<350")
        source = "Copernicus Sentinel-3 SLSTR L2 LST · pasada diurna"
    else:
        band = {"co": "CO", "no2": "NO2", "aerosol": "AER_AI_340_380"}[kind]
        data = [{"type": "sentinel-5p-l2", "dataFilter": {"timeRange": _range(start, end)}}]
        script = _threshold_script([band], "s." + band, kind, mosaic_orbit=True)
        source = "Copernicus Sentinel-5P L2 · " + band
    w0, h0, rows = pngmini.decode(_process(token, bounds, data, script, w, h))
    rows = [list(r) for r in rows]
    poly_px = [_to_px(lat, lon, box, w0, h0) for lat, lon in points]
    parcel = _parcel_class(rows, poly_px, kind, w0, h0)
    _draw_outline(rows, poly_px, w0, h0)
    km = round(2 * half * 111)
    return pngmini.encode_rgba(w0, h0, rows), {"parcel": parcel, "region_km": km}, source


def run(kind, token, points, body):
    """Despacha el producto pedido. Devuelve (png, extra, fuente)."""
    start, end = str(body["start"]), str(body["end"])
    a, b = datetime.fromisoformat(start), datetime.fromisoformat(end)
    if a > b or (b - a).days > 366:
        raise ProductError("Período inválido o mayor a un año", 400)
    if kind == "ndvi_change":
        cs, ce = str(body.get("compare_start") or ""), str(body.get("compare_end") or "")
        if not cs or not ce:
            cs = (a - timedelta(days=365)).strftime("%Y-%m-%d")
            ce = (b - timedelta(days=365)).strftime("%Y-%m-%d")
        if datetime.fromisoformat(cs) > datetime.fromisoformat(ce):
            raise ProductError("El período de comparación es inválido", 400)
        return ndvi_change(token, points, (cs, ce), (start, end))
    if kind == "s1_water":
        return s1_water(token, points, start, end)
    if kind in ("co", "no2", "aerosol") and (b - a).days > 31:
        raise ProductError("Para gases y humo el período máximo es de 31 días", 400)
    if kind in REGIONAL_HALF:
        return regional(token, points, kind, start, end)
    raise ProductError("Producto no soportado", 400)
