"""enso_hovmoller_png v2.0 - El Hovmoller de El Nino en version imprimible.

Toma la matriz que ya genera tools/build_enso_ersst.py (public/data/enso-ersst.json) y la
dibuja con el diseno de DOTS: PNG de 1600x900, listo para una nota, un PDF o Telegram.

No descarga nada ni recalcula indices: usa los datos que valida el workflow
.github/workflows/enso-data-build.yml. La ciencia vive en un solo lugar.

Cada figura lleva tres lecturas alineadas en el mismo eje de tiempo:
  * a la izquierda, la serie del indice Nino 3.4, para saber si hubo Nino o Nina;
  * en el centro, la franja 5S-5N: donde esta el agua caliente en cada momento;
  * a la derecha, los eventos fuertes marcados, detectados de los propios datos.

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
LIMITE = 3.0      # tope de la escala de color, en grados
UMBRAL = 0.5      # desde aca se considera episodio Nino o Nina
MINIMO = 5        # meses seguidos para que cuente como episodio
FUERTE = 1.5      # desde aca se marca en el grafico
ETIQUETA = 2.0    # desde aca se escribe el nombre del evento
FUENTE = 'Fuente: NOAA ERSST v5 · base 1991-2020 · datos de public/data/enso-ersst.json'

# Paleta DOTS, la misma de scripts/nino_graficos.py
FONDO, TINTA, GRIS, LINEA = '#F7F6F2', '#15191A', '#6B706C', '#DEDCD5'
ROJO, PIZARRA, AZUL = '#C8102E', '#4E6A8A', '#0A4D8C'

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

plt.rcParams.update({'font.family': 'IBM Plex Sans', 'font.size': 12.5, 'text.color': TINTA,
                     'axes.labelcolor': GRIS, 'xtick.color': GRIS, 'ytick.color': GRIS,
                     'axes.edgecolor': LINEA, 'figure.facecolor': FONDO, 'axes.facecolor': FONDO,
                     'savefig.facecolor': FONDO})


def numero(v, d=2):
    """Numero con coma decimal, como el resto de las piezas de DOTS."""
    return f'{v:+.{d}f}'.replace('.', ',').replace('-', '−')


def mes_largo(mes):
    """'2026-09' -> 'septiembre de 2026'."""
    return f'{MESES[int(mes[5:]) - 1]} de {mes[:4]}'


def nombre_evento(meses, ini, fin):
    """'1997-05'..'1998-06' -> '1997-98'; si cae en un solo anio, '1982'."""
    a, b = meses[ini][:4], meses[fin][:4]
    return a if a == b else f'{a}-{b[2:]}'


def cargar(ruta=DATOS):
    """Lee el JSON del laboratorio y devuelve meses, longitudes, matriz y el indice Nino 3.4."""
    with open(ruta, encoding='utf-8') as fh:
        d = json.load(fh)
    hov = d['hovmoller']
    matriz = np.array([[np.nan if v is None else float(v) for v in fila] for fila in hov['values']])
    crudo = (d.get('indices') or {}).get('nino34') or []
    serie = np.array([np.nan if v is None else float(v) for v in crudo])
    if serie.size != matriz.shape[0]:  # sin indice no hay panel lateral, pero el mapa se dibuja igual
        serie = np.full(matriz.shape[0], np.nan)
    return d['months'], list(hov['lon']), matriz, serie


def detectar_eventos(serie, meses, umbral=UMBRAL, minimo=MINIMO):
    """Episodios de Nino o Nina: tramos seguidos que superan el umbral al menos 'minimo' meses."""
    eventos, n, i = [], len(serie), 0
    while i < n:
        v = serie[i]
        if np.isnan(v) or abs(v) < umbral:
            i += 1
            continue
        signo = 1 if v > 0 else -1
        j = i
        while j < n and not np.isnan(serie[j]) and serie[j] * signo >= umbral:
            j += 1
        if j - i >= minimo:
            tramo = serie[i:j]
            pico = i + int(np.nanargmax(np.abs(tramo)))
            eventos.append({'ini': i, 'fin': j - 1, 'pico': pico, 'valor': float(serie[pico]),
                            'tipo': 'nino' if signo > 0 else 'nina',
                            'nombre': nombre_evento(meses, i, j - 1)})
        i = j
    return eventos


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


def dibujar_indice(ax, serie, eventos):
    """Panel izquierdo: el indice Nino 3.4 como barras horizontales, alineado al tiempo."""
    filas = np.arange(len(serie))
    limpio = np.nan_to_num(serie, nan=0.0)
    ax.fill_betweenx(filas, 0, limpio, where=limpio >= 0, color=ROJO, alpha=.75, lw=0)
    ax.fill_betweenx(filas, 0, limpio, where=limpio < 0, color=AZUL, alpha=.75, lw=0)
    ax.axvline(0, color=GRIS, lw=.8)
    for e in eventos:
        if abs(e['valor']) >= FUERTE:
            ax.plot(e['valor'], e['pico'], 'o', ms=4, mfc='none', mec=TINTA, mew=1)
    ax.set_xlim(-3.2, 3.2)
    ax.set_xticks([-2, 0, 2])
    ax.set_xticklabels(['−2', '0', '+2'], fontsize=8.5)
    ax.tick_params(length=0, pad=2)
    for lado in ('top', 'right', 'left'):
        ax.spines[lado].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.set_ylabel('')
    ax.text(.5, 1.008, 'Niño 3.4', transform=ax.transAxes, fontsize=9.5, color=GRIS,
            ha='center', va='bottom')


def dibujar(meses, lons, matriz, serie, ruta, titulo, subtitulo, cada=5):
    """Dibuja el Hovmoller con su indice a la izquierda y los eventos fuertes marcados."""
    fig = lienzo('DOTS · El Niño', titulo, subtitulo)
    ax = fig.add_axes([.175, .115, .675, .655])
    axi = fig.add_axes([.075, .115, .062, .655], sharey=ax)

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
    ax.tick_params(labelleft=False)  # los años van una sola vez, en el panel del índice

    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    ax.tick_params(length=0, pad=4)

    # Eventos fuertes: banda tenue y nombre sobre el pico.
    eventos = detectar_eventos(serie, meses)
    for e in eventos:
        if abs(e['valor']) < FUERTE:
            continue
        color = ROJO if e['tipo'] == 'nino' else AZUL
        ax.axhspan(e['ini'] - .5, e['fin'] + .5, color=color, alpha=.09, lw=0, zorder=2)
        if abs(e['valor']) < ETIQUETA:  # solo los muy fuertes llevan nombre, para no amontonar
            continue
        # la etiqueta mide ~14 px: se mantiene dentro del area visible, corrida si el pico toca el borde
        margen = max(1.0, len(meses) * .02)
        y = min(max(e['pico'], margen), len(meses) - 1 - margen)
        ax.text(len(lons) - .9, y, e['nombre'], fontsize=10, color=TINTA,
                ha='right', va='center', zorder=4,
                bbox={'boxstyle': 'round,pad=0.22', 'facecolor': FONDO, 'edgecolor': 'none', 'alpha': .82})

    dibujar_indice(axi, serie, eventos)

    cax = fig.add_axes([.862, .115, .014, .655])
    barra = fig.colorbar(malla, cax=cax)
    barra.set_label('°C', fontsize=11)
    barra.outline.set_visible(False)

    fig.savefig(ruta)
    plt.close(fig)
    return ruta


def generar(carpeta, datos=DATOS):
    """Genera las dos versiones del Hovmoller y devuelve las rutas."""
    meses, lons, matriz, serie = cargar(datos)
    os.makedirs(carpeta, exist_ok=True)
    ultimo = serie[-1] if serie.size else np.nan
    valor = numero(float(ultimo)) if not np.isnan(ultimo) else 'sin dato'

    salidas = [
        dibujar(meses, lons, matriz, serie, os.path.join(carpeta, 'enso-hovmoller-completo.png'),
                'Cómo viaja el agua cálida por el Pacífico',
                'Anomalía promedio entre 5°S y 5°N, de 1981 a hoy, en °C. '
                'Las franjas que bajan a la derecha son ondas Kelvin.'),
    ]

    corte = max(0, len(meses) - 60)
    if corte > 0:
        salidas.append(dibujar(meses[corte:], lons, matriz[corte:], serie[corte:],
                               os.path.join(carpeta, 'enso-hovmoller-5anios.png'),
                               'El último tramo: cinco años de Pacífico',
                               f'De {mes_largo(meses[corte])} a {mes_largo(meses[-1])}. '
                               f'Niño 3.4 en el último mes: {valor} °C.'))
    return salidas


if __name__ == '__main__':
    destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data', 'enso')
    for ruta in generar(destino):
        print(f'{os.path.relpath(ruta, ROOT)}  ({os.path.getsize(ruta) // 1024} KB)')
