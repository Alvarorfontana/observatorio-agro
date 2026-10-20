// DOTS / Campo — Informe de campo con mapa para el celular (Typst). Datos desde campo_offline.build vía sys.inputs.data.
#import "identity.typ": name, cover-id
#let d = json(bytes(sys.inputs.data))
#let ink = rgb("#101828")
#let muted = rgb("#5f6e73")
#let line-c = rgb("#e4e7ec")
#let soft = rgb("#f6f7f9")
#let navy = rgb("#0b2b33")

#set document(title: "Informe de campo · " + d.name, author: name)
#set text(font: "IBM Plex Sans", size: 9.6pt, fill: ink, lang: "es")
#set par(leading: 0.6em)
#set page(paper: "a4", margin: (top: 14mm, bottom: 16mm, x: 15mm),
  footer: context {
    set text(size: 7.2pt, fill: muted)
    line(length: 100%, stroke: 0.5pt + line-c)
    v(-2pt)
    grid(columns: (1fr, auto), [Lectura del terreno y de la historia satelital; no reemplaza la recorrida ni un estudio hidrológico.], [observatorio-agro.vercel.app · pág. #counter(page).display()])
  })
#let card(body, fill: soft) = block(fill: fill, radius: 8pt, inset: 10pt, width: 100%, breakable: false, body)
#let sec(t) = block(above: 14pt, below: 6pt, sticky: true, text(size: 12pt, weight: "semibold")[#t])

#cover-id()
#block(width: 100%, fill: navy, radius: 10pt, inset: (x: 16pt, y: 14pt), {
  set text(fill: white)
  grid(columns: (1fr, auto), align: (left + horizon, right + horizon), column-gutter: 12pt,
    [#text(size: 7.6pt, weight: "bold", tracking: 0.14em)[DOTS · INFORME DE CAMPO] #linebreak()
     #text(size: 21pt, weight: "bold")[#d.name] #linebreak()
     #text(size: 8.5pt)[#calc.round(d.area_ha, digits: 1) ha · #d.date] #v(6pt)
     #text(size: 8.6pt)[*Mapa en el celular:* escaneá el código con la cámara y abrilo una vez con señal. Después funciona sin conexión y, con el GPS, te dice en qué zona del campo estás parado.]],
    box(fill: white, radius: 6pt, inset: 4pt, image(bytes(d.qr_svg), format: "svg", width: 40mm)))
})

#v(6pt)
#card[#text(size: 9.8pt)[#d.risk.reading]]

#sec[Lomas, planos y bajos]
#grid(columns: (1.25fr, 1fr), column-gutter: 12pt,
  block(radius: 6pt, clip: true, fill: rgb("#f3f6f6"), image(bytes(d.map_svg), format: "svg", width: 100%)),
  [
    #table(columns: (auto, 1fr, auto, auto), stroke: (x, y) => (bottom: 0.5pt + line-c), inset: (x: 4pt, y: 5pt),
      [], [*Zona*], [*%*], [*ha*],
      ..d.risk.zones.map(z => (box(width: 9pt, height: 9pt, fill: rgb(z.color), radius: 2pt), z.name, str(z.pct), str(z.ha))).flatten())
    #v(4pt)
    #text(size: 8.4pt, fill: muted)[Desnivel del campo: #d.risk.relief_m m (de #d.risk.cuts.min_m a #d.risk.cuts.max_m m). Bajo: hasta #d.risk.cuts.bajo_m m; loma: desde #d.risk.cuts.loma_m m. Altura media sobre el drenaje más cercano: #d.risk.hand_median_m m.]
  ])

#if d.soils != none and d.soils.units.len() > 0 [
  #sec[Suelos (cartografía 1:50.000 del INTA)]
  #text(size: 9.4pt)[#d.soils.reading]
  #table(columns: (auto, 2fr, auto, 1.3fr, auto), stroke: (x, y) => (bottom: 0.5pt + line-c), inset: (x: 4pt, y: 5pt),
    [*Unidad*], [*Composición (series)*], [*Capacidad de uso*], [*Taxonomía*], [*% del campo*],
    ..d.soils.units.map(u => (str(u.symbol), str(u.composition), str(u.capability), str(u.taxonomy), str(u.pct))).flatten())
  #text(size: 7.6pt, fill: muted)[#d.soils.source]
]

#sec[Método y fuentes]
#text(size: 8.6pt)[#d.risk.method]
#v(4pt)
#text(size: 7.6pt, fill: muted)[Enlace del mapa (el campo viaja dentro del enlace y no se guarda en ningún servidor): #link(d.url)[abrir el mapa del campo]. Fondo del mapa: Esri World Imagery.]
