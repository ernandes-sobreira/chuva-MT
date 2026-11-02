#!/usr/bin/env python3
"""Triagem satelital no entorno da Fazenda Ressaca, Cáceres/MT.

A localização é CENTROIDE CADASTRAL publicado, sem contorno SIGEF validado.
A grade de 2x2 km é espacialmente georreferenciada mas NÃO define o perímetro da fazenda.
Seleciona hotspot apenas pela conversão nativo->pastagem, SEM olhar o resultado de água
para evitar seleção a posteriori. MapBiomas Cobertura C11 30 m, anos 1985–2025.
"""
from pathlib import Path
import os,json,csv,traceback,math,datetime as dt
from pyproj import Transformer,Geod
import ee
P=Path("pesquisa_pantanal/fazenda_ressaca");P.mkdir(exist_ok=True,parents=True)
OUT=P/"resultados";OUT.mkdir(exist_ok=True)
REF="https://cafir.com.br/imovel/1741279-0/"
CENTROID=(-57.72622,-16.27013)
geod=Geod(ellps="GRS80")
to_utm=Transformer.from_crs("EPSG:4326","EPSG:32721",always_xy=True)
from_utm=Transformer.from_crs("EPSG:32721","EPSG:4326",always_xy=True)
CXX,CYY=to_utm.transform(*CENTROID)
CELL=2000
N=12
F={}
G={}
grids=[]
for i in range(N):
 for j in range(N):
  x0=CXX-12_000+i*CELL;x1=x0+CELL
  y0=CYY-12_000+j*CELL;y1=y0+CELL
  corners=[from_utm.transform(x0,y0),from_utm.transform(x1,y0),from_utm.transform(x1,y1),from_utm.transform(x0,y1)]
  corners=[[round(x,7),round(y,7)] for x,y in corners];corners.append(corners[0])
  g={"type":"Polygon","coordinates":[corners]}
  gid=f"C{i:02d}_{j:02d}"
  area=abs(geod.geometry_area_perimeter(g)[0])/10000 if False else 400.0
  grids.append({"type":"Feature","geometry":g,"properties":{"id":gid,"i":i,"j":j,"area_utm_ha":400,
   "recorte":"Célula amostral de 2 km, NÃO perímetro de imóvel"}})
  G[gid]=g
meta={"status":"iniciado","centroide_CAFIR_lonlat":CENTROID,"centroide_fonte":REF,"bioma":None,
 "metodo":"grade de 144 células de 2x2km, 24x24 km ao redor do centroide. Seleção por novos pixels de pastagem sem olhar água.",
 "grid":f"{N}x{N}","células":len(grids),"area_ha_total":N*N*400,
 "classes_nativas_1985":[3,4,6,7,11,12,13,49,50],"classe_pastagem":15,
 "alerta":"Não confundir matriz de células com Fazenda Ressaca. O SIGEF oficial recente não foi confirmado nessa execução.",
 "fontes":["MapBiomas LULC Collection 11 30m","MapBiomas Water Collection 5 30m","CAFIR localização cadastral"],
 "erros":[]}
try:
 k=os.environ["EE_SERVICE_ACCOUNT_KEY"].strip();auth=json.loads(k)
 ee.Initialize(ee.ServiceAccountCredentials(auth["client_email"],key_data=k),project=os.environ.get("EE_PROJECT") or auth["project_id"])
 fc=ee.FeatureCollection([ee.Feature(ee.Geometry(f["geometry"],proj="EPSG:4326",geodesic=False),f["properties"]) for f in grids])
 lulc=ee.Image("projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3")
 water=ee.Image("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_annual_v4")
 nat85=ee.Image(lulc.select("classification_1985")).remap(meta["classes_nativas_1985"],[1]*len(meta["classes_nativas_1985"]),0)
 p85=lulc.select("classification_1985").eq(15)
 p25=lulc.select("classification_2025").eq(15)
 bands=[]
 for year in [1985,1995,2005,2015,2025]:
  bands.append(lulc.select(f"classification_{year}").eq(15).unmask(0).rename(f"past{year}"))
 bands+=[
  p25.And(p85.Not()).unmask(0).rename("newpast25"),
  p25.And(nat85).unmask(0).rename("nat_to_past25"),
  p85.And(p25.Not()).unmask(0).rename("lostpast25"),
  water.select("classification_1985").eq(1).unmask(0).rename("water1985"),
  water.select("classification_2025").eq(1).unmask(0).rename("water2025")]
 img=ee.Image.cat(bands)
 reduced=img.reduceRegions(collection=fc,reducer=ee.Reducer.mean(),scale=30,tileScale=4).getInfo()["features"]
 rows=[]
 for item in reduced:
  d=item["properties"]
  row={"id":d["id"],"i":int(d["i"]),"j":int(d["j"]),"area_ha":400,
       "centro_lonlat":[round(sum(x[0] for x in G[d["id"]]["coordinates"][0][:4])/4,6),
                       round(sum(x[1] for x in G[d["id"]]["coordinates"][0][:4])/4,6)]}
  for yr in [1985,1995,2005,2015,2025]:
   row[f"pastagem_ha_{yr}"]=round(400*float(d.get(f"past{yr}") or 0),2)
  for name in ["newpast25","nat_to_past25","lostpast25","water1985","water2025"]:
   row[name+"_ha"]=round(400*float(d.get(name) or 0),2)
  row["saldo_pastagem_1985_2025_ha"]=round(row["pastagem_ha_2025"]-row["pastagem_ha_1985"],2)
  rows.append(row)
 rows.sort(key=lambda r:(-r["nat_to_past25_ha"],-r["saldo_pastagem_1985_2025_ha"]))
 assert len(rows)==144
 # Select densest conversion cell among those within 8km of centroid of the published property,
 # no matching with property ownership; cells outside the true property are possible.
 candidates=[r for r in rows if math.hypot(r["i"]-5.5,r["j"]-5.5)<=4.2]
 if not candidates:raise RuntimeError("Sem células próximas ao centroide")
 top=candidates[0];ci,cj=top["i"],top["j"]
 cluster=[r for r in rows if abs(r["i"]-ci)<=1 and abs(r["j"]-cj)<=1]
 group_ids={r["id"] for r in cluster}
 assert top["id"] in group_ids
 # Source geometry for focus cluster union of 3x3 grid cells and individual hotspot cell
 focus=[f for f in grids if f["properties"]["id"] in group_ids]
 focus_geo={"type":"FeatureCollection","features":focus}
 (OUT/"GRADE_ENTORNO_RESSACA_2KM.geojson").write_text(json.dumps({"type":"FeatureCollection","features":grids},ensure_ascii=False),encoding="utf-8")
 (OUT/"HOTSPOT_CELULAS_RESSACA.geojson").write_text(json.dumps(focus_geo,ensure_ascii=False),encoding="utf-8")
 with (OUT/"RANKING_CELULAS_RESSACA.csv").open("w",newline="",encoding="utf-8-sig") as f:
  cols=["id","i","j","area_ha","saldo_pastagem_1985_2025_ha","nat_to_past25_ha","newpast25_ha","lostpast25_ha",
  "pastagem_ha_1985","pastagem_ha_1995","pastagem_ha_2005","pastagem_ha_2015","pastagem_ha_2025",
  "water1985_ha","water2025_ha","centro_lonlat"]
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
  for r in rows:w.writerow({**r,"centro_lonlat":str(r["centro_lonlat"])})
 meta["selecionada"]=top
 meta["hotspot_3x3"]={"numero_celulas":len(cluster),"ids":sorted(group_ids),
   "area_aproximada_ha":len(cluster)*400,
   "pastagem85_ha":round(sum(r["pastagem_ha_1985"] for r in cluster),2),
   "pastagem25_ha":round(sum(r["pastagem_ha_2025"] for r in cluster),2),
   "nat_to_past_ha":round(sum(r["nat_to_past25_ha"] for r in cluster),2),
   "water85_ha":round(sum(r["water1985_ha"] for r in cluster),2),
   "water25_ha":round(sum(r["water2025_ha"] for r in cluster),2)}
 meta["total_grade"]={"pastagem85_ha":round(sum(r["pastagem_ha_1985"] for r in rows),2),
 "pastagem25_ha":round(sum(r["pastagem_ha_2025"] for r in rows),2),
 "nat_to_past_ha":round(sum(r["nat_to_past25_ha"] for r in rows),2)}
 meta["status"]="concluido"
except Exception as e:
 meta["status"]="falha";meta["erros"].append(repr(e));traceback.print_exc()
finally:
 (OUT/"RELATORIO_TRIAGEM_RESSACA.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(meta,ensure_ascii=False,indent=2)[:13000],flush=True)
 if meta["status"]!="concluido":raise SystemExit("Triagem não passou. Não atribuir transformações a uma fazenda sem recorte verificado.")
