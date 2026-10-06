import sys
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from flask import Flask, render_template, request, send_file, jsonify
from satellite_data import SatelliteDataEngine
from report_generator import PremiumReportGenerator, generate_charts

app = Flask(__name__, template_folder=os.path.join(base_dir, 'templates'))
engine = SatelliteDataEngine()

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/api/variables', methods=['GET'])
def variables():
    """Devuelve TODAS las variables disponibles"""
    try:
        lat = request.args.get('lat', type=float, default=-34.6037)
        lon = request.args.get('lon', type=float, default=-58.3816)
        
        datos = engine.get_all_data(lat, lon)
        meteo = datos['meteo']
        current = meteo.get('current', {})
        daily = meteo.get('daily', {})
        
        # Construir pronóstico de 16 días
        pronostico = []
        dates = daily.get('time', [])
        for i in range(min(16, len(dates))):
            pronostico.append({
                'fecha': dates[i],
                't_max': daily.get('temperature_2m_max', [0]*16)[i],
                't_min': daily.get('temperature_2m_min', [0]*16)[i],
                't_media': daily.get('temperature_2m_mean', [0]*16)[i],
                'lluvia': daily.get('precipitation_sum', [0]*16)[i],
                'lluvia_horas': daily.get('precipitation_hours', [0]*16)[i],
                'prob_lluvia': daily.get('precipitation_probability_max', [0]*16)[i],
                'viento_max': daily.get('wind_speed_10m_max', [0]*16)[i],
                'rafagas': daily.get('wind_gusts_10m_max', [0]*16)[i],
                'direccion_viento': daily.get('wind_direction_10m_dominant', [0]*16)[i],
                'radiacion_onda_corta': daily.get('shortwave_radiation_sum', [0]*16)[i],
                'radiacion_directa': daily.get('direct_radiation_sum', [0]*16)[i],
                'radiacion_difusa': daily.get('diffuse_radiation_sum', [0]*16)[i],
                'radiacion_terrestre': daily.get('terrestrial_radiation_sum', [0]*16)[i],
                'horas_sol': daily.get('sunshine_duration', [0]*16)[i],
                'horas_luz': daily.get('daylight_duration', [0]*16)[i],
                'uv_max': daily.get('uv_index_max', [0]*16)[i],
                'et0': daily.get('et0_fao_evapotranspiration', [0]*16)[i],
                'humedad_suelo_0_7': daily.get('soil_moisture_0_to_7cm_mean', [0]*16)[i],
                'humedad_suelo_7_28': daily.get('soil_moisture_7_to_28cm_mean', [0]*16)[i],
                'humedad_suelo_28_100': daily.get('soil_moisture_28_to_100cm_mean', [0]*16)[i],
                'humedad_suelo_100_255': daily.get('soil_moisture_100_to_255cm_mean', [0]*16)[i]
            })
        
        return jsonify({
            # Condiciones actuales
            'temp_actual': current.get('temperature_2m'),
            'sensacion_termica': current.get('apparent_temperature'),
            'humedad': current.get('relative_humidity_2m'),
            'es_de_dia': current.get('is_day'),
            'precipitacion_actual': current.get('precipitation'),
            'lluvia_actual': current.get('rain'),
            'nevada_actual': current.get('snowfall'),
            'codigo_clima': current.get('weather_code'),
            'cobertura_nubes': current.get('cloud_cover'),
            'presion_msl': current.get('pressure_msl'),
            'presion_superficie': current.get('surface_pressure'),
            'viento_10m': current.get('wind_speed_10m'),
            'direccion_viento': current.get('wind_direction_10m'),
            'rafagas': current.get('wind_gusts_10m'),
            'viento_80m': current.get('wind_speed_80m'),
            'viento_120m': current.get('wind_speed_120m'),
            'viento_180m': current.get('wind_speed_180m'),
            'temp_80m': current.get('temperature_80m'),
            'temp_120m': current.get('temperature_120m'),
            'temp_180m': current.get('temperature_180m'),
            'humedad_suelo_0_7': current.get('soil_moisture_0_to_7cm_mean'),
            'humedad_suelo_7_28': current.get('soil_moisture_7_to_28cm_mean'),
            'humedad_suelo_28_100': current.get('soil_moisture_28_to_100cm_mean'),
            'humedad_suelo_100_255': current.get('soil_moisture_100_to_255cm_mean'),
            'temp_suelo_0_7': current.get('soil_temperature_0_to_7cm_mean'),
            'temp_suelo_7_28': current.get('soil_temperature_7_to_28cm_mean'),
            'temp_suelo_28_100': current.get('soil_temperature_28_to_100cm_mean'),
            'deficit_presion_vapor': current.get('vapor_pressure_deficit'),
            'evapotranspiracion': current.get('et0_fao_evapotranspiration'),
            
            # THI y ENSO
            'thi': datos['thi'],
            'estado_thi': datos['estado_thi'],
            'enso_estado': datos['enso']['estado'],
            'enso_oni': datos['enso']['oni'],
            
            # Focos de calor
            'focos': datos['focos'],
            'cantidad_focos': len(datos['focos']),
            
            # Pronóstico 16 días
            'pronostico': pronostico
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analizar', methods=['POST'])
def analizar():
    try:
        data = request.json
        lat = data.get('lat')
        lon = data.get('lon')
        nombre = data.get('nombre', 'Lote_Delimitado')

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
        pdf.multi_cell(0, 5, f"THI: {datos['thi']} ({datos['estado_thi']})")
        pdf.multi_cell(0, 5, f"ENSO: {datos['enso']['estado']} (ONI: {datos['enso']['oni']})")
        pdf.multi_cell(0, 5, f"Temp: {datos['temp_actual']}C | Humedad: {datos['hum_actual']}%")
        pdf.multi_cell(0, 5, f"Focos de calor: {len(datos['focos'])}")
        pdf.ln(5)

        pdf.section_title("2. PRONOSTICO 16 DIAS")
        pdf.add_chart("/tmp/chart_rain_rad.png")

        pdf.section_title("3. MATRIZ DE VARIABLES")
        headers = ["Fecha", "T.Max", "T.Min", "Lluvia", "Viento", "UV", "Rad.MJ", "ET0", "Hum.Suelo"]
        rows = []
        dates = daily.get('time', [])
        for i in range(min(16, len(dates))):
            rows.append([
                dates[i][-5:],
                f"{daily.get('temperature_2m_max', [0]*16)[i]:.1f}",
                f"{daily.get('temperature_2m_min', [0]*16)[i]:.1f}",
                f"{daily.get('precipitation_sum', [0]*16)[i]:.1f}",
                f"{daily.get('wind_speed_10m_max', [0]*16)[i]:.1f}",
                f"{daily.get('uv_index_max', [0]*16)[i]:.1f}",
                f"{daily.get('shortwave_radiation_sum', [0]*16)[i]:.1f}",
                f"{daily.get('et0_fao_evapotranspiration', [0]*16)[i]:.2f}",
                f"{daily.get('soil_moisture_0_to_7cm_mean', [0]*16)[i]:.3f}"
            ])
        pdf.add_data_table(headers, rows, [25, 20, 20, 20, 20, 15, 25, 20, 25])

        pdf_path = f"/tmp/informe_{nombre.replace(' ','_')}.pdf"
        pdf.output(pdf_path)
        
        return send_file(pdf_path, as_attachment=True, download_name=f"informe_{nombre}.pdf")
    except Exception as e:
        return jsonify({'error': str(e)}), 500

app = app
