"""El Niño bajo el mar: corte del Pacífico ecuatorial con las boyas TAO/TRITON (NOAA PMEL).

Las boyas de la línea del ecuador (de 137° E a 95° O) miden la temperatura del agua desde la superficie hasta
500 m. Con eso se arma el corte que muestran los especialistas: dónde está el agua más caliente o más fría de lo
normal y a qué profundidad está la termoclina (la isoterma de 20 °C). Cuando una onda fría avanza por debajo hacia
el este, anuncia el final de El Niño meses antes de que se note en la superficie.

  - Ahora: promedio de los últimos 5 días con datos de cada boya (dentro de los últimos 45 días).
  - Normal: promedio de 1993–2020 de cada boya y profundidad (se calcula una vez y se guarda).
  - Sólo datos de calidad 1 a 3 (alta, estándar o menor), como recomienda PMEL.
Fuente: GTMBA Project Office de NOAA/PMEL, vía el ERDDAP de NOAA OSMC. Datos de uso libre.

Salida: data/enso_tao.json (rama datos); climatología en scripts/cache/tao_clima.json.
"""
import csv
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# El mismo conjunto (pmelTaoDyT) se publica en varios servidores ERDDAP de NOAA; se usa el primero que responda.
SERVERS = [u for u in os.environ.get("TAO_ERDDAP", "").split(",") if u] or [
    "https://coastwatch.pfeg.noaa.gov/erddap/tabledap/pmelTaoDyT.csv",
    "https://data.pmel.noaa.gov/generic/erddap/tabledap/pmelTaoDyT.csv",
    "https://data.pmel.noaa.gov/pmel/erddap/tabledap/pmelTaoDyT.csv",
    "https://osmc.noaa.gov/erddap/tabledap/pmelTaoDyT.csv",
]
_GOOD = []
CLIMA_CACHE = os.path.join(ROOT, "scripts", "cache", "tao_clima.json")
DEPTHS = (1, 10, 20, 40, 60, 80, 100, 120, 140, 180, 300, 500)      # profundidades estándar de TAO
CREDIT = "GTMBA Project Office de NOAA/PMEL (boyas TAO/TRITON) vía ERDDAP de NOAA OSMC"
UA = {"User-Agent": "DOTS observatorio (datos abiertos)"}


def fetch_csv(query, timeout=300):
    errors = []
    for base in _GOOD + [u for u in SERVERS if u not in _GOOD]:
        for attempt in range(2):
            try:
                r = requests.get(base + "?" + query, timeout=timeout, headers=UA)
            except requests.RequestException as exc:
                errors.append(f"{base.split('/')[2]}: {type(exc).__name__}")
                time.sleep(8)
                continue
            if r.status_code == 200:
                if base not in _GOOD:
                    _GOOD.insert(0, base)
                    print(f"Servidor de las boyas: {base.split('/')[2]}", flush=True)
                return parse_csv(r.text)
            msg = " ".join(r.text.split())[:160]
            errors.append(f"{base.split('/')[2]}: HTTP {r.status_code} {msg}")
            if r.status_code in (400, 404):      # el servidor no tiene el conjunto o no acepta la consulta: el siguiente
                break
            time.sleep(8)
    raise RuntimeError(" | ".join(errors)[:900] + f" · consulta: {query[:160]}")


def parse_csv(text):
    """CSV de ERDDAP: fila de nombres, fila de unidades y datos. Devuelve diccionarios con números."""
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return []
    head = rows[0]
    out = []
    for r in rows[2:]:
        if len(r) != len(head):
            continue
        d = {}
        for k, v in zip(head, r):
            if k in ("station", "array", "time"):
                d[k] = v
            else:
                try:
                    x = float(v)
                    d[k] = x if x == x else None          # ERDDAP marca los faltantes como NaN
                except ValueError:
                    d[k] = None
        out.append(d)
    return out


def lon180(lon):
    return lon - 360 if lon > 180 else lon


def lon_label(lon):
    l = lon180(lon)
    return f"{abs(l):.0f}° {'E' if l > 0 else 'O'}" if abs(l) < 180 else "180°"


def profiles_now(rows, days=5):
    """Promedio de los últimos `days` días con dato de cada boya y profundidad."""
    by = {}
    for r in rows:
        if r.get("T_20") is None or r.get("depth") is None or r.get("longitude") is None:
            continue
        by.setdefault(r["longitude"], []).append(r)
    out = {}
    for lon, rs in by.items():
        dates = sorted({r["time"][:10] for r in rs})[-days:]
        keep = [r for r in rs if r["time"][:10] in dates]
        prof = {}
        for r in keep:
            prof.setdefault(r["depth"], []).append(r["T_20"])
        out[lon] = {"desde": dates[0], "hasta": dates[-1],
                    "perfil": {d: round(sum(v) / len(v), 2) for d, v in sorted(prof.items())}}
    return out


def isotherm_depth(profile, temp=20.0):
    """Profundidad (m) de la isoterma: interpolación lineal entre las dos mediciones que la rodean."""
    pts = sorted((d, t) for d, t in profile.items() if t is not None)
    for (d1, t1), (d2, t2) in zip(pts, pts[1:]):
        if (t1 - temp) * (t2 - temp) <= 0 and t1 != t2:
            return round(d1 + (temp - t1) * (d2 - d1) / (t2 - t1), 1)
    return None


def climatology():
    if os.path.exists(CLIMA_CACHE):
        with open(CLIMA_CACHE, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("profiles"):
            return c
    rows = fetch_csv("longitude,depth,T_20&latitude=0&time>=1993-01-01&time<=2020-12-31"
                     "&QT_5020>=1&QT_5020<=3&orderByMean(%22longitude,depth%22)", timeout=900)
    prof = {}
    for r in rows:
        if r.get("T_20") is not None and r.get("depth") is not None:
            prof.setdefault(str(r["longitude"]), {})[str(r["depth"])] = round(r["T_20"], 2)
    c = {"periodo": "1993-2020", "profiles": prof}
    os.makedirs(os.path.dirname(CLIMA_CACHE), exist_ok=True)
    with open(CLIMA_CACHE, "w", encoding="utf-8") as f:
        json.dump(c, f)
    return c


def build():
    since = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%dT00:00:00Z")
    rows = fetch_csv(f"station,longitude,time,depth,T_20&latitude=0&time>={since}&QT_5020>=1&QT_5020<=3")
    now = profiles_now(rows)
    clima = climatology()["profiles"]
    buoys = []
    for lon in sorted(now):                       # 0–360: de oeste (137° E) a este (95° O)
        p = now[lon]["perfil"]
        cp = {float(d): t for d, t in (clima.get(str(lon)) or {}).items()}
        anom = {d: round(t - cp[d], 2) for d, t in p.items() if d in cp}
        buoys.append({"longitud": lon, "lon": lon180(lon), "nombre": lon_label(lon), "desde": now[lon]["desde"],
                      "hasta": now[lon]["hasta"],
                      "perfil": [{"prof": d, "temp": t, "anom": anom.get(d)} for d, t in p.items()],
                      "isoterma20_m": isotherm_depth(p), "isoterma20_normal_m": isotherm_depth(cp) if cp else None})
    if len(buoys) < 3:
        raise RuntimeError(f"sólo {len(buoys)} boyas con datos en la línea del ecuador")
    east = [b for b in buoys if b["lon"] < -120]
    west = [b for b in buoys if b["lon"] > 150 or b["lon"] < -170]
    def mean_anom(bs, lo, hi):
        v = [x["anom"] for b in bs for x in b["perfil"] if x["anom"] is not None and lo <= x["prof"] <= hi]
        return round(sum(v) / len(v), 2) if v else None
    return {"actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "fuente": CREDIT,
            "url": "https://www.pmel.noaa.gov/gtmba/", "normal": "promedio 1993–2020 de cada boya y profundidad",
            "boyas": buoys,
            "resumen": {"anom_este_0_150m": mean_anom(east, 0, 150), "anom_oeste_80_200m": mean_anom(west, 80, 200),
                        "ultimo_dato": max(b["hasta"] for b in buoys)},
            "nota": ("Corte de la línea del ecuador con las boyas TAO. Rojo: agua más caliente que lo normal; azul: más fría. "
                     "La línea es la isoterma de 20 °C, que marca la termoclina. Los datos de las boyas llegan con algunas "
                     "semanas de demora y algunas boyas pueden estar sin datos por mantenimiento.")}


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "enso_tao.json")
    try:
        data = build()
    except Exception as exc:          # el motivo queda como anotación visible en GitHub
        print(f"::error::Boyas TAO: {type(exc).__name__}: {str(exc)[:400]}", flush=True)
        raise SystemExit(1)
    print(f"{len(data['boyas'])} boyas · último dato {data['resumen']['ultimo_dato']} · {data['resumen']}", flush=True)
    for b in data["boyas"]:
        print(f"  {b['nombre']}: {len(b['perfil'])} profundidades, isoterma 20 °C {b['isoterma20_m']} m (normal {b['isoterma20_normal_m']} m)", flush=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
