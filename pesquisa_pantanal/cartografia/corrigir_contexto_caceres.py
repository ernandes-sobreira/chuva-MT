#!/usr/bin/env python3
"""Corrigir interpretacao cartografica: municipio de Caceres != HydroBASINS nivel 6.

Usa geometrias reais no repositorio de pesquisa, sem inventar recorte.
Gera PNG com mapa de localizacao e tabela geoespacial de conferencia.
"""
from pathlib import Path
import json, math, unicodedata
from shapely.geometry import shape, Point
from shapely.ops import transform
from pyproj import Transformer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as path_effects
import numpy as np
from PIL import Image

BASE=Path("pesquisa_pantanal/caceres/resultados")
OUT=Path("pesquisa_pantanal/cartografia")
OUT.mkdir(parents=True,exist_ok=True)

def load_feature(path):
    obj=json.loads(Path(path).read_text(encoding="utf-8"))
    return obj["features"][0]
def area_km2(geom):
    convert=Transformer.from_crs("EPSG:4326","EPSG:31981",always_xy=True).transform
    return transform(convert,geom).area/1e6
def polygons(g):
    if g.geom_type=="Polygon":return [g]
    if g.geom_type=="MultiPolygon":return list(g.geoms)
    if g.geom_type=="GeometryCollection":
        return [p for x in g.geoms for p in polygons(x)]
    return []
def fill_geom(ax,geom,facecolor,edgecolor=None,lw=.6,alpha=1,z=2):
    if geom.is_empty:return
    for p in polygons(geom):
        x,y=p.exterior.xy
        ax.fill(x,y,facecolor=facecolor,edgecolor=edgecolor or "none",lw=lw,alpha=alpha,zorder=z)
        for hole in p.interiors:
            xx,yy=hole.xy
            ax.fill(xx,yy,facecolor="white",edgecolor="none",zorder=z+.1)
def outline(ax,geom,color,lw,z=6,ls="-"):
    if geom.is_empty:return
    for p in polygons(geom):
        x,y=p.exterior.xy
        ax.plot(x,y,color=color,lw=lw,zorder=z,linestyle=ls,solid_joinstyle="round")
def label_city(ax,x,y,s=12,off=(12,14)):
    ax.scatter([x],[y],s=110,c="#B72934",edgecolors="white",linewidths=2.2,zorder=20)
    ann=ax.annotate("Cáceres (sede)",(x,y),xytext=off,textcoords="offset points",ha="left",va="bottom",
                   fontsize=s,weight="bold",color="#202F37",zorder=21)
    ann.set_path_effects([path_effects.withStroke(linewidth=3.6,foreground="white")])
def north(ax,x,y):
    ax.annotate("N",(x,y),xytext=(x,y-.18),xycoords="data",textcoords="data",
                ha="center",va="center",fontsize=12,color="#203541",fontweight="bold",
                arrowprops=dict(arrowstyle="->",color="#203541",lw=2))
def setup(ax):
    ax.set_facecolor("#F6F8F7")
    ax.grid(color="#D8E2E3",lw=.55,alpha=.7,zorder=0)
    ax.tick_params(axis="both",labelsize=9,colors="#6C7F86")
    for s in ax.spines.values():s.set_visible(False)
    ax.set_xlabel("Longitude (°O)",size=10,color="#53646C")
    ax.set_ylabel("Latitude (°S)",size=10,color="#53646C")
    ax.set_aspect(1/math.cos(math.radians(16)),adjustable="box")
def return_municipio(code="5102504"):
    d=json.loads(Path("dados/municipios_mt.geojson").read_text(encoding="utf-8"))
    matches=[f for f in d["features"] if str(f["properties"].get("CD_MUN"))==code]
    if len(matches)!=1:raise RuntimeError("Municipio IBGE 5102504 nao encontrado ou duplicado na malha original.")
    return shape(matches[0]["geometry"]),matches[0]["properties"]
mun,props=return_municipio()
local=shape(load_feature(BASE/"caceres_local_hydrobasins.geojson")["geometry"])
up=shape(load_feature(BASE/"caceres_area_montante.geojson")["geometry"])
flood=shape(load_feature(BASE/"caceres_planicie_recorte.geojson")["geometry"])
city=Point(-57.69,-16.06) # referencia IBGE para sede municipal
assert city.within(mun),"Sede nao caiu dentro do municipio: verificar CRS/geometry."
assert city.within(local),"Sede nao caiu no poligono HydroBASINS: verificar posicionamento"
assert local.intersection(mun).area>0,"Nao existe sobreposicao municipio/bacia"
assert flood.intersection(local).area>0,"Recorte Pantanal nao intersecta unidade hidrologica"
stats={
    "status":"validado_geometricamente",
    "municipio":{"nome":props.get("NM_MUN","Cáceres"),"codigo_ibge":str(props.get("CD_MUN")),
                 "area_km2_malha":round(area_km2(mun),2),"bbox_lon_lat":list(mun.bounds)},
    "unidade_hydrobasins":{"id":6060634290,"area_km2":round(area_km2(local),2),"bbox_lon_lat":list(local.bounds)},
    "area_montante":{"area_km2":round(area_km2(up),2)},
    "recorte_pantanal_local":{"area_km2":round(area_km2(flood),2)},
    "intersecao_municipio_unidade":{"area_km2":round(area_km2(local.intersection(mun)),2),
                                   "pct_unidade_dentro_municipio":round(100*area_km2(local.intersection(mun))/area_km2(local),2),
                                   "pct_municipio_na_unidade":round(100*area_km2(local.intersection(mun))/area_km2(mun),2)},
    "sede_caceres_lon_lat":[city.x,city.y],
    "sede_no_municipio":bool(city.within(mun)),
    "sede_na_unidade_hydrobasins":bool(city.within(local)),
    "fontes":["IBGE, malha municipal MT (codigo 5102504) extraida do repositorio Chuva-MT",
              "WWF HydroBASINS nivel 6, identificador 6060634290",
              "IBGE limite bioma Pantanal 2025, intersecao com unidade local",
              "MapBiomas Agua C5 e Cobertura C11, rasters em composicao 2024"],
    "interpretacao":"O mapa antigo era uma unidade de drenagem HydroBASINS, nao o contorno municipal de Caceres.",
    "cautela":"Proporcoes espaciais se referem a estes recortes vetoriais, e nao ao municipio inteiro ou ao Pantanal inteiro."
}
(OUT/"conferencia_geografica_caceres.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding="utf-8")
# Simplificado geometria municipio e local para mapa acessivel
for name,geom in [("municipio_caceres_ibge.geojson",mun),("unidade_hydrobasins_6060634290.geojson",local)]:
    from shapely.geometry import mapping
    obj={"type":"FeatureCollection","features":[{"type":"Feature","properties":{"fonte":"IBGE municipal" if "municipio" in name else "WWF HydroBASINS nível 6"},"geometry":mapping(geom.simplify(.003,preserve_topology=True))}]}
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")
plt.rcParams.update({"font.family":"DejaVu Sans","figure.facecolor":"white"})
fig=plt.figure(figsize=(16,9.5),facecolor="white")
fig.text(.055,.953,"QUAL É O MAPA DE CÁCERES?",fontsize=28,fontweight="bold",color="#22343B")
fig.text(.055,.909,"Sobreposição entre o município (IBGE) e a unidade de drenagem usada no estudo",fontsize=15,color="#53646C")
gs=fig.add_gridspec(1,2,left=.07,right=.975,top=.855,bottom=.18,wspace=.12,width_ratios=[1,1.05])
ax=fig.add_subplot(gs[0,0]);setup(ax)
# full comparison: municipality vs catchment
fill_geom(ax,mun,"#D8EEE4",z=1)
fill_geom(ax,up,"#F0D6C2",alpha=.46,z=2)
fill_geom(ax,local,"#CFDCEB",alpha=.86,z=3)
fill_geom(ax,flood,"#6BB6C8",alpha=.77,z=4)
outline(ax,up,"#D59C6A",1.8,z=6)
outline(ax,mun,"#226F58",3.5,z=8)
outline(ax,local,"#3A5B93",2.8,z=9)
outline(ax,flood,"#1D8198",1.5,z=10)
label_city(ax,city.x,city.y,s=12,off=(10,-37))
ax.set_xlim(-59.9,-55.5);ax.set_ylim(-18.2,-14.45)
ax.set_title("A   Dois contornos diferentes",loc="left",fontsize=16,fontweight="bold",color="#24383D",pad=17)
ax.text(.02,.98,"Limite municipal ≠ unidade hidrográfica",transform=ax.transAxes,va="top",fontsize=12,color="#284E60",
        bbox=dict(fc="white",ec="none",alpha=.9,boxstyle="round,pad=.4"))
north(ax,-56.02,-14.83)
# detail: old map as actual measured satellite raster with accurate municipality line
bx=fig.add_subplot(gs[0,1]);setup(bx)
p=BASE/"MAPA_REAL_CACERES_AGUA_PASTAGEM_2024.png"
if not p.exists():raise RuntimeError("Raster original MapBiomas 2024 ausente. Não gerar figura fictícia.")
im=Image.open(p).convert("RGBA")
arr=np.array(im)
# Preto fora da area ja e transparente no original (se alpha vier 0). Se nao, mascara preto puro.
if (arr[:,:,3]==255).all():
    mask=np.all(arr[:,:,:3]<5,axis=2);arr[mask,3]=0
extent=(-58.63,-57.44,-16.42,-14.79)
bx.imshow(arr,extent=extent,origin="upper",zorder=2,interpolation="nearest")
outline(bx,local,"#3A5B93",2.9,z=6)
outline(bx,mun,"#226F58",2.8,z=8,ls="--")
outline(bx,flood,"#1D8198",1.6,z=9)
label_city(bx,city.x,city.y,s=12,off=(12,14))
bx.set_xlim(-58.85,-57.19);bx.set_ylim(-16.55,-14.64)
bx.set_title("B   O antigo recorte, agora localizado",loc="left",fontsize=16,fontweight="bold",color="#24383D",pad=17)
bx.text(.02,.98,"Água e pastagens: MapBiomas, 2024",transform=bx.transAxes,va="top",fontsize=12,color="#284E60",
       bbox=dict(fc="white",ec="none",alpha=.9,boxstyle="round,pad=.4"))
# legend bottom
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
items=[Line2D([0],[0],color="#226F58",lw=3,label="Município de Cáceres"),
       Line2D([0],[0],color="#3A5B93",lw=3,label="Unidade HydroBASINS usada"),
       Line2D([0],[0],color="#D59C6A",lw=2,label="Área a montante"),
       Patch(facecolor="#6BB6C8",label="Recorte local no Pantanal"),
       Line2D([0],[0],marker="o",linestyle="None",color="#B72934",markeredgecolor="white",markersize=10,label="Sede de Cáceres"),
       Patch(facecolor="#CEA56B",label="Pastagem plantada (2024)"),
       Patch(facecolor="#1C80B0",label="Água superficial (2024)")]
fig.legend(handles=items,loc="lower center",bbox_to_anchor=(.51,.082),ncol=4,frameon=False,fontsize=11,
           columnspacing=1.9,handlelength=1.8)
fig.text(.065,.037,"Fontes: IBGE (limites), WWF HydroBASINS L6 e MapBiomas C5/C11. O recorte estudado não é o município inteiro.",
         fontsize=10,color="#526871")
fig.text(.065,.015,"Valores e áreas obtidos dos vetores reais. Mapa esquemático georreferenciado em longitude/latitude.",
         fontsize=9,color="#82949B")
out=OUT/"MAPA_CORRIGIDO_CONTEXTO_CACERES.png"
fig.savefig(out,dpi=180,facecolor="white")
plt.close(fig)
print(json.dumps({"mapa_png":str(out),"bytes":out.stat().st_size,"metadados":stats},ensure_ascii=False,indent=2))
