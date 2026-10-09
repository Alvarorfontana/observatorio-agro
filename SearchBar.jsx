import React, { useState } from 'react';

export default function SearchBar() {
    const [query, setQuery] = useState('');

    const buscar = async () => {
        if (!query.trim()) return;
        try {
            const r = await fetch(
                `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`
            );
            const data = await r.json();
            if (data[0]) {
                // Emitir evento global para que el mapa lo escuche
                window.dispatchEvent(new CustomEvent('map:flyTo', {
                    detail: { lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon), zoom: 13 }
                }));
            }
        } catch (err) {
            console.error('Error buscando:', err);
        }
    };

    return (
        <div className="search-bar">
            <input
                type="text"
                placeholder="Buscar localidad..."
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyPress={e => e.key === 'Enter' && buscar()}
            />
            <button onClick={buscar}>🔍</button>
        </div>
    );
}
