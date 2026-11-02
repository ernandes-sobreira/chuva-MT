#!/usr/bin/env python3
"""Diagnóstico de conectividade por MERIT Hydro D8 90m entre células do hotspot Ressaca e rede de drenagem.
O algoritmo NÃO afirma fluxo real em planície com bifurcações, nem atribui resultado à fazenda.
Gera GeoJSON de caminhos e diagnóstico de receptor, antes de fazer teste de impacto.
"""
from pathlib import Path
import math, json, os, traceback, collections
import numpy as np
import ee
from shapely.geometry import shape, Point, mapping, LineString
from shapely.ops import unary_union

P=Path("pesquisa_pantanal/fazenda_ressaca")
R=P/"jusante";R.mkdir(exist_ok=True,parents=True)
read=lambda fn:json.loads((P/"resultados"/fn).read_text(encoding="utf8"))
cellgrid=read("GRADE_ENTORNO_RESSACA_2KM.geojson")["features"]
hotgrid=read("HOTSPOT_CELULAS_RESSACA.geojson")["features"]
hotarea=unary_union([shape(f["geometry"]) for f in hotgrid])
core=next(f for f in hotgrid if f["properties"]["id"]=="C05_06")
source_2km=shape(core["geometry"])
# Exact 3 arc second grid (WGS84). Do not rotate ESRI D8 directions.
STEP=3/3600
WEST=-58.30;NORTH=-15.75;WIDTH=1080;HEIGHT=1500
GRID={"dimensions":{"width":WIDTH,"height":HEIGHT},
"affineTransform":{"scaleX":STEP,"shearX":0,"translateX":WEST,
"shearY":0,"scaleY":-STEP,"translateY":NORTH},"crsCode":"EPSG:4326"}
meta={"status":"starting","source":"MERIT/Hydro/v1_0_1","grid":GRID,
"method":"ESRI D8 em grade nativa 3 arcsec; inicia no centro das 9 células e em malha 5x5 dentro da célula mais convertida",
"source_rule":"Não aceitar caminho inferido como prova de conexão superficial no Pantanal (bifurcações e remansos).",
"n_hotspot_cells":len(hotgrid),"errors":[],"traces":[]}
D8={1:(0,1),2:(1,1),4:(1,0),8:(1,-1),16:(0,-1),32:(-1,-1),64:(-1,0),128:(-1,1)}
def lonlat(r,c):return WEST+(c+.5)*STEP,NORTH-(r+.5)*STEP
def ij(x,y):return int(math.floor((NORTH-y)/STEP)),int(math.floor((x-WEST)/STEP))
def aslonline(coords,limit=200):
 if len(coords)<=limit:return coords
 ix=np.linspace(0,len(coords)-1,num=limit).round().astype(int)
 return [coords[i] for i in sorted(set(ix))]
def downstream(p,dir_grid,upa_grid,hnd_grid):
 x,y=p;row,col=ij(x,y);seen=set();coords=[];upas=[];ends="";r0,c0=row,col
 for n in range(4000):
  if not (0<=row<HEIGHT and 0<=col<WIDTH):
   ends="saida_da_grade";break
  if (row,col) in seen:
   ends="ciclo_d8";break
  seen.add((row,col))
  lon,lat=lonlat(row,col)
  coords.append([round(lon,6),round(lat,6)])
  upa=float(upa_grid[row,col])
  hnd=float(hnd_grid[row,col])
  if np.isfinite(upa) and upa>=0:upas.append(upa)
  direction=int(dir_grid[row,col])
  if direction not in D8:
   ends=f"direcao_sem_saida_{direction}";break
  dr,dc=D8[direction]
  row+=dr;col+=dc
 else:ends="excesso_4000passos"
 if not coords:return None
 high=next(((i,coords[i]) for i,c in enumerate(coords) if i<len(upa_grid.flat) and
       (0<=ij(c[0],c[1])[0]<HEIGHT and 0<=ij(c[0],c[1])[1]<WIDTH) and
       float(upa_grid[ij(c[0],c[1])[0],ij(c[0],c[1])[1]])>=20),None)
 return {"start":p,"start_index":[r0,c0],"end_code":ends,"n_steps":len(coords),
 "length_km_approx":round(len(coords)*STEP*108,1),"first_stream_20_km2":high,
 "upa_start":float(upa_grid[r0,c0]) if 0<=r0<HEIGHT and 0<=c0<WIDTH else None,
 "upa_end":upas[-1] if upas else None,
 "hnd_start":float(hnd_grid[r0,c0]) if 0<=r0<HEIGHT and 0<=c0<WIDTH else None,
 "line":aslonline(coords,300)}
try:
 key=os.environ["EE_SERVICE_ACCOUNT_KEY"];obj=json.loads(key)
 ee.Initialize(ee.ServiceAccountCredentials(obj["client_email"],key_data=key),project=os.environ.get("EE_PROJECT") or obj["project_id"])
 im=ee.Image("MERIT/Hydro/v1_0_1").select(["dir","upa","hnd"])
 arr=ee.data.computePixels({"expression":im,"fileFormat":"NUMPY_NDARRAY","grid":GRID})
 print("MERIT array:",arr.shape,arr.dtype.names,flush=True)
 if not arr.dtype.names or not all(k in arr.dtype.names for k in ["dir","upa","hnd"]):raise RuntimeError("Wrong numpy raster bands: "+str(arr.dtype))
 d=np.asarray(arr["dir"]);u=np.asarray(arr["upa"]);h=np.asarray(arr["hnd"])
 meta["raster"]={"shape":d.shape,"valid_dir":int(np.isin(d,list(D8)).sum()),"upa_sample_minmax":[float(np.nanmin(u)),float(np.nanmax(u))],
    "dtype":str(arr.dtype)}
 starts=[]
 # centers of 9 cells
 for f in hotgrid:
  pt=shape(f["geometry"]).centroid
  starts.append({"source_id":f["properties"]["id"],"point":(pt.x,pt.y),"sample_type":"centro_celula"})
 # 5x5 subgrid of pixel locations in the highest conversion 2-km source cell
 x0,y0,x1,y1=source_2km.bounds
 for i in range(5):
  for j in range(5):
   x=x0+(i+.5)/5*(x1-x0);y=y0+(j+.5)/5*(y1-y0)
   if source_2km.contains(Point(x,y)):starts.append({"source_id":f"C05_06_{i}{j}","point":(x,y),"sample_type":"amostra_dentro_celula"})
 feature=[]
 for s in starts:
  trace=downstream(s["point"],d,u,h)
  if trace is None:continue
  feature.append({"type":"Feature","geometry":mapping(LineString(trace["line"])),
    "properties":{"source_id":s["source_id"],"tipo":s["sample_type"],
    "fim":trace["end_code"],"upa_start_km2":trace["upa_start"],"upa_end_km2":trace["upa_end"],
    "conectado_stream_20km2":trace["first_stream_20_km2"] is not None}})
  summary={k:v for k,v in trace.items() if k!="line"}
  summary["source_id"]=s["source_id"];summary["tipo"]=s["sample_type"]
  meta["traces"].append(summary)
 R.joinpath("TRAJETOS_D8_MERIT_EXPLORATORIOS.geojson").write_text(json.dumps({"type":"FeatureCollection","features":feature},ensure_ascii=False),encoding="utf8")
 meta["traces_success_stream_20km2"]=sum(t["first_stream_20_km2"] is not None for t in meta["traces"])
 meta["n_traces"]=len(meta["traces"])
 # where paths first intercept a stream with upa >=20, are they the same receiver?
 points=[]
 for t in meta["traces"]:
  f=t.get("first_stream_20_km2")
  if f:
   _,p=f
   points.append(p)
 meta["first_stream_points"]=points
 # measure distance to western meander area and range of paths
 if points:meta["bbox_stream_contact"]=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
 meta["status"]="diagnostico_raster_concluido"
except Exception as e:
 meta["status"]="falha";meta["errors"].append(repr(e));traceback.print_exc()
finally:
 R.joinpath("DIAGNOSTICO_CONECTIVIDADE_MERIT.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf8")
 print(json.dumps({k:v for k,v in meta.items() if k not in ["traces","first_stream_points"]},ensure_ascii=False,indent=2)[:6500])
 if meta["status"]!="diagnostico_raster_concluido":raise SystemExit("D8 não verificado, não definir áreas a jusante.")
