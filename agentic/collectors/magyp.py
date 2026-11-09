"""Argentina's official crop-estimates dataset (MAGyP CKAN portal)."""
import csv
import io
from datetime import datetime, timezone
import requests

PACKAGE_API = "https://datos.magyp.gob.ar/api/3/action/package_show"
DATASET_ID = "estimaciones-agricolas"
SOURCE_PAGE = "https://datos.magyp.gob.ar/dataset/estimaciones-agricolas"


def _number(value):
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw.lower() in {"s/d", "sd", "null", "na", "-"}:
        return None
    raw = raw.replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def collect(session=requests):
    metadata_response = session.get(
        PACKAGE_API, params={"id": DATASET_ID}, timeout=45
    )
    metadata_response.raise_for_status()
    metadata = metadata_response.json()
    if not metadata.get("success"):
        raise RuntimeError("MAGyP CKAN no devolvió el dataset de estimaciones agrícolas")
    resources = metadata.get("result", {}).get("resources", [])
    csv_resources = [
        resource for resource in resources
        if str(resource.get("format", "")).lower() in {"csv", "text/csv"}
        or str(resource.get("mimetype", "")).lower() == "text/csv"
    ]
    if not csv_resources:
        raise RuntimeError("MAGyP dataset encontrado, pero no publicó un recurso CSV identificable")
    resource = max(csv_resources, key=lambda item: item.get("last_modified") or item.get("created") or "")
    download_url = resource.get("url")
    if not download_url:
        raise RuntimeError("El recurso CSV de MAGyP no tiene URL de descarga")
    response = session.get(download_url, timeout=120)
    response.raise_for_status()
    content = response.content
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = content.decode("latin-1")
    sample = decoded[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(decoded), dialect=dialect)
    required = {"cultivo", "campania", "provincia", "superficie_sembrada_ha",
                "superficie_cosechada_ha", "produccion_tm", "rendimiento_kgxha"}
    headers = {str(name).strip().lower() for name in (reader.fieldnames or [])}
    if not required.issubset(headers):
        raise RuntimeError("El CSV MAGyP cambió su esquema; se detiene la carga para evitar datos mal interpretados")
    records = []
    for source_row in reader:
        row = {str(k).strip().lower(): v for k, v in source_row.items() if k is not None}
        records.append({
            "country": "Argentina",
            "crop": row.get("cultivo"),
            "year": row.get("anio"),
            "campaign": row.get("campania"),
            "province": row.get("provincia"),
            "province_id": row.get("provincia_id"),
            "department": row.get("departamento"),
            "department_id": row.get("departamento_id"),
            "area_sown_ha": _number(row.get("superficie_sembrada_ha")),
            "area_harvested_ha": _number(row.get("superficie_cosechada_ha")),
            "production_t": _number(row.get("produccion_tm")),
            "yield_kg_ha": _number(row.get("rendimiento_kgxha")),
            "source": "MAGyP - Estimaciones Agrícolas",
            "source_url": SOURCE_PAGE,
            "resource_url": download_url,
            "resource_id": resource.get("id"),
            "resource_last_modified": resource.get("last_modified"),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "status": "observed",
        })
    return {
        "source": "MAGyP - Estimaciones Agrícolas",
        "source_url": SOURCE_PAGE,
        "resource_url": download_url,
        "resource_id": resource.get("id"),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "records": records,
    }
