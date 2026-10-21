import pytest
pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("xarray")
"""Pruebas unitarias sin descargar archivos externos."""
import numpy as np
import pandas as pd
import xarray as xr
from tools.build_enso_atmosphere import anomaly, box, series

def test_anomaly_removes_monthly_climatology():
    time = pd.date_range("1991-01-01", periods=360, freq="MS")
    values = np.tile(np.arange(12, dtype=float), 30)
    da = xr.DataArray(values, coords={"time": time}, dims=["time"])
    result = anomaly(da)
    assert np.allclose(result.values, 0)

def test_box_weighted_regional_mean():
    da = xr.DataArray(np.full((2, 3, 3), 5.0),
                      coords={"time": pd.date_range("2020-01-01", periods=2, freq="MS"),
                              "lat": [-5, 0, 5], "lon": [160, 180, 200]},
                      dims=["time", "lat", "lon"])
    values = box(da, -5, 5, 160, 200)
    assert series(values)["values"] == [5.0, 5.0]
