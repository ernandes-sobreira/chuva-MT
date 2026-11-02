#!/usr/bin/env python3
"""Sensibilidade do coeficiente de pastagens, sem inferencia causal, Caceres 1985–2025."""
from pathlib import Path
import json,math
import numpy as np,pandas as pd
from statsmodels.formula.api import ols
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
P=Path("pesquisa_pantanal/hidrologia/analise")
P.mkdir(parents=True,exist_ok=True)
df=pd.read_csv(P/"serie_mensal_integrada_ana_mapbiomas_chirps.csv")
for l in range(1,4):
 if f"rain{l}" not in df:df[f"rain{l}"]=df["chuva_montante_mm"].shift(l)
if "cota0" not in df:df["cota0"]=df["cota_media_m"]
if "vazao0" not in df:df["vazao0"]=df["vazao_media_m3_s"]
if "cota1" not in df:df["cota1"]=df["cota_media_m"].shift(1)
if "vazao1" not in df:df["vazao1"]=df["vazao_media_m3_s"].shift(1)
if "agua_kha" not in df:df["agua_kha"]=df["agua_superficial_local_planicie_ha"]/1000
if "pastagem_mha" not in df:df["pastagem_mha"]=df["pastagem_plantada_montante_ha"]/1e6
if "t" not in df:df["t"]=range(len(df))
formula_base="agua_kha ~ C(mes) + rain0 + rain1 + rain2 + rain3"
formulas={
 "Só chuva e sazonalidade":formula_base+" + pastagem_mha",
 "Chuva + tendência":formula_base+" + t + pastagem_mha",
 "Chuva + tendência + cota":formula_base+" + t + cota0 + cota1 + pastagem_mha",
 "Chuva + tendência + vazão":formula_base+" + t + vazao0 + vazao1 + pastagem_mha"
}
rows=[]
for name,formula in formulas.items():
 req=["agua_kha","rain0","rain1","rain2","rain3","pastagem_mha"]
 if "cota" in name: req+=["cota0","cota1"]
 if "vazão" in name:req+=["vazao0","vazao1"]
 sample=df.dropna(subset=req)
 m=ols(formula,data=sample).fit(cov_type="HAC",cov_kwds={"maxlags":12})
 ci=m.conf_int().loc["pastagem_mha"]
 rows.append({"especificacao":name,"n":len(sample),"coef_agua_mil_ha_por_milhao_ha_pastagem":round(float(m.params["pastagem_mha"]),4),
 "ic95_inf":round(float(ci[0]),4),"ic95_sup":round(float(ci[1]),4),
 "p_HAC":round(float(m.pvalues["pastagem_mha"]),6),"R2_ajustado":round(float(m.rsquared_adj),4)})
r=pd.DataFrame(rows);r.to_csv(P/"sensibilidade_pastagens.csv",index=False,encoding="utf-8-sig")
# Diferencas anuais (n~38 apos filtros) para evitar comparacao ingenua de tendencias de nivel.
ann=df.groupby("ano",as_index=False).agg(agua=("agua_kha","mean"),rain=("chuva_montante_mm","sum"),
 flow=("vazao_media_m3_s","mean"),flow_n=("vazao_media_m3_s","count"),pasture=("pastagem_mha","first"))
ann.loc[ann.flow_n<10,"flow"]=np.nan
for k in ["agua","rain","flow","pasture"]:ann["d_"+k]=ann[k].diff()
d=ann.dropna(subset=["d_agua","d_rain","d_flow","d_pasture"])
m=ols("d_agua ~ d_rain + d_flow + d_pasture",data=d).fit(cov_type="HAC",cov_kwds={"maxlags":2})
ci=m.conf_int().loc["d_pasture"]
annual={"n":len(d),"coef":round(float(m.params["d_pasture"]),4),"IC95%":[round(float(ci[0]),4),round(float(ci[1]),4)],
 "p_HAC":round(float(m.pvalues["d_pasture"]),6),"R2_ajustado":round(float(m.rsquared_adj),4)}
# Walk-forward folds with same ANA-stage valid sample for all compared models.
clean=df.dropna(subset=["agua_kha","rain0","rain1","rain2","rain3","cota0","cota1","pastagem_mha"])
forms2={
 "Só chuva":"agua_kha ~ C(mes) + t + rain0 + rain1 + rain2 + rain3",
 "Chuva + cota":"agua_kha ~ C(mes) + t + rain0 + rain1 + rain2 + rain3 + cota0 + cota1",
 "Chuva + cota + pastagem":"agua_kha ~ C(mes) + t + rain0 + rain1 + rain2 + rain3 + cota0 + cota1 + pastagem_mha"
}
folds=[]
for end in [1999,2004,2009,2014,2019]:
 train=clean[clean.ano<=end];test=clean[(clean.ano>end)&(clean.ano<=end+5)]
 if len(train)<100 or len(test)<24:continue
 record={"treino_ate":end,"teste":f"{end+1}-{min(2025,end+5)}","n_treino":len(train),"n_teste":len(test)}
 for name,formula in forms2.items():
  fitted=ols(formula,data=train).fit()
  pred=fitted.predict(test)
  record[name]=round(math.sqrt(float(np.mean((pred-test.agua_kha)**2))),4)
 folds.append(record)
pd.DataFrame(folds).to_csv(P/"validacao_temporal_multiplas_janelas.csv",index=False,encoding="utf-8-sig")
corr_t=float(np.corrcoef(df["pastagem_mha"],df["t"])[0,1])
report={"especificacoes":rows,"primeiras_diferencas_anuais":annual,
 "correlacao_pastagem_tempo":round(corr_t,5),"validacao_multiplas_janelas":folds,
 "avisos":["A positividade ou negatividade de coeficientes nao e prova causal",
 "Pastagem e ano covariam fortemente e podem produzir instabilidade e supressao estatistica",
 "Pessoas podem alterar a paisagem a montante sem que a area annual de pastagem capture manejo e compactacao",
 "Primeiras diferencas anuais com n limitado e vazao consolidada por mes",
 "Validacao temporal reduz risco de ajuste espurio, mas nao identifica causalidade"]}
(P/"resultados_sensibilidade.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
fig,ax=plt.subplots(figsize=(10,5.5),layout="constrained")
y=np.arange(len(r))
coef=r.coef_agua_mil_ha_por_milhao_ha_pastagem.to_numpy()
lower=coef-r.ic95_inf.to_numpy();upper=r.ic95_sup.to_numpy()-coef
ax.errorbar(coef,y,xerr=np.array([lower,upper]),fmt="o",capsize=4,color="#155D77",linewidth=2)
ax.set_yticks(y,labels=r.especificacao)
ax.invert_yaxis();ax.axvline(0,c="#555555",lw=1)
ax.set_xlabel("Coeficiente de pastagem (mil ha de água por milhão de ha de pastagem)\nIC 95% com erros HAC")
ax.set_title("Sensibilidade da associação pastagem–água: recorte de Cáceres",loc="left",weight="bold")
ax.spines[["top","right"]].set_visible(False);ax.grid(axis="x",alpha=.15)
fig.savefig(P/"FIGURA_05_SENSIBILIDADE_PASTAGEM.png",dpi=210,bbox_inches="tight");plt.close(fig)
if folds:
 f=pd.DataFrame(folds);fig,ax=plt.subplots(figsize=(10,5),layout="constrained")
 for name,color in [("Só chuva","#519A72"),("Chuva + cota","#C37137"),("Chuva + cota + pastagem","#156B88")]:
  ax.plot(f.teste,f[name],marker="o",lw=2,ms=5,label=name,color=color)
 ax.set_title("Validação em janelas temporais sucessivas",loc="left",weight="bold")
 ax.set_ylabel("RMSE em 5 anos fora do treino (mil ha)")
 ax.set_xlabel("Período independente");ax.legend(frameon=False);ax.grid(alpha=.15)
 ax.spines[["top","right"]].set_visible(False)
 fig.savefig(P/"FIGURA_06_VALIDACAO_MULTIPLAS_JANELAS.png",dpi=210,bbox_inches="tight");plt.close(fig)
lines=["# Robustez da hipótese pecuária – Pantanal de Cáceres (1985–2025)","",
 f"Correlação entre expansão de pastagens e passagem do tempo: **r={corr_t:.3f}**.","",
 "## Mudança da estimativa entre especificações"]
for x in rows:lines.append(f"- {x['especificacao']}: β={x['coef_agua_mil_ha_por_milhao_ha_pastagem']}; IC95%={x['ic95_inf']} a {x['ic95_sup']}; p HAC={x['p_HAC']}.")
lines.extend(["","## Primeiras diferenças anuais",
 f"β da mudança das pastagens = {annual['coef']}; IC95% = {annual['IC95%']}; p HAC = {annual['p_HAC']} (n={annual['n']}).",
 "","## Validação em múltiplas janelas", ""])
for f in folds:lines.append(f"- {f['teste']}: RMSE chuva {f['Só chuva']}, chuva+cota {f['Chuva + cota']}, chuva+cota+pastagem {f['Chuva + cota + pastagem']} mil ha.")
lines+=["","**Interpretação:** os resultados são exploratórios, não indicam causa nem proporção atribuível à pecuária. Antes de qualquer atribuição, requer bacias de controle, pastagens/manejo espacializados, barragens, clima e validação de séries hidrométricas."]
(P/"RELATORIO_SENSIBILIDADE_PASTAGENS.md").write_text("\n".join(lines),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2)[:17000])
