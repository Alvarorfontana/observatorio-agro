import research_connectors as c
P=[[-28.51,-59.01],[-28.49,-59.01],[-28.49,-58.99],[-28.51,-58.99]]
def test_bbox():
    b=c.polygon_bbox(P); assert b==(-59.01,-28.51,-58.99,-28.49)
def test_inside():
    assert c.point_in_polygon(-28.50,-59.00,P)
    assert not c.point_in_polygon(-28.60,-59.00,P)
