// DOTS / Campo — Informe El Niño para un lote (Typst). Datos desde enso_report.report_data vía sys.inputs.data.
#let d = json(bytes(sys.inputs.data))

#let ink = rgb("#101828")
#let muted = rgb("#667085")
#let line-c = rgb("#e4e7ec")
#let soft = rgb("#f6f7f9")
#let brand = rgb("#0f9fa6")
#let warm = rgb("#d9480f")
#let cool = rgb("#1c7ed6")
#let wet = rgb("#1f6feb")
#let dry = rgb("#c2410c")
#let ok = rgb("#039855")

#set document(title: d.title, author: "DOTS / Campo")
#set text(font: "IBM Plex Sans", size: 9.4pt, fill: ink, lang: "es")
#set par(leading: 0.6em)
#set page(paper: "a4", margin: (top: 14mm, bottom: 16mm, x: 15mm),
  footer: context {
    set text(size: 7.2pt, fill: muted)
    line(length: 100%, stroke: 0.5pt + line-c)
    v(-2pt)
    grid(columns: (1fr, auto), [Datos oficiales: NOAA (CPC, PSL, PMEL) y Copernicus ERA5. Historia y diagnóstico, no pronóstico estacional.], [#d.url · pág. #counter(page).display()])
  })

#let kicker(t, fill: brand) = text(size: 7pt, weight: "semibold", fill: fill, tracking: 0.12em, upper(t))
#let card(body, fill: soft) = block(fill: fill, radius: 8pt, inset: 10pt, width: 100%, breakable: false, body)
#let sec(t) = block(above: 14pt, below: 6pt, sticky: true, text(size: 12.5pt, weight: "semibold")[#t])
#let note(t) = text(size: 7.2pt, fill: muted)[#t]
#let hd(..xs) = xs.pos().map(t => text(size: 6.8pt, weight: "semibold", fill: muted, upper(t)))
#let sigc(s) = if s == "Niño" { warm } else if s == "Niña" { cool } else { muted }
#let pc(v) = if v == none { muted } else if v > 0 { wet } else if v < 0 { dry } else { muted }

// ───────────── banda ─────────────
#let band = if d.nino { warm } else if d.nina { cool } else { brand }
#block(width: 100%, fill: band, radius: 10pt, inset: (x: 16pt, y: 13pt), {
  set text(fill: white)
  grid(columns: (1fr, auto), align: (left + horizon, right + horizon),
    [#text(size: 7.6pt, weight: "bold", tracking: 0.14em)[DOTS · INFORME EL NIÑO] #linebreak()
     #text(size: 22pt, weight: "bold")[#d.place] #linebreak()
     #text(size: 8.5pt)[lat #d.lat · lon #d.lon]],
    [#text(size: 8pt)[FASE OFICIAL] #linebreak() #text(size: 17pt, weight: "bold")[#d.phase] #linebreak() #text(size: 8.5pt)[ONI #d.oni]])
})
#v(3pt)
#text(size: 8pt, fill: muted)[Informe del #d.generated]

#if d.summary.len() > 0 [
  #v(6pt)
  #block(width: 100%, fill: soft, radius: 8pt, inset: (x: 12pt, y: 10pt), breakable: false)[
    #kicker("Resumen") #v(2pt)
    #for l in d.summary [#text(size: 9.3pt)[#l] #parbreak()]
  ]
]

#v(6pt)
#grid(columns: (1fr, 1fr, 1fr, 1fr), column-gutter: 7pt,
  card[#text(size: 7.4pt, fill: muted)[Lluvia oct–mar con Niño fuerte, histórico] #linebreak() #text(size: 18pt, weight: "bold")[#d.expected] #linebreak() #note[vs años neutrales]],
  card[#text(size: 7.4pt, fill: muted)[Últimos 90 días (#d.window)] #linebreak() #text(size: 18pt, weight: "bold")[#d.now90] #linebreak() #note[#d.obs90 mm caídos]],
  card[#text(size: 7.4pt, fill: muted)[Próximos 16 días] #linebreak() #text(size: 18pt, weight: "bold")[#d.next16] #linebreak() #note[#d.next16pct vs lo normal]],
  card[#text(size: 7.4pt, fill: muted)[Temporadas análogas] #linebreak() #text(size: 10pt, weight: "bold")[#d.analogs]])

// ───────────── qué hacer ─────────────
#if d.advice.len() > 0 [
  #sec[Qué conviene revisar]
  #for a in d.advice [- #a]
  #note[Reglas declaradas sobre los números de este informe. No reemplaza al asesor ni a los avisos oficiales.]
]

// ───────────── cadena ─────────────
#sec[La cadena del Pacífico, eslabón por eslabón]
#table(columns: (auto, 1.4fr, auto, auto, 2.4fr), stroke: none, inset: (x: 4pt, y: 4pt),
  fill: (x, y) => if y == 0 { none } else if calc.odd(y) { soft } else { none },
  ..hd("", "Eslabón", "Valor", "Fecha", "Lectura y récord"),
  ..d.steps.map(s => (
    text(weight: "bold", fill: sigc(s.signal))[#s.n],
    text(weight: "semibold")[#s.title],
    text(weight: "bold", fill: sigc(s.signal))[#s.value],
    text(size: 8pt, fill: muted)[#s.date],
    [#text(size: 8.4pt)[#s.reading] #if s.record != "" [#linebreak() #note[#s.record]]],
  )).flatten())

#if d.extras.len() > 0 [
  #sec[Otros indicadores que vigila DOTS]
  #table(columns: (1.3fr, auto, auto, 2.4fr), stroke: none, inset: (x: 4pt, y: 4pt),
    fill: (x, y) => if y == 0 { none } else if calc.odd(y) { soft } else { none },
    ..hd("Indicador", "Valor", "Fecha", "Qué significa"),
    ..d.extras.map(e => (text(weight: "semibold")[#e.name], text(weight: "bold")[#e.value], text(size: 8pt, fill: muted)[#e.date], text(size: 8.4pt)[#e.reading])).flatten())
]

// ───────────── historia del lote ─────────────
#sec[Qué pasó en este lugar en cada fase (octubre a marzo, desde 1991)]
#if d.groups.len() > 0 [
  #table(columns: (1.6fr, auto, auto, auto, auto), stroke: none, inset: (x: 4pt, y: 4pt),
    fill: (x, y) => if y == 0 { none } else if calc.odd(y) { soft } else { none },
    ..hd("Fase", "Temporadas", "Lluvia mediana", "vs neutral", "Más lluviosas que neutral"),
    ..d.groups.map(g => (text(weight: "semibold")[#g.name], [#g.n], [#g.median mm], text(weight: "bold")[#g.vs], [#g.wetter])).flatten())
  #note[Base neutral: #d.base mm. Más lluviosas: #d.wettest. Más secas: #d.driest.]
] else [#note[Sin historia disponible para este punto.]]

#if d.seasons.len() > 1 {
  let H = 46mm
  let vals = d.seasons.map(s => s.pct)
  let hi = calc.max(40, ..vals)
  let lo = calc.min(-40, ..vals)
  v(6pt)
  block(width: 100%, height: H + 16pt, breakable: false, layout(size => {
    let n = d.seasons.len()
    let g = 22pt
    let W = size.width - g
    let bw = W / n
    let y(v) = (hi - v) / (hi - lo) * H
    place(dx: g, dy: y(0), line(length: W, stroke: 0.6pt + muted))
    for k in (lo, 0, hi) { place(dx: 0pt, dy: y(k) - 4pt, box(width: g - 3pt, align(right, text(size: 6.3pt, fill: muted)[#calc.round(k)%]))) }
    for (i, s) in d.seasons.enumerate() {
      let c = if s.phase.starts-with("El Niño") { warm } else if s.phase.starts-with("La Niña") { cool } else { rgb("#98a2b3") }
      let top = calc.min(y(s.pct), y(0))
      let h = calc.abs(y(s.pct) - y(0))
      place(dx: g + i * bw + bw * 0.15, dy: top, rect(width: bw * 0.7, height: calc.max(h, 0.6pt), fill: c, radius: 1pt))
      if calc.rem(i, 3) == 0 { place(dx: g + i * bw - 4pt, dy: H + 4pt, text(size: 5.8pt, fill: muted)[#s.season]) }
    }
  }))
  note[Cada barra es una temporada: % de lluvia respecto de la mediana de los años neutrales. Naranja: El Niño · azul: La Niña · gris: neutral.]
}

// ───────────── Sudamérica ─────────────

#sec[El Niño en Sudamérica, ahora]
#text(size: 8.6pt)[Para #d.sa.len() localidades: lluvia de los últimos 90 días contra lo normal, lo que El Niño fuerte trajo históricamente en #d.sa_season y la lluvia pronosticada para los próximos 16 días.]
#if not d.sa_ref [#linebreak() #note[La referencia histórica de las localidades todavía se está calculando; por ahora se muestra sólo lo observado.]]
#v(4pt)
#set text(size: 7.6pt)
#table(columns: (1.5fr, 0.9fr, auto, auto, auto, 1.4fr), stroke: none, inset: (x: 3pt, y: 2.6pt),
  fill: (x, y) => if y == 0 { none } else if calc.odd(y) { soft } else { none },
  ..hd("Localidad", "País", "90 días", "Esperado Niño fuerte", "Próx. 16 días", "Lectura"),
  ..d.sa.map(r => (text(weight: "semibold")[#r.name], text(fill: muted)[#r.country], text(weight: "bold", fill: pc(r.now_v))[#r.now],
                   text(fill: pc(r.exp_v))[#r.exp], [#r.next], [#r.signal])).flatten())
#set text(size: 9.4pt)

#sec[Fuentes y alcances]
#set text(size: 8pt)
- Alisios, calor del océano, OLR y MJO: NOAA Climate Prediction Center. Volumen de agua cálida: NOAA PMEL (boyas TAO). Niño 3.4, 1+2, 4, ONI, SOI, MEI e IOD: NOAA Physical Sciences Laboratory.
- Lluvia histórica y de los últimos 90 días: Copernicus ERA5 (grilla de ~25 km, ~6 días de demora) vía Open-Meteo. Próximos 16 días: modelos globales vía Open-Meteo.
- La fase de cada temporada sale del ONI promedio de octubre a diciembre. Cada El Niño es distinto: esto es la historia del lugar, no un pronóstico.
- Pronósticos oficiales: IRI (Universidad de Columbia), NOAA CPC y la perspectiva trimestral del servicio meteorológico de cada país.
#if d.errors != "" [#note[Fuentes que no respondieron al generar el informe: #d.errors.]]
