"""Gráficos de El Niño con el diseño de DOTS (PNG 1600×900, listos para Telegram, notas y redes).

Los usan los avisos automáticos (scripts/avisos_nino.py) y sirven para las notas del diario.
Entrada: la serie diaria de Climate Reanalyzer (NOAA OISST 2.1, región Niño 3.4) como dict {nombre: [366 valores]}.

Uso suelto: python scripts/nino_graficos.py archivo.json carpeta_salida
"""
import json
import os
import sys
from datetime import date, timedelta

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
for _f in os.listdir(os.path.join(HERE, 'fonts')):
    if _f.endswith('.ttf'):
        fm.fontManager.addfont(os.path.join(HERE, 'fonts', _f))

# Paleta DOTS
FONDO, TINTA, GRIS, LINEA, RANGO = '#F7F6F2', '#15191A', '#6B706C', '#DEDCD5', '#E7E5DE'
ROJO, PIZARRA, OCRE, PIEDRA = '#C8102E', '#4E6A8A', '#C28A3A', '#8C8A84'
CAT = [(-99, '#5B83C6'), (0.5, '#E9C46A'), (1.0, '#F0A33A'), (1.5, '#E06A2C'), (2.0, '#C8102E')]
UMBRALES = [(0.5, 'débil'), (1.0, 'moderado'), (1.5, 'fuerte'), (2.0, 'muy fuerte')]
MES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
MES_LARGO = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
INICIO = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
EVENTOS = [('1982-83', ['1982', '1983']), ('1997-98', ['1997', '1998']), ('2015-16', ['2015', '2016']), ('2023-24', ['2023', '2024'])]
FUENTE = 'Fuente: NOAA OISST 2.1 vía Climate Reanalyzer (Universidad de Maine) · Base 1991-2020'

plt.rcParams.update({'font.family': 'IBM Plex Sans', 'font.size': 12.5, 'text.color': TINTA, 'axes.labelcolor': GRIS,
                     'xtick.color': GRIS, 'ytick.color': GRIS, 'axes.edgecolor': LINEA, 'figure.facecolor': FONDO,
                     'axes.facecolor': FONDO, 'savefig.facecolor': FONDO})


def fmt(v, d=1, signo=True):
    s = f'{v:+.{d}f}' if signo else f'{v:.{d}f}'
    return s.replace('.', ',').replace('-', '−')


def color_cat(v):
    c = CAT[0][1]
    for lim, col in CAT:
        if v >= lim:
            c = col
    return c


def lienzo(kicker, titulo, subtitulo):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=125)
    fig.text(.055, .945, kicker.upper(), fontsize=11.5, fontweight='bold', color=ROJO)
    fig.text(.055, .885, titulo, fontsize=25, fontweight='bold', color=TINTA, va='center')
    fig.text(.055, .833, subtitulo, fontsize=14, color=GRIS, va='center')
    fig.add_artist(plt.Line2D([.055, .945], [.075, .075], color=LINEA, lw=1, transform=fig.transFigure))
    fig.text(.055, .038, FUENTE, fontsize=10, color=GRIS, va='center')
    fig.text(.945, .041, 'DOTS', fontsize=15, fontweight='bold', color=TINTA, ha='right', va='center')
    fig.text(.892, .041, 'Datos · Observación · Territorio · Satélite', fontsize=9, color=GRIS, ha='right', va='center')
    return fig


def cifra(fig, x, y, valor, etiqueta, color=ROJO):
    fig.text(x, y, valor, fontsize=34, fontweight='bold', color=color, ha='right', va='center')
    fig.text(x, y - .052, etiqueta, fontsize=11.5, color=GRIS, ha='right', va='center')


def limpiar(ax, y=True):
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.spines['bottom'].set_color(LINEA)
    ax.tick_params(length=0)
    if y:
        ax.grid(axis='y', color=LINEA, lw=.8)
        ax.set_axisbelow(True)


def preparar(d, serie=None):
    normal = d['1991-2020']
    anios = sorted(k for k in d if k.isdigit())
    anio = anios[-1]
    if serie is None:
        pre = d.get('Preliminary') or [None] * len(normal)
        serie = [v if v is not None else pre[i] for i, v in enumerate(d[anio])]
    an = lambda arr: [(v - c) if v is not None and c is not None else None for v, c in zip(arr, normal)]
    ult = max(i for i, v in enumerate(serie) if v is not None)
    return normal, anios, anio, serie, an, ult


def evolucion(d, ruta, serie=None):
    normal, anios, anio, serie, an, ult = preparar(d, serie)
    a = an(serie)
    fecha = date(int(anio), 1, 1) + timedelta(days=ult)
    fig = lienzo('DOTS · El Niño', 'El Pacífico, día por día',
                 f'Diferencia con lo normal en la región Niño 3.4, en °C. {anio} frente a todos los años desde 1981.')
    cifra(fig, .945, .885, fmt(a[ult]) + ' °C', f'{fecha.day} de {MES_LARGO[fecha.month - 1]} de {anio}')
    ax = fig.add_axes([.07, .13, .80, .64])
    limpiar(ax)
    # rango histórico (mínimo y máximo de cada día, sin el año actual)
    hist = [an(d[k]) for k in anios if k != anio]
    lo = [min((h[i] for h in hist if h[i] is not None), default=None) for i in range(366)]
    hi = [max((h[i] for h in hist if h[i] is not None), default=None) for i in range(366)]
    xs = [i for i in range(366) if lo[i] is not None]
    ax.fill_between(xs, [lo[i] for i in xs], [hi[i] for i in xs], color=RANGO, lw=0, zorder=1)
    ax.text(200, min(lo[i] for i in xs if 190 < i < 210) + .15, 'Rango de todos los años 1981-' + str(int(anio) - 1),
            fontsize=10.5, color=PIEDRA, ha='center', zorder=2)
    # umbrales de intensidad
    for lim, nombre in UMBRALES:
        ax.axhline(lim, color=LINEA, lw=.9, ls=(0, (2, 3)), zorder=1)
        ax.text(4, lim + .04, nombre, fontsize=9.5, color=PIEDRA, va='bottom', ha='left', zorder=2)
    ax.axhline(0, color='#B9B7B0', lw=1, zorder=2)
    # años de referencia
    for y, col in [('1982', PIEDRA), ('1997', PIZARRA), ('2015', OCRE)]:
        if y in d:
            r = an(d[y]); j = max(i for i, v in enumerate(r) if v is not None)
            ax.plot(r, color=col, lw=1.6, alpha=.95, zorder=3)
            ax.text(j + 4, r[j], y, color=col, fontsize=11, fontweight='bold', va='center')
    # año actual, con halo y relleno
    xs2 = list(range(ult + 1))
    ax.fill_between(xs2, [0] * len(xs2), [v if v is not None else 0 for v in a[:ult + 1]], color=ROJO, alpha=.07, lw=0, zorder=3)
    ax.plot(a, color=ROJO, lw=8, alpha=.12, solid_capstyle='round', zorder=4)
    ax.plot(a, color=ROJO, lw=3, solid_capstyle='round', zorder=5)
    ax.scatter([ult], [a[ult]], s=90, color=ROJO, edgecolor='white', linewidth=2, zorder=6)
    ax.text(ult - 6, a[ult] + .32, anio, color=ROJO, fontsize=13, fontweight='bold', ha='right')
    ax.set_xticks(INICIO); ax.set_xticklabels(MES)
    ax.set_xlim(0, 365)
    ymin = min(min(v for v in lo if v is not None), -1.5)
    ax.set_ylim(ymin - .2, max(3.2, max(v for v in a if v is not None) + .7))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v, 0, v != 0) + ' °C' if v else '0'))
    fig.savefig(ruta)
    plt.close(fig)
    return ruta


def picos(d, ruta, serie=None):
    normal, anios, anio, serie, an, ult = preparar(d, serie)
    filas = []
    for lab, ys in EVENTOS:
        if all(y in d for y in ys):
            best = max(((v, y, i) for y in ys for i, v in enumerate(an(d[y])) if v is not None))
            filas.append((lab, best[0], date(int(best[1]), 1, 1) + timedelta(days=best[2])))
    a = an(serie)
    best = max((v, i) for i, v in enumerate(a) if v is not None)
    filas.append((anio, best[0], date(int(anio), 1, 1) + timedelta(days=best[1])))
    fig = lienzo('DOTS · El Niño', 'Más caliente que todos los grandes El Niño',
                 'Máxima diferencia diaria con lo normal en cada gran El Niño, región Niño 3.4.')
    record = filas[-1][1] >= max(f[1] for f in filas[:-1])
    cifra(fig, .945, .885, fmt(filas[-1][1]) + ' °C', 'récord de la serie' if record else f'pico de {anio} hasta hoy')
    ax = fig.add_axes([.20, .14, .67, .62])
    for s in ('top', 'right', 'left', 'bottom'):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    tope = max(f[1] for f in filas) * 1.12
    ys = list(range(len(filas)))[::-1]
    for y, (lab, v, dia) in zip(ys, filas):
        actual = lab == anio
        ax.add_patch(FancyBboxPatch((0, y - .29), tope, .58, boxstyle='round,pad=0,rounding_size=.12', color=RANGO, lw=0))
        ax.add_patch(FancyBboxPatch((0, y - .29), v, .58, boxstyle='round,pad=0,rounding_size=.12', color=ROJO if actual else PIZARRA, lw=0))
        ax.text(v - .06, y, fmt(v) + ' °C', color='white', fontsize=14, fontweight='bold', ha='right', va='center')
        ax.text(-.08, y + .1, lab, color=ROJO if actual else TINTA, fontsize=15, fontweight='bold', ha='right', va='center')
        ax.text(-.08, y - .2, f'{MES_LARGO[dia.month - 1]} de {dia.year}', color=GRIS, fontsize=10.5, ha='right', va='center')
        if actual:
            ax.text(tope + .05, y, 'y sigue\nsubiendo', color=ROJO, fontsize=10.5, fontweight='bold', ha='left', va='center')
    ax.set_xlim(0, tope); ax.set_ylim(-.6, len(filas) - .4)
    ax.set_xticks([]); ax.set_yticks([])
    fig.savefig(ruta)
    plt.close(fig)
    return ruta


def mes_a_mes(d, ruta, serie=None):
    normal, anios, anio, serie, an, ult = preparar(d, serie)
    a = an(serie)
    meses, vals = [], []
    for m in range(12):
        seg = [v for v in a[INICIO[m]:(INICIO[m + 1] if m < 11 else 366)] if v is not None]
        if not seg:
            break
        meses.append(MES[m]); vals.append(sum(seg) / len(seg))
    fig = lienzo('DOTS · El Niño', f'Cómo se calentó el Pacífico en {anio}',
                 'Diferencia promedio de cada mes con lo normal en la región Niño 3.4, en °C.')
    cifra(fig, .945, .885, fmt(vals[-1] - vals[0]) + ' °C', f'de {MES_LARGO[0]} a {MES_LARGO[len(vals) - 1]}')
    ax = fig.add_axes([.07, .14, .80, .62])
    limpiar(ax, y=False)
    top = max(max(vals) + .7, 2.6)
    # franjas de intensidad
    bandas = [(.5, 1.0, 'débil'), (1.0, 1.5, 'moderado'), (1.5, 2.0, 'fuerte'), (2.0, top, 'muy fuerte')]
    for i, (y0, y1, nombre) in enumerate(bandas):
        ax.axhspan(y0, y1, color=CAT[i + 1][1], alpha=.06 + .01 * i, lw=0, zorder=0)
        ax.text(len(vals) - .35, (y0 + min(y1, y0 + .5)) / 2, nombre, fontsize=10, color=PIEDRA, va='center', ha='left')
    ax.axhline(0, color='#B9B7B0', lw=1)
    for i, v in enumerate(vals):
        if abs(v) >= .06:
            ax.add_patch(FancyBboxPatch((i - .3, min(0, v)), .6, abs(v), boxstyle='round,pad=0,rounding_size=.05',
                                        color=color_cat(v), lw=0, zorder=3, mutation_aspect=.6))
        else:
            ax.plot([i - .3, i + .3], [0, 0], color=color_cat(v), lw=4, solid_capstyle='round', zorder=3)
        ax.text(i, v + (.12 if v >= 0 else -.22), fmt(v), ha='center', fontsize=13, fontweight='bold', color=TINTA, zorder=4)
    ax.set_xticks(range(len(vals))); ax.set_xticklabels(meses, fontsize=12.5)
    ax.set_xlim(-.6, len(vals) + .4); ax.set_ylim(min(-1, min(vals) - .45), top)
    ax.set_yticks([])
    fig.savefig(ruta)
    plt.close(fig)
    return ruta


def generar(d, carpeta, serie=None):
    os.makedirs(carpeta, exist_ok=True)
    return [evolucion(d, os.path.join(carpeta, 'nino-evolucion.png'), serie),
            picos(d, os.path.join(carpeta, 'nino-picos.png'), serie),
            mes_a_mes(d, os.path.join(carpeta, 'nino-mes-a-mes.png'), serie)]


if __name__ == '__main__':
    with open(sys.argv[1], encoding='utf-8') as fh:
        datos = {x['name']: x['data'] for x in json.load(fh)}
    print(generar(datos, sys.argv[2]))
