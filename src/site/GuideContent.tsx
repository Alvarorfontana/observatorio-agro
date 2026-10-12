/**
 * Guía pública "Cómo funciona DOTS", escrita para productores y no para ingenieros.
 * Explica qué es DOTS, el lote, de dónde sale cada dato (qué satélite o modelo),
 * cómo se procesa, cómo se usa y cuáles son sus límites.
 * Si cambia una fuente en el observatorio, hay que actualizar esta tabla.
 */
import React from "react";

const STEPS: [string, string, string][] = [
  ["Delimitás el lote", "Dibujás el contorno del potrero en el mapa, lo tomás automático o lo importás desde Google Earth.", "Tu lote queda como un polígono: una figura con sus esquinas, su superficie en hectáreas y su perímetro."],
  ["DOTS consulta las fuentes", "Con ese contorno, DOTS pregunta a satélites, modelos del tiempo, estaciones y bases de suelo qué saben de ese lugar.", "Cada consulta va con la ubicación y la fecha. Si una fuente no responde, queda anotado."],
  ["Recorta y procesa sobre tu lote", "De cada imagen o grilla se toma solo lo que cae dentro de tu lote. Se sacan las nubes y se calculan los índices.", "Por ejemplo, el NDVI se calcula píxel por píxel de 10 × 10 metros y después se promedia dentro del potrero."],
  ["Interpreta con reglas claras", "Los valores se comparan con umbrales conocidos: cuándo el calor estresa al rodeo, cuándo falta agua, cuándo el pasto está flojo.", "Así se arma el semáforo de la semana: verde, amarillo o rojo. Las reglas están escritas y son siempre las mismas."],
  ["Te entrega la lectura y el informe", "Ves el tablero del lote y podés descargar el Informe Territorial en PDF.", "Cada número dice de dónde salió, de qué fecha es y qué tan confiable es."],
];

const LAYERS: [string, string, string][] = [
  ["Vigor del pasto (NDVI)", "Mide qué tan verde y activa está la vegetación, mirando cómo refleja la luz roja y la infrarroja. Va de 0 a 1.", "Más de 0,5: pasto con buen vigor. Entre 0,3 y 0,5: medio. Menos de 0,3: pasto pobre, suelo desnudo o seco."],
  ["Estrés del rodeo (THI)", "Combina temperatura y humedad del aire en un solo número: el índice de temperatura y humedad.", "Menos de 72: sin estrés. De 72 a 79: alerta. 79 o más: peligro para la hacienda."],
  ["Balance de agua", "Resta lo que llueve menos lo que la atmósfera le saca al suelo y a las plantas (evapotranspiración).", "Negativo: el campo pierde agua. Positivo: la gana. Se mira por semana."],
  ["Humedad del suelo", "Cuánta agua hay en el suelo a distintas profundidades, de 0 a 81 cm, según modelos.", "Se expresa en m³ de agua por m³ de suelo. Menos de 0,12 en superficie indica suelo seco."],
  ["Lluvia contra lo normal (SPI)", "Compara la lluvia que cayó con la de un mes típico entre 1991 y 2020.", "SPI menor a −1: período seco. Mayor a +1: lluvioso. Cerca de 0: normal."],
  ["Relieve y anegamiento", "Usa un modelo de alturas del terreno para encontrar los bajos donde se junta el agua y por dónde escurre.", "Marca la posición del lote (bajo, media loma o loma), los bajos cerrados y su propensión a anegarse."],
  ["Focos de calor", "Satélites que detectan puntos muy calientes en la superficie, como incendios o quemas.", "Que no haya focos no garantiza que no haya fuego: puede haber nubes o pasar entre dos órbitas."],
  ["Deforestación y carbono", "Compara la cobertura de árboles del lote año por año desde 2017, con corte en 2020.", "Sirve para la exigencia europea de carne libre de deforestación. No es una certificación legal."],
  ["Pasto y carga", "Estima cuánto pasto crece por día y cuántos animales puede sostener el lote.", "Se expresa en kg de materia seca por hectárea por día y en equivalentes vaca (EV) por hectárea. Es una estimación: conviene validarla con un corte."],
  ["El Niño y La Niña", "Índices del océano Pacífico y del Atlántico que anticipan si la temporada viene más lluviosa o más seca.", "Describen la tendencia de la región, no el lote en particular."],
];

// dato → fuente → satélite o modelo → detalle → actualización
const SOURCES: [string, string, string, string, string][] = [
  ["Vigor del pasto (NDVI)", "Sentinel-2 · ESA / Copernicus, vía Microsoft Planetary Computer", "Satélite óptico", "10 m · nubes excluidas", "Cada 5 días aprox., si no hay nubes"],
  ["Imagen de fondo del mapa", "Esri World Imagery", "Mosaico de varios satélites (Maxar y otros)", "Muy alta resolución", "Fecha distinta según la zona"],
  ["Clima y pronóstico", "Open-Meteo", "Modelos ECMWF, GFS, ICON y otros", "Grilla de algunos kilómetros", "Cada hora"],
  ["Clima de los últimos 30 años", "ERA5 (Copernicus) y NASA POWER", "Reanálisis: modelo + observaciones", "Grilla de ~25 km", "Diario"],
  ["Lluvia observada y sequía", "CHIRPS · Climate Hazards Center (UCSB)", "Satélite + estaciones", "~5 km", "Mensual"],
  ["Relieve y anegamiento", "Copernicus DEM GLO-30", "Satélites de radar TanDEM-X", "30 m", "Modelo fijo (2011–2015)"],
  ["Focos de calor", "NASA FIRMS", "Satélites MODIS y VIIRS", "375 m a 1 km", "Varias veces por día"],
  ["Cobertura y deforestación", "Impact Observatory y ESA WorldCover", "Sentinel-2", "10 m", "Anual"],
  ["Límites automáticos de lotes", "Fields of the World (PRUE)", "Sentinel-2 + modelo de detección", "Contornos de lotes", "Mapa 2025"],
  ["Suelo: carbono y nitrógeno", "ISRIC SoilGrids", "Modelo global de suelos", "250 m", "Fijo"],
  ["Humedad del suelo (capa del mapa)", "NASA SMAP", "Satélite de microondas + modelo", "9 km", "Cada 3 horas"],
  ["Nubes en tiempo real", "NOAA GOES-East", "Satélite geoestacionario", "2 km", "Cada 10 minutos"],
  ["Ríos y caudales", "INA (Argentina) y GloFAS (Copernicus)", "Estaciones y modelo hidrológico", "Por estación o río", "Diario"],
  ["El Niño y teleconexiones", "NOAA", "Índices oceánicos", "Escala global", "Mensual"],
];

const USE: [string, string][] = [
  ["Abrí el Observatorio", "Desde el botón “Abrir Observatorio”. Funciona en la computadora y en el celular."],
  ["Buscá tu campo", "Escribí la localidad o el paraje en el buscador, o mové el mapa hasta tu establecimiento."],
  ["Creá tus lotes", "Elegí triángulo, rectángulo o polígono libre y marcá las esquinas. También podés tocar “Automático” o importar tus potreros de Google Earth (archivo KML)."],
  ["Mirá el Tablero", "Arriba ves el semáforo de la semana: agua, pasto y calor. Debajo, las cifras y los gráficos del lote."],
  ["Tocá para ver el detalle", "Cada recuadro abre su dato. En la vista Mapa ves las capas sobre el potrero."],
  ["Descargá el informe", "El botón “Informe PDF” arma un documento con todo lo del lote, listo para compartir."],
];

const WORDS: [string, string][] = [
  ["Polígono", "La figura que forma el contorno de tu lote en el mapa."],
  ["Píxel", "El cuadradito más chico que ve un satélite. En Sentinel-2 mide 10 × 10 metros."],
  ["Resolución", "El tamaño de ese cuadradito. Cuanto más chico, más detalle."],
  ["Escena", "Una foto del satélite tomada un día y una hora determinados."],
  ["Modelo", "Un cálculo por computadora que estima una variable cuando no hay medición directa, como el pronóstico."],
  ["Reanálisis", "Un modelo que reconstruye el clima del pasado mezclando cálculos con mediciones reales."],
  ["Índice", "Un número que resume varias mediciones, como el NDVI o el THI."],
  ["Grilla", "La malla de cuadrados en la que un modelo divide el territorio. Un lote chico puede caer en un solo cuadrado."],
];

const AUDIENCE: [string, string, string][] = [
  ["Productores", "Saber esta semana si al potrero le falta agua, si el pasto viene bien y si el calor va a castigar a la hacienda.", "Y llevarse un informe para el banco, el comprador o el asesor."],
  ["Estudiantes", "Ver en un caso real cómo se mide la vegetación desde el espacio, qué es un modelo del tiempo o cómo se forma un bajo.", "Cada dato dice de dónde sale: sirve para aprender y para citar."],
  ["Profesionales", "Ingenieros, veterinarios y técnicos: una primera lectura del lote antes de ir a campo, con fuente, fecha y método.", "Para llegar a la recorrida sabiendo dónde mirar."],
  ["Periodistas y divulgadores", "Contar una sequía, una inundación o un desmonte con datos de satélite verificables, no con impresiones.", "Cada gráfico se puede rastrear hasta su fuente original."],
];

export function GuideContent({ onDemo }: { onDemo: () => void }) {
  return (
    <>
      <section className="guide-hook">
        <p className="guide-hook-big">Ahora mismo, a 786 kilómetros de altura, un satélite europeo está fotografiando el campo argentino. Vuelve a pasar por el mismo lugar cada cinco días.</p>
        <p>Esa foto dice cuánto vigor tiene el pasto, potrero por potrero. Y no está sola: modelos del tiempo, sensores de lluvia, radares que midieron cada loma del país y satélites que detectan un fuego desde el espacio también tienen algo que decir sobre ese pedazo de tierra.</p>
        <p><b>DOTS junta todo eso y te lo cuenta en idioma claro.</b> Desde el navegador, sin instalar nada, y diciendo siempre de dónde salió cada número.</p>
      </section>

      <section className="guide-audience">
        <span className="section-tag">PARA QUIÉN ES</span>
        <h2>No hace falta ser ingeniero.</h2>
        <div className="guide-four">{AUDIENCE.map(([t, a, b]) => <article key={t}><h3>{t}</h3><p>{a}</p><small>{b}</small></article>)}</div>
      </section>

      <section className="guide-intro">
        <div>
          <span className="section-tag">QUÉ ES DOTS</span>
          <h2>Datos, Observación, Territorio y Satélite.</h2>
        </div>
        <div>
          <p>DOTS junta en un solo lugar lo que hoy está desparramado: el satélite, el pronóstico, la lluvia, el suelo, el agua y los riesgos de un campo. Y lo ordena alrededor de la unidad con la que se trabaja todos los días en el campo: <b>el lote o potrero</b>.</p>
          <p>No reemplaza la recorrida ni al especialista. Muestra qué está pasando, de dónde sale cada dato y qué tan confiable es. Si algo falta, lo dice. Nunca inventa un número.</p>
        </div>
      </section>

      <section className="guide-lot">
        <span className="section-tag">EL LOTE, LA UNIDAD DE TODO</span>
        <h2>Todo empieza en el contorno de tu potrero.</h2>
        <p>Cada consulta, cada gráfico y cada informe se calcula sobre el lote que elegiste: no sobre la provincia ni sobre un punto suelto. Puede ser tu campo, el de un caso que estás estudiando o el de una nota que estás escribiendo. Lo primero es delimitarlo. Hay tres formas:</p>
        <div className="guide-three">
          <article><b>Dibujarlo</b><p>Marcás las esquinas en el mapa: triángulo, rectángulo o polígono libre.</p></article>
          <article><b>Automático</b><p>Tocás dentro de un lote y DOTS toma el contorno de un mapa mundial de lotes detectados por satélite. Verde: contorno confiable. Ámbar: revisá el borde.</p></article>
          <article><b>Importarlo</b><p>Subís el archivo KML de Google Earth o un GeoJSON y se cargan todos tus potreros con su nombre.</p></article>
        </div>
        <p className="guide-note">Por ahora los lotes viven en tu navegador mientras usás la página. Para no perderlos, descargalos con “Descargar KML” y volvé a importarlos cuando quieras.</p>
      </section>

      <section className="guide-steps">
        <span className="section-tag">CÓMO SE GENERA LA INFORMACIÓN</span>
        <h2>Cinco pasos, de la foto del satélite a la decisión.</h2>
        <ol>{STEPS.map(([t, a, b], i) => <li key={t}><span>{i + 1}</span><div><h3>{t}</h3><p>{a}</p><small>{b}</small></div></li>)}</ol>
      </section>

      <section className="guide-layers">
        <span className="section-tag">QUÉ ES CADA COSA</span>
        <h2>Las capas de información, explicadas sin vueltas.</h2>
        <div className="guide-grid">{LAYERS.map(([t, a, b]) => <article key={t}><h3>{t}</h3><p>{a}</p><p className="guide-read"><b>Cómo leerlo:</b> {b}</p></article>)}</div>
      </section>

      <section className="guide-sources">
        <span className="section-tag">DE DÓNDE SALE CADA DATO</span>
        <h2>Qué satélite o qué modelo hay detrás de cada número.</h2>
        <p>Algunos datos se <b>observan</b> (un satélite o una estación los mide), otros se <b>modelan</b> (una computadora los estima) y otros se <b>calculan</b> en DOTS a partir de los anteriores. El tablero y el informe siempre dicen cuál es cuál.</p>
        <div className="guide-table-wrap"><table className="guide-table">
          <thead><tr><th>Dato</th><th>Fuente</th><th>Satélite o modelo</th><th>Detalle</th><th>Se actualiza</th></tr></thead>
          <tbody>{SOURCES.map(r => <tr key={r[0]}>{r.map((c, i) => <td key={i}>{c}</td>)}</tr>)}</tbody>
        </table></div>
      </section>

      <section className="guide-count">
        <span className="section-tag">CUÁNTO TRABAJO HAY DETRÁS</span>
        <h2>Lo que pasa cuando abrís un lote.</h2>
        <div className="guide-numbers">
          <article><b>17</b><span>módulos de datos principales: clima, pasto, lluvia, suelo, relieve, ríos, riesgos y más.</span></article>
          <article><b>6</b><span>servicios meteorológicos nacionales con estaciones: Argentina, Brasil, Chile, Canadá, Estados Unidos y Noruega.</span></article>
          <article><b>+30</b><span>conectores globales (NASA, ESA, NOAA, Copernicus y otros). Algunos todavía esperan credenciales y figuran como pendientes.</span></article>
          <article><b>Miles</b><span>de cálculos por lote: el relieve analiza decenas de miles de celdas de 30 m y el NDVI revisa hasta seis fotos satelitales recientes.</span></article>
        </div>
        <p>El relieve se calcula en tu propio navegador, sin servidor y sin costo. Las interpretaciones del semáforo y las alertas usan reglas escritas y revisables: no hay inteligencia artificial decidiendo por vos.</p>
      </section>

      <section className="guide-use">
        <span className="section-tag">CÓMO USARLO</span>
        <h2>Seis pasos para empezar. Probalo con cualquier campo del país.</h2>
        <ol>{USE.map(([t, d], i) => <li key={t}><b>{i + 1}. {t}</b><span>{d}</span></li>)}</ol>
        <button onClick={onDemo}>Abrir el Observatorio →</button>
      </section>

      <section className="guide-limits">
        <span className="section-tag">LO QUE TENÉS QUE SABER</span>
        <h2>Los límites, dichos de frente.</h2>
        <ul>
          <li><b>Las nubes tapan al satélite óptico.</b> Si estuvo nublado, el NDVI usa la última foto despejada y te dice la fecha.</li>
          <li><b>Los modelos del tiempo trabajan en grillas de kilómetros.</b> Describen la zona; un bajo o una loma pueden tener su propio microclima.</li>
          <li><b>El relieve sale de un modelo de superficie.</b> Montes y galpones suman altura. Indica tendencias, no centímetros exactos.</li>
          <li><b>Que no haya un foco de calor no garantiza que no haya fuego.</b> Puede haber nubes o pasar entre dos pasadas del satélite.</li>
          <li><b>Las estimaciones de pasto y carga son orientativas.</b> Conviene contrastarlas con un corte y con tu experiencia.</li>
          <li><b>Si una fuente no responde, el dato queda vacío.</b> DOTS nunca lo reemplaza por un cero ni por un número supuesto.</li>
        </ul>
      </section>

      <section className="guide-words">
        <span className="section-tag">PALABRAS QUE VAS A VER</span>
        <h2>Glosario corto.</h2>
        <dl>{WORDS.map(([w, d]) => <div key={w}><dt>{w}</dt><dd>{d}</dd></div>)}</dl>
      </section>
    </>
  );
}
