#!/usr/bin/env python3
"""Importa índices climáticos mensuales NOAA PSL a JSON, sin datos sintéticos.

Uso: python tools/import_noaa_teleconnections.py --output data/noaa_teleconnections.json
Dependencia: requests. La descarga se ejecuta fuera del servidor web.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

URLS = {
    "soi": "https://psl.noaa.gov/data/correlation/soi.data",
    "pna": "https://psl.noaa.gov/data/correlation/pna.data",
    "aao": "https://psl.noaa.gov/data/correlation/aao.data",
    "nao": "https://psl.noaa.gov/data/correlation/nao.data",
    "ao": "https://psl.noaa.gov/data/correlation/ao.data",
    "tni": "https://psl.noaa.gov/data/correlation/tni.data",
    "oni": "https://psl.noaa.gov/data/correlation/oni.data",
}


def parse_monthly(text):
    """Lee solo filas NOAA con año y doce valores; ignora encabezados y centinelas."""
    records = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 13 or not fields[0].isdigit() or len(fields[0]) != 4:
            continue
        year = int(fields[0])
        if year < 1800 or year > 2200:
            continue
        for month, raw in enumerate(fields[1:], 1):
            try:
                value = float(raw)
            except ValueError:
                continue
            if not -90 < value < 90:
                continue
            records.append({"month": f"{year:04d}-{month:02d}", "value": value})
    return records


def collect(session=None):
    session = session or requests.Session()
    result = {"provider": "NOAA Physical Sciences Laboratory",
              "retrieved_at": datetime.now(timezone.utc).isoformat(),
              "status": {}, "indices": {}}
    for name, url in URLS.items():
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            rows = parse_monthly(response.text)
            if not rows:
                raise ValueError("No se encontraron registros mensuales válidos")
            result["indices"][name] = {"source": url, "observations": rows}
            result["status"][name] = "ok"
        except (requests.RequestException, ValueError) as exc:
            result["status"][name] = f"unavailable: {type(exc).__name__}"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/noaa_teleconnections.json")
    args = parser.parse_args()
    data = collect()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guardado: {path}; índices disponibles: {len(data['indices'])}/{len(URLS)}")
    if not data["indices"]:
        raise SystemExit("No se descargó ningún índice NOAA")


if __name__ == "__main__":
    main()
