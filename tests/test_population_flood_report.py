"""Regresión: el PDF de población ribereña se crea con resultados existentes."""
import pytest
from poblacion.flood_report import pdf


def test_flood_pdf_is_downloadable():
    data = {
        'place':'Corrientes', 'river':'Paraná', 'radius_km':15, 'total':125000,
        'bands':[{'up_to_m':1,'people':1000,'under5':70,'over65':120},
                 {'up_to_m':3,'people':4500,'under5':350,'over65':540}],
        'scenarios':[{'label':'Alerta','people':4500,'band_m':3}],
    }
    content=pdf(data)
    assert content.startswith(b'%PDF-')
    assert len(content)>1500


def test_missing_population_bands_rejected():
    with pytest.raises(ValueError):
        pdf({'place':'Corrientes','bands':None})
