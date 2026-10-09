// DOTS / Campo — Verificación de libre de deforestación y carbono (Typst).
#let d = json(bytes(sys.inputs.data))

#let ink = rgb("#101828")
#let muted = rgb("#667085")
#let line-c = rgb("#e4e7ec")
#let soft = rgb("#f2f4f7")
#let brand = rgb("#0f9fa6")
#let brand-dark = rgb("#0b2b33")
#let ok = rgb("#039855")
#let warn = rgb("#dc6803")
#let risk = rgb("#d92d20")
#let tone(t) = if t == "ok" { ok } else if t == "warn" { warn } else if t == "risk" { risk } else { muted }

#set document(title: d.title, author: "DOTS / Campo")
#set text(font: "IBM Plex Sans", size: 9.5pt, fill: ink, lang: "es")
#set par(leading: 0.62em)
#set page(paper: "a4", margin: (top: 22mm, bottom: 20mm, x: 18mm),
  header: context { if counter(page).get().first() > 1 {
    set text(size: 7.5pt, fill: muted)
    grid(columns: (1fr, auto), [*DOTS* #text(fill: brand)[\/ CAMPO] · Verificación de libre de deforestación · #d.lot.name], [#d.generated])
    v(-2pt); line(length: 100%, stroke: 0.5pt + line-c)
  }},
  footer: context {
    set text(size: 7pt, fill: muted)
    line(length: 100%, stroke: 0.5pt + line-c); v(-2pt)
    grid(columns: (1fr, auto), [Evidencia técnica de apoyo a la debida diligencia. No es una certificación ni una declaración de debida diligencia.],
      [Página #counter(page).display() de #counter(page).final().first()])
  })

#let section(n, t) = { v(10pt); grid(columns: (auto, 1fr), column-gutter: 8pt, align: horizon,
  box(fill: rgb("#e6f6f7"), inset: (x: 6pt, y: 3pt), radius: 4pt, text(size: 8pt, weight: "bold", fill: brand)[#n]),
  text(size: 13.5pt, weight: "semibold")[#t]); v(4pt) }
#let card(body, fill: white) = block(fill: fill, stroke: 0.6pt + line-c, radius: 8pt, inset: 10pt, width: 100%, body)
#let kv(rows) = table(columns: (1fr, 1.4fr), stroke: none, inset: (x: 0pt, y: 3pt),
  ..rows.map(r => (text(fill: muted)[#r.at(0)], text(weight: "semibold")[#r.at(1)])).flatten())

#let lot-shape(pts, w: 60mm, h: 60mm) = box(width: w, height: h, {
  if pts.len() >= 3 { place(polygon(fill: brand.transparentize(80%), stroke: 1.4pt + brand, ..pts.map(p => (p.at(0) * w, p.at(1) * h)))) }
})

// ───────── portada ─────────
#block(width: 100%, fill: brand-dark, radius: 12pt, inset: 18pt)[
  #set text(fill: white)
  #grid(columns: (1fr, auto),
    [#text(size: 13pt, weight: "bold", tracking: 0.08em)[DOTS] #text(size: 13pt, weight: "bold", fill: rgb("#57dce0"))[\/ CAMPO]],
    text(size: 8pt, fill: rgb("#98a2b3"))[#d.generated])
  #v(12pt)
  #text(size: 8pt, fill: rgb("#57dce0"), tracking: 0.14em, weight: "semibold")[VERIFICACIÓN DE LIBRE DE DEFORESTACIÓN Y CARBONO]
  #v(2pt)
  #text(size: 22pt, weight: "bold")[#d.lot.name]
  #v(2pt)
  #text(size: 9.5pt, fill: rgb("#d0d5dd"))[#d.establishment]
]
#v(10pt)
#block(width: 100%, radius: 10pt, inset: 14pt, fill: tone(d.verdict.tone).transparentize(90%), stroke: 1pt + tone(d.verdict.tone))[
  #text(size: 8pt, fill: muted, tracking: 0.08em)[RESULTADO · FECHA DE CORTE #d.cutoff]
  #v(2pt)
  #text(size: 16pt, weight: "bold", fill: tone(d.verdict.tone))[#upper(d.verdict.text)]
  #v(2pt)
  #text(size: 9pt)[#d.verdict.detail]
]
#v(8pt)
#grid(columns: (64mm, 1fr), column-gutter: 12pt,
  card(fill: soft)[#text(size: 7.5pt, fill: muted, weight: "semibold")[LÍMITE DEL LOTE] #v(3pt) #align(center, lot-shape(d.lot.shape))],
  card[#text(size: 7.5pt, fill: muted, weight: "semibold")[IDENTIFICACIÓN Y GEOLOCALIZACIÓN] #v(3pt) #kv(d.lot.facts)],
)

// ───────── resultados ─────────
#section("01", "Cobertura del lote año por año")
#text(size: 8.5pt, fill: muted)[#d.series_note]
#v(4pt)
#table(columns: (0.6fr, 1fr, 1fr, 1fr, 1fr, 1fr), stroke: (x, y) => (bottom: 0.5pt + line-c), inset: (x: 5pt, y: 4.5pt),
  fill: (x, y) => if y == 0 { soft } else if d.series.at(y - 1, default: (cut: false)).cut { rgb("#e6f6f7") },
  align: (left, right, right, right, right, right),
  table.header(..("Año", "Árboles", "Árboles (ha)", "Pastizal", "Cultivo", "Agua").map(h => text(size: 7.5pt, weight: "semibold", fill: muted)[#h])),
  ..d.series.map(r => (text(weight: if r.cut { "bold" } else { "regular" })[#r.year], [#r.trees], [#r.trees_ha], [#r.rangeland], [#r.crops], [#r.water])).flatten())
#v(4pt)
#if d.worldcover != "" [#card(fill: soft)[#text(size: 8.5pt)[*Control independiente.* #d.worldcover]]]

#section("02", "Criterio de evaluación")
#table(columns: (1.2fr, 2fr), stroke: (x, y) => (bottom: 0.5pt + line-c), inset: (x: 5pt, y: 4.5pt),
  ..d.criteria.map(r => (text(weight: "semibold")[#r.at(0)], text(size: 8.5pt)[#r.at(1)])).flatten())

// ───────── carbono ─────────
#if d.carbon.len() > 0 [
  #section("03", "Carbono del suelo y emisiones del rodeo")
  #grid(columns: (1fr, 1fr), gutter: 8pt, ..d.carbon.map(k => card[
    #text(size: 7.5pt, fill: muted)[#k.label]
    #linebreak()#text(size: 14pt, weight: "bold")[#k.value]
    #linebreak()#text(size: 7.5pt, fill: muted)[#k.detail]
  ]))
  #v(3pt)
  #text(size: 7.5pt, fill: muted)[#d.carbon_note]
]

// ───────── marco y método ─────────
#pagebreak()
#section("04", "Marco normativo")
#for p in d.framework [#par(justify: true)[#p] #v(2pt)]

#section("05", "Fuentes y método")
#table(columns: (1.1fr, 2fr), stroke: (x, y) => (bottom: 0.5pt + line-c), inset: (x: 5pt, y: 4.5pt),
  ..d.sources.map(r => (text(weight: "semibold", size: 8.5pt)[#r.at(0)], text(size: 8.5pt)[#r.at(1)])).flatten())

#section("06", "Límites del análisis")
#for l in d.limits [- #text(size: 9pt)[#l]]

#section("07", "Geolocalización (WGS84, 6 decimales)")
#text(size: 8pt, fill: muted)[#d.geo_note]
#v(4pt)
#table(columns: (0.4fr, 1fr, 1fr, 0.4fr, 1fr, 1fr), stroke: (x, y) => (bottom: 0.4pt + line-c), inset: (x: 4pt, y: 3pt),
  fill: (x, y) => if y == 0 { soft }, align: (right, right, right, right, right, right),
  table.header(..("#", "Latitud", "Longitud", "#", "Latitud", "Longitud").map(h => text(size: 7pt, weight: "semibold", fill: muted)[#h])),
  ..d.coords.map(x => text(size: 7.5pt, font: "IBM Plex Mono")[#x]))
#v(4pt)
#text(size: 7.5pt)[Huella SHA-256 del archivo GeoJSON entregado: #text(font: "IBM Plex Mono", size: 7pt)[#d.geo_hash]]

#v(16pt)
#grid(columns: (1fr, 1fr), column-gutter: 24pt,
  [#line(length: 100%, stroke: 0.6pt + muted) #text(size: 8pt, fill: muted)[Responsable técnico · firma y aclaración]],
  [#line(length: 100%, stroke: 0.6pt + muted) #text(size: 8pt, fill: muted)[Productor / titular del establecimiento]])
#v(8pt)
#text(size: 7pt, fill: muted)[#d.attributions]
