#!/usr/bin/env python3
"""Seleciona possíveis áreas receptoras a jusante e controles comparáveis.
Exposição é definida por traçado D8 MERIT a partir do hotspot (não dados de água pós-1985).
Controles fora dos trajetos, comparados por água 1985, pastagem 1985 e distância a águas do período-base.
Apenas células de 2x2 km, NÃO fazenda como imóvel, nem prova de fluxo no Pantanal.
"""
from pathlib import Path
import csv,json,math,traceback
import pandas as pd
from shapely.geometry import shape, LineString,Point, mapping
from shapely.ops import unary_union
from pyproj import Geod
P=Path("pesquisa_pantanal/fazenda_ressaca")
R=P/"jusante";R.mkdir(exist_ok=True,parents=True)
read=lambda p:json.loads(p.read_text(encoding="utf8"))
diag=read(R/"DIAGNOSTICO_CONECTIVIDADE_MERIT.json")
assert diag["status"]=="diagnostico_raster_concluido"
grid=read(P/"resultados/GRADE_ENTORNO_RESSACA_2KM.geojson")["features"]
hots=read(P/"resultados/HOTSPOT_CELULAS_RESSACA.geojson")["features"]
ranking=pd.read_csv(P/"resultados/RANKING_CELULAS_RESSACA.csv",encoding="utf-8-sig")
hotids={x["properties"]["id"] for x in hots}
geod=Geod(ellps="GRS80")
cellgeom={x["properties"]["id"]:shape(x["geometry"]) for x in grid}
traces=read(R/"TRAJETOS_D8_MERIT_EXPLORATORIOS.geojson")["features"]
# Ignore first steps inside the source. Restrict network to first ~20 km downstream.
# Line output has uniform sampling (300 points over ~150km), so approx 35-45 points for ~20 km.
trail={}
for f in traces:
    name=f["properties"]["source_id"]
    pts=f["geometry"]["coordinates"]
    # approximate 20km along route from source; grid path spacings ~0.5km
    short=pts[:min(45,len(pts))]
    trail[name]=LineString(short)
source=unary_union([cellgeom[i] for i in hotids])
metrics={}
for _,v in ranking.iterrows():
    cid=v["id"];geom=cellgeom[cid]
    touches=sum(geom.intersects(line) for line in trail.values())
    n_core=sum(geom.intersects(line) for nm,line in trail.items() if nm.startswith("C05_06_"))
    overlap_source=cid in hotids
    x,y=geom.centroid.x,geom.centroid.y
    distance_from_source_km=source.distance(geom)*110
    metrics[cid]={"id":cid,"i":int(v["i"]),"j":int(v["j"]),
      "n_trace_intersections":touches,"n_core_trace_intersections":n_core,
      "water_baseline_1985_ha":float(v["water1985_ha"]),
      "pasture_baseline_1985_ha":float(v["pastagem_ha_1985"]),
      "pasture_2025_ha":float(v["pastagem_ha_2025"]),
      "pasture_gain_1985_2025_ha":float(v["saldo_pastagem_1985_2025_ha"]),
      "native_to_past_1985_2025_ha":float(v["nat_to_past25_ha"]),
      "centroid_lon":x,"centroid_lat":y,
      "dist_source_bbox_km_approx":float(distance_from_source_km),
      "source":overlap_source}
# Potential receptor = outside source, connected to CORE trajectories, preferably high baseline water
# Do not filter by later water change.
candidate=[v for v in metrics.values() if not v["source"] and v["n_core_trace_intersections"]>=2
            and v["water_baseline_1985_ha"]>=5]
candidate.sort(key=lambda v:(-min(90,v["water_baseline_1985_ha"]),-v["n_core_trace_intersections"]))
other=[v for v in metrics.values() if not v["source"] and v["n_trace_intersections"]>=2]
other.sort(key=lambda v:(-v["n_core_trace_intersections"],-v["water_baseline_1985_ha"]))
output={"n_cells":len(metrics),"n_core_traces":sum(k.startswith("C05_06_") for k in trail),
"n_candidate_receptor":len(candidate),"potential_receptors":candidate[:35],
"downstream_all":other[:35],
"controls_must_not_intersect_trace":True,
"source_ids":sorted(hotids),"notes":["Passagem de linha MERIT D8 por célula não prova contribuição da pastagem em planície alagável.",
"Selecionar área receptora por conectividade, área inicial de água e relevo antes de ver tendência pós-conversão.",
"Controle deve ter água inicial e configuração de relevo semelhantes, conversão de uso muito menor, e não atravessar trajeto."],
"status":"diagnostico"}
(R/"CANDIDATOS_RECEPTORES_CONTROLE.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf8")
with (R/"GRADE_RECEPTORES_MERIT.csv").open("w",encoding="utf-8-sig",newline="") as f:
 cols=["id","i","j","n_trace_intersections","n_core_trace_intersections","water_baseline_1985_ha",
       "pasture_baseline_1985_ha","pasture_gain_1985_2025_ha","native_to_past_1985_2025_ha",
       "dist_source_bbox_km_approx","source","centroid_lon","centroid_lat"]
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
 for v in sorted(metrics.values(),key=lambda x:x["id"]):w.writerow({k:v.get(k) for k in cols})
print(json.dumps(output,ensure_ascii=False,indent=2)[:15500])
