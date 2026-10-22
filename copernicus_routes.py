"""Copernicus CDSE public STAC discovery for DOTS. No credentials or paid processing."""
from datetime import datetime, timedelta
from io import BytesIO
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Polygon, String, Rect, Line
from xml.sax.saxutils import escape
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
        interval = a.strftime("%Y-%m-%dT00:00:00Z") + "/" + b.strftime("%Y-%m-%dT23:59:59Z")
        r = requests.post(STAC + "/search", json={"bbox": bbox, "datetime": interval,
            "collections": [collection], "limit": limit}, timeout=18)
        if not r.ok:
            try:
                upstream = r.json()
                reason = upstream.get("detail", upstream.get("message", upstream))
            except ValueError:
                reason = r.text[:350]
            return jsonify({"error":"Copernicus rejected the scene search", "detail": str(reason)[:500], "upstream_status":r.status_code}), 502
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
        report_title = str(body.get("title") or "Informe territorial Copernicus")[:120]
        notes = str(body.get("notes") or "")[:1200]
        if not collection:
            raise ValueError("Collection required")
    except (TypeError, ValueError) as exc:
        return jsonify({"error": "Invalid report request", "detail": str(exc)}), 400
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(595, 842), topMargin=44, bottomMargin=44)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("DOTS | " + escape(report_title), styles["Title"]),
        Paragraph("Catalogo satelital y delimitacion territorial", styles["Heading2"]),
        Paragraph("Periodo: %s a %s | Coleccion: %s" % (escape(start), escape(end), escape(collection)), styles["Normal"]),
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
    table = Table(rows, colWidths=[95, 110, 245], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#123747")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),("LINEBELOW",(0,0),(-1,-1),0.4,colors.lightgrey)]))
    # Graficos reproducibles basados solo en metadatos del catalogo.
    from collections import Counter
    dates = Counter()
    cloud_buckets = [0, 0, 0, 0, 0]
    cloud_total = 0
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        props = scene.get("properties") or {}
        dt = str(props.get("datetime") or "")[:10]
        if len(dt) == 10:
            dates[dt] += 1
        cloud = props.get("eo:cloud_cover")
        if isinstance(cloud, (int, float)) and 0 <= cloud <= 100:
            cloud_buckets[min(int(cloud // 20), 4)] += 1
            cloud_total += 1
    def bar_graph(title, pairs):
        canvas = Drawing(450, 160)
        canvas.add(String(8, 145, title, fontSize=11, fillColor=colors.HexColor("#123747")))
        if not pairs:
            canvas.add(String(8, 85, "Sin datos disponibles para este grafico", fontSize=9))
            return canvas
        max_value = max(1, max(v for _, v in pairs))
        top = pairs[:8]
        for i, (label, value) in enumerate(top):
            y = 124 - i * 15
            canvas.add(String(8, y, str(label)[:18], fontSize=8))
            canvas.add(Rect(125, y - 2, 245 * value / max_value, 10,
                            fillColor=colors.HexColor("#35b3cf"), strokeColor=None))
            canvas.add(String(378, y, str(value), fontSize=8))
        return canvas
    elements.extend([Spacer(1, 14), Paragraph("Graficos de las escenas consultadas", styles["Heading2"]),
                     Paragraph("Los siguientes graficos representan metadatos del catalogo, no mediciones dentro de la parcela.", styles["Normal"]),
                     bar_graph("Escenas por fecha (hasta 8 fechas)", sorted(dates.items())),
                     bar_graph("Distribucion de cobertura nubosa (%)",
                               list(zip(["0-19", "20-39", "40-59", "60-79", "80-100"], cloud_buckets)) if cloud_total else [])])
    elements.extend([Spacer(1, 12), Paragraph("Mapas tematicos de vegetacion, agua y temperatura", styles["Heading2"]),
                     Paragraph("No disponibles en esta consulta: requieren procesar pixeles satelitales y recortar el resultado a la parcela. No se generan mapas simulados.", styles["Normal"])])
    elements.extend([table, Spacer(1, 20), Paragraph("Fuente: Copernicus Data Space Ecosystem (STAC). La geometria es la delimitacion aportada por el usuario. Este documento registra escenas de catalogo; no incluye calculos NDVI, mediciones de inundacion ni recorte raster. Las escenas deben verificarse en su origen.",styles["Normal"])])
    if notes.strip():
        elements.extend([Spacer(1, 16), Paragraph("Observaciones del informe", styles["Heading2"]), Paragraph(escape(notes).replace("\\n", "<br/>"), styles["Normal"])])
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="DOTS_Copernicus_catalogo.pdf")
