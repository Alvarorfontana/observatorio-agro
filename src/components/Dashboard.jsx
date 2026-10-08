import React from 'react';
import { analizarLote, descargarPDF } from '../services/api';

export default function Dashboard({ loteSeleccionado, onResultado, loading, setLoading }) {
    const intents = [
        { key: 'integral', label: '📊 Integral' },
        { key: 'pasturas', label: '🌿 Pasturas' },
        { key: 'agua', label: '💧 Agua' },
        { key: 'ganado', label: '🐄 Ganado' },
        { key: 'sequia', label: '🔥 Sequía' },
        { key: 'suelo', label: '🌱 Suelo' },
        { key: 'clima', label: '🌤️ Clima' },
    ];

    const handleClick = async (intent) => {
        if (!loteSeleccionado) {
            alert('Primero delimitá un lote en el mapa');
            return;
        }
        setLoading(true);
        try {
            const result = await analizarLote({
                lat: loteSeleccionado.centroide.lat,
                lon: loteSeleccionado.centroide.lon,
                polygon: loteSeleccionado.polygon,
                prompt: intent,
                nombre: loteSeleccionado.nombre
            });
            onResultado(result);
        } catch (err) {
            alert('Error: ' + err.message);
        } finally {
            setLoading(false);
        }
    };

    const handlePDF = async () => {
        if (!loteSeleccionado) {
            alert('Primero delimitá un lote en el mapa');
            return;
        }
        await descargarPDF({
            lat: loteSeleccionado.centroide.lat,
            lon: loteSeleccionado.centroide.lon,
            polygon: loteSeleccionado.polygon,
            prompt: 'integral',
            nombre: loteSeleccionado.nombre
        });
    };

    return (
        <div className="dashboard">
            {intents.map(i => (
                <button
                    key={i.key}
                    className="btn-dashboard"
                    onClick={() => handleClick(i.key)}
                    disabled={loading}
                >
                    {loading ? '⏳' : i.label}
                </button>
            ))}
            <button className="btn-dashboard btn-pdf" onClick={handlePDF} disabled={loading}>
                {loading ? '⏳ Generando...' : '📄 Informe Territorial DOTS · PDF'}
            </button>
        </div>
    );
}
