#!/usr/bin/env python3
"""Comparação vazão × chuva nas nascentes da região de Cáceres.
Usa coordenada e área das estações ANA HidroInventario + HydroBASINS L10, validação <15%.
Clima: CHIRPS v2 chuva de cada bacia, total Jan–Dez e chuva de recarga Out(y-1)–Jun(y).
Recorte pela rede NEXT_DOWN, nunca pelo município ou polígono a olho.
Não extrair se exutório e área contribuinte forem discrepantes.
"""
import os,json,csv,traceback,datetime as dt,math
from pathlib import Path
import ee
P=Path("pesquisa_pantanal/cabeceiras/resultados");P.mkdir(parents=True,exist_ok=True)
inventory=json.loads((P/"INVENTARIO_ANA_CABECEIRAS.json").read_text(encoding="utf8"))
stations={x["codigo"]:x["matches"][0] for x in inventory["stations"] if x.get("matches") and "Latitude" in x["matches"][0]}
codes=["66055000","66065000","66071400","66072000","66070004"]
report={"date_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"fonte_inventario":"ANA HidroInventario",
"fonte_drenagem":"WWF/HydroSHEDS/v1/Basins/hybas_10",
"fonte_chuva":"UCSB-CHG/CHIRPS/DAILY",
"tolerancia_erro_area_hydro_vs_ana_pct":15,"stations":[],"errors":[],
"cautela":"Área ANA e HydroBASINS podem diferir por versão e posição do posto. Não selecionar polígonos apenas porque a área bate."}
cols=["codigo","rio","estacao","ano","chuva_ano_mm","chuva_recarga_out_jun_mm","area_ana_km2","area_hydro_km2","hybas_id"]
rows=[]
def write():
 with (P/"PRECIPITACAO_CABECEIRAS_CHIRPS_1985_2025.csv").open("w",newline="",encoding="utf-8-sig") as f:
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
 (P/"AUDITORIA_BACIAS_CHUVA_ANA.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf8")
try:
 key=os.environ["EE_SERVICE_ACCOUNT_KEY"].strip();credentials=json.loads(key)
 ee.Initialize(ee.ServiceAccountCredentials(credentials["client_email"],key_data=key),project=os.environ.get("EE_PROJECT") or credentials["project_id"])
 B=ee.FeatureCollection("WWF/HydroSHEDS/v1/Basins/hybas_10")
 # candidate list region, geometry omitted, obtained just once.
 params=ee.Geometry.Rectangle([-61,-18,-54,-12],proj="EPSG:4326",geodesic=False)
 allprops=[x["properties"] for x in B.filterBounds(params).select(
   ["HYBAS_ID","NEXT_DOWN","SUB_AREA","UP_AREA"],retainGeometry=False).getInfo()["features"]]
 byid={int(x["HYBAS_ID"]):x for x in allprops}
 print("Candidate L10 basins:",len(byid),flush=True)
 CH=ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select("precipitation")
 for code in codes:
  sta=stations.get(code);detail={"codigo":code,"status":"pending"}
  if not sta:
   detail["status"]="sem_inventario";report["stations"].append(detail);continue
  try:
   lat=float(sta["Latitude"]);lon=float(sta["Longitude"]);area_ana=float(sta["AreaDrenagem"])
   detail.update({"estacao":sta["Nome"],"rio":sta.get("RioNome"),"lon":lon,"lat":lat,
                  "area_ana_km2":area_ana})
   feat=B.filterBounds(ee.Geometry.Point([lon,lat])).first()
   candidate=feat.getInfo()["properties"]
   hb_id=int(candidate["HYBAS_ID"]);up_area=float(candidate["UP_AREA"])
   detail["exutorio_HYBAS_ID"]=hb_id
   detail["area_hydro_km2"]=up_area
   detail["erro_area_vs_ana_pct"]=round(100*(up_area/area_ana-1),3)
   if abs(detail["erro_area_vs_ana_pct"])>15:
    detail["status"]="nao_validado_area_15pct";report["stations"].append(detail);continue
   selected={hb_id}
   prev=-1
   while prev!=len(selected):
    prev=len(selected)
    selected.update(int(x["HYBAS_ID"]) for x in allprops if int(x.get("NEXT_DOWN") or 0) in selected)
   if not selected.issubset(set(byid)):raise ValueError("Bacia fora da região do candidato")
   total=sum(float(byid[x]["SUB_AREA"]) for x in selected)
   detail["n_subbacias"]=len(selected)
   detail["soma_areas_subbasins"]=round(total,3)
   detail["erro_conectividade_pct"]=round(100*(total/up_area-1),4)
   if abs(detail["erro_conectividade_pct"])>1.5:
    detail["status"]="nao_validado_topologia";report["stations"].append(detail);continue
   region=B.filter(ee.Filter.inList("HYBAS_ID",list(selected))).geometry(maxError=ee.ErrorMargin(250))
   def annualFeature(y):
    y=ee.Number(y).toInt()
    a=CH.filterDate(ee.Date.fromYMD(y,1,1),ee.Date.fromYMD(y.add(1),1,1)).sum().rename("pano")
    winter=CH.filterDate(ee.Date.fromYMD(y.subtract(1),10,1),ee.Date.fromYMD(y,7,1)).sum().rename("precarga")
    vals=ee.Image.cat([a,winter]).reduceRegion(
      ee.Reducer.mean(),geometry=region,scale=5566,maxPixels=1e9,tileScale=4)
    return ee.Feature(None,{"ano":y,"pano":vals.get("pano"),"precarga":vals.get("precarga")})
   features=ee.FeatureCollection(ee.List.sequence(1985,2025).map(annualFeature)).getInfo()["features"]
   extracted=[]
   for f in features:
    d=f["properties"]
    if d.get("pano") is None or d.get("precarga") is None:raise ValueError("Chuva nula em ano "+str(d["ano"]))
    extracted.append({"codigo":code,"rio":sta.get("RioNome"),"estacao":sta["Nome"],
    "ano":int(d["ano"]),"chuva_ano_mm":round(float(d["pano"]),3),
    "chuva_recarga_out_jun_mm":round(float(d["precarga"]),3),
    "area_ana_km2":area_ana,"area_hydro_km2":up_area,"hybas_id":hb_id})
   if len(extracted)!=41:raise ValueError("Ano incompleto "+str(len(extracted)))
   rows+=sorted(extracted,key=lambda d:d["ano"])
   detail["valid_years"]=41
   detail["status"]="concluido"
   print("CHIRPS",code,"area",up_area,"vs ANA",area_ana,"anos",len(extracted),flush=True)
  except Exception as exc:
   detail["status"]="erro";detail["exception"]=repr(exc);report["errors"].append({code:repr(exc)})
  report["stations"].append(detail);write()
except Exception as exc:
 report["errors"].append({"geral":repr(exc)});traceback.print_exc()
finally:
 write()
 print(json.dumps({"status":[{k:v for k,v in s.items() if k in ("codigo","status","area_ana_km2","area_hydro_km2","erro_area_vs_ana_pct","erro_conectividade_pct")} for s in report["stations"]],"n_rows":len(rows),"errors":report["errors"]},ensure_ascii=False))
 if len({r["codigo"] for r in rows})<2:raise SystemExit("Menos de duas bacias com chuva validada")
