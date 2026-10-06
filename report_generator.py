import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import datetime
import os

class PremiumReportGenerator(FPDF):
    def __init__(self, title, zone_name, lat, lon):
        super().__init__()
        self.title = title
        self.zone = zone_name
        self.lat = lat
        self.lon = lon
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(30, 58, 95)
        self.cell(0, 10, self.title, ln=True, align='C')
        self.set_font('Helvetica', '', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, f"Lote: {self.zone} | Centroide: {self.lat}, {self.lon} | Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
        self.ln(3)
        self.set_draw_color(30, 58, 95)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Fuentes: Open-Meteo (Ensemble), NASA GIBS, NOAA | Pag. {self.page_no()}', align='C')

    def section_title(self, title):
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(30, 58, 95)
        self.set_fill_color(230, 240, 250)
        self.cell(0, 7, f"  {title}", ln=True, fill=True)
        self.ln(3)

    def add_data_table(self, headers, data, col_widths=None):
        if not col_widths: col_widths = [190 / len(headers)] * len(headers)
        self.set_font('Helvetica', 'B', 7)
        self.set_fill_color(30, 58, 95)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 5, h, border=1, align='C', fill=True)
        self.ln()
        self.set_font('Helvetica', '', 7)
        self.set_text_color(0, 0, 0)
        fill = False
        for row in data:
            self.set_fill_color(245, 245, 245) if fill else self.set_fill_color(255, 255, 255)
            for i, val in enumerate(row):
                self.cell(col_widths[i], 4, str(val), border=1, align='C', fill=True)
            self.ln()
            fill = not fill
        self.ln(4)

    def add_chart(self, chart_path, w=180):
        if os.path.exists(chart_path):
            self.image(chart_path, x=15, w=w)
            self.ln(5)

def generate_charts(daily, filename_prefix):
    dates = daily.get('time', [])
    if not dates: return
    fig, ax1 = plt.subplots(figsize=(10, 4))
    rain = daily.get('precipitation_sum', [0]*len(dates))
    ax1.bar(range(len(dates)), rain, color='#3182ce', alpha=0.7)
    ax1.set_ylabel('Precipitacion (mm)', color='#3182ce')
    ax2 = ax1.twinx()
    rad = daily.get('shortwave_radiation_sum', [0]*len(dates))
    ax2.plot(range(len(dates)), rad, color='#d69e2e', marker='o', markersize=3)
    ax2.set_ylabel('Radiacion (MJ/m2)', color='#d69e2e')
    ax1.set_xticks(range(len(dates)))
    ax1.set_xticklabels([d[-5:] for d in dates], rotation=45, fontsize=7)
    plt.tight_layout()
    plt.savefig(f"{filename_prefix}_rain_rad.png", dpi=120)
    plt.close()
    
