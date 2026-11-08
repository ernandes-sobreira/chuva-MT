#!/usr/bin/env python3
"""Persiste checkpoints e publica somente um candidato completo e revalidado.

O estado fica separado de dados/ e sobrevive a limites HTTP e falhas normais.
Uma interrupção abrupta do runner pode perder o lote local (no máximo 5 dias),
mas não perde checkpoints já commitados nem altera dados científicos do site.
"""
import argparse
import calendar
import csv
import hashlib
import io
import json
import re
import subprocess
import time
from pathlib import Path

from chirps_checkpoint import (SCHEMA, atomic_json, checkpoint_path, digest,
                               merge_state, validate_checkpoint)
from processar_chirps_v3 import completed_values

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "dados" / "meses.json"
STATE = ROOT / ".state" / "chirps-v3"
CANDIDATE = ROOT / ".work" / "chirps-v3-result.json"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True)


def validate_candidate(candidate, states):
    if candidate.get("schema") != SCHEMA:
        raise ValueError("Candidato inválido")
    ctx = candidate["context"]
    name = checkpoint_path(STATE, ctx).name
    checkpoint = validate_checkpoint(states[name], ctx)
    vals = completed_values(checkpoint)
    record = candidate["record"]
    year, month = map(int, ctx["month"].split("-"))
    whole = calendar.monthrange(year, month)[1]
    expected = {"ano": year, "mes": month, "v": vals, "n": 142,
                "preliminar": ctx["stage"] != "final", "parcial": ctx["ndays"] < whole,
                "dias_observados": ctx["ndays"], "dias_no_mes": whole,
                "colecao": "CHIRPS-v3.0-sat-official"}
    if any(record.get(k) != value for k, value in expected.items()):
        raise ValueError("Candidato não reproduz o checkpoint validado")
    if not re.fullmatch(r"[0-9a-f]{64}", str(candidate.get("previous_record_sha256", ""))):
        raise ValueError("Versão anterior não identificada")
    return ctx["month"], record


def csv_text(record):
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["CD_MUN", "ano", "mes", "chuva_mm", "fonte", "situacao"])
    for code in sorted(record["v"]):
        writer.writerow([code, record["ano"], record["mes"], record["v"][code],
                         "CHIRPS-v3.0-sat", "preliminar" if record["preliminar"] else "definitivo"])
    return buf.getvalue()


def would_regress(old, record):
    if not old or old.get("colecao") != "CHIRPS-v3.0-sat-official":
        return False
    if not old.get("preliminar") and not old.get("parcial"):
        return bool(record.get("preliminar") or record.get("parcial"))
    return bool(old.get("preliminar") and record.get("preliminar") and
                int(old.get("dias_observados") or 0) > int(record.get("dias_observados") or 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint-only", action="store_true")
    args = ap.parse_args()
    states = {}
    for path in STATE.glob("*.json"):
        obj = json.loads(path.read_text(encoding="utf-8"))
        states[path.name] = merge_state(obj, None, path.name)
    candidate = None
    if not args.checkpoint_only and CANDIDATE.exists():
        candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
        validate_candidate(candidate, states)
    if not states and candidate is None:
        print("Nenhum progresso ou resultado para publicar.")
        return
    # Captura estado/candidato em memória ANTES de atualizar a branch remota.
    for attempt in range(4):
        git("fetch", "origin", "main")
        git("reset", "--hard", "origin/main")
        paths = []
        for name, local in states.items():
            path = STATE / name
            remote = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            atomic_json(path, merge_state(local, remote, name))
            paths.append(str(path.relative_to(ROOT)))
        published = None
        if candidate is not None:
            key, record = validate_candidate(candidate, states)
            latest = json.loads(PATH.read_text(encoding="utf-8"))
            old = latest.get(key)
            geometry = ROOT / "dados" / "municipios_mt.geojson"
            geometry_hash = hashlib.sha256(geometry.read_bytes()).hexdigest() if geometry.exists() else None
            # Só altera exatamente a versão de entrada. Nunca regride atualização concorrente.
            if would_regress(old, record):
                print(f"{key}: regressão de versão/cobertura proibida. Checkpoint preservado.")
            elif geometry_hash != candidate["context"]["geometry_sha256"]:
                print(f"{key}: malha remota mudou; candidato não aplicado. Checkpoint preservado.")
            elif digest(old) != candidate["previous_record_sha256"]:
                print(f"{key}: versão remota mudou; candidato não aplicado. Checkpoint preservado.")
            else:
                latest[key] = record
                latest.setdefault("_meta", {})["ultimo_mes_chirps_v3_processado"] = key
                latest["_meta"]["ultimo_status_chirps_v3_processado"] = candidate["context"]["stage"]
                atomic_json(PATH, latest)
                csv_path = ROOT / "dados" / "mensal" / (key + ".csv")
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                csv_path.write_text(csv_text(record), encoding="utf-8")
                paths.extend([str(PATH.relative_to(ROOT)), str(csv_path.relative_to(ROOT))])
                published = key
        git("add", "--", *paths)
        changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
        if changed.returncode == 0:
            print("Estado e resultados já preservados no repositório.")
            return
        if changed.returncode != 1:
            changed.check_returncode()
        git("commit", "-m", "Publica CHIRPS v3 validado e checkpoint" if published else "Preserva checkpoint CHIRPS v3")
        try:
            git("push", "origin", "HEAD:main")
            print("PUBLICAÇÃO CONFIRMADA: " + (published or "somente checkpoint; dados do site intactos"))
            return
        except subprocess.CalledProcessError:
            if attempt == 3:
                raise RuntimeError("Publicação não confirmada após quatro tentativas; nenhum force push utilizado.")
            time.sleep(2 + attempt * 3)


if __name__ == "__main__":
    main()
