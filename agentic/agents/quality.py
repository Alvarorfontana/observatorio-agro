from datetime import datetime, timezone


def assess_source(name, source):
    """Score source availability/provenance without inventing measurements."""
    if source.get('status') != 'recibido':
        return {'source': name, 'score': 0, 'grade': 'sin dato', 'issues': [source.get('error', 'sin respuesta')]}
    payload = source.get('payload') or {}
    score = 40
    issues = []
    if payload.get('source_url'): score += 20
    else: issues.append('sin URL de procedencia')
    if payload.get('consulted_at'): score += 20
    else: issues.append('sin fecha de consulta')
    if payload.get('data') not in (None, {}, []): score += 20
    else: issues.append('respuesta sin datos')
    grade = 'alta' if score >= 80 else 'media' if score >= 60 else 'baja'
    return {'source': name, 'score': score, 'grade': grade, 'issues': issues}


def assess_bundle(bundle):
    checks = [assess_source(k, v) for k, v in bundle.get('sources', {}).items()]
    available = [x for x in checks if x['score'] > 0]
    score = round(sum(x['score'] for x in checks) / max(1, len(checks)))
    return {
        'score': score,
        'grade': 'alta' if score >= 80 else 'media' if score >= 60 else 'baja',
        'available_sources': len(available),
        'total_sources': len(checks),
        'sources': checks,
        'assessed_at': datetime.now(timezone.utc).isoformat(),
    }
