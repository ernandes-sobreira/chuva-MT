#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chuva MT - atualizacao automatica da chuva mensal por municipio.

O que faz:
  1. Autentica no Google Earth Engine com uma conta de servico.
  2. Descobre quais meses, depois de dezembro de 2025, ja estao completos
     na colecao CHIRPS e ainda nao foram guardados no repositorio.
  3. Calcula a chuva media de cada municipio de Mato Grosso em cada mes.
  4. Confere o metodo contra a serie de referencia (trava de validacao).
  5. Grava dados/meses.json (lido pelo site) e um CSV por mes em dados/mensal/.

Nada e estimado ou preenchido: se o Earth Engine nao tiver o mes completo,
o mes simplesmente nao entra.

Variaveis de ambiente:
  EE_SERVICE_ACCOUNT_KEY  conteudo JSON da chave da conta de servico (obrigatoria)
  EE_PROJECT              id do projeto Google Cloud (opcional; padrao: o da chave)
  CHIRPS_COLECAO          id da colecao (opcional; padrao abaixo)
"""
import argparse
import calendar
import csv
import datetime as dt
import json
import os
import statistics
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ_MESES = os.path.join(RAIZ, "dados", "meses.json")
ARQ_MALHA = os.path.join(RAIZ, "dados", "municipios_mt.geojson")
ARQ_VALID = os.path.join(RAIZ, "dados", "validacao_referencia.csv")
DIR_MENSAL = os.path.join(RAIZ, "dados", "mensal")

COLECAO_PADRAO = "UCSB-CHC/CHIRPS/V3/DAILY_SAT"   # CHIRPS v3 diario, banda "precipitation" em mm/dia
BANDA = "precipitation"
ESCALA_M = 5566                                   # resolucao nativa do CHIRPS (0,05 grau)
PRIMEIRO_ANO = 2026                               # a serie de referencia embutida no site vai ate dez/2025
LIMITE_VALIDACAO_PCT = 5.0                        # mediana do desvio relativo aceito na trava
TAM_LOTE = 20                                     # municipios por requisicao


def log(msg):
    print(msg, flush=True)


def iniciar_ee():
    import ee
    chave = os.environ.get("EE_SERVICE_ACCOUNT_KEY", "").strip()
    if not chave:
        sys.exit("ERRO: defina o segredo EE_SERVICE_ACCOUNT_KEY com o JSON da chave da conta de servico.")
    try:
        info = json.loads(chave)
    except json.JSONDecodeError:
        sys.exit("ERRO: EE_SERVICE_ACCOUNT_KEY nao e um JSON valido. Cole o arquivo .json inteiro no segredo.")
    projeto = os.environ.get("EE_PROJECT", "").strip() or info.get("project_id")
    cred = ee.ServiceAccountCredentials(info["client_email"], key_data=chave)
    ee.Initialize(cred, project=projeto)
    log("Earth Engine autenticado. Conta: %s | Projeto: %s" % (info["client_email"], projeto))
    return ee


def carregar_malha():
    with open(ARQ_MALHA, encoding="utf-8") as f:
        gj = json.load(f)
    feats = [{"type": "Feature", "geometry": ft["geometry"],
              "properties": {"CD_MUN": str(ft["properties"]["CD_MUN"]), "NM_MUN": ft["properties"]["NM_MUN"]}}
             for ft in gj["features"]]
    if len(feats) != 142:
        sys.exit("ERRO: a malha deveria ter 142 municipios e tem %d." % len(feats))
    return feats


def ultimo_dia_disponivel(ee, colecao):
    col = ee.ImageCollection(colecao).filterDate("%d-01-01" % (PRIMEIRO_ANO - 1), "2100-01-01")
    ms = col.aggregate_max("system:time_start").getInfo()
    if ms is None:
        sys.exit("ERRO: a colecao %s nao devolveu imagens. Confira o id." % colecao)
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()


def mes_completo(ee, colecao, ano, mes):
    ini = dt.date(ano, mes, 1)
    fim = dt.date(ano + (mes == 12), mes % 12 + 1, 1)
    n = ee.ImageCollection(colecao).filterDate(ini.isoformat(), fim.isoformat()).size().getInfo()
    return n == calendar.monthrange(ano, mes)[1], n


def media_mensal(ee, colecao, feats, ano, mes):
    """Chuva do mes (soma dos dias) como media espacial por municipio. Devolve {CD_MUN: mm}."""
    ini = dt.date(ano, mes, 1)
    fim = dt.date(ano + (mes == 12), mes % 12 + 1, 1)
    img = ee.ImageCollection(colecao).filterDate(ini.isoformat(), fim.isoformat()).select(BANDA).sum()
    out = {}
    for i in range(0, len(feats), TAM_LOTE):
        fc = ee.FeatureCollection({"type": "FeatureCollection", "features": feats[i:i + TAM_LOTE]})
        red = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=ESCALA_M)
        res = red.select(["CD_MUN", "mean"], retainGeometry=False).getInfo()
        for ft in res["features"]:
            p = ft["properties"]
            if p.get("mean") is None:
                sys.exit("ERRO: o Earth Engine devolveu valor vazio para o municipio %s em %d-%02d." % (p.get("CD_MUN"), ano, mes))
            out[str(p["CD_MUN"])] = round(float(p["mean"]), 2)
    if len(out) != len(feats):
        sys.exit("ERRO: esperados %d municipios, recebidos %d em %d-%02d." % (len(feats), len(out), ano, mes))
    return out


def validar(ee, colecao, feats):
    """Recalcula meses de 2025 e compara com a serie de referencia do site."""
    ref = {}
    with open(ARQ_VALID, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ref.setdefault((int(r["ano"]), int(r["mes"])), {})[r["CD_MUN"]] = float(r["chuva_mm"])
    pior = 0.0
    for (ano, mes), vals in sorted(ref.items()):
        novo = media_mensal(ee, colecao, feats, ano, mes)
        difs = [abs(novo[c] - v) / v * 100 for c, v in vals.items() if v >= 20 and c in novo]
        med = statistics.median(difs) if difs else 0.0
        mx = max(difs) if difs else 0.0
        log("  validacao %d-%02d: desvio mediano %.2f%%, maximo %.2f%% (%d municipios)" % (ano, mes, med, mx, len(difs)))
        pior = max(pior, med)
    return pior


def nomes_municipios(feats):
    return {ft["properties"]["CD_MUN"]: ft["properties"]["NM_MUN"] for ft in feats}


def main():
    ap = argparse.ArgumentParser(description="Atualiza a chuva mensal por municipio de MT a partir do CHIRPS no Earth Engine.")
    ap.add_argument("--refazer", action="store_true", help="recalcula todos os meses a partir de %d, mesmo os ja guardados" % PRIMEIRO_ANO)
    ap.add_argument("--ignorar-validacao", action="store_true", help="grava mesmo se a trava de validacao falhar (nao recomendado)")
    args = ap.parse_args()

    colecao = os.environ.get("CHIRPS_COLECAO", "").strip() or COLECAO_PADRAO
    ee = iniciar_ee()
    feats = carregar_malha()
    nomes = nomes_municipios(feats)

    meses = {}
    if os.path.exists(ARQ_MESES):
        with open(ARQ_MESES, encoding="utf-8") as f:
            meses = json.load(f)
    meta = meses.pop("_meta", {}) or {}

    ultimo = ultimo_dia_disponivel(ee, colecao)
    log("Colecao: %s | ultimo dia disponivel: %s" % (colecao, ultimo.isoformat()))

    candidatos = []
    a, m = PRIMEIRO_ANO, 1
    while dt.date(a, m, 1) <= ultimo:
        candidatos.append((a, m))
        a, m = a + (m == 12), m % 12 + 1

    fazer = []
    for a, m in candidatos:
        k = "%d-%02d" % (a, m)
        ja = meses.get(k)
        if ja and not args.refazer and not ja.get("preliminar") and ja.get("colecao") == colecao and ja.get("n") == len(feats):
            continue
        ok, n = mes_completo(ee, colecao, a, m)
        if not ok:
            log("  %s ainda incompleto no Earth Engine (%d dias). Fica para a proxima execucao." % (k, n))
            continue
        fazer.append((a, m))

    if not fazer:
        log("Nada novo para calcular.")
    else:
        log("Meses a calcular: " + ", ".join("%d-%02d" % x for x in fazer))
        log("Trava de validacao (recalculo de meses de 2025 contra a serie de referencia):")
        pior = validar(ee, colecao, feats)
        if pior > LIMITE_VALIDACAO_PCT:
            msg = ("VALIDACAO FALHOU: desvio mediano de %.2f%%, acima do limite de %.1f%%. "
                   "A colecao ou a malha nao reproduzem a serie de 1996 a 2025. Nada foi gravado." % (pior, LIMITE_VALIDACAO_PCT))
            if not args.ignorar_validacao:
                sys.exit(msg)
            log(msg + " (seguindo por causa de --ignorar-validacao)")
        else:
            log("Validacao aprovada: pior desvio mediano de %.2f%%." % pior)

        hoje = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        os.makedirs(DIR_MENSAL, exist_ok=True)
        for a, m in fazer:
            k = "%d-%02d" % (a, m)
            v = media_mensal(ee, colecao, feats, a, m)
            meses[k] = {"ano": a, "mes": m, "v": v, "n": len(v), "preliminar": False, "colecao": colecao,
                        "fonte": "Earth Engine, %s, media por municipio (malha IBGE 2024)" % colecao, "atualizado_em": hoje}
            with open(os.path.join(DIR_MENSAL, k + ".csv"), "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["CD_MUN", "NM_MUN", "ano", "mes", "chuva_mm", "situacao"])
                for c in sorted(v):
                    w.writerow([c, nomes[c], a, m, v[c], "definitivo"])
            media = sum(v.values()) / len(v)
            log("  %s gravado: %d municipios, media simples %.1f mm, minimo %.1f, maximo %.1f" % (k, len(v), media, min(v.values()), max(v.values())))
        meta.update({"validacao_pior_desvio_mediano_pct": round(pior, 2)})

    meta.update({"verificado_em": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                 "colecao": colecao, "ultimo_dia_disponivel": ultimo.isoformat()})
    saida = {"_meta": meta}
    for k in sorted(meses):
        saida[k] = meses[k]
    with open(ARQ_MESES, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=0)
    log("Concluido.")


if __name__ == "__main__":
    main()
