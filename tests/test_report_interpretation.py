import unittest

import report_typst


class VegetationInterpretationTests(unittest.TestCase):
    def test_missing_scene_does_not_invent_a_reading(self):
        text = report_typst.vegetation_interpretation({}, [])
        self.assertIn("No se obtuvo una observación Sentinel-2 válida", text)
        self.assertIn("ausencia de datos", text)

    def test_single_scene_reports_date_value_and_limits(self):
        ndvi = {"latest": {
            "datetime": "2026-10-18T14:00:00Z",
            "ndvi_mean": 0.6432,
            "clear_fraction_lot": 0.82,
        }}
        text = report_typst.vegetation_interpretation(ndvi, [ndvi["latest"]])
        self.assertIn("2026-10-18", text)
        self.assertIn("0,643", text)
        self.assertIn("82,0 %", text)
        self.assertIn("no constituye una medición directa", text)
        self.assertIn("rendimiento", text)

    def test_modis_history_is_reported_as_context_not_parcel_level_crop_history(self):
        chart, note = report_typst.modis_history_chart({
            "sensor": "MODIS Terra MOD13Q1 (250 m, 16 días)",
            "series": [
                {"status": "válida", "datetime": "2022-01-01T00:00:00Z", "ndvi_mean": 0.42},
                {"status": "sin dato", "datetime": "2022-01-17T00:00:00Z"},
                {"status": "válida", "datetime": "2026-01-01T00:00:00Z", "ndvi_mean": 0.61},
            ],
        })
        self.assertEqual(chart["series"][0]["values"], [0.42, 0.61])
        self.assertIn("250 m", chart["subtitle"])
        self.assertIn("no identifica cultivos ni rotaciones", note)
        self.assertIn("no debe compararse directamente", note)

    def test_comparison_is_explicitly_limited_to_two_observations(self):
        rows = [
            {"status": "válida", "datetime": "2026-09-20T00:00:00Z", "ndvi_mean": 0.51},
            {"status": "válida", "datetime": "2026-10-18T00:00:00Z", "ndvi_mean": 0.64},
        ]
        text = report_typst.vegetation_interpretation({"latest": rows[-1]}, rows)
        self.assertIn("aumentó", text)
        self.assertIn("0,130 unidades de NDVI", text)
        self.assertIn("no identifica por sí sola su causa", text)


if __name__ == "__main__":
    unittest.main()
