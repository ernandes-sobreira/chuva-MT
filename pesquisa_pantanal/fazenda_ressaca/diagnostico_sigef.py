#!/usr/bin/env python3
"""Diagnóstico SIGEF IBAMA (somente códigos e nomes; nenhum titular)."""
from pathlib import Path
import json,requests,traceback
P=Path("pesquisa_pantanal/fazenda_ressaca")
API=[
"https://pamgia.ibama.gov.br/server/rest/services/BasesSincronizadas/lim_sigef_publico_incra_p/FeatureServer/0/query",
"https://pamgia.ibama.gov.br/server/rest/services/01_Publicacoes_Bases/lim_imovel_sigef_publico_a/MapServer/10/query"]
queries=[
"nome_area LIKE '%RESSACA%'",
"codigo_imo = '9020122782380'",
"municipio_ = 5102504 AND nome_area LIKE '%RESSACA%'",
"parcela_co LIKE '%925726ed%'",
"1=1"]
results=[]
for endpoint in API:
 for where in queries:
  try:
   params={"where":where,"outFields":"parcela_co,nome_area,codigo_imo,municipio_",
    "returnGeometry":"false","resultRecordCount":20,"f":"json"}
   r=requests.get(endpoint,params=params,timeout=(12,30),headers={"User-Agent":"Mozilla/5.0 scientific research"})
   r.raise_for_status();v=r.json()
   if v.get("error"):raise RuntimeError(str(v["error"]))
   feats=v.get("features",[])
   results.append({"endpoint":endpoint,"where":where,"n":len(feats),
    "sample":[f.get("attributes",{}) for f in feats[:10]]})
  except Exception as e:results.append({"endpoint":endpoint,"where":where,"error":repr(e)})
out=P/"DIAGNOSTICO_NOME_SIGEF.json"
out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(results,ensure_ascii=False,indent=2)[:16000])
