import json
import pytest
import research_connectors as c


def test_coordinates_from_lat_lon():
    assert c.coordinates({'lat': ['-28.5'], 'lon': ['-59.0']}) == (-28.5, -59.0)


def test_coordinates_fallback_to_polygon_centroid():
    poly = json.dumps([[-28.50, -59.05], [-28.50, -59.04], [-28.51, -59.04], [-28.51, -59.05]])
    lat, lon = c.coordinates({'polygon': [poly]})
    assert lat == pytest.approx(-28.505) and lon == pytest.approx(-59.045)


def test_coordinates_without_lat_lon_or_polygon_fails():
    with pytest.raises(ValueError):
        c.coordinates({'lat': [None], 'lon': [None]})
