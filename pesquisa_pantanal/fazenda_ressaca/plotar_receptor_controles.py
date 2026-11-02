#!/usr/bin/env python3
"""Mapa de evidências: área transformada, receptor MERIT D8 e dois controles, 1985/2025.
NÃO fazenda inteira; NÃO prova de conectividade hidráulica.
"""
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image
from shapely.geometry import shape
from shapely.ops import unary_union
from pyproj import Transformer

P=Path("pesquisa_pantanal/fazenda_ressaca")
R=P/"jusante"
geo=json.loads((R/"POLIGONOS_PILOTO_RECEPTOR_CONTROLES.geojson").read_text(encoding="utf8"))
tra=json.loads((R/"TRAJETOS_D8_MERIT_EXPLORATORIOS.geojson").read_text(encoding="utf8"))
toprops={f["properties"]["grupo"]:shape(f["geometry"]) for f in geo["features"]}
lonlat_to_utm=Transformer.from_crs("EPSG:4326","EPSG:32721",always_xy=True)
cx,cy=lonlat_to_utm.transform(-57.72622,-16.27013)
extent=(cx-12000,cx+12000,cy-12000,cy+12000)
colors={"FONTE_PASTAGEM":"#CD713F","RECEPTOR_D8":"#176F9E","CONTROLE_NORTE":"#3F8E6A","CONTROLE_SENSIBILIDADE":"#8965A6"}
names={"FONTE_PASTAGEM":"A · Pastagem expandida","RECEPTOR_D8":"B · Receptor provável","CONTROLE_NORTE":"C · Controle norte","CONTROLE_SENSIBILIDADE":"D · Controle alternativo"}
def polygons(g):
 if g.geom_type=="Polygon":yield g
 elif hasattr(g,"geoms"):
  for sub in g.geoms:yield from polygons(sub)
def outline(ax,geom,col,lw=3):
 for poly in polygons(geom):
  xx,yy=zip(*(lonlat_to_utm.transform(*p) for p in poly.exterior.coords))
  ax.plot(xx,yy,color=col,lw=lw,zorder=8,solid_joinstyle="round")
def center(geom):
 p=geom.representative_point()
 return lonlat_to_utm.transform(p.x,p.y)
fig,axs=plt.subplots(1,2,figsize=(15.7,8.7),facecolor="white")
fig.subplots_adjust(left=.035,right=.965,top=.84,bottom=.15,wspace=.08)
fig.text(.045,.956,"DO PASTO AO RIO: TRÊS ÁREAS DE TESTE",fontweight="bold",fontsize=21,color="#223A48")
fig.text(.045,.918,"Entorno da Fazenda Ressaca, Cáceres (MT) | Pixels reais do MapBiomas, células de 2 km e trajetos MERIT Hydro",fontsize=11.5,color="#63777F")
for ax,yr in zip(axs,[1985,2025]):
 im=Image.open(P/"resultados"/f"RESSACA_USO_SOLO_{yr}.png")
 ax.imshow(im,extent=extent,origin="upper",interpolation="nearest",zorder=1)
 # D8 from 3 source cells, first ~25km of trajectory
 for f in tra["features"]:
  if f["properties"]["source_id"] not in ["C04_06","C05_06","C06_06"]:continue
  coords=f["geometry"]["coordinates"][:45]
  xy=[lonlat_to_utm.transform(*p) for p in coords]
  xx,yy=zip(*xy)
  ax.plot(xx,yy,color="#225D7B",lw=1.6,ls="--",alpha=.75,zorder=6)
 for key,geom in toprops.items():
  outline(ax,geom,colors[key],3.6 if key in ["RECEPTOR_D8","FONTE_PASTAGEM"] else 2.7)
  px,py=center(geom)
  letter=names[key].split(" ")[0]
  ax.text(px,py,letter,color="white",ha="center",va="center",weight="bold",fontsize=13,
   bbox=dict(boxstyle="round,pad=.25",facecolor=colors[key],edgecolor="white",lw=1.5),zorder=15)
 ax.set_xlim(extent[:2]);ax.set_ylim(extent[2:]);ax.set_aspect("equal")
 ax.set_xticks([]);ax.set_yticks([]);ax.set_title(str(yr),fontsize=17,fontweight="bold",pad=9,color="#233F4D")
 for s in ax.spines.values():s.set_visible(False)
legend=[Line2D([0],[0],color=col,lw=3.5,label=names[key]) for key,col in colors.items()]
legend.append(Line2D([0],[0],color="#225D7B",lw=1.5,ls="--",label="Trajeto de drenagem provável (MERIT D8)"))
fig.legend(handles=legend,frameon=False,ncol=3,loc="lower center",bbox_to_anchor=(.5,.075),fontsize=10)
fig.text(.045,.028,"Células A: 3.600 ha com expansão de pastagem. B, C e D: 1.200 ha cada. Limites são de amostragem, NÃO da propriedade.",fontsize=9.7,color="#536A76")
fig.text(.045,.008,"No Pantanal, canais podem bifurcar; traçado D8 não comprova que a água de A chega a B. Fonte: MapBiomas C11 e C5, MERIT Hydro 90m.",fontsize=9.4,color="#536A76")
out=R/"MAPA_PILOTO_JUSANTE_E_CONTROLES.png"
fig.savefig(out,dpi=195,bbox_inches="tight",facecolor="white")
plt.close(fig)
print({"file":str(out),"size_bytes":out.stat().st_size,"groups":names})
