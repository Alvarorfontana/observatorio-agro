"""nitrogen v1.0 — balance de nitrógeno orientativo (ideas de DSSAT y del modelo RothC).

Demanda del cultivo por rinde objetivo, aporte del suelo por mineralización del nitrógeno orgánico
(SOC y relación C:N), crédito del cultivo anterior y eficiencia del fertilizante. Devuelve la dosis
sugerida de N y su equivalente en urea. Es ORIENTATIVO: no reemplaza un análisis de suelo (nitrato
0-60 cm) ni la recomendación oficial (INTA / laboratorio). No incluye lavado, volatilización,
fijación simbiótica medida ni nitrógeno mineral medido en el lote.
"""

# Extracción total de N por tonelada de grano (kg N/t), valores de referencia FAO/INTA.
N_UPTAKE = {'maiz': 25, 'soja': 0, 'trigo': 27, 'girasol': 32, 'sorgo': 25, 'pastura': 0, 'alfalfa': 0}
# Crédito de N que deja el cultivo anterior (kg N/ha): leguminosas y pasturas aportan, los gramíneos poco.
PREV_CREDIT = {'soja': 30, 'alfalfa': 80, 'pastura': 40, 'maiz': 0, 'trigo': 0, 'girasol': 0, 'sorgo': 0}
FERT_EFFICIENCY = 0.55      # fracción del N aplicado que el cultivo aprovecha
MIN_RATE = 0.022            # fracción anual del N orgánico que se mineraliza (orden RothC)
UREA_N = 0.46               # contenido de N de la urea


def organic_n_kg_ha(soc_gkg, bd=1.3, depth_cm=30, cn=10):
    """N orgánico del suelo (kg N/ha) desde el carbono orgánico, la densidad aparente y la relación C:N."""
    if soc_gkg is None:
        return None
    soc_t_ha = soc_gkg * bd * depth_cm * 0.1     # t C/ha (SOC × DA × profundidad × 0,1)
    return round(soc_t_ha / cn * 1000)


def mineralization(soc_gkg, bd=1.3, depth_cm=30, tmean_c=15, ndays=365):
    """N que el suelo puede liberar por mineralización en el período (kg N/ha). Ajuste por temperatura."""
    on = organic_n_kg_ha(soc_gkg, bd, depth_cm)
    if on is None:
        return None
    climate = 0.6 + 0.4 * min(max(tmean_c or 0, 0), 30) / 30
    return round(on * MIN_RATE * climate * ndays / 365)


def demand(crop, yield_t_ha):
    """N que demanda el cultivo para el rinde objetivo (kg N/ha). None si falta el rinde; 0 en leguminosas."""
    rate = N_UPTAKE.get(crop, 0)
    if rate == 0:
        return 0
    if yield_t_ha is None:
        return None
    return round(rate * yield_t_ha)


def recommend(crop, yield_t_ha=None, soc_gkg=None, bd=1.3, depth_cm=30, tmean_c=15,
              prev_crop=None, soil_n_kg_ha=None):
    """Dosis de N sugerida = (demanda − aporte del suelo) / eficiencia. Orientativa."""
    d = demand(crop, yield_t_ha)
    supply = mineralization(soc_gkg, bd, depth_cm, tmean_c)
    credit = PREV_CREDIT.get(prev_crop, 0)
    available = (supply or 0) + credit + (soil_n_kg_ha or 0)
    note = None
    if d is None:
        dose = urea = None
        note = 'Falta el rinde objetivo para estimar la demanda'
    elif d == 0:
        dose = urea = 0
        note = 'Cultivo que fija nitrógeno (leguminosa): la dosis se define por análisis de suelo'
    else:
        dose = round(max(0, d - available) / FERT_EFFICIENCY)
        urea = round(dose / UREA_N) if dose else 0
    out = {'crop': crop, 'yield_t_ha': yield_t_ha, 'demand_kg_ha': d,
           'supply_from_soil_kg_ha': supply, 'prev_crop_credit_kg_ha': credit,
           'soil_n_test_kg_ha': soil_n_kg_ha, 'available_kg_ha': round(available),
           'dose_kg_ha': dose, 'urea_kg_ha': urea, 'note': note}
    if dose is not None and dose > 0:
        out['reading'] = (f"{crop}: demanda {d} kg N/ha (rinde {yield_t_ha} t/ha), el suelo aportaría ~{round(available)} kg N/ha "
                          f"(mineralización {supply} + crédito {credit}); dosis sugerida {dose} kg N/ha (≈{urea} kg de urea). Orientativo: "
                          'conviene ajustar con un análisis de nitrato 0-60 cm.')
    elif d == 0:
        out['reading'] = f"{crop}: cultivo que fija nitrógeno; no se espera respuesta a la fertilización nitrogenada."
    else:
        out['reading'] = (f"{crop}: el suelo cubriría la demanda estimada de {d} kg N/ha"
                          if d is not None else f"{crop}: falta el rinde objetivo para estimar la demanda.")
    return out
