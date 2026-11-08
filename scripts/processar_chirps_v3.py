#!/usr/bin/env python3
"""CHIRPS v3: gera média espacial municipal mensal de arquivos GeoTIFF oficiais.
Usa exclusivamente o CHIRPS (preliminar ou final), nunca GSMaP.
O estágio definitivo substitui a versão preliminar após recalcular os pixels.
"""
import calendar
import hashlib
import tempfile
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
from pathlib import Path
from urllib.request import Request, urlopen

from chirps_checkpoint import (ALGORITHM, SCHEMA, MAX_NEW_FILES, MIN_INTERVAL_SECONDS,
    DeferredDownload, atomic_json, checkpoint_path, defer_origin, digest, iso,
    load_checkpoint, load_control, mark_request, may_request, now_utc, parse_time,
    source_url, validate_checkpoint)


ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "dados" / "municipios_mt.geojson"
MONTHS = ROOT / "dados" / "meses.json"
STATUS = ROOT / "dados" / "status_chirps.json"
DATA = ROOT / "dados" / "mensal"
BASE = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily"
STATE = ROOT / ".state" / "chirps-v3"
CANDIDATE = ROOT / ".work" / "chirps-v3-result.json"


def download(url, target):
    """Uma tentativa, sem insistir após 429/503; pausa também vale entre execuções."""
    control = load_control(STATE)
    if not may_request(STATE):
        if control.get("reason") == "origin_rate_limit":
            raise DeferredDownload("Origem em pausa até " + control["not_before"])
        delay = (parse_time(control["not_before"]) - now_utc()).total_seconds()
        if delay > 0:
            time.sleep(delay)
    if not may_request(STATE):
        raise DeferredDownload("Pausa da origem ainda não terminou")
    mark_request(STATE)
    req = Request(url, headers={"User-Agent": "Chuva-MT academic precipitation analysis (contact via GitHub ernandes-sobreira/chuva-MT)"})
    try:
        with urlopen(req, timeout=120) as src, open(target, "wb") as out:
            while True:
                block = src.read(2 * 1024 * 1024)
                if not block:
                    break
                out.write(block)
    except urllib.error.HTTPError as exc:
        target.unlink(missing_ok=True)
        if exc.code in (429, 503):
            until = defer_origin(STATE, exc.headers.get("Retry-After") if exc.headers else None, exc.code)
            raise DeferredDownload(f"CHIRPS HTTP {exc.code}: progresso preservado; não solicitar antes de {iso(until)}") from exc
        raise
    except Exception:
        target.unlink(missing_ok=True)
        raise


def grid_values(path, shapes, bounds):
    import numpy as np
    import rasterio
    from rasterio.features import rasterize
    from rasterio.windows import from_bounds, transform as window_transform
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


def choose_target(report, data):
    # Mantém a prioridade atual: mês recente, final antes de preliminar.
    for key in sorted(report.get("meses", {}), reverse=True):
        item, old = report["meses"][key], data.get(key) or {}
        same_v3 = old.get("colecao") == "CHIRPS-v3.0-sat-official"
        final_done = same_v3 and not old.get("preliminar") and not old.get("parcial")
        observed = int(old.get("dias_observados") or 0) if same_v3 else 0
        year, month = map(int, key.split("-"))
        whole = calendar.monthrange(year, month)[1]
        if item.get("final_completo") and not final_done:
            return key, "final", whole
        if not final_done:
            available = int(item.get("dias_preliminar") or 0)
            if available > observed or (available == whole and not same_v3):
                return key, "prelim", available
    return None


def raster_signature(path):
    import rasterio
    with rasterio.open(path) as src:
        return {"width": src.width, "height": src.height, "count": src.count,
                "crs": str(src.crs), "transform": list(src.transform)}


def pin_started_coverage(context, published_days):
    """Conclui uma cobertura preliminar iniciada, sem misturar contextos.

Novos dias na origem não descartam progresso todo dia. Depois de publicar o
período iniciado, a próxima execução escolherá a cobertura mais recente.
"""
    if context["stage"] != "prelim":
        return context
    started = []
    for path in STATE.glob("work-*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        ctx = value.get("context", {})
        if all(ctx.get(k) == v for k, v in context.items() if k != "ndays") and \
                type(ctx.get("ndays")) is int and published_days < ctx["ndays"] <= context["ndays"]:
            validate_checkpoint(value, ctx)
            if path.name != checkpoint_path(STATE, ctx).name:
                raise ValueError("Nome do checkpoint não corresponde ao contexto")
            if value["days"]:
                started.append(ctx)
    return max(started, key=lambda c: c["ndays"]) if started else context


def completed_values(checkpoint):
    validate_checkpoint(checkpoint)
    ctx = checkpoint["context"]
    expected = [f"{day:02d}" for day in range(1, ctx["ndays"] + 1)]
    if set(checkpoint["days"]) != set(expected):
        raise ValueError("Mês incompleto: publicação proibida")
    # Mesma ordem e mesma soma do cálculo integral. Arredonda só no final.
    sums = [0.0] * len(ctx["codes"])
    for day in expected:
        sums = [a + b for a, b in zip(sums, checkpoint["days"][day]["values"])]
    return {code: round(float(value), 2) for code, value in zip(ctx["codes"], sums)}


def main():
    # Um resultado antigo nunca pode sobreviver a uma execução incompleta.
    CANDIDATE.unlink(missing_ok=True)
    report = json.loads(STATUS.read_text(encoding="utf-8"))
    data = json.loads(MONTHS.read_text(encoding="utf-8"))
    target = choose_target(report, data)
    if target is None:
        print("Nenhum mês CHIRPS v3 com dados novos para calcular.")
        return
    key, stage, ndays = target
    year, month = map(int, key.split("-"))
    whole = calendar.monthrange(year, month)[1]
    if not 1 <= ndays <= whole or (stage == "final" and ndays != whole):
        raise ValueError("Contagem de dias fora do esperado")
    shapes, bounds = read_geometry()
    context = {"month": key, "stage": stage, "ndays": ndays,
               "source_base": BASE, "algorithm": ALGORITHM,
               "geometry_sha256": hashlib.sha256(GEO.read_bytes()).hexdigest(),
               "codes": [code for code, _ in shapes]}
    old = data.get(key) or {}
    published_days = int(old.get("dias_observados") or 0) if old.get("colecao") == "CHIRPS-v3.0-sat-official" else 0
    context = pin_started_coverage(context, published_days)
    ndays = context["ndays"]
    checkpoint = load_checkpoint(STATE, context)
    path = checkpoint_path(STATE, context)
    pending = [day for day in range(1, ndays + 1) if f"{day:02d}" not in checkpoint["days"]]
    # Permite publicar um checkpoint já completo mesmo sem fazer outra requisição.
    if pending and not may_request(STATE):
        print("CHIRPS em pausa até " + load_control(STATE)["not_before"], flush=True)
        return
    for day in pending[:MAX_NEW_FILES]:
        url = source_url(context, day)
        print(f"{key} {stage}: {day}/{ndays}; {len(checkpoint['days'])} dias já preservados", flush=True)
        with tempfile.TemporaryDirectory(prefix="chuva-mt-chirps-") as temporary:
            raster = Path(temporary) / "day.tif"
            try:
                download(url, raster)
            except DeferredDownload as exc:
                print(str(exc), flush=True)
                return
            file_hash = hashlib.sha256(raster.read_bytes()).hexdigest()
            grid = raster_signature(raster)
            if checkpoint["days"] and any(rec["grid"] != grid for rec in checkpoint["days"].values()):
                raise ValueError("Grade diária mudou: progresso não pode ser misturado")
            sums, counts = grid_values(raster, shapes, bounds)
            if len(sums) != 142 or len(counts) != 142 or any(int(c) <= 0 for c in counts):
                raise ValueError("Dia sem pixels em um ou mais municípios; não publicar")
            record = {"source": url, "file_sha256": file_hash, "grid": grid,
                      "downloaded_at": iso(now_utc()),
                      "values": [float(s) / int(c) for s, c in zip(sums, counts)],
                      "counts": [int(x) for x in counts]}
            record["record_sha256"] = digest(record)
            checkpoint["days"][f"{day:02d}"] = record
            validate_checkpoint(checkpoint, context)
            atomic_json(path, checkpoint)
    if len(checkpoint["days"]) != ndays:
        print(f"PROGRESSO {key} {stage}: {len(checkpoint['days'])}/{ndays} dias. Retomada no próximo agendamento; dados do site intactos.", flush=True)
        return
    vals = completed_values(checkpoint)
    record = {"ano": year, "mes": month, "v": vals, "n": len(vals),
              "preliminar": stage != "final", "parcial": ndays < whole,
              "dias_observados": ndays, "dias_no_mes": whole,
              "colecao": "CHIRPS-v3.0-sat-official",
              "fonte": "Climate Hazards Center CHIRPS v3.0 " + ("preliminar" if stage == "prelim" else "definitivo"),
              "atualizado_em": now_utc().date().isoformat()}
    # O publicador verifica novamente a completude e a versão remota antes do commit.
    atomic_json(CANDIDATE, {"schema": SCHEMA, "context": context,
                           "previous_record_sha256": digest(data.get(key)), "record": record})
    print(f"VALIDADO {key} CHIRPS v3 {stage}: {ndays}/{whole} dias, 142 municípios. Aguardando publicação.", flush=True)


if __name__ == "__main__":
    main()
