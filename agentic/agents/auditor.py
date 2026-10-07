def audit(bundle, quality):
    warnings = []
    scope = bundle.get('scope')
    if scope: warnings.append(scope)
    names = set(bundle.get('sources', {}))
    if 'clima' in names and quality.get('available_sources', 0) < 2:
        warnings.append('No hay redundancia suficiente para afirmar concordancia meteorológica multifuente.')
    warnings.append('La consulta actual es puntual; no representa todavía un promedio raster del polígono.')
    warnings.append('No inferir NDVI, cantidad de animales, bebederos o nitrógeno del pasto sin medición específica.')
    return {
        'status': 'aprobado_con_advertencias' if warnings else 'aprobado',
        'warnings': warnings,
        'publishable': quality.get('score', 0) >= 40,
    }
