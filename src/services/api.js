const API_BASE = '/api/fuentes/agentic';

export async function analizarLote(payload) {
    const response = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const err = await response.text();
        throw new Error(`Error ${response.status}: ${err}`);
    }
    return response.json();
}

export async function descargarPDF(payload) {
    const response = await fetch(`${API_BASE}/pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Error generando PDF');
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${payload.nombre}_${new Date().toISOString().split('T')[0]}.pdf`;
    a.click();
    window.URL.revokeObjectURL(url);
}

export async function statusAPIs() {
    const response = await fetch(`${API_BASE}/status`);
    return response.json();
}
