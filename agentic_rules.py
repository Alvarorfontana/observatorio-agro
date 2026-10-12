"""DOTS Agentic · reglas sobre los módulos del lote (v1.0).

Motor por reglas, sin modelos de lenguaje: cada conclusión cita el dato y el umbral que la dispara.
Lee los resultados que el panel ya calculó (NDVI, pasto y carga, lluvia SPI, probabilidades,
alertas, deforestación y carbono, costos) y los cruza entre sí. Si un módulo no está, no se infiere nada.

Salida: findings, metrics, recommendations (con prioridad) y la lista de módulos usados.
"""


def _n(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _money(v):
    return f"$ {abs(v):,.0f}".replace(',', '.') if v is not None else '—'


def evaluate(known):
    k = known if isinstance(known, dict) else {}
    F, M, R, used = [], [], [], []

    def rec(priority, text, why):
        R.append({'priority': priority, 'text': text, 'why': why})

    # ── vegetación ──
    nd = k.get('ndvi') or {}
    valid = [r for r in nd.get('series') or [] if r.get('status') == 'válida' and _n(r.get('ndvi_mean')) is not None]
    ndvi_last = drop = None
    if valid:
        used.append('ndvi')
        ndvi_last = _n(valid[-1]['ndvi_mean'])
        state = 'bajo' if ndvi_last < 0.3 else 'moderado' if ndvi_last < 0.5 else 'bueno'
        M.append({'variable': 'NDVI del lote', 'value': round(ndvi_last, 2), 'unit': '', 'kind': 'observado por satélite',
                  'reference': '<0,30 bajo · 0,30–0,50 moderado · >0,50 bueno', 'reading': f'vigor {state}'})
        if len(valid) >= 2:
            drop = round(max(_n(r['ndvi_mean']) for r in valid[:-1]) - ndvi_last, 2)
        txt = f"NDVI {ndvi_last:.2f} el {str(valid[-1].get('datetime', ''))[:10]} ({nd.get('sensor') or 'Sentinel-2'}): vigor {state}."
        if drop is not None and drop >= 0.1:
            txt += f' Cayó {drop:.2f} respecto del máximo de la serie.'
        if nd.get('fallback'):
            txt += ' Dato de respaldo MODIS 250 m: menos detalle que Sentinel-2.'
        F.append({'topic': 'Vegetación', 'status': 'observado', 'text': txt})

    # ── pasto y carga ──
    fo = k.get('forraje') or {}
    over_ev = None
    if _n(fo.get('growth_rate_30d')) is not None:
        used.append('forraje')
        ev_ha, cur = _n(fo.get('ev_ha')), _n(fo.get('current_load_ev_ha'))
        M.append({'variable': 'Crecimiento del pasto (30 días)', 'value': round(_n(fo['growth_rate_30d'])), 'unit': 'kg MS/ha/día',
                  'kind': 'calculado', 'reference': 'Modelo de Monteith con NDVI y radiación', 'reading': f"sostiene {ev_ha} EV/ha"})
        txt = f"El pasto crece {fo['growth_rate_30d']:.0f} kg MS/ha/día y sostiene {ev_ha} EV/ha"
        if fo.get('ev_lot') is not None:
            txt += f" ({fo['ev_lot']:.0f} EV en el lote)"
        if cur is not None and ev_ha:
            txt += f'. Carga actual {cur} EV/ha: {fo.get("load_balance")}'
            if cur > ev_ha * 1.1:
                area = _n((k.get('lot') or {}).get('areaHa')) or (fo['ev_lot'] / ev_ha if fo.get('ev_lot') and ev_ha else None)
                over_ev = round((cur - ev_ha) * area) if area else None
        F.append({'topic': 'Pasto y carga', 'status': 'calculado', 'text': txt + '.'})

    # ── lluvia y sequía ──
    spi = ((k.get('lluvia') or {}).get('spi') or {})
    spi3 = _n((spi.get('3') or {}).get('spi'))
    spi1 = _n((spi.get('1') or {}).get('spi'))
    if spi3 is not None:
        used.append('lluvia')
        M.append({'variable': 'SPI 3 meses (CHIRPS)', 'value': spi3, 'unit': '', 'kind': 'calculado',
                  'reference': '≤ −1 sequía · ≥ 1 húmedo', 'reading': spi['3'].get('class')})
        F.append({'topic': 'Lluvia', 'status': 'observado',
                  'text': f"Lluvia de los últimos 3 meses: {spi['3'].get('mm')} mm contra una normal de {spi['3'].get('normal')} mm (SPI {spi3:+.2f}, {spi['3'].get('class')})."})
    dry = spi3 is not None and spi3 <= -1

    # ── probabilidades ──
    st = k.get('estadistica') or {}
    wr = (st.get('ensemble') or {}).get('week_rain') or {}
    seas = st.get('seasonal') or []
    week_med = _n(wr.get('median'))
    if week_med is not None:
        used.append('estadistica')
        F.append({'topic': 'Pronóstico', 'status': 'pronosticado',
                  'text': f"Lluvia probable en 7 días: entre {wr.get('p10')} y {wr.get('p90')} mm (mediana {week_med:.0f} mm), según el conjunto de pronósticos."})
    dry_outlook = [s['period'] for s in seas[:3] if s.get('rain_reading') == 'más seco que lo normal']
    wet_outlook = [s['period'] for s in seas[:3] if s.get('rain_reading') == 'más lluvioso que lo normal']
    if seas:
        F.append({'topic': 'Perspectiva estacional', 'status': 'pronosticado',
                  'text': '; '.join(f"{s['period']}: {s.get('rain_reading')}" for s in seas[:3]) + '.'})

    # ── alertas ──
    al = (k.get('alertas') or {}).get('alerts') or []
    if k.get('alertas'):
        used.append('alertas')
    for a in al:
        if a.get('level') == 'alta':
            rec(1, f"{a['title']}: {a.get('action')}", f"Alerta alta · {a.get('detail')} ({a.get('source')})")
        else:
            F.append({'topic': 'Alerta', 'status': a.get('level'), 'text': f"{a['title']}. {a.get('detail')}"})

    # ── deforestación y carbono ──
    su = k.get('sustentabilidad') or {}
    de, cb = su.get('deforestation') or {}, su.get('carbon') or {}
    verdict = str(de.get('verdict') or '')
    if verdict and verdict != 'sin dato':
        used.append('sustentabilidad')
        F.append({'topic': 'Libre de deforestación', 'status': 'observado por satélite',
                  'text': f"{verdict[0].upper() + verdict[1:]} (corte {de.get('cutoff')}): cambio {de.get('tree_change_pp')} puntos de cobertura arbórea, {de.get('tree_loss_ha')} ha."})
        if 'requiere verificación' in verdict:
            rec(1, 'Antes de vender a un comprador que exija la norma europea (EUDR), revisar imágenes de alta resolución del lote y reunir la documentación del desmonte o del error de clasificación.',
                f"Pérdida de {de.get('tree_loss_ha')} ha, mayor que la variación normal del mapa (±{de.get('map_noise_pp')} puntos) y sostenida.")
        elif 'revisar' in verdict:
            rec(3, 'Revisar visualmente el lote año por año (botón ◧) para descartar error de clasificación.', f'Veredicto: {verdict}.')
    if _n(cb.get('soc_t_ha')) is not None:
        txt = f"Carbono orgánico del suelo {cb['soc_t_ha']} t C/ha en 0–30 cm (modelo global)."
        if cb.get('herd'):
            txt += f" El rodeo de {cb['herd']['heads']} cabezas emite unas {cb['herd']['co2e_t_year']:.0f} t CO₂e por año (IPCC Nivel 1)."
        F.append({'topic': 'Carbono', 'status': 'modelado', 'text': txt})

    # ── costos ──
    co = k.get('costos') or {}
    cm, cl = co.get('margin') or {}, co.get('logistics') or {}
    net, gross, price = _n(cm.get('net')), _n(cm.get('gross')), _n((co.get('inputs') or {}).get('price_kg'))
    if net is not None or cl:
        used.append('costos')
    if net is not None:
        be = _n(cm.get('breakeven_price_kg'))
        txt = f"Margen bruto estimado {'−' if net < 0 else ''}{_money(net)}"
        if cm.get('net_ha') is not None:
            txt += f" ({'−' if cm['net_ha'] < 0 else ''}{_money(cm['net_ha'])}/ha)"
        if be and price:
            safety = (price - be) / price * 100
            txt += f'. Precio de equilibrio {_money(be)}/kg: el precio puede bajar {safety:.0f} % antes de perder plata' if safety > 0 \
                else f'. Precio de equilibrio {_money(be)}/kg, por encima del precio cargado'
            M.append({'variable': 'Margen de seguridad de precio', 'value': round(safety), 'unit': '%', 'kind': 'calculado',
                      'reference': '<10 % ajustado · >25 % holgado', 'reading': 'ajustado' if safety < 10 else 'holgado' if safety > 25 else 'intermedio'})
            if safety < 10:
                rec(2, 'Revisar costos o precio de venta: el margen de seguridad es menor al 10 %.', f'Precio de equilibrio {_money(be)}/kg contra {_money(price)}/kg.')
        F.append({'topic': 'Costos', 'status': 'calculado', 'text': txt + '.'})
        if net < 0:
            rec(1, 'Con los valores cargados la venta da pérdida: revisar precio, peso de venta, destino o costos fijos antes de cerrar.', f'Margen {_money(net)} negativo.')
    if cl.get('km') is not None:
        fr = _n(cm.get('freight'))
        share = fr / gross * 100 if fr is not None and gross else None
        F.append({'topic': 'Logística', 'status': 'calculado',
                  'text': f"Destino a {cl['km']:.0f} km por camino" + (f", {cl['hours']:.1f} h de viaje" if cl.get('hours') else '')
                          + (f"; el flete es el {share:.1f} % del ingreso bruto" if share is not None else '') + '.'})
        if share is not None and share > 8:
            rec(2, 'El flete pesa más del 8 % del ingreso: comparar con un destino más cercano o completar jaulas.', f'Flete {share:.1f} % del ingreso bruto.')
        if cl.get('hours') and cl['hours'] > 8:
            rec(3, 'Viaje de más de 8 horas: planificar descanso, agua y desbaste; considerar la ley de bienestar animal en tránsito.', f"{cl['hours']:.1f} h por camino.")

    # ── cruces entre módulos ──
    if over_ev and (dry or dry_outlook):
        why = (f'SPI 3 meses {spi3:+.2f}' if dry else 'perspectiva más seca que lo normal en ' + ', '.join(dry_outlook))
        rec(1, f'Bajar la carga o suplementar: sobran unas {over_ev} EV para lo que crece el pasto y viene seco.', f'{why}; carga por encima de la receptividad.')
    elif over_ev:
        rec(2, f'Ajustar la carga: hay unas {over_ev} EV por encima de lo que crece el pasto.', 'Carga actual más de 10 % sobre la receptividad estimada.')
    if dry and drop is not None and drop >= 0.1:
        rec(1, 'Sequía y caída del vigor al mismo tiempo: priorizar agua de bebida, reservas de forraje y destete anticipado si hay cría.',
            f'SPI 3 meses {spi3:+.2f} y NDVI −{drop:.2f}.')
    elif dry:
        rec(2, 'Lluvia por debajo de lo normal: revisar reservas de agua y forraje.', f'SPI 3 meses {spi3:+.2f}.')
    if wet_outlook and spi1 is not None and spi1 >= 1:
        rec(2, 'Mes muy lluvioso y perspectiva húmeda: revisar bajos anegables, caminos y sanidad de pezuñas.',
            f"SPI 1 mes {spi1:+.2f}; perspectiva más lluviosa en {', '.join(wet_outlook)}.")
    if ndvi_last is not None and ndvi_last >= 0.5 and fo and not over_ev and not dry:
        rec(3, 'Buen estado del pasto y sin señal de sequía: oportunidad para reservar forraje o aumentar la carga con cuidado.',
            f'NDVI {ndvi_last:.2f} y carga dentro de la receptividad.')

    R.sort(key=lambda r: r['priority'])
    return {'findings': F, 'metrics': M, 'recommendations': R, 'modules': used}
