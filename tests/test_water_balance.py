

def test_spei_loglogistic_is_monotonic_and_centered():
    import water_balance as wb
    ref = [-80, -55, -40, -32, -20, -15, -9, -4, 0, 3, 8, 12, 18, 25, 31, 40, 52, 66, 80, 95, 110, 130, -60, -25, 5, 15, 35, 60, -70, 20]
    vals = [wb.standardize(v, ref) for v in (-120, -50, 0, 50, 150)]
    assert vals == sorted(vals) and vals[0] < -1.5 and vals[-1] > 1.5
    assert abs(wb.standardize(sorted(ref)[15], ref)) < 0.3
    assert wb.loglogistic_fit([1] * 30) is None    # sin variación: cae al percentil empírico
