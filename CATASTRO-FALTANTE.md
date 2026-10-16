# Catastro faltante — estado, contactos y pedido de acceso

El Observatorio toma el límite del campo tocando la **parcela catastral** en el mapa (`catastro.py`, botón «Parcela del catastro»). Se apoya en **servicios WFS abiertos** de las IDE/catastros provinciales. Donde no hay un WFS público, la parcela no se puede leer y el botón avisa qué falta.

Este documento reúne: qué funciona, qué no, **los contactos** de cada infraestructura de datos (IDE) y una **nota modelo** para pedir el acceso. El registro también vive en el código (`catastro.py`, lista `PENDING`).

## 1. Dónde funciona hoy

| Jurisdicción | Organismo | Servicio |
|---|---|---|
| Buenos Aires | ARBA / IDEBA | WFS `idera:Parcela` (cubre todos los partidos) |
| Córdoba | IDECOR | WFS `idecor:parcelas` |
| Salta | IDESA | WFS `geonode:fc_parcelas_v20` (probar con un punto bien adentro de la parcela) |
| Neuquén | Catastro provincial | WFS `Catastro:Parcelas` |
| Gualeguaychú (Entre Ríos) | Catastro municipal | WFS `gis:parcelario` (urbano; el servidor municipal a veces tarda) |
| Paraguay | Servicio Nacional de Catastro | WFS `snc:parcelas_activas` |
| Brasil | SICAR / CAR | WFS `sicar:sicar_imoveis_<estado>` (registro ambiental declarado, no catastro legal) |

## 2. Dónde no está disponible (y por qué)

| Jurisdicción | Organismo | Estado | Qué falta |
|---|---|---|---|
| Santa Fe | IDESF | Parcelas sólo como imagen (WMS) | Publicación vectorial (WFS/GeoJSON) |
| Entre Ríos | IDEER · Catastro (ATER) | Sin capa de parcelas abierta | WFS de parcelas rurales |
| Corrientes | IDECorr | Sin capa de parcelas abierta | WFS de parcelas rurales |
| Misiones | IDE Misiones · DGC | Sin servicio abierto de parcelas | WFS de parcelas |
| Formosa | IDEF | Sin servicio abierto de parcelas | WFS de parcelas |
| Santiago del Estero | IDE Santiago · DGC | Sin capa de parcelas abierta | WFS de parcelas rurales |
| Chaco | IDE Chaco | La capa existe, el servidor no responde | Estabilidad del servicio |
| La Pampa | IDELP · Catastro | La capa existe, el servidor no responde | Estabilidad del servicio |
| Chubut | SIT · Catastro | El servidor rechaza las conexiones | Acceso/estabilidad del servicio |
| Río Negro | IDE Río Negro · Catastro | El servidor devuelve error | Estabilidad del servicio |
| Tucumán | IDET · DGC | El servidor devuelve error | Estabilidad del servicio |
| Tierra del Fuego | IDETDF · Catastro (AREF) | El servidor devuelve error | Estabilidad del servicio |
| Uruguay | IDEuy · Dirección Nacional de Catastro | Sin servicio abierto de padrones | WFS de padrones (hoy sólo metadatos) |

Nota: en los campos rurales el catastro que manda es el **provincial/departamental**, no el municipal; los municipios suelen publicar sólo la planta urbana (por eso en Buenos Aires ARBA ya cubre todo y no hace falta sumar municipios).

## 3. Contactos de las IDE

| Jurisdicción | IDE / Organismo | Correo | Dirección / teléfono | Portal |
|---|---|---|---|---|
| Nacional | IDERA (IGN) | contacto@idera.gob.ar | Cabildo 381, CABA | https://www.idera.gob.ar/ |
| Buenos Aires | ARBA / IDEBA | carto@arba.gov.ar | — | https://ideba.gba.gob.ar/ |
| Córdoba | IDECOR | idecor@cba.gov.ar | — | https://www.idecor.gob.ar/ |
| Salta | IDESA | (formulario del geoportal) | — | https://geoportal.salta.gob.ar/ |
| Neuquén | Catastro provincial | (formulario del sitio) | — | https://catastro.neuquen.gov.ar/ |
| Santa Fe | IDESF | idesf@santafe.gov.ar | San Martín 2466, 6º piso, Santa Fe · (0342) 4508700 int. 5147/5149 | https://www.santafe.gob.ar/idesf/ |
| Entre Ríos | IDEER · ATER | entrerios@ign.gob.ar | Arturo Illia 265, Paraná · (0343) 4450700 int. 2831 | https://geoservicios.entrerios.gov.ar/ |
| Corrientes | IDECorr (SuSTI) | idecorrientes@gmail.com | — | https://ide.corrientes.gob.ar/ |
| Misiones | IDE Misiones · DGC | (formulario del catastro) | — | https://catastro.misiones.gov.ar/ |
| Formosa | IDEF | idef@formosa.gov.ar | Ayacucho 810, 2º piso · (0370) 4429244 | https://idef.formosa.gob.ar/ |
| Santiago del Estero | IDE Santiago · DGC | direcciongeneraldecatastro@dgcsantiago.gob.ar | — | https://www.idesantiago.gob.ar/ |
| Chaco | IDE Chaco | chaco@ign.gob.ar | Av. Belgrano 151, 1º piso, Resistencia | http://idechaco.gob.ar/ |
| La Pampa | IDELP · Catastro | catastro@lapampa.gob.ar | Centro Cívico, planta baja, Santa Rosa · (02954) 452600 int. 1242 | https://idelp.lapampa.gob.ar/ |
| Chubut | SIT · Catastro | chubut@ign.gob.ar | Alejandro Maiz 169, Rawson · (0280) 4481141 | https://catastro.chubut.gov.ar/ |
| Río Negro | IDE Río Negro · Catastro | info.catastro@agencia.rionegro.gov.ar | Moreno 175, Viedma · (02920) 425923 | https://ide.rionegro.gov.ar/ |
| Tucumán | IDET · DGC | sistemas@dgc-tuc.gov.ar | Av. Benjamín Aráoz 96, S. M. de Tucumán · (0381) 4212832 | https://www.tucuman.gob.ar/organismos/direccion-general-de-catastro |
| Tierra del Fuego | IDETDF · Catastro (AREF) | catastrotdf@aref.gob.ar | Antártida Argentina 54, Ushuaia | https://ide.tierradelfuego.gob.ar/ |
| Uruguay | IDEuy · DNC | (formulario en gub.uy) | Liniers 1280, piso 4, Montevideo · (+598) 150 int. 1771/1772 | https://www.gub.uy/infraestructura-datos-espaciales/ |

Los correos `@ign.gob.ar` corresponden a las **Oficinas Provinciales del IGN**, no a la IDE provincial: sirven como vía de contacto cuando la IDE no publica un correo propio.

## 4. Nota modelo para pedir el acceso

> **Asunto:** Solicitud de acceso al servicio de parcelas catastrales (WFS/GeoJSON) — proyecto abierto DOTS
>
> Estimados:
>
> Me dirijo a ustedes en el marco de **DOTS**, un observatorio agroambiental abierto y sin fines comerciales para el sector agropecuario. Documentación y código: https://github.com/Alvarorfontana/observatorio-agro
>
> Para que un productor pueda delimitar su establecimiento, DOTS ofrece la opción de **tocar la parcela catastral** en el mapa. Esto requiere que las parcelas se publiquen como **servicio vectorial abierto (WFS OGC, con salida GeoJSON)**, no sólo como imagen (WMS).
>
> Solicitamos:
> 1. La **URL del servicio WFS** y el **nombre de la capa** de parcelas (idealmente rurales).
> 2. La **geometría** (límite de la parcela) y, si es posible, la **nomenclatura catastral** y la **superficie**.
> 3. Las **condiciones de uso y licencia** (atribución requerida, límites de consulta).
>
> Qué usamos: **sólo el polígono, la nomenclatura y la superficie** para prellenar el límite del campo. No redistribuimos datos personales ni publicamos los contornos de establecimientos de terceros; cada productor ve únicamente su propio campo, y los límites se procesan en el navegador del usuario.
>
> Las fuentes que ya usamos y citamos: ARBA (Buenos Aires), IDECOR (Córdoba), IDESA (Salta), Catastro de Neuquén, Servicio Nacional de Catastro (Paraguay) y SICAR/CAR (Brasil). Sumar a [PROVINCIA] ampliaría la cobertura del catastro abierto.
>
> Quedo a disposición por cualquier aclaración técnica o reunión.
>
> Saludos cordiales,
> [Nombre] — DOTS · [correo de contacto]

Sugerencia de firma: usar el correo configurado en el sitio (`CONTACT_TO`) y adjuntar el enlace a un informe de ejemplo.

## 5. Cómo se agrega una provincia al código

En `catastro.py`, dentro de `PROVIDERS`, se agrega una entrada con el servicio WFS y el mapeo de campos; `parcel_at()` la consulta automáticamente cuando el punto cae en su `bbox`. Cuando un WFS no esté disponible, la entrada queda en la lista `PENDING` (documentada, sin consultarse).

```python
{'id': 'ejemplo', 'name': 'Catastro · Provincia de X', 'url': 'https://.../wfs',
 'layer': 'x:parcelas', 'bbox': (min_lon, min_lat, max_lon, max_lat),
 'fields': lambda p: (p.get('nomenclatura'), p.get('partida'), p.get('tipo'), (p.get('area') or 0) / 1e4)},
```

Regla de la casa: **una fuente caída se informa como faltante, nunca se inventa el dato**.

## 6. Relación con los informes

DOTS **ya genera informes**; el catastro alimenta el límite sobre el que se calculan:

| Informe | Ruta / botón | Qué aporta el catastro |
|---|---|---|
| Informe de campo (lomas, bajos y suelos + QR para el celular) | Observatorio › «Lomas, bajos y suelos» | Toma el polígono legal como límite del campo |
| Informe territorial | `/api/fuentes/analizar` (PDF Agentic) | Incluye la parcela en el análisis |
| Libre de deforestación (EUDR) | PDF + GeoJSON + second opinion Whisp | Geolocaliza el lote con su delimitación |
| El Niño, Cuenca, Localidad, Población | PDFs por endpoint | Usan el mismo perímetro elegido |

Al sumar una provincia, la parcela catastral prellena el límite y el informe sale con la **nomenclatura catastral** y la superficie legal. El informe de campo ya trae un **código QR** que abre el mapa en el celular —también sin señal— y un **KMZ** para recorrerlo en Google Earth.
