import unittest
from unittest.mock import patch, Mock
from enso_data_api import _parse_oni, enso_data_api, _CACHE
from flask import Flask

class EnsoTests(unittest.TestCase):
 def test_parse_official_format(self):
  raw="SEAS YR TOTAL ANOM\n"+ "\n".join(f"DJF {year} 25.01 -1.32" for year in range(1950,2071))
  rows=_parse_oni(raw)
  self.assertEqual(len(rows),121)
  self.assertEqual(rows[0]["month"],"1950-01")
  self.assertEqual(rows[0]["anomalyC"],-1.32)
 def test_bad_data_rejected(self):
  with self.assertRaises(ValueError): _parse_oni("NOT A NOAA FILE")
 def test_endpoint_with_mocked_noaa(self):
  raw="SEAS YR TOTAL ANOM\n"+"\n".join(f"DJF {year} 25.01 -1.32" for year in range(1950,2071))
  app=Flask(__name__);app.register_blueprint(enso_data_api)
  _CACHE.update({"at":0,"data":None,"stale":False})
  with patch("enso_data_api.requests.get",return_value=Mock(status_code=200,text=raw)):
   result=app.test_client().get("/api/enso/oni")
  self.assertEqual(result.status_code,200)
  self.assertEqual(result.json["index"],"ONI")
  self.assertFalse(result.json["stale"])
if __name__=="__main__":unittest.main()
