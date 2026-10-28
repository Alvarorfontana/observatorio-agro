"""El Niño visto por tres satélites: clorofila del Pacífico, humedad del suelo y lluvia (Google Earth Engine).

Uso: python scripts/enso_satelites.py [salida.json]   (por defecto data/enso_satelites.json)
Requiere GOOGLE_CLOUD_PROJECT y GOOGLE_APPLICATION_CREDENTIALS_JSON. No pide cuentas de NASA: los productos están
en el catálogo de Earth Engine.

  · Clorofila-a (MODIS Aqua, NASA OBPG, 4 km): con El Niño el agua caliente frena el afloramiento de nutrientes y el
    mar del Pacífico ecuatorial y de la costa de Perú se vuelve menos verde. Mediana mensual de la región.
  · Humedad del suelo (SMAP nivel 4, NASA, 9 km): superficie (0-5 cm) y zona de raíces (0-100 cm). Promedio mensual.
  · Lluvia (GPM IMERG mensual, NASA y JAXA, 0,1°): milímetros del mes.
Para cada región y mes se compara con el promedio del mismo mes en el período de referencia de cada producto.
Las regiones del continente son las provincias, estados o países completos (FAO GAUL 2015).
Si un producto no responde, se guarda «sin dato» con el motivo: nunca se completa con valores inventados.
"""
import calendar
import json
import os
import sys
import time
import unicodedata
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "enso_satelites.json")

# Rectángulos del océano (oeste, sur, este, norte). La clorofila sólo existe sobre el mar.
OCEANO = [
    ("pacifico", "Pacífico ecuatorial (Niño 3 y 3.4)", (-170, -5, -90, 5)),
    ("peru", "Mar de Perú y Ecuador", (-84, -16, -76, 2)),
]
# Regiones del continente: nombres de FAO GAUL 2015 (nivel 1 = provincias y estados, nivel 0 = países).
TIERRA = [
    ("nea", "NEA argentino", "Argentina", ["Corrientes", "Chaco", "Misiones", "Formosa"]),
    ("litoral", "Entre Ríos y Santa Fe", "Argentina", ["Entre Rios", "Santa Fe"]),
    ("pampa", "Buenos Aires y Córdoba", "Argentina", ["Buenos Aires", "Cordoba"]),
    ("sur-brasil", "Sur de Brasil (RS, SC y PR)", "Brazil", ["Rio Grande Do Sul", "Santa Catarina", "Parana"]),
    ("uruguay", "Uruguay", "Uruguay", None),
    ("paraguay", "Paraguay", "Paraguay", None),
]

PRODUCTOS = {
    "clorofila": {
        "titulo": "Clorofila del Pacífico", "unidad": "mg/m³", "modo": "pct",
        "colecciones": ["NASA/OCEANDATA/MODIS-Aqua/L3SMI"], "banda": "chlor_a", "reductor": "median",
        "desde": 2003, "base": (2003, 2020), "escala": 9277,
        "fuente": "MODIS Aqua · NASA Ocean Biology Processing Group (L3 SMI, 4 km)",
        "lectura": "Menos clorofila que lo normal = menos nutrientes en el agua: es lo que pasa con El Niño.",
    },
    "humedad": {
        "titulo": "Humedad del suelo", "unidad": "m³/m³", "modo": "dif",
        "colecciones": ["NASA/SMAP/SPL4SMGP/008", "NASA/SMAP/SPL4SMGP/007"], "bandas": ["sm_surface", "sm_rootzone"],
        "reductor": "mean", "desde": 2015, "base": (2016, 2025), "escala": 11000,
        "fuente": "SMAP nivel 4 · NASA (9 km, superficie 0-5 cm y zona de raíces 0-100 cm)",
        "lectura": "Más agua en el suelo que lo normal = suelos que absorben menos lluvia y crecidas más probables.",
    },
    "lluvia": {
        "titulo": "Lluvia satelital", "unidad": "mm", "modo": "pct",
        "colecciones": ["NASA/GPM_L3/IMERG_MONTHLY_V07", "NASA/GPM_L3/IMERG_MONTHLY_V06"], "banda": "precipitation",
        "reductor": "mean", "desde": 2001, "base": (2001, 2020), "escala": 11132,
        "fuente": "GPM IMERG mensual · NASA y JAXA (0,1°)",
        "lectura": "Con El Niño fuerte el NEA, el sur de Brasil y Uruguay suelen tener más lluvia que lo normal.",
    },
}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def meses(desde, hasta):
    """Lista de (año, mes) desde enero de `desde` hasta el mes `hasta` (date) inclusive."""
    out, y, m = [], desde, 1
    while (y, m) <= (hasta.year, hasta.month):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def anomalias(serie, base, modo):
    """serie: {'AAAA-MM': valor}. Devuelve filas [mes, valor, normal, anomalía] y la normal por mes del calendario.

    modo 'pct': anomalía como % respecto de la normal; 'dif': diferencia en la unidad del producto.
    La normal de cada mes del calendario es el promedio de los años de referencia con dato (al menos 3).
    """
    normal = {}
    for m in range(1, 13):
        vals = [v for k, v in serie.items() if v is not None and int(k[5:7]) == m and base[0] <= int(k[:4]) <= base[1]]
        normal[m] = sum(vals) / len(vals) if len(vals) >= 3 else None
    filas = []
    for k in sorted(serie):
        v, n = serie[k], normal[int(k[5:7])]
        if v is None:
            continue
        if n is None:
            a = None
        elif modo == "pct":
            a = round(100 * (v - n) / n, 1) if n else None
        else:
            a = round(v - n, 4)
        filas.append([k, round(v, 4), None if n is None else round(n, 4), a])
    return filas, normal


def ultimo(filas):
    return dict(zip(("mes", "valor", "normal", "anomalia"), filas[-1])) if filas else None


# ───────────────────────────── Earth Engine ─────────────────────────────

def ee_init():
    import ee
    info = json.loads(os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
    creds = ee.ServiceAccountCredentials(info["client_email"], key_data=json.dumps(info))
    ee.Initialize(creds, project=os.environ["GOOGLE_CLOUD_PROJECT"])
    return ee


def regiones_tierra(ee):
    feats, faltan = [], []
    for rid, nombre, pais, nombres in TIERRA:
        if nombres is None:
            fc = ee.FeatureCollection("FAO/GAUL/2015/level0").filter(ee.Filter.eq("ADM0_NAME", pais))
        else:
            g1 = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq("ADM0_NAME", pais))
            todos = g1.aggregate_array("ADM1_NAME").getInfo()
            pedidos = {norm(n) for n in nombres}
            elegidos = [n for n in todos if norm(n) in pedidos]
            if len(elegidos) < len(pedidos):
                faltan.append(f"{nombre}: {sorted(pedidos - {norm(n) for n in elegidos})}")
            fc = g1.filter(ee.Filter.inList("ADM1_NAME", elegidos))
        feats.append(ee.Feature(fc.geometry(1000).simplify(2000), {"id": rid}))
    if faltan:
        print("Regiones incompletas en GAUL:", "; ".join(faltan))
    return ee.FeatureCollection(feats)


def regiones_oceano(ee):
    return ee.FeatureCollection([ee.Feature(ee.Geometry.Rectangle(list(b), None, False), {"id": rid}) for rid, _, b in OCEANO])


def coleccion(ee, p):
    """Primera colección del producto que exista en el catálogo."""
    for cid in p["colecciones"]:
        try:
            col = ee.ImageCollection(cid)
            col.limit(1).size().getInfo()
            return cid, col
        except Exception as ex:
            print(f"{cid}: {str(ex)[:120]}")
    raise RuntimeError("Ninguna de las colecciones respondió: " + ", ".join(p["colecciones"]))


def serie_anio(ee, col, p, regiones, anio, hasta):
    """Valor mensual de cada banda y región para un año. Devuelve {(banda, región): {'AAAA-MM': valor}}."""
    bandas = p.get("bandas") or [p["banda"]]
    red = ee.Reducer.median() if p["reductor"] == "median" else ee.Reducer.mean()
    out = {}
    for (y, m) in meses(anio, hasta):
        if y != anio:
            break
        ini = f"{y}-{m:02d}-01"
        fin = f"{y + (m == 12)}-{(m % 12) + 1:02d}-01"
        sub = col.filterDate(ini, fin).select(bandas)
        if sub.size().getInfo() == 0:
            continue
        img = sub.mean()
        if p is PRODUCTOS["lluvia"]:
            img = img.multiply(24 * calendar.monthrange(y, m)[1])          # mm/h → mm del mes
        res = img.reduceRegions(collection=regiones, reducer=red.setOutputs(bandas) if len(bandas) > 1 else red,
                                scale=p["escala"], tileScale=4).getInfo()
        for f in res["features"]:
            pr = f["properties"]
            for b in bandas:
                v = pr.get(b) if len(bandas) > 1 else pr.get(p["reductor"])
                out.setdefault((b, pr["id"]), {})[f"{y}-{m:02d}"] = v
    return out


def producto(ee, clave, regiones, hasta):
    p = PRODUCTOS[clave]
    cid, col = coleccion(ee, p)
    acum = {}
    for anio in range(p["desde"], hasta.year + 1):
        for intento in range(3):
            try:
                for k, s in serie_anio(ee, col, p, regiones, anio, hasta).items():
                    acum.setdefault(k, {}).update(s)
                break
            except Exception as ex:
                print(f"{clave} {anio}: {str(ex)[:160]}")
                time.sleep(10 * (intento + 1))
        print(f"{clave} {anio} listo")
    nombres = {rid: n for rid, n, *_ in (OCEANO if clave == "clorofila" else TIERRA)}
    bandas = p.get("bandas") or [p["banda"]]
    capas = []
    for b in bandas:
        regs = []
        for rid, nombre in nombres.items():
            filas, normal = anomalias(acum.get((b, rid), {}), p["base"], p["modo"])
            regs.append({"id": rid, "nombre": nombre, "serie": filas, "ultimo": ultimo(filas),
                         "normal_mes": {str(m): (None if v is None else round(v, 4)) for m, v in normal.items()}})
        capas.append({"banda": b, "regiones": regs})
    meses_con_dato = sorted({f[0] for c in capas for r in c["regiones"] for f in r["serie"]})
    return {"id": clave, "titulo": p["titulo"], "unidad": p["unidad"], "modo": p["modo"], "fuente": p["fuente"],
            "coleccion": cid, "lectura": p["lectura"], "referencia": f"{p['base'][0]}-{p['base'][1]}",
            "periodo": [meses_con_dato[0], meses_con_dato[-1]] if meses_con_dato else None, "capas": capas}


def main():
    t0 = time.time()
    ee = ee_init()
    hasta = date.today()
    tierra, oceano = regiones_tierra(ee), regiones_oceano(ee)
    variables, errores = [], {}
    for clave in PRODUCTOS:
        try:
            variables.append(producto(ee, clave, oceano if clave == "clorofila" else tierra, hasta))
        except Exception as ex:
            errores[clave] = str(ex)[:300]
            variables.append({"id": clave, "titulo": PRODUCTOS[clave]["titulo"], "error": errores[clave]})
            print(f"{clave}: sin dato · {errores[clave]}")
    salida = {"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variables": variables,
              "metodo": __doc__.split("\n\n", 1)[1].strip(), "errores": errores}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(salida, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"Listo en {(time.time() - t0) / 60:.0f} min · {len(variables) - len(errores)} de {len(variables)} productos")
    return 0 if len(errores) < len(variables) else 1


if __name__ == "__main__":
    sys.exit(main())
