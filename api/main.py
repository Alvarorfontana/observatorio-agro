"""Punto de entrada FastAPI para DOTS Campo v1.5 - versión robusta"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

app = FastAPI(
    title="DOTS Campo API",
    version="1.5",
    description="Observatorio Territorial Agroambiental"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Importar routers con try/except para que no crashee todo si uno falla
try:
    from api.fuentes import agentic
    app.include_router(agentic.router, prefix="/api/fuentes/agentic", tags=["Agentic"])
    print("✅ Router agentic cargado")
except Exception as e:
    print(f"⚠️ Router agentic no cargado: {e}")

try:
    from api.fuentes import escenas
    app.include_router(escenas.router, prefix="/api/fuentes/escenas", tags=["Escenas"])
    print("✅ Router escenas cargado")
except Exception as e:
    print(f"⚠️ Router escenas no cargado: {e}")

try:
    from api.fuentes import conexiones
    app.include_router(conexiones.router, prefix="/api/fuentes/conexiones", tags=["Conexiones"])
    print("✅ Router conexiones cargado")
except Exception as e:
    print(f"⚠️ Router conexiones no cargado: {e}")


@app.get("/")
async def root():
    return {
        "name": "DOTS Campo API",
        "version": "1.5",
        "status": "operativa",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/fuentes/agentic/status")
async def status_fallback():
    """Endpoint de status que funciona aunque fallen los routers"""
    try:
        import api.research_connectors as c
        lat, lon = -28.507, -59.043
        clima = c.open_meteo_forecast(lat, lon)
        return {
            "tested_at": datetime.now(timezone.utc).isoformat(),
            "sources": {
                "clima": {"status": clima["status"], "organism": clima.get("organism")}
            }
        }
    except Exception as e:
        return {"error": str(e), "status": "backend_failing"}
