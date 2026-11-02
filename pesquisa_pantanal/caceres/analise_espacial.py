#!/usr/bin/env python3
"""Piloto hidrologico espacial de Caceres, MapBiomas Agua C5 + Cobertura C11 + CHIRPS v2.
NUNCA equiparar correlacao a causalidade. Dados resumidos a resolucao exploratoria.
"""
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
import os,json,csv,traceback,requests
import ee

ROOT=Path("pesquisa_pantanal/caceres/resultados")
ROOT.mkdir(parents=True,exist_ok=True)
META={"inicio":datetime.now(timezone.utc).isoformat(),"escala_m":{"agua":120,"pastagem":180,"chuva":5566,"mapa_visualizacao":"pixels MapBiomas reamostrados apenas na imagem PNG"},"erros":[],"etapas":[]}
def save():
 (ROOT/"relatorio_piloto_caceres.json").write_text(json.dumps(META,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
def log(msg):
 print(msg,flush=True);META["etapas"].append(msg);save()
def csvwrite(path,rows,cols):
 with (ROOT/path).open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
  for r in rows:w.writerow(r)
def geojson_write(name,geom,props):
 x=geom.simplify(550).getInfo()
 (ROOT/name).write_text(json.dumps({"type":"FeatureCollection","features":[{"type":"Feature","geometry":x,"properties":props}]},ensure_ascii=False),encoding="utf-8")
def area_ha(mask,region,scale):
 d=ee.Image.pixelArea().rename("area").updateMask(mask).reduceRegion(ee.Reducer.sum(),region,scale,maxPixels=1e9,tileScale=4)
 return ee.Number(ee.Algorithms.If(d.get("area"),d.get("area"),0)).divide(10000)
try:
 key=os.environ["EE_SERVICE_ACCOUNT_KEY"].strip();info=json.loads(key)
 ee.Initialize(ee.ServiceAccountCredentials(info["client_email"],key_data=key),project=os.environ.get("EE_PROJECT") or info["project_id"])
 B=ee.FeatureCollection("WWF/HydroSHEDS/v1/Basins/hybas_6")
 target=6060634290
 rect=ee.Geometry.Rectangle([-62,-19,-52,-12])
 bsmall=B.filterBounds(rect).select(["HYBAS_ID","NEXT_DOWN","UP_AREA","SUB_AREA"],retainGeometry=False)
 rec=[f["properties"] for f in bsmall.getInfo()["features"]]
 upstream={target};changed=True
 while changed:
  new={int(x["HYBAS_ID"]) for x in rec if int(x.get("NEXT_DOWN") or 0) in upstream}
  changed=bool(new-upstream)
  upstream|=new
 sum_area=sum(float(x["SUB_AREA"]) for x in rec if int(x["HYBAS_ID"]) in upstream)
 target_rec=next(x for x in rec if int(x["HYBAS_ID"])==target)
 META["hydrobasins"]={"local_id":target,"proximajusante_id":target_rec.get("NEXT_DOWN"),
 "local_km2":target_rec.get("SUB_AREA"),"montante_km2_catalogo":target_rec.get("UP_AREA"),
 "n_unidades_montante":len(upstream),"soma_areas_montante_km2":round(sum_area,1),
 "frac_cobertura_montante":round(sum_area/float(target_rec["UP_AREA"]),4)}
 if sum_area/float(target_rec["UP_AREA"])<0.90:
  raise RuntimeError("Coleta de sub-bacias incompleta; nao executar com geometrias parciais")
 local=ee.Feature(B.filter(ee.Filter.eq("HYBAS_ID",target)).first()).geometry()
 montante=B.filter(ee.Filter.inList("HYBAS_ID",list(upstream))).geometry()
 geob=json.loads(Path("pesquisa_pantanal/resultados/geometria_pantanal_chirps.geojson").read_text(encoding="utf-8"))
 bioma=ee.Geometry(geob["features"][0]["geometry"],proj="EPSG:4326",geodesic=False)
 planicie=local.intersection(bioma,ee.ErrorMargin(250))
 pl_area=planicie.area(250).divide(1e6).getInfo()
 META["area_estudo"]={"area_planicie_intersecao_km2":pl_area,
 "advertencia":"Recorte espacial = unidade hidrobasins local intersectada com limite de bioma Pantanal; nao e toda planicie de Caceres."}
 if pl_area<5:raise RuntimeError("Intersecao local com bioma Pantanal pequena demais: "+str(pl_area))
 geojson_write("caceres_local_hydrobasins.geojson",local,{"nome":"Unidade local hidrográfica Cáceres","HYBAS_ID":target,"fonte":"WWF HydroBASINS v1 nivel 6"})
 geojson_write("caceres_area_montante.geojson",montante,{"nome":"Área acumulada a montante no ponto de Cáceres","fonte":"HydroBASINS v1 nivel 6","subbasins":len(upstream)})
 geojson_write("caceres_planicie_recorte.geojson",planicie,{"nome":"Área local intersectada com bioma Pantanal","fontes":"HydroBASINS L6 + IBGE 2025"})
 (ROOT/"hidrobasins_montante_ids.json").write_text(json.dumps(sorted(upstream)),encoding="utf-8")
 log("Geometrias conferidas e salvas: "+json.dumps(META["hydrobasins"],ensure_ascii=False))
 W=ee.Image("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_annual_v4")
 L=ee.Image("projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3")
 C=ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select("precipitation")
 # Estruturacao server-side por lotes para reduzir ida e volta e cobrir periodo inteiro.
 def annual_feat(y):
  y=ee.Number(y).toInt()
  band=ee.String("classification_").cat(y.format("%d"))
  yy=ee.Image(W.select([band]))
  ll=ee.Image(L.select([band]))
  rain=C.filterDate(ee.Date.fromYMD(y,1,1),ee.Date.fromYMD(y.add(1),1,1)).sum()
  out=rain.reduceRegion(ee.Reducer.mean(),montante,5566,maxPixels=1e9,tileScale=4)
  return ee.Feature(None,{
   "ano":y,
   "agua_local_planicie_ha":area_ha(yy.eq(1),planicie,120),
   "pastagem_plantada_montante_ha":area_ha(ll.eq(15),montante,180),
   "pastagem_plantada_local_ha":area_ha(ll.eq(15),local,180),
   "chuva_chirps_montante_mm":out.get("precipitation")
  })
 annual=[]
 for ano in range(1985,2026):
  f=annual_feat(ee.Number(ano)).getInfo()
  p=f["properties"]
  annual.append({k:round(v,3) if isinstance(v,float) else v for k,v in p.items()})
  if ano%5==0 or ano==2025:
   csvwrite("serie_anual_caceres_1985_2025.csv",annual,["ano","agua_local_planicie_ha","pastagem_plantada_montante_ha","pastagem_plantada_local_ha","chuva_chirps_montante_mm"])
   log("Serie anual ate "+str(ano)+": "+str(len(annual))+" anos")
 csvwrite("serie_anual_caceres_1985_2025.csv",annual,["ano","agua_local_planicie_ha","pastagem_plantada_montante_ha","pastagem_plantada_local_ha","chuva_chirps_montante_mm"])
 META["serie_anual_linhas"]=len(annual)
 # TESTE MENSAL: 4 anos, depois sera possivel expandir mantendo mesmo metodo.
 M=ee.ImageCollection("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_monthly_v4")
 YEARS=[1988,2018,2024,2025]
 def monthly_feat(im):
  im=ee.Image(im)
  idx=ee.String(im.get("system:index"))
  ano=ee.Number.parse(idx.slice(14,18))
  mes=ee.Number.parse(idx.slice(19,21))
  a=area_ha(im.eq(mes),planicie,120)
  return ee.Feature(None,{"ano":ano,"mes":mes,"agua_mensal_local_planicie_ha":a})
 monthly=[]
 for ano in YEARS:
  for mes in range(1,13):
   idx="water_monthly_%d_%02d"%(ano,mes)
   im=ee.Image(M.filter(ee.Filter.eq("system:index",idx)).first())
   feat=monthly_feat(im).getInfo()
   p=feat["properties"]
   monthly.append({"ano":int(p["ano"]),"mes":int(p["mes"]),
       "agua_mensal_local_planicie_ha":round(float(p["agua_mensal_local_planicie_ha"]),3)})
  csvwrite("pulso_mensal_caceres_anos_referencia.csv",monthly,["ano","mes","agua_mensal_local_planicie_ha"])
  log("Serie mensal concluida: "+str(ano)+", "+str(len(monthly))+" meses")
 META["serie_mensal_linhas"]=len(monthly)
 # Gerar mapas de classes REAIS, recortadas; o visual em PNG usa reducao de resolucao.
 renderbox=local.buffer(4000).bounds(500)
 bbox=renderbox.getInfo()
 META["mapas_georreferenciados"]="As imagens PNG incluem classificacao espacial MapBiomas; a geometria geojson define recorte e posicao. PNG nao e raster analitico."
 base=ee.Image.constant(0).visualize(min=0,max=1,palette=["#ecf0ee"]).clip(local)
 for ano in [1988,2018,2024,2025]:
  water=ee.Image(W.select("classification_"+str(ano))).eq(1).selfMask().visualize(palette=["#1877ae"]).clip(local)
  pasture=ee.Image(L.select("classification_"+str(ano))).eq(15).selfMask().visualize(palette=["#d6b57d"]).clip(local)
  composite=ee.ImageCollection([base,pasture,water]).mosaic().clip(local)
  url=composite.getThumbURL({"region":bbox,"dimensions":950,"format":"png"})
  r=requests.get(url,timeout=150);r.raise_for_status()
  from PIL import Image
  import io
  im=Image.open(io.BytesIO(r.content));im.verify()
  (ROOT/("mapbiomas_agua_pastagem_%d_caceres.png"%ano)).write_bytes(r.content)
  META.setdefault("mapas",[]).append({"ano":ano,"arquivo":"mapbiomas_agua_pastagem_%d_caceres.png"%ano,"bytes":len(r.content)})
  log("Mapa raster oficial gerado para "+str(ano))
 # Mapas de DURACAO MENSAL (numero de meses com agua no ano)
 for ano in [1988,2024,2025]:
  imgs=[]
  for m in range(1,13):
   im=ee.Image(M.filter(ee.Filter.eq("system:index","water_monthly_%d_%02d"%(ano,m))).first())
   imgs.append(im.eq(m).unmask(0).rename("mes_com_agua"))
  hydro=ee.ImageCollection.fromImages(imgs).sum().clip(planicie)
  hist=hydro.reduceRegion(ee.Reducer.frequencyHistogram(),planicie,120,maxPixels=1e9,tileScale=4).getInfo()
  META.setdefault("histograma_duracao_meses_agua_escala120m",{})[str(ano)]=hist
  rgb=hydro.visualize(min=0,max=12,palette=["#edf2ed","#c6e9e0","#83c8d4","#3795c2","#105c96","#12385f"]).clip(local)
  url=rgb.getThumbURL({"region":bbox,"dimensions":950,"format":"png"})
  r=requests.get(url,timeout=150);r.raise_for_status()
  (ROOT/("meses_inundados_%d_caceres.png"%ano)).write_bytes(r.content)
  log("Mapa de duracao mensal gerado: "+str(ano))
 META["status"]="extraido"
except Exception as e:
 META["status"]="erro_parcial"
 META["erros"].append(repr(e))
 traceback.print_exc()
finally:
 save()
 print(json.dumps({k:v for k,v in META.items() if k not in ["etapas"]},ensure_ascii=False,indent=2,default=str))
