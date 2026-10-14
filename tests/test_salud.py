import salud as s


def test_thermal_curve():
    assert s.thermal(17) == 0 and s.thermal(35) == 0
    assert s.thermal(29) > 0.95 and s.thermal(22) < s.thermal(27)


def test_heatwave_and_place():
    days = [('d1', 36, 23), ('d2', 37, 24), ('d3', 36, 23), ('d4', 30, 18), ('d5', 36, 23)]
    assert s.heatwave(days, 35, 22) == [{'from': 'd1', 'to': 'd3', 'days': 3}]
    t = [f'2026-10-{i:02d}' for i in range(1, 31)] + [f'2026-11-{i:02d}' for i in range(1, 17)]
    daily = {'time': t, 'temperature_2m_mean': [28] * 46, 'temperature_2m_max': [36] * 46, 'temperature_2m_min': [23] * 46, 'precipitation_sum': [5] * 46}
    out = s.analyze_place(daily, '2026-10-31')
    assert out['dengue_class'] in ('alto', 'muy alto') and out['rain_30d_mm'] == 150
    assert out['heat_class'] == 'ola de calor' and out['heat_threshold']['fixed']
