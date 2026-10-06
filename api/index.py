import sys
import os

# Esto es CRÍTICO: le dice a Python que busque los módulos en la carpeta raíz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, send_file, jsonify
from satellite_data import SatelliteDataEngine
from report_generator import PremiumReportGenerator, generate_charts

# El template_folder apunta a la carpeta templates que está UN NIVEL ARRIBA de /api
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'))
engine = SatelliteDataEngine()

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/api/analizar', methods=['POST'])
def analizar():
    data = request.json
    lat = data.get('lat')
    lon = data.get('lon')
    nombre = data.get('nombre', 'Lote_Delimitado')

    datos = engine.get_all_data(lat, lon)
    daily = datos['meteo'].get('daily', {})
    
    # Generar gráficos en /tmp (único lugar writable en Vercel)
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
    pdf.multi_cell(0, 5, f"THI: {datos['thi']} ({datos['estado_thi']}) | ENSO: {datos['enso']['estado']} (ONI: {datos['enso']['oni']})")
    pdf.multi_cell(0, 5, f"Temp: {datos['temp_actual']}C | Humedad: {datos['hum_actual']}% | Viento: {datos['viento_actual']} km/h")
    pdf.ln(5)

    pdf.section_title("2. PRONOSTICO 16 DIAS")
    pdf.add_chart("/tmp/chart_rain_rad.png")

    pdf.section_title("3. MATRIZ DE VARIABLES")
    headers = ["Fecha", "T.Max", "T.Min", "Lluvia", "Viento", "UV", "Rad.MJ"]
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
            f"{daily.get('shortwave_radiation_sum', [0]*16)[i]:.1f}"
        ])
    pdf.add_data_table(headers, rows, [30, 25, 25, 25, 25, 20, 40])

    pdf_path = f"/tmp/informe_{nombre.replace(' ','_')}.pdf"
    pdf.output(pdf_path)
    
    return send_file(
        pdf_path, 
        as_attachment=True, 
        download_name=f"informe_{nombre}.pdf",
        mimetype='application/pdf'
    )

# Esta línea es OBLIGATORIA para Vercel
app = app
