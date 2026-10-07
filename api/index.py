import sys
import os

# Configurar rutas para Vercel
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from flask import Flask, render_template, request, send_file, jsonify, send_from_directory
from satellite_data import SatelliteDataEngine
from report_generator import PremiumReportGenerator, generate_charts

app = Flask(__name__, template_folder=os.path.join(base_dir, 'templates'))
engine = SatelliteDataEngine()

# Research adapters; leave the existing UI and endpoints intact.
from research_routes import research_api
app.register_blueprint(research_api)

@app.route('/', methods=['GET'])
def index():
    return send_from_directory(os.path.join(base_dir,'dist'),'index.html')

@app.route('/api/variables', methods=['GET'])
def variables():
    """Devuelve TODAS las variables en tiempo real"""
    try:
        lat = request.args.get('lat', type=float, default=-34.6037)
        lon = request.args.get('lon', type=float, default=-58.3816)
        
        datos = engine.get_all_data(lat, lon)
        meteo = datos['meteo']
        current = meteo.get('current', {})
        daily = meteo.get('daily', {})
        
        # Construir pronóstico limpio
        pronostico = []
        dates = daily.get('time', [])
        for i in range(min(16, len(dates))):
            pronostico.append({
                'fecha': dates[i][-5:],
                't_max': daily.get('temperature_2m_max', [0]*16)[i],
                't_min': daily.get('temperature_2m_min', [0]*16)[i],
                'lluvia': daily.get('precipitation_sum', [0]*16)[i],
                'viento_max': daily.get('wind_speed_10m_max', [0]*16)[i],
                'uv_max': daily.get('uv_index_max', [0]*16)[i],
                'et0': daily.get('et0_fao_evapotranspiration', [0]*16)[i]
            })
        
        return jsonify({
            'temp_actual': current.get('temperature_2m', 0),
            'sensacion_termica': current.get('apparent_temperature', 0),
            'humedad': current.get('relative_humidity_2m', 0),
            'precipitacion_actual': current.get('precipitation', 0),
            'cobertura_nubes': current.get('cloud_cover', 0),
            'presion_superficie': current.get('surface_pressure', 0),
            'viento_10m': current.get('wind_speed_10m', 0),
            'rafagas': current.get('wind_gusts_10m', 0),
            'viento_80m': current.get('wind_speed_80m', 0),
            'viento_180m': current.get('wind_speed_180m', 0),
            'humedad_suelo_0_7': current.get('soil_moisture_0_to_7cm_mean', 0),
            'temp_suelo_0_7': current.get('soil_temperature_0_to_7cm_mean', 0),
            'deficit_presion_vapor': current.get('vapor_pressure_deficit', 0),
            'evapotranspiracion': current.get('et0_fao_evapotranspiration', 0),
            'thi': datos['thi'],
            'estado_thi': datos['estado_thi'],
            'enso_estado': datos['enso']['estado'],
            'enso_oni': datos['enso']['oni'],
            'cantidad_focos': len(datos['focos']),
            'pronostico': pronostico
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analizar', methods=['POST'])
def analizar():
    """Genera el PDF Premium"""
    try:
        data = request.json
        lat = data.get('lat')
        lon = data.get('lon')
        nombre = data.get('nombre', 'Lote_Premium')

        datos = engine.get_all_data(lat, lon)
        daily = datos['meteo'].get('daily', {})
        
        os.makedirs('/tmp', exist_ok=True)
        generate_charts(daily, "/tmp/chart")

        pdf = PremiumReportGenerator(
            title="INFORME AGROCLIMATICO PREMIUM", 
            zone_name=nombre, 
            lat=lat, 
            lon=lon
        )
        pdf.add_page()
        
        pdf.section_title("1. RESUMEN EJECUTIVO")
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, f"THI: {datos['thi']} ({datos['estado_thi']}) | ENSO: {datos['enso']['estado']}")
        pdf.multi_cell(0, 5, f"Temp: {datos['temp_actual']}C | Humedad: {datos['hum_actual']}% | Focos: {len(datos['focos'])}")
        pdf.ln(5)

        pdf.section_title("2. PRONOSTICO 16 DIAS (Ensemble)")
        pdf.add_chart("/tmp/chart_rain_rad.png")

        pdf_path = f"/tmp/informe_{nombre.replace(' ','_')}.pdf"
        pdf.output(pdf_path)
        
        return send_file(pdf_path, as_attachment=True, download_name=f"informe_{nombre}.pdf")
    except Exception as e:
        return jsonify({'error': str(e)}), 500

app = app

@app.get('/assets/<path:filename>')
def assets(filename):return send_from_directory(os.path.join(base_dir,'dist','assets'),filename)
@app.get('/legacy')
def legacy():return render_template('index.html')
@app.get('/<name>.md')
def docs(name):return send_from_directory(os.path.join(base_dir,'public'),name+'.md')
