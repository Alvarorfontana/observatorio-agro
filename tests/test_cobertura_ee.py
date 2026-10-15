import json
import cobertura_ee as ce

POLY = [[-28.50, -59.05], [-28.50, -59.00], [-28.55, -59.00], [-28.55, -59.05]]


def test_dw_shares_orders_and_names():
    rows = ce.dw_shares({'label': {'4': 600, '2': 300, '0': 100}})
    assert [r['key'] for r in rows] == ['crops', 'grass', 'water'] and rows[0]['pct'] == 60.0
    assert ce.dw_shares({'label_mode': {'1': 5}})[0]['name'] == 'Árboles'
    assert ce.dw_shares({}) == []


def test_change_reading():
    rows = [{'year': y, 'similarity': s, 'changed_pct': p} for y, s, p in
            [(2018, .93, 2), (2019, .94, 1), (2020, .92, 3), (2021, .61, 48), (2022, .93, 2)]]
    text, year = ce.change_reading(rows)
    assert year == 2021 and '2020 y 2021' in text and '48 %' in text
    calm = [{'year': y, 'similarity': .93, 'changed_pct': 1} for y in range(2018, 2024)]
    assert ce.change_reading(calm)[1] is None


def test_expressions_are_json_and_use_assets():
    dw = json.dumps(ce.dw_expression(POLY, '2026-07-01', '2026-10-01'))
    emb = json.dumps(ce.emb_expression(POLY, 2021))
    assert ce.DW in dw and 'ImageCollection.mode' in dw and 'frequencyHistogram' in dw
    assert ce.EMB in emb and '2020-01-01' in emb and '2022-01-01' in emb and 'Image.lt' in emb
