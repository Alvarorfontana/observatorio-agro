"""Contract tests for DOTS Campo scientific reports (offline)."""
import unittest
from unittest.mock import patch
import enso_science
import enso_data_api
from flask import Flask

class ScientificReportTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(enso_data_api.enso_data_api)
        self.client = self.app.test_client()

    def test_summary_has_provenance_and_no_event_claim(self):
        result = enso_science.summarize_oni([
            {"month": "2025-01", "anomalyC": 0.8},
            {"month": "2025-02", "anomalyC": -0.7},
            {"month": "2025-03", "anomalyC": 0.1},
        ])
        self.assertEqual(result["counts_overlapping_seasons"], {"warm": 1, "cold": 1, "neutral": 1})
        self.assertFalse(result["phase_is_official_event"])
        self.assertEqual(result["period"]["end"], "2025-03")

    def test_no_data_rejected(self):
        with self.assertRaises(ValueError):
            enso_science.summarize_oni([])

    def test_report_json_offline(self):
        points = [{"month": "2025-01", "anomalyC": 0.6}, {"month": "2025-02", "anomalyC": 0.7}]
        with patch.dict(enso_data_api._CACHE, {"data": points, "at": 999999999999.0, "url": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", "stale": False}):
            response = self.client.get("/api/enso/scientific-report")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["sample_size_overlapping_seasons"], 2)
        self.assertFalse(body["traceability"]["synthetic"])
        self.assertIn("limitations", body)
        self.assertIn("source_url", body["traceability"])

    def test_soi_missing_and_out_of_range(self):
        rows = "\n".join(["2020 " + " ".join(["-99.99", "999.9", "0.3"] * 4)] * 12)
        with self.assertRaises(ValueError):
            enso_data_api._parse_psl_soi(rows)

if __name__ == "__main__":
    unittest.main()
