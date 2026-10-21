#!/usr/bin/env python3
"""Importador seguro de observaciones NASA POWER aportadas por el usuario.
No extrapola un punto a todo el país ni interpreta -999 como medición.
"""
import argparse
import json
import math
from pathlib import Path

def convert(source):
    data=json.loads(Path(source).read_text(encoding="utf-8"))
    if data.get("type")!="Feature" or data.get("geometry",{}).get("type")!="Point":
        raise ValueError("Se requiere NASA POWER GeoJSON puntual")
    coordinates=data["geometry"]["coordinates"]
    raw=data.get("properties",{}).get("parameter",{})
    if not raw: raise ValueError("No se encontraron parámetros NASA POWER")
    observations={}
    for variable, series in raw.items():
        if not isinstance(series,dict): continue
        observations[variable]={
            str(k): (round(float(v),4) if isinstance(v,(int,float)) and math.isfinite(v) and float(v)>-900 else None)
            for k,v in sorted(series.items()) if len(str(k)) in (8,10)
        }
    return {
        "source":"NASA POWER",
        "source_url":"https://power.larc.nasa.gov/",
        "kind":"point_observation",
        "coverage":"Punto individual, no interpolado ni extrapolado",
        "longitude":coordinates[0],"latitude":coordinates[1],
        "parameters":observations,
        "missing_value_rule":"Valores -999 o menores que -900 convertidos a null",
        "caveat":"Archivo de ejemplo de octubre de 2026; no representa la cobertura global de DOTS"
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    result=convert(args.input)
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("NASA POWER importado:",result["latitude"],result["longitude"],list(result["parameters"]))
if __name__=="__main__":main()
