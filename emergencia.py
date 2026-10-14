"""emergencia v1.0 — emergencia y desastre agropecuario (Ley 26.509): qué es, cómo se pide y respaldo técnico del lote.

No existe un listado oficial abierto y legible por máquina de las zonas declaradas: cada declaración es una
resolución (provincial y luego nacional) publicada en el Boletín Oficial. DOTS no inventa ese mapa; aporta indicadores
medidos que el productor puede adjuntar a su declaración jurada ante la comisión provincial:
  - sequía: índice de balance de agua tipo SPEI de 3, 6 y 12 meses (ERA5, ver water_balance.py);
  - exceso de agua: el mismo índice en valores positivos y, si hay lote, agua detectada por radar Sentinel-1.
Lectura: un SPEI de −1,5 o menos (sequía severa o extrema) o de +1,5 o más (exceso) en 3 a 6 meses respalda el pedido.
"""
import research_connectors as c
import water_balance as wb

STEPS = [
    'El productor presenta una declaración jurada de daños ante el organismo provincial (comisión de emergencia agropecuaria o ministerio de producción), dentro del plazo que fija la provincia.',
    'La provincia declara la emergencia o el desastre por resolución o decreto, para una zona y un período determinados.',
    'La Comisión Nacional de Emergencias y Desastres Agropecuarios evalúa el pedido y el Ministerio nacional lo homologa por resolución publicada en el Boletín Oficial.',
    'Con el certificado de emergencia que emite la provincia, el productor accede a los beneficios ante ARCA y los bancos.',
]
BENEFITS = [
    'Emergencia: producción o capacidad de producción afectada en 50 % o más. Desastre: 80 % o más (Ley 26.509).',
    'Prórroga de vencimientos de impuestos nacionales y suspensión de juicios de cobro (ARCA), mientras dure la declaración.',
    'En desastre, exención de parte de los impuestos patrimoniales del período, según la normativa vigente.',
    'Prórroga de deudas y líneas de crédito especiales en bancos oficiales (Banco Nación y bancos provinciales).',
]
LINKS = [
    {'name': 'Ley 26.509 · Sistema Nacional de Emergencias Agropecuarias (texto actualizado)', 'url': 'https://www.argentina.gob.ar/normativa/nacional/norma-157271/actualizacion'},
    {'name': 'ARCA · Emergencia agropecuaria, normativa y beneficios', 'url': 'https://www.afip.gob.ar/actividadesAgropecuarias/herramientas-de-asistencia/emergencia-agropecuaria/ayuda/normativa.asp'},
    {'name': 'Boletín Oficial de la República Argentina (resoluciones de declaración)', 'url': 'https://www.boletinoficial.gob.ar'},
]


def reading(spei):
    s3, s6 = (spei.get('3') or {}).get('index'), (spei.get('6') or {}).get('index')
    worst = min([v for v in (s3, s6) if v is not None], default=None)
    best = max([v for v in (s3, s6) if v is not None], default=None)
    if worst is not None and worst <= -1.5:
        return 'sequía', f'El balance de agua muestra sequía severa o extrema (SPEI {worst:+.1f}): es un respaldo técnico para pedir la emergencia por sequía.'
    if best is not None and best >= 1.5:
        return 'exceso de agua', f'El balance de agua muestra exceso hídrico marcado (SPEI {best:+.1f}): respalda un pedido por anegamiento o inundación, junto con el agua detectada en el lote.'
    if worst is not None and worst <= -1:
        return 'sequía moderada', f'Hay sequía moderada (SPEI {worst:+.1f}); por sí sola no suele alcanzar para una declaración, conviene seguirla.'
    return 'sin señal', 'Los indicadores de agua no muestran hoy una sequía ni un exceso que respalden un pedido de emergencia.'


def analyze(lat, lon, polygon=None):
    errors = {}
    try:
        w = wb.water_balance(lat, lon)['data'] or {}
    except Exception as e:
        w, errors['balance'] = {}, type(e).__name__
    water = None
    if polygon:
        try:
            import radar
            rd = (radar.flooding(polygon, 60) or {}).get('data') or {}
            water = rd.get('latest')
        except Exception as e:
            errors['radar'] = type(e).__name__
    kind, text = reading(w.get('spei') or {})
    out = {'capability': 'ANALYSIS', 'kind': kind, 'reading': text, 'spei': w.get('spei'), 'last_month': w.get('last_month'),
           'radar_water': water, 'steps': STEPS, 'benefits': BENEFITS, 'links': LINKS, 'errors': errors,
           'note': 'DOTS no tiene un listado oficial de zonas declaradas: consultá el Boletín Oficial y el organismo de tu provincia.',
           'method': __doc__.split('\n\n', 1)[1].strip()}
    return c.envelope(out, 'multi', 'emergencia agropecuaria · respaldo técnico', 'ERA5 · Sentinel-1 · Ley 26.509',
                      'recibido' if w else 'sin dato', None if w else 'No respondió el balance de agua')
