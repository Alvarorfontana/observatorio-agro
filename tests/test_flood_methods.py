from flood_methods import adaptive_water_change, otsu_threshold_db, reference_confusion


def test_otsu_separates_clear_classes():
    samples = [0.001] * 60 + [0.1] * 60
    t = otsu_threshold_db(samples)
    assert -31 < t < -9


def test_adaptive_change_with_fixed_threshold():
    result = adaptive_water_change([0.1, 0.1], [0.001, 0.1], -18)
    assert result["counts"]["new_water"] == 1


def test_reference_metrics():
    m = reference_confusion([True, True, False, False], [True, False, True, False])
    assert m["precision"] == .5
    assert m["recall"] == .5
    assert m["iou"] == .3333
