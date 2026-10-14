"""Reglas DOTS Agentic sobre módulos del lote: cada conclusión sale de un dato y un umbral declarados."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import agentic_rules as ar


def ndvi(*vals):
    return {'sensor': 'Sentinel-2', 'series': [{'status': 'válida', 'ndvi_mean': v, 'datetime': f'2026-09-{i + 10}T00:00:00Z'} for i, v in enumerate(vals)]}


def test_empty_infers_nothing():
    out = ar.evaluate({})
    assert out == {'findings': [], 'metrics': [], 'recommendations': [], 'modules': []}


def test_overload_plus_drought_is_top_priority():
    k = {'ndvi': ndvi(0.55, 0.40),
         'forraje': {'growth_rate_30d': 20, 'ev_ha': 0.5, 'ev_lot': 100, 'current_load_ev_ha': 0.8, 'load_balance': 'carga por encima'},
         'lluvia': {'spi': {'3': {'spi': -1.4, 'mm': 120, 'normal': 260, 'class': 'sequía moderada'}}},
         'lot': {'areaHa': 200}}
    out = ar.evaluate(k)
    top = out['recommendations'][0]
    assert top['priority'] == 1 and 'Bajar la carga' in top['text'] and '60 EV' in top['text']
    assert any('Sequía y caída del vigor' in r['text'] for r in out['recommendations'])
    assert set(out['modules']) >= {'ndvi', 'forraje', 'lluvia'}


def test_eudr_verification_and_negative_margin():
    k = {'sustentabilidad': {'deforestation': {'verdict': 'pérdida de cobertura arbórea detectada · requiere verificación',
                                               'cutoff': '31/12/2020', 'tree_change_pp': -8, 'tree_loss_ha': 20, 'map_noise_pp': 0.6}},
         'costos': {'inputs': {'price_kg': 1800}, 'margin': {'net': -500000, 'gross': 10_000_000, 'breakeven_price_kg': 1900, 'freight': 1_200_000},
                    'logistics': {'km': 650, 'hours': 9.5}}}
    out = ar.evaluate(k)
    texts = ' | '.join(r['text'] for r in out['recommendations'])
    assert 'EUDR' in texts and 'pérdida' in texts and 'flete pesa' in texts and '8 horas' in texts
    assert [r['priority'] for r in out['recommendations']] == sorted(r['priority'] for r in out['recommendations'])


def test_engine_merges_rules(monkeypatch):
    import agentic_engine as ae, research_connectors as c
    monkeypatch.setattr(c, 'research_bundle', lambda lat, lon, ina=None: {'sources': {}})
    r = ae.analyze(-28.5, -59.0, 'clima', known={'lluvia': {'spi': {'3': {'spi': -1.2, 'mm': 1, 'normal': 2, 'class': 'sequía moderada'}}}})
    assert r['modules'] == ['lluvia'] and r['recommendations'][0].startswith('Prioridad media')
    assert 'módulos del lote' in r['summary']


def test_enso_strong_nino_wet_zone():
    k = {'enso': {'phase': 'El Niño muy fuerte', 'oni': 2.16, 'lot': {'analog_seasons': ['1997-98', '2015-16'],
          'groups': {'El Niño fuerte o muy fuerte': {'n': 3, 'vs_neutral_pct': 57, 'wetter_than_neutral': 2}}}}}
    out = ar.evaluate(k)
    assert 'enso' in out['modules'] and out['recommendations'][0]['priority'] == 1
    assert 'preparar bajos' in out['recommendations'][0]['text'] and '+57 %' in out['findings'][0]['text']
