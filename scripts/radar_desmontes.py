"""Confirmación por radar (Sentinel-1) de los parches de desmonte por NDVI.

El NDVI mide verdor: una sequía, una helada o una pastura castigada también lo bajan aunque el monte siga en pie.
El radar mide otra cosa: cuánta señal rebota en la estructura de la vegetación (troncos, ramas, copas). La
polarización cruzada VH es la más sensible al volumen leñoso. Si el monte se cortó, el VH cae; si solo se secó, el
VH casi no cambia. Además el radar no depende del sol ni de las nubes.

Medida: diferencia de VH (dB) entre la ventana «después» y la ventana «antes», con la mediana de todas las pasadas
de cada ventana (reduce el moteado propio del radar) y el promedio dentro del parche.

No cambia la gravedad del parche (los umbrales no están validados en el terreno): suma una señal que se muestra en el
globo y queda guardada en el campo «radar».

Fuente: Sentinel-1 GRD (Copernicus/ESA), colección COPERNICUS/S1_GRD de Earth Engine. Datos Copernicus de libre uso.
Lee y reescribe data/desmonte_ndvi_<ventana>.json. Si algo falla, deja el archivo como estaba.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENTANA = os.environ.get("DESMONTE_VENTANA", "verano")
ARCHIVO = os.path.join(ROOT, "data", f"desmonte_ndvi_{VENTANA}.json")
COLECCION = "COPERNICUS/S1_GRD"
FUENTE = "Sentinel-1 GRD, banda VH (Copernicus/ESA)"
PREFIJO = "Radar:"
ESCALA = 30        # m: el GRD viene a 10 m; a 30 m el promedio del parche es el mismo y gasta menos cuota
LOTE = 40          # parches por consulta a Earth Engine
MIN_PASADAS = 3    # pasadas de radar por ventana para confiar en el parche

# Rangos de lectura sobre la diferencia de VH en dB (orientativos, sin validar en el terreno)
RANGOS = [
    (-2.0, "confirma", "la estructura del monte se perdió: refuerza el desmonte"),
    (-1.0, "cambio leve", "la estructura bajó un poco: raleo, desmonte parcial o suelo más seco"),
    (None, "sin cambio", "la estructura sigue en pie: la caída de verdor puede ser sequía, helada o pastoreo"),
]


def lectura(delta):
    """Devuelve (rótulo, explicación) para una diferencia de VH en dB (después menos antes)."""
    for umbral, rotulo, texto in RANGOS:
        if umbral is None or delta <= umbral:
            return rotulo, texto
    return RANGOS[-1][1], RANGOS[-1][2]


def aplicar(datos, medidas):
    """Agrega la diferencia y la señal a cada parche. Quita las de corridas anteriores.

    medidas: {id: {"vh_antes": dB, "vh_despues": dB, "pasadas_antes": n, "pasadas_despues": n}}
    """
    for p in datos.get("parches") or []:
        p["senales"] = [s for s in (p.get("senales") or []) if not s.startswith(PREFIJO)]
        p.pop("radar", None)
        m = medidas.get(p["id"])
        if not m or m.get("vh_antes") is None or m.get("vh_despues") is None:
            continue
        if min(m.get("pasadas_antes") or 0, m.get("pasadas_despues") or 0) < MIN_PASADAS:
            continue
        delta = m["vh_despues"] - m["vh_antes"]
        rot, texto = lectura(delta)
        p["radar"] = {"vh_antes": round(m["vh_antes"], 1), "vh_despues": round(m["vh_despues"], 1),
                      "delta_db": round(delta, 1), "lectura": rot}
        p["senales"].append(f"{PREFIJO} VH {m['vh_antes']:.1f} → {m['vh_despues']:.1f} dB (Δ {delta:+.1f})".replace(".", ",")
                            + f", {rot}: {texto}.")
    datos["radar"] = {
        "fuente": FUENTE, "escala_m": ESCALA, "min_pasadas": MIN_PASADAS,
        "rangos": [{"hasta_db": u, "rotulo": r} for u, r, _ in RANGOS],
        "parches_evaluados": sum(1 for p in datos.get("parches") or [] if "radar" in p),
    }
    return datos


def ventana_vh(ee, v, region):
    col = (ee.ImageCollection(COLECCION).filterBounds(region).filterDate(v["desde"], v["hasta"])
           .filter(ee.Filter.eq("instrumentMode", "IW"))
           .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
           .select("VH"))
    return col.median(), col.count()


def medir(ee, parches, antes, despues):
    out = {}
    for i in range(0, len(parches), LOTE):
        grupo = [p for p in parches[i:i + LOTE] if p.get("geom")]
        if not grupo:
            continue
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry(p["geom"]), {"id": p["id"]}) for p in grupo])
        region = fc.geometry().bounds()
        ma, ca = ventana_vh(ee, antes, region)
        md, cd = ventana_vh(ee, despues, region)
        img = ee.Image.cat([ma.rename("vh_antes"), md.rename("vh_despues"),
                            ca.rename("pasadas_antes"), cd.rename("pasadas_despues")])
        res = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=ESCALA, tileScale=4).getInfo()
        for f in res["features"]:
            pr = f["properties"]
            if pr.get("vh_antes") is None or pr.get("vh_despues") is None:
                continue
            out[pr["id"]] = {k: float(pr[k]) for k in ("vh_antes", "vh_despues", "pasadas_antes", "pasadas_despues")
                             if pr.get(k) is not None}
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
    print(f"Radar Sentinel-1 (VH) en {len(parches)} parches")
    medidas = medir(ee, parches, datos["antes"], datos["despues"])
    aplicar(datos, medidas)
    tmp = ARCHIVO + ".tmp"
    json.dump(datos, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, ARCHIVO)
    cuenta = {}
    for p in parches:
        r = (p.get("radar") or {}).get("lectura")
        if r:
            cuenta[r] = cuenta.get(r, 0) + 1
    print("Resultado:", ", ".join(f"{k}: {v}" for k, v in cuenta.items()) or "sin datos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
