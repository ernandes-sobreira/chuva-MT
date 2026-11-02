#!/usr/bin/env python3
"""492 meses de agua superficial no Pantanal de Caceres e chuva na area montante.
Extracao OBSERVADA Google Earth Engine; recorte IBGE Pantanal x HydroBASINS nivel 6.
Resumidos 120m, e nao pixel nativo 30m. Sem interpolacao de valores nulos.
"""
import os,json,datetime as dt,csv,traceback
from pathlib import Path
import ee
ROOT=Path("pesquisa_pantanal/hidrologia/resultados")
ROOT.mkdir(parents=True,exist_ok=True)
C=Path("pesquisa_pantanal/caceres/resultados")
OUT=ROOT/"agua_chuva_mensal_caceres_1985_2025.csv"
META={"date_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"fonte_agua":"projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_monthly_v4",
 "fonte_chuva":"UCSB-CHG/CHIRPS/DAILY","fonte_recortes":"HydroBASINS nivel 6 / IBGE biomas 2025",
 "escala_agua_m":120,"escala_chuva_m":5566,
 "definicao_agua":"agua superficial detectada no mes, nao volume nem toda inundacao sazonal",
 "erros":[],"anos_extraidos":[]}
fields=["ano","mes","data","agua_superficial_local_planicie_ha","chuva_montante_mm"]
def save_csv(records):
 with OUT.open("w",encoding="utf-8-sig",newline="") as f:
  wr=csv.DictWriter(f,fieldnames=fields);wr.writeheader()
  wr.writerows([records[k] for k in sorted(records)])
def save_meta():
 (ROOT/"relatorio_agua_chuva_mensal.json").write_text(json.dumps(META,ensure_ascii=False,indent=2),encoding="utf-8")
try:
 key=os.environ["EE_SERVICE_ACCOUNT_KEY"].strip(); info=json.loads(key)
 ee.Initialize(ee.ServiceAccountCredentials(info["client_email"],key_data=key),project=os.environ.get("EE_PROJECT") or info["project_id"])
 localjson=json.loads((C/"caceres_planicie_recorte.geojson").read_text(encoding="utf-8"))
 upjson=json.loads((C/"caceres_area_montante.geojson").read_text(encoding="utf-8"))
 flood=ee.Geometry(localjson["features"][0]["geometry"],proj="EPSG:4326",geodesic=False)
 upstream=ee.Geometry(upjson["features"][0]["geometry"],proj="EPSG:4326",geodesic=False)
 water=ee.ImageCollection(META["fonte_agua"])
 rain=ee.ImageCollection(META["fonte_chuva"]).select("precipitation")
 output={}
 if OUT.exists():
  with OUT.open(encoding="utf-8-sig",newline="") as f:
   for r in csv.DictReader(f):
    if r.get("data") and r.get("agua_superficial_local_planicie_ha") and r.get("chuva_montante_mm"):
     output[r["data"]]=r
 for y in range(1985,2026):
  if all(f"{y}-{m:02d}" in output for m in range(1,13)):
   print("Ja completo:",y,flush=True);META["anos_extraidos"].append(y);continue
  masks=[];rainbands=[]
  for m in range(1,13):
   yearnext=y+(m==12)
   monthnext=(m%12)+1
   idx="water_monthly_%d_%02d"%(y,m)
   im=ee.Image(water.filter(ee.Filter.eq("system:index",idx)).first())
   pix=im.select("water_monthly").eq(m)
   masks.append(ee.Image.pixelArea().updateMask(pix).divide(10000).rename(f"m{m:02d}"))
   rainfall=rain.filterDate(f"{y}-{m:02d}-01",f"{yearnext}-{monthnext:02d}-01").sum().rename(f"m{m:02d}")
   rainbands.append(rainfall)
  areas=ee.Image.cat(masks).reduceRegion(reducer=ee.Reducer.sum(),geometry=flood,scale=120,maxPixels=1e9,tileScale=4).getInfo()
  rains=ee.Image.cat(rainbands).reduceRegion(reducer=ee.Reducer.mean(),geometry=upstream,scale=5566,maxPixels=1e9,tileScale=4).getInfo()
  if len(areas)!=12 or len(rains)!=12:raise RuntimeError("12 bandas mensais esperadas "+str(y)+" "+repr(areas)+repr(rains))
  for m in range(1,13):
   label=f"m{m:02d}"
   area,rain_mm=areas.get(label),rains.get(label)
   if area is None or rain_mm is None:raise RuntimeError("Imagem mensal nula "+str(y)+"/"+str(m))
   d=f"{y}-{m:02d}"
   output[d]={"ano":y,"mes":m,"data":d,"agua_superficial_local_planicie_ha":round(float(area),3),"chuva_montante_mm":round(float(rain_mm),3)}
  save_csv(output)
  META["anos_extraidos"].append(y)
  print("ANO",y,"n=",len(output),"agua_m01_ha",output[f"{y}-01"]["agua_superficial_local_planicie_ha"],"chuva_m01_mm",output[f"{y}-01"]["chuva_montante_mm"],flush=True)
  save_meta()
 META["status"]="concluido" if len(output)==492 else "incompleto"
 META["total_meses"]=len(output)
 # Verificacao com piloto de 48 meses anterior, tolerancia 2% devido geometria identica e escala igual.
 previous=C/"pulso_mensal_caceres_anos_referencia.csv"
 audit=[]
 with previous.open(encoding="utf-8-sig",newline="") as f:
  for row in csv.DictReader(f):
   d=f'{row["ano"]}-{int(row["mes"]):02d}'
   if d not in output:continue
   old=float(row["agua_mensal_local_planicie_ha"]);new=float(output[d]["agua_superficial_local_planicie_ha"])
   diff=abs(new-old)/max(old,1)
   audit.append({"mes":d,"piloto_ha":old,"atual_ha":new,"diferenca_pct":round(100*diff,3)})
 META["comparacao_piloto_48_meses"]={"max_diferenca_pct":max(x["diferenca_pct"] for x in audit),"n":len(audit)}
 if META["comparacao_piloto_48_meses"]["max_diferenca_pct"]>5:raise RuntimeError("Diferença de pixels maior que 5% versus piloto; ver auditoria")
 (ROOT/"validacao_mapbiomas_meses.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
except Exception as e:
 META["status"]="falha_parcial";META["erros"].append(repr(e));traceback.print_exc()
finally:
 save_meta()
 print(json.dumps({k:v for k,v in META.items() if k not in ["anos_extraidos"]},ensure_ascii=False,indent=2))
 if META.get("status")!="concluido":raise SystemExit("Extracao nao concluida; preservando resultados parciais.")
