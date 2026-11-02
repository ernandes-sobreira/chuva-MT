#!/usr/bin/env python3
"""REEXTRACAO CIENTIFICA DO RECORTE VALIDADO, sem reutilizar a unidade HydroBASINS L6.
Estação ANA 66070004: area upstream HydroBASINS L10 (222 subbacias).
Indicadores: chuva CHIRPS no catchment, pastagens no catchment, agua superficial
NA INTERSECAO DO BIOMA PANTANAL (IBGE 2025) COM o catchment. Nao medir volume.
"""
from pathlib import Path
import os,json,csv,traceback,datetime as dt
import ee
from shapely.geometry import shape,mapping
from shapely.ops import unary_union
from pyproj import Geod

P=Path("pesquisa_pantanal/recorte_cientifico")
R=P/"resultados";R.mkdir(parents=True,exist_ok=True)
out=R/"SERIE_CORRIGIDA_BACIA_ANA_66070004_1985_2025.csv"
meta=json.loads((R/"VALIDACAO_RECORTE_CACERES.json").read_text(encoding="utf-8"))
if meta.get("status")!="concluido":raise SystemExit("Bacia nao validada!")
BASE=shape(json.loads((R/"BACIA_VERIFICADA_UPSTREAM_ANA_66070004.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
B=json.loads((R/"BIOMAS_IBGE_2025_CONTEXTO_CACERES.geojson").read_text(encoding="utf-8"))["features"]
panta=unary_union([shape(f["geometry"]) for f in B if f["properties"].get("bioma")=="Pantanal"])
flood=BASE.intersection(panta)
if not flood.is_valid:flood=flood.buffer(0)
geod=Geod(ellps="GRS80")
areakm2=abs(geod.geometry_area_perimeter(flood)[0])/1e6
if not 700 < areakm2 < 1200:raise SystemExit("Recorte pantaneiro difere da auditoria: "+str(areakm2))
(R/"RECORTE_PANTANAL_INTERSECAO_BACIA_ANA_66070004.geojson").write_text(json.dumps({"type":"FeatureCollection","features":[{"type":"Feature","geometry":mapping(flood.simplify(.003,preserve_topology=True)),"properties":{"fonte":"IBGE biomas 2025 × HydroBASINS L10 validado","bioma":"Pantanal","estacao":"ANA 66070004","area_km2":round(areakm2,2)}}]},ensure_ascii=False),encoding="utf-8")
qc={"data_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
"status":"inicio","recorte_agua":"bioma Pantanal IBGE 2025 ∩ bacia ANA 66070004 (HydroBASINS L10)",
"recorte_chuva_pastagem":"bacia contribuinte ANA 66070004 (HydroBASINS L10)",
"area_bacia_km2":meta["rede_hidrografica"]["area_up_area_km2"],
"area_pantanal_intersecao_km2":round(areakm2,2),
"asset_agua_mensal":"projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_monthly_v4",
"asset_agua_anual":"projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_annual_v4",
"asset_uso_solo":"projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3",
"asset_chuva":"UCSB-CHG/CHIRPS/DAILY",
"resolucao_agua_m":120,"resolucao_pastagem_m":180,"resolucao_chuva_m":5566,
"advertencias":["Analise de área com água e não volume.","Apenas 960 km² do bioma Pantanal dentro da drenagem até a estação; não é a planície toda.",
"A bacia da estação é estimada com HydroBASINS L10; não é o polígono oficial de ANA.",
"Não usar as regressões anteriores do nível 6 como inferências para este novo recorte."],
"anos_completos":[],"erros":[]}
def save():
 (R/"STATUS_EXTRAÇÃO_RECORTE_VALIDADO.json").write_text(json.dumps(qc,ensure_ascii=False,indent=2),encoding="utf-8")
header=["ano","mes","data","agua_superficial_bioma_pantanal_montante_ha","chuva_na_bacia_mm","pastagem_plantada_bacia_ha",
        "agua_anual_bioma_pantanal_montante_ha"]
records={}
def store():
 with out.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=header);w.writeheader()
  for k in sorted(records):w.writerow(records[k])
try:
 k=os.environ["EE_SERVICE_ACCOUNT_KEY"].strip();data=json.loads(k)
 ee.Initialize(ee.ServiceAccountCredentials(data["client_email"],key_data=k),project=os.environ.get("EE_PROJECT") or data["project_id"])
 G=ee.Geometry(mapping(BASE.simplify(.002,preserve_topology=True)),proj="EPSG:4326",geodesic=False)
 F=ee.Geometry(mapping(flood.simplify(.002,preserve_topology=True)),proj="EPSG:4326",geodesic=False)
 WM=ee.ImageCollection(qc["asset_agua_mensal"])
 WA=ee.Image(qc["asset_agua_anual"])
 LU=ee.Image(qc["asset_uso_solo"])
 CH=ee.ImageCollection(qc["asset_chuva"]).select("precipitation")
 for y in range(1985,2026):
  bank=[]
  rains=[]
  for m in range(1,13):
   i=ee.Image(WM.filter(ee.Filter.eq("system:index",f"water_monthly_{y}_{m:02d}")).first())
   pix=i.select("water_monthly").eq(m)
   bank.append(ee.Image.pixelArea().updateMask(pix).divide(10000).rename(f"m{m:02d}"))
   ny=y+(m==12);nm=m%12+1
   rain=CH.filterDate(f"{y}-{m:02d}-01",f"{ny}-{nm:02d}-01").sum().rename(f"m{m:02d}")
   rains.append(rain)
  aq=ee.Image.cat(bank).reduceRegion(ee.Reducer.sum(),geometry=F,scale=120,tileScale=4,maxPixels=1e9).getInfo()
  rq=ee.Image.cat(rains).reduceRegion(ee.Reducer.mean(),geometry=G,scale=5566,tileScale=4,maxPixels=1e9).getInfo()
  cover=LU.select(f"classification_{y}").eq(15)
  pasture=ee.Image.pixelArea().updateMask(cover).divide(10000).reduceRegion(ee.Reducer.sum(),geometry=G,scale=180,tileScale=4,maxPixels=1e9).getInfo().get("area")
  ay=WA.select(f"classification_{y}").eq(1)
  waterannual=ee.Image.pixelArea().updateMask(ay).divide(10000).reduceRegion(ee.Reducer.sum(),geometry=F,scale=120,tileScale=4,maxPixels=1e9).getInfo().get("area")
  if pasture is None or waterannual is None:raise RuntimeError("Nulos anuais "+str(y))
  if float(pasture)>3_300_000 or float(waterannual)>100000:raise RuntimeError("Area acima limite fisico para "+str(y))
  for m in range(1,13):
   key=f"m{m:02d}"
   if key not in aq or key not in rq:raise RuntimeError("Bandas ausentes "+str(y)+"/"+str(m))
   area,rain=aq[key],rq[key]
   if area is None or rain is None:raise RuntimeError("Mes nulo "+str(y)+"/"+str(m))
   if not 0<=float(area)<=100000:raise RuntimeError("Agua acima area do recorte "+str(y)+"/"+str(m))
   records[f"{y}-{m:02d}"]={"ano":y,"mes":m,"data":f"{y}-{m:02d}",
       "agua_superficial_bioma_pantanal_montante_ha":round(float(area),3),
       "chuva_na_bacia_mm":round(float(rain),3),
       "pastagem_plantada_bacia_ha":round(float(pasture),3),
       "agua_anual_bioma_pantanal_montante_ha":round(float(waterannual),3)}
  store()
  qc["anos_completos"].append(y)
  if y%5==0 or y==2025:print(f"Validado {y}: {len(records)} meses; pastagem={pasture:.1f} ha; agua anual={waterannual:.1f} ha",flush=True)
  save()
 qc["total_meses"]=len(records)
 if len(records)!=492:raise RuntimeError("Serie de 492 meses incompleta")
 qc["status"]="concluido"
except Exception as e:
 qc["status"]="falha";qc["erros"].append(repr(e));traceback.print_exc()
finally:
 store();save()
 print(json.dumps({k:v for k,v in qc.items() if k not in ["anos_completos"]},ensure_ascii=False,indent=2))
 if qc["status"]!="concluido":raise SystemExit("Falha de extracao: dados parciais guardados e nao considerados conclusivos")
