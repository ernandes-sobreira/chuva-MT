#!/usr/bin/env python3
"""Gera um ano de CHIRPS diario para os 142 municipios.
Backfill incremental: um ano por execução; anos futuros entram automaticamente.
Nao fabrica dias faltantes e nao mistura GSMaP com CHIRPS.
"""
import argparse
import calendar
import datetime as dt
import json
import os
from pathlib import Path

import ee

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "dados" / "chirps_diario"
GEO = ROOT / "dados" / "municipios_mt.geojson"
COL = os.getenv("CHIRPS_COLECAO", "UCSB-CHC/CHIRPS/V3/DAILY_SAT")
SCALE = 5566
BEGIN = 1996


def auth():
    key = os.getenv("EE_SERVICE_ACCOUNT_KEY", "").strip()
    if not key:
        raise RuntimeError("Falta EE_SERVICE_ACCOUNT_KEY em GitHub Actions Secrets")
    info = json.loads(key)
    creds = ee.ServiceAccountCredentials(info["client_email"], key_data=key)
    ee.Initialize(creds, project=os.getenv("EE_PROJECT") or info["project_id"])


def features():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    feats = [
        {"type": "Feature", "geometry": f["geometry"],
         "properties": {"CD_MUN": str(f["properties"]["CD_MUN"])}}
        for f in geo["features"]
    ]
    if len(feats) != 142:
        raise RuntimeError("Geometria municipal inesperada: %s" % len(feats))
    return ee.FeatureCollection({"type": "FeatureCollection", "features": feats})


def newest_date():
    ms = ee.ImageCollection(COL).aggregate_max("system:time_start").getInfo()
    if ms is None:
        raise RuntimeError("CHIRPS sem imagens: " + COL)
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()


def run_year(year, end, fc):
    path = DEST / (str(year) + ".json")
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    days = old.get("dias", {})
    num_added = 0
    for month in range(1, 13):
        first = dt.date(year, month, 1)
        if first > end:
            break
        last = min(dt.date(year, month, calendar.monthrange(year, month)[1]), end)
        # somente datas nao processadas; atualizar ultimos dias do ano atual
        todo = [first + dt.timedelta(days=i) for i in range((last-first).days+1)
                if (first + dt.timedelta(days=i)).isoformat() not in days]
        if not todo:
            continue
        # Lotes curtos para evitar exceder limites do getInfo no Earth Engine.
        for start in range(0, len(todo), 5):
            batch = todo[start:start+5]
            collection = ee.ImageCollection(COL).filterDate(batch[0].isoformat(), (batch[-1] + dt.timedelta(days=1)).isoformat())
            available = set(collection.aggregate_array("system:time_start").getInfo())
            for date in batch:
                stamp = int(dt.datetime(date.year, date.month, date.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
                if stamp not in available:
                    print("Sem imagem", date, flush=True)
                    continue
                img = ee.Image(collection.filterDate(date.isoformat(), (date + dt.timedelta(days=1)).isoformat()).first()).select("precipitation")
                reduced = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=SCALE, tileScale=4)
                data = reduced.select(["CD_MUN", "mean"], retainGeometry=False).getInfo()["features"]
                vals = {str(x["properties"]["CD_MUN"]): round(float(x["properties"]["mean"]), 2)
                        for x in data if x["properties"].get("mean") is not None}
                if len(vals) != 142:
                    print("Descartando dia incompleto", date, len(vals), flush=True)
                    continue
                days[date.isoformat()] = vals
                num_added += 1
            # preserva progresso se houver interrupcao
            DEST.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"_meta": {"fonte": COL, "ano": year,
                        "verificado_em": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "dias": len(days), "ultimo_dia_fonte": end.isoformat()},
                        "dias": dict(sorted(days.items()))}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("Ano", year, "dias", len(days), "novos", num_added, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int)
    args = parser.parse_args()
    auth()
    end = newest_date()
    DEST.mkdir(parents=True, exist_ok=True)
    year_now = end.year
    if args.ano:
        year = args.ano
    else:
        # Primeiro o ano atual e o anterior; depois volta no tempo.
        choices = [year_now, year_now - 1] + list(range(year_now - 2, BEGIN - 1, -1))
        year = None
        for y in choices:
            p = DEST / (str(y)+".json")
            if not p.exists():
                year = y
                break
            doc = json.loads(p.read_text(encoding="utf-8"))
            maximum = min(end, dt.date(y, 12, 31))
            if y == end.year and (not doc.get("_meta") or doc["_meta"].get("ultimo_dia_fonte") != end.isoformat()):
                year = y
                break
        if year is None:
            print("Todos os anos já processados. Última data da fonte:", end)
            return
    if year < BEGIN or year > end.year:
        raise RuntimeError("Ano fora da janela CHIRPS suportada: " + str(year))
    print("Processando CHIRPS", COL, "ano", year, "ate", end, flush=True)
    run_year(year, end, features())


if __name__ == "__main__":
    main()
