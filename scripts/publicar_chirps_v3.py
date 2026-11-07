#!/usr/bin/env python3
"""Publica apenas meses CHIRPS v3 calculados, mesclando com a branch remota.

Evita rebase conflitante quando a atualização mensal legada escreve no mesmo
dados/meses.json simultaneamente. Não altera meses não recalculados.
"""
import csv
import json
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
PATH=ROOT/"dados"/"meses.json"
CSV=ROOT/"dados"/"mensal"


def git(*args):
    subprocess.run(["git",*args],cwd=ROOT,check=True)


def main():
    generated=json.loads(PATH.read_text(encoding="utf-8"))
    changes={k:v for k,v in generated.items() if k!="_meta" and
             isinstance(v,dict) and v.get("colecao")=="CHIRPS-v3.0-sat-official"}
    if not changes:
        print("Nenhum mês CHIRPS v3 para publicar.")
        return
    # Preserve CSVs do processamento antes de atualizar HEAD.
    csvs={k:(CSV/(k+".csv")).read_text(encoding="utf-8") for k in changes
          if (CSV/(k+".csv")).exists()}
    for attempt in range(4):
        git("fetch","origin","main")
        git("reset","--hard","origin/main")
        latest=json.loads(PATH.read_text(encoding="utf-8"))
        real_changes={}
        for k,v in changes.items():
            old=latest.get(k,{})
            # Nunca trocar o definitivo CHIRPS v3 por preliminar.
            if old.get("colecao")=="CHIRPS-v3.0-sat-official" and not old.get("preliminar") and v.get("preliminar"):
                continue
            if old.get("colecao")=="CHIRPS-v3.0-sat-official" and old.get("preliminar") and v.get("preliminar") and int(old.get("dias_observados") or 0)>int(v.get("dias_observados") or 0):
                continue
            if old!=v:
                latest[k]=v
                real_changes[k]=v
        if not real_changes:
            print("Os meses CHIRPS v3 já estão publicados.")
            return
        latest.setdefault("_meta",{})["ultimo_mes_chirps_v3_processado"]=max(real_changes)
        latest["_meta"]["ultimo_status_chirps_v3_processado"]=(
            "prelim" if real_changes[max(real_changes)].get("preliminar") else "final")
        PATH.write_text(json.dumps(latest,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        for k in real_changes:
            if k in csvs:
                (CSV/(k+".csv")).write_text(csvs[k],encoding="utf-8")
        git("add","dados/meses.json","dados/mensal")
        git("commit","-m","Publica CHIRPS v3 municipal com mesclagem segura")
        try:
            git("push","origin","HEAD:main")
            print("PUBLICAÇÃO CONFIRMADA:",", ".join(sorted(real_changes)))
            return
        except subprocess.CalledProcessError:
            print("Concorrência na publicação. Tentativa",attempt+2,flush=True)
            time.sleep(2+attempt*3)
    raise RuntimeError("Quatro tentativas de publicação falharam; nenhum force push utilizado.")


if __name__=="__main__":
    main()
