#!/usr/bin/env python3
"""PROSPECÇÃO REAL DE VAZÕES NAS CABECEIRAS DO ALTO PARAGUAI, 1985–2025.

Pontos do inventário estadual MT (códigos antigos, exigem rechecagem) e estudo WWF.
NÃO assumir que Jauru, a jusante de Cáceres, explica cota na estação Cáceres.
Usa vazão (m³/s), não cota ou área superficial de água. Meses ausentes ficam nulos.
NívelConsistencia=1 é bruto; requer comparação com consistido=2 em etapa posterior.
"""
import requests, json, csv, math, calendar, datetime as dt, time, hashlib, traceback, io
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
from scipy.stats import kendalltau, theilslopes

OUT=Path("pesquisa_pantanal/cabeceiras/resultados");OUT.mkdir(parents=True,exist_ok=True)
API="https://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica"
# Metadados publicados em documento técnico MT; atuais e coordenadas ainda a confirmar com inventário ANA.
STATIONS=[
 ("66071300","Fazenda Salu","Jauru",1219,"cabeceira"),
 ("66071400","Água Suja","Jauru",2860,"montante"),
 ("66072000","Porto Esperidião","Jauru",5660,"saida_cabeceiras"),
 ("66055000","São José do Sepotuba","Sepotuba",8090,"afluente_provavel_montante_caceres"),
 ("66065000","Estrada MT-125","Cabaçal",3620,"afluente_provavel_montante_caceres"),
 ("66070004","Cáceres DNPVN","Paraguai",32400,"exutorio_caceres"),
 ("66090000","Descalvados","Paraguai",47100,"jusante_caceres"),
 ("66120000","Porto Conceição","Paraguai",64000,"jusante_pantanal")
]
meta={"data_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"fonte_api":API,
"estacoes_publicadas":[{"codigo":s[0],"estacao":s[1],"rio":s[2],"area_referencia_km2":s[3],"papel":s[4]} for s in STATIONS],
"fonte_codigos":"https://metadados.geo.mt.gov.br/geonetwork/srv/api/records/8fdb418a-ef00-4702-8e76-0733a5651f5d/attachments/DSEE-RH-MT-001.pdf",
"fonte_areas_atualizadas":"HidroInventario ANA 2026: pesquisa_pantanal/cabeceiras/resultados/INVENTARIO_ANA_CABECEIRAS.json",
"fonte_jauru_wwf":"https://wwfbrnew.awsassets.panda.org/downloads/wwf-brasil_o_valor_da_restauracao.pdf",
"aviso":"A estação Porto Esperidião fica na bacia do Jauru e NÃO é considerada entrada a montante da estação Cáceres; há tributários a jusante.",
"metodo":"MediaDiaria=1; preferir consistência 2 (consistido) para mesma data, senão 1 (bruto), preservando os níveis; status vazio/1; 20 dias para mês, 300 dias para ano, 105 dias secos. Séries mistas devem ser auditadas.",
"fontes_migracao":["https://www.snirh.gov.br/hidroweb/acesso-api","https://telemetriaws1.ana.gov.br/Dados.aspx"],
"erros":[],"estacoes":[]}
SESSION=requests.Session();SESSION.headers.update({"User-Agent":"Mozilla/5.0 hydrology scientific reproducibility"})
def csvout(file,rows,fields):
 with (OUT/file).open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def station_data(code):
 params={"codEstacao":code,"dataInicio":"01/01/1985","dataFim":"31/12/2025",
         "tipoDados":3,"nivelConsistencia":1}
 resp=SESSION.get(API,params=params,timeout=(30,140));resp.raise_for_status()
 root=ET.fromstring(resp.content)
 if root.tag.split("}")[-1]!="DataTable":raise ValueError("ANA HTTP result not DataTable: "+root.tag)
 rows={};level={};errors=Counter();countrows=0
 for node in root.iter():
  if node.tag.split("}")[-1]!="SerieHistorica":continue
  rec={a.tag.split("}")[-1]:(a.text or "").strip() for a in node}
  if rec.get("EstacaoCodigo")!=code:
   errors["another_station"]+=1;continue
  if rec.get("MediaDiaria")!="1":
   errors["not_daily"]+=1;continue
  consistencia=rec.get("NivelConsistencia")
  if consistencia not in ("1","2"):
   errors["nivel_desconhecido"]+=1;continue
  errors["series_mensais_nivel_"+consistencia]+=1
  textdate=rec.get("DataHora","")[:10]
  try:year,month=map(int,textdate[:7].split("-"))
  except (ValueError,TypeError):errors["wrong_date"]+=1;continue
  if year<1985 or year>2025:continue
  countrows+=1
  for day in range(1,calendar.monthrange(year,month)[1]+1):
   v=rec.get(f"Vazao{day:02d}","")
   flag=rec.get(f"Vazao{day:02d}Status","")
   if flag not in ("","1"):
    errors["status_"+str(flag)]+=1;continue
   if not v:continue
   try:flow=float(v.replace(",","."))
   except ValueError:errors["non_numeric"]+=1;continue
   if not math.isfinite(flow) or not 0<=flow<=100000:
    errors["invalid_flow"]+=1;continue
   daystring=f"{year}-{month:02d}-{day:02d}"
   if daystring in rows:
    if abs(rows[daystring]-flow)>1e-8:
     errors["duplicate_diff"]+=1
    elif level[daystring]==consistencia:
     errors["duplicate_identical"]+=1
    # Mesmo dia pode existir em bruto (1) e consistido (2). Selecionar 2.
    if int(level[daystring])>=int(consistencia):
     continue
   rows[daystring]=flow
   level[daystring]=consistencia
 errors["dias_selecionados_consistidos_2"]=sum(x=="2" for x in level.values())
 errors["dias_selecionados_brutos_1"]=sum(x=="1" for x in level.values())
 return rows,level,resp.url,len(resp.content),hashlib.sha256(resp.content).hexdigest(),dict(errors),countrows
monthly=[];annual=[];daily=[]
for code,name,river,area,role in STATIONS:
 desc={"codigo":code,"nome":name,"rio":river,"ref_area_km2":area,"papel":role,"status":"processing"}
 try:
  values,levels,url,length,sha,issues,n_series=station_data(code)
  desc.update({"api_url":url,"response_bytes":length,"sha256":sha,"n_month_records":n_series,
               "n_daily":len(values),"issues":issues})
  for iso,q in sorted(values.items()):
   daily.append({"codigo":code,"data":iso,"vazao_m3_s":round(q,5),"nivel_consistencia":levels[iso]})
  years=set()
  for year in range(1985,2026):
   vv=[]
   dry=[]
   for month in range(1,13):
    ms=[values[f"{year}-{month:02d}-{day:02d}"] for day in range(1,calendar.monthrange(year,month)[1]+1)
        if f"{year}-{month:02d}-{day:02d}" in values]
    good=len(ms)>=20
    if month in (7,8,9,10):dry.extend(ms)
    if good:vv.extend(ms)
    monthly.append({"codigo":code,"estacao":name,"rio":river,"ano":year,"mes":month,
     "n_dias":len(ms),"q_media_m3_s":round(float(np.mean(ms)),4) if good else "",
     "q_min_m3_s":round(min(ms),4) if good else "",
     "q_max_m3_s":round(max(ms),4) if good else "",
     "q90_m3_s":round(float(np.percentile(ms,10)),4) if good else ""})
   all_year=[flow for d,flow in values.items() if d[:4]==str(year)]
   nfull=len(all_year)
   good=(nfull>=300)
   days=366 if calendar.isleap(year) else 365
   q=float(np.mean(all_year)) if good else None
   qd=float(np.mean(dry)) if len(dry)>=105 else None
   q90=float(np.percentile(all_year,10)) if good else None
   rec={"codigo":code,"estacao":name,"rio":river,"ano":year,
         "dias_ano":nfull,"dias_seca_jul_out":len(dry),
         "q_media_m3_s":round(q,4) if q is not None else "",
         "q_seca_jul_out_m3_s":round(qd,4) if qd is not None else "",
         "q90_m3_s":round(q90,4) if q90 is not None else "",
         "q_especifica_L_s_km2":round(q*1000/area,4) if q is not None and area else "",
         "defluvio_mm_ano":round(q*86400*days/(1000*area),3) if q is not None and area else "",
         "volume_anual_km3":round(q*86400*days/1e9,5) if q is not None else ""}
   annual.append(rec)
  valid=[r for r in annual if r["codigo"]==code and r["q_media_m3_s"]!=""]
  years=[r["ano"] for r in valid]
  if len(years)>=15:
   yvals=np.array([r["q_media_m3_s"] for r in valid],dtype=float)
   tau,p=kendalltau(years,yvals)
   slope,intercept,lo,hi=theilslopes(yvals,years,0.95)
   desc["annual_trend"]={"valid_years":len(years),"period":[years[0],years[-1]],
       "tau":float(tau),"p_kendall":float(p),"theil_sen_q_m3_s_year":float(slope),
       "slope_CI95":[float(lo),float(hi)]}
  else:desc["annual_trend"]={"valid_years":len(years)}
  desc["status"]="extraido"
 except Exception as e:
  desc["status"]="falhou";desc["erro"]=repr(e);meta["erros"].append({"station":code,"error":repr(e)})
 meta["estacoes"].append(desc)
 print(json.dumps({"estacao":code,"status":desc["status"],"n_daily":desc.get("n_daily"),
                   "anos_validos":desc.get("annual_trend",{}).get("valid_years"),"erro":desc.get("erro")},ensure_ascii=False),flush=True)
 csvout("ANA_CABECEIRAS_VAZAO_DIARIA_1985_2025.csv",daily,["codigo","data","vazao_m3_s","nivel_consistencia"])
 csvout("ANA_CABECEIRAS_VAZAO_MENSAL_1985_2025.csv",monthly,
        ["codigo","estacao","rio","ano","mes","n_dias","q_media_m3_s","q_min_m3_s","q_max_m3_s","q90_m3_s"])
 csvout("ANA_CABECEIRAS_VAZAO_ANUAL_1985_2025.csv",annual,
        ["codigo","estacao","rio","ano","dias_ano","dias_seca_jul_out","q_media_m3_s","q_seca_jul_out_m3_s",
         "q90_m3_s","q_especifica_L_s_km2","defluvio_mm_ano","volume_anual_km3"])
 (OUT/"RELATORIO_PROSPECCAO_ANA.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps({"status":"ok" if any(x["status"]=="extraido" for x in meta["estacoes"]) else "erro",
"total_stations":len(meta["estacoes"]),"successful":sum(x["status"]=="extraido" for x in meta["estacoes"]),
"st_years":[(x["codigo"],x.get("annual_trend",{}).get("valid_years")) for x in meta["estacoes"]]},ensure_ascii=False))
if sum(x["status"]=="extraido" and x.get("annual_trend",{}).get("valid_years",0)>=20 for x in meta["estacoes"])<2:
 raise SystemExit("Par insuficiente de séries históricas - não produzir conclusões sem estação de montante e jusante")
