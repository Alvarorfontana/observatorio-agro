"""Anegamientos por radar: lo que calcula la tarea semanal «Anegamientos» (rama datos), cruzado con el INA.

El cálculo corre en GitHub Actions (scripts/anegamientos.py). Acá solo se lee el resultado y se compara cada
zona con el último estado del río que publicó el INA (data/avisos.json), para marcar si el radar coincide.
"""
ESCALA_INA = {
    'Corrientes (capital)': 'parana-corrientes', 'Bella Vista': 'parana-bellavista', 'Goya': 'parana-goya',
    'Esquina': 'parana-esquina', 'Ituzaingó': 'parana-ituzaingo', 'Paso de los Libres': 'uruguay-libres',
}
RIO_ALTO = ('Alerta', 'Evacuación')


def ultimo_estado(avisos):
    """Último aviso del INA por escala (el más reciente por fecha)."""
    out = {}
    for it in (avisos or {}).get('items') or []:
        k = it.get('id')
        if k and (k not in out or (it.get('date') or '') > (out[k].get('date') or '')):
            out[k] = it
    return out


def coincidencia(zona, rio):
    """¿El radar va en el mismo sentido que el río? Orientativo."""
    r = zona.get('resumen') or {}
    if zona.get('estado') != 'ok':
        return None, 'Sin datos de radar esta semana.'
    if not rio:
        return None, 'Sin escala del INA en el recuadro: no se puede contrastar.'
    alto = rio.get('to') in RIO_ALTO
    hoy, hab, nueva = r.get('agua_hoy_ha') or 0, r.get('agua_habitual_ha') or 0, r.get('agua_nueva_ha') or 0
    if alto and hoy < hab:
        return False, ('El río está en ' + rio['to'].lower() + ' y el radar ve menos agua que lo habitual. '
                       'Posible viento sobre el río o geometría de la pasada. En revisión.')
    if hab > 100 and hoy < 0.5 * hab:
        return False, ('El radar ve menos de la mitad del agua habitual y el río no está bajo según el INA. '
                       'Posible viento sobre el río o geometría de la pasada. En revisión.')
    if alto and nueva <= 0:
        return False, 'El río está en ' + rio['to'].lower() + ' y el radar no ve agua nueva. En revisión.'
    if not alto and nueva > 500:
        return False, 'El radar ve mucha agua nueva con el río en estado normal o de atención. En revisión.'
    return True, 'Coincide con el estado del río.'


def armar(data, avisos):
    if not data:
        return None
    estados = ultimo_estado(avisos)
    zonas = []
    for z in data.get('zonas') or []:
        rio = estados.get(ESCALA_INA.get(z.get('zona')))
        ok, texto = coincidencia(z, rio)
        z = dict(z, ina=({k: rio.get(k) for k in ('place', 'river', 'to', 'height', 'alert', 'evac', 'date')} if rio else None),
                 coincide=ok, contraste=texto)
        zonas.append(z)
    return dict(data, zonas=zonas)
