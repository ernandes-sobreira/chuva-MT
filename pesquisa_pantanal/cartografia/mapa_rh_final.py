#!/usr/bin/env python3
"""Revisão final cartográfica: comparação legível RH Paraguai oficial ANA vs drenagem da estação de Cáceres.
Sem requisições externas; apenas geometrias auditadas no repositório.
"""
from pathlib import Path
import json,math
from shapely.geometry import shape
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib import patheffects

R=Path("pesquisa_pantanal/recorte_cientifico/resultados");O=Path("pesquisa_pantanal/cartografia")
RH=shape(json.loads((R/"RH_PARAGUAI_Brasil_ANA.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
PAN=shape(json.loads((R/"Pantanal_bioma_dentro_RH_Paraguai_IBGE.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
CATCH=shape(json.loads((R/"BACIA_VERIFICADA_UPSTREAM_ANA_66070004.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
META=json.loads((R/"STATUS_RH_PARAGUAI_ANA.json").read_text(encoding="utf-8"))
if META["status"]!="concluido":raise RuntimeError("RH ANA não validada")
CENTER=(-57.68777778,-16.06305556)
colors=dict(rh="#E1E7DC",pant="#79C1CE",catch="#8A9EC8",station="#C23D47",line="#233A49")
def geometries(g):
 if g.is_empty:return
 if g.geom_type=="Polygon":yield g
 elif hasattr(g,"geoms"):
  for v in g.geoms:yield from geometries(v)
def polygon(ax,geom,color):
 for g in geometries(geom):
  x,y=g.exterior.xy;ax.fill(x,y,color=color,linewidth=0,zorder=2)
def outline(ax,geom,color,lw=2):
 for g in geometries(geom):
  x,y=g.exterior.xy;ax.plot(x,y,lw=lw,color=color,zorder=5)
def station(ax,lab=True):
 ax.scatter(CENTER[0],CENTER[1],s=115,c=colors["station"],edgecolors="white",lw=2,zorder=10)
 if lab:
  x=ax.annotate("Cáceres | ANA 66070004",xy=CENTER,xytext=(11,9),textcoords="offset points",
   fontsize=9,fontweight="bold",color=colors["line"],zorder=11)
  x.set_path_effects([patheffects.withStroke(linewidth=3.3,foreground="white")])
def setup(ax):
 ax.set_facecolor("#F8FBFA")
 ax.set_aspect(1/math.cos(math.radians(17)),adjustable="box")
 ax.grid(color="#D6E1E2",alpha=.45,lw=.5,zorder=0)
 ax.tick_params(colors="#73848B",labelsize=8,length=0)
 for s in ax.spines.values():s.set_visible(False)
 ax.set_xlabel("Longitude (°)",color="#6B7F85",fontsize=9)
 ax.set_ylabel("Latitude (°)",color="#6B7F85",fontsize=9)
plt.rcParams["font.family"]="DejaVu Sans"
fig,axes=plt.subplots(1,2,figsize=(15.3,8.6),facecolor="white")
fig.subplots_adjust(left=.055,right=.965,top=.84,bottom=.235,wspace=.18)
fig.text(.06,.954,"PANTANAL E CABECEIRAS | AGORA COM OS LIMITES CERTOS",fontsize=20,
 fontweight="bold",color=colors["line"])
fig.text(.06,.914,"O que chega à estação de Cáceres é apenas uma parte do sistema hidrológico do Pantanal",
 fontsize=12,color="#677B82")
for ax in axes:
 setup(ax)
 polygon(ax,RH,colors["rh"]);polygon(ax,PAN,colors["pant"]);polygon(ax,CATCH,colors["catch"])
 outline(ax,RH,"#536E65",1.6);outline(ax,PAN,"#21859C",1.8);outline(ax,CATCH,"#1B5182",2.8);station(ax)
ax=axes[0]
ax.set_xlim(-60.1,-52.8);ax.set_ylim(-22.9,-12.9)
ax.set_title("A   Região Hidrográfica do Paraguai — Brasil",loc="left",fontweight="bold",fontsize=13,color=colors["line"],pad=18)
ax.text(.02,.965,"Área: ~362 mil km² (ANA)",transform=ax.transAxes,va="top",fontsize=10,
 color=colors["line"],bbox=dict(boxstyle="round,pad=.35",facecolor="white",edgecolor="none",alpha=.9))
ax=axes[1]
ax.set_xlim(-59.45,-55.9);ax.set_ylim(-16.8,-13.9)
ax.set_title("B   Bacia que drena até a estação de Cáceres",loc="left",fontweight="bold",fontsize=13,color=colors["line"],pad=18)
ax.text(.02,.965,"Área: 32.753 km²  |  apenas 9,1% da RH Paraguai",transform=ax.transAxes,va="top",
 fontsize=10,color=colors["line"],bbox=dict(boxstyle="round,pad=.35",facecolor="white",edgecolor="none",alpha=.9))
legend=[
 Patch(color=colors["rh"],label="Região Hidrográfica (ANA)"),
 Patch(color=colors["pant"],label="Bioma Pantanal (IBGE)"),
 Patch(color=colors["catch"],label="Drenagem até Cáceres (HydroBASINS L10)"),
 Line2D([0],[0],marker="o",markersize=8,color=colors["station"],lw=0,label="Estação ANA 66070004")]
fig.legend(handles=legend,loc="lower center",bbox_to_anchor=(.5,.118),ncol=2,frameon=False,
 fontsize=10.5,columnspacing=2.5,handletextpad=.7)
fig.text(.06,.063,"Interpretação: a bacia da estação não representa a planície inteira. A RH Paraguai (ANA) é a porção brasileira da região, não toda a BAP internacional.",
 fontsize=9.1,color="#53676E")
fig.text(.06,.041,"Fontes: ANA/SNIRH (RH Paraguai); IBGE (bioma Pantanal); HydroBASINS L10 (222 unidades upstream); dados da estação ANA 66070004.",
 fontsize=8.8,color="#53676E")
fig.text(.06,.021,"Os limites do bioma não são divisores de águas. A área contribuinte foi conferida com a área hidrométrica publicada, mas ainda requer revisão pela BHO ANA.",
 fontsize=8.8,color="#53676E")
out=O/"MAPA_RH_PARAGUAI_E_EXUTORIO_CACERES_FINAL.png"
fig.savefig(out,dpi=190,facecolor="white")
plt.close(fig)
print(json.dumps({"arquivo":str(out),"bytes":out.stat().st_size,"area_RH_km2":META["area_RH_brasileira_km2"],
"area_bacia_caceres_km2":32752.7,"pct_caceres_rh":META["pct_RH_upstream_Caceres"]},ensure_ascii=False))
