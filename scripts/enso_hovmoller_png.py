"""enso_hovmoller_png v1.0 - El Hovmoller de El Nino en version imprimible.

Toma la matriz que ya genera tools/build_enso_ersst.py (public/data/enso-ersst.json) y la
dibuja con el diseno de DOTS: PNG de 1600x900, listo para una nota, un PDF o Telegram.

No descarga nada ni recalcula indices: usa los datos que valida el workflow
.github/workflows/enso-data-build.yml. La ciencia vive en un solo lugar.

Salidas (por defecto en data/enso):
  * enso-hovmoller-completo.png   desde 1981 hasta el ultimo mes con dato
  * enso-hovmoller-5anios.png     ultimos cinco anios, que es lo que se lee en una nota

Uso: python scripts/enso_hovmoller_png.py [carpeta_salida]
Requiere: pip install numpy matplotlib
"""
import json
import os
import sys

import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _f in os.listdir(os.path.join(HERE, 'fonts')):
    if _f.endswith('.ttf'):
        fm.fontManager.addfont(os.path.join(HERE, 'fonts', _f))

DATOS = os.path.join(ROOT, 'public', 'data', 'enso-ersst.json')
LIMITE = 3.0  # tope de la escala de color, en grados
FUENTE = 'Fuente: NOAA ERSST v5 · base 1991-2020 · datos de public/data/enso-ersst.json'

# Paleta DOTS, la misma de scripts/nino_graficos.py
FONDO, TINTA, GRIS, LINEA = '#F7F6F2', '#15191A', '#6B706C', '#DEDCD5'
ROJO, PIZARRA = '#C8102E', '#4E6A8A'

plt.rcParams.update({'font.family': 'IBM Plex Sans', 'font.size': 12.5, 'text.color': TINTA,
                     'axes.labelcolor': GRIS, 'xtick.color': GRIS, 'ytick.color': GRIS,
                     'axes.edgecolor': LINEA, 'figure.facecolor': FONDO, 'axes.facecolor': FONDO,
                     'savefig.facecolor': FONDO})


def numero(v, d=2):
    """Numero con coma decimal, como el resto de las piezas de DOTS."""
    return f'{v:+.{d}f}'.replace('.', ',').replace('-', '−')


MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']


def mes_largo(mes):
    """'2026-09' -> 'septiembre de 2026'."""
    return f'{MESES[int(mes[5:]) - 1]} de {mes[:4]}'


def cargar(ruta=DATOS):
    """Lee el JSON del laboratorio y devuelve meses, longitudes y la matriz del Hovmoller."""
    with open(ruta, encoding='utf-8') as fh:
        d = json.load(fh)
    hov = d['hovmoller']
    matriz = np.array([[np.nan if v is None else float(v) for v in fila] for fila in hov['values']])
    return d['months'], list(hov['lon']), matriz, d.get('indices', {})


def etiqueta_lon(x):
    """123 -> 123E, 187 -> 173O, 180 -> 180."""
    x = x % 360
    if x == 180:
        return '180°'
    if x > 180:
        return f'{int(round(360 - x))}°O'
    return f'{int(round(x))}°E'


def indice_cercano(lons, objetivo):
    """Posicion de la malla mas cercana a una longitud pedida, cruzando la linea de fecha."""
    return min(range(len(lons)), key=lambda i: abs(((lons[i] - objetivo + 180) % 360) - 180))


def lienzo(kicker, titulo, subtitulo):
    """Encabezado y pie con el diseno de DOTS."""
    fig = plt.figure(figsize=(12.8, 7.2), dpi=125)
    fig.text(.055, .945, kicker.upper(), fontsize=11.5, fontweight='bold', color=ROJO)
    fig.text(.055, .885, titulo, fontsize=25, fontweight='bold', color=TINTA, va='center')
    fig.text(.055, .833, subtitulo, fontsize=14, color=GRIS, va='center')
    fig.text(.055, .038, FUENTE, fontsize=10, color=GRIS, va='center')
    fig.text(.945, .041, 'DOTS', fontsize=15, fontweight='bold', color=TINTA, ha='right', va='center')
    fig.text(.892, .041, 'Datos · Observación · Territorio · Satélite', fontsize=9, color=GRIS,
             ha='right', va='center')
    return fig


def dibujar(meses, lons, matriz, ruta, titulo, subtitulo, cada=5):
    """Dibuja un Hovmoller: longitud en el eje horizontal, tiempo en el vertical."""
    fig = lienzo('DOTS · El Niño', titulo, subtitulo)
    ax = fig.add_axes([.075, .115, .775, .655])
    malla = ax.pcolormesh(np.arange(len(lons)), np.arange(len(meses)), matriz,
                          cmap='RdBu_r', norm=TwoSlopeNorm(vcenter=0, vmin=-LIMITE, vmax=LIMITE),
                          shading='auto')
    ax.set_xlim(-.5, len(lons) - .5)
    ax.set_ylim(-.5, len(meses) - .5)

    marcas = [indice_cercano(lons, objetivo) for objetivo in (120, 180, 240, 280)]
    ax.set_xticks(marcas)
    ax.set_xticklabels([etiqueta_lon(lons[i]) for i in marcas])

    anios = [i for i, m in enumerate(meses) if m.endswith('-01') and int(m[:4]) % cada == 0]
    if len(anios) < 3:  # ventanas cortas: una marca por anio, no cada cinco
        anios = [i for i, m in enumerate(meses) if m.endswith('-01')]
    ax.set_yticks(anios)
    ax.set_yticklabels([meses[i][:4] for i in anios])

    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    ax.tick_params(length=0, pad=4)

    cax = fig.add_axes([.862, .115, .014, .655])
    barra = fig.colorbar(malla, cax=cax)
    barra.set_label('°C', fontsize=11)
    barra.outline.set_visible(False)

    fig.savefig(ruta)
    plt.close(fig)
    return ruta


def generar(carpeta, datos=DATOS):
    """Genera las dos versiones del Hovmoller y devuelve las rutas."""
    meses, lons, matriz, indices = cargar(datos)
    os.makedirs(carpeta, exist_ok=True)
    n34 = indices.get('nino34') or []
    valor = numero(float(n34[-1])) if n34 and n34[-1] is not None else 'sin dato'

    salidas = [
        dibujar(meses, lons, matriz, os.path.join(carpeta, 'enso-hovmoller-completo.png'),
                'Cómo viaja el agua cálida por el Pacífico',
                'Anomalía promedio entre 5°S y 5°N, de 1981 a hoy, en °C. '
                'Las franjas que bajan a la derecha son ondas Kelvin.'),
    ]

    corte = max(0, len(meses) - 60)
    if corte > 0:
        salidas.append(dibujar(meses[corte:], lons, matriz[corte:],
                               os.path.join(carpeta, 'enso-hovmoller-5anios.png'),
                               'El último tramo: cinco años de Pacífico',
                               f'De {mes_largo(meses[corte])} a {mes_largo(meses[-1])}. '
                               f'Niño 3.4 en el último mes: {valor} °C.'))
    return salidas


if __name__ == '__main__':
    destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data', 'enso')
    for ruta in generar(destino):
        print(f'{os.path.relpath(ruta, ROOT)}  ({os.path.getsize(ruta) // 1024} KB)')
