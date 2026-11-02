#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste reproducível de defasagens de mudanças de pastagem sobre água do Pantanal na bacia ANA 66070004.

O eixo primário é anual (1985–2025), porque a pastagem MapBiomas é anual.
Teste 0–10 anos e janelas móveis de 15 anos. Não duplicar dados anuais em 12
meses como se fossem 492 observações independentes de pastagem.
Lag = k significa: mudança na pastagem do ano t-k com mudança na água do ano t.
Controle chuva, memória hídrica e autocorrelação. Testes exploratórios, não causalidade.
"""
from pathlib import Path
import csv, json, math, warnings
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from statsmodels.api import OLS, add_constant
from statsmodels.stats.multitest import multipletests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

DIR=Path("pesquisa_pantanal/recorte_cientifico")
SRC=DIR/"resultados/SERIE_CORRIGIDA_BACIA_ANA_66070004_1985_2025.csv"
META=DIR/"resultados/STATUS_EXTRAÇÃO_RECORTE_VALIDADO.json"
FLOW=Path("pesquisa_pantanal/hidrologia/resultados/vazao_mensal_ana_caceres_1985_2025.csv")
OUT=DIR/"janelas_defasagens"; OUT.mkdir(parents=True,exist_ok=True)
qc=json.loads(META.read_text(encoding="utf8"))
assert qc.get("status")=="concluido" and qc.get("total_meses")==492, "Base mensal não validada"
assert 950 < qc.get("area_pantanal_intersecao_km2",0) < 1000, "Recorte Pantanal divergente"
raw=pd.read_csv(SRC,encoding="utf-8-sig").sort_values(["ano","mes"])
assert len(raw)==492 and not raw.duplicated(subset=["ano","mes"]).any()
assert (raw.groupby("ano").size()==12).all()
assert raw["ano"].min()==1985 and raw["ano"].max()==2025

def aggregate(x):
    return pd.Series({
      "agua_media_ha":x.agua_superficial_bioma_pantanal_montante_ha.mean(),
      "agua_seca_ha":x.loc[x.mes.isin([7,8,9,10]),"agua_superficial_bioma_pantanal_montante_ha"].mean(),
      "agua_anual_ha":x.agua_anual_bioma_pantanal_montante_ha.iloc[0],
      "chuva_mm":x.chuva_na_bacia_mm.sum(),
      "pastagem_ha":x.pastagem_plantada_bacia_ha.iloc[0]})
ann=raw.groupby("ano",as_index=False).apply(aggregate,include_groups=False).reset_index()
if "index" in ann.columns:ann=ann.drop(columns="index")
ann=ann.sort_values("ano").reset_index(drop=True)
if "ano" not in ann: raise RuntimeError("Chave anual ausente")
assert len(ann)==41
for y,grp in raw.groupby("ano"):
  assert grp.pastagem_plantada_bacia_ha.max()-grp.pastagem_plantada_bacia_ha.min()<1e-6
  assert grp.agua_anual_bioma_pantanal_montante_ha.max()-grp.agua_anual_bioma_pantanal_montante_ha.min()<1e-6
for metric in ["agua_media_ha","agua_seca_ha","agua_anual_ha","chuva_mm","pastagem_ha"]:
    ann["d_"+metric]=ann[metric].diff()
for lag in range(0,11):
    ann[f"dP_lag{lag}"]=ann["d_pastagem_ha"].shift(lag)/100000  # 100 mil ha de mudança
ann["dRain"]=ann["d_chuva_mm"]/100                     # 100 mm ano/ano
ann["dRain1"]=ann["dRain"].shift(1)
ann["dQprev"]=ann["d_agua_media_ha"].shift(1)/1000
ann["ano_centro"]=(ann.ano-2005)/10

# Vazão como controle de sensibilidade: pode ser mediadora dos impactos de uso do solo.
try:
   flow=pd.read_csv(FLOW,encoding="utf-8-sig")
   def annual_flow(v):
     vv=v.vazao_media_m3_s.dropna()
     return pd.Series({"n_meses_vazao":len(vv),"vazao_media_m3_s":vv.mean() if len(vv)>=10 else np.nan})
   agg_flow=flow.groupby("ano",as_index=False).apply(annual_flow,include_groups=False).reset_index()
   if "index" in agg_flow.columns:agg_flow=agg_flow.drop(columns="index")
   ann=ann.merge(agg_flow,on="ano",validate="one_to_one")
   ann["dFlow"]=ann.vazao_media_m3_s.diff()/100
except Exception as exc:
   ann["dFlow"]=np.nan
   warnings.warn(f"Vazão indisponível: {exc}")

# Mesma amostra de anos (1996 a 2025) para TODOS os lags no teste primário.
# 1985+11=1996 garante dP(t-10) observado. Controles com dW(t-1), dRain(t-1).
EVAL_START=1996
TARGETS={
 "Água média mensal":"d_agua_media_ha",
 "Água na seca (jul–out)":"d_agua_seca_ha",
 "Área anual de água":"d_agua_anual_ha"}
rows=[];models={}
for name,target in TARGETS.items():
  for k in range(11):
    df=ann[ann.ano>=EVAL_START].copy()
    df["y"]=df[target]/1000     # mudança da água em mil hectares
    df["dWprev"]=ann[target].shift(1).loc[df.index]/1000
    cols=["y",f"dP_lag{k}","dRain","dRain1","dWprev"]
    df=df.dropna(subset=cols)
    if len(df)<25:raise RuntimeError(f"Amostra curta em {name} lag {k}: {len(df)}")
    X=add_constant(df[[f"dP_lag{k}","dRain","dRain1","dWprev"]].rename(columns={f"dP_lag{k}":"pastagem"}),has_constant="add")
    fit=OLS(df.y,X).fit(cov_type="HAC",cov_kwds={"maxlags":2})
    v=fit.conf_int().loc["pastagem"]
    rows.append({"desfecho":name,"lag_anos":k,"n":len(df),
       "coef_kha_por_100kha":float(fit.params["pastagem"]),
       "ic95_inf":float(v.iloc[0]),"ic95_sup":float(v.iloc[1]),
       "p_hac":float(fit.pvalues["pastagem"]),"r2_ajustado":float(fit.rsquared_adj),
       "AIC":float(fit.aic),"BIC":float(fit.bic)})
    models[(name,k)]=fit
results=pd.DataFrame(rows)
# Correção simultânea por 33 testes (11 lags x 3 desfechos).
rej,padj,_,_=multipletests(results.p_hac,alpha=.05,method="fdr_bh")
results["p_fdr_33"]=padj;results["fdr_5pct"]=rej
results.to_csv(OUT/"lag_0_a_10_anos_resultados_HAC_FDR33.csv",index=False,encoding="utf-8-sig")
ann.to_csv(OUT/"serie_anual_com_deltas_e_defasagens.csv",index=False,encoding="utf-8-sig")

# 3 e 5 anos de janela móvel, exclusivamente para visualização de processos lentos.
rolling={}
for k in [3,5]:
  for v in ["agua_media_ha","agua_seca_ha","chuva_mm","pastagem_ha"]:
    col=f"mm{k}_{v}"
    ann[col]=ann[v].rolling(k,min_periods=k).mean()
    rolling[col]=col
ann.to_csv(OUT/"serie_anual_com_deltas_e_defasagens.csv",index=False,encoding="utf-8-sig")

# Correlação em janelas rolantes de 15 anos, sobre o resíduo de variações de água
# após ajuste para chuva e memória hídrica. Apenas visualização exploratória.
rollingrows=[]
BASE=ann[["ano","d_agua_media_ha","dRain","dRain1"]].copy()
BASE["dWprev"]=ann["d_agua_media_ha"].shift(1)
valid=BASE.dropna()
base_fit=OLS(valid.d_agua_media_ha,add_constant(valid[["dRain","dRain1","dWprev"]])).fit()
ann["anomalia_agua_ajustada_ha"]=np.nan
ann.loc[valid.index,"anomalia_agua_ajustada_ha"]=base_fit.resid
WINDOW=15
for lag in [0,2,3,5]:
  for i in range(len(ann)):
    if i+1<WINDOW:continue
    part=ann.iloc[i-WINDOW+1:i+1]
    vv=part[["anomalia_agua_ajustada_ha",f"dP_lag{lag}"]].dropna()
    if len(vv)<12 or vv.iloc[:,1].std()<=1e-12:continue
    r,p=pearsonr(vv.iloc[:,1],vv.iloc[:,0])
    rollingrows.append({"ano_final":int(ann.ano.iloc[i]),"lag_anos":lag,
      "n":len(vv),"r":float(r),"p_nao_corrigido":float(p)})
rr=pd.DataFrame(rollingrows)
rr.to_csv(OUT/"correlacoes_janela_deslizante_15_anos.csv",index=False,encoding="utf-8-sig")

# Cumulative changes for exposure windows 1 (instantaneous), 3, 5 years
# compared at fixed lag start 0,1,2,3. Highly overlapping; observational.
cumulative=[]
for window in [1,3,5]:
  for startlag in [0,1,2,3]:
    data=ann[ann.ano>=EVAL_START].copy()
    exposure=ann.d_pastagem_ha.shift(startlag).rolling(window,min_periods=window).sum()/100000
    data["x_cum"]=exposure.loc[data.index]
    data["y"]=data.d_agua_media_ha/1000
    data["dWprev"]=ann.d_agua_media_ha.shift(1).loc[data.index]/1000
    data=data.dropna(subset=["x_cum","y","dRain","dRain1","dWprev"])
    X=add_constant(data[["x_cum","dRain","dRain1","dWprev"]])
    fit=OLS(data.y,X).fit(cov_type="HAC",cov_kwds={"maxlags":2})
    ci=fit.conf_int().loc["x_cum"]
    cumulative.append({"janela_anos":window,"inicio_defasagem_anos":startlag,"n":len(data),
      "coef_kha_por_100kha":float(fit.params["x_cum"]),"ci95_inf":float(ci.iloc[0]),
      "ci95_sup":float(ci.iloc[1]),"p_hac":float(fit.pvalues["x_cum"])})
pd.DataFrame(cumulative).to_csv(OUT/"efeito_acumulado_1_3_5_anos.csv",index=False,encoding="utf-8-sig")

# Sensibilidade do lag 2,3 e do maior lag exploratório: tendência e com vazão.
bestrow=results[results.desfecho=="Água média mensal"].sort_values("p_hac").iloc[0]
best=int(bestrow.lag_anos)
sens=[]
for lag in sorted(set([0,2,3,5,best])):
  for form in ["base","com_tendencia","com_vazao"]:
    df=ann[ann.ano>=EVAL_START].copy()
    df["y"]=df.d_agua_media_ha/1000
    df["dWprev"]=ann.d_agua_media_ha.shift(1).loc[df.index]/1000
    df["dp"]=df[f"dP_lag{lag}"]
    cs=["dp","dRain","dRain1","dWprev"]
    if form=="com_tendencia":cs.append("ano_centro")
    if form=="com_vazao":cs.append("dFlow")
    df=df.dropna(subset=["y",*cs])
    if len(df)<21:continue
    fit=OLS(df.y,add_constant(df[cs])).fit(cov_type="HAC",cov_kwds={"maxlags":2})
    ci=fit.conf_int().loc["dp"]
    sens.append({"lag_anos":lag,"especificacao":form,"n":len(df),
     "coef":float(fit.params["dp"]),"ci95_inf":float(ci.iloc[0]),
     "ci95_sup":float(ci.iloc[1]),"p_hac":float(fit.pvalues["dp"])})
pd.DataFrame(sens).to_csv(OUT/"sensibilidade_defasagem_hidrologia.csv",index=False,encoding="utf-8-sig")

# Fora da amostra temporal: comparar chuva base x chuva + lag preespecificado;
# reconstrucao do ano t utilizando chuva t observada, nao previsao de chuva futura.
folds=[]
for limit in [2009,2014,2019]:
  train_end=limit;test_start=limit+1;test_end=min(limit+5,2025)
  for lag in [0,2,3,5]:
    d=ann[ann.ano>=1992].copy()
    d["y"]=d.d_agua_media_ha/1000
    d["dWprev"]=d.d_agua_media_ha.shift(1)/1000
    d["dp"]=d[f"dP_lag{lag}"]
    d=d.dropna(subset=["y","dWprev","dRain","dRain1","dp"])
    tr=d[d.ano<=train_end];te=d[(d.ano>=test_start)&(d.ano<=test_end)]
    if len(tr)<14 or len(te)<4:continue
    xbase=["dRain","dRain1","dWprev"]
    for variant,xcols in [("clima",xbase),("clima_mais_pastagem",xbase+["dp"])]:
      f=OLS(tr.y,add_constant(tr[xcols],has_constant="add")).fit()
      pred=f.predict(add_constant(te[xcols],has_constant="add"))
      rmse=np.sqrt(np.mean((te.y-pred)**2))
      folds.append({"treino_ate":train_end,"teste":f"{test_start}-{test_end}",
       "lag_anos":lag,"modelo":variant,"n_treino":len(tr),"n_teste":len(te),
       "rmse_mil_ha":float(rmse)})
pd.DataFrame(folds).to_csv(OUT/"validacao_blocos_temporais_lags.csv",index=False,encoding="utf-8-sig")

# Graphics; pale moving averages are descriptive and not independent tests.
plt.rcParams.update({"font.family":"DejaVu Sans","figure.facecolor":"white",
 "axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,"grid.alpha":.15})
C={"water":"#1A6B8B","pasture":"#AA854E","rain":"#53937C","grey":"#56646D","lags":"#A64C44"}
fig,axs=plt.subplots(2,1,figsize=(11.6,7.7),sharex=True,layout="constrained")
fig.suptitle("Pantanal de Cáceres | Transformação da paisagem e memória hidrológica",
  fontsize=16,fontweight="bold")
axs[0].plot(ann.ano,ann.pastagem_ha/1e6,color=C["pasture"],lw=1.5,alpha=.45,label="Anual")
axs[0].plot(ann.ano,ann.mm5_pastagem_ha/1e6,color=C["pasture"],lw=2.7,label="Média móvel de 5 anos")
axs[0].set_ylabel("Pastagem na bacia (milhão ha)");axs[0].legend(frameon=False)
axs[1].plot(ann.ano,ann.agua_media_ha/1000,color=C["water"],lw=1.2,alpha=.45,label="Anual")
axs[1].plot(ann.ano,ann.mm3_agua_media_ha/1000,lw=2,color="#66A6BE",label="Média móvel de 3 anos")
axs[1].plot(ann.ano,ann.mm5_agua_media_ha/1000,lw=2.7,color=C["water"],label="Média móvel de 5 anos")
axs[1].set_ylabel("Água média mensal (mil ha)");axs[1].set_xlabel("Ano");axs[1].legend(frameon=False,ncol=3)
fig.savefig(OUT/"FIGURA_01_JANELAS_MOVEIS_3_5_ANOS.png",dpi=215,bbox_inches="tight");plt.close(fig)

fig,ax=plt.subplots(figsize=(11,5.5),layout="constrained")
sub=results[results.desfecho=="Água média mensal"].sort_values("lag_anos")
x=sub.lag_anos.to_numpy();v=sub.coef_kha_por_100kha.to_numpy()
ax.axhline(0,lw=1,c=C["grey"])
ax.errorbar(x,v,yerr=np.array([v-sub.ic95_inf.to_numpy(),sub.ic95_sup.to_numpy()-v]),fmt="o-",color=C["water"],ms=5,capsize=3,lw=1.8)
for _,p in sub.iterrows():
  if p.fdr_5pct:ax.scatter([p.lag_anos],[p.coef_kha_por_100kha],s=145,facecolors="none",edgecolors=C["lags"],lw=2,zorder=10)
ax.set_xticks(np.arange(11));ax.set_xlabel("Defasagem entre alteração de pastagem e alteração de água (anos)")
ax.set_ylabel("Δ água (mil ha) / Δ pastagem (100 mil ha)\nIC95% HAC(2)")
ax.set_title("Associações defasadas (0–10 anos) | Mesma amostra de 30 anos",loc="left",fontweight="bold",fontsize=14)
ax.text(.01,.01,"Círculos vazios: p ajustado FDR em 33 testes < 0,05",transform=ax.transAxes,fontsize=9,color=C["grey"])
fig.savefig(OUT/"FIGURA_02_EFEITOS_DEFASADOS_0_10_ANOS.png",dpi=215,bbox_inches="tight");plt.close(fig)

fig,ax=plt.subplots(figsize=(11.5,5.4),layout="constrained")
for lag,col in [(0,C["pasture"]),(2,C["water"]),(3,C["rain"]),(5,"#8D6AA6")]:
  tmp=rr[rr.lag_anos==lag]
  ax.plot(tmp.ano_final,tmp.r,lw=2,marker="o",ms=2.5,label=f"Defasagem {lag} anos",color=col)
ax.axhline(0,c=C["grey"],lw=1)
ax.set_ylim(-1,1);ax.set_ylabel("Correlação r na janela de 15 anos")
ax.set_xlabel("Último ano da janela");ax.set_title("Janela deslizante: a associação muda no tempo",loc="left",fontsize=15,fontweight="bold")
ax.legend(frameon=False,ncol=2);fig.savefig(OUT/"FIGURA_03_CORRELACAO_DESLIZANTE_15_ANOS.png",dpi=215,bbox_inches="tight");plt.close(fig)

# Multi-hypothesis overview: 3 endpoint sets in one figure.
fig,axs=plt.subplots(3,1,figsize=(12,9),sharex=True,layout="constrained")
for ax,(name,color) in zip(axs,[("Água média mensal",C["water"]),("Água na seca (jul–out)",C["pasture"]),("Área anual de água",C["rain"])]):
  d=results[results.desfecho==name].sort_values("lag_anos")
  ax.axhline(0,c="#777",lw=.9)
  ax.plot(d.lag_anos,d.coef_kha_por_100kha,marker="o",lw=2,color=color)
  ax.fill_between(d.lag_anos,d.ic95_inf,d.ic95_sup,color=color,alpha=.16)
  sig=d[d.fdr_5pct]
  if len(sig):ax.scatter(sig.lag_anos,sig.coef_kha_por_100kha,s=130,facecolor="none",edgecolors="#A23D45",lw=2)
  ax.set_ylabel(name+"\nβ (mil ha / 100 mil ha)")
axs[-1].set_xticks(np.arange(11));axs[-1].set_xlabel("Lag (anos)")
fig.suptitle("Resultados por desfecho | Corrigidos por 33 comparações",fontsize=15,fontweight="bold")
fig.savefig(OUT/"FIGURA_04_SENSIBILIDADE_POR_DESFECHO.png",dpi=215,bbox_inches="tight");plt.close(fig)

# Formal short report with key table
lagsprimary=results[results.desfecho=="Água média mensal"].sort_values("lag_anos")
maxlag=int(lagsprimary.iloc[np.argmax(abs(lagsprimary.coef_kha_por_100kha))].lag_anos)
mins=lagsprimary.sort_values("p_hac").iloc[0]
n_sig=int(results.fdr_5pct.sum())
rpts=[
 "# Pastagens e água: defasagens de 0 a 10 anos — bacia ANA Cáceres 66070004",
 "",
 f"**Recorte:** bacia HydroBASINS L10 com {qc['area_bacia_km2']:.1f} km²; água na intersecção com o bioma Pantanal ({qc['area_pantanal_intersecao_km2']:.1f} km²). Não é todo o Pantanal.",
 "**Fonte:** MapBiomas Água C5, Cobertura C11, CHIRPS v2 e vazões ANA, 1985–2025.",
 "**Método:** expansão anual de pastagens (ΔP_t), diferença anual da média mensal de água (ΔW_t) e desfechos de seca e água anual. 11 defasagens (k=0…10), janela fixa 1996–2025, ajustes por Δchuva_t, Δchuva_(t−1), Δágua_(t−1), erros HAC(2), IC95%, correção FDR-BH em 33 testes. Janela móvel de 15 anos e média móvel 3/5 anos.",
 "",
 "## Teste primário por defasagem",
 "",
 "| Lag (anos) | Coef. Δágua (mil ha / 100 mil ha pastagem) | IC95% | p HAC | p FDR (33 testes) |",
 "|---:|---:|---:|---:|---:|"
]
for v in lagsprimary.itertuples():
 rpts.append(f"| {v.lag_anos} | {v.coef_kha_por_100kha:.3f} | [{v.ic95_inf:.3f}; {v.ic95_sup:.3f}] | {v.p_hac:.3f} | {v.p_fdr_33:.3f} |")
rpts+=["",f"**Menor p bruto do teste primário:** lag {int(mins.lag_anos)} anos (p={mins.p_hac:.4f}, FDR={mins.p_fdr_33:.4f}).",
 f"**Total de resultados FDR significativos entre 33 testes:** {n_sig}.",
 "","## Interpretação","",
 "Um lag estatisticamente significativo não demonstra efeito causal: pastagens e clima seguem trajetórias próprias, há poucos anos, potenciais fatores omitidos e múltiplas hipóteses. Correlações em janelas móveis são **descritivas**, não p-valores causais.",
 "","## Testes de robustez","",
 "- Três desfechos físicos diferentes (média mensal, seca, área anual).",
 "- Diferenças anuais para mitigar tendência comum; mesma janela temporal para todos os lags.",
 "- Sensibilidade com Δvazão (possível mediador hidrológico), tendência e acumulados de 1, 3 e 5 anos.",
 "- Validação de reconstrução fora da amostra em blocos temporais; chuva do próprio ano observada, não previsão climática.",
 "- Não interpretar janelas sobrepostas como observações independentes.",
 "","## Limitações fundamentais","",
 "A pastagem foi mapeada anualmente no mesmo limite, sem informação sobre lotação bovina ou manejo. A área com água não é volume. O bioma Pantanal dentro da bacia da estação abrange apenas um pequeno setor, não a planície inteira. É necessário estudar várias sub-bacias, conectividade, solo, barragens e clima para atribuição causal.",
 "","Arquivos de reprodução, tabelas e gráficos disponíveis neste diretório do ramo de pesquisa."
]
(OUT/"RELATORIO_LAGS_JANELAS.md").write_text("\n".join(rpts),encoding="utf-8")
summary={"anos":41,"anos_fixo":f"{EVAL_START}–2025","n_por_lag":int(lagsprimary.n.iloc[0]),
"endpoint_primario":"mudança na média mensal de área com água","lags_testados":11,"desfechos":3,
"corrigidos_fdr":33,"n_significativos_fdr":n_sig,
"menor_p_primario":{"lag":int(mins.lag_anos),"beta":float(mins.coef_kha_por_100kha),
"p":float(mins.p_hac),"p_fdr":float(mins.p_fdr_33)},
"lag_maior_beta_absoluto":maxlag,
"janelas_moveis_anos":[3,5,15],"area_bacia_km2":qc["area_bacia_km2"],
"area_pantanal_intersecao_km2":qc["area_pantanal_intersecao_km2"],
"erro_nao_causal":"Não extrapolar para a planície inteira nem atribuir causalidade.","arquivos":[p.name for p in OUT.iterdir()]}
(OUT/"RESUMO_LAGS_JANELAS.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
