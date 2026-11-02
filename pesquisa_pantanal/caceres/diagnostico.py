#!/usr/bin/env python3
"""Diagnostico do recorte Pantanal Caceres: dados GEE, sem conclusoes prematuras."""
from pathlib import Path
import os,json,traceback,datetime
import ee
OUT=Path("pesquisa_pantanal/caceres/resultados")
OUT.mkdir(parents=True,exist_ok=True)
meta={"data_execucao_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"status":"inicio","erros":[]}
def save():
 (OUT/"diagnostico_gee.json").write_text(json.dumps(meta,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
try:
 key=os.environ["EE_SERVICE_ACCOUNT_KEY"].strip()
 obj=json.loads(key)
 project=os.environ.get("EE_PROJECT") or obj["project_id"]
 ee.Initialize(ee.ServiceAccountCredentials(obj["client_email"],key_data=key),project=project)
 meta["earth_engine"]="autenticado"
 point=ee.Geometry.Point([-57.681,-16.075])
 basins=ee.FeatureCollection("WWF/HydroSHEDS/v1/Basins/hybas_6")
 nearby=basins.filterBounds(point)
 meta["caceres_ponto"]=[-57.681,-16.075]
 meta["n_bacias_intersectam_ponto"]=nearby.size().getInfo()
 meta["basins_at_point"]=[{"id":int(f["properties"]["HYBAS_ID"]),"next_down":f["properties"].get("NEXT_DOWN"),
 "upstream_km2":f["properties"].get("UP_AREA"),"sub_km2":f["properties"].get("SUB_AREA"),
 "pfaf":f["properties"].get("PFAF_ID")} for f in nearby.limit(5).getInfo()["features"]]
 if meta["n_bacias_intersectam_ponto"]>0:
  geom=ee.Feature(nearby.first()).geometry().simplify(500).getInfo()
  (OUT/"hidrobasins_unidade_local_caceres.geojson").write_text(json.dumps({"type":"FeatureCollection","features":[{"type":"Feature","geometry":geom,"properties":{"fonte":"HydroBASINS nivel 6","tipo":"unidade local, nao bacia total a montante"}}]},ensure_ascii=False),encoding="utf-8")
 col_id="projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_monthly_v4"
 col=ee.ImageCollection(col_id)
 meta["mapbiomas_mensal_asset"]=col_id
 meta["mapbiomas_mensal_n_imagens"]=col.size().getInfo()
 meta["primeira_imagem_id"]=col.first().id().getInfo()
 meta["primeira_imagem_bandNames"]=col.first().bandNames().getInfo()
 meta["ultimas_imagens"]=col.sort("system:index",False).limit(3).aggregate_array("system:index").getInfo()
 annual_id="projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_annual_v4"
 annual=ee.Image(annual_id)
 meta["mapbiomas_anual_asset"]=annual_id
 bn=annual.bandNames().getInfo()
 meta["mapbiomas_annual_band_first_last"]=[bn[:3],bn[-3:]]
 cover_id="projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3"
 cover=ee.Image(cover_id)
 meta["mapbiomas_cobertura_asset"]=cover_id
 bn=cover.bandNames().getInfo()
 meta["cover_bands"]=[bn[:2],bn[-2:]]
 try:
  first=ee.Image(col.filter(ee.Filter.stringContains("system:index","2024_06")).first())
  mm=first.reduceRegion(reducer=ee.Reducer.frequencyHistogram(),geometry=ee.Geometry.Rectangle([-57.95,-16.35,-57.35,-15.85]),scale=300,maxPixels=1e8,bestEffort=True).getInfo()
  meta["histograma_mensal_2024_06_res300m"]=mm
  meta["id_mensal_2024_06"]=first.id().getInfo()
 except Exception as e:meta["erros"].append("histograma: "+repr(e))
 meta["status"]="diagnostico_concluido"
except Exception as e:
 meta["status"]="erro"
 meta["erros"].append(repr(e));traceback.print_exc()
finally:
 save()
print(json.dumps(meta,ensure_ascii=False,indent=2,default=str)[:15000])
