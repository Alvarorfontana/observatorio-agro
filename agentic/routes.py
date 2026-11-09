"""DOTS agent registry and read-only access to collected source snapshots."""
import json
from pathlib import Path
from flask import Blueprint, jsonify, abort
from agentic.agents.registry import AGENTS, DEFAULT_AGENT_STATE

dots_agentic_api = Blueprint("dots_agentic_api", __name__, url_prefix="/api/agentic")
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "dots"
ALLOWED_DATASETS = {"agricultural_history", "climate"}


@dots_agentic_api.get("/agents")
def agents():
    return jsonify({
        "system": "DOTS Agentic",
        "registry_state": DEFAULT_AGENT_STATE,
        "note": "Defined does not mean running. Runtime state requires a tested adapter and successful scheduled execution.",
        "agents": [
            {"id": agent_id, **definition, "state": DEFAULT_AGENT_STATE}
            for agent_id, definition in AGENTS.items()
        ],
    })


@dots_agentic_api.get("/atlas")
def atlas():
    return jsonify({
        "module": "DOTS Historical and Temporal Atlas",
        "status": "data_pipeline_in_development",
        "time_scales": ["millennium", "century", "decade", "year", "month", "day"],
        "geographic_scope": {
            "continent": "South America",
            "initial_countries": ["Argentina", "Brasil", "Uruguay", "Paraguay"],
            "administrative_detail": "provincias, estados, departamentos y regiones productivas según cobertura de cada fuente",
        },
        "indicators": ["area_harvested", "production", "yield", "precipitation", "temperature"],
        "data_policy": "Display only source-backed observations at their actual temporal and geographic resolution.",
        "schema": "agentic/temporal/schema.json",
    })


@dots_agentic_api.get("/runs/latest")
def latest_run():
    path = DATA_DIR / "latest_run.json"
    if not path.exists():
        return jsonify({"state": "not_run_yet", "message": "Todavía no hay una ejecución de recolección registrada."}), 200
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@dots_agentic_api.get("/data/<dataset>")
def dataset(dataset):
    if dataset not in ALLOWED_DATASETS:
        abort(404)
    path = DATA_DIR / (dataset + ".json")
    if not path.exists():
        return jsonify({"state": "not_collected", "dataset": dataset, "record_count": 0, "records": []}), 200
    return jsonify(json.loads(path.read_text(encoding="utf-8")))
