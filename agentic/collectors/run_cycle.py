"""Run the first DOTS collection cycle and persist auditable snapshots."""
import json
from datetime import datetime, timezone
from pathlib import Path

from agentic.collectors.faostat import collect as collect_faostat
from agentic.collectors.nasa_power import collect as collect_nasa_power

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "dots"


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = []
    for agent, collector in (
        ("agricultural_history", collect_faostat),
        ("climate", collect_nasa_power),
    ):
        try:
            payload = collector()
            payload["agent_id"] = agent
            payload["run_id"] = run_id
            write_json(OUT / (agent + ".json"), payload)
            results.append({"agent_id": agent, "state": "success", "record_count": payload["record_count"]})
        except Exception as exc:
            results.append({"agent_id": agent, "state": "error", "error": str(exc)})
    manifest = {
        "run_id": run_id, "completed_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "successful_agents": sum(r["state"] == "success" for r in results),
        "failed_agents": sum(r["state"] == "error" for r in results),
    }
    write_json(OUT / "latest_run.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if manifest["failed_agents"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
