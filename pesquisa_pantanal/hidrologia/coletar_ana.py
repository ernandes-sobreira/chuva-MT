#!/usr/bin/env python3
"""Extração verificável: cotas médias diárias ANA em Cáceres; tentativa de série de vazões.
NÃO mistura leituras da Marinha e níveis da ANA.
Dados somente observados; sem imputação.
"""
import csv, collections, datetime as dt, hashlib, io, json, math, os, re, traceback
import urllib.request, urllib.parse, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path("pesquisa_pantanal/hidrologia/resultados")
ROOT.mkdir(parents=True,exist_ok=True)
SOURCE="https://raw.githubusercontent.com/ernandes-sobreira/cota-rio-paraguai/main/data/history-ana.csv"
PROVENANCE="https://raw.githubusercontent.com/ernandes-sobreira/cota-rio-paraguai/main/data/history-provenance.json"
ANA="https://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica"
STATION="66070004"
META={"fonte_nivel":SOURCE,"fonte_procedencia":PROVENANCE,"fonte_vazao":ANA,
      "estacao":"Cáceres","codigo_ana":STATION,"erros":[],"limites":"Cota e vazao nao equivalentes; nulos preservados.",
      "data_consulta_utc":dt.datetime.now(dt.timezone.utc).isoformat()}
def load(url,timeout=120):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (Pantanal scientific analysis; research source)","Accept":"*/*"})
 with urllib.request.urlopen(req,timeout=timeout) as res:return res.read()
def write_csv(fn,fieldnames,rows):
 with (ROOT/fn).open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fieldnames,extrasaction="ignore");w.writeheader();w.writerows(rows)
def month_days(year,month):
 import calendar
 return calendar.monthrange(year,month)[1]
def parse_flow(xml):
 root=ET.fromstring(xml)
 if root.tag.rsplit("}",1)[-1]!="DataTable":raise ValueError("Tipo de resposta ANA inesperado: "+root.tag)
 daily={}
 issue=collections.Counter()
 for n in root.iter():
  if n.tag.rsplit("}",1)[-1]!="SerieHistorica":continue
  v={c.tag.rsplit("}",1)[-1]:(c.text or "").strip() for c in n}
  if v.get("EstacaoCodigo")!=STATION:continue
  if v.get("MediaDiaria")!="1":continue
  if v.get("NivelConsistencia") not in ["1","2"]:continue
  stamp=v.get("DataHora","")[:10]
  if not re.fullmatch(r"\d{4}-\d\d-\d\d",stamp):continue
  y,m=map(int,stamp[:7].split("-"))
  for d in range(1,month_days(y,m)+1):
   s=v.get("Vazao%02d"%d,"")
   flag=v.get("Vazao%02dStatus"%d,"")
   if flag not in ["","1"]:issue["bad_status_"+flag]+=1;continue
   if not s:continue
   try:x=float(s.replace(",","."))
   except ValueError:issue["not_numeric"]+=1;continue
   if not math.isfinite(x) or x<0 or x>100000:issue["out_of_range"]+=1;continue
   date=dt.date(y,m,d).isoformat()
   if not "1985-01-01"<=date<="2025-12-31":continue
   if date in daily and daily[date]!=x:issue["duplicate_conflict"]+=1;continue
   daily[date]=x
 return daily,dict(issue)
try:
 raw=load(SOURCE)
 provenance=json.loads(load(PROVENANCE).decode("utf-8-sig"))
 digest=hashlib.sha256(raw).hexdigest()
 expected=provenance.get("output_sha256")
 if expected and digest!=expected:
  raise ValueError("CHECKSUM histórico ANA divergente: "+digest+" esperado "+expected)
 META["sha256_arquivo_ana"]=digest
 META["sha256_verificado"]=bool(expected)
 META["procedencia_ana"]=provenance["stations"]["Cáceres"]
 rd=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
 daily={}
 for r in rd:
  if r.get("station")!="Cáceres":continue
  if not re.fullmatch(r"\d{4}-\d\d-\d\d",r.get("date_str","")):continue
  if not "1985-01-01"<=r["date_str"]<="2025-12-31":continue
  if r.get("daily_mean")!="1" or r.get("consistency")!="1":continue
  if r.get("source_status") not in ("","1"):continue
  x=float(r["cota_m"])
  if not math.isfinite(x) or not -10<=x<=30:continue
  if r["date_str"] in daily and daily[r["date_str"]]!=x:raise ValueError("Duplicata conflitante: "+r["date_str"])
  daily[r["date_str"]]=x
 META["n_dias_cota_1985_2025"]=len(daily)
 years=range(1985,2026)
 monthly=[]
 for y in years:
  for m in range(1,13):
   values=[daily[dt.date(y,m,d).isoformat()] for d in range(1,month_days(y,m)+1)
           if dt.date(y,m,d).isoformat() in daily]
   n=len(values)
   monthly.append({"ano":y,"mes":m,"data":f"{y}-{m:02d}",
     "cota_media_m":round(sum(values)/n,4) if n>=20 else "",
     "cota_max_m":round(max(values),4) if n>=20 else "",
     "cota_min_m":round(min(values),4) if n>=20 else "",
     "n_dias":n,"dias_mes":month_days(y,m),"cobertura_pct":round(100*n/month_days(y,m),1),
     "cota_media_sem_filtro_m":round(sum(values)/n,4) if n else ""})
 write_csv("cota_mensal_ana_caceres_1985_2025.csv",
 ["ano","mes","data","cota_media_m","cota_max_m","cota_min_m","n_dias","dias_mes","cobertura_pct","cota_media_sem_filtro_m"],monthly)
 annual=[]
 for y in years:
  v=[v for ds,v in daily.items() if ds.startswith(str(y)+"-")]
  valid_months=[r for r in monthly if r["ano"]==y and r["cota_media_m"]!=""]
  annual.append({"ano":y,"n_dias":len(v),"n_meses_validos":len(valid_months),
       "cota_media_anual_m":round(sum(v)/len(v),4) if len(v)>=300 and len(valid_months)>=10 else "",
       "cota_max_anual_m":round(max(v),4) if len(v)>=300 and len(valid_months)>=10 else "",
       "cota_min_anual_m":round(min(v),4) if len(v)>=300 and len(valid_months)>=10 else ""})
 write_csv("cota_anual_ana_caceres_1985_2025.csv",
 ["ano","cota_media_anual_m","cota_max_anual_m","cota_min_anual_m","n_dias","n_meses_validos"],annual)
 META["meses_validos_cota"]=sum(r["cota_media_m"]!="" for r in monthly)
 META["anos_validos_cota"]=sum(r["cota_media_anual_m"]!="" for r in annual)
 META["cobertura_por_ano"]=[{"ano":r["ano"],"n_dias":r["n_dias"],"n_meses_validos":r["n_meses_validos"]} for r in annual]
 print("COTA DATASET: "+json.dumps({k:META[k] for k in ["n_dias_cota_1985_2025","meses_validos_cota","anos_validos_cota"]}),flush=True)
 # Historical flow: independent check of the legacy ANA station source, not inferred from stage.
 try:
  params=dict(codEstacao=STATION,dataInicio="01/01/1985",dataFim="31/12/2025",tipoDados=3,nivelConsistencia=1)
  url=ANA+"?"+urllib.parse.urlencode(params)
  body=load(url,95)
  META["vazao_resposta_bytes"]=len(body)
  META["vazao_sha256"]=hashlib.sha256(body).hexdigest()
  flow,issues=parse_flow(body)
  META["vazao_n_dias"]=len(flow)
  META["vazao_pendencias"]=issues
  mmflow=[]
  for y in years:
   for m in range(1,13):
    vv=[flow[dt.date(y,m,d).isoformat()] for d in range(1,month_days(y,m)+1)
        if dt.date(y,m,d).isoformat() in flow]
    n=len(vv)
    mmflow.append({"ano":y,"mes":m,"vazao_media_m3_s":round(sum(vv)/n,3) if n>=20 else "",
     "vazao_max_m3_s":round(max(vv),3) if n>=20 else "","n_dias_vazao":n})
  write_csv("vazao_mensal_ana_caceres_1985_2025.csv",["ano","mes","vazao_media_m3_s","vazao_max_m3_s","n_dias_vazao"],mmflow)
  META["meses_validos_vazao"]=sum(r["vazao_media_m3_s"]!="" for r in mmflow)
  META["vazao_status"]="consulta respondida com dados verificados" if META["meses_validos_vazao"] else "consulta retornou sem dados mensais suficientes"
 except Exception as exc:
  META["vazao_status"]="fonte indisponivel ou resposta nao elegivel; nao interpolado"
  META["erros"].append("vazao_ANA: "+repr(exc))
except Exception as exc:
 META["erros"].append("FALHA_ANA_COTA: "+repr(exc))
 traceback.print_exc()
finally:
 (ROOT/"relatorio_integridade_ana.json").write_text(json.dumps(META,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
 print(json.dumps({k:v for k,v in META.items() if k not in ["procedencia_ana","cobertura_por_ano"]},indent=2,ensure_ascii=False,default=str))
 if META.get("n_dias_cota_1985_2025",0)<5000:raise SystemExit("N de dias cota insuficiente")
