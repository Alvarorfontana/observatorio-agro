"""Verifica la serie diaria Niño 3.4 de Climate Reanalyzer antes de guardarla.

Uso: python scripts/nino34_verificar.py entrada.json salida.json
Se guarda sólo si trae la normal 1991-2020 y el año en curso con datos plausibles (20 a 33 °C);
si no, termina con error y queda la copia anterior.
"""
import json
import re
import sys


def verificar(j):
    if not isinstance(j, list):
        raise ValueError('no es una lista de series')
    series = {x.get('name'): x.get('data') for x in j if isinstance(x, dict)}
    normal = series.get('1991-2020')
    if not normal or len(normal) < 365:
        raise ValueError('falta la normal 1991-2020')
    anios = sorted(k for k in series if k and re.fullmatch(r'\d{4}', k))
    if not anios:
        raise ValueError('no hay años')
    ult = [v for v in series[anios[-1]] if v is not None]
    if not ult:
        raise ValueError(f'el año {anios[-1]} no tiene datos')
    if not all(20 <= v <= 33 for v in ult):
        raise ValueError('valores fuera de rango')
    return anios[-1], len(ult), ult[-1]


if __name__ == '__main__':
    j = json.load(open(sys.argv[1], encoding='utf-8'))
    anio, n, v = verificar(j)
    json.dump(j, open(sys.argv[2], 'w', encoding='utf-8'), separators=(',', ':'))
    print(f'Niño 3.4: {anio}, {n} días, último {v} °C')
