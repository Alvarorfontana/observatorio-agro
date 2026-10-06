import requests
import csv
import io

class SatelliteDataEngine:
    def __init__(self):
        self.FIRMS_API_KEY = "" 

    def get_massive_open_meteo(self, lat, lon):
        current_vars = "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m,temperature_80m,temperature_120m,temperature_180m,wind_speed_80m,wind_speed_120m,wind_speed_180m,soil_temperature_0_to_7cm_mean,soil_temperature_7_to_28cm_mean,soil_temperature_28_to_100cm_mean,soil_moisture_0_to_7cm_mean,soil_moisture_7_to_28cm_mean,soil_moisture_28_to_100cm_mean,soil_moisture_100_to_255cm_mean,vapor_pressure_deficit,et0_fao_evapotranspiration"
        
        daily_vars = "weather_code,temperature_2m_max,temperature_2m_mean,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,rain_sum,showers_sum,snowfall_sum,precipitation_hours,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,shortwave_radiation_sum,direct_radiation_sum,diffuse_radiation_sum,direct_normal_irradiance_sum,terrestrial_radiation_sum,sunshine_duration,daylight_duration,uv_index_max,et0_fao_evapotranspiration,soil_moisture_0_to_7cm_mean,soil_moisture_7_to_28cm_mean,soil_moisture_28_to_100cm_mean,soil_moisture_100_to_255cm_mean"

        params = {
            "latitude": lat, "longitude": lon,
            "current": current_vars,
            "daily": daily_vars,
            "models": "gfs_seamless,ecmwf_ifs04,icon_seamless,gem_seamless",
            "timezone": "auto"
        }
        try:
            return requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15).json()
        except Exception as e:
            return {"error": str(e)}

    def get_enso_status(self):
        try:
            r = requests.get("https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", timeout=10)
            lines = r.text.strip().split('\n')
            last_line = lines[-1].split()
            oni_value = float(last_line[-1])
            estado = "El Niño" if oni_value >= 0.5 else "La Niña" if oni_value <= -0.5 else "Neutral"
            return {"oni": oni_value, "estado": estado}
        except:
            return {"oni": None, "estado": "No disponible"}

    def get_firms_hotspots(self, lat, lon, radius_km=50):
        if not self.FIRMS_API_KEY:
            return []
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{self.FIRMS_API_KEY}/viirs_snpp_nrt/1/{lon},{lat},{radius_km}"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code != 200 or "No data" in r.text: return []
            return [{'lat': float(row['latitude']), 'lon': float(row['longitude']), 'confianza': row['confidence']} for row in csv.DictReader(io.StringIO(r.text))]
        except:
            return []

    def calcular_thi(self, temp, humedad):
        if not temp or not humedad: return 0, "N/A"
        thi = (1.8 * temp + 32) - (0.55 - 0.0055 * humedad) * (1.8 * temp - 26)
        if thi < 72: return round(thi, 1), "Sin estrés"
        elif thi < 79: return round(thi, 1), "Estrés moderado"
        elif thi < 89: return round(thi, 1), "Estrés severo"
        else: return round(thi, 1), "EMERGENCIA"

    def get_all_data(self, lat, lon):
        meteo = self.get_massive_open_meteo(lat, lon)
        enso = self.get_enso_status()
        focos = self.get_firms_hotspots(lat, lon)
        current = meteo.get('current', {})
        thi, estado_thi = self.calcular_thi(current.get('temperature_2m', 0), current.get('relative_humidity_2m', 50))
        
        return {
            'meteo': meteo, 'enso': enso, 'focos': focos,
            'thi': thi, 'estado_thi': estado_thi,
            'temp_actual': current.get('temperature_2m', 0),
            'hum_actual': current.get('relative_humidity_2m', 0),
            'viento_actual': current.get('wind_speed_10m', 0),
            'presion_actual': current.get('surface_pressure', 0)
        
        }
