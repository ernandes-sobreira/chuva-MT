#!/usr/bin/env python3
"""Consulta inventário ANA antigo para geolocalizar estações fluviométricas.
Não inferir bacia sem conferir posição oficial, área publicada e rede de drenagem.
"""
import requests,json,xml.etree.ElementTree as ET,datetime as dt
from pathlib import Path
OUT=Path("pesquisa_pantanal/cabeceiras/resultados");OUT.mkdir(parents=True,exist_ok=True)
URL="https://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroInventario"
codes=["66071400","66072000","66055000","66065000","66070004","66090000","66120000"]
res={"time_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"endpoint":URL,"stations":[], "errors":[]}
session=requests.Session()
for code in codes:
 item={"codigo":code}
 try:
  params={"codEstDE":code,"codEstATE":code,"tpEst":"1","nmEst":"","nmRio":"",
  "codSubBacia":"","codBacia":"","nmMunicipio":"","nmEstado":"","sgResp":"","sgOper":"","telemetrica":""}
  r=session.get(URL,params=params,timeout=(20,60))
  r.raise_for_status()
  item["url"]=r.url;item["response_bytes"]=len(r.content)
  root=ET.fromstring(r.content)
  item["root"]=root.tag
  childtypes=list({x.tag.split("}")[-1] for x in root.iter()})
  item["xml_tags"]=childtypes[:80]
  found=[]
  for n in root.iter():
   if n.tag.split("}")[-1] not in ("Table","Estacao","Estacoes","HidroInventario","EstacaoInventario"):continue
   a={c.tag.split("}")[-1]:c.text for c in n}
   if code in [str(v).strip() for v in a.values()]:found.append(a)
  if not found:
   found=[{x.tag.split("}")[-1]:x.text for x in list(root)[:30]}]
  item["matches"]=found[:3]
  item["status"]="ok"
 except Exception as e:
  item["status"]="erro";item["error"]=repr(e);res["errors"].append({code:repr(e)})
 res["stations"].append(item)
 print(json.dumps({"codigo":code,"status":item["status"],"bytes":item.get("response_bytes"),"matches":item.get("matches")},ensure_ascii=False)[:1200],flush=True)
(OUT/"INVENTARIO_ANA_CABECEIRAS.json").write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding="utf8")
