"""Pruebas offline de la auditoría hidrológica y radar.

Ejecutar: python -m pytest tests/test_audit_hydro_radar.py -q
No realiza consultas externas ni necesita credenciales.
"""
import importlib.util
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_hydro_radar.py"
SPEC = importlib.util.spec_from_file_location("audit_hydro_radar", SCRIPT)
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)


def test_sources_have_unique_names():
    names = [row[0] for row in audit_module.SOURCES]
    assert len(names) == len(set(names))


def test_offline_audit_never_calls_network():
    with patch.object(audit_module, "probe", side_effect=AssertionError("unexpected network call")):
        report = audit_module.audit(live=False)
    assert report["mode"] == "offline"
    assert len(report["results"]) == len(audit_module.SOURCES)
    assert all(row["data_status"] == "NOT_VERIFIED" for row in report["results"])
    assert all(row["connectivity"]["status"] in ("NOT_CHECKED", "NOT_APPLICABLE")
               for row in report["results"])


def test_live_mode_does_not_claim_data_certification():
    with patch.object(audit_module, "probe", return_value={"status": "HTTP_REACHABLE", "http_status": 200}):
        report = audit_module.audit(live=True)
    assert all(row["data_status"] == "NOT_VERIFIED" for row in report["results"])
    assert all(row["connectivity"]["status"] == "HTTP_REACHABLE"
               for row in report["results"] if row["source"] != "cuenca-plata")


def test_missing_module_is_reported_not_crash(tmp_path):
    with patch.object(audit_module, "ROOT", tmp_path):
        report = audit_module.audit(live=False)
    assert all(row["code_status"] == "MISSING" for row in report["results"])
