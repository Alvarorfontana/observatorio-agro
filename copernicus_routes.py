"""Copernicus CDSE public STAC discovery for DOTS. No credentials or paid processing."""
from datetime import datetime, timedelta
import os
import time
from threading import Lock
from io import BytesIO
from flask import send_file, Response
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Polygon, String, Rect, Line
from xml.sax.saxutils import escape
import requests
from flask import Blueprint, jsonify, request

copernicus_api = Blueprint("copernicus_api", __name__)
_token_cache = {"token": None, "expires": 0}
_token_lock = Lock()
STAC = "https://stac.dataspace.copernicus.eu/v1"

@copernicus_api.get("/api/copernicus/status")
def status():
    return jsonify({"service": "copernicus", "catalog": STAC, "catalog_mode": "public",
                    "processing": "configured" if os.getenv("CDSE_CLIENT_ID") and os.getenv("CDSE_CLIENT_SECRET") else "credentials_required", "agent": "alpha_access_required",
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

def _cdse_token():
    client_id = os.getenv("CDSE_CLIENT_ID")
    secret = os.getenv("CDSE_CLIENT_SECRET")
    if not client_id or not secret:
        raise RuntimeError("Copernicus processing credentials not configured")
    with _token_lock:
        if _token_cache["token"] and time.time() < _token_cache["expires"]:
            return _token_cache["token"]
        response = requests.post(
            "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret},
            timeout=15)
        response.raise_for_status()
        data = response.json()
        _token_cache.update(token=data["access_token"],
                            expires=time.time() + max(30, int(data.get("expires_in", 300)) - 60))
        return data["access_token"]


@copernicus_api.post("/api/copernicus/map")
def thematic_map():
    """Process actual Sentinel-2 pixels. Never fabricate thematic rasters."""
    try:
        body = request.get_json(silent=True) or {}
        points = _valid_polygon(body.get("polygon"))
        kind = body.get("index", "ndvi")
        if kind not in ("ndvi", "ndwi", "truecolor"):
            raise ValueError("Supported indexes: ndvi, ndwi, truecolor")
        start, end = str(body["start"]), str(body["end"])
        a, b = datetime.fromisoformat(start), datetime.fromisoformat(end)
        if a > b or (b - a).days > 366:
            raise ValueError("Invalid period or period longer than 366 days")
        west, east = min(p[1] for p in points), max(p[1] for p in points)
        south, north = min(p[0] for p in points), max(p[0] for p in points)
        if west == east or south == north or (east-west)*(north-south) > 0.2:
            raise ValueError("Invalid or oversized parcel")
        ring = [[lon, lat] for lat, lon in points]
        ring.append(ring[0])
        token = _cdse_token()
        if kind == "ndvi":
            script = """//VERSION=3
function setup(){return {input:[{bands:["B04","B08","dataMask"]}],output:{bands:4,sampleType:"UINT8"}}}
function evaluatePixel(s){if(!s.dataMask)return [0,0,0,0];let v=(s.B08-s.B04)/(s.B08+s.B04+0.00001);return v<0?[145,95,65,255]:v<0.2?[230,188,90,255]:v<0.45?[203,223,83,255]:v<0.7?[86,171,77,255]:[16,106,54,255]}
"""
        elif kind == "ndwi":
            script = """//VERSION=3
function setup(){return {input:[{bands:["B03","B08","dataMask"]}],output:{bands:4,sampleType:"UINT8"}}}
function evaluatePixel(s){if(!s.dataMask)return [0,0,0,0];let v=(s.B03-s.B08)/(s.B03+s.B08+0.00001);return v<0?[171,139,92,255]:v<0.2?[197,212,172,255]:v<0.4?[98,177,209,255]:[26,96,180,255]}
"""
        else:
            script = """//VERSION=3
function setup(){return {input:[{bands:["B04","B03","B02","dataMask"]}],output:{bands:4,sampleType:"UINT8"}}}
function evaluatePixel(s){if(!s.dataMask)return [0,0,0,0];return [Math.min(255,Math.round(s.B04*650)),Math.min(255,Math.round(s.B03*650)),Math.min(255,Math.round(s.B02*650)),255]}
"""
        payload = {"input":{"bounds":{"geometry":{"type":"Polygon","coordinates":[ring]},
                      "properties":{"crs":"http://www.opengis.net/def/crs/OGC/1.3/CRS84"}},
                  "data":[{"type":"sentinel-2-l2a","dataFilter":{"timeRange":{"from":start+"T00:00:00Z","to":end+"T23:59:59Z"},"mosaickingOrder":"leastCC"}}]},
                   "output":{"width":512,"height":512,"responses":[{"identifier":"default","format":{"type":"image/png"}}]},
                   "evalscript":script}
        response = requests.post("https://sh.dataspace.copernicus.eu/api/v1/process",
                                 json=payload,headers={"Authorization":"Bearer "+token},timeout=55)
        if not response.ok:
            return jsonify({"error":"Sentinel Hub processing failed","status":response.status_code,
                            "detail":response.text[:350]}), 502
        return Response(response.content,mimetype="image/png",headers={"Cache-Control":"no-store","X-DOTS-Source":"CDSE Sentinel-2 L2A"})
    except RuntimeError as exc:
        return jsonify({"error":"Processing unavailable","detail":str(exc)}), 503
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"error":"Invalid processing request","detail":str(exc)}), 400
    except (requests.RequestException, KeyError) as exc:
        return jsonify({"error":"Copernicus processing connection failed","detail":str(exc)[:250]}), 502
