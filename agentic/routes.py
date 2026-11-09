"""Read-only API exposing DOTS agent responsibilities and temporal atlas contract."""
from flask import Blueprint, jsonify
from agentic.agents.registry import AGENTS, DEFAULT_AGENT_STATE

dots_agentic_api = Blueprint("dots_agentic_api", __name__, url_prefix="/api/agentic")


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
        "status": "specification",
        "time_scales": ["millennium", "century", "decade", "year", "month", "day"],
        "initial_regions": ["Provincia de Buenos Aires", "Península Ibérica", "Península Itálica"],
        "indicators": ["area_sown", "area_harvested", "production", "yield", "precipitation", "temperature", "vegetation"],
        "data_policy": "Display only source-backed observations at their actual temporal and geographic resolution.",
        "schema": "agentic/temporal/schema.json",
    })
