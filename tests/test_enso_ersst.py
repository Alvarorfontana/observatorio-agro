import pytest
np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
xr = pytest.importorskip("xarray")
from tools.build_enso_ersst import build

def test_ersst_realistic_synthetic_fixture_only(tmp_path):
    # Dataset artificial exclusivamente para probar cálculos, nunca se publica.
    times = pd.date_range("1991-01-01", periods=372, freq="MS")
    lat = np.array([-10., -5., 0., 5., 10.])
    lon = np.arange(120., 281., 10.)
    seasonal = np.tile(np.arange(12, dtype=float), 31)
    vals = np.broadcast_to(seasonal[:, None, None], (372, len(lat), len(lon))).copy()
    vals[360:] += 1.5
    path = tmp_path / "sst.nc"
    xr.Dataset({"sst": (("time", "lat", "lon"), vals)}, coords={"time": times, "lat": lat, "lon": lon}).to_netcdf(path)
    result = build(path, since="1991-01")
    assert result["baseline"] == "1991-2020"
    assert len(result["months"]) == 372
    assert len(result["hovmoller"]["values"]) == 372
    assert result["indices"]["nino34"][-1] == 1.5
    assert result["maps"]["months"][0] == "1991-01"
