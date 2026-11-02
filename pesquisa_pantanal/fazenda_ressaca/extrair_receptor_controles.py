#!/usr/bin/env python3
"""Extração observada de células receptoras e controle (2 km) no entorno Ressaca.
Receptor preselecionado pela trajetória MERIT D8 + área de água em 1985.
Controle preselecionado por ausência de trajetória e água basal semelhante; NÃO prova ausência de exposição hidrológica.
MapBiomas Água mensal C5, uso do solo C11, CHIRPS v2, HAND MERIT.
"""
from pathlib import Path
import os, json, csv, traceback
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
import ee
P=Path("pesquisa_pantanal/fazenda_ressaca")
R=P/"jusante"; R.mkdir(parents=True,exist_ok=True)
raw=json.loads((P/"resultados/GRADE_ENTORNO_RESSACA_2KM.geojson").read_text(encoding="utf-8"))
G={f["properties"]["id"]:shape(f["geometry"]) for f in raw["features"]}
ids={
 "FONTE_PASTAGEM":["C04_05","C04_06","C04_07","C05_05","C05_06","C05_07","C06_05","C06_06","C06_07"],
 "RECEPTOR_D8":["C03_02","C03_03","C03_04"],
 "CONTROLE_NORTE":["C03_09","C03_10","C03_11"],
 "CONTROLE_SENSIBILIDADE":["C04_08","C04_09","C04_10"]
}
rx=json.loads((R/"CANDIDATOS_RECEPTORES_CONTROLE.json").read_text(encoding="utf8"))
assert rx["n_candidate_receptor"]>=3
# Confirm a priori no source overlap; observed D8 route counts are criteria, not proof.
gridmetrics={r["id"]:r for r in json.loads((R/"CANDIDATOS_RECEPTORES_CONTROLE.json").read_text(encoding="utf8"))["downstream_all"]}
for cid in ids["RECEPTOR_D8"]:
 assert cid in gridmetrics and gridmetrics[cid]["n_core_trace_intersections"]>=10
for name in ["CONTROLE_NORTE","CONTROLE_SENSIBILIDADE"]:
 assert all(x not in gridmetrics for x in ids[name])
assert not set(ids["RECEPTOR_D8"]).intersection(ids["FONTE_PASTAGEM"])
assert not set(ids["CONTROLE_NORTE"]).intersection(ids["FONTE_PASTAGEM"])
def grpgeom(cells):return unary_union([G[k] for k in cells])
groups={name:grpgeom(cells) for name,cells in ids.items()}
features=[{"type":"Feature","properties":{"grupo":name,"ids":list(cells),"area_teorica_ha":len(cells)*400,
    "tipo":"amostragem de 2 km; não é limite de imóvel ou bacia hidrológica oficial"},
    "geometry":mapping(groups[name])} for name,cells in ids.items()]
(R/"POLIGONOS_PILOTO_RECEPTOR_CONTROLES.geojson").write_text(json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False),encoding="utf8")
header=["ano","mes","grupo","agua_mensal_ha","chuva_mensal_mm","pastagem_anual_ha"]
annual=["ano","grupo","agua_anual_ha","pastagem_anual_ha"]
mrows=[];arows=[]
status={"status":"inicio","groups":ids,"fontes":["MapBiomas Água C5","MapBiomas cobertura C11","CHIRPS v2","MERIT Hydro HAND"],
 "escala_m":{"agua":30,"pastagem":30,"precipitacao":5566},
 "regras":["Selecionar receptor por conexões MERIT D8, controle por ausência de trajetos e água basal 1985.",
 "Os controles não têm garantia de ausência de influência hidrológica da expansão das pastagens.",
 "Sazonalidade de água não é vazão ou volume.",
 "As séries de 41 anos não validam a delimitação fundiária da Fazenda Ressaca."],
 "completed_years":[],"erros":[]}
def write(name,cols,rows):
 with (R/name).open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
def report():
 (R/"STATUS_PAREAMENTO_HIDROLOGICO.json").write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf8")
try:
 key=os.environ["EE_SERVICE_ACCOUNT_KEY"].strip()
 auth=json.loads(key)
 ee.Initialize(ee.ServiceAccountCredentials(auth["client_email"],key_data=key),project=os.environ.get("EE_PROJECT") or auth["project_id"])
 fcoll=ee.FeatureCollection([ee.Feature(ee.Geometry(mapping(v),proj="EPSG:4326",geodesic=False),{"grupo":k}) for k,v in groups.items()])
 cover=ee.Image("projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3")
 water=ee.Image("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_annual_v4")
 wm=ee.ImageCollection("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_monthly_v4")
 rain=ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select("precipitation")
 merit=ee.Image("MERIT/Hydro/v1_0_1")
 h=merit.select("hnd")
 hand=h.reduceRegions(collection=fcoll,reducer=ee.Reducer.median(),scale=92,maxPixelsPerRegion=1e6).getInfo()
 status["hand_median_m"]={f["properties"]["grupo"]:f["properties"].get("median") for f in hand["features"]}
 for year in range(1985,2026):
  masks=[];prec=[]
  for month in range(1,13):
   im=ee.Image(wm.filter(ee.Filter.eq("system:index",f"water_monthly_{year}_{month:02d}")).first())
   masks.append(ee.Image.pixelArea().updateMask(im.select("water_monthly").eq(month)).divide(10000).rename(f"m{month:02d}"))
   ny=year+(month==12);nm=month%12+1
   prec.append(rain.filterDate(f"{year}-{month:02d}-01",f"{ny}-{nm:02d}-01").sum().rename(f"m{month:02d}"))
  wresp=ee.Image.cat(masks).reduceRegions(collection=fcoll,reducer=ee.Reducer.sum(),scale=30,tileScale=4).getInfo()["features"]
  presp=ee.Image.cat(prec).reduceRegions(collection=fcoll,reducer=ee.Reducer.mean(),scale=5566,tileScale=4).getInfo()["features"]
  past=ee.Image.pixelArea().updateMask(cover.select(f"classification_{year}").eq(15)).divide(10000)
  wat=ee.Image.pixelArea().updateMask(water.select(f"classification_{year}").eq(1)).divide(10000)
  ar=ee.Image.cat([past.rename("pastagem_ha"),wat.rename("agua_anual_ha")]).reduceRegions(
    collection=fcoll,reducer=ee.Reducer.sum(),scale=30,tileScale=4).getInfo()["features"]
  wdata={x["properties"]["grupo"]:x["properties"] for x in wresp}
  pdata={x["properties"]["grupo"]:x["properties"] for x in presp}
  adata={x["properties"]["grupo"]:x["properties"] for x in ar}
  if any(len(z)!=4 for z in [wdata,pdata,adata]):raise RuntimeError("Grupos incompletos "+str(year))
  for g in ids:
   pv=adata[g].get("pastagem_ha");wv=adata[g].get("agua_anual_ha")
   arw={"ano":year,"grupo":g,"agua_anual_ha":round(float(wv or 0),3),
        "pastagem_anual_ha":round(float(pv or 0),3)}
   arows.append(arw)
   for month in range(1,13):
    k=f"m{month:02d}";v=wdata[g].get(k);r=pdata[g].get(k)
    if r is None:raise RuntimeError(f"CHIRPS nulo {year}-{month} {g}")
    mrows.append({"ano":year,"mes":month,"grupo":g,"agua_mensal_ha":round(float(v or 0),3),
     "chuva_mensal_mm":round(float(r),3),"pastagem_anual_ha":arw["pastagem_anual_ha"]})
  status["completed_years"].append(year)
  if year%5==0 or year==2025:
   write("GRUPOS_PILOTO_MENSAL_1985_2025.csv",header,mrows)
   write("GRUPOS_PILOTO_ANUAL_1985_2025.csv",annual,arows)
   print("year",year,"monthly records",len(mrows),"water receptor",wdata["RECEPTOR_D8"].get("m01"),flush=True)
   report()
 write("GRUPOS_PILOTO_MENSAL_1985_2025.csv",header,mrows)
 write("GRUPOS_PILOTO_ANUAL_1985_2025.csv",annual,arows)
 if len(mrows)!=492*4 or len(arows)!=41*4:raise RuntimeError("Séries incompletas")
 status["n_monthly"]=len(mrows);status["n_annual"]=len(arows)
 status["status"]="concluido"
except Exception as e:
 status["status"]="falha_parcial";status["erros"].append(repr(e));traceback.print_exc()
finally:
 report()
 print(json.dumps({k:v for k,v in status.items() if k not in ["completed_years"]},ensure_ascii=False,indent=2)[:4500])
 if status["status"]!="concluido":raise SystemExit("Falha extração: não calcular associação causal.")
