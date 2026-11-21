#!/usr/bin/env python3
"""Deriva productos atmosféricos ENSO de NetCDF oficiales NOAA/NCEP.

No descarga datasets durante peticiones web. Los archivos se suministran al
proceso offline y la ausencia de una variable se declara, nunca se simula.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import xarray as xr

BASE = slice("1991-01", "2020-12")
SOURCES = {
    "olr": "https://psl.noaa.gov/data/gridded/data.interp_OLR.html",
    "wind": "https://psl.noaa.gov/data/gridded/data.ncep.reanalysis.derived.pressure.html",
    "slp": "https://psl.noaa.gov/data/gridded/data.ncep.reanalysis.derived.surface.html",
    "soil": "https://psl.noaa.gov/data/gridded/data.cpcsoil.html",
}
def clean(v):
    return None if not np.isfinite(v) else round(float(v), 3)

def anomaly(da):
    base = da.sel(time=BASE)
    if base.sizes.get("time", 0) < 300:
        raise ValueError("No hay climatología mensual completa 1991–2020")
    return da.groupby("time.month") - base.groupby("time.month").mean("time", skipna=True)

def box(da, lat1, lat2, lon1, lon2):
    lat = da.lat
    lon = da.lon
    sub = da.where((lat >= lat1) & (lat <= lat2) &
                   (lon >= lon1) & (lon <= lon2), drop=True)
    if not sub.sizes.get("lat", 0) or not sub.sizes.get("lon", 0):
        raise ValueError("Región fuera de cobertura")
    weights = np.cos(np.deg2rad(sub.lat)).clip(min=0)
    return sub.weighted(weights).mean(("lat", "lon"))

def series(da):
    return {"months": [str(np.datetime_as_string(t, unit="M")) for t in da.time.values],
            "values": [clean(v) for v in da.values]}

def open_variable(path, variable):
    with xr.open_dataset(path) as ds:
        if variable not in ds:
            raise ValueError(f"Variable {variable} ausente en {path}")
        return ds[variable].load()

def derive(olr=None, wind=None, slp=None, soil=None):
    result = {"baseline": "1991-2020", "status": {}, "products": {},
              "sources": SOURCES, "data_kind": "reanálisis/observación interpolada"}
    if olr:
        try:
            a = anomaly(open_variable(olr, "olr"))
            result["products"]["olr_pacific"] = series(box(a, -5, 5, 160, 280))
            result["status"]["olr"] = "ok"
        except (ValueError, KeyError, OSError) as exc:
            result["status"]["olr"] = type(exc).__name__
    if wind:
        try:
            u = open_variable(wind, "uwnd")
            if "level" not in u.coords:
                raise ValueError("No hay niveles de presión")
            u850 = u.sel(level=850)
            u200 = u.sel(level=200)
            result["products"]["trade_winds_850"] = series(box(anomaly(u850), -5, 5, 160, 280))
            result["products"]["walker_shear_200_minus_850"] = series(
                box(anomaly(u200 - u850), -5, 5, 160, 280))
            result["status"]["wind"] = "ok"
        except (ValueError, KeyError, OSError) as exc:
            result["status"]["wind"] = type(exc).__name__
    if slp:
        try:
            a = anomaly(open_variable(slp, "slp"))
            # Presión regional cercana a Tahití y Darwin: NO es SOI estandarizado.
            tahiti = box(a, -20, -15, 208, 213)
            darwin = box(a, -15, -10, 129, 133)
            result["products"]["tahiti_minus_darwin_slp_anomaly"] = series(tahiti - darwin)
            result["status"]["slp"] = "ok"
        except (ValueError, KeyError, OSError) as exc:
            result["status"]["slp"] = type(exc).__name__
    if soil:
        try:
            a = anomaly(open_variable(soil, "soilw"))
            result["products"]["soil_argentina"] = series(box(a, -55, -22, 286, 313))
            result["status"]["soil"] = "ok"
        except (ValueError, KeyError, OSError) as exc:
            result["status"]["soil"] = type(exc).__name__
    return result

# Si un archivo de NOAA PSL dejó de actualizarse (el OLR interpolado se frenó en 2022), se completa con el
# índice equivalente que publica el CPC de NOAA, mes a mes, y se anota la fuente usada.
CPC_RESPALDO = {
    "olr_pacific": ("https://www.cpc.ncep.noaa.gov/data/indices/olr", "ANOMALY",
                    "NOAA CPC · índice OLR del Pacífico ecuatorial (160°E-160°O), anomalía mensual"),
    "tahiti_minus_darwin_slp_anomaly": ("https://www.cpc.ncep.noaa.gov/data/indices/soi", "ANOMALY",
                                        "NOAA CPC · índice SOI (Tahití menos Darwin), anomalía mensual"),
}


def parse_cpc(text):
    """Archivos de índices del CPC: secciones ORIGINAL / ANOMALY / STANDARDIZED, 12 columnas de 6 caracteres."""
    import re
    sections, cur = {}, "ORIGINAL"
    for line in text.splitlines():
        u = line.upper()
        if "DATA" in u and not re.match(r"^\s*\d{4}", line):
            words = [w for w in re.findall(r"[A-Z]+", u) if w != "DATA"]
            if words:
                cur = words[0]
            continue
        m = re.match(r"^(\d{4})(.*)$", line.rstrip())
        if not m:
            continue
        y, rest = int(m.group(1)), m.group(2)
        for mi in range(12):
            try:
                f = float(rest[mi * 6:mi * 6 + 6])
            except ValueError:
                continue
            if f > -999:
                sections.setdefault(cur, []).append((y, mi + 1, f))
    return sections


def meses_de_atraso(serie):
    import datetime as dt
    if not serie or not serie.get("months"):
        return 999
    y, m = map(int, serie["months"][-1].split("-"))
    hoy = dt.date.today()
    return (hoy.year - y) * 12 + hoy.month - m


def completar_con_cpc(output, max_atraso=4, bajar=None):
    import urllib.request
    bajar = bajar or (lambda url: urllib.request.urlopen(url, timeout=60).read().decode("latin-1"))
    for clave, (url, seccion, fuente) in CPC_RESPALDO.items():
        actual = output["products"].get(clave)
        if meses_de_atraso(actual) <= max_atraso:
            continue
        try:
            filas = parse_cpc(bajar(url)).get(seccion) or []
        except Exception as exc:
            print(f"{clave}: respaldo CPC no disponible ({type(exc).__name__})")
            continue
        if len(filas) < 400:
            continue
        output["products"][clave] = {"months": [f"{y}-{m:02d}" for y, m, _ in filas],
                                     "values": [round(v, 3) for _, _, v in filas]}
        output.setdefault("fuentes_respaldo", {})[clave] = {"fuente": fuente, "url": url}
        var = "olr" if clave.startswith("olr") else "slp"
        output["status"][var] = "ok"
        print(f"{clave}: completado con {fuente} hasta {filas[-1][0]}-{filas[-1][1]:02d}")
    return output

def main():
    p = argparse.ArgumentParser()
    for name in SOURCES:
        p.add_argument("--" + name)
    p.add_argument("--output", default="public/data/enso-atmosphere.json")
    a = p.parse_args()
    if not any(getattr(a, k) for k in SOURCES):
        p.error("Se requiere al menos un NetCDF de entrada")
    output = completar_con_cpc(derive(**{k: getattr(a, k) for k in SOURCES}))
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Exportado {dest}; productos: {list(output['products'])}")
    if not output["products"]:
        raise SystemExit("Ningún producto atmosférico válido")

if __name__ == "__main__":
    main()
