import temporales as tp


def _datos(caida=0.7, vientos=None):
    t = [f"2026-10-{12 + i // 24:02d}T{i % 24:02d}:00" for i in range(144)]
    P = [1015 if i < 60 else 1015 - (i - 60) * caida for i in range(144)]
    v = vientos or [10] * 144
    return {'hourly': {'time': t, 'pressure_msl': P, 'wind_speed_10m': v, 'wind_direction_10m': [135] * 144, 'wind_gusts_10m': [x * 1.5 for x in v]},
            'daily': {'time': [f'2026-10-{d}' for d in range(12, 18)], 'temperature_2m_max': [30, 31, 33, 20, 18, 22],
                      'temperature_2m_min': [15, 16, 18, 10, 8, 9], 'wind_gusts_10m_max': [30, 40, 85, 50, 30, 20], 'precipitation_sum': [0] * 6}}


def test_frentes_detecta_ciclogenesis_frente_y_rafagas():
    a = tp.frentes(_datos(), hoy='2026-10-13T00')
    tipos = {e['tipo']: e['nivel'] for e in a['eventos']}
    assert tipos == {'Ciclogénesis': 'Alerta', 'Frente frío': 'Alerta', 'Ráfagas': 'Alerta'}
    assert a['nivel'] == 'Alerta' and a['caida24h'] == 16.8


def test_frentes_tiempo_tranquilo():
    d = _datos(caida=0.0)
    d['daily']['temperature_2m_max'] = [25] * 6; d['daily']['wind_gusts_10m_max'] = [30] * 6
    a = tp.frentes(d, hoy='2026-10-13T00')
    assert a['nivel'] == 'Normal' and a['eventos'] == []


def test_sudestada_niveles():
    calma = tp.sudestada(_datos(), hoy='2026-10-13T00')
    assert calma['nivel'] == 'Normal'
    v = [10] * 144
    for i in range(40, 56): v[i] = 35          # 16 h de sudeste a 35 km/h
    mod = tp.sudestada(_datos(vientos=v), hoy='2026-10-13T00')
    assert mod['nivel'] == 'Atención' and mod['horas'] == 16 and 'sudeste' in mod['texto']
    for i in range(40, 56): v[i] = 50
    assert tp.sudestada(_datos(vientos=v), hoy='2026-10-13T00')['nivel'] == 'Alerta'
    for i in range(40, 50): v[i] = 50; v[50:56] = [10] * 6     # sólo 10 h: no alcanza
    assert tp.sudestada(_datos(vientos=v), hoy='2026-10-13T00')['nivel'] == 'Normal'
