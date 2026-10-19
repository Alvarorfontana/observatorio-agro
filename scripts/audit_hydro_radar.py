#!/usr/bin/env python3
"""Auditoría complementaria de fuentes DOTS: sin credenciales y sin modificar datos.

Uso:
  python scripts/audit_hydro_radar.py
  python scripts/audit_hydro_radar.py --live

El modo predeterminado comprueba solamente la configuración del repositorio.
--live hace consultas ligeras a endpoints públicos; disponibilidad no implica que
existan observaciones recientes para todas las localidades.
"""
import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ("ina-argentina", "ina_a5.py", "https://alerta.ina.gob.ar/a5/obs/puntual/series?var_id=2", "OBSERVATION"),
    ("sentinel-1-rtc", "radar.py", "https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-rtc", "CATALOG"),
    ("copernicus-gfm", "gfm.py", "https://stac.eodc.eu/api/v1/collections", "CATALOG"),
    ("chirps", "rainfall.py", "https://climateserv.servirglobal.net/api", "DATA_SERVICE"),
    ("cuenca-plata", "cuenca.py", None, "ANALYSIS"),
)


def probe(url, timeout=10):
    request = Request(url, headers={"User-Agent": "DOTS-Campo-source-audit/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return {"status": "HTTP_REACHABLE", "http_status": response.status}
    except HTTPError as exc:
        # An HTTP response (even 401/403) proves host connectivity, NOT data access.
        return {"status": "HTTP_ERROR", "http_status": exc.code}
    except (URLError, TimeoutError, OSError) as exc:
        return {"status": "NETWORK_ERROR", "error_type": type(exc).__name__}


def audit(live=False):
    rows = []
    for name, relative, url, capability in SOURCES:
        path = ROOT / relative
        present = path.is_file()
        row = {"source": name, "module": relative, "capability": capability,
               "code_status": "PRESENT" if present else "MISSING",
               "data_status": "NOT_VERIFIED"}
        if present:
            try:
                source = path.read_text(encoding="utf-8")
                compile(source, str(path), "exec")
                row["syntax"] = "OK"
            except (OSError, SyntaxError, UnicodeError) as exc:
                row["syntax"] = "ERROR"
                row["syntax_error_type"] = type(exc).__name__
        if live and url:
            row["connectivity"] = probe(url)
        elif url:
            row["connectivity"] = {"status": "NOT_CHECKED"}
        else:
            row["connectivity"] = {"status": "NOT_APPLICABLE"}
        rows.append(row)
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "live" if live else "offline", "results": rows,
            "warning": "Conectividad HTTP y presencia de código no certifican datos ni mapas reales."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Comprobar conectividad pública")
    args = parser.parse_args()
    print(json.dumps(audit(live=args.live), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
