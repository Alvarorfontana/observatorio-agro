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


# Servicios y situación del barrio según el RENABAP. Los nombres de los campos cambian entre versiones del registro,
# así que se buscan por palabra clave.
SERVICE_FIELDS = {
    "agua": ("agua",),
    "cloaca": ("cloaca", "efluente"),
    "electricidad": ("electric", "energia_el"),
    "cocina": ("cocina",),
    "tenencia": ("dominio", "tenencia", "situa_dom", "tipo_tierra"),
    "clasificacion": ("clasif", "clas_bar"),
}


def services(props):
    out = {k: (str(pick(props, *needles) or "")[:60] or None) for k, needles in SERVICE_FIELDS.items()}
    year = pick(props, "creacion", "ano_de_cre", "anio", "año", numeric=True)
    out["creacion"] = int(year) if year and 1900 < year < 2100 else None
    return out


def export_barrios(data, path):
    """Todos los barrios del país, simplificados (≈5 m), para consultarlos dentro de un área dibujada en el mapa."""
    from shapely.geometry import shape, mapping
    feats = []
    for f in data.get("features", []):
        geom, props = f.get("geometry"), f.get("properties") or {}
        if not geom:
            continue
        try:
            g = shape(geom)
            if not g.is_valid:
                g = g.buffer(0)
            s = g.simplify(0.00005, preserve_topology=True)
            c = g.representative_point()
            b = g.bounds
        except Exception:
            continue
        fam = pick(props, "famil", numeric=True)
        geo = mapping(s)
        def rnd(o):
            return [rnd(x) for x in o] if isinstance(o, (list, tuple)) and o and isinstance(o[0], (list, tuple)) \
                else ([round(o[0], 5), round(o[1], 5)] if isinstance(o, (list, tuple)) else o)
        feats.append({"type": "Feature", "geometry": {"type": geo["type"], "coordinates": rnd(geo["coordinates"])},
                      "properties": {"nombre": str(pick(props, "nombre", "barrio") or "Sin nombre")[:80],
                                     "familias": round(fam) if fam is not None else None,
                                     "ha": round(area_ha(geom), 2),
                                     "provincia": str(pick(props, "provincia") or "")[:40],
                                     "localidad": str(pick(props, "localidad", "municipio", "departamento") or "")[:60],
                                     **services(props),
                                     "lat": round(c.y, 5), "lon": round(c.x, 5),
                                     "bbox": [round(v, 5) for v in b]}})
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "source": CREDIT, "features": feats}, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"Barrios exportados para el mapa: {len(feats)} · {os.path.getsize(path) / 1e6:.1f} MB", flush=True)


def main(out_path):
    import cuenca
    data = download()
    keys = sorted((data.get("features") or [{}])[0].get("properties", {}).keys())
    print(f"RENABAP: {len(data.get('features', []))} barrios · atributos: {', '.join(keys)}", flush=True)
    from collections import Counter
    for k, needles in SERVICE_FIELDS.items():
        vals = Counter(str(pick(f.get("properties") or {}, *needles) or "")[:60] for f in data.get("features", []))
        print(f"  {k}: {dict(vals.most_common(8))}", flush=True)
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
    export_barrios(data, os.path.join(os.path.dirname(out_path), "renabap_barrios.geojson"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "renabap_localidades.json"))
