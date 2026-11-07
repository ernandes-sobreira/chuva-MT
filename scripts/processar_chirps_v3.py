#!/usr/bin/env python3
"""CHIRPS v3: gera média espacial municipal mensal de arquivos GeoTIFF oficiais.
Usa exclusivamente o CHIRPS (preliminar ou final), nunca GSMaP.
O estágio definitivo substitui a versão preliminar após recalcular os pixels.
"""
import calendar
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds, transform as window_transform

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "dados" / "municipios_mt.geojson"
MONTHS = ROOT / "dados" / "meses.json"
STATUS = ROOT / "dados" / "status_chirps.json"
DATA = ROOT / "dados" / "mensal"
BASE = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily"
CACHE = Path("/tmp/chirps-mt")
CACHE.mkdir(parents=True, exist_ok=True)


def download(url, target):
    # Evita sobrecarregar a origem CHC; respeita Retry-After e limita tentativas.
    for attempt in range(5):
        req = Request(url, headers={"User-Agent": "Chuva-MT academic precipitation analysis (contact via GitHub ernandes-sobreira/chuva-MT)"})
        try:
            with urlopen(req, timeout=120) as src, open(target, "wb") as out:
                while True:
                    block = src.read(2 * 1024 * 1024)
                    if not block:
                        break
                    out.write(block)
            return
        except urllib.error.HTTPError as exc:
            target.unlink(missing_ok=True)
            if exc.code not in (429, 503):
                raise
            retry = exc.headers.get("Retry-After")
            pause = min(300, max(30, int(retry) if retry and retry.isdigit() else 45 * (attempt + 1)))
            print(f"CHIRPS limitou acesso (HTTP {exc.code}); tentativa {attempt+1}/5, respeitando pausa de {pause}s", flush=True)
            if attempt == 4:
                raise RuntimeError("Servidor CHIRPS limitou downloads. Arquivos municipais não foram alterados.") from exc
            time.sleep(pause)
    raise RuntimeError("Falha no download CHIRPS")


def grid_values(path, shapes, bounds):
    with rasterio.open(path) as src:
        w = from_bounds(*bounds, transform=src.transform)
        w = w.round_offsets().round_lengths()
        # Limita janela válida à grade, evitando bordas de pixel externas.
        w = w.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        arr = src.read(1, window=w, masked=True)
        trans = window_transform(w, src.transform)
        ids = rasterize(
            [(geom, idx + 1) for idx, (code, geom) in enumerate(shapes)],
            out_shape=arr.shape, transform=trans,
            fill=0, all_touched=False, dtype="uint16",
        )
        values = np.ma.filled(arr, np.nan).astype("float64")
        if src.nodata is not None:
            values[values == src.nodata] = np.nan
        ok = np.isfinite(values) & (ids > 0)
        n = len(shapes)
        sums = np.bincount(ids[ok], weights=values[ok], minlength=n + 1)
        counts = np.bincount(ids[ok], minlength=n + 1)
        return sums[1:], counts[1:]


def read_geometry():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    from shapely.geometry import shape
    from rasterio.warp import transform_geom
    entries = []
    bounds = [180., 90., -180., -90.]
    for f in geo["features"]:
        code = str(f["properties"]["CD_MUN"])
        geom = f["geometry"]
        # IBGE malha distribuída em coordenadas lon/lat
        g = shape(geom)
        if geo.get("crs", {}).get("properties", {}).get("name", "").upper().endswith("3857"):
            geom = transform_geom("EPSG:3857", "EPSG:4326", geom)
            g = shape(geom)
        minx, miny, maxx, maxy = g.bounds
        bounds = [min(bounds[0], minx), min(bounds[1], miny),
                  max(bounds[2], maxx), max(bounds[3], maxy)]
        entries.append((code, geom))
    if len(entries) != 142:
        raise RuntimeError("Esperados 142 municípios, obtidos %s" % len(entries))
    return entries, bounds


def main():
    report = json.loads(STATUS.read_text(encoding="utf-8"))
    data = json.loads(MONTHS.read_text(encoding="utf-8"))
    avail = report.get("meses", {})
    # Prioriza o mês mais recente e aceita acumulados preliminares incompletos.
    # Recalcula apenas ao chegar um novo dia ou uma versão definitiva.
    targets = []
    for key in sorted(avail, reverse=True):
        item = avail[key]
        old = data.get(key) or {}
        same_v3 = old.get("colecao") == "CHIRPS-v3.0-sat-official"
        final_done = same_v3 and not old.get("preliminar") and not old.get("parcial")
        observed = int(old.get("dias_observados") or 0) if same_v3 else 0
        year, month = map(int, key.split("-"))
        days_in_month = calendar.monthrange(year, month)[1]
        if item.get("final_completo") and not final_done:
            targets.append((key, "final", days_in_month))
        elif not final_done:
            available = int(item.get("dias_preliminar") or 0)
            # Só reprocessar se novos dias chegaram ou a fonte agora está completa.
            if available > observed or (available == days_in_month and not same_v3):
                targets.append((key, "prelim", available))
    if not targets:
        print("Nenhum mês CHIRPS v3 com dados novos para calcular.")
        return
    key, stage, ndays = targets[0]
    year, month = map(int, key.split("-"))
    whole_month = calendar.monthrange(year, month)[1]
    if not (1 <= ndays <= whole_month):
        raise RuntimeError("Contagem de dias fora do esperado")
    shapes, bounds = read_geometry()
    sums = np.zeros(len(shapes), dtype="float64")
    urlbase = f"{BASE}/{stage}/sat/{year}"
    for day in range(1, ndays + 1):
        date = f"{year}.{month:02d}.{day:02d}"
        name = f"chirps-v3.0.{'sat' if stage == 'final' else 'prelim'}.{date}.tif"
        path = CACHE / name
        print(f"{key} {stage}: {day}/{ndays} {name}", flush=True)
        download(f"{urlbase}/{name}", path)
        x, counts = grid_values(path, shapes, bounds)
        if np.any(counts == 0):
            raise RuntimeError(f"Sem pixel para {int(np.sum(counts == 0))} municípios no dia {date}; valores não publicados")
        sums += x / counts
        path.unlink(missing_ok=True)
        time.sleep(2)
    vals = {code: round(float(value), 2) for (code, _), value in zip(shapes, sums)}
    if len(vals) != 142 or not all(np.isfinite(list(vals.values()))):
        raise RuntimeError("Saída incompleta: não publicar")
    data[key] = {
        "ano": year, "mes": month, "v": vals, "n": len(vals),
        "preliminar": stage != "final", "parcial": ndays < whole_month,
        "dias_observados": ndays, "dias_no_mes": whole_month,
        "colecao": "CHIRPS-v3.0-sat-official",
        "fonte": "Climate Hazards Center CHIRPS v3.0 " + ("preliminar" if stage == "prelim" else "definitivo"),
        "atualizado_em": dt.datetime.now(dt.timezone.utc).date().isoformat(),
    }
    data.setdefault("_meta", {})["ultimo_mes_chirps_v3_processado"] = key
    data["_meta"]["ultimo_status_chirps_v3_processado"] = stage
    MONTHS.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    DATA.mkdir(exist_ok=True, parents=True)
    import csv
    with (DATA / (key + ".csv")).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["CD_MUN", "ano", "mes", "chuva_mm", "fonte", "situacao"])
        for code in sorted(vals):
            writer.writerow([code, year, month, vals[code], "CHIRPS-v3.0-sat", "preliminar" if stage == "prelim" else "definitivo"])
    print(f"PROCESSADO {key} CHIRPS v3 {stage}: {ndays}/{whole_month} dias, 142 municípios", flush=True)


if __name__ == "__main__":
    main()
