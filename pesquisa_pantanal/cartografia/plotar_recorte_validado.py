#!/usr/bin/env python3
"""Mapa auditável do verdadeiro recorte exutório ANA 66070004, não do município.
Fonte biométrica: IBGE 2025; HydroBASINS L10, rio Paraguai, Cáceres IBGE.
"""
from pathlib import Path
import json, math, textwrap
from shapely.geometry import shape,Point
from shapely.ops import unary_union
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe

D=Path("pesquisa_pantanal/recorte_cientifico/resultados")
F=Path("pesquisa_pantanal/cartografia")
F.mkdir(exist_ok=True,parents=True)
meta=json.loads((D/"VALIDACAO_RECORTE_CACERES.json").read_text(encoding="utf-8"))
if meta.get("status")!="concluido":raise RuntimeError("Bacia ainda nao passou na validacao!")
bacia=shape(json.loads((D/"BACIA_VERIFICADA_UPSTREAM_ANA_66070004.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
old=shape(json.loads(Path("pesquisa_pantanal/caceres/resultados/caceres_area_montante.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
mun=shape(json.loads((F/"municipio_caceres_ibge.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
biomas=json.loads((D/"BIOMAS_IBGE_2025_CONTEXTO_CACERES.geojson").read_text(encoding="utf-8"))["features"]
station=meta["estacao"];pt=Point(float(station["lon"]),float(station["lat"]))
if not bacia.buffer(0.025).contains(pt):raise RuntimeError("Estação fora da bacia calculada")
COLOR={"Amazônia":"#74AE88","Cerrado":"#D8B777","Pantanal":"#81C6CF","Mata Atlântica":"#B6A6D7"}
TEXT="#1C3440";GRAY="#637782"
plt.rcParams.update({"font.family":"DejaVu Sans","figure.facecolor":"white","savefig.facecolor":"white",
"axes.spines.top":False,"axes.spines.right":False,"axes.spines.bottom":False,"axes.spines.left":False})
def parts(g):
 if g.is_empty:return
 if g.geom_type=="Polygon":yield g
 elif hasattr(g,"geoms"):
  for x in g.geoms:yield from parts(x)
def fill(ax,g,color,alpha=1,z=1):
 for p in parts(g):
  x,y=p.exterior.xy
  ax.fill(x,y,facecolor=color,lw=0,alpha=alpha,zorder=z)
def border(ax,g,color,linewidth=2,linestyle="-",z=8):
 for p in parts(g):
  x,y=p.exterior.xy
  ax.plot(x,y,color=color,lw=linewidth,ls=linestyle,zorder=z,solid_joinstyle="round")
def setup(ax):
 ax.set_facecolor("#F9FBFA")
 ax.set_aspect(1/math.cos(math.radians(15.5)),adjustable="box")
 ax.grid(lw=.5,alpha=.16,zorder=0)
 ax.tick_params(labelsize=8,colors="#778A91",length=0)
 ax.set_xlabel("Longitude (°)",fontsize=9,color=GRAY)
 ax.set_ylabel("Latitude (°)",fontsize=9,color=GRAY)
def footprint(ax):
 for f in biomas:
  lab=f["properties"]["bioma"]
  col=COLOR.get(lab,"#E3E5E6")
  fill(ax,shape(f["geometry"]),col,alpha=.82,z=1)
def mark(ax,city=True):
 ax.scatter([pt.x],[pt.y],s=90,facecolors="#D14242",edgecolors="white",linewidths=1.8,zorder=20)
 t=ax.annotate("Estação ANA 66070004\nCáceres",xy=(pt.x,pt.y),xytext=(24,-7),
 textcoords="offset points",fontsize=10,weight="bold",ha="left",color=TEXT,zorder=22)
 t.set_path_effects([pe.withStroke(linewidth=3.5,foreground="white")])
def textbox(ax,txt):
 ax.text(.02,.97,txt,transform=ax.transAxes,va="top",ha="left",color=TEXT,fontsize=10,
 bbox={"boxstyle":"round,pad=.5","fc":"white","ec":"none","alpha":.9},zorder=40)
fig=plt.figure(figsize=(16,9.7),facecolor="white")
fig.text(.054,.955,"DE ONDE VEM A ÁGUA QUE CHEGA A CÁCERES?",color=TEXT,fontsize=24,fontweight="bold")
fig.text(.054,.913,"Bacia contribuinte até a estação do rio Paraguai — não confundir com o município ou com todo o Pantanal",
 color=GRAY,fontsize=12)
gs=fig.add_gridspec(1,2,left=.05,right=.97,top=.868,bottom=.20,wspace=.12,width_ratios=[1.08,1])
ax=fig.add_subplot(gs[0,0]);setup(ax)
footprint(ax)
border(ax,mun,"#285F59",linewidth=2,linestyle=(0,(5,3)),z=5)
border(ax,old,"#999E9E",linewidth=1.6,linestyle=(0,(4,4)),z=6)
border(ax,bacia,"#204B79",linewidth=3.1,z=8)
mark(ax)
ax.set_xlim(-60.0,-55.3);ax.set_ylim(-18.3,-12.95)
ax.set_title("A   Localização e limites corretos",loc="left",fontsize=16,color=TEXT,fontweight="bold",pad=16)
textbox(ax,"Azul escuro: bacia a montante da estação\nVerde tracejado: município de Cáceres\nCinza: recorte hidrológico anterior")
ax2=fig.add_subplot(gs[0,1]);setup(ax2)
footprint(ax2)
# Atenuar tudo fora da bacia pela sobreposicao branca transparência, sem alterar geometrias reais
border(ax2,bacia,"#143C65",linewidth=3,z=8)
outline_old=False
mark(ax2)
x0,y0,x1,y1=bacia.bounds
ax2.set_xlim(x0-.25,x1+.35);ax2.set_ylim(y0-.24,y1+.27)
ax2.set_title("B   Quais biomas realmente contribuem?",loc="left",fontsize=16,color=TEXT,fontweight="bold",pad=16)
textbox(ax2,"222 unidades conectadas à estação\nÁrea de drenagem: 32.753 km² (HydroBASINS L10)")
# Percentage indicators and methodology
areas=meta["biomas_dentro_area_contribuinte_km2"]
total=sum(areas.values())
y=.147
fig.text(.058,y+0.013,"DENTRO DA BACIA:",fontsize=11,fontweight="bold",color=TEXT)
left=.285; available=.66
for name in ["Amazônia","Cerrado","Pantanal"]:
 share=areas.get(name,0)/total
 fig.patches.append(plt.Rectangle((left,y),available*share,.023,transform=fig.transFigure,color=COLOR[name],clip_on=False))
 left+=available*share
s="    ".join(f"{name}: {100*areas.get(name,0)/total:.1f}%" for name in ["Amazônia","Cerrado","Pantanal"])
fig.text(.287,.113,s,fontsize=11,color=TEXT)
fig.text(.058,.075,"Área publicada da estação: 32.774 km²  •  HydroBASINS L10: 32.753 km²  •  erro relativo: 0,07%",
 fontsize=10,color=TEXT)
fig.text(.058,.052,"Fontes: WWF HydroBASINS (rede e área), IBGE 2025 (biomas), IBGE (município), ANA 66070004.",
 fontsize=9,color=GRAY)
fig.text(.058,.031,"Cuidado: bioma Pantanal não é exatamente sinônimo de planície geomorfológica; o mapa não é a BAP inteira.",
 fontsize=9,color=GRAY)
fig.savefig(F/"MAPA_BACIA_REAL_ESTACAO_CACERES_BIOMAS.png",dpi=190,facecolor="white")
plt.close(fig)
print(json.dumps({"map":"pesquisa_pantanal/cartografia/MAPA_BACIA_REAL_ESTACAO_CACERES_BIOMAS.png","area_km2":meta["rede_hidrografica"]["area_up_area_km2"],"biomas_km2":areas,"estacao":station},ensure_ascii=False))
