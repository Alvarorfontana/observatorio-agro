import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import nino34_verificar as nv

RESPALDO = os.path.join(os.path.dirname(__file__), '..', 'public', 'nino-diario', 'nino34-respaldo.json')


def test_respaldo_real_pasa():
    anio, n, v = nv.verificar(json.load(open(RESPALDO, encoding='utf-8')))
    assert anio == '2026' and n > 200 and 20 < v < 33


@pytest.mark.parametrize('malo', [{}, [], [{'name': '1991-2020', 'data': [26] * 366}],
                                  [{'name': '1991-2020', 'data': [26] * 366}, {'name': '2026', 'data': [99, None]}]])
def test_rechaza_datos_rotos(malo):
    with pytest.raises(ValueError):
        nv.verificar(malo)
