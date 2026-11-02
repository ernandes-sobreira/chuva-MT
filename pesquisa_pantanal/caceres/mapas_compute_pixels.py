#!/usr/bin/env python3
"""Gera raster tematico oficial com computePixels (nao getThumbURL).
Uso exploratorio: GEE MapBiomas C5 Agua, C11 Cobertura. Sem falsificar pixels.
"""
from pathlib import Path
import os,json,traceback,io
from PIL import Image
import ee
OUT=Path("pesquisa_pantanal/caceres/resultados")
OUT.mkdir(parents=True,exist_ok=True)
info={"metodo":"earthengine computePixels PNG","erros":[],"imagens":[]}
try:
 key=os.environ["EE_SERVICE_ACCOUNT_KEY"];data=json.loads(key)
 ee.Initialize(ee.ServiceAccountCredentials(data["client_email"],key_data=key),project=os.environ.get("EE_PROJECT") or data["project_id"])
 raw=json.loads((OUT/"caceres_local_hydrobasins.geojson").read_text())["features"][0]["geometry"]
 geom=ee.Geometry(raw,proj="EPSG:4326",geodesic=False)
 # Formato espaco-bounds cobre a unidade local HydroBASINS em Caceres.
 bbox=[-58.63,-16.42,-57.44,-14.79]
 width,height=760,900
 grid={"dimensions":{"width":width,"height":height},
    "affineTransform":{"scaleX":(bbox[2]-bbox[0])/width,"shearX":0,"translateX":bbox[0],
                       "shearY":0,"scaleY":-(bbox[3]-bbox[1])/height,"translateY":bbox[3]},
    "crsCode":"EPSG:4326"}
 # Os produtos base tem 30m; reamostragem para exibir ~0,17km pixel na figura.
 W=ee.Image("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_annual_v4")
 L=ee.Image("projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3")
 M=ee.ImageCollection("projects/mapbiomas-public/assets/brazil/water/collection5/mapbiomas_brazil_collection5_water_monthly_v4")
 base=ee.Image.constant(0).visualize(min=0,max=1,palette=["#edf1ed"]).clip(geom)
 for year in [1988,2024]:
  past=L.select("classification_"+str(year)).eq(15).selfMask().visualize(palette=["#cea56b"]).clip(geom)
  water=W.select("classification_"+str(year)).eq(1).selfMask().visualize(palette=["#1c80b0"]).clip(geom)
  composite=ee.ImageCollection.fromImages([base,past,water]).mosaic().clip(geom)
  image_bytes=ee.data.computePixels({"expression":composite,"fileFormat":"PNG","grid":grid})
  im=Image.open(io.BytesIO(image_bytes));im.verify()
  name="MAPA_REAL_CACERES_AGUA_PASTAGEM_%d.png"%year
  (OUT/name).write_bytes(image_bytes);info["imagens"].append({"ano":year,"arquivo":name,"bytes":len(image_bytes)})
 for year in [1988,2024]:
  imgs=[]
  for m in range(1,13):
   img=ee.Image(M.filter(ee.Filter.eq("system:index","water_monthly_%d_%02d"%(year,m))).first())
   imgs.append(img.eq(m).unmask(0))
  count=ee.ImageCollection.fromImages(imgs).sum().clip(geom)
  cmap=count.visualize(min=0,max=12,palette=["#eff4ef","#c3dbe0","#88c7df","#448eae","#114c86"]).clip(geom)
  image_bytes=ee.data.computePixels({"expression":cmap,"fileFormat":"PNG","grid":grid})
  im=Image.open(io.BytesIO(image_bytes));im.verify()
  name="MAPA_REAL_CACERES_MESES_INUNDADOS_%d.png"%year
  (OUT/name).write_bytes(image_bytes);info["imagens"].append({"ano":year,"arquivo":name,"bytes":len(image_bytes)})
 info["status"]="pixels_reais_exportados"
except Exception as exc:
 info["status"]="bloqueio_ou_erro";info["erros"].append(repr(exc));traceback.print_exc()
finally:
 (OUT/"relatorio_exportacao_mapa.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf8")
 print(json.dumps(info,ensure_ascii=False,indent=2))
