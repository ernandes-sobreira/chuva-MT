#!/usr/bin/env python3
"""Coleta dados oficiais para pesquisa do Pantanal. Executa no ramo isolado do GitHub."""
import csv, io, json, re, unicodedata, zipfile, traceback
from pathlib import Path
import requests
from openpyxl import load_workbook

ROOT=Path("pesquisa_pantanal/resultados")
ROOT.mkdir(parents=True,exist_ok=True)
WATER_URL="https://brasil.mapbiomas.org/wp-content/uploads/sites/3/2026/10/5-MAPBIOMAS-BRAZIL-WATER-ANNUAL-SURFACE-WATER-COLLECTION_5-MULTIPLE_TERRITORIES.zip"
TARGETS={
"MT":["Barão de Melgaço","Cáceres","Itiquira","Lambari do Oeste","Nossa Senhora do Livramento","Poconé","Santo Antônio de Leverger"],
"MS":["Aquidauana","Bodoquena","Corumbá","Coxim","Ladário","Miranda","Porto Murtinho","Rio Verde de Mato Grosso","Sonora"]}
summary={"fontes":{"agua":WATER_URL,"bovinos":"https://apisidra.ibge.gov.br/tabela/3939"},"erros":[]}
def req(url,timeout=120):
    r=requests.get(url,timeout=timeout,headers={"User-Agent":"Mozilla/5.0 (research Pantanal data 2026)","Accept":"*/*"})
    r.raise_for_status()
    return r
def normalize(x):
    x=str(x or "").lower()
    return "".join(c for c in unicodedata.normalize("NFD",x) if unicodedata.category(c)!="Mn").strip()
def cleaned(v):
    if v is None:return ""
    s=str(v)
    if len(s)>150:return s[:147]+"..."
    return s
try:
    r=req(WATER_URL,180)
    z=zipfile.ZipFile(io.BytesIO(r.content))
    namelist=[{"nome":x.filename,"bytes":x.file_size} for x in z.infolist() if not x.is_dir()]
    summary["zip_agua"]={"tamanho_download_bytes":len(r.content),"arquivos":namelist}
    matches=[]
    inspected=[]
    candidates=sorted(
        [x for x in z.infolist() if x.filename.lower().endswith((".xlsx",".csv"))],
        key=lambda x:(0 if any(t in normalize(x.filename) for t in ("biome","bioma","pantanal")) else 1, x.file_size))
    for inf in candidates[:30]:
        if inf.file_size>250_000_000:
            inspected.append({"nome":inf.filename,"status":"arquivo_muito_grande","bytes":inf.file_size})
            continue
        try:
            if inf.filename.lower().endswith(".xlsx"):
                wb=load_workbook(io.BytesIO(z.read(inf)),read_only=True,data_only=True)
                for ws in wb.worksheets:
                    count=0; found=0; preview=[]
                    for idx,row in enumerate(ws.iter_rows(values_only=True),1):
                        vals=[cleaned(v) for v in row[:60]]
                        if idx<=5:preview.append({"linha":idx,"valores":vals[:22]})
                        if "pantanal" in normalize(" | ".join(vals[:12])):
                            matches.append({"arquivo":inf.filename,"aba":ws.title,"linha":idx,"valores":vals[:60]})
                            found+=1
                        count+=1
                        if count>=120000:break
                    inspected.append({"arquivo":inf.filename,"aba":ws.title,"linhas_lidas":count,"pantanal_linhas":found,"amostra":preview})
                wb.close()
            else:
                bb=z.read(inf)
                txt=bb.decode("utf-8-sig",errors="replace")
                rd=csv.reader(io.StringIO(txt))
                found=0;preview=[];n=0
                for idx,row in enumerate(rd,1):
                    if idx<=5:preview.append({"linha":idx,"valores":row[:20]})
                    if "pantanal" in normalize(" | ".join(row[:12])):
                        matches.append({"arquivo":inf.filename,"aba":"csv","linha":idx,"valores":row[:60]})
                        found+=1
                    n+=1
                    if n>=120000:break
                inspected.append({"arquivo":inf.filename,"linhas_lidas":n,"pantanal_linhas":found,"amostra":preview})
        except Exception as e:
            inspected.append({"arquivo":inf.filename,"erro":str(e)})
    summary["agua_arquivos_inspecionados"]=inspected
    summary["agua_linhas_pantanal"]=len(matches)
    (ROOT/"mapbiomas_linhas_pantanal.json").write_text(json.dumps(matches,ensure_ascii=False,indent=2),encoding="utf-8")
except Exception as e:
    summary["erros"].append("mapbiomas: "+repr(e))
    traceback.print_exc()
try:
    geos={}
    for uf,names in TARGETS.items():
        loc=req("https://servicodados.ibge.gov.br/api/v1/localidades/estados/"+uf+"/municipios",45).json()
        idx={normalize(x["nome"]):str(x["id"]) for x in loc}
        for name in names:
            cod=idx.get(normalize(name))
            if not cod:raise RuntimeError("Municipio sem codigo IBGE: "+name)
            geos[cod]=(uf,name)
    codigos=",".join(geos)
    url="https://apisidra.ibge.gov.br/values/t/3939/n6/"+codigos+"/v/105/p/1985-2025/c79/2670?formato=json"
    resp=req(url,180).json()
    if not isinstance(resp,list) or len(resp)<2:raise RuntimeError("Resposta SIDRA inesperada "+str(resp)[:200])
    hd=resp[0]
    summary["sidra_metadados"]={"cabecalho":hd,"municipios":geos,"linhas":len(resp)-1,"url":url}
    placekey=next((k for k,v in hd.items() if "Munic" in str(v) and ("Cod" in normalize(v) or "Cód" in str(v))),"D1C")
    yearkey=next((k for k,v in hd.items() if ("Ano" in str(v) or "Período" in str(v)) and ("Cod" in normalize(v) or "Cód" in str(v))),"D2C")
    data={}
    for item in resp[1:]:
        try:
            cod=str(item[placekey]);year=int(str(item[yearkey]));val=int(float(str(item["V"]).replace(",",".")))
            if cod in geos and 1985<=year<=2025:data[(cod,year)]=val
        except (ValueError,TypeError,KeyError):continue
    with (ROOT/"ibge_ppm_bovinos_16_municipios_1985_2025.csv").open("w",encoding="utf-8-sig",newline="") as out:
        wr=csv.writer(out)
        wr.writerow(["ano","uf","municipio","codigo_ibge","bovinos_municipio","escala"])
        for year in range(1985,2026):
            for cod,(uf,name) in sorted(geos.items(),key=lambda x:(x[1][0],x[1][1])):
                wr.writerow([year,uf,name,cod,data.get((cod,year),""),"municipio_inteiro; nao rebanho da planicie"])
    summary["sidra_validade"]={"observacoes_extraidas":len(data),"esperadas":16*41,"anos_completos":[y for y in range(1985,2026) if sum((cod,y) in data for cod in geos)==16]}
except Exception as e:
    summary["erros"].append("SIDRA: "+repr(e))
    traceback.print_exc()
(ROOT/"relatorio_extracao.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in summary.items() if k not in ("agua_arquivos_inspecionados","zip_agua","sidra_metadados")},ensure_ascii=False,indent=2))
if not summary.get("sidra_validade") and not summary.get("agua_linhas_pantanal"):raise SystemExit("As duas fontes falharam, veja relatório.")
