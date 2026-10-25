"""Desmontes recientes por resta de NDVI (Sentinel-2) y evaluación de su gravedad.

Método (el mismo que se usó para ubicar la tala de un centro de datos junto al río Oulujoki, en Finlandia, sin
coordenadas previas): no se busca un sitio, se resta el verdor de dos ventanas comparables de toda la región y se
deja que los desmontes más grandes aparezcan solos.

  1. Dos ventanas de Sentinel-2 (nubes quitadas con Cloud Score+):
       · verano:   diciembre–marzo del último verano completo contra el verano anterior
       · reciente: los últimos 120 días contra los mismos días del año anterior
     Comparar la misma época del año evita confundir la seca del invierno con un desmonte.
  2. NDVI de cada ventana como percentil 75 de las pasadas sin nubes (robusto a sombras y nubes que se escapan).
  3. Candidato: píxel que antes era vegetación densa (NDVI ≥ 0,55), cayó al menos 0,25 y quedó por debajo de 0,45.
     Se descartan agua o inundación en la segunda ventana (MNDWI), cultivos y zonas construidas (ESA WorldCover):
     en el NEA una crecida baja el NDVI tanto como un desmonte.
  4. Los píxeles vecinos se unen en parches y se mide cada parche con tres umbrales (−0,25, −0,35, −0,45). Un
     desmonte no tiene un borde limpio: caminos, suelo pelado y pilas de rolos se leen distinto, así que el área se
     informa como rango y no como un número.
  5. Gravedad, con señales que se pueden revisar una por una: bosque en 2020 según el mapa de la UE (JRC, la
     referencia del EUDR), categoría de la Ley de Bosques si se cargó data/otbn.geojson, pendiente (erosión),
     cercanía a agua permanente (costas y sedimentos), tamaño, y si en el período hubo fuego (MODIS), que puede
     explicar la caída sin que haya desmonte.

Salida (rama datos, no publica la web): data/desmonte_ndvi_<ventana>.json y data/desmonte_ndvi/<ventana>_<id>_{a,d}.png
Requiere los secretos GOOGLE_CLOUD_PROJECT y GOOGLE_APPLICATION_CREDENTIALS_JSON (los mismos de Vercel).
"""
import concurrent.futures as cf
import hashlib
import json
import math
import os
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

VENTANA = os.environ.get("DESMONTE_VENTANA", "verano")   # verano | reciente
ANIO = os.environ.get("DESMONTE_ANIO", "")               # verano a analizar (año en que termina); vacío = el último
PROVINCIAS = [p.strip() for p in os.environ.get(
    "DESMONTE_PROVINCIAS",
    "Salta,Jujuy,Tucumán,Santiago del Estero,Chaco,Formosa,Santa Fe,Corrientes,Misiones,Entre Ríos").split(",") if p.strip()]
TILE_DEG = float(os.environ.get("DESMONTE_TILE", "0.5"))
SCALE = 20                    # m: banda roja/NIR llevadas a la grilla de 20 m de Sentinel-2
MIN_HA = float(os.environ.get("DESMONTE_MIN_HA", "10"))
MAX_PARCHES = int(os.environ.get("DESMONTE_MAX", "80"))
MAX_FOTOS = int(os.environ.get("DESMONTE_FOTOS", "24"))
WORKERS = int(os.environ.get("DESMONTE_WORKERS", "6"))
BUDGET_MIN = float(os.environ.get("DESMONTE_MINUTOS", "280"))   # corta a tiempo para guardar lo calculado

NDVI_ANTES_MIN = 0.55          # antes había vegetación densa
NDVI_DESPUES_MAX = 0.45        # después quedó poco verde
UMBRALES = (-0.25, -0.35, -0.45)   # amplio, medio, estricto
MIN_PASADAS = 2                # pasadas sin nubes por ventana para confiar en el píxel

OTBN_FILE = os.path.join(ROOT, "data", "otbn.geojson")
OUT_JSON = os.path.join(ROOT, "data", f"desmonte_ndvi_{VENTANA}.json")
OUT_DIR = os.path.join(ROOT, "data", "desmonte_ndvi")

CREDITOS = [
    "Copernicus Sentinel-2 (ESA), nivel 2A armonizado · Cloud Score+ (Google)",
    "Mapa de bosques 2020 de la UE, JRC GFC2020 v2 (referencia del EUDR)",
    "ESA WorldCover 2021 · NASADEM · JRC Global Surface Water · MODIS MCD64A1 (área quemada)",
    "Límites: FAO GAUL 2015",
]


# ───────────────────────────── partes puras (se prueban sin red) ─────────────────────────────

def norm(s):
    """Minúsculas y sin acentos, para comparar nombres de provincias."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def ventanas(tipo, hoy=None, anio=None):
    """Dos ventanas comparables (antes, después), cada una como (inicio, fin) en ISO, fin excluido."""
    hoy = hoy or date.today()
    if tipo == "reciente":
        fin = hoy - timedelta(days=5)              # Sentinel-2 L2A tarda unos días en publicarse
        ini = fin - timedelta(days=120)
        return ((ini - timedelta(days=365)).isoformat(), (fin - timedelta(days=365)).isoformat()), (ini.isoformat(), fin.isoformat())
    # verano austral: 1 de diciembre al 1 de abril. Se usa el último terminado.
    y = int(anio) if anio else (hoy.year if hoy.month >= 4 else hoy.year - 1)
    return (f"{y - 2}-12-01", f"{y - 1}-04-01"), (f"{y - 1}-12-01", f"{y}-04-01")


def rotulo_ventana(v):
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    a = date.fromisoformat(v[0]); b = date.fromisoformat(v[1]) - timedelta(days=1)
    return f"{meses[a.month - 1]} {a.year} – {meses[b.month - 1]} {b.year}"


def grilla(bboxes, paso=TILE_DEG):
    """Celdas de `paso` grados que tocan alguna de las cajas (oeste, sur, este, norte). Sin repetir."""
    celdas = set()
    for w, s, e, n in bboxes:
        x0, y0 = math.floor(w / paso), math.floor(s / paso)
        x1, y1 = math.ceil(e / paso), math.ceil(n / paso)
        for i in range(x0, x1):
            for j in range(y0, y1):
                celdas.add((round(i * paso, 6), round(j * paso, 6), round((i + 1) * paso, 6), round((j + 1) * paso, 6)))
    return sorted(celdas)


def pid(lat, lon, ventana):
    return hashlib.sha1(f"{ventana}:{lat:.4f}:{lon:.4f}".encode()).hexdigest()[:8]


def categoria_otbn(valor):
    """Normaliza la categoría del Ordenamiento Territorial de Bosques Nativos (Ley 26.331)."""
    v = norm(valor)
    if not v:
        return None
    if v in ("i", "1", "rojo", "roja", "categoria i") or "roj" in v:
        return "rojo"
    if v in ("ii", "2", "amarillo", "amarilla", "categoria ii") or "amarill" in v:
        return "amarillo"
    if v in ("iii", "3", "verde", "categoria iii") or "verde" in v:
        return "verde"
    return None


def evaluar(p):
    """Nivel de gravedad y señales legibles a partir de las mediciones del parche.

    p: area_ha, frac_medio, frac_estricto, bosque_2020, pendiente, ribera, fuego, otbn (rojo/amarillo/verde/None).
    Devuelve (nivel, tipo, señales): nivel alto/medio/bajo; tipo «desmonte probable» o «posible incendio».
    """
    puntos, senales = 0, []
    area = p.get("area_ha") or 0
    fuego = p.get("fuego") or 0
    tipo = "desmonte probable"
    if fuego >= 0.3:
        tipo = "posible incendio"
        senales.append(f"El {fuego:.0%} del parche figura quemado en el período (MODIS): la caída puede ser fuego y no desmonte.")

    otbn = p.get("otbn")
    if otbn == "rojo":
        puntos += 3
        senales.append("Zona roja de la Ley de Bosques: ahí no se puede desmontar ni aprovechar.")
    elif otbn == "amarillo":
        puntos += 2
        senales.append("Zona amarilla de la Ley de Bosques: se permite uso sostenible, no cambio de uso del suelo.")
    elif otbn == "verde":
        senales.append("Zona verde de la Ley de Bosques: el desmonte puede estar autorizado; hay que pedir el permiso.")

    bosque = p.get("bosque_2020") or 0
    if bosque >= 0.5:
        puntos += 2
        senales.append(f"El {bosque:.0%} era bosque en 2020 según el mapa de la UE: lo que salga de ahí no se puede vender a Europa (EUDR).")
    elif bosque >= 0.2:
        puntos += 1
        senales.append(f"El {bosque:.0%} era bosque en 2020 según el mapa de la UE.")

    if area >= 500:
        puntos += 2
        senales.append(f"Muy grande: {area:,.0f} ha (unas {area / 0.714:,.0f} canchas de fútbol).".replace(",", "."))
    elif area >= 100:
        puntos += 1
        senales.append(f"Grande: {area:,.0f} ha.".replace(",", "."))

    if (p.get("pendiente") or 0) >= 5:
        puntos += 1
        senales.append(f"Pendiente media de {p['pendiente']:.0f}°: sin cobertura, el suelo se lava con las lluvias.")
    if (p.get("ribera") or 0) >= 0.05:
        puntos += 1
        senales.append("Llega a menos de 100 m de agua permanente: erosión de costas y sedimentos al río.")

    if (p.get("frac_estricto") or 0) >= 0.5:
        senales.append("La mitad o más del parche perdió casi todo el verde: corte total, no raleo.")
    elif (p.get("frac_medio") or 0) < 0.3:
        senales.append("Caída moderada en casi todo el parche: puede ser raleo, sequía fuerte o pastura degradada.")

    nivel = "alto" if puntos >= 4 else "medio" if puntos >= 2 else "bajo"
    if tipo == "posible incendio" and nivel == "alto":
        nivel = "medio"
    return nivel, tipo, senales


def armar_parche(props, geom, ventana, lugar=None, otbn=None):
    """Convierte lo que devuelve Earth Engine en el registro que lee la web."""
    lat, lon = props["lat"], props["lon"]
    area = props["area_ha"]
    p = {
        "id": pid(lat, lon, ventana),
        "lat": round(lat, 5), "lon": round(lon, 5),
        "provincia": (lugar or {}).get("provincia"), "departamento": (lugar or {}).get("departamento"),
        "area_ha": {"amplio": round(area, 1),
                    "medio": round(area * (props.get("frac_medio") or 0), 1),
                    "estricto": round(area * (props.get("frac_estricto") or 0), 1)},
        "ndvi_antes": round(props.get("ndvi_antes") or 0, 2), "ndvi_despues": round(props.get("ndvi_despues") or 0, 2),
        "dndvi": round(props.get("dndvi") or 0, 2),
        "bosque_2020": round(props.get("bosque_2020") or 0, 2), "pendiente": round(props.get("pendiente") or 0, 1),
        "ribera": round(props.get("ribera") or 0, 2), "fuego": round(props.get("fuego") or 0, 2),
        "otbn": otbn,
        "geom": redondear(geom),
    }
    nivel, tipo, senales = evaluar({**props, "otbn": otbn})
    p.update(nivel=nivel, tipo=tipo, senales=senales)
    return p


def redondear(geom, dec=5):
    if not geom:
        return None

    def r(c):
        return [r(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], dec), round(c[1], dec)]
    return {"type": geom["type"], "coordinates": r(geom["coordinates"])}


MEDIAS = ("ndvi_antes", "ndvi_despues", "dndvi", "frac_medio", "frac_estricto", "bosque_2020", "pendiente", "ribera", "fuego")


def unir_bordes(feats, tol=0.0002):
    """Une parches que se tocan (partidos por el borde de las celdas). Promedios ponderados por superficie."""
    if len(feats) < 2:
        return feats
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    geoms = [shape(f["geometry"]).buffer(0) for f in feats]
    tree = STRtree(geoms)
    padre = list(range(len(feats)))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i
    for i, g in enumerate(geoms):
        for j in tree.query(g.buffer(tol)):
            j = int(j)
            if j > i and geoms[j].distance(g) <= tol:
                padre[raiz(j)] = raiz(i)
    grupos = {}
    for i in range(len(feats)):
        grupos.setdefault(raiz(i), []).append(i)
    out = []
    for idx in grupos.values():
        if len(idx) == 1:
            out.append(feats[idx[0]])
            continue
        partes = [feats[i]["properties"] for i in idx]
        area = sum(p["area_ha"] for p in partes)
        props = {k: sum((p.get(k) or 0) * p["area_ha"] for p in partes) / area for k in MEDIAS}
        g = unary_union([geoms[i].buffer(tol) for i in idx]).buffer(-tol)
        c = g.centroid
        props.update(area_ha=area, lat=c.y, lon=c.x)
        out.append({"type": "Feature", "geometry": mapping(g), "properties": props})
    return out


def resumen(parches):
    """Totales por provincia y por nivel, para la cabecera del módulo."""
    prov, niveles = {}, {"alto": 0, "medio": 0, "bajo": 0}
    for p in parches:
        k = p.get("provincia") or "Sin dato"
        d = prov.setdefault(k, {"parches": 0, "ha": 0.0})
        d["parches"] += 1
        d["ha"] = round(d["ha"] + p["area_ha"]["amplio"], 1)
        niveles[p["nivel"]] += 1
    return {"provincias": dict(sorted(prov.items(), key=lambda kv: -kv[1]["ha"])), "niveles": niveles,
            "ha_total": {k: round(sum(p["area_ha"][k] for p in parches), 1) for k in ("amplio", "medio", "estricto")}}


# ───────────────────────────── Ley de Bosques (archivo opcional) ─────────────────────────────

_OTBN = None


def otbn_en(lat, lon):
    """Categoría OTBN en el punto, si se cargó data/otbn.geojson (propiedad «categoria», «cat» o «CATEGORIA»)."""
    global _OTBN
    if _OTBN is None:
        _OTBN = []
        if os.path.exists(OTBN_FILE):
            try:
                from shapely.geometry import shape
                from shapely.strtree import STRtree
                feats = json.load(open(OTBN_FILE, encoding="utf-8")).get("features") or []
                geoms, cats = [], []
                for f in feats:
                    props = f.get("properties") or {}
                    cat = categoria_otbn(props.get("categoria") or props.get("cat") or props.get("CATEGORIA") or props.get("Categoria"))
                    if f.get("geometry") and cat:
                        geoms.append(shape(f["geometry"])); cats.append(cat)
                _OTBN = (STRtree(geoms), geoms, cats) if geoms else []
            except Exception as e:  # el archivo es opcional: un error no frena el resto
                print(f"OTBN: no se pudo leer {OTBN_FILE} ({e})")
                _OTBN = []
    if not _OTBN:
        return None
    from shapely.geometry import Point
    tree, geoms, cats = _OTBN
    pt = Point(lon, lat)
    for i in tree.query(pt):
        if geoms[i].contains(pt):
            return cats[i]
    return None


# ───────────────────────────── Earth Engine ─────────────────────────────

def ee_init():
    import ee
    info = json.loads(os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
    creds = ee.ServiceAccountCredentials(info["client_email"], key_data=json.dumps(info))
    ee.Initialize(creds, project=os.environ["GOOGLE_CLOUD_PROJECT"])
    return ee


def s2(ee, region, v):
    cs = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    return (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(region).filterDate(v[0], v[1])
            .linkCollection(cs, ["cs"]).map(lambda i: i.updateMask(i.select("cs").gte(0.6))))


def ventana_img(ee, region, v):
    col = s2(ee, region, v)
    ndvi = col.map(lambda i: i.normalizedDifference(["B8", "B4"]).rename("NDVI"))
    mndwi = col.map(lambda i: i.normalizedDifference(["B3", "B11"]).rename("MNDWI")).median()
    return ndvi.reduce(ee.Reducer.percentile([75])).rename("NDVI"), mndwi, ndvi.count().rename("n")


def bosque_2020(ee):
    """Mapa de bosques 2020 del JRC (EUDR). Si el catálogo no lo tuviera, Hansen: copa > 30 % y sin pérdida antes de 2021."""
    try:
        img = ee.ImageCollection("JRC/GFC2020/V2").mosaic().select(0).eq(1).unmask(0)
        img.bandNames().getInfo()
        return img, "JRC GFC2020 v2"
    except Exception:
        h = ee.Image("UMD/hansen/global_forest_change_2024_v1_12")
        loss = h.select("lossyear")
        return h.select("treecover2000").gt(30).And(loss.eq(0).Or(loss.gt(20))).unmask(0), "Hansen/UMD (respaldo)"


def construir(ee, antes, despues, mascara_prov):
    """Imagen de candidatos y pila de mediciones (todas como promedio dentro del parche)."""
    region_glob = ee.Geometry.Rectangle([-75, -56, -53, -21])
    na, wa, ca = ventana_img(ee, region_glob, antes)
    nd, wd, cd = ventana_img(ee, region_glob, despues)
    d = nd.subtract(na).rename("dndvi")
    wc = ee.ImageCollection("ESA/WorldCover/v200").first()
    excluir = wc.eq(40).Or(wc.eq(50)).Or(wc.eq(80))           # cultivo, construido, agua
    valido = ca.gte(MIN_PASADAS).And(cd.gte(MIN_PASADAS)).And(wd.lt(0)).And(excluir.Not())
    cand = (na.gte(NDVI_ANTES_MIN).And(nd.lte(NDVI_DESPUES_MAX)).And(d.lte(UMBRALES[0]))
            .And(valido).And(mascara_prov).selfMask().rename("cand"))

    bosque, fuente_bosque = bosque_2020(ee)
    slope = ee.Terrain.slope(ee.Image("NASA/NASADEM_HGT/001").select("elevation")).rename("pendiente")
    agua = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gte(50).unmask(0)
    ribera = agua.focalMax(100, "circle", "meters").rename("ribera")
    quemado = (ee.ImageCollection("MODIS/061/MCD64A1").filterDate(antes[0], despues[1]).select("BurnDate")
               .max().gt(0).unmask(0).rename("fuego"))
    medidas = ee.Image.cat([
        na.rename("ndvi_antes"), nd.rename("ndvi_despues"), d,
        d.lte(UMBRALES[1]).rename("frac_medio"), d.lte(UMBRALES[2]).rename("frac_estricto"),
        bosque.rename("bosque_2020"), slope, ribera, quemado,
    ])
    return cand, medidas, fuente_bosque


def parches_de_celda(ee, cand, medidas, celda, profundidad=0):
    """Parches de una celda con sus mediciones. Si Earth Engine se queda sin memoria, parte la celda en cuatro."""
    w, s, e, n = celda
    geom = ee.Geometry.Rectangle([w, s, e, n], None, False)
    try:
        vec = cand.reduceToVectors(geometry=geom, scale=SCALE, geometryType="polygon", eightConnected=True,
                                   maxPixels=1e10, tileScale=4, labelProperty="cand")
        vec = (vec.map(lambda f: f.set("area_ha", f.geometry().area(5).divide(1e4)))
               .filter(ee.Filter.gte("area_ha", MIN_HA)))
        con = medidas.reduceRegions(collection=vec, reducer=ee.Reducer.mean(), scale=SCALE, tileScale=4)

        def plano(f):
            c = f.geometry().centroid(5).coordinates()
            return (ee.Feature(f.geometry().simplify(40), f.toDictionary())
                    .set("lon", c.get(0), "lat", c.get(1)))
        return con.map(plano).getInfo().get("features") or []
    except Exception as ex:
        msg = str(ex)
        if profundidad < 2 and any(k in msg for k in ("memory", "Computation timed out", "Too many", "aggregation")):
            mx, my = (w + e) / 2, (s + n) / 2
            out = []
            for sub in ((w, s, mx, my), (mx, s, e, my), (w, my, mx, n), (mx, my, e, n)):
                out += parches_de_celda(ee, cand, medidas, sub, profundidad + 1)
            return out
        raise


def provincias(ee):
    """Geometría de las provincias pedidas (FAO GAUL) y sus cajas, comparando nombres sin acentos."""
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq("ADM0_NAME", "Argentina"))
    nombres = gaul.aggregate_array("ADM1_NAME").getInfo()
    pedidas = {norm(p) for p in PROVINCIAS}
    elegidas = [nm for nm in nombres if norm(nm) in pedidas]
    faltan = pedidas - {norm(nm) for nm in elegidas}
    if faltan:
        print(f"Provincias sin coincidencia en GAUL: {', '.join(sorted(faltan))}")
    fc = gaul.filter(ee.Filter.inList("ADM1_NAME", elegidas))
    cajas = []
    for f in fc.map(lambda f: ee.Feature(f.geometry().bounds(1000))).getInfo()["features"]:
        xs = [c[0] for c in f["geometry"]["coordinates"][0]]; ys = [c[1] for c in f["geometry"]["coordinates"][0]]
        cajas.append((min(xs), min(ys), max(xs), max(ys)))
    mascara = ee.Image(0).paint(fc, 1).eq(1)
    return mascara, cajas, elegidas


def lugares(ee, puntos):
    """Provincia y departamento de cada punto (FAO GAUL nivel 2), en una sola consulta."""
    if not puntos:
        return []
    g2 = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq("ADM0_NAME", "Argentina"))
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([lon, lat]), {"i": i}) for i, (lat, lon) in enumerate(puntos)])

    def uno(f):
        m = g2.filterBounds(f.geometry()).first()
        return f.set("provincia", ee.Algorithms.If(m, ee.Feature(m).get("ADM1_NAME"), None),
                     "departamento", ee.Algorithms.If(m, ee.Feature(m).get("ADM2_NAME"), None))
    res = {f["properties"]["i"]: f["properties"] for f in fc.map(uno).getInfo()["features"]}
    return [{"provincia": res.get(i, {}).get("provincia"), "departamento": res.get(i, {}).get("departamento")}
            for i in range(len(puntos))]


def foto(ee, p, v, ruta):
    """Color natural del parche en una ventana, con 30 % de margen, 320 px."""
    import requests
    xs = [c[0] for c in _coords(p["geom"])]; ys = [c[1] for c in _coords(p["geom"])]
    w, e, s, n = min(xs), max(xs), min(ys), max(ys)
    mx, my = max((e - w) * 0.3, 0.004), max((n - s) * 0.3, 0.004)
    reg = ee.Geometry.Rectangle([w - mx, s - my, e + mx, n + my], None, False)
    img = s2(ee, reg, v).select(["B4", "B3", "B2"]).median().divide(10000)
    contorno = ee.Image().byte().paint(ee.Geometry(p["geom"]), 1, 2).visualize(palette=["ffd400"])
    vis = img.visualize(min=0, max=0.25, gamma=1.3).blend(contorno)
    url = vis.getThumbURL({"region": reg, "dimensions": 320, "format": "png"})
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    open(ruta, "wb").write(r.content)


def _coords(g):
    c = g["coordinates"]
    if g["type"] == "Polygon":
        return c[0]
    if g["type"] == "MultiPolygon":
        return [pt for poly in c for pt in poly[0]]
    return []


def main():
    t0 = time.time()
    antes, despues = ventanas(VENTANA, anio=ANIO)
    print(f"Ventana {VENTANA}: antes {antes[0]}→{antes[1]} · después {despues[0]}→{despues[1]}")
    ee = ee_init()
    mascara, cajas, elegidas = provincias(ee)
    celdas = grilla(cajas)
    print(f"{len(elegidas)} provincias · {len(celdas)} celdas de {TILE_DEG}°")
    cand, medidas, fuente_bosque = construir(ee, antes, despues, mascara)

    crudos, fallidas = [], []
    pool = cf.ThreadPoolExecutor(max_workers=WORKERS)
    futs = {pool.submit(parches_de_celda, ee, cand, medidas, c): c for c in celdas}
    hechas = 0
    for fut in cf.as_completed(futs):
        c = futs[fut]
        hechas += 1
        try:
            feats = fut.result()
            crudos += feats
            if feats:
                print(f"[{hechas}/{len(celdas)}] {c}: {len(feats)} parches")
        except Exception as ex:
            fallidas.append(c)
            print(f"[{hechas}/{len(celdas)}] {c}: error {str(ex)[:160]}")
        if (time.time() - t0) / 60 > BUDGET_MIN:
            print("Se acabó el tiempo: se guarda lo calculado.")
            break
    pool.shutdown(wait=False, cancel_futures=True)
    sin_tiempo = len(celdas) - hechas

    # Un desmonte que cruza el borde de dos celdas llega partido: se unen las partes que se tocan
    crudos = unir_bordes(crudos)
    crudos.sort(key=lambda f: -f["properties"]["area_ha"])
    elegidos = crudos[:MAX_PARCHES]
    ubic = lugares(ee, [(f["properties"]["lat"], f["properties"]["lon"]) for f in elegidos])
    parches = [armar_parche(f["properties"], f.get("geometry"), VENTANA, lugar=u,
                            otbn=otbn_en(f["properties"]["lat"], f["properties"]["lon"]))
               for f, u in zip(elegidos, ubic)]

    fotos = 0
    for p in parches[:MAX_FOTOS]:
        try:
            foto(ee, p, antes, os.path.join(OUT_DIR, f"{VENTANA}_{p['id']}_a.png"))
            foto(ee, p, despues, os.path.join(OUT_DIR, f"{VENTANA}_{p['id']}_d.png"))
            p["fotos"] = True; fotos += 1
        except Exception as ex:
            print(f"foto {p['id']}: {str(ex)[:120]}")

    salida = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ventana": VENTANA,
        "antes": {"desde": antes[0], "hasta": antes[1], "rotulo": rotulo_ventana(antes)},
        "despues": {"desde": despues[0], "hasta": despues[1], "rotulo": rotulo_ventana(despues)},
        "provincias": elegidas,
        "metodo": {"ndvi_antes_min": NDVI_ANTES_MIN, "ndvi_despues_max": NDVI_DESPUES_MAX, "umbrales": list(UMBRALES),
                   "escala_m": SCALE, "min_ha": MIN_HA, "bosque_2020": fuente_bosque,
                   "otbn": os.path.exists(OTBN_FILE)},
        "cobertura": {"celdas": len(celdas), "fallidas": len(fallidas), "sin_tiempo": sin_tiempo,
                      "parches_detectados": len(crudos)},
        "resumen": resumen(parches),
        "parches": parches,
        "creditos": CREDITOS,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(salida, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"Listo en {(time.time() - t0) / 60:.0f} min: {len(crudos)} parches ≥ {MIN_HA:.0f} ha, {len(parches)} guardados, "
          f"{fotos} con fotos, {len(fallidas)} celdas con error, {sin_tiempo} sin tiempo.")
    return 0 if parches or not fallidas else 1


if __name__ == "__main__":
    sys.exit(main())
