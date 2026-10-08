"""Punto de entrada FastAPI para DOTS Campo v1.5"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.fuentes import agentic, conexiones, escenas

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

# Rutas
app.include_router(agentic.router, prefix="/api/fuentes/agentic", tags=["Agentic"])
app.include_router(conexiones.router, prefix="/api/fuentes/conexiones", tags=["Conexiones"])
app.include_router(escenas.router, prefix="/api/fuentes/escenas", tags=["Escenas"])

@app.get("/")
async def root():
    return {
        "name": "DOTS Campo API",
        "version": "1.5",
        "status": "operativa"
    }
