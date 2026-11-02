#!/usr/bin/env python3
"""Ampliar recorte com a RH-Paraguai OFICIAL DA ANA, mantendo bacia Cáceres separada.
A RH Paraguai é área brasileira de planejamento hidrológico, não toda BAP transfronteiriça.
"""
from pathlib import Path
import requests,json,traceback,io,zipfile,shapefile
from shapely.geometry import shape,mapping,box
from shapely.ops import unary_union
from pyproj import Geod
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

D=Path("pesquisa_pantanal/recorte_cientifico/resultados")
F=Path("pesquisa_pantanal/cartografia");F.mkdir(parents=True,exist_ok=True)
URLS=[
 "https://portal1.snirh.gov.br/server/rest/services/Regi%C3%B5es_Hidrogr%C3%A1ficas/MapServer/0/query",
 "https://www.snirh.gov.br/arcgis/rest/services/SGI/Regioes_Hidrograficas/MapServer/0/query"
]
IBGE="https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/biomas/vetores/2025_Biomas-e-Sistema-Costeiro-Marinho-do-Brasil-1-250000_shp.zip"
report={"fonte_regiao":"ANA/SNIRH Região Hidrográfica do Paraguai (Brasil)","erros":[],"todas_tentativas":[]}
def fc(g,props):return {"type":"FeatureCollection","features":[{"type":"Feature","geometry":mapping(g),"properties":props}]}
def shapes(g):
 if g.is_empty:return
 if g.geom_type=="Polygon":yield g
 elif hasattr(g,"geoms"):
  for x in g.geoms: yield from shapes(x)
def filled(ax,g,color,alpha=1):
 for p in shapes(g):
  x,y=p.exterior.xy;ax.fill(x,y,color=color,lw=0,alpha=alpha,zorder=2)
def outline(ax,g,color,width=2,style="-"):
 for p in shapes(g):
  x,y=p.exterior.xy;ax.plot(x,y,color=color,lw=width,ls=style,zorder=8)
try:
 candidate=[]
 for url in URLS:
  for query in ["RHI_NM='PARAGUAI'","RHI_NM LIKE '%PARAGUAI%'"]:
   try:
    r=requests.get(url,params={"where":query,"outFields":"*","returnGeometry":"true","outSR":"4674","f":"geojson"},timeout=(22,65))
    r.raise_for_status()
    o=r.json();features=o.get("features",[])
    report["todas_tentativas"].append({"url":r.url,"n":len(features),"bytes":len(r.content)})
    if len(features)==1 and features[0].get("geometry"):
     candidate=[url,features[0]];break
   except Exception as e:report["todas_tentativas"].append({"url":url,"query":query,"erro":repr(e)})
  if candidate:break
 if not candidate:raise RuntimeError("GeoJSON oficial ANA não disponível - não criar poligono estimado")
 url,feat=candidate
 g=shape(feat["geometry"])
 if not g.is_valid:g=g.buffer(0)
 geod=Geod(ellps="GRS80")
 area=abs(geod.geometry_area_perimeter(g)[0])/1e6
 report["area_RH_brasileira_km2"]=round(area,1)
 report["atributos_ANA"]={k:v for k,v in feat.get("properties",{}).items() if v is not None and isinstance(v,(str,float,int))}
 report["url_confirmada"]=url
 if not 325000<area<395000:raise RuntimeError("Area inesperada ANA RH Paraguai: "+str(area))
 (D/"RH_PARAGUAI_Brasil_ANA.geojson").write_text(json.dumps(fc(g.simplify(.003,preserve_topology=True),{"nome":"Região Hidrográfica Paraguai - área brasileira","fonte":url,"area_km2":area}),ensure_ascii=False),encoding="utf-8")
 # Bioma Pantanal oficial IBGE para indicar zona de inundação; não equivale à planície geomorf.
 z=requests.get(IBGE,timeout=(30,150));z.raise_for_status()
 zipped=zipfile.ZipFile(io.BytesIO(z.content))
 shp=next(x for x in zipped.namelist() if x.lower().endswith(".shp"));prefix=shp[:-4]
 dbf=next(x for x in zipped.namelist() if x.lower()==(prefix+".dbf").lower())
 shx=next(x for x in zipped.namelist() if x.lower()==(prefix+".shx").lower())
 cpg=next((x for x in zipped.namelist() if x.lower()==(prefix+".cpg").lower()),None)
 enc=zipped.read(cpg).decode(errors="replace").strip() if cpg else "latin1"
 reader=shapefile.Reader(shp=io.BytesIO(zipped.read(shp)),dbf=io.BytesIO(zipped.read(dbf)),shx=io.BytesIO(zipped.read(shx)),encoding=enc)
 fields=[x[0] for x in reader.fields[1:]]
 pant=[]
 for record in reader.iterShapeRecords():
  p=dict(zip(fields,record.record))
  if "Pantanal" in p.values():pant.append(shape(record.shape.__geo_interface__))
 if not pant:raise RuntimeError("IBGE: Bioma Pantanal não encontrado")
 gp=unary_union(pant).intersection(g)
 if gp.is_empty:raise RuntimeError("RH Paraguai não intersecta bioma Pantanal")
 pg=abs(geod.geometry_area_perimeter(gp)[0])/1e6
 report["area_bioma_Pantanal_dentro_RH_km2"]=round(pg,1)
 (D/"Pantanal_bioma_dentro_RH_Paraguai_IBGE.geojson").write_text(json.dumps(fc(gp.simplify(.003,preserve_topology=True),{"tipo":"bioma Pantanal × RH Paraguai (ANA)","area_km2":pg}),ensure_ascii=False),encoding="utf-8")
 catch=shape(json.loads((D/"BACIA_VERIFICADA_UPSTREAM_ANA_66070004.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
 cpt=(-57.687777777777775,-16.063055555555557)
 report["pct_RH_upstream_Caceres"]=round(100*32752.7/area,2)
 if catch.intersection(g).area/catch.area<.93:report["alerta"]="Bacia HydroBASINS não coincide plenamente com recorte RH ANA; requer correção e análise."
 # Figura - dois recortes diferentes mas conectados
 plt.rcParams.update({"font.family":"DejaVu Sans","figure.facecolor":"white","axes.spines.top":False,"axes.spines.right":False})
 fig,axs=plt.subplots(1,2,figsize=(16,9.3),layout="constrained")
 def setup(ax):
  ax.set_aspect(1/0.96,adjustable="box");ax.grid(alpha=.15)
  ax.tick_params(labelsize=8,colors="#6B828B")
  ax.set_xlabel("Longitude",fontsize=9);ax.set_ylabel("Latitude",fontsize=9)
  ax.set_facecolor("#F9FBFA")
 # A full RH
 ax=axs[0];setup(ax)
 filled(ax,g,"#E5E7D5")
 filled(ax,gp,"#82C7CC")
 filled(ax,catch.intersection(g),"#A4B0D8",alpha=.95)
 outline(ax,g,"#556758",2)
 outline(ax,gp,"#218D9D",1.4)
 outline(ax,catch,"#244E87",2.6)
 ax.scatter(*cpt,s=140,color="#C63A4B",edgecolors="white",lw=2,zorder=20)
 ax.annotate("Cáceres",cpt,xytext=(8,8),textcoords="offset points",fontsize=12,fontweight="bold")
 ax.set_xlim(-60.4,-52.5);ax.set_ylim(-23.2,-12.3)
 ax.set_title("A   Toda a Região Hidrográfica do Paraguai (Brasil)",fontweight="bold",fontsize=15,loc="left")
 # B zoom upstream gauge
 ax=axs[1];setup(ax)
 filled(ax,g,"#EDF0E9")
 filled(ax,gp,"#A3D7DD")
 filled(ax,catch,"#A4B0D8")
 outline(ax,catch,"#244E87",3)
 outline(ax,gp,"#218D9D",1.2)
 ax.scatter(*cpt,s=140,color="#C63A4B",edgecolors="white",lw=2,zorder=20)
 ax.annotate("Estação ANA 66070004",cpt,xytext=(10,-25),textcoords="offset points",fontsize=11,fontweight="bold")
 ax.set_xlim(-59.4,-55.9);ax.set_ylim(-16.8,-13.6)
 ax.set_title("B   Só a drenagem até a estação de Cáceres",fontweight="bold",fontsize=15,loc="left")
 fig.suptitle("PANTANAL E BACIA DO ALTO PARAGUAI | DOIS RECORTES, DUAS PERGUNTAS",fontsize=20,fontweight="bold")
 fig.legend(handles=[Patch(color="#E5E7D5",label="RH Paraguai (ANA)"),Patch(color="#82C7CC",label="Bioma Pantanal (IBGE)"),
  Patch(color="#A4B0D8",label="Bacia contribuinte em Cáceres (HydroBASINS L10)"),
  Line2D([0],[0],marker="o",ms=9,ls="None",color="#C63A4B",label="Estação ANA 66070004")],frameon=False,loc="lower center",ncol=4,bbox_to_anchor=(.5,-.012),fontsize=10)
 fig.text(.05,.01,"RH Paraguai = área brasileira de planejamento da ANA, não toda a BAP transfronteiriça. Bioma Pantanal ≠ toda planície geomorfológica.",
          fontsize=9,color="#50616A")
 fig.savefig(Path("pesquisa_pantanal/cartografia")/"MAPA_BAP_ANA_VS_BACIA_CACERES.png",dpi=180,bbox_inches="tight",facecolor="white")
 plt.close(fig)
 report["status"]="concluido"
except Exception as e:
 report["status"]="indisponivel";report["erros"].append(repr(e));traceback.print_exc()
finally:
 (D/"STATUS_RH_PARAGUAI_ANA.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False,indent=2)[:11000])
