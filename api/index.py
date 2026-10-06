import sys
import os

# Configurar rutas para que Python encuentre los módulos
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from flask import Flask, render_template, request, send_file, jsonify
from satellite_data import SatelliteDataEngine
from report_generator import PremiumReportGenerator, generate_charts

app = Flask(__name__, template_folder=os.path.join(base_dir, 'templates'))
engine = SatelliteDataEngine()

# ============================================
# RUTA 1: Página principal
# ============================================
@app.route('/', methods=['GET'])
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Error cargando la página: {str(e)}", 500

# ============================================
# RUTA 2: Variables en tiempo real (para el panel lateral)
# ============================================
@app.route('/api/variables', methods=['GET'])
def variables():
    try:
        lat = request.args.get('lat', type=float, default=-34.6037)
        lon = request.args.get('lon', type=float, default=-58.3816)
        
        datos = engine.get_all_data(lat, lon)
        
        return jsonify({
            'temp_actual': datos.get('temp_actual', 0),
            'hum_actual': datos.get('hum_actual', 0),
            'viento_actual': datos.get('viento_actual', 0),
            'presion_actual': datos.get('presion_actual', 0),
            'thi': datos.get('thi', 0),
            'estado_thi': datos.get('estado_thi', 'N/A'),
            'enso_estado': datos.get('enso', {}).get('estado', 'N/A'),
            'enso_oni': datos.get('enso', {}).get('oni', 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# RUTA 3: Generar informe PDF
# ============================================
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
        pdf.ln(5)

        pdf.section_title("2. PRONOSTICO 16 DIAS")
        pdf.add_chart("/tmp/chart_rain_rad.png")

        pdf_path = f"/tmp/informe_{nombre.replace(' ','_')}.pdf"
        pdf.output(pdf_path)
        
        return send_file(pdf_path, as_attachment=True, download_name=f"informe_{nombre}.pdf")
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Handler para Vercel
app = app
