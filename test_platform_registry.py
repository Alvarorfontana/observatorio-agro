import os
import research_connectors as c

def test_registry_distinguishes_protocols():
    r=c.platform_registry(); by={x['id']:x for x in r['sources']}
    assert by['nasa-gibs']['protocol']=='WMS/WMTS'
    assert by['copernicus-stac']['protocol']=='STAC'
    assert by['nasa-power']['protocol']=='REST'
    assert by['sentinel-hub']['capability']=='raster-analysis'
    assert by['conae-saocom']['status']=='NOT_CERTIFIED'

def test_polygon_bbox_and_inside():
    p=[[-28.51,-59.05],[-28.51,-59.03],[-28.49,-59.03],[-28.49,-59.05]]
    assert c.polygon_bbox(p)==(-59.05,-28.51,-59.03,-28.49)
    assert c.point_in_polygon(-28.50,-59.04,p)
    assert not c.point_in_polygon(-28.60,-59.04,p)
