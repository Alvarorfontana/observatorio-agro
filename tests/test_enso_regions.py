"""Contract tests for official NOAA monthly SST index parsing.

Run: python -m pytest tests/test_enso_regions.py
"""
from enso_data_api import _parse_sstoi
import pytest


def test_regions_parse_and_sort():
    rows = ["YR MON NINO1+2 SST ANOM NINO3 SST ANOM NINO4 SST ANOM NINO3.4 SST ANOM"]
    for year in range(2010, 2021):
        for month in range(1, 13):
            rows.append(f"{year} {month} 24.0 0.1 26.0 0.2 28.0 0.3 27.0 0.4")
    result = _parse_sstoi("\n".join(reversed(rows)))
    assert len(result) == 132
    assert result[0]["month"] == "2010-01"
    assert result[-1]["month"] == "2020-12"
    assert result[-1]["nino12"] == pytest.approx(0.1)
    assert result[-1]["nino3"] == pytest.approx(0.2)
    assert result[-1]["nino4"] == pytest.approx(0.3)
    assert result[-1]["nino34"] == pytest.approx(0.4)


def test_regions_reject_duplicate_month():
    row = "2010 1 24 0.1 26 0.2 28 0.3 27 0.4"
    with pytest.raises(ValueError):
        _parse_sstoi("\n".join([row] * 120))


def test_regions_reject_truncated():
    with pytest.raises(ValueError):
        _parse_sstoi("2010 1 24 0.1 26 0.2 28 0.3 27 0.4")
