from agentic.agents.registry import AGENTS, DEFAULT_AGENT_STATE
from agentic.routes import dots_agentic_api
from flask import Flask


def test_registry_defines_distinct_research_roles():
    assert len(AGENTS) >= 9
    assert "agricultural_history" in AGENTS
    assert "historical_timeline" in AGENTS
    assert all(item.get("role") and item.get("cadence") for item in AGENTS.values())


def test_agent_endpoint_marks_agents_as_defined_not_running():
    app = Flask(__name__)
    app.register_blueprint(dots_agentic_api)
    response = app.test_client().get("/api/agentic/agents")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["registry_state"] == DEFAULT_AGENT_STATE
    assert len(payload["agents"]) == len(AGENTS)
    assert all(agent["state"] == "defined" for agent in payload["agents"])


def test_atlas_endpoint_exposes_temporal_scales_and_regions():
    app = Flask(__name__)
    app.register_blueprint(dots_agentic_api)
    response = app.test_client().get("/api/agentic/atlas")
    assert response.status_code == 200
    payload = response.get_json()
    assert "day" in payload["time_scales"]
    assert "millennium" in payload["time_scales"]
    assert "Provincia de Buenos Aires" in payload["initial_regions"]
