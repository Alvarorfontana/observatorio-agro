"""Anegamientos en Corrientes: manchas de agua nueva con radar Sentinel-1 (tarea semanal).

Corre en GitHub Actions, nunca en el sitio. Gratis: Sentinel-1 RTC de Microsoft Planetary
Computer (sin clave). Lee solo el recuadro de cada zona, no la escena entera.

Para cada zona:
  1. Busca las pasadas de la misma órbita relativa del último año.
  2. Limpia el speckle de cada una con filtro Lee (20 m).
  3. Arma el «fondo» de cada píxel con recorte sigma sobre las pasadas anteriores
     (dejando afuera los últimos 30 días).
  4. Compara la última pasada con su fondo y cataloga las manchas de agua nueva.
  5. Revisa la serie de % de agua con Hampel para marcar fechas raras.

Salida liviana (rama datos):  data/anegamientos.json  ·  data/anegamientos.geojson
Variables: ANEG_ZONAS="Goya,Esquina" para limitar zonas · ANEG_DIAS (400) · ANEG_FONDO_MAX (15)
Todo es orientativo: sin validar en terreno.
"""
import json
import os
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import manchas_agua as ma  # noqa: E402

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
RES_M = 20
CRS_UTM = "EPSG:32721"          # UTM 21 S: cubre toda Corrientes
SALIDA = Path("data")
MAX_MANCHAS = 30
COBERTURA_MIN = 0.6           # la última pasada tiene que cubrir al menos el 60 % del recuadro
FONDO_MIN = 5                 # pasadas válidas mínimas por píxel para armar su fondo

# Recuadros de ~20 × 20 km sobre localidades ribereñas y bajos de Corrientes (lon, lat centro)
ZONAS = {
    "Corrientes (capital)": (-58.83, -27.47),
    "Santa Lucía": (-59.10, -28.99),
    "Bella Vista": (-59.04, -28.51),
    "Goya": (-59.26, -29.14),
    "Esquina": (-59.53, -30.01),
    "Ituzaingó": (-56.69, -27.59),
    "Paso de los Libres": (-57.09, -29.71),
    "Mercedes": (-58.08, -29.18),
}
MEDIO_LADO = 0.10                # grados


def _iso(d):
    return d.isoformat().replace("+00:00", "Z")


def buscar(bbox, dias):
    import requests
    ahora = datetime.now(timezone.utc)
    consulta = {"collections": ["sentinel-1-rtc"], "bbox": list(bbox),
                "datetime": _iso(ahora - timedelta(days=dias)) + "/" + _iso(ahora), "limit": 250}
    r = requests.post(STAC, json=consulta, timeout=60)
    r.raise_for_status()
    return r.json().get("features", [])


def cobertura_huella(pasada, bbox):
    """Fracción del recuadro que cubren las huellas (geometría STAC) de los tramos de una pasada."""
    from shapely.geometry import box, shape
    from shapely.ops import unary_union
    geoms = [shape(e["geometry"]) for e in pasada if e.get("geometry")]
    if not geoms:
        return 1.0      # sin huella en el catálogo: se decide después, al leer
    caja = box(*bbox)
    return unary_union(geoms).intersection(caja).area / caja.area


def elegir_orbita(escenas, bbox=None):
    """Agrupa por órbita relativa y dirección, una pasada por día con todos sus tramos.

    Elige la órbita cuya última pasada cubre de verdad el recuadro (huella ≥ COBERTURA_MIN) y tiene
    historia suficiente; entre esas, la más reciente. Una franja puede rozar el recuadro sin cubrirlo.
    """
    grupos = {}
    for s in escenas:
        p = s.get("properties", {})
        clave = (p.get("sat:orbit_state"), p.get("sat:relative_orbit"))
        if None in clave or "vv" not in s.get("assets", {}):
            continue
        grupos.setdefault(clave, []).append(s)
    if not grupos:
        return None, []
    candidatas = []
    for clave, lista in grupos.items():
        # el satélite corta la franja en tramos contiguos: un recuadro puede caer entre dos
        por_dia = {}
        for s in sorted(lista, key=lambda s: s["properties"]["datetime"]):
            por_dia.setdefault(s["properties"]["datetime"][:10], []).append(s)
        pasadas = [por_dia[d] for d in sorted(por_dia)]
        cubre = cobertura_huella(pasadas[-1], bbox) if bbox else 1.0
        candidatas.append(((len(pasadas) >= 6, cubre >= COBERTURA_MIN, _fecha(pasadas[-1])[:10], len(pasadas)),
                           f"{clave[0]}/{clave[1]}", pasadas))
    _, nombre, pasadas = max(candidatas, key=lambda c: (c[0][0] and c[0][1], c[0][1], c[0][2], c[0][3]))
    return nombre, pasadas


def _fecha(pasada):
    return pasada[0]["properties"]["datetime"]


def grilla(lon, lat):
    from pyproj import Transformer
    from rasterio.transform import from_origin
    t = Transformer.from_crs("EPSG:4326", CRS_UTM, always_xy=True)
    xs, ys = t.transform([lon - MEDIO_LADO, lon + MEDIO_LADO], [lat - MEDIO_LADO, lat + MEDIO_LADO])
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    ancho, alto = int((x1 - x0) // RES_M), int((y1 - y0) // RES_M)
    return from_origin(x0, y1, RES_M, RES_M), ancho, alto


def leer_pasada(pasada, transform, ancho, alto):
    """Une los tramos de un mismo día (promedio donde se superponen)."""
    capas = [leer_vv(e, transform, ancho, alto) for e in pasada]
    if len(capas) == 1:
        return capas[0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(np.stack(capas), axis=0)


def cobertura(arr):
    return float(np.isfinite(arr).mean()) if arr.size else 0.0


def leer_vv(escena, transform, ancho, alto):
    """Lee VV lineal remuestreado (promedio) a la grilla de 20 m. Solo baja los bloques del recuadro."""
    import planetary_computer
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    firmada = planetary_computer.sign(escena)
    with rasterio.open(firmada["assets"]["vv"]["href"]) as src:
        with WarpedVRT(src, crs=CRS_UTM, transform=transform, width=ancho, height=alto,
                       resampling=Resampling.average, src_nodata=src.nodata, nodata=np.nan,
                       dtype="float32") as vrt:
            return vrt.read(1).astype("float64")


def fondo_espaciado(escenas, corte, maximo):
    previas = [s for s in escenas if _fecha(s) < corte]
    if len(previas) <= maximo:
        return previas
    idx = np.linspace(0, len(previas) - 1, maximo).round().astype(int)
    return [previas[i] for i in sorted(set(idx))]


def analizar_zona(nombre, lon, lat, dias, fondo_max):
    from pyproj import Transformer
    from rasterio.features import shapes
    from rasterio.transform import xy
    from shapely.geometry import shape, mapping
    from shapely.ops import transform as stransform

    bbox = (lon - MEDIO_LADO, lat - MEDIO_LADO, lon + MEDIO_LADO, lat + MEDIO_LADO)
    orbita, escenas = elegir_orbita(buscar(bbox, dias), bbox)
    if len(escenas) < 6:
        return {"zona": nombre, "estado": "sin datos suficientes",
                "detalle": f"{len(escenas)} pasadas de una misma órbita en {dias} días (mínimo 6)"}, []
    actual = escenas[-1]
    f_actual = _fecha(actual)
    corte = _iso(datetime.fromisoformat(f_actual.replace("Z", "+00:00")) - timedelta(days=30))
    previas = fondo_espaciado(escenas, corte, fondo_max)
    if len(previas) < 5:
        return {"zona": nombre, "estado": "sin datos suficientes",
                "detalle": f"solo {len(previas)} pasadas para armar el fondo (mínimo 5)"}, []

    transform, ancho, alto = grilla(lon, lat)
    a_wgs = Transformer.from_crs(CRS_UTM, "EPSG:4326", always_xy=True)

    def a_lonlat(f, c):
        x, y = xy(transform, f, c)   # centro del píxel
        return a_wgs.transform(x, y)

    hoy_db = ma.a_db(ma.filtro_lee(leer_pasada(actual, transform, ancho, alto)))
    cob = cobertura(hoy_db)
    if cob < COBERTURA_MIN:
        return {"zona": nombre, "estado": "cobertura insuficiente", "fecha_actual": f_actual,
                "detalle": f"la última pasada cubre el {cob:.0%} del recuadro (mínimo {COBERTURA_MIN:.0%})"}, []
    pila = []
    serie = []
    for s in previas:
        try:
            db = ma.a_db(ma.filtro_lee(leer_pasada(s, transform, ancho, alto)))
        except Exception as e:  # una pasada que no se puede leer no frena la zona
            print(f"  {nombre}: no se pudo leer {_fecha(s)[:10]}: {e}")
            continue
        pila.append(db)
        if cobertura(db) >= COBERTURA_MIN:     # la serie solo con pasadas comparables
            serie.append((_fecha(s)[:10], db))
    if len(pila) < 5:
        return {"zona": nombre, "estado": "sin datos suficientes", "detalle": "pasadas ilegibles"}, []

    umbral = ma.umbral_otsu(hoy_db)
    metodo_umbral = "Otsu sobre la última pasada"
    if umbral is None:
        umbral, metodo_umbral = ma.UMBRAL_AGUA_DB, "fijo −18 dB (Otsu sin dos modos claros o fuera de −24 a −15 dB)"

    med, sd, n = ma.sigma_recortado(np.stack(pila))
    med = np.where(n >= FONDO_MIN, med, np.nan)   # sin historia suficiente, el píxel no se juzga
    manchas, etiquetas, resumen = ma.detectar_manchas(hoy_db, med, sd, RES_M * RES_M, umbral_db=umbral,
                                                      a_lonlat=a_lonlat)

    # serie de % de agua por fecha (fondo + hoy) y fechas raras por Hampel
    serie.append((f_actual[:10], hoy_db))
    pct = []
    for fecha, db in serie:
        v = np.isfinite(db)
        pct.append(round(100.0 * float((db[v] < umbral).sum()) / max(1, int(v.sum())), 2))
    raras = ma.hampel(pct)
    serie_json = [{"fecha": f, "agua_pct": p, "rara": bool(r)} for (f, _), p, r in zip(serie, pct, raras)]

    # polígonos livianos de las manchas que quedan en el catálogo
    a_wgs_xy = lambda x, y: a_wgs.transform(x, y)  # noqa: E731
    elegidas = {m["id"]: m for m in manchas[:MAX_MANCHAS]}
    features = []
    mascara = np.isin(etiquetas, list(elegidas)) if elegidas else None
    if elegidas:
        for geom, valor in shapes(etiquetas.astype("int32"), mask=mascara, transform=transform, connectivity=8):
            m = elegidas.get(int(valor))
            if not m:
                continue
            g = stransform(a_wgs_xy, shape(geom)).simplify(0.0002, preserve_topology=True)
            features.append({"type": "Feature", "geometry": mapping(g),
                             "properties": {"zona": nombre, "id": m["id"], "fecha": f_actual[:10],
                                            "superficie_ha": m["superficie_ha"], "z_medio": m["z_medio"],
                                            "intensidad": m["intensidad"]}})
    for m in manchas:
        m.pop("fila_col", None)
        m.pop("caja", None)
    return {"zona": nombre, "estado": "ok", "centro": [lon, lat], "bbox": [round(b, 3) for b in bbox],
            "orbita": orbita, "fecha_actual": f_actual, "fondo_fechas": [_fecha(s)[:10] for s in previas], "cobertura": round(cob, 3),
            "umbral_db": umbral, "umbral_metodo": metodo_umbral,
            "resumen": resumen, "manchas": manchas[:MAX_MANCHAS], "manchas_total": len(manchas),
            "serie": serie_json}, features


def main():
    dias = int(os.environ.get("ANEG_DIAS", "400"))
    fondo_max = int(os.environ.get("ANEG_FONDO_MAX", "15"))
    pedidas = [z.strip() for z in os.environ.get("ANEG_ZONAS", "").split(",") if z.strip()]
    zonas = {k: v for k, v in ZONAS.items() if not pedidas or k in pedidas}
    resultados, features = [], []
    for nombre, (lon, lat) in zonas.items():
        print(f"Zona {nombre}…", flush=True)
        try:
            r, f = analizar_zona(nombre, lon, lat, dias, fondo_max)
        except Exception as e:
            r, f = {"zona": nombre, "estado": "error", "detalle": str(e)[:300]}, []
        print(f"  {r.get('estado')}: {r.get('resumen') or r.get('detalle')}", flush=True)
        resultados.append(r)
        features.extend(f)
    SALIDA.mkdir(exist_ok=True)
    salida = {
        "generado": _iso(datetime.now(timezone.utc)),
        "fuente": "Sentinel-1 RTC (ESA Copernicus, procesado por Microsoft Planetary Computer), polarización VV",
        "tipo": "medición satelital procesada; clasificación orientativa sin validar en terreno",
        "metodo": ("Filtro Lee 5×5 · fondo por píxel con recorte sigma (3σ, mediana y MAD) sobre pasadas de la misma "
                   "órbita, excluidos los últimos 30 días · desvío z · umbral de agua Otsu · apertura 3×3 · "
                   "regiones conectadas (8 vecinos), mínimo 1 ha · Hampel sobre la serie de % de agua"),
        "resolucion_m": RES_M,
        "rangos": {"intensidad": {"fuerte": "z medio ≤ −5", "moderada": "−5 a −4", "leve": "−4 a −3"},
                   "agua_nueva": "hoy bajo el umbral de agua, fondo sobre el umbral y z ≤ −3"},
        "limites": ["No ve agua bajo monte, pajonal o cultivos altos densos",
                    "No mide profundidad ni caudal",
                    "Puede confundir sombra de radar, asfalto o suelo muy liso con agua",
                    "Una pasada cada 6 a 12 días: puede perder anegamientos cortos",
                    "Píxel de 20 m: manchas menores a 1 ha no se informan"],
        "cobertura_minima": COBERTURA_MIN,
        "zonas": resultados,
    }
    (SALIDA / "anegamientos.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    (SALIDA / "anegamientos.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8")
    ok = sum(1 for r in resultados if r.get("estado") == "ok")
    print(f"Listo: {ok}/{len(resultados)} zonas, {len(features)} manchas en el mapa.")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
