"""Segunda opinión de AlphaEarth sobre los parches de desmonte por NDVI.

La resta de NDVI marca dónde cayó el verdor, pero una sequía fuerte, una pastura degradada o una crecida también lo
bajan. AlphaEarth Foundations (Google DeepMind) resume cada píxel de 10 m y cada año en un vector de 64 números que
describe la cobertura (monte, pastura, cultivo, agua, suelo). Si el vector del año anterior y el del año siguiente
apuntan para el mismo lado, la cobertura es la misma; si se separan, cambió de verdad.

Medida: producto escalar de los dos vectores (son unitarios), promediado dentro del parche.
  · 1 = cobertura idéntica · cerca de 0 = cobertura totalmente distinta.
No cambia la gravedad del parche (los umbrales no están validados en el terreno): suma una señal que se muestra en el
globo y queda guardada en el campo «alphaearth».

Fuente: colección GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL de Earth Engine (CC BY 4.0), un mapa por año.
Lee y reescribe data/desmonte_ndvi_<ventana>.json. Si algo falla, deja el archivo como estaba.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENTANA = os.environ.get("DESMONTE_VENTANA", "verano")
ARCHIVO = os.path.join(ROOT, "data", f"desmonte_ndvi_{VENTANA}.json")
COLECCION = "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"
FUENTE = "AlphaEarth Foundations · Google y Google DeepMind (CC BY 4.0)"
PREFIJO = "AlphaEarth:"
ESCALA = 30      # m: los mapas son de 10 m; a 30 m el promedio del parche es el mismo y gasta menos cuota
LOTE = 40        # parches por consulta a Earth Engine

# Rangos de lectura (orientativos, sin validar en el terreno)
RANGOS = [
    (0.90, "sin cambio", "la cobertura siguió igual: la caída de verdor puede ser sequía, pastoreo o manejo"),
    (0.70, "cambio moderado", "la cobertura cambió en parte: raleo, desmonte parcial o pastura nueva"),
    (-1.0, "cambio fuerte", "la cobertura es otra: confirma un desmonte o un cambio de uso del suelo"),
]


def lectura(sim):
    """Devuelve (rótulo, explicación) para una similitud."""
    for umbral, rotulo, texto in RANGOS:
        if sim >= umbral:
            return rotulo, texto
    return RANGOS[-1][1], RANGOS[-1][2]


def elegir_anios(antes, despues, ultimo):
    """Año de antes y de después a comparar. None si todavía no hay mapa anual posterior."""
    a = int(antes["desde"][:4])
    d = min(int(despues["hasta"][:4]), ultimo)
    if d <= a:
        return None
    return a, d


def aplicar(datos, sims, anios):
    """Agrega la similitud y la señal a cada parche. Quita las de corridas anteriores."""
    a, d = anios
    for p in datos.get("parches") or []:
        p["senales"] = [s for s in (p.get("senales") or []) if not s.startswith(PREFIJO)]
        p.pop("alphaearth", None)
        sim = sims.get(p["id"])
        if sim is None:
            continue
        rot, texto = lectura(sim)
        p["alphaearth"] = {"similitud": round(sim, 2), "lectura": rot}
        p["senales"].append(f"{PREFIJO} similitud {sim:.2f} entre {a} y {d}".replace(".", ",") + f", {rot}: {texto}.")
    datos["alphaearth"] = {
        "anio_antes": a, "anio_despues": d, "fuente": FUENTE, "escala_m": ESCALA,
        "rangos": [{"desde": u, "rotulo": r} for u, r, _ in RANGOS],
        "parches_evaluados": sum(1 for p in datos.get("parches") or [] if "alphaearth" in p),
    }
    return datos


def ultimo_anio(ee):
    fechas = ee.ImageCollection(COLECCION).aggregate_max("system:time_start").getInfo()
    from datetime import datetime, timezone
    return datetime.fromtimestamp(fechas / 1000, tz=timezone.utc).year


def similitudes(ee, parches, a, d):
    col = ee.ImageCollection(COLECCION)
    ia = col.filterDate(f"{a}-01-01", f"{a + 1}-01-01").mosaic()
    idd = col.filterDate(f"{d}-01-01", f"{d + 1}-01-01").mosaic()
    dot = ia.multiply(idd).reduce(ee.Reducer.sum()).rename("sim")
    out = {}
    for i in range(0, len(parches), LOTE):
        grupo = [p for p in parches[i:i + LOTE] if p.get("geom")]
        if not grupo:
            continue
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry(p["geom"]), {"id": p["id"]}) for p in grupo])
        res = dot.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=ESCALA, tileScale=4).getInfo()
        for f in res["features"]:
            v = f["properties"].get("mean")
            if v is not None:
                out[f["properties"]["id"]] = max(-1.0, min(1.0, float(v)))
        print(f"  {min(i + LOTE, len(parches))}/{len(parches)} parches", flush=True)
    return out


def main():
    if not os.path.exists(ARCHIVO):
        print(f"No está {ARCHIVO}: no hay parches para revisar.")
        return 0
    datos = json.load(open(ARCHIVO, encoding="utf-8"))
    parches = datos.get("parches") or []
    if not parches:
        print("Sin parches: nada que revisar.")
        return 0
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from desmonte_ndvi import ee_init
    ee = ee_init()
    ultimo = ultimo_anio(ee)
    anios = elegir_anios(datos["antes"], datos["despues"], ultimo)
    if not anios:
        print(f"El último mapa anual de AlphaEarth es {ultimo}: todavía no cubre el período «después». Queda sin evaluar.")
        return 0
    print(f"AlphaEarth {anios[0]} contra {anios[1]} en {len(parches)} parches")
    sims = similitudes(ee, parches, *anios)
    aplicar(datos, sims, anios)
    tmp = ARCHIVO + ".tmp"
    json.dump(datos, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, ARCHIVO)
    cuenta = {}
    for p in parches:
        r = (p.get("alphaearth") or {}).get("lectura")
        if r:
            cuenta[r] = cuenta.get(r, 0) + 1
    print("Resultado:", ", ".join(f"{k}: {v}" for k, v in cuenta.items()) or "sin datos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
