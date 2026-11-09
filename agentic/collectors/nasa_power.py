"""NASA POWER daily climate collector for explicitly labelled reference points."""
from datetime import date, datetime, timedelta, timezone
import requests

BASE = "https://power.larc.nasa.gov/api/temporal/daily/point"
# Representative research points, not national spatial averages.
POINTS = [
    {"id": "ar_pampas_buenos_aires", "country": "Argentina", "region": "Pampas - Buenos Aires", "lat": -34.60, "lon": -58.38},
    {"id": "ar_pampas_cordoba", "country": "Argentina", "region": "Pampas - Córdoba", "lat": -31.42, "lon": -64.18},
    {"id": "br_mato_grosso_cuiaba", "country": "Brasil", "region": "Centro-Oeste - Cuiabá", "lat": -15.60, "lon": -56.10},
    {"id": "br_parana_curitiba", "country": "Brasil", "region": "Sul - Curitiba", "lat": -25.43, "lon": -49.27},
    {"id": "uy_soriano_mercedes", "country": "Uruguay", "region": "Litoral agrícola - Soriano", "lat": -33.25, "lon": -58.03},
    {"id": "py_alto_parana", "country": "Paraguay", "region": "Oriental - Alto Paraná", "lat": -25.51, "lon": -54.61},
]
PARAMETERS = "PRECTOTCORR,T2M"


def collect(session=requests, start_date=None, end_date=None):
    end_date = end_date or (date.today() - timedelta(days=2))
    start_date = start_date or (end_date - timedelta(days=30))
    results = []
    for point in POINTS:
        params = {
            "parameters": PARAMETERS, "community": "AG", "longitude": point["lon"],
            "latitude": point["lat"], "start": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"), "format": "JSON",
        }
        response = session.get(BASE, params=params, timeout=90)
        response.raise_for_status()
        payload = response.json()
        parameter_data = payload.get("properties", {}).get("parameter", {})
        for parameter, daily_values in parameter_data.items():
            for day, value in daily_values.items():
                numeric = None if value in (-999, -999.0, None) else value
                results.append({
                    **point, "indicator": parameter,
                    "date": datetime.strptime(day, "%Y%m%d").date().isoformat(),
                    "value": numeric, "unit": "mm/day" if parameter == "PRECTOTCORR" else "degC",
                    "source": "NASA POWER Daily API",
                    "source_url": "https://power.larc.nasa.gov/docs/services/api/temporal/daily/",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "status": "observed" if numeric is not None else "missing",
                    "spatial_method": "single_reference_point_not_national_average",
                })
    return {
        "source": "NASA POWER Daily API", "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "record_count": len(results), "records": results,
    }
