"""Copernicus CDSE public STAC discovery for DOTS. No credentials or paid processing."""
from datetime import datetime
from io import BytesIO
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Polygon, String
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

def _valid_polygon(value):
    if not isinstance(value, list) or not 3 <= len(value) <= 200:
        raise ValueError("A polygon with 3 to 200 vertices is required")
    points = []
    for point in value:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Invalid polygon coordinate")
        lat, lon = map(float, point)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Polygon coordinate out of range")
        points.append((lat, lon))
    if len(set(points)) < 3:
        raise ValueError("At least three distinct vertices required")
    return points

@copernicus_api.post("/api/copernicus/report")
def report():
    """PDF catalog report: footprint and verified scene metadata, no invented indices."""
    try:
        body = request.get_json(silent=True) or {}
        points = _valid_polygon(body.get("polygon"))
        scenes = body.get("scenes", [])
        if not isinstance(scenes, list) or len(scenes) > 50:
            raise ValueError("Invalid scenes list")
        start, end = str(body.get("start", "")), str(body.get("end", ""))
        datetime.fromisoformat(start)
        datetime.fromisoformat(end)
        collection = str(body.get("collection", ""))[:100]
        if not collection:
            raise ValueError("Collection required")
    except (TypeError, ValueError) as exc:
        return jsonify({"error": "Invalid report request", "detail": str(exc)}), 400
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(595, 842), topMargin=44, bottomMargin=44)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("DOTS | Informe de consulta Copernicus", styles["Title"]),
        Paragraph("Catalogo satelital y delimitacion territorial", styles["Heading2"]),
        Paragraph("Periodo: %s a %s | Coleccion: %s" % (start, end, collection), styles["Normal"]),
        Paragraph("Vertices del area: %d | Escenas incluidas: %d" % (len(points), len(scenes)), styles["Normal"]),
        Spacer(1, 18),
        Paragraph("Delimitacion de la zona de estudio", styles["Heading2"]),
    ]
    minlat, maxlat = min(p[0] for p in points), max(p[0] for p in points)
    minlon, maxlon = min(p[1] for p in points), max(p[1] for p in points)
    w, h = 450, 210
    drawing = Drawing(w, h)
    dx, dy = max(maxlon-minlon, 1e-9), max(maxlat-minlat, 1e-9)
    coords = []
    for lat, lon in points:
        coords.extend([24 + (lon-minlon)/dx*(w-48), 22 + (lat-minlat)/dy*(h-44)])
    drawing.add(Polygon(coords, strokeColor=colors.HexColor("#087f9e"), fillColor=colors.HexColor("#d5edf2"), strokeWidth=2))
    drawing.add(String(8, 5, "Oeste %.5f / Sur %.5f / Este %.5f / Norte %.5f" % (minlon,minlat,maxlon,maxlat), fontSize=8))
    elements.extend([drawing, Spacer(1, 16), Paragraph("Escenas reportadas por la consulta", styles["Heading2"])])
    rows = [["Fecha", "Coleccion", "ID de escena"]]
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        props = scene.get("properties") or {}
        rows.append([str(props.get("datetime") or "N/D")[:19], str(scene.get("collection") or "")[:24], str(scene.get("id") or "")[:44]])
    if len(rows) == 1:
        rows.append(["Sin escenas", "-", "-"])
    table = Table(rows, colWidths=[110, 125, 285], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#123747")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),("LINEBELOW",(0,0),(-1,-1),0.4,colors.lightgrey)]))
    elements.extend([table, Spacer(1, 20), Paragraph("Fuente: Copernicus Data Space Ecosystem (STAC). La geometria es la delimitacion aportada por el usuario. Este documento registra escenas de catalogo; no incluye calculos NDVI, mediciones de inundacion ni recorte raster. Las escenas deben verificarse en su origen.",styles["Normal"])])
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="DOTS_Copernicus_catalogo.pdf")
