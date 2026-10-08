# DOTS Campo v1.4 — APIs y accesos

- Nueva ruta pública `/conexiones` con directorio de APIs, explicación, acceso oficial y prueba del conector DOTS.
- Cada tarjeta muestra institución, cobertura, uso, variables, modalidad de acceso y estado de prueba.
- Botón `Gestión / documentación` abre la dirección oficial indicada para registro/credenciales.
- Botón `Probar conexión` llama al backend DOTS cuando existe conector implementado.
- NASA GIBS incorpora validación WMS GetCapabilities sin API key.
- NASA POWER 30 años, Copernicus STAC, SoilGrids, FIRMS y conectores protegidos quedan enlazados a sus rutas existentes.
- Las fuentes protegidas no simulan datos: verifican credenciales y permanecen pendientes hasta una consulta autenticada end-to-end.
- Se incorporan identificadores visuales del dominio oficial en cada tarjeta y explicación contextual en la página.
