import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';
import 'leaflet-draw';

export default function Map({ onLoteSeleccionado, onEscenasCargadas }) {
    const mapRef = useRef(null);
    const mapInstanceRef = useRef(null);
    const drawnItemsRef = useRef(null);

    useEffect(() => {
        if (mapInstanceRef.current) return;

        const map = L.map('map').setView([-34.6, -58.4], 6);
        mapInstanceRef.current = map;

        // Capa satelital real (Esri World Imagery)
        const satelital = L.tileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            { attribution: 'Tiles © Esri', maxZoom: 19 }
        ).addTo(map);

        // NASA GIBS NDVI
        const ndviGIBS = L.tileLayer.wms(
            'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi',
            {
                layers: 'MODIS_Terra_L3_NDVI_Equal_Daily',
                format: 'image/png', transparent: true, version: '1.3.0'
            }
        );

        L.control.layers({
            '🛰️ Satelital': satelital,
            '🌿 NDVI (NASA GIBS)': ndviGIBS
        }).addTo(map);

        // Herramientas de dibujo
        const drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);
        drawnItemsRef.current = drawnItems;

        const drawControl = new L.Control.Draw({
            draw: {
                polygon: { allowIntersection: false, shapeOptions: { color: '#00d4aa', weight: 3 } },
                rectangle: { shapeOptions: { color: '#3498db', weight: 3 } },
                marker: true, circle: false, circlemarker: false, polyline: false
            },
            edit: { featureGroup: drawnItems, remove: true }
        });
        map.addControl(drawControl);

        let loteCounter = 0;
        const colores = ['#00d4aa', '#3498db', '#e74c3c', '#f39c12', '#9b59b6'];

        map.on(L.Draw.Event.CREATED, function(event) {
            loteCounter++;
            const layer = event.layer;
            const color = colores[(loteCounter - 1) % colores.length];
            layer.setStyle({ color, fillColor: color, fillOpacity: 0.25, weight: 3 });

            const geojson = layer.toGeoJSON();
            const coords = geojson.geometry.coordinates[0];
            const areaM2 = L.GeometryUtil.geodesicArea(coords);
            const areaHa = (areaM2 / 10000).toFixed(2);
            const centro = layer.getBounds().getCenter();

            layer.bindTooltip(`Lote ${loteCounter}<br>${areaHa} ha`);
            drawnItems.addLayer(layer);

            const lote = {
                id: `lote_${loteCounter}`,
                nombre: `Lote ${loteCounter}`,
                area_ha: parseFloat(areaHa),
                centroide: { lat: centro.lat, lon: centro.lng },
                vertices: coords.map(c => [c[1], c[0]]),
                polygon: coords.map(c => [c[1], c[0]]),
                color, layer
            };

            onLoteSeleccionado(lote);

            // Cargar escenas Sentinel-2 del área
            fetch(`/api/fuentes/escenas?lat=${centro.lat}&lon=${centro.lng}&limit=5`)
                .then(r => r.json())
                .then(data => {
                    if (data.features) {
                        onEscenasCargadas(data.features);
                        dibujarFootprints(map, data.features);
                    }
                })
                .catch(err => console.error('Error cargando escenas:', err));
        });

        function dibujarFootprints(map, features) {
            if (window.escenasLayer) map.removeLayer(window.escenasLayer);
            window.escenasLayer = L.featureGroup().addTo(map);

            features.forEach(scene => {
                const coords = scene.geometry.coordinates[0].map(c => [c[1], c[0]]);
                const nubes = scene.properties['eo:cloud_cover'] ?? 100;
                const color = nubes < 20 ? '#00d4aa' : nubes < 50 ? '#f39c12' : '#e74c3c';

                L.polygon(coords, {
                    color, weight: 2, fillOpacity: 0.1, dashArray: '5, 5'
                }).bindTooltip(
                    `Escena ${scene.properties.datetime.split('T')[0]}<br>Nubes: ${nubes}%`
                ).addTo(window.escenasLayer);
            });
        }
    }, []);

    return <div id="map" ref={mapRef} />;
}
