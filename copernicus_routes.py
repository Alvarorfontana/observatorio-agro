"""Copernicus CDSE public STAC discovery for DOTS. No credentials or paid processing."""
from datetime import datetime
import requests
from flask import Blueprint, jsonify, request

copernicus_api = Blueprint("copernicus_api", __name__)
STAC = "https://stac.dataspace.copernicus.eu/v1"

@copernicus_api.get("/api/copernicus/status")
def status():
    return jsonify({"service": "copernicus", "catalog": STAC, "catalog_mode": "public",
                    "processing": "not_configured", "agent": "alpha_access_required",
                    "collections": ["sentinel-1", "sentinel-2", "sentinel-3", "sentinel-5p"],
                    "note": "Availability must be checked in live STAC collections."})

@copernicus_api.get("/api/copernicus/collections")
def collections():
    try:
        r = requests.get(STAC + "/collections", timeout=12)
        r.raise_for_status()
        payload = r.json()
        return jsonify({"collections": [{"id": x.get("id"), "title": x.get("title")}
                   for x in payload.get("collections", [])]})
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"error": "Copernicus catalog unavailable", "detail": str(exc)}), 502

@copernicus_api.get("/api/copernicus/scenes")
def scenes():
    try:
        bbox = [float(x) for x in request.args.get("bbox", "").split(",")]
        if len(bbox) != 4 or not (-180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90):
            raise ValueError("Invalid bbox")
        if (bbox[2]-bbox[0]) * (bbox[3]-bbox[1]) > 4:
            raise ValueError("Area exceeds public query limit")
        start = request.args["start"]
        end = request.args["end"]
        a = datetime.fromisoformat(start.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end.replace("Z", "+00:00"))
        if a > b:
            raise ValueError("start must precede end")
        collection = request.args.get("collection", "sentinel-2-l2a")
        if not collection.replace("-", "").replace("_", "").isalnum() or len(collection) > 80:
            raise ValueError("Invalid collection")
        limit = min(max(int(request.args.get("limit", 20)), 1), 50)
    except (ValueError, KeyError) as exc:
        return jsonify({"error": "Invalid query", "detail": str(exc)}), 400
    try:
        r = requests.post(STAC + "/search", json={"bbox": bbox, "datetime": start + "/" + end,
            "collections": [collection], "limit": limit}, timeout=18)
        r.raise_for_status()
        data = r.json()
        return jsonify({"type": "FeatureCollection", "features": [{
            "id": f.get("id"), "collection": f.get("collection"),
            "geometry": f.get("geometry"), "properties": {
                "datetime": f.get("properties", {}).get("datetime"),
                "eo:cloud_cover": f.get("properties", {}).get("eo:cloud_cover")},
            "links": [x for x in f.get("links", []) if x.get("rel") in ("self", "alternate")]
        } for f in data.get("features", [])], "returned": len(data.get("features", []))})
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"error": "Copernicus query failed", "detail": str(exc)}), 502
