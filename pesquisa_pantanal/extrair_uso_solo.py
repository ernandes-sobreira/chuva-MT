#!/usr/bin/env python3
"""Extrai serie 1985-2025 de cobertura/pastagens da Colecao 11 do MapBiomas por bioma/UF."""
from pathlib import Path
import json,io,traceback,re,requests
from openpyxl import load_workbook
URL="https://brasil.mapbiomas.org/wp-content/uploads/sites/3/2026/08/MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE.xlsx"
ROOT=Path("pesquisa_pantanal/resultados");ROOT.mkdir(parents=True,exist_ok=True)
report={"url":URL,"erros":[],"planilhas":[],"linhas_pantanal":0}
out=[]
try:
  r=requests.get(URL,timeout=(40,200),headers={"User-Agent":"Mozilla/5.0"})
  r.raise_for_status()
  report["baixado_bytes"]=len(r.content)
  wb=load_workbook(io.BytesIO(r.content),read_only=True,data_only=True)
  for sheet in wb.worksheets:
    p={"aba":sheet.title,"linhas":0,"colunas":sheet.max_column,"cabecalhos":[],"matches":0}
    for idx,vals in enumerate(sheet.iter_rows(values_only=True),1):
      if idx<=6:
        p["cabecalhos"].append({"linha":idx,"valores":[str(v)[:70] if v is not None else "" for v in vals[:20]]})
      if any("pantanal" in str(v).lower() for v in vals[:7]):
        out.append({"aba":sheet.title,"linha":idx,"valores":[str(v) if v is not None else "" for v in vals[:70]]})
        p["matches"]+=1
      p["linhas"]+=1
      if idx>100000:break
    report["planilhas"].append(p)
  wb.close()
  report["linhas_pantanal"]=len(out)
  (ROOT/"mapbiomas_col11_pantanal_bioma_uf.json").write_text(json.dumps(out,ensure_ascii=False),encoding="utf-8")
except Exception as e:
  report["erros"].append(str(e))
  traceback.print_exc()
(ROOT/"relatorio_pastagens.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2)[:7000])
