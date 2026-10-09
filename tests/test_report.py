"""Informe PDF con diseño DOTS (Typst) y respaldo ReportLab."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import report_typst as rt

RESULT = {
    'version': 'DOTS Agentic 0.7', 'generated_at': '2026-10-09T20:46:00+00:00',
    'point': [-28.5, -59.04], 'polygon': [[-28.51, -59.05], [-28.51, -59.03], [-28.49, -59.03], [-28.49, -59.05]],
    'confidence': {'score': 77, 'label': 'media', 'received_sources': 5, 'failed_sources': 1},
    'summary': 'Análisis integral con 5 fuentes.', 'recommendations': ['Revisar aguadas.'],
    'warnings': ['Fuente X sin respuesta.'],
    'findings': [{'topic': 'Clima', 'status': 'modelado', 'text': 'Calor moderado / 50% — prueba de caracteres #especiales *y* [corchetes]'}],
    'metrics': [{'variable': 'Temperatura', 'value': 31.0, 'unit': '°C', 'reference': 'r', 'reading': 'x'},
                {'variable': 'THI bovino', 'value': 81.2, 'unit': 'índice', 'reference': 'r', 'reading': 'alto'},
                {'variable': 'Lluvia 7 días', 'value': 2.0, 'unit': 'mm', 'reference': 'r', 'reading': 'x'},
                {'variable': 'ET₀ 7 días', 'value': 30.0, 'unit': 'mm', 'reference': 'r', 'reading': 'x'}],
    'evidence': [{'source': 'clima', 'status': 'recibido', 'consulted_at': '2026-10-09T20:46:00', 'scope': 'clima'},
                 {'source': 'firms', 'status': 'sin dato'}],
    'raw': {'clima': {'payload': {'data': {'daily': {'time': [f'2026-10-{d:02d}' for d in range(9, 16)],
                                                     'precipitation_sum': [0, 1, 0, 0, 5, 0, 0],
                                                     'et0_fao_evapotranspiration': [5] * 7,
                                                     'temperature_2m_max': [33] * 7, 'temperature_2m_min': [19] * 7}}}}},
}


def test_number_format_argentino():
    assert rt.num(1234.5) == '1.234,5' and rt.num(0.712, 2) == '0,71' and rt.num(None) == '—'


def test_shape_normalized_and_proportional():
    pts = rt.shape(RESULT['polygon'])
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    assert min(xs) >= 0 and max(xs) <= 1 and min(ys) >= 0 and max(ys) <= 1
    assert rt.shape([[1, 1]]) == []


def test_build_data_kpis_and_charts():
    d = rt.build_data(RESULT, 'Potrero', {'lot': {'name': 'Potrero Norte', 'areaHa': 400, 'perimeterKm': 8, 'compactness': 0.78}})
    by = {k['label']: k for k in d['kpis']}
    assert by['THI bovino']['tone'] == 'risk' and by['Balance lluvia − ET₀']['value'] == '-28,0'
    assert d['lot']['name'] == 'Potrero Norte' and any(f[0] == 'Compacidad' for f in d['lot']['facts'])
    assert d['charts'][0]['labels'][0] == '09/10'
    json.dumps(d, ensure_ascii=False)


def test_pdf_compiles_with_typst():
    pytest.importorskip('typst')
    pdf, engine = rt.pdf(RESULT, 'Potrero', {'lot': {'name': 'Potrero Norte', 'areaHa': 400, 'perimeterKm': 8, 'compactness': 0.78}})
    assert engine == 'typst' and pdf[:5] == b'%PDF-' and len(pdf) > 20000


def test_pdf_falls_back_to_reportlab(monkeypatch):
    monkeypatch.setattr(rt, 'TEMPLATE', '/no/existe.typ')
    pdf, engine = rt.pdf(RESULT, 'Potrero')
    assert engine == 'reportlab' and pdf[:5] == b'%PDF-'
