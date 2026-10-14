import pasture_gpw as g


def test_summarize_and_ranges():
    rows = [{'year': y, 'gpp': 1000 + (y - 2000) * 10} for y in range(2000, 2025)]
    rows[-1]['gpp'] = 1500
    s = g.summarize(rows)
    assert s['n'] == 25 and s['last']['year'] == 2024 and s['rank_last'] == 1
    assert s['last']['class'] == 'muy bueno' and s['trend_pct'] > 0
    assert g.classify(0) == 'normal' and g.classify(-20) == 'malo' and g.classify(-10) == 'flojo'


def test_expression_shape():
    e = g.expression([[-28.56, -58.71], [-28.56, -58.69], [-28.54, -58.69]])
    assert e['expression']['values']['out']['functionInvocationValue']['functionName'] == 'Collection.map'
