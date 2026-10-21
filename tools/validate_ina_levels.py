#!/usr/bin/env python3
"""Valida archivos hidrométricos INA sin confundir estaciones listadas con alturas medidas."""
import argparse
import csv
import json
from pathlib import Path

LEVEL_FIELDS=("altura_m","nivel_m","altura","nivel","altura_actual_m")
DATE_FIELDS=("fecha_medicion","fecha_observacion","fecha_hora","timestamp")
STATION_FIELDS=("estacion","nombre_estacion","station")

def read_levels(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        fields=set(reader.fieldnames or [])
        level=next((k for k in LEVEL_FIELDS if k in fields),None)
        date=next((k for k in DATE_FIELDS if k in fields),None)
        station=next((k for k in STATION_FIELDS if k in fields),None)
        if not station: raise ValueError("Falta identificación de estación")
        if not level or not date:
            return {"status":"no_measurements","source":"INA (archivo suministrado)","stations":[row[station] for row in reader if row.get(station)],"observations":[],"warning":"El archivo solo enumera estaciones: no incluye altura y fecha de medición verificables."}
        observations=[]
        for row in reader:
            try: value=float(row[level].replace(",","."))
            except (ValueError,AttributeError):continue
            if not (-20<=value<=100) or not row.get(date) or not row.get(station):continue
            observations.append({"station":row[station],"observed_at":row[date],"level_m":value})
        return {"status":"observed" if observations else "no_measurements","source":"INA (archivo suministrado)","observations":observations,"warning":"Confirmar datum y escala hidrométrica de cada estación antes de compararlas."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    d=read_levels(a.input)
    dest=Path(a.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
    print(d["status"],len(d["observations"]),"mediciones")
if __name__=="__main__":main()
