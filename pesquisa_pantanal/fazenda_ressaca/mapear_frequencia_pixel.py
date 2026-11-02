#!/usr/bin/env python3
"""Mapa pixel 30m: frequência de água do MapBiomas C5 mensal (pre 1985–94 vs post 2015–25).
Não contar pixels como réplicas independentes nem usar para inferência causal.
A frequência é fração de meses com água detectada, não duração exata de inundação.
"""
from pathlib import Path
import os,json,traceback,io
import numpy as np
import ee
from shapely.geometry import shape
from pyproj import Transformer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

P=Path("pesquisa_pantanal/fazenda_ressaca")
R=P/"jusante";R.mkdir(exist_ok=True,parents=True)
fc=json.loads((R/"POLIGONOS_PILOTO_RECEPTOR_CONTROLES.geojson").read_text())["features"]
statuses=json.loads((R/"STATUS_PAREAMENTO_HIDROLOGICO.json").read_text(encoding="utf8"))
assert statuses["status"]=="concluido"
meta={"status":"inicio","fonte":"MapBiomas Água C5 mensal, 30m","periodo_base":"1985–1994","periodo_final":"2015–2025",
"meses_pre":120,"meses_post":132,"metrica":"fração de meses com água detectada em cada pixel",
"limites":["Frequência de água detectada não mede volume ou profundidade.",
"No-data classificado como 0 na exportação; verificar qualidade de cobertura satelital.",
"Pixels próximos não são réplicas independentes.","Controles MERIT D8 em planície são provisórios."],"erros":[]}
colors={"FONTE_PASTAGEM":"#CD713F","RECEPTOR_D8":"#176F9E","CONTROLE_NORTE":"#3F8E6A","CONTROLE_SENSIBILIDADE":"#8965A6"}
try:
 k=os.environ["EE_SERVICE_ACCOUNT_KEY"];creds=json.loads(k)
 ee.Initialize(ee.ServiceAccountCredentials(creds["client_email"],key_data=k),project=os.environ.get("EE_PROJECT") or creds["project_id"])
 WM=ee.ImageCollection("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_monthly_v4")
 def frequency(first,last):
  imgs=[]
  for y in range(first,last+1):
   for m in range(1,13):
    im=ee.Image(WM.filter(ee.Filter.eq("system:index",f"water_monthly_{y}_{m:02d}")).first())
    imgs.append(im.select("water_monthly").eq(m).unmask(0))
  return ee.ImageCollection.fromImages(imgs).mean()
 base=frequency(1985,1994).rename("antes")
 after=frequency(2015,2025).rename("depois")
 diff=after.subtract(base).rename("delta")
 trend=ee.Image.cat([base,after,diff,diff.lt(-.2).rename("reduz_20pp"),diff.gt(.2).rename("aumenta_20pp")])
 groups=ee.FeatureCollection([ee.Feature(ee.Geometry(f["geometry"],proj="EPSG:4326",geodesic=False),
  {"grupo":f["properties"]["grupo"]}) for f in fc])
 output=trend.reduceRegions(collection=groups,reducer=ee.Reducer.mean(),scale=30,tileScale=4).getInfo()["features"]
 meta["estatisticas_grupo"]=({x["properties"]["grupo"]:{
  key:round(float(x["properties"][key]),5) if x["properties"].get(key) is not None else None
  for key in ["antes","depois","delta","reduz_20pp","aumenta_20pp"]} for x in output})
 # Visual only, raster 34m/px. Use float array for categorical full-period difference.
 transform=Transformer.from_crs("EPSG:4326","EPSG:32721",always_xy=True)
 cx,cy=transform.transform(-57.72622,-16.27013)
 W,H=700,700
 cell=24000/W
 grid={"dimensions":{"width":W,"height":H},
 "affineTransform":{"scaleX":cell,"shearX":0,"translateX":cx-12000,
 "scaleY":-cell,"shearY":0,"translateY":cy+12000},"crsCode":"EPSG:32721"}
 delta_arr=ee.data.computePixels({"expression":diff,"fileFormat":"NUMPY_NDARRAY","grid":grid})
 data=np.asarray(delta_arr["delta"],dtype=float) if delta_arr.dtype.names else np.asarray(delta_arr,dtype=float)
 if data.shape!=(H,W):raise RuntimeError("Matriz pixels inesperada "+str(data.shape))
 # avoid showing tiny near-zero differences as compelling changes
 fig,ax=plt.subplots(figsize=(10.5,10.2),facecolor="white")
 extent=(cx-12000,cx+12000,cy-12000,cy+12000)
 heat=ax.imshow(data,extent=extent,origin="upper",vmin=-.35,vmax=.35,cmap="RdBu",interpolation="nearest")
 for f in fc:
  name=f["properties"]["grupo"];g=shape(f["geometry"])
  for poly in ([g] if g.geom_type=="Polygon" else list(g.geoms)):
   pts=[transform.transform(*p) for p in poly.exterior.coords]
   xs,ys=zip(*pts);ax.plot(xs,ys,color=colors[name],lw=3,zorder=5)
   px,py=transform.transform(g.representative_point().x,g.representative_point().y)
   lab={"FONTE_PASTAGEM":"A","RECEPTOR_D8":"B","CONTROLE_NORTE":"C","CONTROLE_SENSIBILIDADE":"D"}[name]
   ax.text(px,py,lab,color="white",fontsize=14,weight="bold",ha="center",va="center",
    bbox=dict(fc=colors[name],ec="white",lw=1.5,boxstyle="round,pad=.35"),zorder=7)
 ax.scatter(cx,cy,marker="+",s=150,color="#22252A",lw=2,zorder=6)
 cb=fig.colorbar(heat,ax=ax,fraction=.048,pad=.025)
 cb.set_label("Diferença da frequência mensal com água (2015–25 menos 1985–94)",fontsize=10)
 ax.set_title("Mudança espacial na presença de água (pixels ~30 m)\nEntorno Ressaca: antes versus depois da expansão de pastagens",
 fontsize=15,weight="bold",pad=13)
 ax.set_xlabel("UTM 21S (m)")
 ax.set_ylabel("UTM 21S (m)")
 ax.ticklabel_format(useOffset=False,style="plain")
 ax.set_aspect("equal")
 fig.text(.08,.015,"Vermelho: menor frequência de água; azul: maior. Zeros não indicam nível constante. MapBiomas Água C5, 252 meses. Recortes A–D não são propriedades.",
 fontsize=8.5,color="#58686E")
 out=R/"MAPA_DELTA_FREQUENCIA_AGUA_PIXELS_1985_2025.png"
 fig.savefig(out,dpi=205,bbox_inches="tight")
 plt.close(fig)
 meta["map_png"]=out.name;meta["shape"]=list(data.shape)
 meta["status"]="concluido"
except Exception as e:
 meta["status"]="falha";meta["erros"].append(repr(e));traceback.print_exc()
finally:
 (R/"STATUS_HIDROPERIODO_PIXELS.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf8")
 print(json.dumps(meta,ensure_ascii=False,indent=2)[:6500])
 if meta["status"]!="concluido":raise SystemExit("Frequência por pixel não exportada")
