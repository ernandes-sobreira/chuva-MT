#!/usr/bin/env python3
"""Auditoria de exutório da estação ANA 66070004: HydroBASINS L6..L10.
Não usa centro urbano como exutório. Compara ponto publicado (duas coordenadas) e área ANA/SGB.
Saída: candidatos e diferenças, sem escolher automaticamente uma bacia inadequada.
"""
from pathlib import Path
import json,os,datetime as dt,traceback
import ee
R=Path("pesquisa_pantanal/recorte_cientifico/resultados");R.mkdir(parents=True,exist_ok=True)
SOURCES=[
 {"id":"SGB_2025","lon":-(57+42/60+8/3600),"lat":-(16+4/60+33/3600),"source":"AbrHidro artigo estação 66070004; datum SAD69; aproximação sem transformação explícita; area referência 32393 km²","referencia_km2":32393.0},
 {"id":"ACADEMICO_2006","lon":-(57+41/60+16/3600),"lat":-(16+3/60+47/3600),"source":"Dissertação UEM; coordenadas publicadas para estação 66070004; datum não certificado; ref 32774 km²","referencia_km2":32774.0},
 {"id":"PONTO_ANTERIOR_INVALIDO","lon":-57.681,"lat":-16.075,"source":"Ponto arbitrário do piloto, NÃO coordenada da estação","referencia_km2":32393.0}
]
result={"date_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"station_code":"66070004","type":"auditoria de localização do exutório","reference_areas_km2":[32393,32774],"queries":[],"errors":[]}
try:
 key=os.environ["EE_SERVICE_ACCOUNT_KEY"]; info=json.loads(key)
 ee.Initialize(ee.ServiceAccountCredentials(info["client_email"],key_data=key),project=os.environ.get("EE_PROJECT") or info["project_id"])
 for p in SOURCES:
  for level in [6,7,8,9,10]:
   rec={"id":p["id"],"n":level,"station_lon":round(p["lon"],7),"station_lat":round(p["lat"],7),"reference_area_km2":p["referencia_km2"],"source":p["source"]}
   try:
    fc=ee.FeatureCollection(f"WWF/HydroSHEDS/v1/Basins/hybas_{level}")
    fs=fc.filterBounds(ee.Geometry.Point([p["lon"],p["lat"]])).select(["HYBAS_ID","NEXT_DOWN","SUB_AREA","UP_AREA","PFAF_ID","DIST_MAIN"],retainGeometry=False).limit(3)
    items=[x["properties"] for x in fs.getInfo()["features"]]
    rec["matches"]=items
    if items:
     rec["delta_area_pct"]=round(100*(float(items[0]["UP_AREA"])/p["referencia_km2"]-1),3)
     rec["same_station_upstream_area"]=round(float(items[0]["UP_AREA"]),2)
   except Exception as e:rec["error"]=repr(e)
   result["queries"].append(rec)
   print(json.dumps({k:rec[k] for k in ["id","n","same_station_upstream_area","delta_area_pct"] if k in rec},ensure_ascii=False),flush=True)
except Exception as e:
 result["errors"].append(repr(e));traceback.print_exc()
finally:
 (R/"diagnostico_exutorio_niveis_6_10.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"total":len(result["queries"]),"errors":result["errors"]},ensure_ascii=False))
