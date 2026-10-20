"""NOAA CPC ONI: official overlapping seasonal three-month index.
This adapter does not recalculate ONI from monthly SST and does not claim a
hydrological forecast. Uses short-lived caching to limit NOAA traffic.
"""
import time
import requests
from flask import Blueprint, jsonify

enso_data_api = Blueprint("enso_data_api", __name__)
_NOAA_URLS = ("https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", "https://origin.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt")
_CACHE = {"at": 0.0, "data": None}
_SEASONS = ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ")
_CENTER_MONTH = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6, "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}

def _parse_oni(text):
    points = []
    for line in text.splitlines():
        columns = line.split()
        if len(columns) < 4 or columns[0] not in _SEASONS:
            continue
        try:
            year = int(columns[1])
            anomaly = float(columns[3])
        except (ValueError, IndexError):
            continue
        if not (1950 <= year <= 2100 and -10 < anomaly < 10):
            continue
        month = _CENTER_MONTH[columns[0]]
        points.append({"month": f"{year:04d}-{month:02d}", "season": columns[0], "anomalyC": anomaly})
    points.sort(key=lambda x: x["month"])
    if len(points) < 120:
        raise ValueError("Respuesta NOAA incompleta o formato inesperado")
    return points

@enso_data_api.get("/api/enso/oni")
def oni_official():
    try:
        if _CACHE["data"] is None or time.time() - _CACHE["at"] > 21600:
            last_error = None
            for url in _NOAA_URLS:
                try:
                    response = requests.get(url, timeout=12, headers={"User-Agent": "DOTS-Campo/1.0 scientific data"})
                    response.raise_for_status()
                    points = _parse_oni(response.text)
                    _CACHE.update({"at": time.time(), "data": points, "url": url, "stale": False})
                    break
                except (requests.RequestException, ValueError) as exc:
                    last_error = exc
            else:
                if _CACHE["data"] is None:
                    raise last_error or ValueError("No hay datos")
                _CACHE["stale"] = True
        return jsonify({
            "status": "recibido",
            "source": "NOAA Climate Prediction Center",
            "source_url": _CACHE.get("url", _NOAA_URLS[0]),
            "stale": bool(_CACHE.get("stale", False)),
            "index": "ONI",
            "method": "Anomalía oficial trimestral móvil por estaciones superpuestas; el criterio operativo de episodios debe revisarse con la metodología NOAA vigente",
            "units": "°C",
            "points": _CACHE["data"],
            "last_month": _CACHE["data"][-1]["month"],
            "updated_from_source": not bool(_CACHE.get("stale", False))
        })
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"status": "sin dato", "error": "No fue posible obtener o validar el ONI de NOAA", "detail": type(exc).__name__}), 503

# Additional monthly oceanic regions. Source format: year month followed by
# (SST, anomaly) for Niño 1+2, Niño 3, Niño 4, Niño 3.4, respectively.
_MONTHLY_URLS = (
    "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices",
    "https://origin.cpc.ncep.noaa.gov/data/indices/sstoi.indices",
)
_MONTHLY_CACHE = {"at": 0.0, "data": None}

def _parse_sstoi(text):
    """Reject partial, malformed or implausible NOAA monthly Niño index feeds."""
    points = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 10:
            continue
        try:
            year, month = int(fields[0]), int(fields[1])
            vals = [float(x) for x in fields[2:10]]
        except (ValueError, IndexError):
            continue
        if not (1950 <= year <= 2100 and 1 <= month <= 12):
            continue
        if not all(-10 < vals[i] < 10 for i in (1, 3, 5, 7)):
            continue
        points.append({
            "month": f"{year:04d}-{month:02d}",
            "nino12": vals[1], "nino3": vals[3],
            "nino4": vals[5], "nino34": vals[7],
        })
    points.sort(key=lambda x: x["month"])
    if len(points) < 120 or len({p["month"] for p in points}) != len(points):
        raise ValueError("Serie mensual NOAA incompleta, duplicada o inválida")
    return points

@enso_data_api.get("/api/enso/nino-regions")
def nino_regions():
    try:
        if _MONTHLY_CACHE["data"] is None or time.time() - _MONTHLY_CACHE["at"] > 21600:
            last_error = None
            for url in _MONTHLY_URLS:
                try:
                    response = requests.get(url, timeout=12, headers={"User-Agent": "DOTS-Campo/1.0 scientific data"})
                    response.raise_for_status()
                    points = _parse_sstoi(response.text)
                    _MONTHLY_CACHE.update({"at": time.time(), "data": points, "url": url, "stale": False})
                    break
                except (requests.RequestException, ValueError) as exc:
                    last_error = exc
            else:
                if _MONTHLY_CACHE["data"] is None:
                    raise last_error or ValueError("Sin datos")
                _MONTHLY_CACHE["stale"] = True
        return jsonify({
            "status": "recibido", "source": "NOAA Climate Prediction Center",
            "source_url": _MONTHLY_CACHE["url"], "stale": _MONTHLY_CACHE.get("stale", False),
            "frequency": "mensual", "units": "°C",
            "kind": "observación", "index": "Niño SST anomalies",
            "method": "Anomalías mensuales NOAA CPC en regiones Niño 1+2, 3, 4 y 3.4; no equivalen al ONI trimestral",
            "limitations": "La anomalía oceánica no es por sí sola un pronóstico hidrológico regional.",
            "last_month": _MONTHLY_CACHE["data"][-1]["month"],
            "points": _MONTHLY_CACHE["data"],
        })
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"status": "sin dato", "error": "No fue posible obtener o validar las regiones Niño NOAA", "detail": type(exc).__name__}), 503

@enso_data_api.get("/api/enso/scientific-report")
def scientific_report():
    """JSON report with data provenance; PDF generation remains a separate task."""
    from enso_science import summarize_oni, report_metadata
    try:
        if _CACHE["data"] is None or time.time() - _CACHE["at"] > 21600:
            # Reuse the same validated NOAA endpoint logic; no mock fallback.
            response = oni_official()
            if isinstance(response, tuple):
                return response
        data = summarize_oni(_CACHE["data"])
        data["traceability"] = report_metadata(
            _CACHE.get("url", _NOAA_URLS[0]),
            _CACHE["data"][-1]["month"],
            data["method"],
            data["limitations"],
        )
        data["traceability"]["source_stale"] = bool(_CACHE.get("stale", False))
        data["provider"] = "NOAA Climate Prediction Center"
        return jsonify(data)
    except (ValueError, TypeError, KeyError):
        return jsonify({"status": "sin dato", "error": "No hay observaciones NOAA válidas para el informe"}), 503

# NOAA PSL SOI monthly values. No synthetic or cached fixture fallback.
_SOI_URL = "https://psl.noaa.gov/data/correlation/soi.data"
_SOI_CACHE = {"at": 0.0, "data": None}

def _parse_psl_soi(raw):
    import math
    result = []
    for line in raw.splitlines():
        cols = line.split()
        if len(cols) != 13:
            continue
        try:
            year = int(cols[0])
        except ValueError:
            continue
        if not 1860 <= year <= 2100:
            continue
        for month, token in enumerate(cols[1:], start=1):
            try:
                val = float(token)
            except ValueError:
                continue
            if math.isfinite(val) and -30 < val < 30 and val > -99:
                result.append({"month": f"{year:04d}-{month:02d}", "soi": val})
    result.sort(key=lambda p: p["month"])
    if len(result) < 120 or len(set(p["month"] for p in result)) != len(result):
        raise ValueError("Serie SOI NOAA PSL no válida")
    return result

@enso_data_api.get("/api/enso/soi")
def soi_official():
    try:
        if _SOI_CACHE["data"] is None or time.time() - _SOI_CACHE["at"] > 21600:
            try:
                response = requests.get(_SOI_URL, timeout=12, headers={"User-Agent": "DOTS-Campo/1.0 scientific data"})
                response.raise_for_status()
                _SOI_CACHE.update({"at": time.time(), "data": _parse_psl_soi(response.text), "stale": False})
            except (requests.RequestException, ValueError):
                if _SOI_CACHE["data"] is None:
                    raise
                _SOI_CACHE["stale"] = True
        return jsonify({
            "status": "recibido", "source": "NOAA Physical Sciences Laboratory",
            "source_url": _SOI_URL, "stale": bool(_SOI_CACHE.get("stale")),
            "index": "SOI", "frequency": "mensual", "kind": "observación",
            "units": "índice estandarizado",
            "method": "Índice de Oscilación del Sur mensual publicado por NOAA PSL; valores de relleno excluidos",
            "limitations": "El SOI no determina por sí solo la fase ENSO ni impactos hidrológicos locales",
            "points": _SOI_CACHE["data"],
            "last_month": _SOI_CACHE["data"][-1]["month"],
        })
    except (requests.RequestException, ValueError):
        return jsonify({"status": "sin dato", "error": "No se pudo validar el SOI oficial NOAA PSL"}), 503
