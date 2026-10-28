/**
 * "Todo lo que hace DOTS": catálogo completo de funciones, ordenado por necesidad, con el enlace a donde se hace cada
 * cosa. Complementa la Guía (/guia, cómo se usa) y Módulos (/modulos, método de cada módulo principal).
 * Si se agrega o se quita una función del sitio, hay que actualizar esta lista.
 */
import React from "react";

type Fila = [string, string, string?, string?];          // nombre, qué hace, fuente, enlace
type Tabla = { titulo?: string; cols: string[]; filas: Fila[] };
type Seccion = { id: string; tag: string; titulo: string; lead: string; tablas?: Tabla[]; puntos?: [string, string][]; nota?: string;
  ir?: [string, string] };


const ENLACES: Record<string, string> = {
  "Clima y suelo": "/observatorio?vista=variables", "Comparar modelos globales": "/observatorio?vista=modelos",
  "Probabilidades y tendencias": "/observatorio?vista=estadistica", "Pronóstico estacional": "/observatorio?vista=estacional",
  "Estaciones": "/observatorio?vista=smn", "Histórico reciente": "/observatorio?vista=historico", "Clima de 20 a 30 años": "/observatorio?vista=serie",
  "Índices agroclimáticos": "/observatorio?vista=indices", "Proyección 2031-2040": "/observatorio?vista=proyeccion",
  "Lluvia observada y sequía": "/observatorio?vista=lluvia", "Balance de agua": "/observatorio?vista=balance-agua",
  "Humedad del suelo contra lo normal": "/observatorio?vista=humedad-nasa", "Humedad del suelo por radar": "/observatorio?vista=humedad-sar",
  "Riesgo hídrico": "/observatorio?vista=riesgo-hidrico", "Ríos y caudales": "/observatorio?vista=rios", "Nivel del río": "/observatorio?vista=nivel-rio",
  "Relieve y anegamiento": "/observatorio?vista=relieve", "Nitrógeno y carbono del suelo": "/observatorio?vista=suelo",
  "Focos de incendio": "/observatorio?vista=firms", "Calidad del aire": "/observatorio?vista=aire", "Caminos y transitabilidad": "/observatorio?vista=caminos",
  "Emergencia agropecuaria": "/observatorio?vista=emergencia", "Alertas del lote": "/observatorio?vista=alertas",
  "NDVI del lote": "/observatorio?vista=ndvi", "Índices satelitales": "/observatorio?vista=indices-espectrales",
  "Cobertura reciente": "/observatorio?vista=sustentabilidad", "Cambios año a año": "/observatorio?vista=sustentabilidad",
  "Historia desde 1985": "/observatorio?vista=sustentabilidad", "Historia en imágenes": "/observatorio?vista=copernicus",
  "Pasto y carga": "/observatorio?vista=forraje", "Ganado": "/observatorio?vista=ganado", "Pasto año por año": "/observatorio?vista=forraje",
  "Costos y margen": "/observatorio?vista=costos", "Informe de cultivo": "/cultivos", "Labores": "/cultivos", "Planificación": "/cultivos",
  "Clima avanzado": "/cultivos", "Rinde por agua regional": "/cultivos", "Heladas por satélite": "/focos",
  "Nivel de cada localidad": "/alertas", "Lluvia en las cabeceras": "/alertas", "Represas de Brasil": "/alertas",
  "Caudal de los grandes ríos": "/alertas", "Agua de crecida detectada": "/alertas", "Temporales": "/alertas", "Eventos extremos": "/focos",
  "Población en una zona": "/poblacion", "Gente en la zona baja": "/poblacion#crecidas", "Mapa de la zona baja": "/poblacion#crecidas",
  "Barrios populares": "/poblacion#barrios", "Barrios detectados por radar": "/poblacion#barrios", "Dengue": "/poblacion#salud",
  "Olas de calor": "/poblacion#salud",
  "Verificación libre de deforestación": "/observatorio?vista=sustentabilidad", "Árboles fuera del bosque": "/observatorio?vista=sustentabilidad",
  "¿Puedo vender a la UE?": "/observatorio?vista=sustentabilidad", "Segunda opinión": "/observatorio?vista=sustentabilidad",
  "Informe y polígono": "/observatorio?vista=sustentabilidad",
  "Últimos 120 días": "/satelital#desmontes", "Último verano": "/satelital#desmontes", "Pérdida anual": "/satelital#desmontes", "Gravedad": "/satelital#desmontes",
  "Informe de un campo o lote": "/informes", "Alerta de crecida por localidad": "/informes",
  "Cuenca del Plata": "/informes", "Población en zona baja": "/informes", "El Niño en una localidad": "/informes",
  "Población expuesta en una zona": "/poblacion", "Informe de relieve": "/lente",
};

const C3 = ["Consulta", "Qué te dice", "Fuente"];

const SECCIONES: Seccion[] = [
  {
    id: "lote", tag: "MI CAMPO", titulo: "El tablero del lote.",
    lead: "Con el lote dibujado, el Observatorio arma un tablero con un semáforo semanal de agua, pasto y calor. Cada recuadro abre su detalle, y en la vista Mapa las capas se ven sobre el potrero.",
    ir: ["Abrir el Observatorio", "/observatorio"],
    tablas: [
      { titulo: "Clima y pronóstico", cols: C3, filas: [
        ["Clima y suelo", "Temperatura, humedad, viento, lluvia y evapotranspiración de hoy y de los próximos días", "Open-Meteo (ECMWF, GFS, ICON y otros)"],
        ["Comparar modelos globales", "Qué pronostica cada modelo y cuánto coinciden entre sí", "7 proveedores vía Open-Meteo"],
        ["Probabilidades y tendencias", "Chance de que llueva más de cierto umbral o haga cierto calor, con el abanico de corridas", "Conjuntos ECMWF y GFS, ERA5"],
        ["Pronóstico estacional", "Si los próximos meses vienen más húmedos o más secos que lo normal", "ECMWF SEAS5 (Copernicus)"],
        ["Estaciones", "Datos medidos en las estaciones más cercanas", "SMN, INMET (Brasil) y DMC (Chile)"],
      ] },
      { titulo: "Clima del pasado", cols: C3, filas: [
        ["Histórico reciente", "Cómo vienen las últimas semanas frente a lo normal", "NASA POWER"],
        ["Clima de 20 a 30 años", "Normales por mes y tendencia del lugar", "ERA5 (Copernicus)"],
        ["Índices agroclimáticos", "Días de calor, heladas, rachas secas y lluviosas", "ERA5, definiciones ETCCDI"],
        ["Proyección 2031-2040", "Cómo podría cambiar el clima del lugar en la próxima década", "Modelos climáticos CMIP6"],
      ] },
      { titulo: "Agua", cols: C3, filas: [
        ["Lluvia observada y sequía", "Lluvia caída por mes y el índice de sequía SPI", "CHIRPS (satélite y estaciones, 5 km)"],
        ["Balance de agua", "Lo que llueve menos lo que se evapora, semana a semana, desde 1991", "ERA5"],
        ["Humedad del suelo contra lo normal", "Si el perfil tiene más o menos agua que lo habitual para la fecha", "NASA POWER (MERRA-2)"],
        ["Humedad del suelo por radar", "Si el lote está más húmedo o más seco que en sus pasadas anteriores, aun con nubes", "Sentinel-1"],
        ["Riesgo hídrico", "Qué parte del lote está baja respecto del agua y cuánto se anegó históricamente", "MERIT Hydro y agua superficial del JRC"],
        ["Ríos y caudales", "Caudal pronosticado del río más cercano", "GloFAS (Copernicus)"],
        ["Nivel del río", "Alturas y caudales medidos en la estación más cercana", "INA"],
      ] },
      { titulo: "Suelo, relieve y riesgos", cols: C3, filas: [
        ["Relieve y anegamiento", "Si el lote está en bajo, media loma o loma, dónde se junta el agua y por dónde escurre", "Copernicus DEM 30 m"],
        ["Nitrógeno y carbono del suelo", "Contenido estimado en las primeras capas", "ISRIC SoilGrids (250 m)"],
        ["Focos de incendio", "Fuegos detectados en el lote y alrededor en los últimos días", "NASA FIRMS"],
        ["Calidad del aire", "Humo, polvo y contaminantes", "CAMS (Copernicus)"],
        ["Caminos y transitabilidad", "Qué caminos de acceso pueden estar intransitables por la lluvia de las últimas 72 horas", "OpenStreetMap y Open-Meteo"],
        ["Emergencia agropecuaria", "Respaldo técnico para pedir la emergencia (Ley 26.509)", "ERA5 y Sentinel-1"],
        ["Alertas del lote", "Avisos por helada, calor, lluvia fuerte, sequía y fuego, con reglas escritas y siempre iguales", "Fuentes anteriores"],
      ] },
    ],
  },
  {
    id: "satelites", tag: "SATÉLITES Y VEGETACIÓN", titulo: "El lote visto desde el espacio, desde 1985.",
    lead: "Satélites ópticos, de radar y de temperatura. Las imágenes ópticas necesitan cielo despejado; el radar ve aunque haya nubes.",
    tablas: [
      { titulo: "Sobre tu lote", cols: ["Herramienta", "Qué hace", "Fuente"], filas: [
        ["NDVI del lote", "Vigor de la vegetación píxel por píxel de 10 m, con la última imagen sin nubes y vista en color real", "Sentinel-2", "/observatorio"],
        ["Zonas de vigor", "Divide el lote en zonas de vigor alto, medio y bajo para recorrerlo o manejarlo por ambientes", "Sentinel-2", "/agricultura-precision"],
        ["Índices satelitales", "228 índices de vegetación, agua, suelo y quema calculados sobre el lote", "Sentinel-2 y awesome-spectral-indices", "/agricultura-precision"],
        ["NDVI histórico", "La historia productiva del lote de 5 a 25 años, cada 16 días, con descarga en CSV y PDF", "MODIS (NASA), 250 m", "/agricultura-precision"],
        ["Cobertura reciente", "Qué hay en el lote en los últimos 90 días contra el año anterior", "Dynamic World (Google y WRI)", "/observatorio"],
        ["Cambios año a año", "Cuánto cambió el lote de un año al otro desde 2017", "Satellite Embedding (Google DeepMind)", "/observatorio"],
        ["Historia desde 1985", "Uso del suelo año por año: monte, pastizal, cultivo, agua", "MapBiomas (Landsat, 30 m)", "/observatorio"],
        ["Historia en imágenes", "Una foto por año del entorno del lote", "Google Earth Timelapse", "/observatorio"],
        ["Agua por radar", "Superficie cubierta de agua en dos fechas, aun con nubes", "Sentinel-1", "/radar"],
      ] },
      { titulo: "Herramientas regionales", cols: ["Herramienta", "Qué hace"], filas: [
        ["Panel Satelital", "Contaminación del aire (Sentinel-5P), nieve en la cordillera (MODIS), desmontes y tormentas, con sus rangos de lectura", "", "/satelital"],
        ["Lente de Relieve", "Una lupa que se arrastra sobre el mapa y muestra el relieve: sombreado, pendiente, orientación y verdor. Traza perfiles y mide altura y pendiente", "", "/lente"],
        ["Radar de inundaciones", "Compara dos pasadas de radar para estimar cómo cambió la superficie con agua. Experimental", "", "/radar"],
        ["Mapa del campo sin señal", "Guarda en el teléfono el mapa del campo con sus zonas bajas para la recorrida sin conexión", "", "/campo"],
        ["Focos de calor", "Focos de cuatro satélites de la NASA en el sur de Sudamérica, con provincia y qué se está quemando", "", "/focos"],
      ] },
    ],
  },
  {
    id: "ganaderia", tag: "GANADERÍA Y CULTIVOS", titulo: "Del satélite a la decisión de manejo.",
    lead: "Cuánto pasto hay, cuántos animales aguanta el lote, cuándo pulverizar, sembrar o cosechar. Los coeficientes son orientativos y siempre se muestran; ninguno reemplaza un corte de pasto, un análisis de suelo o al asesor.",
    tablas: [
      { titulo: "Ganadería y pasto", cols: ["Módulo", "Qué calcula", "Cómo"], filas: [
        ["Pasto y carga", "Cuánto pasto crece por día (kg de materia seca por hectárea) y cuántos equivalentes vaca sostiene el lote", "Modelo de Monteith con NDVI de Sentinel-2 y radiación solar"],
        ["Ganado", "Rodeo por lote, carga, agua de bebida según el calor, estrés térmico (THI) y valor de referencia del rodeo", "Reglas declaradas, pronóstico y precios de Cañuelas"],
        ["Pasto año por año", "Si la productividad del pasto del lote viene subiendo o bajando desde 2000", "Global Pasture Watch (30 m)"],
        ["Costos y margen", "Flete, distancia a destino, valores en dólares y margen ganadero", "OSRM, OpenStreetMap y DolarAPI"],
      ] },
      { titulo: "Cultivos", cols: ["Módulo", "Qué calcula", "Cómo"], filas: [
        ["Informe de cultivo", "Por localidad, cultivo y fecha de siembra: lluvia y evapotranspiración de los últimos 30 días y los próximos 7, temperaturas contra el umbral de helada del cultivo, grados día y alertas", "Open-Meteo (ERA5 y pronóstico)"],
        ["Labores", "Si conviene pulverizar (viento, Delta T, humedad, lluvia), sembrar (temperatura del suelo) o cosechar, el peligro de incendio (índice FWI), el lavado de agroquímicos a 48 horas y las heladas de los últimos 30 años", "Open-Meteo y ERA5"],
        ["Planificación", "Margen bruto con valores que carga el productor, calendario de siembra por zona, plagas y enfermedades de la zona y carbono del suelo", "SoilGrids y método IPCC 2019"],
        ["Clima avanzado", "Pronóstico de 16 días, comparador de dos localidades, viento en altura, potencial de tormentas severas, calidad del aire y lavado de nitratos", "Open-Meteo, ECMWF y CAMS"],
        ["Rinde por agua regional", "Maíz y soja en 19 localidades de Sudamérica: la campaña en curso contra las anteriores, con 30 escenarios de lo que falta", "AquaCrop (FAO)"],
        ["Heladas por satélite", "Temperatura mínima de la superficie la última noche en cada localidad", "GOES-19, todas las mañanas"],
      ] },
    ],
    ir: ["Ver el informe de cultivo", "/cultivos"],
  },
  {
    id: "europa", tag: "VENDER A EUROPA", titulo: "La evidencia para el reglamento europeo de deforestación.",
    lead: "Desde el 30 de diciembre de 2026, la Unión Europea sólo compra carne, soja y madera de tierras sin deforestación posterior al 31 de diciembre de 2020. Para micro y pequeñas empresas rige desde el 30 de junio de 2027.",
    puntos: [
      ["Verificación libre de deforestación", "Compara los árboles del lote año por año desde 2017, con corte en 2020: sin pérdida, pérdida menor para revisar o requiere verificación. Lo cruza con ESA WorldCover y MapBiomas."],
      ["Árboles fuera del bosque", "Separa el bosque 2020 del mapa de referencia de la UE, las cortinas y árboles sueltos, y los montes de media hectárea o más que conviene revisar antes de talar. Con mapa del lote."],
      ["¿Puedo vender a la UE?", "Autoevaluación por producto: lo que mide DOTS más lo que declara el productor (título, RENSPA, trazabilidad, Ley de Bosques, registros laborales). Da un resultado y los pasos que faltan."],
      ["Segunda opinión", "Consulta a Whisp, la herramienta de la FAO que cruza decenas de mapas públicos de bosques."],
      ["Informe y polígono", "Informe de verificación en PDF con huella digital del polígono, y el GeoJSON en el formato del sistema TRACES de la UE."],
    ],
    nota: "Es evidencia técnica de apoyo, no una certificación. La declaración de debida diligencia la presenta el exportador o importador.",
    ir: ["Qué pide el reglamento", "/libre-deforestacion"],
  },
  {
    id: "desmontes", tag: "DESMONTES", titulo: "Los desmontes grandes del Gran Chaco y el NEA, sin buscarlos.",
    lead: "DOTS resta el verdor de diez provincias entre dos períodos de la misma época del año y los parches que perdieron vegetación aparecen solos, desde 10 hectáreas, con fotos de antes y después.",
    puntos: [
      ["Últimos 120 días", "Contra los mismos días del año anterior. Se calcula el día 3 de cada mes."],
      ["Último verano", "Diciembre a marzo contra el verano anterior. Se calcula cada 20 de abril."],
      ["Pérdida anual", "La pérdida de bosque año por año desde 2001 (Hansen, Universidad de Maryland)."],
      ["Gravedad", "Suma puntos por Ley de Bosques, bosque en 2020, tamaño, pendiente y cercanía al agua. Alta con 4 o más; si más del 30 % figura quemado, se marca como posible incendio."],
    ],
    nota: "Es una señal para revisar, no una prueba de desmonte ilegal: una sequía extrema, una pastura degradada o una quema también bajan el verdor.",
    ir: ["Abrir el Panel Satelital", "/satelital#desmontes"],
  },
  {
    id: "crecidas", tag: "CRECIDAS", titulo: "Las crecidas de la Cuenca del Plata, antes de que lleguen.",
    lead: "DOTS sigue 34 localidades del Iguazú, el Paraná, el Paraguay y el Uruguay. Junta lo que llueve en las cabeceras, lo que sueltan las represas y lo que miden las escalas.",
    tablas: [{ cols: C3, filas: [
      ["Nivel de cada localidad", "Altura del río y su estado: normal, atención, alerta o evacuación", "INA y escalas de Prefectura"],
      ["Lluvia en las cabeceras", "Lluvia de los próximos 15 días en 21 subcuencas, con la probabilidad de superar 50 y 100 mm", "Conjuntos ECMWF (51 corridas) y GFS (31)"],
      ["Represas de Brasil", "Caudal que sueltan Itaipú, Salto Caxias, Porto Primavera, Itá y Foz do Chapecó", "ONS (Brasil)"],
      ["Caudal de los grandes ríos", "Caudal de hoy y pronóstico a 30 días contra lo normal para la fecha", "GloFAS (Copernicus)"],
      ["Agua de crecida detectada", "Mapa del agua que dejó cada pasada de radar, separada de ríos y lagunas", "Copernicus Global Flood Monitoring"],
      ["Temporales", "Caídas de presión, frentes fríos, ráfagas, calor extremo y sudestada en el Río de la Plata", "Open-Meteo"],
      ["Eventos extremos", "Ciclones activos en el Atlántico Sur y alertas internacionales en la región", "NOAA IBTrACS y GDACS"],
    ] }],
    nota: "Cada dos horas DOTS revisa el nivel de cada localidad y, si cambia de estado, avisa en la web, por Telegram, por correo y por RSS, con texto formal. Los avisos son orientativos: las alertas oficiales son del INA, Prefectura, el SMN y Defensa Civil.",
    ir: ["Ver las alertas", "/alertas"],
  },
  {
    id: "poblacion", tag: "POBLACIÓN Y SALUD", titulo: "Cuánta gente queda expuesta.",
    lead: "El riesgo no es sólo el agua o el fuego: es cuánta gente queda expuesta. Un punto de partida medible para Defensa Civil y los municipios.",
    tablas: [{ cols: ["Herramienta", "Qué hace", "Fuente"], filas: [
      ["Población en una zona", "Dibujás una zona de estudio y otra de amenaza, y DOTS calcula cuánta gente vive en la intersección", "WorldPop"],
      ["Gente en la zona baja", "En las 34 localidades ribereñas, cuántas personas viven a 1, 2, 3, 5 y 10 metros sobre el río, con menores de 5 y mayores de 65, en los niveles de alerta y evacuación", "WorldPop 2020 y MERIT Hydro"],
      ["Mapa de la zona baja", "El terreno bajo de cada localidad y dónde vive la gente dentro de él", "Earth Engine"],
      ["Barrios populares", "Los barrios del RENABAP en un mapa, con familias, superficie y servicios; filtros y descarga en CSV", "RENABAP"],
      ["Barrios detectados por radar", "Un modelo que reconoce barrios populares por la forma de sus construcciones, incluso los que no figuran en el registro", "Sentinel-1, Sentinel-2 y WorldCover"],
      ["Dengue", "Qué tan favorable está el clima para el mosquito en 80 localidades. Mide condiciones, no casos", "Curva térmica de Mordecai (2017) y lluvia"],
      ["Olas de calor", "Si la temperatura supera el umbral de calor propio de cada localidad", "ERA5 2001-2020 y pronóstico"],
    ] }],
    nota: "Las cifras de población son estimaciones de un modelo, no un censo. La zona baja no es una mancha de inundación modelada: no considera defensas ni terraplenes.",
    ir: ["Abrir Población y riesgo", "/poblacion"],
  },
  {
    id: "nino", tag: "EL NIÑO", titulo: "Del Pacífico al lote.",
    lead: "El Niño define buena parte de la lluvia del Litoral y de las crecidas de la Cuenca del Plata. DOTS lo sigue con las mismas fuentes que usan NOAA y la Universidad de Columbia.",
    tablas: [{ cols: ["Herramienta", "Qué muestra", "Fuente"], filas: [
      ["El Niño día por día", "La temperatura del mar en la región Niño 3.4 todos los días desde 1981, el puesto de este año y cuántos días seguidos lleva como el más caliente", "NOAA OISST 2.1", "/nino-diario"],
      ["La cadena de El Niño", "Alisios, calor bajo el mar, superficie y atmósfera: si la cadena está completa", "NOAA CPC, PSL y PMEL", "/el-nino"],
      ["Pronóstico", "Probabilidades oficiales, el índice MEI, los gráficos de Columbia y la tendencia en las localidades ribereñas", "NOAA, CCSR/IRI y ECMWF SEAS5", "/el-nino"],
      ["El impacto ahora", "En 80 localidades: lluvia de 90 días contra lo normal, lo que trajeron los El Niño fuertes y el pronóstico de 16 días", "ERA5 y NOAA", "/el-nino"],
      ["Qué pasó en tu zona", "La lluvia de 35 temporadas en cada localidad, separada por fase de El Niño", "ERA5", "/el-nino"],
      ["El Niño visto por satélite", "Clorofila del Pacífico, humedad del suelo y lluvia satelital, mes a mes contra lo normal", "MODIS, SMAP y GPM (NASA)", "/el-nino"],
      ["Teleconexiones", "SOI, AAO, Atlántico tropical, PDO, radiación saliente y presión Tahití-Darwin", "NOAA PSL", "/el-nino"],
      ["El Niño y crecidas", "Amenaza de crecida por período de retorno, población expuesta e historia de inundaciones", "JRC, WorldPop y Global Flood Database", "/nino-crecidas"],
      ["Simulador ambiental", "Escenarios de El Niño y su efecto en la región", "ENSO y NASA POWER", "/simulador-ambiental"],
    ] }],
    nota: "Un newsletter diario de El Niño y crecidas llega por correo a quienes se suscriben.",
  },
  {
    id: "informes", tag: "INFORMES Y DESCARGAS", titulo: "Todo lo que se calcula, se puede llevar.",
    lead: "Cada informe dice de dónde sale cada número, de qué fecha es y qué límites tiene. La Mesa de Informes los reúne con vista previa, historial y enlace para compartir.",
    tablas: [{ cols: ["Informe en PDF", "Qué contiene"], filas: [
      ["Informe de un campo o lote", "Todo lo del tablero: clima, agua, suelo, vegetación, riesgos y alertas"],
      ["Verificación libre de deforestación", "La evidencia para vender a Europa, con el polígono y su huella digital", "", "/informes"],
      ["Alerta de crecida por localidad", "Nivel del río, cuencas que aportan y variables disponibles"],
      ["Cuenca del Plata", "El Niño, lluvia en las cabeceras, imágenes, ríos, represas y tiempos de traslado del agua"],
      ["Población en zona baja", "Personas por franja de altura, escenarios de alerta y evacuación, y el mapa de la zona baja"],
      ["Barrios populares", "Por localidad, por zona dibujada o para toda la Cuenca del Plata", "", "/informes"],
      ["El Niño en una localidad", "Estado del Pacífico y lo que históricamente trajo El Niño a ese lugar"],
      ["Población expuesta en una zona", "La intersección entre la zona de estudio y la amenaza, con su método"],
      ["Informe de relieve", "El corte del terreno trazado con la Lente de Relieve"],
    ] }],
    nota: "Además: lotes en KML y GeoJSON, datos en CSV y JSON, y gráficos como imagen listos para una nota o un informe.",
    ir: ["Abrir la Mesa de Informes", "/informes"],
  },
];

const INDICE: Record<string, string> = {
  lote: "Mi campo", satelites: "Satélites y vegetación", ganaderia: "Ganadería y cultivos", europa: "Vender a Europa",
  desmontes: "Desmontes", crecidas: "Crecidas", poblacion: "Población y salud", nino: "El Niño", informes: "Informes y descargas",
};

const FRECUENCIAS: [string, string][] = [
  ["Cada 30 minutos", "Rayos detectados por el satélite GOES-19"],
  ["Cada 2 horas", "Avisos de crecidas y resumen de El Niño y crecidas"],
  ["Todos los días", "El Niño día por día, pronósticos y avisos de El Niño, heladas de la última noche, normales de la Cuenca del Plata y un chequeo del sitio en vivo"],
  ["Dos veces por semana", "Boyas del Pacífico ecuatorial (TAO)"],
  ["Cada lunes", "Procesamiento semanal de los lotes guardados"],
  ["Una vez por mes", "Desmontes recientes, El Niño en Sudamérica, El Niño por satélite, atmósfera de El Niño, historia de focos y barrios del RENABAP"],
  ["Cada tres meses", "Barrios populares detectados por radar"],
  ["Una vez por año", "Desmontes del último verano y umbrales de ola de calor"],
];

function TablaFunciones({ t }: { t: Tabla }) {
  const cols = t.cols.slice(0, 3).filter(c => c);              // el enlace va en el nombre, no en una columna aparte
  return <>
    {t.titulo && <h3 style={{ marginTop: 28 }}>{t.titulo}</h3>}
    <div className="guide-table-wrap"><table className="guide-table">
      <thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{t.filas.map(f => <tr key={f[0]}>
        <td>{(f[3] || ENLACES[f[0]]) ? <a href={f[3] || ENLACES[f[0]]}>{f[0]}</a> : f[0]}</td>
        <td>{f[1]}</td>
        {cols.length > 2 ? <td>{f[2]}</td> : null}
      </tr>)}</tbody>
    </table></div>
  </>;
}

export function FuncionesContent() {
  return <>
    <nav className="module-index" aria-label="Secciones">
      {SECCIONES.map(s => <a key={s.id} href={"#" + s.id}>{INDICE[s.id]}</a>)}
      <a href="#fuentes">Fuentes y límites</a>
    </nav>
    {SECCIONES.map(s => <section key={s.id} id={s.id}>
      <span className="section-tag">{s.tag}</span>
      <h2>{s.titulo}</h2>
      <p>{s.lead}</p>
      {s.tablas?.map((t, i) => <TablaFunciones key={i} t={t} />)}
      {s.puntos && <div className="guide-grid">{s.puntos.map(([t, d]) => <article key={t}><h3>{ENLACES[t] ? <a href={ENLACES[t]}>{t}</a> : t}</h3><p>{d}</p></article>)}</div>}
      {s.nota && <p className="guide-note" style={{ marginTop: 18 }}>{s.nota}</p>}
      {s.ir && <p style={{ marginTop: 14 }}><a className="module-action-link" href={s.ir[1]}>{s.ir[0]} →</a></p>}
    </section>)}
    <section id="fuentes">
      <span className="section-tag">FUENTES, ACTUALIZACIÓN Y LÍMITES</span>
      <h2>Sólo fuentes abiertas, y siempre a la vista.</h2>
      <p>Agencias espaciales (NASA, ESA, JAXA, NOAA), servicios meteorológicos, organismos oficiales argentinos (INA, SMN, RENABAP, Prefectura) y proyectos científicos con licencia abierta. Cada número aclara si se observó, se modeló o se calculó en DOTS, y cada módulo muestra sus rangos de lectura.</p>
      <h3 style={{ marginTop: 28 }}>Cuándo se actualiza cada cosa</h3>
      <div className="guide-table-wrap"><table className="guide-table">
        <thead><tr><th>Frecuencia</th><th>Qué se actualiza</th></tr></thead>
        <tbody>{FRECUENCIAS.map(([f, q]) => <tr key={f}><td>{f}</td><td>{q}</td></tr>)}</tbody>
      </table></div>
      <p style={{ marginTop: 18 }}>DOTS no reemplaza la recorrida, el análisis de suelo ni al especialista, y sus avisos no reemplazan a los organismos oficiales. Un satélite de 10 m no ve un árbol aislado ni una zanja chica, las imágenes ópticas no ven a través de las nubes y los modelos de 25 km pueden poner un lote chico en una sola celda. Cuando una fuente no responde, el dato aparece como «sin dato» y nunca se completa con valores inventados.</p>
      <p><a className="module-action-link" href="/guia">Cómo se usa DOTS →</a> <a className="module-action-link" href="/modulos" style={{ marginLeft: 16 }}>El método de cada módulo →</a></p>
    </section>
  </>;
}
