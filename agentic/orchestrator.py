from datetime import datetime, timezone
from agentic.agents.quality import assess_bundle
from agentic.agents.auditor import audit
import research_connectors as connectors


def analyze_point(lat, lon, ina_id=None):
    """First DOTS Agentic flow. Preserves raw evidence and adds quality/audit layers."""
    raw = connectors.research_bundle(lat, lon, ina_id)
    quality = assess_bundle(raw)
    audit_result = audit(raw, quality)
    evidence = []
    for name, source in raw.get('sources', {}).items():
        payload = source.get('payload') or {}
        evidence.append({
            'source': name,
            'status': source.get('status'),
            'source_url': payload.get('source_url'),
            'consulted_at': payload.get('consulted_at'),
        })
    return {
        'engine': 'DOTS Agentic',
        'version': '0.1.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'target': {'type': 'point', 'coordinates': [lat, lon]},
        'quality': quality,
        'audit': audit_result,
        'evidence': evidence,
        'raw_bundle': raw,
    }
