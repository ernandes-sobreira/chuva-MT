#!/usr/bin/env python3
"""Chuva anual CHIRPS v3 no bioma Pantanal - pesquisa exploratoria, recorte IBGE 2025."""
import os,io,json,zipfile,traceback
from pathlib import Path
import requests
import shapefile
from shapely.geometry import shape,mapping
import ee
OUT=Path("pesquisa_pantanal/resultados");OUT.mkdir(parents=True,exist_ok=True)
GEO="https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/biomas/vetores/2025_Biomas-e-Sistema-Costeiro-Marinho-do-Brasil-1-250000_shp.zip"
FALLBACK="https://services.arcgis.com/F7DSX1DSNSiWmOqh/ArcGIS/rest/services/Brazil_Biomas/FeatureServer/0/query"
META={"recorte_bioma":GEO,"colecao":"UCSB-CHC/CHIRPS/V3/DAILY_SAT","variavel":"precipitation","unidade":"mm/ano; media espacial sobre o bioma","erros":[]}
def load_ibge():
 r=requests.get(GEO,timeout=(35,120));r.raise_for_status()
 z=zipfile.ZipFile(io.BytesIO(r.content))
 shpname=next(n for n in z.namelist() if n.lower().endswith(".shp") and not n.startswith("__MACOSX"))
 prefix=shpname[:-4]; dbf=next(n for n in z.namelist() if n.lower()==(prefix+".dbf").lower())
 rd=shapefile.Reader(shp=io.BytesIO(z.read(shpname)),dbf=io.BytesIO(z.read(dbf)),encoding="latin1")
 fields=[x[0] for x in rd.fields[1:]]
 matches=[]; info=[]
 for rec in rd.iterShapeRecords():
  props=dict(zip(fields,rec.record))
  if len(info)<8:info.append({k:str(v)[:60] for k,v in props.items()})
  if any("pantanal" in str(v).lower() for v in props.values()):matches.append(shape(rec.shape.__geo_interface__))
 if not matches:raise RuntimeError("Nao identificado Pantanal no vetor IBGE. Amostra "+repr(info))
 from shapely.ops import unary_union
 geom=unary_union(matches)
 if not geom.is_valid:geom=geom.buffer(0)
 geom=geom.simplify(.004,preserve_topology=True)
 META["n_poligonos_bioma"]=len(matches)
 META["area_geometrica_graus2"]=round(geom.area,3)
 META["recorte_modo"]="IBGE 2025, poligonos simplificados 0,004 grau"
 return mapping(geom)
def fallback_arcgis():
 params={"where":"Bioma='Pantanal'","outFields":"Bioma","outSR":4326,"f":"geojson"}
 r=requests.get(FALLBACK,params=params,timeout=90);r.raise_for_status()
 geoj=r.json()
 if not geoj.get("features"):raise RuntimeError("Sem poligono Pantanal no ArcGIS")
 from shapely.ops import unary_union
 geom=unary_union([shape(f["geometry"]) for f in geoj["features"]]).simplify(.006,preserve_topology=True)
 META["recorte_modo"]="FALLBACK - ArcGIS Brazil_Biomas, pode divergir IBGE 2025"
 return mapping(geom)
try:
 try:g=load_ibge()
 except Exception as e:
  META["erros"].append("IBGE shape primario: "+str(e))
  g=fallback_arcgis()
 (OUT/"geometria_pantanal_chirps.geojson").write_text(json.dumps({"type":"FeatureCollection","features":[{"type":"Feature","properties":{"recorte":META["recorte_modo"]},"geometry":g}]},ensure_ascii=False),encoding="utf8")
 key=os.environ.get("EE_SERVICE_ACCOUNT_KEY","").strip()
 if not key:raise RuntimeError("Segredo do Earth Engine nao configurado")
 obj=json.loads(key);project=os.environ.get("EE_PROJECT") or obj["project_id"]
 ee.Initialize(ee.ServiceAccountCredentials(obj["client_email"],key_data=key),project=project)
 region=ee.Geometry(g,proj="EPSG:4326",geodesic=False)
 col=ee.ImageCollection(META["colecao"]).select("precipitation")
 years=[]
 for year in range(1985,2026):
  start=f"{year}-01-01";end=f"{year+1}-01-01"
  total=col.filterDate(start,end).sum().rename("mm")
  stats=total.reduceRegion(reducer=ee.Reducer.mean(),geometry=region,scale=5600,maxPixels=1e9,bestEffort=True, tileScale=4).getInfo()
  val=stats.get("mm")
  if val is None:raise RuntimeError(f"CHIRPS retornou valor nulo {year}")
  years.append({"ano":year,"precipitacao_bioma_pantanal_mm":round(float(val),3)})
  print(f"CHIRPS {year}: {val:.2f} mm",flush=True)
 (OUT/"precipitacao_chirps_bioma_pantanal_1985_2025.csv").write_text("ano,precipitacao_bioma_pantanal_mm\n"+"\n".join(str(d["ano"])+","+str(d["precipitacao_bioma_pantanal_mm"]) for d in years)+"\n",encoding="utf8")
 META["anos"]=len(years)
 META["min_mm"]=min(d["precipitacao_bioma_pantanal_mm"] for d in years)
 META["max_mm"]=max(d["precipitacao_bioma_pantanal_mm"] for d in years)
except Exception as e:
 META["erros"].append("CHIRPS: "+repr(e))
 traceback.print_exc()
finally:
 (OUT/"relatorio_chuva.json").write_text(json.dumps(META,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps(META,ensure_ascii=False,indent=2))
