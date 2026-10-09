import React from 'react';

export default function ScenesPanel({ escenas }) {
    if (!escenas || escenas.length === 0) return null;

    return (
        <div className="escenas-lista">
            {escenas.map((scene, i) => {
                const fecha = scene.properties.datetime.split('T')[0];
                const nubes = scene.properties['eo:cloud_cover'] ?? 'n/d';
                const id = scene.id;
                const linkOficial = `https://browser.dataspace.copernicus.eu/?product=${id}`;
                const claseNubes = nubes < 20 ? 'buena' : nubes < 50 ? 'media' : 'mala';

                return (
                    <div key={i} className="escena-card">
                        <div className="escena-info">
                            <strong>📅 {fecha}</strong>
                            <span className={`nubes ${claseNubes}`}>☁️ {nubes}%</span>
                            <a href={linkOficial} target="_blank" rel="noopener noreferrer">
                                Ver en Copernicus Data Space ↗
                            </a>
                            <p className="aviso-fuente">
                                Catálogo STAC · fuente: Copernicus Data Space
                            </p>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
