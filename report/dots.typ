// DOTS / Campo — plantilla del informe territorial (Typst) · v3
// Los datos llegan ya formateados desde report_typst.py vía sys.inputs.data (JSON).
// Principios: la decisión primero, el lote real a la vista, colores de alerta sólo para alertas,
// gráficos con escala legible y el contenido corrido (sin hojas casi vacías).
#let d = json(bytes(sys.inputs.data))

#let ink = rgb("#101828")
#let ink2 = rgb("#344054")
#let muted = rgb("#667085")
#let line-c = rgb("#e4e7ec")
#let soft = rgb("#f6f7f9")
#let brand = rgb("#0f9fa6")
#let brand-dark = rgb("#0b2b33")
#let brand-soft = rgb("#e6f6f7")
#let brand-light = rgb("#57dce0")
#let rain-c = rgb("#2e90fa")   // lluvia: azul, no se confunde con alertas
#let neutral = rgb("#98a2b3")  // segunda serie: gris, nunca naranja
#let ok = rgb("#039855")
#let warn = rgb("#dc6803")
#let risk = rgb("#d92d20")
#let tone(t) = if t == "ok" { ok } else if t == "warn" { warn } else if t == "risk" { risk } else { muted }

#set document(title: d.title, author: "DOTS / Campo")
#set text(font: "IBM Plex Sans", size: 9.5pt, fill: ink, lang: "es")
#set par(leading: 0.62em, justify: false)
#set page(
  paper: "a4",
  margin: (top: 20mm, bottom: 18mm, x: 16mm),
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

// ─────────────────────────── utilidades ───────────────────────────
#let fmt(v, digits: 1) = {
  let r = calc.round(v, digits: digits)
  let s = if digits == 0 or r == calc.round(r) { str(int(r)) } else { str(r) }
  s.replace(".", ",")
}
// techo "lindo" para ejes: 1, 2, 5 × 10^n
#let nice(x) = {
  if x <= 0 { 1 } else {
    let p = calc.pow(10.0, calc.floor(calc.log(x, base: 10)))
    let f = x / p
    (if f <= 1 { 1 } else if f <= 2 { 2 } else if f <= 2.5 { 2.5 } else if f <= 3 { 3 } else if f <= 4 { 4 } else if f <= 5 { 5 } else if f <= 6 { 6 } else if f <= 8 { 8 } else { 10 }) * p
  }
}
#let sec = counter("dots-section")
#let section(t) = {
  sec.step()
  block(sticky: true, above: 16pt, below: 8pt, grid(columns: (auto, 1fr), column-gutter: 8pt, align: horizon,
    box(fill: brand-soft, inset: (x: 6pt, y: 3pt), radius: 4pt, text(size: 8pt, weight: "bold", fill: brand, context { let n = sec.get().first(); if n < 10 { "0" + str(n) } else { str(n) } })),
    text(size: 13.5pt, weight: "semibold")[#t],
  ))
}
#let kicker(t, fill: brand) = text(size: 7pt, weight: "semibold", fill: fill, tracking: 0.12em, upper(t))
#let card(body, fill: white, stroke: 0.6pt + line-c, inset: 10pt) = block(fill: fill, stroke: stroke, radius: 8pt, inset: inset, width: 100%, breakable: false, body)
#let pill(t, c) = box(fill: c.transparentize(88%), inset: (x: 6pt, y: 2.5pt), radius: 8pt, text(size: 7pt, weight: "semibold", fill: c)[#t])
#let swatch(c) = box(width: 7pt, height: 7pt, fill: c, radius: 1.5pt, baseline: 0.5pt)
#let legend(items) = { set text(size: 7pt, fill: ink2); for (n, c) in items [#swatch(c) #n #h(10pt)] }

// ─────────────────────────── gráficos ───────────────────────────
#let gutter = 24pt
#let ylabel(y, t) = place(dx: 0pt, dy: y - 4pt, box(width: gutter - 5pt, align(right, text(size: 6.5pt, fill: muted)[#t])))
#let xlabels(labels, x0, cw, y, every: 1) = for (i, lab) in labels.enumerate() {
  if calc.rem(i, every) == 0 or i == labels.len() - 1 {
    place(dx: x0 + i * cw, dy: y, box(width: cw, align(center, text(size: 6.5pt, fill: muted)[#lab])))
  }
}

// Barras agrupadas con escala a la izquierda (0, mitad, máximo)
#let bars(labels, series, unit: "", h: 44mm, colors: (brand, neutral)) = {
  let all = series.map(s => s.values).flatten().filter(v => v != none)
  let mx = nice(if all.len() > 0 { calc.max(..all) } else { 1 })
  let n = labels.len()
  block(width: 100%, height: h + 14pt, breakable: false, layout(size => {
    let W = size.width - gutter
    let cw = W / calc.max(n, 1)
    let bw = calc.min((cw - 4pt) / calc.max(series.len(), 1), 14pt)
    let off = (cw - bw * series.len()) / 2
    for k in range(3) {
      let y = h - h * k / 2
      place(dx: gutter, dy: y, line(length: W, stroke: if k == 0 { 0.6pt + ink2.transparentize(60%) } else { 0.4pt + line-c }))
      ylabel(y, fmt(mx * k / 2, digits: if mx < 5 { 1 } else { 0 }))
    }
    for i in range(n) {
      for (j, s) in series.enumerate() {
        let v = s.values.at(i, default: none)
        if v != none and v > 0 {
          let bh = h * (v / mx)
          place(dx: gutter + i * cw + off + j * bw, dy: h - bh, rect(width: bw - 1pt, height: bh, fill: colors.at(j, default: brand), radius: (top: 1.5pt)))
        }
      }
    }
    xlabels(labels, gutter, cw, h + 3pt, every: calc.max(1, calc.ceil(n / 12)))
  }))
}

// Balance diario: lluvia hacia arriba, evapotranspiración hacia abajo, línea de balance acumulado
#let balance(labels, rain, et, h: 46mm) = {
  let n = labels.len()
  let val(a, i) = { let v = a.at(i, default: none); if v == none { 0 } else { v } }
  let cum = ()
  let acc = 0
  for i in range(n) { acc = acc + val(rain, i) - val(et, i); cum.push(acc) }
  let up = nice(calc.max(..range(n).map(i => val(rain, i)), ..cum, 1))
  let down = nice(calc.max(..range(n).map(i => val(et, i)), ..cum.map(c => -c), 1))
  block(width: 100%, height: h + 14pt, breakable: false, layout(size => {
    let W = size.width - gutter
    let cw = W / calc.max(n, 1)
    let y0 = h * up / (up + down)
    let y(v) = y0 - h * v / (up + down)
    for (v, lab) in ((up, "+" + fmt(up, digits: 0)), (0, "0"), (-down, "−" + fmt(down, digits: 0))) {
      place(dx: gutter, dy: y(v), line(length: W, stroke: if v == 0 { 0.7pt + ink2.transparentize(50%) } else { 0.4pt + line-c }))
      ylabel(y(v), lab)
    }
    let bw = calc.min(cw * 0.42, 16pt)
    for i in range(n) {
      let x = gutter + i * cw + (cw - bw) / 2
      let r = val(rain, i)
      let e = val(et, i)
      if r > 0 { place(dx: x, dy: y(r), rect(width: bw, height: y0 - y(r), fill: rain-c, radius: (top: 1.5pt))) }
      if e > 0 { place(dx: x, dy: y0, rect(width: bw, height: y(-e) - y0, fill: neutral.transparentize(35%), radius: (bottom: 1.5pt))) }
    }
    let pts = range(n).map(i => (gutter + i * cw + cw / 2, y(cum.at(i))))
    if pts.len() > 1 { place(curve(stroke: 1.6pt + ink2, curve.move(pts.first()), ..pts.slice(1).map(p => curve.line(p)))) }
    for p in pts { place(dx: p.at(0) - 2pt, dy: p.at(1) - 2pt, circle(radius: 2pt, fill: ink2)) }
    let last = cum.at(n - 1, default: 0)
    let lp = pts.at(n - 1, default: (0pt, 0pt))
    place(dx: lp.at(0) - 30pt, dy: lp.at(1) + (if last < 0 { 5pt } else { -12pt }),
      box(width: 30pt, align(right, text(size: 7pt, weight: "bold", fill: if last < -15 { warn } else { ink2 })[#(if last > 0 { "+" } else { "" })#fmt(last, digits: 0)])))
    xlabels(labels, gutter, cw, h + 3pt)
  }))
}

// Rango diario de temperatura: barra de mínima a máxima, con los valores escritos
#let band(labels, hi, lo, h: 46mm) = {
  let hs = hi.filter(v => v != none)
  let ls = lo.filter(v => v != none)
  let top = if hs.len() > 0 { calc.ceil(calc.max(..hs) / 5) * 5 + 2 } else { 40 }
  let bot = if ls.len() > 0 { calc.floor(calc.min(..ls) / 5) * 5 - 2 } else { 0 }
  let n = labels.len()
  block(width: 100%, height: h + 14pt, breakable: false, layout(size => {
    let W = size.width - gutter
    let cw = W / calc.max(n, 1)
    let y(v) = h - h * (v - bot) / (top - bot)
    for v in range(int(calc.ceil(bot / 5) * 5), int(top) + 1, step: 5) {
      place(dx: gutter, dy: y(v), line(length: W, stroke: if v == 35 { (paint: warn.transparentize(40%), thickness: 0.6pt, dash: "dashed") } else { 0.4pt + line-c }))
      ylabel(y(v), str(v) + "°")
    }
    let bw = calc.min(cw * 0.36, 12pt)
    for i in range(n) {
      let a = hi.at(i, default: none)
      let b = lo.at(i, default: none)
      if a != none and b != none {
        let x = gutter + i * cw + (cw - bw) / 2
        let c = if a >= 35 { warn } else { brand }
        place(dx: x, dy: y(a), rect(width: bw, height: y(b) - y(a), radius: bw / 2, fill: gradient.linear(c, c.lighten(55%), angle: 90deg)))
        place(dx: gutter + i * cw, dy: y(a) - 10pt, box(width: cw, align(center, text(size: 7pt, weight: "bold", fill: if a >= 35 { warn } else { ink })[#fmt(a, digits: 0)°])))
        place(dx: gutter + i * cw, dy: y(b) + 2pt, box(width: cw, align(center, text(size: 6.5pt, fill: muted)[#fmt(b, digits: 0)°])))
      }
    }
    xlabels(labels, gutter, cw, h + 3pt)
  }))
}

// Línea con escala a la izquierda
#let linechart(labels, values, lo: none, hi: none, h: 44mm, color: brand, digits: 2) = {
  let vs = values.filter(v => v != none)
  let mn = if lo != none { lo } else if vs.len() > 0 { calc.min(..vs) } else { 0 }
  let mx = if hi != none { hi } else if vs.len() > 0 { calc.max(..vs) } else { 1 }
  let span = if mx - mn == 0 { 1 } else { mx - mn }
  let n = values.len()
  block(width: 100%, height: h + 14pt, breakable: false, layout(size => {
    let W = size.width - gutter - 8pt
    let step = if n > 1 { W / (n - 1) } else { W }
    for k in range(5) {
      let y = h * k / 4
      place(dx: gutter, dy: y, line(length: W + 8pt, stroke: 0.4pt + line-c))
      if calc.rem(k, 2) == 0 { ylabel(y, fmt(mx - span * k / 4, digits: digits)) }
    }
    let pts = ()
    for (i, v) in values.enumerate() {
      if v != none { pts.push((gutter + 4pt + i * step, h - h * (v - mn) / span)) }
    }
    if pts.len() > 1 {
      place(curve(fill: color.transparentize(88%), stroke: none, curve.move((pts.first().at(0), h)), ..pts.map(p => curve.line(p)), curve.line((pts.last().at(0), h)), curve.close()))
      place(curve(stroke: 1.6pt + color, curve.move(pts.first()), ..pts.slice(1).map(p => curve.line(p))))
    }
    if n <= 16 { for p in pts { place(dx: p.at(0) - 2pt, dy: p.at(1) - 2pt, circle(radius: 2pt, fill: color)) } }
    let every = calc.max(1, calc.ceil(n / 6))
    for (i, lab) in labels.enumerate() {
      if calc.rem(i, every) == 0 or i == n - 1 {
        place(dx: gutter + 4pt + i * step - 14pt, dy: h + 3pt, box(width: 28pt, align(center, text(size: 6.5pt, fill: muted)[#lab])))
      }
    }
  }))
}

#let chart-card(ch) = card[
  #text(weight: "semibold")[#ch.title]
  #linebreak()#text(size: 7.5pt, fill: muted)[#ch.subtitle]
  #v(12pt)
  #if ch.kind == "balance" {
    balance(ch.labels, ch.series.at(0).values, ch.series.at(1).values)
    legend((("Lluvia", rain-c), ("Evapotranspiración", neutral), ("Balance acumulado", ink2)))
  } else if ch.kind == "band" {
    band(ch.labels, ch.series.at(0).values, ch.series.at(1).values)
  } else if ch.kind == "bars" {
    let cs = if ch.series.len() > 1 and ch.series.at(0).name == "Observada" { (rain-c, neutral) } else if ch.unit == "mm" { (rain-c, neutral) } else { (brand, neutral) }
    bars(ch.labels, ch.series, unit: ch.unit, colors: cs)
    if ch.series.len() > 1 { legend(ch.series.enumerate().map(((j, s)) => (s.name, cs.at(j, default: brand)))) }
  } else {
    linechart(ch.labels, ch.series.at(0).values, lo: ch.at("lo", default: none), hi: ch.at("hi", default: none),
      digits: if ch.at("hi", default: none) == 1 { 2 } else { 0 })
  }
]
#let charts-of(g) = d.charts.filter(c => c.at("group", default: "") == g)
#let chart-grid(cs) = if cs.len() > 0 { grid(columns: (1fr, 1fr), gutter: 10pt, ..cs.map(chart-card)) }

// Lote: imagen satelital con el contorno encima (o el contorno solo si no hay imagen)
#let lot-map(lot, w: 64mm) = box(width: w, height: w, radius: 8pt, clip: true, fill: soft, {
  let pts = lot.shape
  if lot.at("image", default: none) != none {
    place(image(bytes(lot.image), width: w, height: w, fit: "stretch"))
  }
  if pts.len() >= 3 {
    let has-img = lot.at("image", default: none) != none
    place(polygon(
      fill: if has-img { brand-light.transparentize(85%) } else { brand.transparentize(80%) },
      stroke: (paint: if has-img { brand-light } else { brand }, thickness: 1.6pt, join: "round"),
      ..pts.map(p => (p.at(0) * w, p.at(1) * w)),
    ))
  } else {
    place(center + horizon, text(fill: muted, size: 8pt)[Sin polígono: consulta por punto])
  }
  place(bottom + right, dx: -6pt, dy: -6pt, box(fill: white.transparentize(15%), inset: (x: 4pt, y: 2pt), radius: 3pt, text(size: 6pt, fill: ink2)[N ↑]))
})

// ─────────────────────────── PORTADA ───────────────────────────
#block(width: 100%, fill: brand-dark, radius: 12pt, inset: (x: 18pt, y: 16pt))[
  #set text(fill: white)
  #grid(columns: (1fr, auto), align: horizon,
    [#text(size: 12pt, weight: "bold", tracking: 0.08em)[DOTS] #text(size: 12pt, weight: "bold", fill: brand-light, tracking: 0.08em)[\/ CAMPO]
     #h(6pt) #text(size: 7pt, fill: rgb("#98a2b3"), tracking: 0.1em)[OBSERVATORIO GANADERO]],
    text(size: 8pt, fill: rgb("#98a2b3"))[#d.generated],
  )
  #v(10pt)
  #text(size: 7.5pt, fill: brand-light, tracking: 0.14em, weight: "semibold")[INFORME TERRITORIAL DEL LOTE]
  #v(1pt)
  #text(size: 22pt, weight: "bold")[#d.lot.name]
  #h(8pt) #text(size: 9pt, fill: rgb("#d0d5dd"))[#d.place]
  #if d.summary != "" [
    #v(6pt)
    #block(width: 92%, text(size: 10pt, fill: rgb("#e4e7ec"))[#d.summary])
  ]
]

#v(10pt)
#kicker("Esta semana en el lote", fill: ink2)
#v(4pt)
#grid(columns: (1fr, 1fr, 1fr), gutter: 8pt, ..d.week.map(w => block(
  width: 100%, height: 80pt, breakable: false, radius: 8pt, clip: true, stroke: 0.6pt + line-c, fill: white, {
    block(width: 100%, height: 4pt, fill: tone(w.tone), above: 0pt, below: 0pt)
    block(inset: (x: 10pt, top: 8pt, bottom: 10pt), above: 0pt)[
      #grid(columns: (1fr, auto), align: horizon, kicker(w.key, fill: muted),
        box(width: 9pt, height: 9pt, radius: 4.5pt, fill: tone(w.tone)))
      #v(2pt)
      #text(size: 12pt, weight: "bold", fill: if w.tone == "idle" { muted } else { tone(w.tone) })[#w.head]
      #linebreak()#text(size: 10pt, weight: "semibold")[#w.value]
      #linebreak()#text(size: 7pt, fill: muted)[#w.hint]
    ]
  })))
#v(4pt)
#text(size: 7pt, fill: muted)[#d.confidence_line]

#v(8pt)
#grid(columns: (64mm, 1fr), column-gutter: 12pt,
  [
    #lot-map(d.lot)
    #v(3pt)
    #text(size: 6.5pt, fill: muted)[#d.lot.origin #d.lot.image_credit]
  ],
  [
    #card(inset: (x: 12pt, y: 10pt))[
      #kicker[Ficha del lote]
      #v(2pt)
      #table(columns: (1fr, auto), stroke: (x, y) => (bottom: 0.4pt + line-c), inset: (x: 0pt, y: 4.5pt), align: (left, right),
        ..d.lot.facts.map(f => (text(fill: muted)[#f.at(0)], text(weight: "semibold")[#f.at(1)])).flatten())
    ]
    #if d.recommendations.len() > 0 [
      #v(6pt)
      #card(fill: brand-soft, stroke: none, inset: (x: 12pt, y: 10pt))[
        #kicker[Qué hacer]
        #v(3pt)
        #for (i, r) in d.recommendations.enumerate() [
          #grid(columns: (16pt, 1fr), align: top,
            move(dy: 0.5pt, box(width: 12pt, height: 12pt, radius: 6pt, fill: brand, align(center + horizon, text(size: 7pt, weight: "bold", fill: white)[#(i + 1)]))),
            text(size: 8.8pt)[#r])
          #v(1pt)
        ]
      ]
    ]
  ],
)

#if d.at("alerts", default: ()).len() > 0 [
  #section("Alertas activas")
  #text(size: 7.5pt, fill: muted)[#d.alerts_note]
  #v(3pt)
  #grid(columns: (1fr, 1fr), gutter: 8pt, ..d.alerts.map(a => block(width: 100%, breakable: false, inset: (left: 10pt, rest: 8pt), radius: (right: 6pt),
    fill: tone(a.tone).transparentize(93%), stroke: (left: 3pt + tone(a.tone)))[
    #text(weight: "semibold", fill: tone(a.tone))[#a.title]
    #linebreak()#text(size: 7pt, fill: muted)[#upper(a.level) · #a.source]
    #linebreak()#text(size: 8.5pt)[#a.detail]
    #linebreak()#text(size: 8.5pt, weight: "medium")[→ #a.action]
  ]))
]

// ─────────────────────────── HALLAZGOS Y VARIABLES ───────────────────────────
#if d.findings.len() > 0 [
  #section("Hallazgos por dimensión")
  #grid(columns: (1fr, 1fr), gutter: 8pt,
    ..d.findings.map(f => block(width: 100%, breakable: false, radius: 8pt, stroke: 0.6pt + line-c, inset: (left: 11pt, rest: 10pt),
      fill: white)[
      #grid(columns: (1fr, auto), align: horizon, text(weight: "semibold")[#f.topic], pill(f.status, ink2))
      #v(3pt)
      #text(size: 8.5pt, fill: ink2)[#f.text]
    ])
  )
]

#if d.metrics.len() > 0 [
  #section("Variables del lote")
  #grid(columns: (1fr, 1fr), column-gutter: 8pt, row-gutter: 6pt,
    ..d.metrics.map(m => block(width: 100%, breakable: false, radius: 8pt, fill: soft, inset: (x: 10pt, y: 8pt))[
      #grid(columns: (3pt, 1fr, auto), column-gutter: 8pt, align: horizon,
        rect(width: 3pt, height: 26pt, radius: 1.5pt, fill: tone(m.tone)),
        [#text(size: 8.5pt, weight: "semibold")[#m.variable]
         #linebreak()#text(size: 6.8pt, fill: muted)[#m.reference]],
        align(right)[
          #text(size: 12.5pt, weight: "bold", fill: if m.tone == "risk" or m.tone == "warn" { tone(m.tone) } else { ink })[#m.value]
          #linebreak()#if m.reading != "" { pill(m.reading, tone(m.tone)) }
        ],
      )
    ])
  )
]

// ─────────────────────────── CLIMA, VEGETACIÓN, LLUVIA ───────────────────────────
#if charts-of("clima").len() > 0 [
  #section("Clima de la semana")
  #chart-grid(charts-of("clima"))
]

#if charts-of("veg").len() > 0 or d.at("forage", default: ()).len() > 0 [
  #section("Vegetación y pasto")
  #if d.at("forage", default: ()).len() > 0 [
    #grid(columns: (1fr, 1fr, 1fr, 1fr), gutter: 6pt, ..d.forage.map(k => card(fill: soft, stroke: none, inset: 9pt)[
      #text(size: 7pt, fill: muted)[#k.label]
      #linebreak()#text(size: 14pt, weight: "bold")[#k.value]#text(size: 7.5pt, fill: muted)[ #k.unit]
    ]))
    #v(6pt)
  ]
  #chart-grid(charts-of("veg"))
  #if d.at("forage_note", default: "") != "" [#v(3pt) #text(size: 7pt, fill: muted)[#d.forage_note]]
]

#if d.at("spi", default: ()).len() > 0 or charts-of("lluvia").len() > 0 [
  #section("Lluvia observada y sequía")
  #text(size: 8pt, fill: muted)[#d.spi_note]
  #v(4pt)
  #grid(columns: (1fr, 1fr, 1fr, 1fr), gutter: 6pt,
    ..d.spi.map(s => card(fill: soft, stroke: none, inset: 9pt)[
      #text(size: 7pt, fill: muted)[#s.label]
      #linebreak()#text(size: 14pt, weight: "bold")[#s.mm]#text(size: 7.5pt, fill: muted)[ mm]
      #linebreak()#text(size: 7.5pt, fill: tone(s.tone), weight: "semibold")[#s.class] #text(size: 7pt, fill: muted)[· SPI #s.spi]
      #linebreak()#text(size: 7pt, fill: muted)[normal #s.normal mm]
    ])
  )
  #if charts-of("lluvia").len() > 0 [
    #v(6pt)
    #card[
      #let ch = charts-of("lluvia").first()
      #text(weight: "semibold")[#ch.title]
      #linebreak()#text(size: 7.5pt, fill: muted)[#ch.subtitle]
      #v(12pt)
      #bars(ch.labels, ch.series, unit: ch.unit, colors: (rain-c, neutral), h: 36mm)
      #legend(ch.series.enumerate().map(((j, s)) => (s.name, (rain-c, neutral).at(j))))
    ]
  ]
]

// ─────────────────────────── RELIEVE ───────────────────────────
#if d.at("relief", default: none) != none [
  #let r = d.relief
  #section("Relieve y anegamiento")
  #grid(columns: (60mm, 1fr), column-gutter: 10pt,
    card(fill: tone(r.tone).transparentize(93%), stroke: none)[
      #kicker("Posición en el paisaje", fill: muted)
      #v(2pt)
      #text(size: 16pt, weight: "bold", fill: tone(r.tone))[#r.position]
      #linebreak()#text(size: 7.5pt, fill: muted)[#r.position_n / 100 respecto del entorno]
      #v(8pt)
      #kicker("Propensión a anegarse", fill: muted)
      #v(3pt)
      #box(width: 100%, height: 9pt, radius: 4.5pt, clip: true, fill: line-c,
        stack(dir: ltr, ..r.risk.filter(x => x.pct > 0).map(x => rect(width: x.pct * 1%, height: 9pt, fill: tone(x.tone)))))
      #v(3pt)
      #for x in r.risk [#box[#swatch(tone(x.tone)) #text(size: 7pt)[#x.label #fmt(x.pct, digits: 0) %]] #h(3pt)]
    ],
    card[
      #table(columns: (1fr, auto, 1fr, auto), stroke: (x, y) => (bottom: 0.4pt + line-c), inset: (x: 3pt, y: 5pt), align: (left, right, left, right),
        ..r.facts.chunks(2).map(pair => pair.map(f => (text(size: 8pt, fill: muted)[#f.at(0)], text(size: 8.5pt, weight: "semibold")[#f.at(1)])).flatten()).flatten())
      #v(3pt)
      #text(size: 6.8pt, fill: muted)[#r.note]
    ],
  )
]

#if d.at("water", default: none) != none [
  #let w = d.water
  #section("Agua detectada por satélite")
  #grid(columns: (1fr, 1fr), column-gutter: 10pt,
    card[
      #table(columns: (1fr, auto), stroke: (x, y) => (bottom: 0.4pt + line-c), inset: (x: 3pt, y: 5pt), align: (left, right),
        ..w.facts.map(f => (text(size: 8pt, fill: muted)[#f.at(0)], text(size: 8.5pt, weight: "semibold")[#f.at(1)])).flatten())
      #v(3pt)
      #text(size: 6.8pt, fill: muted)[#w.note]
    ],
    if w.values.len() > 1 { card[
      #text(weight: "semibold")[Agua en el lote, semana a semana]
      #linebreak()#text(size: 7.5pt, fill: muted)[hectáreas detectadas en cada imagen procesada]
      #v(12pt)
      #bars(w.labels, ((name: "Agua", values: w.values),), unit: "ha", colors: (rain-c,), h: 30mm)
    ] } else { card(fill: soft, stroke: none)[#text(size: 8pt, fill: muted)[La evolución semanal aparece a partir de la segunda imagen procesada.]] },
  )
]

// ─────────────────────────── ÍNDICES, PROBABILIDADES, SUSTENTABILIDAD ───────────────────────────
#if d.indices.len() > 0 [
  #section("Índices agroclimáticos")
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
  #if charts-of("indices").len() > 0 [#v(6pt) #chart-grid(charts-of("indices"))]
]

#if d.at("prob", default: ()).len() > 0 or d.at("seasonal", default: ()).len() > 0 [
  #section("Probabilidades y tendencias")
  #if d.stat_note != "" [#text(size: 8.5pt)[#d.stat_note] #v(4pt)]
  #if d.prob.len() > 0 [
    #table(columns: (0.7fr, 1fr, 1fr, 1fr, 1.2fr), stroke: (x, y) => (bottom: 0.5pt + line-c), inset: (x: 5pt, y: 4pt),
      fill: (x, y) => if y == 0 { soft }, align: (left, right, right, right, right),
      table.header(..("Día", "Prob. helada", "Prob. ≥ 35 °C", "Prob. lluvia ≥ 10 mm", "Mín / máx (mediana)").map(h => text(size: 7.5pt, weight: "semibold", fill: muted)[#h])),
      ..d.prob.map(r => (r.day, r.frost, r.heat, r.rain, r.temps)).flatten().map(x => text(size: 8pt)[#x])
    )
  ]
  #if d.seasonal.len() > 0 [
    #v(6pt)
    #text(weight: "semibold")[Perspectiva estacional ECMWF] #text(size: 7.5pt, fill: muted)[· % de pronósticos con lluvia baja / normal / alta frente a 1991-2020]
    #table(columns: (0.8fr, 0.9fr, 1.5fr, 1.5fr), stroke: (x, y) => (bottom: 0.5pt + line-c), inset: (x: 5pt, y: 4pt),
      ..d.seasonal.map(m => (text(weight: "semibold")[#m.period], text(size: 8pt)[#m.split], text(size: 8pt)[#m.rain], text(size: 8pt, fill: muted)[#m.temp])).flatten()
    )
  ]
  #if d.trends.len() > 0 [
    #v(6pt)
    #text(weight: "semibold")[Tendencias del clima local] #text(size: 7.5pt, fill: muted)[· Mann-Kendall y pendiente de Sen]
    #grid(columns: (1fr, 1fr), gutter: 6pt, ..d.trends.map(tr => card[
      #text(size: 7.5pt, fill: muted)[#tr.label]
      #linebreak()#text(size: 12pt, weight: "bold", fill: tone(tr.tone))[#tr.value]
      #linebreak()#text(size: 7pt, fill: muted)[#tr.reading]
    ]))
  ]
]

#if d.at("costs", default: ()).len() > 0 [
  #section("Costos y logística")
  #grid(columns: (1fr, 1fr, 1fr), gutter: 6pt, ..d.costs.map(k => card(fill: soft, stroke: none, inset: 9pt)[
    #text(size: 7pt, fill: muted)[#k.label]
    #linebreak()#text(size: 13pt, weight: "bold")[#k.value]#text(size: 7.5pt, fill: muted)[ #k.unit]
  ]))
  #if d.costs_lines.len() > 0 [
    #v(4pt)
    #table(columns: (1fr, auto), stroke: (x, y) => (bottom: 0.4pt + line-c), inset: (x: 4pt, y: 3.5pt),
      ..d.costs_lines.map(l => (text(size: 8.5pt)[#l.label], text(size: 8.5pt, weight: "semibold")[#l.value])).flatten())
  ]
  #v(3pt)
  #text(size: 7pt, fill: muted)[#d.costs_note]
]

#if d.at("sust", default: ()).len() > 0 [
  #section("Sustentabilidad")
  #for s in d.sust [
    #block(width: 100%, breakable: false, inset: (left: 9pt, rest: 7pt), radius: (right: 6pt), fill: tone(s.tone).transparentize(93%), stroke: (left: 3pt + tone(s.tone)))[
      #text(size: 7.5pt, fill: muted)[#s.label]
      #linebreak()#text(weight: "semibold", fill: tone(s.tone))[#s.value]
      #linebreak()#text(size: 8pt)[#s.detail]
    ]
    #v(3pt)
  ]
  #text(size: 7pt, fill: muted)[La verificación de cobertura por satélite no es una certificación legal; la debida diligencia de la Unión Europea exige además documentación y trazabilidad.]
]

#if d.telecon.len() > 0 [
  #section("El Niño y teleconexiones")
  #if d.enso_text != "" [#card(fill: brand-soft, stroke: none)[#d.enso_text] #v(4pt)]
  #grid(columns: (1fr, 1fr, 1fr, 1fr), gutter: 6pt,
    ..d.telecon.map(t => card(fill: soft, stroke: none, inset: 9pt)[
      #text(size: 7pt, fill: muted)[#t.name]
      #linebreak()#text(size: 13pt, weight: "bold")[#t.value]
      #linebreak()#text(size: 7pt, fill: brand, weight: "semibold")[#t.phase] #text(size: 7pt, fill: muted)[· #t.period]
    ])
  )
]

// ─────────────────────────── LÍMITES Y TRAZABILIDAD ───────────────────────────
#if d.warnings.len() > 0 [
  #section("Límites de la lectura")
  #for w in d.warnings [- #text(fill: ink2)[#w]]
]

#section("Trazabilidad de fuentes")
#text(size: 8pt, fill: muted)[#d.evidence_note]
#v(4pt)
#table(
  columns: (1.2fr, 0.7fr, 1.6fr, 0.9fr),
  stroke: (x, y) => (bottom: 0.5pt + line-c),
  inset: (x: 5pt, y: 4pt),
  align: horizon,
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
