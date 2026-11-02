#!/usr/bin/env python3
"""Piloto Fazenda Ressaca, Cáceres (MT). Busca perímetros oficiais de parcelas SIGEF
por código público via espelho geoespacial IBAMA. Não consulta titulares.
Imóvel pode ter mais de uma inscrição CAR ou parcelamento; representar APENAS a união
das parcelas certificadas associadas ao imóvel SNCR 9020122782380. Recorte legal
de 2025 não implica que tenha permanecido idêntico em 1985.
"""
from pathlib import Path
import json, traceback, time
import requests
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from pyproj import Geod
OUT=Path("pesquisa_pantanal/fazenda_ressaca");OUT.mkdir(parents=True,exist_ok=True)
API="https://pamgia.ibama.gov.br/server/rest/services/BasesSincronizadas/lim_sigef_publico_incra_p/FeatureServer/0/query"
ALT="https://pamgia.ibama.gov.br/server/rest/services/01_Publicacoes_Bases/lim_imovel_sigef_publico_a/MapServer/10/query"
UUID=[
"925726ed-78a3-4df1-8965-211bf6f8a71d",
"ab22d616-c010-4beb-8058-834eec0e14d5",
"6b53a2fa-4e2a-4aab-8264-7dc223430c7e",
"1f5f8d41-5a03-49de-9515-7f3673a0f3f2",
]
report={"nome":"Fazenda Ressaca","municipio":"Cáceres/MT",
  "codigo_imovel_sncr":"9020122782380","fonte_SIGEF":"INCRA, SIGEF Público espelhado por IBAMA",
  "fonte_vinculo_uuid":"https://www.registrorural.com.br/imoveis/9020122782380/",
  "identificadores_parcelas":UUID,
  "cadastro_CAR_comparacao":"MT-5102504-7C29B983D23F4E47B31AE9D354DB836A",
  "observacao":"CAR citado possui 25.997 ha, SIGEF 4 parcelas ~33.680 ha e CAFIR ~35.843 ha; não tratá-los como limites intercambiáveis.",
  "erros":[],"parcelas":[]}
geod=Geod(ellps="GRS80")
features=[]
try:
 for uid in UUID:
  result=None; failures=[]
  for base in [API,ALT]:
   for where in [f"parcela_co = '{uid}'",f"parcela_co LIKE '{uid}%'"]:
    try:
     resp=requests.get(base,params={"where":where,"outFields":"parcela_co,nome_area,codigo_imo,municipio_,objectid",
           "returnGeometry":"true","outSR":4326,"f":"geojson"},timeout=(20,85),
           headers={"User-Agent":"Mozilla/5.0 scientific reproduction Pantanal"})
     resp.raise_for_status()
     data=resp.json()
     if data.get("error"):raise ValueError(str(data["error"]))
     if len(data.get("features",[]))!=1:raise ValueError("Unexpected match count "+str(len(data.get("features",[]))))
     ft=data["features"][0]
     if str(ft["properties"].get("parcela_co","")).lower()!=uid.lower():raise ValueError("Código de parcela não coincide")
     if not ft.get("geometry"):raise ValueError("Geometria faltante")
     result={"ft":ft,"fonte":base,"where":where}
     break
    except Exception as e:failures.append({"endpoint":base,"query":where,"error":repr(e)})
   if result:break
  if not result:
   report["erros"].append({"uuid":uid,"falhas":failures})
   continue
  geom=shape(result["ft"]["geometry"])
  if not geom.is_valid:geom=geom.buffer(0)
  area=abs(geod.geometry_area_perimeter(geom)[0])/10000
  pr=result["ft"].get("properties",{})
  report["parcelas"].append({"codigo":uid,"nome_area":pr.get("nome_area"),
    "codigo_imovel":pr.get("codigo_imo"),"municipio_id":pr.get("municipio_"),
    "area_geodesica_ha":round(area,3),"origem":result["fonte"],
    "bbox":list(map(lambda x:round(x,5),geom.bounds))})
  features.append({"type":"Feature","geometry":mapping(geom),
       "properties":{"uuid_SIGEF":uid,"nome_area":pr.get("nome_area"),"codigo_imovel":pr.get("codigo_imo"),
        "area_geo_ha":round(area,3),"origem_SIGEF":result["fonte"]}})
 if len(features)!=len(UUID):raise RuntimeError("Perímetros incompletos: "+str(len(features))+"/"+str(len(UUID)))
 merged=unary_union([shape(f["geometry"]) for f in features])
 if not merged.is_valid:merged=merged.buffer(0)
 total=abs(geod.geometry_area_perimeter(merged)[0])/10000
 gross=sum(p["area_geodesica_ha"] for p in report["parcelas"])
 report["area_uniao_ha"]=round(total,2)
 report["area_soma_ha"]=round(gross,2)
 report["percent_interseccao"] = round(100*(gross-total)/gross,3)
 report["bbox"]=list(map(lambda x:round(x,6),merged.bounds))
 # Area 33,680 ha SIGEF reported in public CAFIR snapshot, but do not require exact (difference may be version or new polygon)
 if not (26000<=total<=42000):
  raise RuntimeError(f"Área SIGEF inesperada {total:.1f} ha, revisar parcelas")
 if report["percent_interseccao"]>2:raise RuntimeError("Sobreposição >=2%, revisar cadastro")
 (OUT/"fazenda_ressaca_parcelas_SIGEF_INCRA.geojson").write_text(json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False),encoding="utf-8")
 (OUT/"fazenda_ressaca_uniao_SIGEF.geojson").write_text(json.dumps({"type":"FeatureCollection","features":[{"type":"Feature","geometry":mapping(merged),
    "properties":{"nome":"Fazenda Ressaca (união de quatro parcelas SIGEF)","area_geo_ha":round(total,2),"natureza":"base SIGEF, ano de referência 2025; verificar histórico"}}]},ensure_ascii=False),encoding="utf-8")
 report["status"]="geometria_oficial_obtida"
except Exception as e:
 report["status"]="parcial_falha";report["erros"].append(repr(e));traceback.print_exc()
finally:
 (OUT/"AUDITORIA_PERIMETRO_SIGEF.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False,indent=2)[:15000],flush=True)
 if report["status"]!="geometria_oficial_obtida":raise SystemExit("Perímetro NÃO confirmado, recusar atribuição de mudança à fazenda.")
