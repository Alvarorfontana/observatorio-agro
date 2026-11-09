"""FAOSTAT QCL collector for South American countries."""
from datetime import datetime, timezone
import requests

BASE = "https://fenixservices.fao.org/faostat/api/v1/en/data/QCL"
COUNTRIES = {"Argentina": "9", "Brasil": "21", "Paraguay": "169", "Uruguay": "234"}
# FAOSTAT filter codes, not display codes.
ELEMENTS = {"area_harvested": "2312", "yield": "2412", "production": "2510"}
FIRST_YEAR = 1961


def collect(session=requests, end_year=None):
    end_year = end_year or datetime.now(timezone.utc).year - 1
    years = ",".join(str(y) for y in range(FIRST_YEAR, end_year + 1))
    params = {
        "area": ",".join(COUNTRIES.values()), "element": ",".join(ELEMENTS.values()),
        "year": years, "area_cs": "FAO", "show_code": "1", "show_unit": "1",
        "show_flags": "1", "null_values": "0", "limit": "-1", "output_type": "objects",
    }
    response = session.get(BASE, params=params, timeout=90)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data", [])
    if not isinstance(rows, list):
        raise ValueError("FAOSTAT returned an unexpected data structure")
    records = []
    for row in rows:
        area = str(row.get("Area Code") or row.get("Area Code (M49)") or row.get("Area Code (FAO)") or "")
        element = str(row.get("Element Code") or "")
        if not area or not element:
            continue
        country = next((name for name, code in COUNTRIES.items() if code == area), row.get("Area"))
        records.append({
            "country": country, "area_code": area, "item": row.get("Item"),
            "item_code": row.get("Item Code"),
            "indicator": next((k for k, v in ELEMENTS.items() if v == element), row.get("Element")),
            "element": row.get("Element"), "year": row.get("Year"), "value": row.get("Value"),
            "unit": row.get("Unit"), "flag": row.get("Flag"), "source": "FAOSTAT QCL",
            "source_url": "https://www.fao.org/faostat/en/#data/QCL",
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "status": "observed",
        })
    return {
        "source": "FAOSTAT QCL", "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "countries_requested": list(COUNTRIES), "years": [FIRST_YEAR, end_year],
        "record_count": len(records), "records": records,
    }
