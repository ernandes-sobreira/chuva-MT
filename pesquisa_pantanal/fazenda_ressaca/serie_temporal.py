#!/usr/bin/env python3
"""Série observada no hotspot de 3x3 células, NÃO no perímetro da Fazenda Ressaca.
MapBiomas Cobertura C11, MapBiomas Água C5 e CHIRPS. Sem imputação.
"""
import os,json,csv,traceback
from pathlib import Path
from shapely.geometry import shape,mapping
from shapely.ops import unary_union
import ee
R=Path("pesquisa_pantanal/fazenda_ressaca/resultados")
grid=json.loads((R/"HOTSPOT_CELULAS_RESSACA.geojson").read_text())
geom=unary_union([shape(x["geometry"]) for x in grid["features"]])
m={"status":"início","erros":[],"anos":[],"aviso":"Hotspot no entorno do centroide. NÃO equivale ao imóvel SIGEF."}
def write(name,head,data):
 with (R/name).open("w",newline="",encoding="utf-8-sig") as f:
  w=csv.DictWriter(f,fieldnames=head);w.writeheader();w.writerows(data)
try:
 key=os.environ["EE_SERVICE_ACCOUNT_KEY"];o=json.loads(key)
 ee.Initialize(ee.ServiceAccountCredentials(o["client_email"],key_data=key),project=os.environ.get("EE_PROJECT") or o["project_id"])
 g=ee.Geometry(mapping(geom),proj="EPSG:4326",geodesic=False)
 cover=ee.Image("projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3")
 annual=ee.Image("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_annual_v4")
 monthly=ee.ImageCollection("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_monthly_v4")
 # Rain in same 6x6km footprint. Low CHIRPS spatial resolution: interpret cautiously.
 rain=ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select("precipitation")
 years=[];months=[]
 for y in range(1985,2026):
  pc=cover.select(f"classification_{y}").eq(15)
  wc=annual.select(f"classification_{y}").eq(1)
  im=ee.Image.cat([
   ee.Image.pixelArea().updateMask(pc).divide(10000).rename("p"),
   ee.Image.pixelArea().updateMask(wc).divide(10000).rename("w")])
  vals=im.reduceRegion(ee.Reducer.sum(),g,30,maxPixels=1e8,tileScale=4).getInfo()
  yrs={"ano":y,"pastagem_ha":round(float(vals.get("p") or 0),2),
       "agua_anual_ha":round(float(vals.get("w") or 0),2)}
  years.append(yrs)
  wm=[];rm=[]
  for month in range(1,13):
   wimg=ee.Image(monthly.filter(ee.Filter.eq("system:index",f"water_monthly_{y}_{month:02d}")).first())
   wm.append(ee.Image.pixelArea().updateMask(wimg.eq(month)).divide(10000).rename(f"m{month:02d}"))
   ny=y+(month==12);nm=month%12+1
   rm.append(rain.filterDate(f"{y}-{month:02d}-01",f"{ny}-{nm:02d}-01").sum().rename(f"m{month:02d}"))
  water=ee.Image.cat(wm).reduceRegion(ee.Reducer.sum(),g,30,maxPixels=1e8,tileScale=4).getInfo()
  rainval=ee.Image.cat(rm).reduceRegion(ee.Reducer.mean(),g,5566,maxPixels=1e8,tileScale=4).getInfo()
  for month in range(1,13):
   t=f"m{month:02d}"
   if rainval.get(t) is None:raise RuntimeError(f"CHIRPS nulo {y}-{month}")
   months.append({"ano":y,"mes":month,"agua_mensal_ha":round(float(water.get(t) or 0),2),
      "chuva_mm":round(float(rainval[t]),2),"pastagem_anual_ha":yrs["pastagem_ha"]})
  if y%5==0 or y==2025:
   print("Ano",y,"pastagem",yrs["pastagem_ha"],"agua",yrs["agua_anual_ha"],flush=True)
   write("SERIE_ANUAL_HOTSPOT_1985_2025.csv",["ano","pastagem_ha","agua_anual_ha"],years)
   write("SERIE_MENSAL_HOTSPOT_1985_2025.csv",["ano","mes","agua_mensal_ha","chuva_mm","pastagem_anual_ha"],months)
  m["anos"].append(y)
 write("SERIE_ANUAL_HOTSPOT_1985_2025.csv",["ano","pastagem_ha","agua_anual_ha"],years)
 write("SERIE_MENSAL_HOTSPOT_1985_2025.csv",["ano","mes","agua_mensal_ha","chuva_mm","pastagem_anual_ha"],months)
 # Pixel de 30m: identificar primeiro ano com dois anos consecutivos de pastagem
 native=cover.select("classification_1985").remap([3,4,6,7,11,12,13,49,50],[1]*9,0).eq(1)
 past25=cover.select("classification_2025").eq(15)
 first=ee.Image.constant(0).toInt16()
 for y in range(1986,2025):
  consecutive=cover.select(f"classification_{y}").eq(15).And(cover.select(f"classification_{y+1}").eq(15))
  first=first.where(first.eq(0).And(consecutive),y)
 h=first.updateMask(native.And(past25)).rename("firstyear").reduceRegion(ee.Reducer.frequencyHistogram(),g,30,maxPixels=1e8,tileScale=4).getInfo()
 m["ano_primeira_pastagem_2anos_persistente"]=h
 m["dados"]={"anos":len(years),"meses":len(months),"past85":years[0],"past2005":years[20],"past2025":years[-1]}
 if len(years)!=41 or len(months)!=492:raise RuntimeError("Séries incompletas")
 m["status"]="concluído"
except Exception as e:
 m["status"]="erro_parcial";m["erros"].append(repr(e));traceback.print_exc()
finally:
 (R/"STATUS_SERIE_HOTSPOT.json").write_text(json.dumps(m,indent=2,ensure_ascii=False),encoding="utf-8")
 print(json.dumps({k:v for k,v in m.items() if k!="anos"},ensure_ascii=False)[:6000])
 if m["status"]!="concluído":raise SystemExit("Série hotspot não validada.")
