#!/usr/bin/env python3
"""Prancha 1985/2005/2025 com PIXELS reais MapBiomas C11/C5
e grade de 2km baseada no centro cadastral do entorno da Fazenda Ressaca.
Não representa limites patrimoniais.
"""
import os,json,io,math
from pathlib import Path
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch,Rectangle
from shapely.geometry import shape
from pyproj import Transformer
import ee
P=Path("pesquisa_pantanal/fazenda_ressaca/resultados")
tri=json.loads((P/"RELATORIO_TRIAGEM_RESSACA.json").read_text(encoding="utf-8"))
assert tri["status"]=="concluido"
grid=json.loads((P/"GRADE_ENTORNO_RESSACA_2KM.geojson").read_text(encoding="utf-8"))["features"]
hot=json.loads((P/"HOTSPOT_CELULAS_RESSACA.geojson").read_text(encoding="utf-8"))["features"]
key=os.environ["EE_SERVICE_ACCOUNT_KEY"];d=json.loads(key)
ee.Initialize(ee.ServiceAccountCredentials(d["client_email"],key_data=key),project=os.environ.get("EE_PROJECT") or d["project_id"])
trans=Transformer.from_crs("EPSG:4326","EPSG:32721",always_xy=True)
cx,cy=trans.transform(-57.72622,-16.27013)
size=700;step=24000/size
gridpixels={"dimensions":{"width":size,"height":size},
 "affineTransform":{"scaleX":step,"shearX":0,"translateX":cx-12000,
                   "scaleY":-step,"shearY":0,"translateY":cy+12000},
 "crsCode":"EPSG:32721"}
cover=ee.Image("projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3")
water=ee.Image("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_annual_v4")
imgs=[]
for y in [1985,2005,2025]:
 c=cover.select(f"classification_{y}")
 w=water.select(f"classification_{y}").eq(1)
 # código 0: uso não especificado; 1: natural florestal;
 # 2: savana/campo nativo; 3: pastagem plantada; 4: água detectada.
 view=ee.Image.constant(0).where(c.eq(3).Or(c.eq(6)),1)
 view=view.where(c.eq(4).Or(c.eq(7)).Or(c.eq(11)).Or(c.eq(12)).Or(c.eq(13)),2)
 view=view.where(c.eq(15),3).where(w,4)
 rgb=view.visualize(min=0,max=4,palette=["#E7E6E3","#39775E","#8AB69D","#D4A76F","#237AAE"])
 b=ee.data.computePixels({"expression":rgb,"fileFormat":"PNG","grid":gridpixels})
 im=Image.open(io.BytesIO(b)).convert("RGB")
 P.joinpath(f"RESSACA_USO_SOLO_{y}.png").write_bytes(b)
 imgs.append(im)
def xy(pt):
 return trans.transform(*pt)
fig,ax=plt.subplots(1,3,figsize=(18,7.4),sharex=True,sharey=True)
fig.suptitle("Entorno da Fazenda Ressaca | Transformação da paisagem detectada por satélite",
 fontsize=18,fontweight="bold",y=.99)
extent=(cx-12000,cx+12000,cy-12000,cy+12000)
for a,im,y in zip(ax,imgs,[1985,2005,2025]):
 a.imshow(im,extent=extent,origin="upper",interpolation="nearest")
 for f in grid:
  coords=f["geometry"]["coordinates"][0]
  xx=[xy(p)[0] for p in coords]; yy=[xy(p)[1] for p in coords]
  a.plot(xx,yy,color="#ffffff",lw=.34,alpha=.22,zorder=4)
 for f in hot:
  coords=f["geometry"]["coordinates"][0]
  xx=[xy(p)[0] for p in coords]; yy=[xy(p)[1] for p in coords]
  a.plot(xx,yy,color="#EC5E45",lw=1.3,zorder=8)
 a.scatter([cx],[cy],marker="+",s=130,lw=2.3,c="#151C22",zorder=10)
 a.set_title(str(y),fontsize=17,fontweight="bold",pad=12)
 a.set_xlim(extent[:2]);a.set_ylim(extent[2:]);a.set_aspect("equal")
 a.set_xticks([]);a.set_yticks([])
 for s in a.spines.values():s.set_visible(False)
 a.text(.02,.98,"24 × 24 km",transform=a.transAxes,va="top",fontsize=10,
 bbox=dict(fc="white",ec="none",alpha=.84))
legend=[Patch(color="#39775E",label="Formação florestal"),
 Patch(color="#8AB69D",label="Campo / savana / área úmida natural"),
 Patch(color="#D4A76F",label="Pastagem plantada"),
 Patch(color="#237AAE",label="Água superficial"),
 Patch(facecolor="none",edgecolor="#EC5E45",linewidth=2,label="Células selecionadas para piloto")]
fig.legend(handles=legend,loc="lower center",bbox_to_anchor=(.5,.05),ncol=3,frameon=False,fontsize=11)
fig.text(.047,.007,
 "Centro cadastral do imóvel (cruz), NÃO perímetro da fazenda. Células do hotspot selecionadas por conversão 1985–2025, sem olhar água.",
 fontsize=10,color="#52666B")
fig.text(.047,.029,"Fontes: MapBiomas C11/C5, CAFIR centro cadastral publicado. Raster visual reamostrado; valores calculados a 30m.",fontsize=9,color="#52666B")
out=P/"FIGURA_MAPA_RESSACA_1985_2005_2025.png"
fig.savefig(out,dpi=190,bbox_inches="tight",facecolor="white")
print(json.dumps({"out":str(out),"bytes":out.stat().st_size,"mapas_anos":[1985,2005,2025],"nota":"Entorno, não Fazenda Ressaca inteira"},ensure_ascii=False))
