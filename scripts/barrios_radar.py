"""Barrios populares por radar en las localidades ribereñas de DOTS (Sentinel-1 + Sentinel-2 + RENABAP).

Idea (Sapienza / Pavía): las imágenes en color confunden un barrio popular con un barrio denso común; el radar
Sentinel-1 responde a la forma y al desorden de las construcciones, y casi no cambia entre estaciones.

Qué hace, en GitHub Actions y con Google Earth Engine:
  1. Baja los polígonos del Registro Nacional de Barrios Populares (RENABAP) alrededor de cada localidad.
  2. Arma, para cada píxel construido (ESA WorldCover), tres escalones de radar —brillo (VV, VH, VH−VV),
     textura (GLCM: contraste, varianza, entropía, homogeneidad) e índice de dispersión (coeficiente de variación
     local y temporal, y diferencia entre estación seca y húmeda)—, las bandas ópticas de Sentinel-2 y la
     morfología de las construcciones (Google Open Buildings temporal: cantidad, altura y su variación).
  3. Etiquetas: dentro de un polígono RENABAP = barrio popular; construido a más de 60 m de cualquiera = barrio común.
  4. Entrena bosques aleatorios (solo óptico / óptico + radar / + edificios / + etiquetas de otras ciudades, como
     los barrios populares de Nairobi mapeados en OpenStreetMap o data/etiquetas_externas.geojson) y los evalúa dejando afuera una ciudad
     argentina por vez: así se mide cómo anda en una ciudad que el modelo nunca vio.
  5. Aplica el mejor de los dos con radar a las 34 localidades (también Paraguay y Uruguay, donde no hay RENABAP),
     y cruza con WorldPop 2020 y la altura sobre el río (MERIT Hydro HAND).

Salida: data/barrios_radar.json y data/barrios_radar/<id>.png (rama datos).
Requiere los secretos GOOGLE_CLOUD_PROJECT y GOOGLE_APPLICATION_CREDENTIALS_JSON (los mismos de Vercel).
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

YEAR = int(os.environ.get("BARRIOS_YEAR", "2024"))
RADIUS_M = 15000
POINTS_PER_CLASS = int(os.environ.get("BARRIOS_POINTS", "400"))
MIN_POLYGONS = 3            # una ciudad entra al entrenamiento si tiene al menos estos barrios RENABAP
NEG_BUFFER_M = 60
HAND_BANDS = (1, 2, 3, 5)
# Muestras ya calculadas: muestrear es lo que más cuota de Earth Engine gasta. Se reutilizan si no cambió el año ni
# las capas; BARRIOS_RESAMPLE=1 obliga a recalcularlas.
SAMPLES_CACHE = os.path.join(ROOT, "scripts", "cache", "barrios_muestras.json")
TRAIN_PER_CITY = 250       # puntos por ciudad que se suben a Earth Engine para entrenar el mapa
SEED = 7
# Bosque aleatorio como en el estudio: 500 árboles, profundidad 30, √variables por corte, clases balanceadas
RF_PARAMS = dict(n_estimators=500, max_depth=30, max_features="sqrt", class_weight="balanced", n_jobs=-1,
                 random_state=SEED)

# Archivo nacional oficial del RENABAP (6.467 barrios, diciembre de 2023). Se baja una sola vez y se guarda en caché.
RENABAP_URL = os.environ.get("RENABAP_URL", "https://www.argentina.gob.ar/sites/default/files/renabap-2023-12-06.geojson")
RENABAP_CACHE = os.path.join(ROOT, "scripts", "cache", "renabap.geojson")
RENABAP_WFS = os.environ.get("RENABAP_WFS", "https://geoportal.obraspublicas.gob.ar/geoserver/ows")
RENABAP_LAYER = os.environ.get("RENABAP_LAYER", "geonode:renabap2020_smz")
RENABAP_FILE = os.path.join(ROOT, "data", "renabap.geojson")      # alternativa: archivo descargado a mano
RENABAP_CREDIT = ("Registro Nacional de Barrios Populares (RENABAP), Secretaría de Integración Socio-Urbana · "
                  "versión 2023-12-06 publicada en argentina.gob.ar")

RADAR = ["VV", "VH", "VHVV", "VV_dry", "VV_wet", "VV_season", "VV_tstd",
         "VVt_contrast", "VVt_var", "VVt_ent", "VVt_idm", "VHt_contrast", "VHt_var", "VHt_ent",
         "VH_diff", "VV_cv3", "VV_cv5", "VV_lmean"]
OPTICAL = ["B2", "B3", "B4", "B8", "B11", "B12", "NDVI", "NDBI"]
BUILDINGS = ["BLD_count", "BLD_presence", "BLD_height", "BLD_hstd"]
SETS = {"optico": OPTICAL, "optico_radar": OPTICAL + RADAR, "optico_radar_edificios": OPTICAL + RADAR + BUILDINGS}
FINAL_CANDIDATES = ("optico_radar", "optico_radar_edificios", "optico_radar_externas")
# Etiquetas de otras ciudades (por ejemplo Nairobi y Eldoret, si los autores las comparten). GeoJSON con polígonos
# y propiedades «clase» ("informal" o "formal") y «ciudad». Se suman al entrenamiento solo si mejoran el resultado
# en ciudades argentinas que el modelo no vio.
EXTERNAL_FILE = os.path.join(ROOT, "data", "etiquetas_externas.geojson")
# Barrios populares de otras ciudades tomados de OpenStreetMap (Map Kibera, mapeo de Mathare y otros). Solo hay
# polígonos de barrio popular: los barrios comunes se toman de lo construido a más de EXTERNAL_NEG_BUFFER_M,
# más lejos que en Argentina porque OSM no marca todos los asentamientos.
OVERPASS = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
EXTERNAL_NEG_BUFFER_M = 300
OSM_CITIES = [
    {"ciudad": "Nairobi", "lat": -1.286, "lon": 36.817, "radius_m": 16000,
     "nombres": ["Kibera", "Kibra", "Mathare", "Mukuru", "Korogocho", "Kawangware", "Kangemi", "Viwandani",
                 "Kiambiu", "Majengo", "Sinai", "Kosovo", "Kiamaiko", "Gitathuru", "Soweto"]},
]


# ───────────────────────────── geometría ─────────────────────────────

def circle_bbox(lat, lon, radius_m=RADIUS_M):
    import math
    dlat = radius_m / 111320
    dlon = radius_m / (111320 * math.cos(math.radians(lat)))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def clean_polygons(geojson, bbox, tolerance=0.00003):
    """Polígonos válidos y simplificados dentro del recuadro, sin atributos (solo geometría)."""
    from shapely.geometry import box, mapping, shape
    area = box(*bbox)
    out = []
    for f in (geojson or {}).get("features", []):
        try:
            g = shape(f.get("geometry"))
        except Exception:
            continue
        if g.is_empty:
            continue
        if not g.is_valid:
            g = g.buffer(0)
        if not g.intersects(area):
            continue
        g = g.simplify(tolerance, preserve_topology=True)
        if g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty:
            out.append(mapping(g))
    return out


# ───────────────────────────── RENABAP ─────────────────────────────

_RENABAP_ALL = None
_WFS_DOWN = False


def _national():
    """Archivo nacional: caché local, si no el archivo oficial, si no un archivo dejado a mano en data/."""
    global _RENABAP_ALL
    if _RENABAP_ALL is not None:
        return _RENABAP_ALL
    for path in (RENABAP_CACHE, RENABAP_FILE):
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    _RENABAP_ALL = json.load(f)
                log(f"RENABAP desde {os.path.relpath(path, ROOT)}: {len(_RENABAP_ALL.get('features', []))} barrios")
                return _RENABAP_ALL
            except (OSError, ValueError):
                pass
    for attempt in range(2):
        try:
            r = requests.get(RENABAP_URL, timeout=300, headers={"User-Agent": "DOTS observatorio (datos abiertos)"})
            if r.ok:
                data = r.json()
                if data.get("features"):
                    os.makedirs(os.path.dirname(RENABAP_CACHE), exist_ok=True)
                    with open(RENABAP_CACHE, "w", encoding="utf-8") as f:
                        json.dump(data, f)
                    _RENABAP_ALL = data
                    log(f"RENABAP descargado: {len(data['features'])} barrios")
                    return data
            log(f"RENABAP oficial respondió HTTP {r.status_code}")
        except (requests.RequestException, ValueError) as exc:
            log(f"RENABAP oficial no respondió: {type(exc).__name__}")
        time.sleep(10)
    _RENABAP_ALL = {}
    return _RENABAP_ALL


def renabap(bbox):
    """Barrios RENABAP dentro del recuadro: archivo nacional oficial; el WFS queda como último recurso."""
    global _WFS_DOWN
    data = _national()
    if data.get("features"):
        return clean_polygons(data, bbox), "oficial"
    if not _WFS_DOWN:
        params = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": RENABAP_LAYER,
                  "outputFormat": "application/json", "srsName": "EPSG:4326",
                  "bbox": "%f,%f,%f,%f,EPSG:4326" % bbox}
        try:
            r = requests.get(RENABAP_WFS, params=params, timeout=45)
            if r.ok and r.headers.get("content-type", "").startswith(("application/json", "application/geo+json")):
                return clean_polygons(r.json(), bbox), "wfs"
        except (requests.RequestException, ValueError):
            pass
        _WFS_DOWN = True          # si no responde una vez, no se insiste en cada localidad
        log("El WFS del RENABAP tampoco responde: se sigue sin él")
    return [], "sin fuente"


def log(msg, error=False):
    """Mensaje al registro de la tarea; los errores además quedan como anotación visible en GitHub."""
    print(("::error::" if error else "") + msg, flush=True)


# ───────────────────────────── Earth Engine ─────────────────────────────

def ee_init():
    import ee
    info = json.loads(os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
    creds = ee.ServiceAccountCredentials(info["client_email"], key_data=json.dumps(info))
    ee.Initialize(creds, project=os.environ["GOOGLE_CLOUD_PROJECT"])
    return ee


def stack(ee, region):
    """Capas por píxel: radar en tres escalones + óptico. 10 m."""
    start, end = f"{YEAR}-01-01", f"{YEAR + 1}-01-01"
    # radar: tres años centrados en YEAR. Desde la falla de Sentinel-1B hay zonas sin pasadas VV+VH en un solo año.
    s1 = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(region).filterDate(f"{YEAR - 1}-01-01", f"{YEAR + 2}-01-01")
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
          .select(["VV", "VH"]))
    med = s1.median()
    vv, vh = med.select("VV"), med.select("VH")
    dry = s1.filter(ee.Filter.calendarRange(6, 9, "month")).select("VV").median().rename("VV_dry")
    wet = s1.filter(ee.Filter.calendarRange(12, 3, "month")).select("VV").median().rename("VV_wet")
    tstd = s1.select("VV").reduce(ee.Reducer.stdDev()).rename("VV_tstd")
    # textura (escalón 2 del estudio): GLCM 3×3 sobre VV y VH en dB llevados a enteros
    q = vv.add(30).multiply(4).clamp(0, 160).toInt().rename("VVt")
    glcm = q.glcmTexture(size=1).select(["VVt_contrast", "VVt_var", "VVt_ent", "VVt_idm"])
    qh = vh.add(35).multiply(4).clamp(0, 160).toInt().rename("VHt")
    glcm_h = qh.glcmTexture(size=1).select(["VHt_contrast", "VHt_var", "VHt_ent"])
    # escalón 3 del estudio: entropía de VH en 7×7 sobre la retrodispersión VH media (lineal)
    vh_lin = ee.Image(10).pow(vh.divide(10))
    vh_diff = (qh.glcmTexture(size=3).select("VHt_ent")
               .divide(vh_lin.reduceNeighborhood(ee.Reducer.mean(), ee.Kernel.square(3))).rename("VH_diff"))
    # índice de dispersión: retornos débiles y desparejos de construcciones chicas y desordenadas
    lin = ee.Image(10).pow(vv.divide(10))
    k3, k5 = ee.Kernel.square(1), ee.Kernel.square(2)
    m3 = lin.reduceNeighborhood(ee.Reducer.mean(), k3)
    cv3 = lin.reduceNeighborhood(ee.Reducer.stdDev(), k3).divide(m3).rename("VV_cv3")
    m5 = lin.reduceNeighborhood(ee.Reducer.mean(), k5)
    cv5 = lin.reduceNeighborhood(ee.Reducer.stdDev(), k5).divide(m5).rename("VV_cv5")
    radar = ee.Image.cat([vv.rename("VV"), vh.rename("VH"), vh.subtract(vv).rename("VHVV"), dry, wet,
                          wet.subtract(dry).rename("VV_season"), tstd, glcm, glcm_h, vh_diff, cv3, cv5,
                          m5.log10().multiply(10).rename("VV_lmean")])
    cs = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(region).filterDate(start, end)
          .linkCollection(cs, ["cs"]).map(lambda i: i.updateMask(i.select("cs").gte(0.6)))
          .select(["B2", "B3", "B4", "B8", "B11", "B12"]).median().divide(10000))
    ndvi = s2.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndbi = s2.normalizedDifference(["B11", "B8"]).rename("NDBI")
    # morfología de las construcciones (Google Open Buildings temporal, 4 m): cuántas, qué tan altas y qué tan
    # parejas en 25 m a la redonda. Si la región no tiene cobertura queda en 0 y el modelo sin edificios gana.
    yb = min(YEAR, 2023)
    ob = (ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1").filterBounds(region)
          .filterDate(f"{yb}-01-01", f"{yb + 1}-01-01").mosaic())
    k25 = ee.Kernel.circle(25, "meters")
    bld = ee.Image.cat([
        ob.select("building_fractional_count").reduceNeighborhood(ee.Reducer.sum(), k25).rename("BLD_count"),
        ob.select("building_presence").reduceNeighborhood(ee.Reducer.mean(), k25).rename("BLD_presence"),
        ob.select("building_height").reduceNeighborhood(ee.Reducer.mean(), k25).rename("BLD_height"),
        ob.select("building_height").reduceNeighborhood(ee.Reducer.stdDev(), k25).rename("BLD_hstd"),
    ]).unmask(0)
    built = ee.ImageCollection("ESA/WorldCover/v200").first().eq(50).rename("built")
    return ee.Image.cat([s2, ndvi, ndbi, radar, bld]).updateMask(built), built


def labels(ee, polys, built, neg_buffer=NEG_BUFFER_M):
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry(p)) for p in polys])
    inside = ee.Image(0).paint(fc, 1)
    near = fc.distance(neg_buffer * 2).lte(neg_buffer).unmask(0)
    pos = built.And(inside.eq(1))
    neg = built.And(inside.eq(0)).And(near.eq(0))
    return ee.Image(0).where(neg, 0).where(pos, 1).updateMask(pos.Or(neg)).rename("label").toInt(), fc


def sample_city(ee, lat, lon, polys, radius_m=RADIUS_M, neg_buffer=NEG_BUFFER_M):
    region = ee.Geometry.Point([lon, lat]).buffer(radius_m)
    img, built = stack(ee, region)
    lab, _ = labels(ee, polys, built, neg_buffer)
    pts = img.addBands(lab).stratifiedSample(numPoints=POINTS_PER_CLASS, classBand="label", region=region, scale=10,
                                             seed=SEED, classValues=[0, 1],
                                             classPoints=[POINTS_PER_CLASS, POINTS_PER_CLASS],
                                             dropNulls=True, tileScale=8, geometries=False)
    return pts


def load_external():
    """Etiquetas de otras ciudades agrupadas por ciudad: {ciudad: {"informal": [...], "formal": [...]}}."""
    if not os.path.exists(EXTERNAL_FILE):
        return {}
    with open(EXTERNAL_FILE, encoding="utf-8") as f:
        gj = json.load(f)
    out = {}
    for feat in gj.get("features", []):
        props, geom = feat.get("properties") or {}, feat.get("geometry")
        clase = str(props.get("clase", "")).lower()
        if clase not in ("informal", "formal") or not geom:
            continue
        out.setdefault(str(props.get("ciudad") or "externa"), {"informal": [], "formal": []})[clase].append(geom)
    return {c: v for c, v in out.items() if v["informal"] and v["formal"]}


def overpass_query(bbox, names):
    w, s_, e, n = bbox
    bb = f"{s_},{w},{n},{e}"
    pattern = "|".join(names)
    return f"""[out:json][timeout:180];
(
  way["landuse"="residential"]["residential"="informal"]({bb});
  relation["landuse"="residential"]["residential"="informal"]({bb});
  way["informal"="yes"]["landuse"]({bb});
  relation["informal"="yes"]["landuse"]({bb});
  way["place"~"^(neighbourhood|suburb|quarter)$"]["name"~"^({pattern})",i]({bb});
  relation["place"~"^(neighbourhood|suburb|quarter)$"]["name"~"^({pattern})",i]({bb});
  way["landuse"="residential"]["name"~"^({pattern})",i]({bb});
  relation["landuse"="residential"]["name"~"^({pattern})",i]({bb});
  way["residential"="informal"]({bb});
  relation["residential"="informal"]({bb});
);
out geom;"""


def osm_polygons(elements):
    """Polígonos a partir de la respuesta de Overpass (vías cerradas y multipolígonos)."""
    from shapely.geometry import LineString, Polygon, mapping
    from shapely.ops import polygonize, unary_union
    out = []
    for el in elements:
        if el.get("type") == "way":
            pts = [(p["lon"], p["lat"]) for p in el.get("geometry") or []]
            if len(pts) >= 4 and pts[0] == pts[-1]:
                g = Polygon(pts)
                if g.is_valid and g.area > 0:
                    out.append(mapping(g))
        elif el.get("type") == "relation":
            lines = [LineString([(p["lon"], p["lat"]) for p in m.get("geometry") or []])
                     for m in el.get("members") or [] if m.get("role") in ("outer", "") and len(m.get("geometry") or []) >= 2]
            polys = list(polygonize(unary_union(lines))) if lines else []
            if polys:
                out.append(mapping(unary_union(polys)))
    return out


def osm_informal(city):
    bbox = circle_bbox(city["lat"], city["lon"], city["radius_m"])
    for attempt in range(3):
        try:
            r = requests.post(OVERPASS, data={"data": overpass_query(bbox, city["nombres"])}, timeout=200,
                              headers={"User-Agent": "DOTS observatorio (datos abiertos)"})
            if r.ok:
                els = r.json().get("elements", [])
                kinds = {}
                for el in els:
                    kinds[el.get("type")] = kinds.get(el.get("type"), 0) + 1
                names = sorted({(el.get("tags") or {}).get("name", "") for el in els} - {""})[:15]
                log(f"  Overpass {city['ciudad']}: {len(els)} elementos {kinds} · {', '.join(names)}")
                return clean_polygons({"features": [{"geometry": g} for g in osm_polygons(els)]}, bbox)
            log(f"  Overpass respondió HTTP {r.status_code}")
        except (requests.RequestException, ValueError) as exc:
            log(f"  Overpass no respondió: {type(exc).__name__}")
        time.sleep(10 * (attempt + 1))
    return []


def sample_external(ee, groups):
    """Puntos de barrio popular (1) y barrio común (0) dentro de los polígonos de otra ciudad."""
    inf = ee.FeatureCollection([ee.Feature(ee.Geometry(g)) for g in groups["informal"]])
    frm = ee.FeatureCollection([ee.Feature(ee.Geometry(g)) for g in groups["formal"]])
    region = inf.merge(frm).geometry().bounds()
    img, built = stack(ee, region)
    lab = (ee.Image(0).paint(frm, 2).paint(inf, 3).subtract(2).updateMask(
        ee.Image(0).paint(frm, 1).paint(inf, 1).eq(1)).rename("label").toInt())
    return img.addBands(lab).stratifiedSample(numPoints=POINTS_PER_CLASS, classBand="label", region=region, scale=10,
                                              seed=SEED, classValues=[0, 1],
                                              classPoints=[POINTS_PER_CLASS, POINTS_PER_CLASS],
                                              dropNulls=True, tileScale=8, geometries=False)


# ───────────────────────────── evaluación ─────────────────────────────

def rows_to_xy(rows, feats):
    X, y = [], []
    for r in rows:
        if all(isinstance(r.get(f), (int, float)) for f in feats) and r.get("label") in (0, 1):
            X.append([r[f] for f in feats])
            y.append(int(r["label"]))
    return X, y


def leave_one_city_out(samples, external=None):
    """Entrena con todas las ciudades menos una y mide en la que quedó afuera.

    Las muestras externas (otras ciudades del mundo) solo se suman al entrenamiento de la variante
    «optico_radar_externas»; la medición es siempre en ciudades argentinas que el modelo no vio."""
    external = external or []
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score
    cities = [c for c, rows in samples.items() if len({r.get("label") for r in rows}) == 2]
    per_city = []
    for test in cities:
        row = {"city": test}
        variants = dict(SETS)
        if external:
            variants["optico_radar_externas"] = SETS["optico_radar"]
        for name, feats in variants.items():
            Xtr, ytr = [], []
            for c in cities:
                if c != test:
                    X, y = rows_to_xy(samples[c], feats)
                    Xtr += X; ytr += y
            if name == "optico_radar_externas":
                X, y = rows_to_xy(external, feats)
                Xtr += X; ytr += y
            Xte, yte = rows_to_xy(samples[test], feats)
            if len(set(ytr)) < 2 or len(set(yte)) < 2:
                continue
            rf = RandomForestClassifier(**RF_PARAMS)
            rf.fit(Xtr, ytr)
            pred = rf.predict(Xte)
            row[name] = {"f1_barrio": round(f1_score(yte, pred, pos_label=1), 3),
                         "exactitud": round(accuracy_score(yte, pred), 3), "puntos": len(yte)}
        if len(row) > 1:
            per_city.append(row)
    def mean(name, key):
        vals = [r[name][key] for r in per_city if name in r]
        return round(sum(vals) / len(vals), 3) if vals else None
    names = list(SETS) + (["optico_radar_externas"] if external else [])
    summary = {name: {"f1_barrio": mean(name, "f1_barrio"), "exactitud": mean(name, "exactitud")} for name in names}
    importance = None
    best = choose_final(summary)
    allX, ally = [], []
    feats_best = feats_for(best)
    for c in cities:
        X, y = rows_to_xy(samples[c], feats_best)
        allX += X; ally += y
    if best == "optico_radar_externas":
        X, y = rows_to_xy(external, feats_best)
        allX += X; ally += y
    if len(set(ally)) == 2:
        rf = RandomForestClassifier(**RF_PARAMS).fit(allX, ally)
        pairs = sorted(zip(feats_best, rf.feature_importances_), key=lambda p: -p[1])
        importance = [{"capa": k, "peso": round(float(v), 3)} for k, v in pairs]
    return per_city, summary, importance


def feats_for(name):
    return SETS["optico_radar"] if name == "optico_radar_externas" else SETS[name]


def choose_final(summary):
    """Modelo final: el que mejor encuentra barrios en ciudades que no vio (sin edificios ante empate)."""
    score = lambda n: (summary.get(n) or {}).get("f1_barrio") or -1
    return max(FINAL_CANDIDATES, key=lambda n: (score(n), n == "optico_radar"))


# ───────────────────────────── mapeo y exposición ─────────────────────────────

def map_place(ee, clf, st, polys, feats):
    region = ee.Geometry.Point([st["lon"], st["lat"]]).buffer(RADIUS_M)
    img, built = stack(ee, region)
    informal = img.select(feats).classify(clf).eq(1).And(built).selfMask().rename("informal")
    area = ee.Image.pixelArea()
    popcoll = ee.ImageCollection("WorldPop/GP/100m/pop").filter(ee.Filter.eq("year", 2020))
    proj = popcoll.first().projection()   # el mosaico pierde la grilla de 100 m: se la devuelvo
    pop = popcoll.mosaic().select("population").setDefaultProjection(proj)
    hand = ee.Image("MERIT/Hydro/v1_0_1").select("hnd")
    bands = [area.updateMask(informal).rename("informal_m2")]
    # Personas: se cuentan en la grilla nativa de WorldPop (100 m), como en el módulo de zona baja, multiplicando la
    # gente de cada celda por la fracción de esa celda que el modelo marca como barrio popular (calculada a 20 m).
    # La versión anterior (densidad × área a 20 m) devolvía 0 personas en todas las localidades.
    frac = (informal.unmask(0).toFloat().reproject(ee.Projection("EPSG:3857").atScale(20))
            .reduceResolution(ee.Reducer.mean(), maxPixels=1024).reproject(proj))
    pop_bands = [pop.multiply(frac).rename("pop_informal")]
    for t in HAND_BANDS:
        pop_bands.append(pop.multiply(frac).multiply(hand.lte(t)).rename(f"pop_informal_le{t}"))
    if polys:
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry(p)) for p in polys])
        ren = ee.Image(0).paint(fc, 1).eq(1)
        near = fc.distance(NEG_BUFFER_M * 2).lte(NEG_BUFFER_M).unmask(0)
        bands += [area.updateMask(informal).updateMask(ren).rename("in_renabap_m2"),
                  area.updateMask(informal).updateMask(near.eq(0)).rename("outside_renabap_m2"),
                  area.updateMask(built).updateMask(ren).rename("renabap_built_m2"),
                  area.updateMask(built).updateMask(ren).updateMask(informal).rename("renabap_detected_m2")]
    stats, err = None, "sin respuesta"
    for scale in (20, 30):                 # superficies y personas no necesitan 10 m: 20 m es 4 veces más rápido
        try:
            stats = ee.Image.cat(bands).reduceRegion(ee.Reducer.sum(), region, scale=scale, maxPixels=1e10,
                                                      tileScale=8).getInfo()
            break
        except Exception as exc:  # cómputo muy grande: se reintenta a 30 m
            err = str(exc)[:200]
    if stats is None:
        return {"error": err}
    try:
        stats.update(ee.Image.cat(pop_bands).reduceRegion(ee.Reducer.sum(), region, crs=proj, maxPixels=1e10,
                                                          tileScale=8).getInfo() or {})
    except Exception as exc:  # sin personas, pero con superficie y mapa
        stats["pop_error"] = str(exc)[:200]
    ha = lambda k: None if stats.get(k) is None else round(stats[k] / 10000, 1)
    pp = lambda k: None if stats.get(k) is None else round(stats[k])
    out = {"informal_ha": ha("informal_m2"), "pop_informal": pp("pop_informal"),
           "pop_informal_hand": [{"hasta_m": t, "personas": pp(f"pop_informal_le{t}")} for t in HAND_BANDS]}
    if polys:
        built_ren, det = stats.get("renabap_built_m2") or 0, stats.get("renabap_detected_m2") or 0
        out.update(renabap_barrios=len(polys), in_renabap_ha=ha("in_renabap_m2"),
                   a_verificar_ha=ha("outside_renabap_m2"),
                   renabap_detectado=round(det / built_ren, 3) if built_ren else None)
    # imagen: fondo en color natural atenuado + zonas detectadas en rojo + RENABAP en amarillo
    try:
        bg = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(region)
              .filterDate(f"{YEAR}-01-01", f"{YEAR + 1}-01-01").filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
              .median().visualize(bands=["B4", "B3", "B2"], min=0, max=2500, gamma=1.2))
        layers = [bg, informal.visualize(palette=["d7301f"], opacity=0.75)]
        if polys:
            fc = ee.FeatureCollection([ee.Feature(ee.Geometry(p)) for p in polys])
            layers.append(ee.Image().byte().paint(fc, 1, 2).visualize(palette=["ffd400"]))
        url = ee.ImageCollection(layers).mosaic().getThumbURL(
            {"region": region.bounds(), "dimensions": 640, "format": "png"})
        out["_png"] = requests.get(url, timeout=120).content
    except Exception as exc:
        out["imagen_error"] = str(exc)[:160]
    return out


def rows_to_fc(ee, rows_by_city, feats, n=TRAIN_PER_CITY):
    """Colección de entrenamiento armada con las muestras guardadas (equilibrada por clase y ciudad)."""
    import random
    rnd = random.Random(SEED)
    feats_out = []
    for rows in rows_by_city.values():
        for label in (0, 1):
            pool = [r for r in rows if r.get("label") == label and all(isinstance(r.get(f), (int, float)) for f in feats)]
            for r in rnd.sample(pool, min(len(pool), n // 2)):
                feats_out.append(ee.Feature(None, {**{f: r[f] for f in feats}, "label": label}))
    return ee.FeatureCollection(feats_out)


def load_samples_cache():
    if os.environ.get("BARRIOS_RESAMPLE") == "1" or not os.path.exists(SAMPLES_CACHE):
        return None
    try:
        with open(SAMPLES_CACHE, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, ValueError):
        return None
    if c.get("year") != YEAR or c.get("capas") != sorted(set(OPTICAL + RADAR + BUILDINGS)):
        return None
    return c


def save_samples_cache(samples, external):
    os.makedirs(os.path.dirname(SAMPLES_CACHE), exist_ok=True)
    with open(SAMPLES_CACHE, "w", encoding="utf-8") as f:
        json.dump({"year": YEAR, "capas": sorted(set(OPTICAL + RADAR + BUILDINGS)),
                   "ciudades": samples, "externas": external}, f)


def main(out_path):
    import cuenca
    ee = ee_init()
    stations = cuenca.STATIONS
    polys_by, samples, sources = {}, {}, {}
    for st in stations:
        polys, src = renabap(circle_bbox(st["lat"], st["lon"]))
        polys_by[st["id"]], sources[st["id"]] = polys, src
        print(f"{st['place']}: {len(polys)} barrios RENABAP ({src})", flush=True)
    train = [st for st in stations if len(polys_by[st["id"]]) >= MIN_POLYGONS]
    if len(train) < 3:
        log(f"Solo {len(train)} localidades con barrios RENABAP: no alcanza para entrenar. Revisá la fuente.", error=True)
        raise SystemExit(1)
    cache = load_samples_cache()
    if cache:
        log(f"Reutilizo las muestras guardadas de {len(cache['ciudades'])} ciudades (no se vuelve a muestrear)")
        samples = {k: v for k, v in cache["ciudades"].items() if k in {st["id"] for st in train}}
    fcs = []
    for st in ([] if cache else train):
        fc = sample_city(ee, st["lat"], st["lon"], polys_by[st["id"]])
        try:
            samples[st["id"]] = [f["properties"] for f in fc.getInfo()["features"]]
            fcs.append(fc)          # solo las ciudades que muestrearon bien: una con error arruina el entrenamiento
            print(f"  muestras {st['place']}: {len(samples[st['id']])}", flush=True)
        except Exception as exc:
            print(f"  sin muestras en {st['place']}: {str(exc)[:160]}", flush=True)
    ext_fcs, ext_rows, ext_cities = [], [], []
    ext_by = dict((cache or {}).get("externas") or {})
    for city, rows in ext_by.items():
        ext_rows += rows; ext_cities.append(city)
    for city, groups in ({} if cache else load_external()).items():
        try:
            fc = sample_external(ee, groups)
            rows = [f["properties"] for f in fc.getInfo()["features"]]
            ext_fcs.append(fc); ext_rows += rows; ext_cities.append(city); ext_by[city] = rows
            print(f"  etiquetas externas {city}: {len(rows)} puntos", flush=True)
        except Exception as exc:
            print(f"  sin muestras externas en {city}: {str(exc)[:160]}", flush=True)
    for city in ([] if cache else OSM_CITIES):
        polys = osm_informal(city)
        print(f"  OpenStreetMap {city['ciudad']}: {len(polys)} barrios populares", flush=True)
        if len(polys) < MIN_POLYGONS:
            continue
        try:
            fc = sample_city(ee, city["lat"], city["lon"], polys, city["radius_m"], EXTERNAL_NEG_BUFFER_M)
            rows = [f["properties"] for f in fc.getInfo()["features"]]
            name = city["ciudad"] + " (OpenStreetMap)"
            ext_fcs.append(fc); ext_rows += rows; ext_cities.append(name); ext_by[name] = rows
            print(f"  etiquetas externas {city['ciudad']}: {len(rows)} puntos", flush=True)
        except Exception as exc:
            print(f"  sin muestras en {city['ciudad']}: {str(exc)[:160]}", flush=True)
    if not cache:
        save_samples_cache(samples, ext_by)
    per_city, summary, importance = leave_one_city_out(samples, ext_rows)
    final = choose_final(summary)
    log("Promedio por variante: " + json.dumps(summary, ensure_ascii=False))
    log(f"Modelo final: {final}")
    train_rows = dict(samples)
    if final == "optico_radar_externas":
        train_rows.update({"ext:" + k: v for k, v in ext_by.items()})
    training = rows_to_fc(ee, train_rows, feats_for(final))
    # para mapear alcanzan 200 árboles (la evaluación usa 500): el mapa sale mucho más rápido
    clf = ee.Classifier.smileRandomForest(numberOfTrees=200, seed=SEED).train(
        training, "label", feats_for(final))
    places = []

    def write(d):
        """Guarda lo que haya: si la tarea se corta por tiempo, queda lo ya calculado."""
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)

    base = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "year": YEAR,
            "model": {"promedio": summary, "modelo_final": final, "capas_mas_utiles": importance,
                      "ciudades_entrenamiento": [st["place"] for st in train], "ciudades_externas": ext_cities,
                      "evaluacion_por_ciudad": [dict(r, city=next(s["place"] for s in stations if s["id"] == r["city"]))
                                                for r in per_city]}}
    write(dict(base, places=[], parcial=True))
    img_dir = os.path.join(os.path.dirname(out_path), "barrios_radar")
    os.makedirs(img_dir, exist_ok=True)
    def one(st):
        res = map_place(ee, clf, st, polys_by[st["id"]], feats_for(final))
        png = res.pop("_png", None)
        if png and png.startswith(b"\x89PNG"):
            with open(os.path.join(img_dir, st["id"] + ".png"), "wb") as f:
                f.write(png)
            res["imagen"] = f"barrios_radar/{st['id']}.png"
        res.update(id=st["id"], place=st["place"], river=st["river"], entrenamiento=st in train,
                   fuente_renabap=sources[st["id"]])
        log(f"{st['place']}: {res.get('informal_ha')} ha, {res.get('pop_informal')} personas"
            + (f" · {res['error'][:120]}" if res.get("error") else ""))
        return res

    from concurrent.futures import ThreadPoolExecutor
    order = {st["id"]: i for i, st in enumerate(stations)}
    with ThreadPoolExecutor(max_workers=4) as pool:   # Earth Engine procesa varias localidades a la vez
        for res in pool.map(one, stations):
            places.append(res)
            places.sort(key=lambda p: order[p["id"]])
            write(dict(base, places=places, parcial=len(places) < len(stations)))
    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "year": YEAR,
        "model": {
            "method": __doc__.split("\n\n", 1)[1].strip(),
            "ciudades_entrenamiento": [st["place"] for st in train],
            "ciudades_externas": ext_cities,
            "puntos_por_clase_y_ciudad": POINTS_PER_CLASS,
            "evaluacion_por_ciudad": [dict(r, city=next(s["place"] for s in stations if s["id"] == r["city"]))
                                      for r in per_city],
            "promedio": summary,
            "modelo_final": final,
            "capas_mas_utiles": importance,
            "nota": ("Evaluado dejando afuera una ciudad por vez, con puntos balanceados entre barrio popular y "
                     "barrio común construido. No es la misma métrica del estudio de Nairobi, aunque mide lo mismo: "
                     "cuánto mejora al sumar el radar."),
        },
        "places": places,
        "sources": [RENABAP_CREDIT, "Copernicus Sentinel-1 GRD y Sentinel-2 L2A vía Google Earth Engine",
                    "Cloud Score+ (Google)", "OpenStreetMap (ODbL) · barrios populares de Nairobi", "Google Open Buildings temporal v1 · CC BY 4.0", "ESA WorldCover 2021 · CC BY 4.0", "WorldPop 2020 · CC BY 4.0",
                    "MERIT Hydro (Yamazaki et al., 2019)"],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("Promedio por ciudad dejada afuera:", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "barrios_radar.json"))
    except SystemExit:
        raise
    except Exception as exc:  # que el motivo quede visible como anotación
        import traceback
        log(f"Falló: {type(exc).__name__}: {str(exc)[:300]}", error=True)
        traceback.print_exc()
        raise SystemExit(1)
