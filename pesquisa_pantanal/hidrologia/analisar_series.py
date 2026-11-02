#!/usr/bin/env python3
"""Análise científica observacional Cáceres 1985–2025.
Cotas e vazões ANA; inundação MapBiomas C5; chuva CHIRPS v2; pastagem MapBiomas C11.
Regressões HAC, defasagens 0..6 meses, FDR BH, validação temporal bloqueada.
Não demonstram causalidade, nem contabilizam volume de água no Pantanal.
"""
from pathlib import Path
import json, math, warnings
import numpy as np
import pandas as pd
from scipy.stats import pearsonr,spearmanr
from statsmodels.formula.api import ols
from statsmodels.stats.multitest import multipletests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

P=Path("pesquisa_pantanal/hidrologia")
ROOT=P/"resultados"; OUT=P/"analise";OUT.mkdir(parents=True,exist_ok=True)
W=ROOT/"agua_chuva_mensal_caceres_1985_2025.csv"
if not W.exists():raise SystemExit("Série mensal MapBiomas ainda não extraída")
w=pd.read_csv(W,encoding="utf-8-sig")
if len(w)!=492:raise SystemExit(f"Esperava 492 meses reais, recebeu {len(w)}")
c=pd.read_csv(ROOT/"cota_mensal_ana_caceres_1985_2025.csv",encoding="utf-8-sig")
q=pd.read_csv(ROOT/"vazao_mensal_ana_caceres_1985_2025.csv",encoding="utf-8-sig")
a=pd.read_csv("pesquisa_pantanal/caceres/resultados/serie_anual_caceres_1985_2025.csv",encoding="utf-8-sig")
df=w.merge(c.drop(columns=["data"],errors="ignore"),on=["ano","mes"],validate="one_to_one").merge(q,on=["ano","mes"],validate="one_to_one")
df=df.merge(a[["ano","pastagem_plantada_montante_ha"]],on="ano",validate="many_to_one")
df=df.sort_values(["ano","mes"]).reset_index(drop=True)
df["t"]=np.arange(len(df))
df["agua_kha"]=df["agua_superficial_local_planicie_ha"]/1000
df["pastagem_mha"]=df["pastagem_plantada_montante_ha"]/1e6
df["month"]=df["mes"]
df["rain0"]=df["chuva_montante_mm"]
for lag in range(1,7):
 df[f"rain{lag}"]=df["chuva_montante_mm"].shift(lag)
 df[f"cota{lag}"]=df["cota_media_m"].shift(lag)
 df[f"vazao{lag}"]=df["vazao_media_m3_s"].shift(lag)
df["cota0"]=df["cota_media_m"];df["vazao0"]=df["vazao_media_m3_s"]
if not df["data"].equals(pd.Series(pd.date_range("1985-01-01",periods=492,freq="MS").strftime("%Y-%m"))):
 raise SystemExit("Eixo temporal 1985-2025 inconsistente.")
df.to_csv(OUT/"serie_mensal_integrada_ana_mapbiomas_chirps.csv",index=False,encoding="utf-8-sig")

plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,"axes.spines.right":False,
 "figure.facecolor":"white","axes.facecolor":"white","axes.grid":True,"grid.alpha":0.17})
COL={"water":"#156B88","rain":"#519A72","stage":"#C37137","flow":"#6A659D","pasture":"#A58B68","gray":"#5B6672"}
def safe_float(v):return None if v is None or not np.isfinite(v) else round(float(v),6)
# Lags predefinidos; HAC correlacao parcial padronizada (sazonalidade + tendencia linear).
families=[
 ("Chuva montante → cota na estação", "cota_media_m","chuva_montante_mm"),
 ("Cota em Cáceres → água local","agua_kha","cota_media_m"),
 ("Vazão em Cáceres → água local","agua_kha","vazao_media_m3_s"),
 ("Chuva montante → água local","agua_kha","chuva_montante_mm")
]
lagrows=[]
for family,yvar,xvar in families:
 familyrows=[]
 for lag in range(7):
  z=df[["ano","mes","t",yvar,xvar]].copy()
  z["x"]=z[xvar].shift(lag);z["y"]=z[yvar]
  z=z.dropna(subset=["x","y"]).copy()
  if len(z)<100:continue
  z["x_z"]=(z["x"]-z["x"].mean())/z["x"].std(ddof=1)
  z["y_z"]=(z["y"]-z["y"].mean())/z["y"].std(ddof=1)
  m=ols("y_z ~ x_z + C(mes) + t",data=z).fit(cov_type="HAC",cov_kwds={"maxlags":12})
  ci=m.conf_int().loc["x_z"]
  familyrows.append({"familia":family,"lag_meses":lag,"n":len(z),
   "beta_padronizado":safe_float(m.params["x_z"]),"ic95_inf":safe_float(ci.iloc[0]),"ic95_sup":safe_float(ci.iloc[1]),
   "p_hac":safe_float(m.pvalues["x_z"]),"r2":safe_float(m.rsquared)})
 if familyrows:
  pvals=[v["p_hac"] for v in familyrows]
  reject,padj,_,_=multipletests(pvals,alpha=.05,method="fdr_bh")
  for item,pval,reject_ in zip(familyrows,padj,reject):
   item["p_fdr_bh"]=safe_float(pval);item["significativo_fdr"]=bool(reject_)
  lagrows.extend(familyrows)
pd.DataFrame(lagrows).to_csv(OUT/"coeficientes_defasagem_hac_fdr.csv",index=False,encoding="utf-8-sig")
# Modelos explicativos e teste bloqueado: 1985–2014 treino, 2015–2025 teste (nem sempre cobertos por ANA).
base="agua_kha ~ C(mes) + t + rain0 + rain1 + rain2 + rain3"
forms={
 "Chuva+estação+tempo":base,
 "Chuva+cota+estação+tempo":base+" + cota0 + cota1",
 "Chuva+vazão+estação+tempo":base+" + vazao0 + vazao1",
 "Chuva+cota+pastagem+tempo":base+" + cota0 + cota1 + pastagem_mha"
}
records=[]
models={}
for name,formula in forms.items():
 # Todas as comparacoes usam a mesma amostra da familia do modelo de cota para evitar vantagem artificial.
 features=("cota0","cota1","pastagem_mha") if "pastagem" in name else \
           ("cota0","cota1") if "cota" in name else \
           ("vazao0","vazao1") if "vazão" in name else ()
 req=["agua_kha","rain0","rain1","rain2","rain3",*features]
 d=df.dropna(subset=req).copy()
 train=d[d["ano"]<=2014];test=d[d["ano"]>=2015]
 if len(train)<100 or len(test)<30:continue
 m=ols(formula,data=train).fit()
 pred=m.predict(test)
 rmse=math.sqrt(float(np.mean((pred-test["agua_kha"])**2)))
 maev=float(np.mean(np.abs(pred-test["agua_kha"])))
 full=ols(formula,data=d).fit(cov_type="HAC",cov_kwds={"maxlags":12})
 models[name]=(full,d)
 p=full.pvalues.get("pastagem_mha")
 ci=full.conf_int().loc["pastagem_mha"].tolist() if p is not None else [None,None]
 records.append({"modelo":name,"n_total":len(d),"n_treino":len(train),"n_teste":len(test),
 "rmse_teste_mil_ha":round(rmse,4),"mae_teste_mil_ha":round(maev,4),"r2_ajustado_geral":round(float(full.rsquared_adj),4),
 "beta_pastagem_mha":safe_float(full.params.get("pastagem_mha",float("nan"))),
 "p_hac_pastagem":safe_float(p) if p is not None else None,
 "ic95_pastagem_inf":safe_float(ci[0]),"ic95_pastagem_sup":safe_float(ci[1])})
pd.DataFrame(records).to_csv(OUT/"modelos_validacao_temporal.csv",index=False,encoding="utf-8-sig")
# Coeficientes são associações ajustadas, NÃO contribuição causal.
a_summary=df.groupby("ano",as_index=False).agg(agua_media_mensal_kha=("agua_kha","mean"),
 chuva_montante_mm=("chuva_montante_mm","sum"),cota_media_m=("cota_media_m","mean"),
 vazao_media_m3_s=("vazao_media_m3_s","mean"),
 n_meses_cota=("cota_media_m","count"),n_meses_vazao=("vazao_media_m3_s","count"),
 pastagem_montante_mha=("pastagem_mha","first"))
a_summary.loc[a_summary.n_meses_cota<10,"cota_media_m"]=np.nan
a_summary.loc[a_summary.n_meses_vazao<10,"vazao_media_m3_s"]=np.nan
a_summary.to_csv(OUT/"serie_anual_comparativa_1985_2025.csv",index=False,encoding="utf-8-sig")
# Figura 1 - serie combinada, nature-like.
fig,axes=plt.subplots(4,1,figsize=(11,10),sharex=True,layout="constrained")
fig.suptitle("Cáceres | Ciclo hidrológico e transformação da paisagem",x=.08,y=1.02,ha="left",fontweight="bold",fontsize=17)
for ax,col,label,color in [
 (axes[0],"chuva_montante_mm","Chuva nas cabeceiras (mm/ano)",COL["rain"]),
 (axes[1],"cota_media_m","Cota média em Cáceres (m)",COL["stage"]),
 (axes[2],"vazao_media_m3_s","Vazão média em Cáceres (m³/s)",COL["flow"]),
 (axes[3],"agua_media_mensal_kha","Água detectada no recorte local (mil ha)",COL["water"])
]:
 ax.plot(a_summary.ano,a_summary[col],color=color,linewidth=2.15,marker="o",markersize=2.7)
 ax.set_ylabel(label,labelpad=10,fontsize=9)
 ax.grid(True,alpha=.16)
axes[3].set_xlabel("Ano")
fig.text(.08,-.01,"Fontes: ANA (cota e vazão) · MapBiomas Água C5 · CHIRPS v2 · HydroBASINS · 1985–2025. Médias mensais, não volume.",fontsize=8,color=COL["gray"])
fig.savefig(OUT/"FIGURA_01_SERIES_OBSERVADAS.png",dpi=200,bbox_inches="tight");plt.close(fig)
# Climatologia mensal de chuva, cota, vazão e água.
clim=df.groupby("mes",as_index=False).agg(chuva=("chuva_montante_mm","mean"),
 cota=("cota_media_m","mean"),vazao=("vazao_media_m3_s","mean"),agua=("agua_kha","mean"))
fig,axs=plt.subplots(2,2,figsize=(12,7),layout="constrained")
for ax,key,lab,color in [(axs[0,0],"chuva","Chuva nas cabeceiras (mm/mês)",COL["rain"]),
 (axs[0,1],"cota","Cota média em Cáceres (m)",COL["stage"]),
 (axs[1,0],"vazao","Vazão média em Cáceres (m³/s)",COL["flow"]),
 (axs[1,1],"agua","Água superficial local (mil ha)",COL["water"])]:
 ax.plot(clim.mes,clim[key],marker="o",lw=2.4,color=color,ms=5)
 ax.set_ylabel(lab);ax.set_xticks(range(1,13))
 ax.set_xticklabels(["J","F","M","A","M","J","J","A","S","O","N","D"])
 ax.grid(alpha=.17)
fig.suptitle("Climatologia mensal | Escalas hidrológicas distintas",fontweight="bold",fontsize=15)
fig.savefig(OUT/"FIGURA_02_SAZONALIDADE_HIDROLOGICA.png",dpi=200,bbox_inches="tight");plt.close(fig)
# Lags: four panels with HAC CI and FDR significance.
if lagrows:
 fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True,layout="constrained")
 for ax,(name,_,_) in zip(axes.flat,families):
  d=pd.DataFrame([x for x in lagrows if x["familia"]==name])
  if d.empty:continue
  x=d.lag_meses.values;y=d.beta_padronizado.values
  err=np.vstack([y-d.ic95_inf.values,d.ic95_sup.values-y])
  ax.axhline(0,color="#555555",lw=.85)
  ax.errorbar(x,y,yerr=err,fmt="o-",capthick=1.1,capsize=3,linewidth=1.7,color=COL["water"])
  for row in d.itertuples():
   if row.significativo_fdr:ax.scatter(row.lag_meses,row.beta_padronizado,s=110,facecolors="none",edgecolors="#CB6C30",linewidths=1.8)
  ax.set_title(name,loc="left",fontsize=11,fontweight="bold")
  ax.set_xlabel("Defasagem do indicador explicativo (meses)");ax.set_ylabel("Coeficiente padronizado ± IC95%")
  ax.set_xticks(range(7));ax.grid(alpha=.14)
 fig.suptitle("Defasagens: associações ajustadas por sazonalidade e tendência (HAC)",fontweight="bold",fontsize=14)
 fig.text(.01,-.01,"Círculos vazios = FDR BH < 0,05; pares avaliados por mês; ausência de controle causal.",color=COL["gray"],fontsize=8)
 fig.savefig(OUT/"FIGURA_03_DEFASAGENS_HAC.png",dpi=200,bbox_inches="tight");plt.close(fig)
if records:
 fig,ax=plt.subplots(figsize=(10,4.5),layout="constrained")
 r=sorted(records,key=lambda x:x["rmse_teste_mil_ha"])
 ax.barh([x["modelo"] for x in r],[x["rmse_teste_mil_ha"] for x in r],color=COL["water"])
 ax.invert_yaxis();ax.set_xlabel("RMSE na janela de teste 2015–2025 (mil hectares) ↓ melhor")
 ax.set_title("Validação temporal fora do treino | Modelos observacionais",loc="left",fontweight="bold",fontsize=14)
 ax.grid(axis="x",alpha=.14)
 fig.savefig(OUT/"FIGURA_04_COMPARACAO_MODELOS.png",dpi=200,bbox_inches="tight");plt.close(fig)
# Diagnosticos e discussao.
p_corr=pearsonr(df.dropna(subset=["cota_media_m","vazao_media_m3_s"]).cota_media_m,
 df.dropna(subset=["cota_media_m","vazao_media_m3_s"]).vazao_media_m3_s)
best={name:sorted([v for v in lagrows if v["familia"]==name],key=lambda x:abs(x["beta_padronizado"]),reverse=True)[0] for name,_,_ in families}
summary={"janela":"1985–2025","n_meses_total":len(df),"n_valid_cota":int(df.cota_media_m.notna().sum()),
 "n_valid_vazao":int(df.vazao_media_m3_s.notna().sum()),
 "n_valid_agua":int(df.agua_kha.notna().sum()),
 "correlacao_cota_vazao_r":safe_float(p_corr.statistic),
 "lag_max_associacao_absoluta":best,"modelos":records,
 "climatologia_pico":{"chuva":int(clim.loc[clim.chuva.idxmax(),"mes"]),
 "cota":int(clim.loc[clim.cota.idxmax(),"mes"]),"vazao":int(clim.loc[clim.vazao.idxmax(),"mes"]),
 "agua":int(clim.loc[clim.agua.idxmax(),"mes"])},
 "limitacoes":["Ausencia de meses ANA nao preenchida", "Cota e vazao oriundas de serie bruta com possiveis mudancas de secao/curva-chave",
 "Area de agua nao representa volume de inundacao", "Chuva montante CHIRPS, nao redes pluviometricas locais",
 "Pastagem e tendencia temporal colineares, coeficiente nao causal",
 "Contemporaneidade cota/agua no mesmo mes nao estabelece direcao causal",
 "MapBiomas processado a 120m em pesquisa piloto, nao resolucao nativa 30m"]}
(OUT/"resumo_estatistico.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
lines=["# Cáceres — resultados hidrológicos científicos (1985–2025)","",
 "Fonte: ANA, MapBiomas C5, MapBiomas C11, CHIRPS v2, HydroBASINS. Reprodução e data no GitHub.",
 "",
 f"Meses: {len(df)}, cota válida: {summary['n_valid_cota']}, vazão válida: {summary['n_valid_vazao']}.",
 f"Correlação bruta cota–vazão: r={summary['correlacao_cota_vazao_r']}.","",
 "## Defasagens pré-definidas (0–6 meses), com mês do ano, tendência linear, HAC(12) e FDR BH",""]
for name,v in best.items():
 lines.append(f"- {name}: maior |β| em lag {v['lag_meses']} meses; β={v['beta_padronizado']}; IC95%=[{v['ic95_inf']},{v['ic95_sup']}]; p_FDR={v['p_fdr_bh']}; n={v['n']}.")
lines+=["","**Não escolher apenas o maior lag para inferência causal.** Os 7 testes por família são exploratórios, mesmo após FDR.","",
 "## Reconstrução fora do treino (1985–2014 → 2015–2025)",""]
for v in records:
 lines.append(f"- {v['modelo']}: RMSE={v['rmse_teste_mil_ha']:.3f} mil ha; n treino={v['n_treino']}, n teste={v['n_teste']}; p_HAC pastagem={v['p_hac_pastagem']}.")
lines+=["","## Limitações","","- "+"\\n- ".join(summary["limitacoes"]),
 "","**Não existe estimativa confiável de causalidade pecuária → perda de água nesta análise.**"]
(OUT/"RELATORIO_HIDROLOGICO_CACERES.md").write_text("\n".join(lines),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2)[:18000])
