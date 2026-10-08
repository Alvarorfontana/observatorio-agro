"""Entrypoint mínimo para Vercel - sin imports externos"""
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

@app.get("/")
async def root():
    return {
        "name": "DOTS Campo API",
        "version": "1.5",
        "status": "operativa",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/fuentes/agentic/status")
async def status():
    """Endpoint de status básico - sin dependencias externas"""
    return {
        "status": "ok",
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "clima": {"status": "pendiente", "note": "requiere research_connectors.py"}
        }
    }

@app.get("/api/fuentes/conexiones")
async def conexiones():
    """Directorio de APIs - versión básica"""
    return {
        "status": "ok",
        "total_apis": 20,
        "note": "Versión básica. Conectores completos pendientes."
    }
