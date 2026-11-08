#!/usr/bin/env python3
"""Estado de retomada CHIRPS; não contém nem publica dados mensais do site."""
import datetime as dt
import calendar
import hashlib
import json
import math
import os
import re
import tempfile
from email.utils import parsedate_to_datetime
from pathlib import Path

SCHEMA = 1
ALGORITHM = "municipal-pixel-center-daily-mean-v1"
MIN_INTERVAL_SECONDS = 60
DEFAULT_COOLDOWN_SECONDS = 24 * 60 * 60
MAX_NEW_FILES = 5
UTC = dt.timezone.utc


class DeferredDownload(Exception):
    """Origem pediu pausa. Estado válido pode ser salvo, mas mês não publicado."""


def now_utc():
    return dt.datetime.now(UTC)


def iso(value):
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def parse_time(value):
    result = dt.datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Horário de checkpoint sem fuso")
    return result.astimezone(UTC)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def retry_after_until(value, now):
    """Aceita segundos ou HTTP-date. Nunca limita a espera solicitada."""
    value = (value or "").strip()
    try:
        if re.fullmatch(r"[0-9]+", value):
            target = now + dt.timedelta(seconds=int(value))
        else:
            target = parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=UTC)
            target = target.astimezone(UTC)
        return max(target, now + dt.timedelta(seconds=MIN_INTERVAL_SECONDS))
    except OverflowError:
        # Um prazo positivo muito grande não pode ser encurtado para 24 h.
        return dt.datetime.max.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return now + dt.timedelta(seconds=DEFAULT_COOLDOWN_SECONDS)


def validate_control(value):
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("Controle CHIRPS inválido")
    for name in ("not_before", "last_request_at"):
        if value.get(name) is not None:
            parse_time(value[name])
    return value


def load_control(state):
    path = Path(state) / "control.json"
    if not path.exists():
        return {"schema": SCHEMA}
    return validate_control(json.loads(path.read_text(encoding="utf-8")))


def may_request(state, now=None):
    control = load_control(state)
    now = now or now_utc()
    return not control.get("not_before") or now >= parse_time(control["not_before"])


def mark_request(state, now=None):
    now = now or now_utc()
    control = load_control(state)
    control["last_request_at"] = iso(now)
    control["reason"] = "minimum_interval"
    control.pop("last_http_status", None)
    control["not_before"] = iso(max(now + dt.timedelta(seconds=MIN_INTERVAL_SECONDS),
                                   parse_time(control["not_before"]) if control.get("not_before") else now))
    atomic_json(Path(state) / "control.json", control)


def defer_origin(state, retry_after, status, now=None):
    now = now or now_utc()
    control = load_control(state)
    until = retry_after_until(retry_after, now)
    if control.get("not_before"):
        until = max(until, parse_time(control["not_before"]))
    control.update(not_before=iso(until), last_request_at=iso(now),
                   last_http_status=int(status), reason="origin_rate_limit")
    atomic_json(Path(state) / "control.json", control)
    return until


def checkpoint_path(state, context):
    return Path(state) / ("work-" + digest(context) + ".json")


def validate_checkpoint(value, context=None):
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("Checkpoint CHIRPS inválido")
    ctx = value.get("context")
    if not isinstance(ctx, dict) or (context is not None and ctx != context):
        raise ValueError("Checkpoint pertence a outra fonte, malha ou método")
    if ctx.get("algorithm") != ALGORITHM or ctx.get("stage") not in ("prelim", "final"):
        raise ValueError("Método/estágio de checkpoint inválido")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", str(ctx.get("month", ""))):
        raise ValueError("Mês de checkpoint inválido")
    codes = ctx.get("codes", [])
    if len(codes) != 142 or len(set(codes)) != 142 or not all(isinstance(c, str) and re.fullmatch(r"[0-9]{7}", c) for c in codes):
        raise ValueError("Checkpoint deve identificar 142 municípios distintos")
    if not isinstance(ctx.get("ndays"), int) or not 1 <= ctx["ndays"] <= 31:
        raise ValueError("Número de dias inválido")
    year, month = map(int, ctx["month"].split("-"))
    whole = calendar.monthrange(year, month)[1]
    if ctx["ndays"] > whole or (ctx["stage"] == "final" and ctx["ndays"] != whole):
        raise ValueError("Cobertura não corresponde ao calendário/estágio")
    if not re.fullmatch(r"[0-9a-f]{64}", str(ctx.get("geometry_sha256", ""))):
        raise ValueError("Identificação de malha inválida")
    if ctx.get("source_base") != "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily":
        raise ValueError("Fonte CHIRPS inesperada")
    days = value.get("days")
    if not isinstance(days, dict):
        raise ValueError("Dias ausentes no checkpoint")
    grids = []
    for day, record in days.items():
        if not re.fullmatch(r"[0-9]{2}", day) or not 1 <= int(day) <= ctx["ndays"]:
            raise ValueError("Dia fora do período no checkpoint")
        expected_source = source_url(ctx, int(day))
        if record.get("source") != expected_source:
            raise ValueError("Dia pertence a outra origem/versão")
        vals, counts = record.get("values", []), record.get("counts", [])
        if len(vals) != 142 or len(counts) != 142:
            raise ValueError("Dia incompleto no checkpoint")
        if not all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in vals):
            raise ValueError("Precipitação inválida no checkpoint")
        if not all(type(v) is int and v > 0 for v in counts):
            raise ValueError("Cobertura espacial inválida no checkpoint")
        if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("file_sha256", ""))):
            raise ValueError("Arquivo diário sem identificação")
        grid = record.get("grid")
        if not isinstance(grid, dict) or any(type(grid.get(k)) is not int or grid[k] <= 0 for k in ("width", "height", "count")):
            raise ValueError("Grade diária inválida")
        if not grid.get("crs") or not isinstance(grid.get("transform"), list) or len(grid["transform"]) != 9 or not all(type(x) in (int, float) and math.isfinite(x) for x in grid["transform"]):
            raise ValueError("Referência espacial inválida")
        if grids and grid != grids[0]:
            raise ValueError("Grades diárias incompatíveis")
        grids.append(grid)
        parse_time(record["downloaded_at"])
        expected_digest = digest({k: v for k, v in record.items() if k != "record_sha256"})
        if record.get("record_sha256") != expected_digest:
            raise ValueError("Checkpoint diário corrompido")
    return value


def load_checkpoint(state, context):
    path = checkpoint_path(state, context)
    if not path.exists():
        return {"schema": SCHEMA, "context": context, "days": {}}
    return validate_checkpoint(json.loads(path.read_text(encoding="utf-8")), context)


def source_url(context, day):
    year, month = map(int, context["month"].split("-"))
    stage = context["stage"]
    name = "chirps-v3.0.%s.%04d.%02d.%02d.tif" % (
        "sat" if stage == "final" else "prelim", year, month, day)
    return "%s/%s/sat/%d/%s" % (context["source_base"], stage, year, name)


def merge_state(local, remote, name):
    """Mescla progresso sem perder dias nem reduzir pausa já conhecida."""
    if name == "control.json":
        validate_control(local)
        if remote is None:
            return local
        validate_control(remote)
        merged = dict(remote)
        for field in ("not_before", "last_request_at"):
            choices = [x[field] for x in (local, remote) if x.get(field)]
            if choices:
                merged[field] = max(choices, key=parse_time)
        if local.get("reason"):
            merged["reason"] = local["reason"]
            merged["last_http_status"] = local.get("last_http_status")
        return merged
    validate_checkpoint(local)
    if name != checkpoint_path(".", local["context"]).name:
        raise ValueError("Nome do checkpoint não corresponde ao conteúdo")
    if remote is None:
        return local
    validate_checkpoint(remote, local["context"])
    merged = {"schema": SCHEMA, "context": local["context"], "days": dict(remote["days"])}
    for day, record in local["days"].items():
        if day in merged["days"] and merged["days"][day] != record:
            raise ValueError("Conflito de versões do mesmo dia; publicação suspensa")
        merged["days"][day] = record
    return validate_checkpoint(merged)
