#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chuva MT - atualização diária por município.

Fonte padrão: JAXA GSMaP v8 operational (NRT), resolução horária de 0,1 grau.
A página histórica continua usando CHIRPS. Este arquivo alimenta apenas a aba Diário / Agora.

Regras:
- autentica no Earth Engine com a mesma conta de serviço do fluxo mensal;
- considera o dia civil de Mato Grosso em UTC-4 (00:00–24:00 local = 04:00–04:00 UTC);
- só grava dias com 24 imagens horárias disponíveis;
- soma hourlyPrecipRate (mm/h) ao longo das 24 horas e calcula a média espacial por município;
- na primeira execução, preenche os 120 dias completos mais recentes;
- depois, acrescenta dias novos e recalcula os 14 dias mais recentes para incorporar revisões NRT;
- mantém uma janela móvel de até 180 dias no repositório.

Nenhum valor é estimado ou preenchido quando faltam imagens ou municípios.
"""
import datetime as dt
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ_MALHA = os.path.join(RAIZ, "dados", "municipios_mt.geojson")
ARQ_SAIDA = os.path.join(RAIZ, "dados", "diario.json")

COLECAO_PADRAO = "JAXA/GPM_L3/GSMaP/v8/operational"
BANDA_PADRAO = "hourlyPrecipRate"
ESCALA_M = 11132
FUSO_H = -4
DIAS_INICIAIS = 120
DIAS_RECALCULAR = 14
DIAS_MANTER = 180
LOTE_DIAS = 10


def log(msg):
    print(msg, flush=True)


def iniciar_ee():
    import ee
    chave = os.environ.get("EE_SERVICE_ACCOUNT_KEY", "").strip()
    if not chave:
        sys.exit("ERRO: defina o segredo EE_SERVICE_ACCOUNT_KEY com o JSON da chave da conta de serviço.")
    try:
        info = json.loads(chave)
    except json.JSONDecodeError:
        sys.exit("ERRO: EE_SERVICE_ACCOUNT_KEY não é um JSON válido.")
    projeto = os.environ.get("EE_PROJECT", "").strip() or info.get("project_id")
    cred = ee.ServiceAccountCredentials(info["client_email"], key_data=chave)
    ee.Initialize(cred, project=projeto)
    log("Earth Engine autenticado. Conta: %s | Projeto: %s" % (info["client_email"], projeto))
    return ee


def carregar_malha(ee):
    with open(ARQ_MALHA, encoding="utf-8") as f:
        gj = json.load(f)
    feats = []
    for ft in gj["features"]:
        feats.append({
            "type": "Feature",
            "geometry": ft["geometry"],
            "properties": {
                "CD_MUN": str(ft["properties"]["CD_MUN"]),
                "NM_MUN": ft["properties"]["NM_MUN"],
            },
        })
    if len(feats) != 142:
        sys.exit("ERRO: a malha deveria ter 142 municípios e tem %d." % len(feats))
    return feats, ee.FeatureCollection({"type": "FeatureCollection", "features": feats})


def utc_inicio_dia_local(d):
    h_utc = -FUSO_H
    return dt.datetime(d.year, d.month, d.day, h_utc, 0, tzinfo=dt.timezone.utc)


def iso_utc(x):
    return x.isoformat().replace("+00:00", "Z")


def colecao_dia(ee, colecao, d):
    ini = utc_inicio_dia_local(d)
    fim = ini + dt.timedelta(days=1)
    return ee.ImageCollection(colecao).filterDate(iso_utc(ini), iso_utc(fim))


def ultimo_instante(ee, colecao):
    ms = ee.ImageCollection(colecao).aggregate_max("system:time_start").getInfo()
    if ms is None:
        sys.exit("ERRO: a coleção %s não devolveu imagens." % colecao)
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)


def ultimo_dia_completo(ee, colecao, ult_utc):
    local = ult_utc + dt.timedelta(hours=FUSO_H)
    d = local.date()
    for _ in range(10):
        n = colecao_dia(ee, colecao, d).size().getInfo()
        log("  conferindo %s: %d imagens horárias" % (d.isoformat(), n))
        if n == 24:
            return d
        d -= dt.timedelta(days=1)
    sys.exit("ERRO: não encontrei um dia completo (24 imagens) nos últimos 10 dias disponíveis da coleção.")


def ler_saida():
    if not os.path.exists(ARQ_SAIDA):
        return {"_meta": {}, "dias": {}}
    try:
        with open(ARQ_SAIDA, encoding="utf-8") as f:
            x = json.load(f)
        if not isinstance(x, dict):
            return {"_meta": {}, "dias": {}}
        x.setdefault("_meta", {})
        x.setdefault("dias", {})
        return x
    except Exception:
        return {"_meta": {}, "dias": {}}


def datas_para_calcular(saida, ultimo):
    dias = saida.get("dias", {})
    if not dias:
        ini = ultimo - dt.timedelta(days=DIAS_INICIAIS - 1)
        return [ini + dt.timedelta(days=i) for i in range(DIAS_INICIAIS)]

    existentes = []
    for k in dias:
        try:
            existentes.append(dt.date.fromisoformat(k))
        except ValueError:
            pass
    if not existentes:
        ini = ultimo - dt.timedelta(days=DIAS_INICIAIS - 1)
        return [ini + dt.timedelta(days=i) for i in range(DIAS_INICIAIS)]

    ultima_gravada = max(existentes)
    wanted = set()
    d = ultima_gravada + dt.timedelta(days=1)
    while d <= ultimo:
        wanted.add(d)
        d += dt.timedelta(days=1)
    ini_refresh = max(
        ultimo - dt.timedelta(days=DIAS_RECALCULAR - 1),
        ultimo - dt.timedelta(days=DIAS_MANTER - 1),
    )
    d = ini_refresh
    while d <= ultimo:
        wanted.add(d)
        d += dt.timedelta(days=1)
    return sorted(wanted)


def calcular_lote(ee, colecao, banda, fc, datas):
    """Calcula vários dias em uma única avaliação do Earth Engine."""
    tudo = ee.FeatureCollection([])
    for d in datas:
        col = colecao_dia(ee, colecao, d)
        nimg = col.size()
        img = col.select(banda).sum().rename("chuva_mm")
        red = img.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.mean().setOutputs(["chuva_mm"]),
            scale=ESCALA_M,
            tileScale=4,
        )
        data_txt = d.isoformat()

        def marcar(f):
            return f.set({"data": data_txt, "n_img": nimg})

        red = red.map(marcar)
        tudo = tudo.merge(red)

    info = tudo.select(
        ["CD_MUN", "NM_MUN", "chuva_mm", "data", "n_img"],
        retainGeometry=False,
    ).getInfo()
    out = {}
    counts = {}
    for ft in info.get("features", []):
        p = ft.get("properties", {})
        data = str(p.get("data", ""))
        counts[data] = int(p.get("n_img") or 0)
        if counts[data] != 24:
            continue
        cod = str(p.get("CD_MUN", ""))
        val = p.get("chuva_mm")
        if not cod or val is None:
            continue
        out.setdefault(data, {})[cod] = round(float(val), 2)
    return out, counts


def main():
    ee = iniciar_ee()
    colecao = os.environ.get("DIARIO_COLECAO", "").strip() or COLECAO_PADRAO
    banda = os.environ.get("DIARIO_BANDA", "").strip() or BANDA_PADRAO
    feats, fc = carregar_malha(ee)
    saida = ler_saida()

    ult_utc = ultimo_instante(ee, colecao)
    log("Coleção diária: %s | banda: %s | último instante disponível: %s" %
        (colecao, banda, iso_utc(ult_utc)))
    ultimo = ultimo_dia_completo(ee, colecao, ult_utc)
    log("Último dia completo em Mato Grosso (UTC-4): %s" % ultimo.isoformat())

    datas = datas_para_calcular(saida, ultimo)
    if datas:
        log("Dias a calcular/recalcular: %d (%s a %s)" %
            (len(datas), datas[0].isoformat(), datas[-1].isoformat()))
    else:
        log("Nenhum dia novo para calcular; atualizando apenas os metadados da verificação.")

    dias = saida.get("dias", {})
    for i in range(0, len(datas), LOTE_DIAS):
        lote = datas[i:i + LOTE_DIAS]
        log("  lote %s a %s" % (lote[0].isoformat(), lote[-1].isoformat()))
        vals, counts = calcular_lote(ee, colecao, banda, fc, lote)
        for d in lote:
            k = d.isoformat()
            nimg = counts.get(k, 0)
            v = vals.get(k, {})
            if nimg != 24:
                log("    %s incompleto (%d imagens); não gravado." % (k, nimg))
                continue
            if len(v) != len(feats):
                log("    %s devolveu %d de %d municípios; não gravado." %
                    (k, len(v), len(feats)))
                continue
            dias[k] = {
                "v": v,
                "n": len(v),
                "n_imagens": nimg,
                "fonte": "GSMaP v8 operational / Earth Engine",
                "banda": banda,
                "preliminar": True,
            }
            media = sum(v.values()) / len(v)
            log("    %s gravado: %d municípios, média simples %.1f mm, mínimo %.1f, máximo %.1f" %
                (k, len(v), media, min(v.values()), max(v.values())))

    corte = ultimo - dt.timedelta(days=DIAS_MANTER - 1)
    dias = {
        k: v for k, v in dias.items()
        if k >= corte.isoformat() and k <= ultimo.isoformat()
    }

    agora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta = {
        "fonte": "JAXA GSMaP v8 operational (NRT)",
        "colecao": colecao,
        "banda": banda,
        "unidade_origem": "mm/h; soma das 24 imagens horárias do dia local",
        "fuso_dia": "UTC-4 (Mato Grosso)",
        "verificado_em": agora,
        "ultimo_instante_disponivel_utc": iso_utc(ult_utc),
        "ultimo_dia_completo_local": ultimo.isoformat(),
        "dias_armazenados": len(dias),
        "janela_max_dias": DIAS_MANTER,
        "observacao": "Série diária separada da série histórica CHIRPS; produto NRT/provisório, sujeito a revisões.",
    }
    with open(ARQ_SAIDA, "w", encoding="utf-8") as f:
        json.dump(
            {"_meta": meta, "dias": dict(sorted(dias.items()))},
            f,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    log("Concluído. %d dias disponíveis na aba diária." % len(dias))


if __name__ == "__main__":
    main()
