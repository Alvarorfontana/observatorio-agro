"""Auditable ENSO statistics; standard-library only, no synthetic data."""
from collections import Counter
from datetime import datetime, timezone

def summarize_oni(points):
    """Summarize NOAA overlapping seasons, not official ENSO event counts."""
    rows = sorted(
        (p for p in points if isinstance(p.get("anomalyC"), (float, int))),
        key=lambda p: p["month"],
    )
    if not rows:
        raise ValueError("Sin observaciones ONI verificadas")
    values = [float(p["anomalyC"]) for p in rows]
    latest = rows[-1]
    v = float(latest["anomalyC"])
    phase = "calida" if v >= 0.5 else "fria" if v <= -0.5 else "neutral"
    return {
        "index": "ONI",
        "kind": "observacion",
        "phase_thermal": phase,
        "phase_is_official_event": False,
        "last_observation": latest,
        "period": {"start": rows[0]["month"], "end": latest["month"]},
        "sample_size_overlapping_seasons": len(values),
        "mean_anomaly_c": round(sum(values) / len(values), 3),
        "min_anomaly_c": min(values),
        "max_anomaly_c": max(values),
        "counts_overlapping_seasons": {
            "warm": sum(v >= 0.5 for v in values),
            "cold": sum(v <= -0.5 for v in values),
            "neutral": sum(-0.5 < v < 0.5 for v in values),
        },
        "method": "Resumen descriptivo de ONI oficial; temporadas trimestrales solapadas.",
        "limitations": [
            "La fase termica de un trimestre no constituye por si sola un episodio ENSO.",
            "Las temporadas solapadas no son muestras independientes.",
            "No predice precipitaciones, sequias ni caudales en Argentina.",
        ],
    }


def report_metadata(source_url, source_updated, method, limitations):
    """Common traceability contract for scientific DOTS Campo exports."""
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": source_url,
        "source_updated": source_updated,
        "method": method,
        "limitations": list(limitations),
        "synthetic": False,
        "derived_from_observations": True,
        "forecast": False,
    }
