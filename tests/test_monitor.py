import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import research_connectors as c
import monitor


class R:
    def __init__(self, code): self.status_code = code


def test_monitor_reports_each_source(monkeypatch):
    def get(url, params=None, timeout=None, headers=None):
        if 'isric' in url: raise TimeoutError()
        return R(503 if 'osrm' in url else 200)
    monkeypatch.setattr(c.SESSION, 'get', get)
    d = monitor.check()['data']
    by = {r['source']: r for r in d['sources']}
    assert by['ISRIC SoilGrids']['error'] == 'TimeoutError' and by['OSRM rutas']['http'] == 503
    assert d['up'] == d['total'] - 2
    assert all('key' not in r['source'].lower() for r in d['sources'])
