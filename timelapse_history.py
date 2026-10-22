"""Historia del territorio con los mosaicos anuales de Google Earth Timelapse (1984–2022).

Asset: projects/ee-earth-timelapse/assets/annual · 30 m · bandas red/green/blue de 8 bits.
Licencia CC-BY 4.0: «Google Earth Timelapse (Google, Landsat, Copernicus)». Contiene datos
modificados de Copernicus Sentinel (2015 en adelante). Es una imagen para mirar, no para medir:
Google no la recomienda para análisis radiométrico cuantitativo.
"""
import math

import requests

import pngmini
import vegetation as veg
from copernicus_products import _draw_outline, _to_px

ASSET = "projects/ee-earth-timelapse/assets/annual"
FIRST_YEAR, LAST_YEAR = 1984, 2022
ATTRIBUTION = ("Google Earth Timelapse (Google, Landsat, Copernicus) · CC-BY 4.0 · "
               "contiene datos modificados de Copernicus Sentinel (2015 en adelante)")


class HistoryError(Exception):
    def __init__(self, message, status=502, detail=""):
        super().__init__(message)
        self.status, self.detail = status, detail


def _k(v):
    return {"constantValue": v}


def _f(name, **args):
    return {"functionInvocationValue": {"functionName": name, "arguments": args}}


def window(points, margin=0.35, min_deg=0.01):
    """Recuadro del lote con margen para ver el entorno."""
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    w, e, s, n = min(lons), max(lons), min(lats), max(lats)
    dy = max(n - s, min_deg) * (1 + 2 * margin) / 2
    cy = (n + s) / 2
    dx = max((e - w) * (1 + 2 * margin) / 2, dy / math.cos(math.radians(cy)) * 0.5)
    cx = (e + w) / 2
    return cx - dx, cy - dy, cx + dx, cy + dy


def request_body(year, box, width, height):
    image = _f("Image.select",
               input=_f("Collection.first", collection=_f(
                   "Collection.filter",
                   collection=_f("ImageCollection.load", id=_k(ASSET)),
                   filter=_f("Filter.equals", leftField=_k("year"), rightValue=_k(int(year))))),
               bandSelectors=_k(["red", "green", "blue"]))
    west, south, east, north = box
    return {"expression": {"result": "0", "values": {"0": image}},
            "fileFormat": "PNG",
            "grid": {"dimensions": {"width": width, "height": height},
                     "affineTransform": {"scaleX": (east - west) / width, "shearX": 0, "translateX": west,
                                         "shearY": 0, "scaleY": -(north - south) / height, "translateY": north},
                     "crsCode": "EPSG:4326"}}


def year_image(points, year):
    year = int(year)
    if not FIRST_YEAR <= year <= LAST_YEAR:
        raise HistoryError(f"Hay mosaicos de {FIRST_YEAR} a {LAST_YEAR}", 400)
    box = window(points)
    west, south, east, north = box
    aspect = (east - west) * math.cos(math.radians((north + south) / 2)) / (north - south)
    width, height = (384, max(64, round(384 / aspect))) if aspect >= 1 else (max(64, round(384 * aspect)), 384)
    try:
        proj, tok = veg.gee_token()
    except PermissionError as exc:
        raise HistoryError("Falta la credencial de Earth Engine en el servidor", 503, str(exc))
    except Exception as exc:  # cuenta de servicio mal pegada o rechazada
        raise HistoryError("Google no aceptó la cuenta de servicio de Earth Engine", 503, f"{type(exc).__name__}: {str(exc)[:160]}")
    try:
        r = requests.post(f"{veg.GEE}/projects/{proj}/image:computePixels", json=request_body(year, box, width, height),
                          headers={"Authorization": f"Bearer {tok}"}, timeout=45)
    except requests.RequestException as exc:
        raise HistoryError("No hubo conexión con Earth Engine", 502, str(exc)[:200])
    if r.status_code >= 400:
        try:
            msg = (r.json().get("error") or {}).get("message", "")
        except ValueError:
            msg = r.text[:200]
        raise HistoryError("Earth Engine rechazó el pedido", 502, f"HTTP {r.status_code}: {msg[:250]}")
    w, h, rows = pngmini.decode(r.content)
    rows = [list(row) for row in rows]
    _draw_outline(rows, [_to_px(lat, lon, box, w, h) for lat, lon in points], w, h)
    return pngmini.encode_rgba(w, h, rows)
