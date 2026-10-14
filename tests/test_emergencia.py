import emergencia as em


def test_reading():
    assert em.reading({'3': {'index': -1.8}, '6': {'index': -1.2}})[0] == 'sequía'
    assert em.reading({'3': {'index': 1.7}, '6': {'index': 0.5}})[0] == 'exceso de agua'
    assert em.reading({'3': {'index': -1.1}})[0] == 'sequía moderada'
    assert em.reading({})[0] == 'sin señal'
