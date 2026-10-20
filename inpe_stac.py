"""Conector experimental gratuito INPE Brazil Data Cube (STAC).
Solo descubre escenas y sus metadatos: NO calcula NDVI ni descarga raster.
No requiere clave. No sustituye la verificación end-to-end en Vercel.
"""
import math
import requests
from datetime import datetime, timezone

BASE = "https://data.inpe.br/bdc/stac/v1"
TIMEOUT = 18

def _json(url, params=None):
    response = requests.get(url, params=params, timeout=TIMEOUT,
                            headers={"User-Agent": "DOTS-Campo/1.0 (STAC research)"})
    response.raise_for_status()
    return response.json()

def collections():
    """Colecciones disponibles: obtener IDs reales, nunca suponerlos."""
    data = _json(BASE + "/collections")
    return [{"id": c.get("id"), "title": c.get("title"),
             "description": (c.get("description") or "")[:250]}
            for c in data.get("collections", []) if c.get("id")]

def scenes(lat, lon, collection_id, radius_deg=0.04, limit=10,
           start=None, end=None):
    """Escenas en una envolvente; no asegura cobertura dentro del polígono."""
    lat, lon = float(lat), float(lon)
    if not all(map(math.isfinite, (lat, lon))) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordenadas inválidas")
    if not isinstance(collection_id, str) or not collection_id or "/" in collection_id:
        raise ValueError("ID de colección inválido")
    radius_deg = float(radius_deg)
    if not 0 < radius_deg <= 1:
        raise ValueError("Radio inválido")
    limit = max(1, min(int(limit), 30))
    params = {"bbox": ",".join(map(str, [max(-180, lon-radius_deg),
                                         max(-90, lat-radius_deg),
                                         min(180, lon+radius_deg),
                                         min(90, lat+radius_deg)])),
              "limit": limit}
    if start and end:
        params["datetime"] = f"{start}/{end}"
    from urllib.parse import quote
    url = BASE + "/collections/" + quote(collection_id, safe="") + "/items"
    payload = _json(url, params)
    items = []
    for f in payload.get("features", []):
        props = f.get("properties") or {}
        assets = f.get("assets") or {}
        items.append({"id": f.get("id"), "collection": f.get("collection", collection_id),
                      "datetime": props.get("datetime"), "bbox": f.get("bbox"),
                      "cloud_cover": props.get("eo:cloud_cover"),
                      "assets": [{"name": k, "href": v.get("href"), "type": v.get("type")}
                                 for k, v in assets.items() if v.get("href")],
                      "source": "INPE Brazil Data Cube"})
    return {"status": "recibido", "data": {"scenes": items, "count": len(items)},
            "error": None, "consulted_at": datetime.now(timezone.utc).isoformat(),
            "source_url": url, "scope": "catálogo de escenas STAC, no raster procesado",
            "organism": "INPE / Brazil Data Cube"}
