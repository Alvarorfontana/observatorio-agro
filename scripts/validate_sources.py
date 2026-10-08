#!/usr/bin/env python3
"""DOTS source audit. A source is never OPERATIVE merely because an env var exists."""
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import research_connectors as c
LAT,LON=-28.507,-59.043
POLY=[[-28.512,-59.049],[-28.502,-59.049],[-28.502,-59.037],[-28.512,-59.037]]
checks=[
 ('open-meteo','ANALYSIS',lambda:c.variables(LAT,LON)),
 ('nasa-gibs','IMAGE',c.nasa_gibs_capabilities),
 ('sentinel-2','CATALOG',lambda:c.scenes(LAT,LON,POLY)),
 ('nasa-power','ANALYSIS',lambda:c.nasa_power_long(LAT,LON,1)),
]
if os.environ.get('FIRMS_MAP_KEY'): checks.append(('nasa-firms','MARKERS',lambda:c.firms(LAT,LON,POLY)))
out=[]
for name,cap,fn in checks:
 row={'source':name,'capability':cap,'checked_at':datetime.now(timezone.utc).isoformat()}
 try:
  r=fn(); row.update(status='OPERATIVE',source_url=r.get('source_url'),scope=r.get('scope'))
 except Exception as e: row.update(status='ERROR',error=type(e).__name__+': '+str(e))
 out.append(row)
for name,envs in {'sentinel-hub':['CDSE_CLIENT_ID','CDSE_CLIENT_SECRET'],'era5-cds':['CDS_API_KEY'],'nasa-earthdata':['EARTHDATA_TOKEN']}.items():
 missing=[x for x in envs if not os.environ.get(x)];out.append({'source':name,'capability':'PROTECTED','status':'REQUIRES_CREDENTIAL' if missing else 'CREDENTIAL_PRESENT_NOT_E2E_CERTIFIED','missing_env':missing})
print(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'results':out},ensure_ascii=False,indent=2))
