"""Avisos automáticos de El Niño (corre en GitHub Actions una vez por día, gratis).

1. Lee la temperatura diaria del mar en la región Niño 3.4 (NOAA OISST 2.1 vía Climate Reanalyzer, Univ. de Maine),
   la misma serie que muestra la página /nino-diario.
2. Calcula la diferencia del último día con su normal 1991-2020 y la compara con lo guardado en
   data/nino_avisos_estado.json.
3. Avisa sólo si pasa algo que importa:
   - cambia de categoría (neutral, débil, moderado, fuerte, muy fuerte, o La Niña);
   - marca un nuevo máximo de toda la serie desde 1981;
   - sube 0,5 °C o más en 7 días.
4. Lo manda por Telegram, ntfy y correo con los mismos secretos que los avisos de crecidas, siempre con el link a la
   página interactiva. Texto formal, sin emojis.

Uso: python scripts/avisos_nino.py
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, '..', 'data', 'nino_avisos_estado.json')
FEED = os.path.join(HERE, '..', 'data', 'nino_avisos.json')
SITE = os.environ.get('DOTS_SITE', 'https://observatorio-agro.vercel.app')
PAGINA = f'{SITE}/nino-diario'
FUENTE = 'https://climatereanalyzer.org/clim/sst_daily/json_2clim/oisst2.1_nino3.4_sst_day.json'
NTFY_TOPIC = os.environ.get('NTFY_TOPIC_NINO') or 'dots-el-nino'
SUBA_7D = 0.5
MAX_FEED = 100

# (límite inferior, nombre): mismos rangos que la página /nino-diario
CATEGORIAS = [(-99, 'La Niña'), (-0.5, 'neutral'), (0.5, 'El Niño débil'), (1.0, 'El Niño moderado'),
              (1.5, 'El Niño fuerte'), (2.0, 'El Niño muy fuerte')]


def categoria(a):
    nombre = CATEGORIAS[0][1]
    for lim, n in CATEGORIAS:
        if a >= lim:
            nombre = n
    return nombre


def nivel(nombre):
    return [n for _, n in CATEGORIAS].index(nombre)


def num(v, d=1):
    return f'{v:+.{d}f}'.replace('.', ',')


def load(path, default):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


def leer_serie():
    r = requests.get(FUENTE, timeout=60, headers={'User-Agent': 'Mozilla/5.0 (DOTS observatorio; +https://observatorio-agro.vercel.app)', 'Accept': 'application/json'})
    r.raise_for_status()
    d = {x['name']: x['data'] for x in r.json()}
    normal = d['1991-2020']
    anios = sorted(k for k in d if k.isdigit())
    anio = anios[-1]
    pre = d.get('Preliminary') or [None] * len(normal)
    serie = [v if v is not None else pre[i] for i, v in enumerate(d[anio])]
    ult = max(i for i, v in enumerate(serie) if v is not None)
    anom = lambda arr, i: None if arr[i] is None or normal[i] is None else arr[i] - normal[i]
    maximo, max_anio = -99.0, ''
    for k in anios:
        arr = serie if k == anio else d[k]
        for i in range(len(arr)):
            a = anom(arr, i)
            if a is not None and a > maximo and not (k == anio and i == ult):
                maximo, max_anio = a, k
    hace7 = anom(serie, ult - 7) if ult >= 7 else None
    dia = date(int(anio), 1, 1) + timedelta(days=ult)
    return {'fecha': dia.isoformat(), 'temp': serie[ult], 'normal': normal[ult], 'anom': anom(serie, ult),
            'hace7': hace7, 'max_previo': maximo, 'max_previo_anio': max_anio,
            'preliminar': d[anio][ult] is None, '_d': d, '_anio': anio, '_serie': serie, '_ult': ult}


# ───────────────────────── Gráficos (mismo diseño que la nota del diario y la página /nino-diario) ─────────────────────────
MES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
INICIO = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
EVENTOS = [('1982-83', ['1982', '1983']), ('1997-98', ['1997', '1998']), ('2015-16', ['2015', '2016']), ('2023-24', ['2023', '2024'])]
FUENTE_TXT = 'Fuente: DOTS, con datos NOAA OISST 2.1 vía Climate Reanalyzer (Univ. de Maine).'


def graficos(dato, carpeta):
    """Genera los tres gráficos en PNG y devuelve sus rutas."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 13, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '#9a9a92',
                         'xtick.color': '#5a5a55', 'ytick.color': '#5a5a55', 'axes.labelcolor': '#3a3a36'})
    RED, INK = '#c8102e', '#141414'
    d, anio, serie, ult = dato['_d'], dato['_anio'], dato['_serie'], dato['_ult']
    normal = d['1991-2020']
    an = lambda arr: [(v - c) if v is not None and c is not None else None for v, c in zip(arr, normal)]
    os.makedirs(carpeta, exist_ok=True)
    rutas = []
    fecha = datetime.fromisoformat(dato['fecha']).strftime('%d/%m/%Y')

    # 1) Evolución diaria
    fig, ax = plt.subplots(figsize=(12, 6.3), dpi=130)
    for y, v in d.items():
        if y.isdigit() and y not in ('1982', '1997', '2015', anio):
            ax.plot(an(v), color='#cfcfc8', lw=.8, zorder=1)
    for y, col, lab in [('1982', '#8a8a84', '1982'), ('1997', '#5b6f8c', '1997'), ('2015', '#e08a3c', '2015')]:
        a = an(d[y]); j = max(i for i, v in enumerate(a) if v is not None)
        ax.plot(a, color=col, lw=2, zorder=3); ax.text(j + 3, a[j], lab, color=col, fontsize=12, fontweight='bold', va='center')
    a26 = an(serie)
    ax.plot(a26, color=RED, lw=3.4, zorder=5); ax.scatter([ult], [a26[ult]], color=RED, s=60, zorder=6)
    ax.annotate(f'{anio}: {num(a26[ult])} °C\n{fecha}', (ult, a26[ult]), xytext=(-14, 18), textcoords='offset points',
                ha='right', color=RED, fontsize=14, fontweight='bold', va='bottom')
    ax.axhline(0, color='#777', lw=1)
    ax.set_xticks(INICIO); ax.set_xticklabels(MES); ax.set_xlim(0, 410); ax.spines['bottom'].set_bounds(0, 365)
    ax.set_ylabel('Diferencia con el promedio 1991-2020 (°C)'); ax.grid(axis='y', color='#ebebe6', lw=.8)
    ax.set_title('El Niño día por día: temperatura del mar en la región Niño 3.4', loc='left', fontsize=17, fontweight='bold', color=INK, pad=26)
    ax.text(0, 1.02, 'Cada línea gris es un año desde 1981.', transform=ax.transAxes, fontsize=12, color='#555')
    fig.text(.01, .01, FUENTE_TXT, fontsize=9.5, color='#777'); fig.tight_layout(rect=(0, .03, 1, 1))
    rutas.append(os.path.join(carpeta, 'nino-evolucion.png')); fig.savefig(rutas[-1]); plt.close(fig)

    # 2) Pico de cada gran El Niño
    filas = [(lab, max(v for y in ys for v in an(d[y]) if v is not None)) for lab, ys in EVENTOS if all(y in d for y in ys)]
    filas.append((anio, max(v for v in a26 if v is not None)))
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=130)
    bars = ax.bar([f[0] for f in filas], [f[1] for f in filas], color=['#bdbdb6'] * (len(filas) - 1) + [RED], width=.62)
    for b, f in zip(bars, filas):
        ax.text(b.get_x() + b.get_width() / 2, f[1] + .05, num(f[1]) + ' °C', ha='center', fontsize=14, fontweight='bold', color=INK)
    ax.set_ylim(0, max(f[1] for f in filas) * 1.15); ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_title('El pico de cada gran El Niño', loc='left', fontsize=17, fontweight='bold', color=INK, pad=26)
    ax.text(0, 1.02, 'Mayor diferencia diaria con lo normal en la región Niño 3.4.', transform=ax.transAxes, fontsize=12, color='#555')
    fig.text(.01, .01, FUENTE_TXT, fontsize=9.5, color='#777'); fig.tight_layout(rect=(0, .03, 1, 1))
    rutas.append(os.path.join(carpeta, 'nino-picos.png')); fig.savefig(rutas[-1]); plt.close(fig)

    # 3) Mes a mes del año actual
    meses, vals = [], []
    for m in range(12):
        seg = [v for v in a26[INICIO[m]:(INICIO[m + 1] if m < 11 else 366)] if v is not None]
        if not seg:
            break
        meses.append(MES[m]); vals.append(sum(seg) / len(seg))
    fig, ax = plt.subplots(figsize=(10, 5.4), dpi=130)
    cols = ['#5b8bd0' if v < 0 else ('#f2b134' if v < 1 else ('#e0662e' if v < 2 else RED)) for v in vals]
    bars = ax.bar(meses, vals, color=cols, width=.66)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + (.06 if v >= 0 else -.2), num(v), ha='center', fontsize=12.5, fontweight='bold', color=INK)
    ax.axhline(0, color='#777', lw=1); ax.set_ylim(min(-1, min(vals) - .4), max(vals) * 1.18 + .2)
    ax.set_yticks([]); ax.spines['left'].set_visible(False); ax.spines['bottom'].set_visible(False)
    ax.set_title(f'Cómo se calentó el Pacífico en {anio}', loc='left', fontsize=17, fontweight='bold', color=INK, pad=26)
    ax.text(0, 1.02, 'Diferencia promedio de cada mes con lo normal, en °C. Región Niño 3.4.', transform=ax.transAxes, fontsize=12, color='#555')
    fig.text(.01, .01, FUENTE_TXT, fontsize=9.5, color='#777'); fig.tight_layout(rect=(0, .03, 1, 1))
    rutas.append(os.path.join(carpeta, 'nino-mes-a-mes.png')); fig.savefig(rutas[-1]); plt.close(fig)
    return rutas


def evaluar(dato, prev):
    """Devuelve la lista de avisos (texto) para el dato del día."""
    avisos = []
    fecha = datetime.fromisoformat(dato['fecha']).strftime('%d/%m/%Y')
    cat = categoria(dato['anom'])
    temp = f"{dato['temp']:.1f}".replace('.', ',')
    base = (f"Región Niño 3.4, {fecha}: el mar está a {temp} °C, {num(dato['anom'])} °C respecto de lo "
            f"normal 1991-2020.")
    if prev.get('categoria') and cat != prev['categoria']:
        sube = nivel(cat) > nivel(prev['categoria'])
        avisos.append(f"Cambio de categoría: de {prev['categoria']} a {cat}. "
                      + ('El Pacífico se sigue calentando. ' if sube else 'El Pacífico se está enfriando. ') + base)
    if dato['anom'] > dato['max_previo'] and dato['anom'] > prev.get('max_avisado', -99):
        avisos.append(f"Nuevo récord de la serie diaria desde 1981: {num(dato['anom'])} °C. El máximo anterior era "
                      f"{num(dato['max_previo'])} °C ({dato['max_previo_anio']}). " + base)
    if dato['hace7'] is not None and dato['anom'] - dato['hace7'] >= SUBA_7D:
        avisos.append(f"Suba rápida: {num(dato['anom'] - dato['hace7'])} °C en 7 días. " + base)
    if avisos and dato['preliminar']:
        avisos[-1] += ' Dato preliminar: puede corregirse unas décimas.'
    return avisos, cat


def telegram(texto, imagenes=()):
    tok, chat = os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not (tok and chat):
        return 'sin configurar'
    api = f'https://api.telegram.org/bot{tok}'
    if imagenes:
        # álbum con los gráficos; el texto va como pie de la primera imagen (hasta 1024 caracteres) y completo aparte
        files, media = {}, []
        for i, ruta in enumerate(imagenes):
            files[f'g{i}'] = open(ruta, 'rb')
            media.append({'type': 'photo', 'media': f'attach://g{i}'})
        media[0]['caption'] = texto[:1024]
        r = requests.post(f'{api}/sendMediaGroup', timeout=60, data={'chat_id': chat, 'media': json.dumps(media)}, files=files)
        for fh in files.values():
            fh.close()
        if r.ok and len(texto) <= 1024:
            return 'enviado con gráficos'
        if not r.ok:
            print(f'Telegram no aceptó las imágenes ({r.status_code}); se manda sólo el texto.')
    r = requests.post(f'{api}/sendMessage', timeout=30, json={'chat_id': chat, 'text': texto[:4000], 'disable_web_page_preview': False})
    return ('enviado' + (' con gráficos' if imagenes else '')) if r.ok else f'error {r.status_code}'


def ntfy(titulo, texto):
    if os.environ.get('NTFY_DISABLED') == '1':
        return 'desactivado'
    r = requests.post(f'https://ntfy.sh/{NTFY_TOPIC}', data=texto.encode('utf-8'), timeout=30, headers={
        'Title': titulo.encode('utf-8'), 'Click': PAGINA, 'Tags': 'ocean'})
    return 'enviado' if r.ok else f'error {r.status_code}'


def email(titulo, avisos):
    key, aud = os.environ.get('RESEND_API_KEY'), os.environ.get('RESEND_AUDIENCE_ID')
    if not (key and aud):
        return 'sin configurar'
    sender = os.environ.get('AVISOS_FROM') or os.environ.get('CONTACT_FROM') or 'DOTS Campo <onboarding@resend.dev>'
    html = ('<div style="font-family:Arial,sans-serif;font-size:15px;color:#101828">'
            '<p><b>DOTS · Aviso de El Niño</b></p>' + ''.join(f'<p>{a}</p>' for a in avisos) +
            f'<p>Gráficos interactivos, comparación con 1983, 1998 y 2016, y datos para descargar: '
            f'<a href="{PAGINA}">{PAGINA}</a></p>'
            '<p style="color:#667085;font-size:12px">Datos: NOAA OISST 2.1 vía Climate Reanalyzer (Universidad de Maine). '
            'Para el pronóstico de lluvias, la referencia oficial es el SMN. '
            'Para dejar de recibir estos avisos usá el enlace de baja: {{{RESEND_UNSUBSCRIBE_URL}}}</p></div>')
    h = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    r = requests.post('https://api.resend.com/broadcasts', headers=h, timeout=30, json={
        'audience_id': aud, 'from': sender, 'subject': titulo, 'html': html,
        'name': f'El Niño {datetime.now(timezone.utc):%Y-%m-%d}'})
    if not r.ok:
        return f'error {r.status_code}'
    r2 = requests.post(f"https://api.resend.com/broadcasts/{r.json().get('id')}/send", headers=h, timeout=30, json={})
    return 'enviado' if r2.ok else f'error {r2.status_code}'


def main():
    try:
        dato = leer_serie()
    except Exception as e:  # la fuente no respondió: no se inventa nada, pero queda registrado el intento
        print(f'Climate Reanalyzer no respondió ({type(e).__name__}: {e}): no se cambia nada.')
        prev = load(STATE, {})
        prev['ultimo_error'] = {'at': datetime.now(timezone.utc).isoformat(timespec='minutes'), 'detalle': f'{type(e).__name__}: {e}'[:300]}
        save(STATE, prev)
        return
    prev = load(STATE, {})
    forzar = os.environ.get('NINO_FORZAR', '').lower() in ('1', 'si', 'sí', 'true')
    if forzar:
        # parte a pedido: manda el estado actual con los gráficos aunque no haya cambios
        cat = categoria(dato['anom'])
        fecha = datetime.fromisoformat(dato['fecha']).strftime('%d/%m/%Y')
        temp = f"{dato['temp']:.1f}".replace('.', ',')
        txt = (f"DOTS · Parte de El Niño\n\nRegión Niño 3.4, {fecha}: el mar está a {temp} °C, {num(dato['anom'])} °C respecto "
               f"de lo normal 1991-2020. Categoría: {cat}."
               + (f" Hace 7 días: {num(dato['hace7'])} °C." if dato['hace7'] is not None else '')
               + (' Dato preliminar.' if dato['preliminar'] else '') + f"\n\nGráficos interactivos y datos: {PAGINA}")
        imgs = graficos(dato, os.path.join(HERE, '..', 'data', 'nino_graficos'))
        print('Parte a pedido. Telegram:', telegram(txt, imgs), '· ntfy:', ntfy(f"DOTS · El Niño: {num(dato['anom'])} °C, {cat}", txt))
        if prev.get('fecha') != dato['fecha']:
            prev.update({'fecha': dato['fecha'], 'anom': round(dato['anom'], 3), 'categoria': cat}); save(STATE, prev)
        return
    if prev.get('fecha') == dato['fecha']:
        print(f"Sin dato nuevo (último: {dato['fecha']})."); return
    avisos, cat = ([], categoria(dato['anom'])) if not prev else evaluar(dato, prev)
    nuevo = {'fecha': dato['fecha'], 'anom': round(dato['anom'], 3), 'categoria': cat,
             'max_avisado': max(prev.get('max_avisado', -99), dato['anom'] if dato['anom'] > dato['max_previo'] else -99)}
    save(STATE, nuevo)
    if not prev:
        print(f"Estado inicial: {dato['fecha']} {num(dato['anom'], 2)} °C, {cat}."); return
    if not avisos:
        print(f"Sin avisos: {dato['fecha']} {num(dato['anom'], 2)} °C, {cat}."); return
    titulo = f"DOTS · El Niño: {num(dato['anom'])} °C, {cat}"
    texto = 'DOTS · Aviso de El Niño\n\n' + '\n\n'.join(avisos) + f'\n\nGráficos interactivos y datos: {PAGINA}'
    try:
        imgs = graficos(dato, os.path.join(HERE, '..', 'data', 'nino_graficos'))
    except Exception as e:  # un gráfico que falla no frena el aviso
        print(f'No se pudieron generar los gráficos ({type(e).__name__}: {e}).'); imgs = []
    tg, nt, em = telegram(texto, imgs), ntfy(titulo, '\n\n'.join(avisos)), email(titulo, avisos)
    feed = load(FEED, {'items': []})
    for a in avisos:
        feed['items'].insert(0, {'at': datetime.now(timezone.utc).isoformat(timespec='minutes'), 'fecha': dato['fecha'], 'text': a})
    feed['items'] = feed['items'][:MAX_FEED]
    feed['updated'] = datetime.now(timezone.utc).isoformat(timespec='minutes')
    save(FEED, feed)
    print(f'{len(avisos)} aviso(s). Telegram: {tg}. ntfy: {nt}. Correo: {em}.')
    for a in avisos:
        print(' -', a)


if __name__ == '__main__':
    sys.exit(main())
