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

def main():
    p = argparse.ArgumentParser()
    for name in SOURCES:
        p.add_argument("--" + name)
    p.add_argument("--output", default="public/data/enso-atmosphere.json")
    a = p.parse_args()
    if not any(getattr(a, k) for k in SOURCES):
        p.error("Se requiere al menos un NetCDF de entrada")
    output = derive(**{k: getattr(a, k) for k in SOURCES})
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Exportado {dest}; productos: {list(output['products'])}")
    if not output["products"]:
        raise SystemExit("Ningún producto atmosférico válido")

if __name__ == "__main__":
    main()
