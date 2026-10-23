"""Barrios populares registrados (RENABAP) alrededor de cada localidad ribereña de DOTS.

Sin satélites ni Earth Engine: lee el archivo nacional oficial del RENABAP (argentina.gob.ar, 2023-12-06) y, para
cada una de las 34 localidades de las alertas de crecidas, cuenta los barrios cuyo centro está a 15 km o menos,
suma las familias que informa el registro y la superficie. Sirve de dato oficial mientras el modelo de radar no
haya mapeado la localidad, y de control para lo que el modelo detecta.

Salida: data/renabap_localidades.json (rama datos).
"""
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

URL = os.environ.get("RENABAP_URL", "https://www.argentina.gob.ar/sites/default/files/renabap-2023-12-06.geojson")
RADIUS_KM = 15
CREDIT = "Registro Nacional de Barrios Populares (RENABAP) · versión 2023-12-06 · argentina.gob.ar"


def download():
    for attempt in range(3):
        try:
            r = requests.get(URL, timeout=300, headers={"User-Agent": "DOTS observatorio (datos abiertos)"})
            if r.ok:
                return r.json()
            print(f"RENABAP respondió HTTP {r.status_code}", flush=True)
        except (requests.RequestException, ValueError) as exc:
            print(f"RENABAP no respondió: {type(exc).__name__}", flush=True)
        time.sleep(15 * (attempt + 1))
    raise SystemExit("No se pudo bajar el RENABAP")


def pick(props, *needles, numeric=False):
    """Primer atributo cuyo nombre contiene alguna de las palabras (el registro cambió nombres entre versiones)."""
    for k, v in props.items():
        low = k.lower()
        if any(n in low for n in needles):
            if numeric:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
            if v not in (None, ""):
                return v
    return None


def km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def area_ha(geom):
    """Superficie aproximada en hectáreas (proyección local; suficiente para barrios)."""
    from shapely.geometry import shape
    from shapely.ops import transform
    g = shape(geom)
    lat0 = g.centroid.y
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110540
    return transform(lambda x, y, z=None: (x * kx, y * ky), g).area / 10000


def summarize(data, stations):
    from shapely.geometry import shape
    feats = []
    for f in data.get("features", []):
        geom, props = f.get("geometry"), f.get("properties") or {}
        if not geom:
            continue
        try:
            c = shape(geom).representative_point()
        except Exception:
            continue
        feats.append({"lat": c.y, "lon": c.x, "geom": geom,
                      "nombre": pick(props, "nombre", "barrio"),
                      "familias": pick(props, "famil", numeric=True)})
    places = []
    for st in stations:
        near = [f for f in feats if km(st["lat"], st["lon"], f["lat"], f["lon"]) <= RADIUS_KM]
        fam = [f["familias"] for f in near if f["familias"] is not None]
        sup = sum(area_ha(f["geom"]) for f in near)
        top = sorted((f for f in near if f["familias"] is not None), key=lambda f: -f["familias"])[:5]
        places.append({"id": st["id"], "place": st["place"], "river": st["river"], "barrios": len(near),
                       "familias": round(sum(fam)) if fam else None, "superficie_ha": round(sup, 1),
                       "mayores": [{"nombre": str(f["nombre"] or "Sin nombre")[:80], "familias": round(f["familias"])}
                                   for f in top]})
    return places


def main(out_path):
    import cuenca
    data = download()
    keys = sorted((data.get("features") or [{}])[0].get("properties", {}).keys())
    print(f"RENABAP: {len(data.get('features', []))} barrios · atributos: {', '.join(keys)}", flush=True)
    places = summarize(data, cuenca.STATIONS)
    for p in places:
        print(f"{p['place']}: {p['barrios']} barrios, {p['familias']} familias, {p['superficie_ha']} ha", flush=True)
    out = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "radius_km": RADIUS_KM, "source": CREDIT,
           "nota": ("Barrios cuyo centro está a 15 km o menos de la localidad. Las familias son las que estima el "
                    "registro; los barrios posteriores a su último relevamiento no figuran. Fuera de Argentina no hay "
                    "RENABAP."),
           "places": places}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "renabap_localidades.json"))
