// DOTS / Campo — plantilla del informe territorial (Typst).
// Los datos llegan ya formateados desde report_typst.py vía sys.inputs.data (JSON).
#let d = json(bytes(sys.inputs.data))

#let ink = rgb("#101828")
#let ink2 = rgb("#344054")
#let muted = rgb("#667085")
#let line-c = rgb("#e4e7ec")
#let soft = rgb("#f2f4f7")
#let brand = rgb("#0f9fa6")
#let brand-dark = rgb("#0b2b33")
#let brand-soft = rgb("#e6f6f7")
#let ok = rgb("#039855")
#let warn = rgb("#dc6803")
#let risk = rgb("#d92d20")
#let tone(t) = if t == "ok" { ok } else if t == "warn" { warn } else if t == "risk" { risk } else { muted }

#set document(title: d.title, author: "DOTS / Campo")
#set text(font: "IBM Plex Sans", size: 9.5pt, fill: ink, lang: "es")
#set par(leading: 0.62em, justify: false)
#set page(
  paper: "a4",
  margin: (top: 22mm, bottom: 20mm, x: 18mm),
  header: context {
    if counter(page).get().first() > 1 {
      set text(size: 7.5pt, fill: muted)
      grid(columns: (1fr, auto),
        [*DOTS* #text(fill: brand)[\/ CAMPO] · #d.lot.name],
        [#d.generated],
      )
      v(-2pt)
      line(length: 100%, stroke: 0.5pt + line-c)
    }
  },
  footer: context {
    set text(size: 7.5pt, fill: muted)
    line(length: 100%, stroke: 0.5pt + line-c)
    v(-2pt)
    grid(columns: (1fr, auto),
      [Informe generado con datos públicos y trazables. No reemplaza la recorrida a campo.],
      [Página #counter(page).display() de #counter(page).final().first()],
    )
  },
)

#let kicker(t) = text(size: 7.5pt, weight: "semibold", fill: brand, tracking: 0.12em, upper(t))
#let section(n, t) = {
  v(10pt)
  grid(columns: (auto, 1fr), column-gutter: 8pt, align: horizon,
    box(fill: brand-soft, inset: (x: 6pt, y: 3pt), radius: 4pt, text(size: 8pt, weight: "bold", fill: brand)[#n]),
    text(size: 14pt, weight: "semibold")[#t],
  )
  v(4pt)
}
#let card(body, fill: white, stroke: 0.6pt + line-c) = block(fill: fill, stroke: stroke, radius: 8pt, inset: 10pt, width: 100%, body)

#let kpi(k) = card[
  #text(size: 7.5pt, fill: muted)[#k.label]
  #v(1pt)
  #text(size: 18pt, weight: "bold", fill: tone(k.tone))[#k.value]#text(size: 8pt, fill: muted)[ #k.unit]
  #v(1pt)
  #text(size: 7pt, fill: muted)[#k.hint]
]

// Dibujo del lote: coordenadas normalizadas 0..1 (x hacia el este, y hacia el sur)
#let lot-shape(pts, w: 62mm, h: 62mm) = box(width: w, height: h, {
  if pts.len() >= 3 {
    place(polygon(
      fill: brand.transparentize(78%),
      stroke: 1.4pt + brand,
      ..pts.map(p => (p.at(0) * w, p.at(1) * h)),
    ))
  } else {
    place(center + horizon, text(fill: muted, size: 8pt)[Sin polígono: consulta por punto])
  }
})

// Gráfico de barras simple
#let bars(labels, series, unit: "", w: 100%, h: 46mm, colors: (brand, rgb("#e9a23b"))) = {
  let all = series.map(s => s.values).flatten().filter(v => v != none)
  let mx = if all.len() > 0 { calc.max(..all, 0.0001) } else { 1 }
  let n = labels.len()
  block(width: w, height: h + 14pt, layout(size => {
    let cw = size.width / calc.max(n, 1)
    let bw = (cw - 6pt) / calc.max(series.len(), 1)
    for (i, lab) in labels.enumerate() {
      for (j, s) in series.enumerate() {
        let v = s.values.at(i, default: none)
        if v != none {
          let bh = h * (v / mx)
          place(dx: i * cw + 3pt + j * bw, dy: h - bh, rect(width: bw - 1pt, height: bh, fill: colors.at(j, default: brand), radius: (top: 1.5pt)))
        }
      }
      place(dx: i * cw, dy: h + 3pt, box(width: cw, align(center, text(size: 6.5pt, fill: muted)[#lab])))
    }
    place(dx: 0pt, dy: h, line(length: size.width, stroke: 0.5pt + line-c))
    place(dx: 0pt, dy: -1pt, text(size: 6.5pt, fill: muted)[máx #calc.round(mx, digits: 1) #unit])
  }))
}

// Gráfico de línea simple
#let linechart(labels, values, lo: none, hi: none, w: 100%, h: 46mm, color: brand) = {
  let vs = values.filter(v => v != none)
  let mn = if lo != none { lo } else if vs.len() > 0 { calc.min(..vs) } else { 0 }
  let mx = if hi != none { hi } else if vs.len() > 0 { calc.max(..vs) } else { 1 }
  let span = if mx - mn == 0 { 1 } else { mx - mn }
  block(width: w, height: h + 14pt, layout(size => {
    let n = values.len()
    let step = if n > 1 { size.width / (n - 1) } else { size.width }
    let pts = ()
    for (i, v) in values.enumerate() {
      if v != none { pts.push((i * step, h - h * (v - mn) / span)) }
    }
    for k in range(5) {
      place(dx: 0pt, dy: h * k / 4, line(length: size.width, stroke: 0.4pt + line-c))
    }
    if pts.len() > 1 { place(curve(stroke: 1.6pt + color, curve.move(pts.first()), ..pts.slice(1).map(p => curve.line(p)))) }
    for p in pts { place(dx: p.at(0) - 2pt, dy: p.at(1) - 2pt, circle(radius: 2pt, fill: color)) }
    for (i, lab) in labels.enumerate() {
      if calc.rem(i, calc.max(1, calc.ceil(n / 6))) == 0 or i == n - 1 {
        place(dx: i * step - 14pt, dy: h + 3pt, box(width: 28pt, align(center, text(size: 6.5pt, fill: muted)[#lab])))
      }
    }
    place(dx: 0pt, dy: -1pt, text(size: 6.5pt, fill: muted)[#calc.round(mx, digits: 2)])
    place(dx: 0pt, dy: h - 8pt, text(size: 6.5pt, fill: muted)[#calc.round(mn, digits: 2)])
  }))
}

#let pill(t, c) = box(fill: c.transparentize(88%), inset: (x: 5pt, y: 2pt), radius: 8pt, text(size: 7pt, weight: "semibold", fill: c)[#t])

// ─────────────────────────── PORTADA ───────────────────────────
#block(width: 100%, fill: brand-dark, radius: 12pt, inset: 18pt)[
  #set text(fill: white)
  #grid(columns: (1fr, auto), align: horizon,
    [#text(size: 13pt, weight: "bold", tracking: 0.08em)[DOTS] #text(size: 13pt, weight: "bold", fill: rgb("#57dce0"), tracking: 0.08em)[\/ CAMPO]
     #h(6pt) #text(size: 7.5pt, fill: rgb("#98a2b3"), tracking: 0.1em)[OBSERVATORIO GANADERO]],
    text(size: 8pt, fill: rgb("#98a2b3"))[#d.generated],
  )
  #v(14pt)
  #text(size: 8pt, fill: rgb("#57dce0"), tracking: 0.14em, weight: "semibold")[INFORME TERRITORIAL DEL LOTE]
  #v(2pt)
  #text(size: 24pt, weight: "bold")[#d.lot.name]
  #v(2pt)
  #text(size: 9.5pt, fill: rgb("#d0d5dd"))[#d.place]
]

#v(10pt)
#grid(columns: (66mm, 1fr), column-gutter: 12pt,
  card(fill: soft, stroke: none)[
    #kicker[Límite del lote]
    #v(4pt)
    #align(center, lot-shape(d.lot.shape))
    #v(4pt)
    #text(size: 7pt, fill: muted)[#d.lot.origin]
  ],
  [
    #grid(columns: (1fr, 1fr), gutter: 8pt, ..d.kpis.map(kpi))
    #v(8pt)
    #card[
      #kicker[Ficha del lote]
      #v(3pt)
      #table(columns: (1fr, auto), stroke: none, inset: (x: 0pt, y: 3pt),
        ..d.lot.facts.map(f => (text(fill: muted)[#f.at(0)], text(weight: "semibold")[#f.at(1)])).flatten())
    ]
  ],
)

#section("01", "Resumen ejecutivo")
#card(fill: brand-soft, stroke: none)[
  #grid(columns: (auto, 1fr), column-gutter: 12pt, align: horizon,
    box(width: 26mm)[
      #text(size: 22pt, weight: "bold", fill: brand)[#d.confidence.score]#text(size: 9pt, fill: muted)[/100]
      #linebreak()#text(size: 7pt, fill: muted, tracking: 0.08em)[CONFIANZA #upper(d.confidence.label)]
    ],
    text(size: 10pt)[#d.summary],
  )
]

#if d.recommendations.len() > 0 [
  #v(6pt)
  #text(weight: "semibold")[Recomendaciones operativas]
  #for r in d.recommendations [- #r]
]

// ─────────────────────────── HALLAZGOS ───────────────────────────
#pagebreak()
#section("02", "Hallazgos por dimensión")
#grid(columns: (1fr, 1fr), gutter: 8pt,
  ..d.findings.map(f => card[
    #grid(columns: (1fr, auto), align: horizon, text(weight: "semibold")[#f.topic], pill(f.status, brand))
    #v(3pt)
    #text(size: 8.5pt, fill: ink2)[#f.text]
  ])
)

#if d.metrics.len() > 0 [
  #section("03", "Indicadores medidos")
  #table(
    columns: (1.3fr, 0.8fr, 1.6fr, 1.2fr),
    stroke: (x, y) => (bottom: 0.5pt + line-c),
    inset: (x: 5pt, y: 5pt),
    fill: (x, y) => if y == 0 { soft },
    table.header(..("Variable", "Valor", "Referencia", "Lectura").map(h => text(size: 7.5pt, weight: "semibold", fill: muted)[#h])),
    ..d.metrics.map(m => (text(weight: "medium")[#m.variable], text(weight: "semibold")[#m.value], text(size: 8pt, fill: muted)[#m.reference], text(size: 8pt)[#m.reading])).flatten()
  )
]

// ─────────────────────────── CLIMA Y VEGETACIÓN ───────────────────────────
#if d.charts.len() > 0 [
  #pagebreak()
  #section("04", "Clima y vegetación")
  #grid(columns: (1fr, 1fr), gutter: 10pt,
    ..d.charts.map(ch => card[
      #text(weight: "semibold")[#ch.title]
      #linebreak()#text(size: 7.5pt, fill: muted)[#ch.subtitle]
      #v(6pt)
      #if ch.kind == "bars" {
        bars(ch.labels, ch.series, unit: ch.unit)
      } else {
        linechart(ch.labels, ch.series.at(0).values, lo: ch.at("lo", default: none), hi: ch.at("hi", default: none))
      }
      #if ch.series.len() > 1 [
        #for (j, s) in ch.series.enumerate() [#box(width: 6pt, height: 6pt, fill: (brand, rgb("#e9a23b")).at(j, default: brand), radius: 1pt) #text(size: 7pt)[#s.name] #h(8pt)]
      ]
    ])
  )
]

#if d.indices.len() > 0 [
  #section("05", "Índices agroclimáticos")
  #text(size: 8pt, fill: muted)[#d.indices_note]
  #v(4pt)
  #table(
    columns: (2fr, 0.9fr, 0.9fr, 0.8fr),
    stroke: (x, y) => (bottom: 0.5pt + line-c),
    inset: (x: 5pt, y: 4.5pt),
    fill: (x, y) => if y == 0 { soft },
    align: (left, right, right, right),
    table.header(..d.indices_head.map(h => text(size: 7.5pt, weight: "semibold", fill: muted)[#h])),
    ..d.indices.map(r => (
      [#r.label #text(size: 7pt, fill: muted)[· #r.unit]],
      text(weight: "semibold")[#r.last],
      text(fill: muted)[#r.mean],
      text(fill: tone(r.tone), weight: "semibold")[#r.diff],
    )).flatten()
  )
]

#if d.telecon.len() > 0 [
  #section("06", "El Niño y teleconexiones")
  #if d.enso_text != "" [#card(fill: brand-soft, stroke: none)[#d.enso_text] #v(4pt)]
  #grid(columns: (1fr, 1fr, 1fr, 1fr), gutter: 6pt,
    ..d.telecon.map(t => card[
      #text(size: 7pt, fill: muted)[#t.name]
      #linebreak()#text(size: 13pt, weight: "bold")[#t.value]
      #linebreak()#text(size: 7pt, fill: brand, weight: "semibold")[#t.phase] #text(size: 7pt, fill: muted)[· #t.period]
    ])
  )
]

// ─────────────────────────── LÍMITES Y TRAZABILIDAD ───────────────────────────
#pagebreak()
#if d.warnings.len() > 0 [
  #section("07", "Límites de la lectura")
  #for w in d.warnings [- #text(fill: ink2)[#w]]
]

#section("08", "Trazabilidad de fuentes")
#text(size: 8pt, fill: muted)[#d.evidence_note]
#v(4pt)
#table(
  columns: (1.2fr, 0.7fr, 1.6fr, 0.9fr),
  stroke: (x, y) => (bottom: 0.5pt + line-c),
  inset: (x: 5pt, y: 4pt),
  fill: (x, y) => if y == 0 { soft },
  table.header(..("Fuente", "Estado", "Alcance", "Consulta UTC").map(h => text(size: 7.5pt, weight: "semibold", fill: muted)[#h])),
  ..d.evidence.map(e => (
    text(size: 8pt, weight: "medium")[#e.source],
    pill(e.status, if e.status == "recibido" { ok } else { warn }),
    text(size: 7.5pt, fill: muted)[#e.scope],
    text(size: 7.5pt, font: "IBM Plex Mono")[#e.when],
  )).flatten()
)
#v(8pt)
#text(size: 7pt, fill: muted)[#d.attributions]
