"""Barrios populares por radar en las localidades ribereñas de DOTS (Sentinel-1 + Sentinel-2 + RENABAP).

Idea (Sapienza / Pavía): las imágenes en color confunden un barrio popular con un barrio denso común; el radar
Sentinel-1 responde a la forma y al desorden de las construcciones, y casi no cambia entre estaciones.

Qué hace, en GitHub Actions y con Google Earth Engine:
  1. Baja los polígonos del Registro Nacional de Barrios Populares (RENABAP) alrededor de cada localidad.
  2. Arma, para cada píxel construido (ESA WorldCover), tres escalones de radar —brillo (VV, VH, VH−VV),
     textura (GLCM: contraste, varianza, entropía, homogeneidad) e índice de dispersión (coeficiente de variación
     local y temporal, y diferencia entre estación seca y húmeda)— y las bandas ópticas de Sentinel-2.
  3. Etiquetas: dentro de un polígono RENABAP = barrio popular; construido a más de 60 m de cualquiera = barrio común.
  4. Entrena dos bosques aleatorios (solo óptico / óptico + radar) y los evalúa dejando afuera una ciudad por vez:
     así se mide cómo anda en una ciudad que el modelo nunca vio.
  5. Aplica el modelo óptico + radar a las 34 localidades (también Paraguay y Uruguay, donde no hay RENABAP),
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
SEED = 7

RENABAP_WFS = os.environ.get("RENABAP_WFS", "https://geoportal.obraspublicas.gob.ar/geoserver/ows")
RENABAP_LAYER = os.environ.get("RENABAP_LAYER", "geonode:renabap2020_smz")
RENABAP_FILE = os.path.join(ROOT, "data", "renabap.geojson")      # alternativa: archivo descargado a mano
RENABAP_CREDIT = ("Registro Nacional de Barrios Populares (RENABAP), Ministerio de Desarrollo Social de la Nación, "
                  "vía geoportal del Ministerio de Obras Públicas")

RADAR = ["VV", "VH", "VHVV", "VV_dry", "VV_wet", "VV_season", "VV_tstd",
         "VVt_contrast", "VVt_var", "VVt_ent", "VVt_idm", "VV_cv3", "VV_cv5", "VV_lmean"]
OPTICAL = ["B2", "B3", "B4", "B8", "B11", "B12", "NDVI", "NDBI"]
SETS = {"optico": OPTICAL, "optico_radar": OPTICAL + RADAR}


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


def renabap(bbox):
    """Barrios RENABAP dentro del recuadro: primero el WFS oficial, si no un archivo local."""
    global _RENABAP_ALL
    params = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": RENABAP_LAYER,
              "outputFormat": "application/json", "srsName": "EPSG:4326",
              "bbox": "%f,%f,%f,%f,EPSG:4326" % bbox}
    for attempt in range(3):
        try:
            r = requests.get(RENABAP_WFS, params=params, timeout=90)
            if r.ok and r.headers.get("content-type", "").startswith(("application/json", "application/geo+json")):
                return clean_polygons(r.json(), bbox), "wfs"
        except (requests.RequestException, ValueError):
            pass
        time.sleep(3 * (attempt + 1))
    if _RENABAP_ALL is None and os.path.exists(RENABAP_FILE):
        with open(RENABAP_FILE, encoding="utf-8") as f:
            _RENABAP_ALL = json.load(f)
    if _RENABAP_ALL:
        return clean_polygons(_RENABAP_ALL, bbox), "archivo"
    return [], "sin fuente"


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
    s1 = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(region).filterDate(start, end)
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
          .select(["VV", "VH"]))
    med = s1.median()
    vv, vh = med.select("VV"), med.select("VH")
    dry = s1.filter(ee.Filter.calendarRange(6, 9, "month")).select("VV").median().rename("VV_dry")
    wet = s1.filter(ee.Filter.calendarRange(12, 3, "month")).select("VV").median().rename("VV_wet")
    tstd = s1.select("VV").reduce(ee.Reducer.stdDev()).rename("VV_tstd")
    # textura: GLCM sobre VV en dB llevado a enteros
    q = vv.add(30).multiply(4).clamp(0, 160).toInt().rename("VVt")
    glcm = q.glcmTexture(size=2).select(["VVt_contrast", "VVt_var", "VVt_ent", "VVt_idm"])
    # índice de dispersión: retornos débiles y desparejos de construcciones chicas y desordenadas
    lin = ee.Image(10).pow(vv.divide(10))
    k3, k5 = ee.Kernel.square(1), ee.Kernel.square(2)
    m3 = lin.reduceNeighborhood(ee.Reducer.mean(), k3)
    cv3 = lin.reduceNeighborhood(ee.Reducer.stdDev(), k3).divide(m3).rename("VV_cv3")
    m5 = lin.reduceNeighborhood(ee.Reducer.mean(), k5)
    cv5 = lin.reduceNeighborhood(ee.Reducer.stdDev(), k5).divide(m5).rename("VV_cv5")
    radar = ee.Image.cat([vv.rename("VV"), vh.rename("VH"), vh.subtract(vv).rename("VHVV"), dry, wet,
                          wet.subtract(dry).rename("VV_season"), tstd, glcm, cv3, cv5,
                          m5.log10().multiply(10).rename("VV_lmean")])
    cs = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(region).filterDate(start, end)
          .linkCollection(cs, ["cs"]).map(lambda i: i.updateMask(i.select("cs").gte(0.6)))
          .select(["B2", "B3", "B4", "B8", "B11", "B12"]).median().divide(10000))
    ndvi = s2.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndbi = s2.normalizedDifference(["B11", "B8"]).rename("NDBI")
    built = ee.ImageCollection("ESA/WorldCover/v200").first().eq(50).rename("built")
    return ee.Image.cat([s2, ndvi, ndbi, radar]).updateMask(built), built


def labels(ee, polys, built):
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry(p)) for p in polys])
    inside = ee.Image(0).paint(fc, 1)
    near = fc.distance(NEG_BUFFER_M * 2).lte(NEG_BUFFER_M).unmask(0)
    pos = built.And(inside.eq(1))
    neg = built.And(inside.eq(0)).And(near.eq(0))
    return ee.Image(0).where(neg, 0).where(pos, 1).updateMask(pos.Or(neg)).rename("label").toInt(), fc


def sample_city(ee, lat, lon, polys):
    region = ee.Geometry.Point([lon, lat]).buffer(RADIUS_M)
    img, built = stack(ee, region)
    lab, _ = labels(ee, polys, built)
    pts = img.addBands(lab).stratifiedSample(numPoints=POINTS_PER_CLASS, classBand="label", region=region, scale=10,
                                             seed=SEED, classValues=[0, 1],
                                             classPoints=[POINTS_PER_CLASS, POINTS_PER_CLASS],
                                             dropNulls=True, tileScale=8, geometries=False)
    return pts


# ───────────────────────────── evaluación ─────────────────────────────

def rows_to_xy(rows, feats):
    X, y = [], []
    for r in rows:
        if all(isinstance(r.get(f), (int, float)) for f in feats) and r.get("label") in (0, 1):
            X.append([r[f] for f in feats])
            y.append(int(r["label"]))
    return X, y


def leave_one_city_out(samples):
    """Entrena con todas las ciudades menos una y mide en la que quedó afuera."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score
    cities = [c for c, rows in samples.items() if len({r.get("label") for r in rows}) == 2]
    per_city = []
    for test in cities:
        row = {"city": test}
        for name, feats in SETS.items():
            Xtr, ytr = [], []
            for c in cities:
                if c != test:
                    X, y = rows_to_xy(samples[c], feats)
                    Xtr += X; ytr += y
            Xte, yte = rows_to_xy(samples[test], feats)
            if len(set(ytr)) < 2 or len(set(yte)) < 2:
                continue
            rf = RandomForestClassifier(n_estimators=200, min_samples_leaf=2, n_jobs=-1, random_state=SEED)
            rf.fit(Xtr, ytr)
            pred = rf.predict(Xte)
            row[name] = {"f1_barrio": round(f1_score(yte, pred, pos_label=1), 3),
                         "exactitud": round(accuracy_score(yte, pred), 3), "puntos": len(yte)}
        if len(row) > 1:
            per_city.append(row)
    def mean(name, key):
        vals = [r[name][key] for r in per_city if name in r]
        return round(sum(vals) / len(vals), 3) if vals else None
    summary = {name: {"f1_barrio": mean(name, "f1_barrio"), "exactitud": mean(name, "exactitud")} for name in SETS}
    importance = None
    allX, ally = [], []
    for c in cities:
        X, y = rows_to_xy(samples[c], SETS["optico_radar"])
        allX += X; ally += y
    if len(set(ally)) == 2:
        rf = RandomForestClassifier(n_estimators=200, min_samples_leaf=2, n_jobs=-1, random_state=SEED).fit(allX, ally)
        pairs = sorted(zip(SETS["optico_radar"], rf.feature_importances_), key=lambda p: -p[1])
        importance = [{"capa": k, "peso": round(float(v), 3)} for k, v in pairs[:10]]
    return per_city, summary, importance


# ───────────────────────────── mapeo y exposición ─────────────────────────────

def map_place(ee, clf, st, polys):
    region = ee.Geometry.Point([st["lon"], st["lat"]]).buffer(RADIUS_M)
    img, built = stack(ee, region)
    informal = img.select(SETS["optico_radar"]).classify(clf).eq(1).And(built).selfMask().rename("informal")
    area = ee.Image.pixelArea()
    pop = (ee.ImageCollection("WorldPop/GP/100m/pop").filter(ee.Filter.eq("year", 2020)).mosaic()
           .select("population"))
    popd = pop.divide(ee.Image.pixelArea().reproject(pop.projection()))          # personas por m²
    hand = ee.Image("MERIT/Hydro/v1_0_1").select("hnd")
    bands = [area.updateMask(informal).rename("informal_m2"),
             popd.multiply(area).updateMask(informal).rename("pop_informal")]
    for t in HAND_BANDS:
        bands.append(popd.multiply(area).updateMask(informal).updateMask(hand.lte(t)).rename(f"pop_informal_le{t}"))
    if polys:
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry(p)) for p in polys])
        ren = ee.Image(0).paint(fc, 1).eq(1)
        near = fc.distance(NEG_BUFFER_M * 2).lte(NEG_BUFFER_M).unmask(0)
        bands += [area.updateMask(informal).updateMask(ren).rename("in_renabap_m2"),
                  area.updateMask(informal).updateMask(near.eq(0)).rename("outside_renabap_m2"),
                  area.updateMask(built).updateMask(ren).rename("renabap_built_m2"),
                  area.updateMask(built).updateMask(ren).updateMask(informal).rename("renabap_detected_m2")]
    stats, err = None, "sin respuesta"
    for scale in (10, 20):
        try:
            stats = ee.Image.cat(bands).reduceRegion(ee.Reducer.sum(), region, scale=scale, maxPixels=1e10,
                                                      tileScale=8).getInfo()
            break
        except Exception as exc:  # cómputo muy grande: se reintenta a 20 m
            err = str(exc)[:200]
    if stats is None:
        return {"error": err}
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
        raise SystemExit("Muy pocas localidades con barrios RENABAP: revisá la fuente (RENABAP_WFS o data/renabap.geojson).")
    fcs = []
    for st in train:
        fc = sample_city(ee, st["lat"], st["lon"], polys_by[st["id"]])
        fcs.append(fc)
        try:
            samples[st["id"]] = [f["properties"] for f in fc.getInfo()["features"]]
            print(f"  muestras {st['place']}: {len(samples[st['id']])}", flush=True)
        except Exception as exc:
            print(f"  sin muestras en {st['place']}: {str(exc)[:160]}", flush=True)
    per_city, summary, importance = leave_one_city_out(samples)
    training = ee.FeatureCollection(fcs).flatten()
    clf = ee.Classifier.smileRandomForest(numberOfTrees=200, minLeafPopulation=2, seed=SEED).train(
        training, "label", SETS["optico_radar"])
    places = []
    img_dir = os.path.join(os.path.dirname(out_path), "barrios_radar")
    os.makedirs(img_dir, exist_ok=True)
    for st in stations:
        res = map_place(ee, clf, st, polys_by[st["id"]])
        png = res.pop("_png", None)
        if png and png.startswith(b"\x89PNG"):
            with open(os.path.join(img_dir, st["id"] + ".png"), "wb") as f:
                f.write(png)
            res["imagen"] = f"barrios_radar/{st['id']}.png"
        res.update(id=st["id"], place=st["place"], river=st["river"], entrenamiento=st in train,
                   fuente_renabap=sources[st["id"]])
        places.append(res)
        print(f"{st['place']}: {res.get('informal_ha')} ha, {res.get('pop_informal')} personas", flush=True)
    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "year": YEAR,
        "model": {
            "method": __doc__.split("\n\n", 1)[1].strip(),
            "ciudades_entrenamiento": [st["place"] for st in train],
            "puntos_por_clase_y_ciudad": POINTS_PER_CLASS,
            "evaluacion_por_ciudad": [dict(r, city=next(s["place"] for s in stations if s["id"] == r["city"]))
                                      for r in per_city],
            "promedio": summary,
            "capas_mas_utiles": importance,
            "nota": ("Evaluado dejando afuera una ciudad por vez, con puntos balanceados entre barrio popular y "
                     "barrio común construido. No es la misma métrica del estudio de Nairobi, aunque mide lo mismo: "
                     "cuánto mejora al sumar el radar."),
        },
        "places": places,
        "sources": [RENABAP_CREDIT, "Copernicus Sentinel-1 GRD y Sentinel-2 L2A vía Google Earth Engine",
                    "Cloud Score+ (Google)", "ESA WorldCover 2021 · CC BY 4.0", "WorldPop 2020 · CC BY 4.0",
                    "MERIT Hydro (Yamazaki et al., 2019)"],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("Promedio por ciudad dejada afuera:", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "barrios_radar.json"))
