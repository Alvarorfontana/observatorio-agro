import herd


def test_clean_and_ev():
    rows = herd.clean_herd([{'cat': 'vaca', 'heads': 100, 'weight': 400}, {'cat': 'x', 'heads': 3}, {'cat': 'toro', 'heads': 0}])
    assert rows == [{'cat': 'vaca', 'name': 'Vacas', 'heads': 100, 'weight': 400}]
    assert abs(herd.ev(400) - 1) < 1e-9


def test_thi():
    assert herd.thi_class(herd.thi(35, 60)) in ('peligro', 'emergencia')
    assert herd.thi_class(herd.thi(20, 50)) == 'normal'


def test_analyze(monkeypatch):
    monkeypatch.setattr(herd, 'weather', lambda la, lo: [{'date': '2026-10-15', 'tmax': 33, 'tmin': 20, 'rain': 0, 'thi_max': 80.2, 'thi_class': 'peligro', 'thi_hours_72': 6},
                                                         {'date': '2026-10-16', 'tmax': 22, 'tmin': 10, 'rain': 5, 'thi_max': 65, 'thi_class': 'normal', 'thi_hours_72': 0}])
    market = {'date': '13/10/2026', 'categories': [{'category': 'Vacas', 'min': 2100.0, 'max': 4100.0}]}
    out = herd.analyze(-28.5, -58.7, [{'cat': 'vaca', 'heads': 100, 'weight': 400}, {'cat': 'ternero', 'heads': 50, 'weight': 180}],
                       area_ha=100, forage={'growth_rate_30d': 15, 'use': 0.5, 'kind_label': 'Pastizal natural'}, market=market)['data']
    assert out['heads'] == 150 and out['ev_total'] > 100
    assert out['forage']['supply_kg_ms_day'] == 750 and out['forage']['ratio'] > 1.1
    assert out['days'][0]['water_l'] == round((100 * 400 + 50 * 180) * 0.12)
    assert out['heat']['days_danger'] == 1
    assert out['value']['min'] == 100 * 400 * 2100 and 'Terneros y terneras' in out['value']['missing']
    assert any('Falta pasto' in a for a in out['advice'])
