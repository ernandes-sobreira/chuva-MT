#!/usr/bin/env python3
"""Auditoria diária de disponibilidade CHIRPS v3 preliminar/final (fonte oficial CHC).

NÃO rotula valores antigos como definitivos só porque uma versão final passou
a existir na origem. Disponibilidade da fonte e processamento municipal são
estados independentes. Nunca mistura CHIRPS v2 com CHIRPS v3.
"""
import calendar
import datetime as dt
import html.parser
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dados" / "status_chirps.json"
MONTHS = ROOT / "dados" / "meses.json"
BASE = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily"
USER_AGENT = "Chuva-MT-status-monitor/1.0 (daily metadata check; polite one request per directory)"


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.urls.append(href)


def directory_listing(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=35) as r:
        if r.status != 200:
            raise RuntimeError("HTTP %s em %s" % (r.status, url))
        body = r.read(450000).decode("utf-8", errors="replace")
    parser = Links()
    parser.feed(body)
    return parser.urls


def parse_daily_names(links, year):
    pat = re.compile(r"^chirps-v3\\.0\\.sat\\.(%04d)\\.(\\d{2})\\.(\\d{2})\\.tif$" % year)
    found = set()
    for link in links:
        name = link.split("/")[-1].split("?")[0]
        m = pat.match(name)
        if m:
            try:
                found.add(dt.date(year, int(m.group(2)), int(m.group(3))).isoformat())
            except ValueError:
                pass
    return found


def load_months():
    if not MONTHS.exists():
        return {}
    with MONTHS.open(encoding="utf-8") as f:
        return json.load(f)


def audit(now=None):
    today = now or dt.datetime.now(dt.timezone.utc).date()
    # Últimos seis meses, incluindo o mês corrente, atravessando anos.
    first_y = today.year + (today.month <= 6) - 1
    first_m = (today.month - 6) % 12 + 1
    first = dt.date(first_y, first_m, 1)
    months = []
    cursor = first
    while cursor <= today:
        months.append((cursor.year, cursor.month))
        cursor = dt.date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)

    years = sorted(set(y for y, _ in months))
    sources = {}
    for year in years:
        for kind in ("final", "prelim"):
            url = "%s/%s/sat/%d/" % (BASE, kind, year)
            try:
                links = directory_listing(url)
                sources[(kind, year)] = {"days": parse_daily_names(links, year), "error": None}
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    sources[(kind, year)] = {"days": set(), "error": None}
                else:
                    raise
            time.sleep(0.8)

    data = load_months()
    output = {}
    for y, m in months:
        count = calendar.monthrange(y, m)[1]
        days = [dt.date(y, m, day).isoformat() for day in range(1, count + 1)]
        nf = sum(d in sources[("final", y)]["days"] for d in days)
        np = sum(d in sources[("prelim", y)]["days"] for d in days)
        key = "%04d-%02d" % (y, m)
        loaded = data.get(key, {})
        # Uma série legada CHIRPS v2 não é convertida para CHIRPS v3 por metadados.
        loaded_collection = str(loaded.get("colecao") or "")
        loaded_v3 = "CHIRPS/V3/" in loaded_collection.upper()
        if loaded_v3 and loaded.get("v") and not loaded.get("preliminar") and not loaded.get("parcial"):
            processed_status = "definitivo"
        elif loaded_v3 and loaded.get("v"):
            processed_status = "preliminar"
        elif loaded.get("v"):
            processed_status = "outra_versao_chirps"
        else:
            processed_status = "sem_dados_municipais"
        available = "final" if nf == count else ("preliminar" if np else "indisponivel")
        output[key] = {
            "fonte": "CHIRPS v3.0 sat",
            "situacao_na_origem": available,
            "dias_final": nf,
            "dias_preliminar": np,
            "dias_necessarios": count,
            "final_completo": nf == count,
            "preliminar_completo": np == count,
            "situacao_no_site": processed_status,
            "versao_no_site": loaded_collection or None,
            "requer_reprocessamento": nf == count and processed_status != "definitivo",
            "origem_final": "%s/final/sat/%d/" % (BASE, y),
            "origem_preliminar": "%s/prelim/sat/%d/" % (BASE, y),
        }
    return {
        "_meta": {
            "verificado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "data_verificacao": today.isoformat(),
            "fonte": "Climate Hazards Center, CHIRPS v3.0, daily/sat",
            "observacao": "Arquivo final encontrado não implica que os valores municipais já foram recalculados. Versões distintas não são misturadas.",
        },
        "meses": output,
    }


def main():
    try:
        result = audit()
    except Exception as exc:
        print("ERRO ao verificar CHIRPS: %s" % exc, file=sys.stderr)
        sys.exit(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    new = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    OUT.write_text(new, encoding="utf-8")
    for key, val in result["meses"].items():
        print("%s: origem=%s final=%d/%d prelim=%d/%d site=%s" %
              (key, val["situacao_na_origem"], val["dias_final"], val["dias_necessarios"],
               val["dias_preliminar"], val["dias_necessarios"], val["situacao_no_site"]), flush=True)


if __name__ == "__main__":
    main()
