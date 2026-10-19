"""Pruebas unitarias del núcleo de cambios SAR, sin red."""
import pytest
from flood_sar_change import classify_water, compare_scenes, quality_gate


def test_threshold():
    assert classify_water(0.001) is True
    assert classify_water(0.1) is False
    assert classify_water(None) is None
    assert classify_water(-1) is None


def test_new_and_receded_water():
    result = compare_scenes(
        before=[0.1, 0.001, 0.1, 0.001],
        after=[0.001, 0.001, 0.1, 0.1],
        pixel_area_m2=100,
    )
    assert result["counts"] == {
        "persistent_water": 1, "new_water": 1,
        "receded_water": 1, "persistent_land": 1,
    }
    assert result["area_ha"]["new_water"] == 0.01
    assert result["status"] == "ESTIMATE_NOT_VALIDATED"


def test_nodata_excluded_in_pairs():
    result = compare_scenes([0.1, None, 0.001], [0.001, 0.1, None])
    assert result["paired_valid_pixels"] == 1
    assert result["coverage_fraction"] == 0.3333
    assert not quality_gate(result)["reviewable"]


def test_no_valid_pairs_rejected():
    with pytest.raises(ValueError):
        compare_scenes([None], [0.1])


def test_mismatched_grids_rejected():
    with pytest.raises(ValueError):
        compare_scenes([0.1], [0.1, 0.2])


def test_no_automatic_alerts():
    result = compare_scenes([0.1], [0.001])
    assert quality_gate(result)["automatic_alert_allowed"] is False
