import goes


def test_geometry_and_grid():
    a, b, h = 6378137.0, 6356752.31414, 35786023.0
    assert goes.latlon_to_xy(0, -75.2, -75.2, h + a, a, b) == (0.0, 0.0)
    x, y = goes.latlon_to_xy(-34.6, -58.4, -75.2, h + a, a, b)
    assert x > 0 and y < 0                       # al este y al sur del punto bajo el satélite
    assert goes.latlon_to_xy(0, 60, -75.2, h + a, a, b) is None
    assert goes.index_of(0.5, 0.0, 0.1, 10) == 5 and goes.index_of(2.0, 0.0, 0.1, 10) is None
    assert len(goes.grid_cells((-60, -40, -58, -38), 1)) == 4
    assert round(goes.km((-34.6, -58.4), (-31.4, -64.2))) in range(640, 660)
