#!/usr/bin/env python3
"""Produce mapas y Hovmöller históricos NOAA ERSST v5 para DOTS.

Ejecutar fuera del servidor: pip install xarray netCDF4 numpy
python tools/build_enso_ersst.py --input /ruta/sst.mnmean.nc --output public/data/enso-ersst.json
No inventa observaciones ni descarga datasets voluminosos en una petición Flask.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import xarray as xr

REGIONS = {"nino12": (-10, 0, 270, 280), "nino3": (-5, 5, 210, 270),
           "nino34": (-5, 5, 190, 240), "nino4": (-5, 5, 160, 210)}
BASE_START, BASE_END = "1991-01", "2020-12"

def build(path, since="1981-01"):
    with xr.open_dataset(path) as ds:
        if "sst" not in ds:
            raise ValueError("El archivo no contiene la variable SST")
        sst = ds["sst"].sel(time=slice(since, None))
        if sst.sizes.get("time", 0) < 12:
            raise ValueError("Se requieren al menos 12 meses de observaciones")
        baseline = ds["sst"].sel(time=slice(BASE_START, BASE_END))
        if baseline.sizes.get("time", 0) < 300:
            raise ValueError("Climatología 1991-2020 incompleta")
        climatology = baseline.groupby("time.month").mean("time", skipna=True)
        anomaly = sst.groupby("time.month") - climatology
        # Recorte del Pacífico tropical: 120 E a 80 W.
        pac = anomaly.sel(lat=slice(-15, 15), lon=slice(120, 280))
        if pac.sizes.get("lat", 0) == 0:
            pac = anomaly.sel(lat=slice(15, -15), lon=slice(120, 280))
        if pac.sizes.get("lon", 0) == 0 or pac.sizes.get("lat", 0) == 0:
            raise ValueError("No hay cobertura válida del Pacífico tropical")
        months = [str(np.datetime_as_string(t, unit="M")) for t in sst.time.values]
        lat_band = pac.sel(lat=slice(-5, 5))
        if lat_band.sizes.get("lat", 0) == 0:
            lat_band = pac.sel(lat=slice(5, -5))
        hov = lat_band.mean("lat", skipna=True)
        # Malla reducida, evita cargar NetCDF en el navegador.
        hov = hov.coarsen(lon=4, boundary="trim").mean()
        maps = pac.isel(time=slice(None, None, 12)).coarsen(lat=2, lon=4, boundary="trim").mean()
        def safe(v):
            return None if not np.isfinite(v) else round(float(v), 3)
        indices = {}
        for key, (la, lb, lo, hi) in REGIONS.items():
            sub = anomaly.where((anomaly.lat >= la) & (anomaly.lat <= lb) &
                                (anomaly.lon >= lo) & (anomaly.lon <= hi), drop=True)
            weighted = sub.weighted(np.cos(np.deg2rad(sub.lat)).clip(min=0)).mean(("lat", "lon"))
            indices[key] = [safe(v) for v in weighted.values]
        return {
            "source": "NOAA ERSST v5", "source_url": "https://psl.noaa.gov/data/gridded/data.noaa.ersst.v5.html",
            "kind": "observed_reanalysis", "baseline": "1991-2020",
            "method": "Anomalía mensual frente a climatología 1991-2020; no equivale al ONI oficial CPC",
            "months": months, "indices": indices,
            "hovmoller": {"lon": [round(float(v), 2) for v in hov.lon.values],
                           "values": [[safe(v) for v in row] for row in hov.values]},
            "maps": {"months": [months[i] for i in range(0, len(months), 12)],
                     "lat": [round(float(v), 2) for v in maps.lat.values],
                     "lon": [round(float(v), 2) for v in maps.lon.values],
                     "values": [[[safe(v) for v in row] for row in frame] for frame in maps.values]},
        }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="public/data/enso-ersst.json")
    args = parser.parse_args()
    result = build(args.input)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"ERSST exportado: {out} ({len(result['months'])} meses)")

if __name__ == "__main__":
    main()
