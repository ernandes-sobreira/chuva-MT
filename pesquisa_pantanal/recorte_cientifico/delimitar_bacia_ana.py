#!/usr/bin/env python3
"""Reconstruir area contribuinte da estacao 66070004 (Caceres) por conexao NEXT_DOWN.
NÃO usar centro urbano nem limites do municipio como bacia. Não reter poligono por similaridade de area somente.
HydroBASINS L10, validar soma das sub-bacias x UP_AREA, e confrontar ANA/SGB.
"""
import os,json,traceback,datetime as dt,io,zipfile,unicodedata
from pathlib import Path
import requests, shapefile, ee
from shapely.geometry import shape,mapping,box
from shapely.ops import unary_union
from pyproj import Geod

ROOT=Path("pesquisa_pantanal/recorte_cientifico/resultados");ROOT.mkdir(parents=True,exist_ok=True)
BASE=Path("pesquisa_pantanal/caceres/resultados")
IBGE_URL="https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/biomas/vetores/2025_Biomas-e-Sistema-Costeiro-Marinho-do-Brasil-1-250000_shp.zip"
ANA_URL="https://portal1.snirh.gov.br/server/rest/services/dados_abertos/Estacao_Fluviometrica/MapServer/0/query"
meta={"executado_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"objeto":"bacia a montante da estacao ANA 66070004",
"hidrografia":"WWF HydroBASINS L10", "IBGE_biomas":"IBGE biomas 2025, 1:250.000",
"referencias_area_km2":{"publicacao_2015":32393,"publicacao_2017":32774},
"erros":[],"alertas":[]}
def dump(name,obj): (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
def norm(s):
 return "".join(c for c in unicodedata.normalize("NFD",str(s)) if unicodedata.category(c)!="Mn").lower()
def tofc(features):return {"type":"FeatureCollection","features":features}
def feature(geom,attrs):return {"type":"Feature","geometry":mapping(geom),"properties":attrs}
try:
 key=os.environ["EE_SERVICE_ACCOUNT_KEY"].strip();auth=json.loads(key)
 ee.Initialize(ee.ServiceAccountCredentials(auth["client_email"],key_data=key),project=os.environ.get("EE_PROJECT") or auth["project_id"])
 # Fonte primaria exata ANA. Se a API falhar, usar pontos de duas publicacoes e registrar explicitamente.
 station={"origem":"SGB/academico (fallback)","lon":-(57+41/60+16/3600),"lat":-(16+3/60+47/3600)}
 try:
  r=requests.get(ANA_URL,params={"where":"CODIGO=66070004","outFields":"*","returnGeometry":"true","outSR":"4674","f":"json"},timeout=35,headers={"User-Agent":"Mozilla/5.0"})
  r.raise_for_status();obj=r.json()
  meta["consulta_ana_url"]=r.url
  matches=obj.get("features",[])
  if len(matches)==1 and matches[0].get("geometry"):
   an=matches[0];props=an["attributes"];geometry=an["geometry"]
   station={"origem":"ANA SNIRH camada Estacao_Fluviometrica 0","lon":geometry["x"],"lat":geometry["y"],
   "area_ana_km2":props.get("AREADRENAGEM"),"atributos":props}
  else:meta["alertas"].append("Consulta ANA nao retornou exatamente 1 estacao; usado ponto publicado")
 except Exception as e:meta["alertas"].append("Servico de geolocalizacao ANA indisponivel: "+repr(e))
 meta["estacao"]=station
 print("ANA station:",json.dumps(station,ensure_ascii=False)[:500],flush=True)
 basin10=ee.FeatureCollection("WWF/HydroSHEDS/v1/Basins/hybas_10")
 pt=ee.Geometry.Point([float(station["lon"]),float(station["lat"])])
 candidate=basin10.filterBounds(pt).select(["HYBAS_ID","NEXT_DOWN","UP_AREA","SUB_AREA","PFAF_ID"],retainGeometry=False).first().getInfo()["properties"]
 target=int(candidate["HYBAS_ID"])
 meta["subbacia_exutorio"]=candidate
 # Montar lista de todos os fragmentos que pertencem a esta area de drenagem.
 # A selecao abrangente inicial e o envelope das 3 unidades do piloto; apenas para acelerar a consulta.
 # A selecao FINAL e exclusivamente via NEXT_DOWN, e deve bater com UP_AREA.
 older=json.loads((BASE/"caceres_area_montante.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"]
 window=ee.Geometry(older,proj="EPSG:4326",geodesic=False)
 candidates=basin10.filterBounds(window).select(["HYBAS_ID","NEXT_DOWN","UP_AREA","SUB_AREA","PFAF_ID"],retainGeometry=False).getInfo()["features"]
 p=[f["properties"] for f in candidates]
 if len(p)>25000:raise RuntimeError("Excesso de sub-bacias: "+str(len(p)))
 selected={target};last=-1
 while last!=len(selected):
  last=len(selected)
  selected|={int(row["HYBAS_ID"]) for row in p if int(row.get("NEXT_DOWN") or 0) in selected}
 if target not in {int(row["HYBAS_ID"]) for row in p}:raise RuntimeError("Exutorio ausente da area de busca")
 rows=[row for row in p if int(row["HYBAS_ID"]) in selected]
 total=sum(float(row["SUB_AREA"]) for row in rows)
 upstream=float(candidate["UP_AREA"])
 err=100*abs(total-upstream)/upstream
 meta["rede_hidrografica"]={"HYBAS_ID_exutorio":target,"fragmentos_consultados":len(p),"fragmentos_a_montante":len(rows),
   "area_soma_subbasins_km2":round(total,2),"area_up_area_km2":round(upstream,2),"diferenca_topologica_pct":round(err,4),
   "diferenca_para_32774_pct":round(100*(upstream/32774-1),4)}
 # Tolerancia topologica < 0.5%, comparação área publicação ≤ 5%.
 if err>0.5:raise RuntimeError("Falha de continuidade da rede HydroBASINS: "+str(err)+"%")
 if not 0.95<=upstream/32774<=1.05:raise RuntimeError("Area incompatível com referencia oficial "+str(upstream))
 dump("ids_montante_hybas10.json",sorted(selected))
 selected_fc=basin10.filter(ee.Filter.inList("HYBAS_ID",list(selected)))
 geom=selected_fc.geometry(maxError=ee.ErrorMargin(150)).simplify(maxError=ee.ErrorMargin(140))
 geometry=geom.getInfo()
 bs=shape(geometry)
 if not bs.is_valid:bs=bs.buffer(0)
 # Área geodésica calculada independentemente.
 geod=Geod(ellps="GRS80")
 ag=abs(geod.geometry_area_perimeter(bs)[0])/1e6
 meta["area_geodesica_km2"]=round(ag,2)
 meta["desvio_poligono_vs_UP_AREA_pct"]=round(100*(ag/upstream-1),3)
 # Area geodesica pode variar por simplificacao ~ 1%; adotar erro de 5% conservador
 if abs(ag/upstream-1)>0.05:raise RuntimeError("Area geometrica muito diferente da tabular")
 dump("BACIA_VERIFICADA_UPSTREAM_ANA_66070004.geojson",tofc([feature(bs,{"estacao":"ANA 66070004","tipo":"area contribuinte HydroBASINS L10",
  "area_upstream_km2":upstream,"area_referencia_publicada_km2":32774,"codigo_exutorio":str(target),"n_subbasins":len(rows)})]))
 # Recortar biomas oficiais ao poligono verificado e ao contexto geográfico.
 z=requests.get(IBGE_URL,timeout=(30,150),headers={"User-Agent":"Mozilla/5.0"});z.raise_for_status()
 zf=zipfile.ZipFile(io.BytesIO(z.content));shp=next(x for x in zf.namelist() if x.lower().endswith(".shp"))
 prefix=shp[:-4]
 dbf=next(x for x in zf.namelist() if x.lower()==(prefix+".dbf").lower())
 shx=next(x for x in zf.namelist() if x.lower()==(prefix+".shx").lower())
 cpg=next((x for x in zf.namelist() if x.lower()==(prefix+".cpg").lower()),None)
 enc=zf.read(cpg).decode(errors="replace").strip() if cpg else "latin1"
 reader=shapefile.Reader(shp=io.BytesIO(zf.read(shp)),dbf=io.BytesIO(zf.read(dbf)),shx=io.BytesIO(zf.read(shx)),encoding=enc)
 fields=[f[0] for f in reader.fields[1:]]
 context=box(*(bs.bounds[0]-.75,bs.bounds[1]-.75,bs.bounds[2]+.75,bs.bounds[3]+.75))
 biomes=[]
 biome_areas={}
 for rec in reader.iterShapeRecords():
  prop=dict(zip(fields,rec.record))
  label=next((str(v) for v in prop.values() if any(k in norm(v) for k in ["amazon","cerrado","pantanal","caatinga","atlantica","pampa"])),str(prop))
  g=shape(rec.shape.__geo_interface__)
  if not g.is_valid:g=g.buffer(0)
  sub=g.intersection(bs)
  if not sub.is_empty:
   area=abs(geod.geometry_area_perimeter(sub)[0])/1e6
   biome_areas[label]=biome_areas.get(label,0)+area
  geo=g.intersection(context)
  if not geo.is_empty:
   biomes.append(feature(geo.simplify(.003,preserve_topology=True),{"bioma":label,"fonte":"IBGE 2025"}))
 meta["biomas_dentro_area_contribuinte_km2"]={k:round(v,2) for k,v in biome_areas.items()}
 meta["soma_biomas_km2"]=round(sum(biome_areas.values()),2)
 dump("BIOMAS_IBGE_2025_CONTEXTO_CACERES.geojson",tofc(biomes))
 # Referencia do municipio e sede
 munjson=json.loads(Path("pesquisa_pantanal/cartografia/municipio_caceres_ibge.geojson").read_text(encoding="utf-8"))
 municipio=shape(munjson["features"][0]["geometry"])
 inter=bs.intersection(municipio)
 meta["intersecao_municipio_caceres_km2"]=round(abs(geod.geometry_area_perimeter(inter)[0])/1e6,2)
 meta["conclusao"]="Area contribuinte da estacao validada por topologia NEXT_DOWN e referencia de drenagem. Nao e limite municipal nem bacia inteira do Pantanal."
 meta["status"]="concluido"
except Exception as e:
 meta["status"]="falha_validacao";meta["erros"].append(repr(e));traceback.print_exc()
finally:
 dump("VALIDACAO_RECORTE_CACERES.json",meta)
 print(json.dumps(meta,ensure_ascii=False,indent=2,default=str)[:17000],flush=True)
 if meta.get("status")!="concluido":raise SystemExit("A delimitacao nao passou na auditoria, preservar a pesquisa sem atribuir recorte definitivo.")
