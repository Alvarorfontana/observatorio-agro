"""herd v1.0 — módulo Ganado: rodeo por lote, carga, agua, calor y valor de referencia.

Todo con reglas declaradas sobre datos abiertos; los coeficientes son orientativos y se informan:
  - Equivalente vaca (EV): 1 EV = vaca de 400 kg; cada animal = (peso / 400)^0,75 (peso metabólico).
    Consumo de 1 EV = 10 kg de materia seca por día (igual que el módulo de pasto).
  - Oferta de pasto: crecimiento de los últimos 30 días del lote (Sentinel-2 + radiación, modelo de Monteith)
    × superficie × factor de uso.
  - Agua de bebida: % del peso vivo por día según la máxima pronosticada (guía orientativa):
    8 % con menos de 25 °C, 10 % hasta 30 °C, 12 % hasta 35 °C y 14 % por encima.
  - Calor: índice de temperatura y humedad (ITH/THI) horario del pronóstico; umbrales del Livestock
    Weather Safety Index: 72 alerta, 79 peligro, 84 emergencia.
  - Valor: kilos por categoría × precio mínimo y máximo del día del Mercado Agroganadero de Cañuelas.
No reemplaza el criterio del productor ni del veterinario.
"""
from concurrent.futures import ThreadPoolExecutor

import research_connectors as c

CATS = {  # clave: (nombre, peso típico kg, categoría del Mercado Agroganadero)
    'vaca': ('Vacas', 420, 'Vacas'), 'vaquillona': ('Vaquillonas', 320, 'Vaquillonas'),
    'novillo': ('Novillos', 440, 'Novillos'), 'novillito': ('Novillitos', 330, 'Novillitos'),
    'ternero': ('Terneros y terneras', 180, None), 'toro': ('Toros', 700, 'Toros'),
}
EV_KG = 400.0
EV_MS_DAY = 10.0
FORECAST = 'https://api.open-meteo.com/v1/forecast'


def clean_herd(rows):
    out = []
    for r in rows or []:
        cat = str(r.get('cat') or '').lower()
        if cat not in CATS:
            continue
        try:
            heads = int(float(r.get('heads') or 0))
            w = float(r.get('weight') or CATS[cat][1])
        except (TypeError, ValueError):
            continue
        if heads <= 0 or not 30 <= w <= 1200 or heads > 100000:
            continue
        out.append({'cat': cat, 'name': CATS[cat][0], 'heads': heads, 'weight': round(w)})
    return out


def ev(weight):
    return (weight / EV_KG) ** 0.75


def water_pct(tmax):
    return 0.08 if tmax < 25 else 0.10 if tmax < 30 else 0.12 if tmax < 35 else 0.14


def thi(t, rh):
    return 0.8 * t + rh / 100 * (t - 14.4) + 46.4


def thi_class(v):
    return 'emergencia' if v >= 84 else 'peligro' if v >= 79 else 'alerta' if v >= 72 else 'normal'


def weather(lat, lon):
    js = c._get(FORECAST, {'latitude': lat, 'longitude': lon, 'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum',
                           'hourly': 'temperature_2m,relative_humidity_2m', 'forecast_days': 7, 'timezone': 'auto'}, timeout=20).json()
    d, h = js.get('daily') or {}, js.get('hourly') or {}
    by = {}
    for t, tc, rh in zip(h.get('time') or [], h.get('temperature_2m') or [], h.get('relative_humidity_2m') or []):
        if tc is None or rh is None:
            continue
        by.setdefault(t[:10], []).append(thi(tc, rh))
    days = []
    for i, day in enumerate(d.get('time') or []):
        tmax = (d.get('temperature_2m_max') or [None])[i]
        vals = by.get(day) or []
        mx = round(max(vals), 1) if vals else None
        days.append({'date': day, 'tmax': tmax, 'tmin': (d.get('temperature_2m_min') or [None])[i],
                     'rain': (d.get('precipitation_sum') or [None])[i], 'thi_max': mx,
                     'thi_class': thi_class(mx) if mx is not None else None,
                     'thi_hours_72': sum(1 for v in vals if v >= 72)})
    return days


def analyze(lat, lon, herd, area_ha=None, forage=None, market=None):
    rows = clean_herd(herd)
    if not rows:
        raise ValueError('Cargá al menos una categoría con cabezas')
    heads = sum(r['heads'] for r in rows)
    kg = sum(r['heads'] * r['weight'] for r in rows)
    evs = sum(r['heads'] * ev(r['weight']) for r in rows)
    for r in rows:
        r['ev'] = round(r['heads'] * ev(r['weight']), 1)
        r['kg_total'] = r['heads'] * r['weight']
    errors = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        fw = pool.submit(weather, lat, lon)
        fm = pool.submit(_market) if market is None else None
        try:
            days = fw.result()
        except Exception as e:
            days = []; errors['pronóstico'] = type(e).__name__
        if fm:
            try:
                market = fm.result(timeout=20)
            except Exception as e:
                market = None; errors['precios'] = type(e).__name__
    demand = evs * EV_MS_DAY
    out = {'capability': 'ANALYSIS', 'herd': rows, 'heads': heads, 'kg_total': round(kg), 'ev_total': round(evs, 1),
           'demand_kg_ms_day': round(demand), 'area_ha': area_ha, 'errors': errors}
    # carga y pasto
    if area_ha:
        out['ev_ha'] = round(evs / area_ha, 2)
    f = forage or {}
    if f.get('growth_rate_30d') is not None and area_ha:
        use = float(f.get('use') or 0.5)
        supply = f['growth_rate_30d'] * area_ha * use
        out['forage'] = {'growth_rate_30d': f['growth_rate_30d'], 'use': use, 'supply_kg_ms_day': round(supply),
                         'capacity_ev': round(supply / EV_MS_DAY, 1), 'balance_kg_ms_day': round(supply - demand),
                         'balance_30d_kg_ms': round((supply - demand) * 30), 'kind': f.get('kind_label'),
                         'ratio': round(demand / supply, 2) if supply > 0 else None}
        r = out['forage']['ratio']
        out['forage']['reading'] = ('sin crecimiento de pasto medido' if r is None else
                                    'el rodeo come más de lo que crece el pasto: revisar carga o suplementar' if r > 1.1 else
                                    'el rodeo está en equilibrio con lo que crece el pasto' if r >= 0.7 else
                                    'sobra pasto: hay margen para más carga o para reservar')
    # agua y calor
    if days:
        wd = []
        for d in days:
            if d['tmax'] is None:
                continue
            liters = sum(r['heads'] * r['weight'] * water_pct(d['tmax']) for r in rows)
            wd.append({**d, 'water_l': round(liters), 'water_l_head': round(liters / heads, 1)})
        out['days'] = wd
        if wd:
            out['water_max_l_day'] = max(x['water_l'] for x in wd)
            out['water_week_l'] = sum(x['water_l'] for x in wd)
        worst = max((x for x in wd if x.get('thi_max') is not None), key=lambda x: x['thi_max'], default=None)
        out['heat'] = {'worst_day': worst['date'] if worst else None, 'worst_thi': worst['thi_max'] if worst else None,
                       'worst_class': worst['thi_class'] if worst else None,
                       'days_alert': sum(1 for x in wd if (x.get('thi_max') or 0) >= 72),
                       'days_danger': sum(1 for x in wd if (x.get('thi_max') or 0) >= 79)}
    # valor
    if market and market.get('categories'):
        prices = {x['category']: x for x in market['categories']}
        vrows, lo, hi, missing = [], 0.0, 0.0, []
        for r in rows:
            p = prices.get(CATS[r['cat']][2] or '')
            if not p:
                missing.append(r['name']); continue
            a, b = r['kg_total'] * p['min'], r['kg_total'] * p['max']
            lo += a; hi += b
            vrows.append({'name': r['name'], 'kg': r['kg_total'], 'min': p['min'], 'max': p['max'], 'value_min': round(a), 'value_max': round(b)})
        out['value'] = {'rows': vrows, 'min': round(lo), 'max': round(hi), 'missing': missing, 'date': market.get('date'),
                        'source': 'Mercado Agroganadero de Cañuelas', 'unit': '$'}
    out['advice'] = advice(out)
    out['method'] = __doc__.split('\n\n', 1)[1].strip()
    return c.envelope(out, FORECAST, 'rodeo, carga, agua y calor', 'DOTS · Open-Meteo · Mercado Agroganadero')


def _market():
    import costs
    return costs.mag_prices()


def advice(o):
    a = []
    f = o.get('forage') or {}
    if f.get('ratio') is not None:
        if f['ratio'] > 1.1:
            a.append(f"Falta pasto: el rodeo consume {o['demand_kg_ms_day']:,} kg de materia seca por día y el lote produce unos {f['supply_kg_ms_day']:,}. "
                     f"La carga que sostiene hoy es de {f['capacity_ev']} EV.".replace(',', '.'))
        elif f['ratio'] < 0.7:
            a.append('Sobra pasto respecto del consumo: se puede pensar en más carga, en otra categoría o en hacer reservas.')
    h = o.get('heat') or {}
    if h.get('days_danger'):
        a.append(f"Calor: {h['days_danger']} día(s) con ITH de peligro en la semana. Asegurar sombra y agua, y no mover ni trabajar hacienda en las horas de más calor.")
    elif h.get('days_alert'):
        a.append(f"Calor moderado: {h['days_alert']} día(s) con ITH de alerta. Revisar sombra y bebederos.")
    if o.get('water_max_l_day'):
        a.append(f"Agua: el día de más calor el rodeo necesita unos {o['water_max_l_day']:,} litros. Verificar caudal y capacidad de los bebederos.".replace(',', '.'))
    return a
