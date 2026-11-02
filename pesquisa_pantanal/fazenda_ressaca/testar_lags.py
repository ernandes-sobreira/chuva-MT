#!/usr/bin/env python3
"""Lags de 0-10 anos e janelas no hotspot 3x3 próximo à Fazenda Ressaca.
Observacional, não delimitação da fazenda, pastagem anual a 30m.
"""
from pathlib import Path
import json, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
from statsmodels.api import OLS, add_constant
from statsmodels.stats.multitest import multipletests
P=Path("pesquisa_pantanal/fazenda_ressaca/resultados")
status=json.loads((P/"STATUS_SERIE_HOTSPOT.json").read_text(encoding="utf-8"))
assert status["status"]=="concluído" and status["dados"]["meses"]==492
m=pd.read_csv(P/"SERIE_MENSAL_HOTSPOT_1985_2025.csv",encoding="utf-8-sig")
a=pd.read_csv(P/"SERIE_ANUAL_HOTSPOT_1985_2025.csv",encoding="utf-8-sig")
assert len(m)==492 and len(a)==41
t=m.groupby("ano").agg(agua_mensal_media_ha=("agua_mensal_ha","mean"),
 chuva_ano_mm=("chuva_mm","sum")).reset_index()
t["agua_seca_ha"]=m[m.mes.isin([7,8,9,10])].groupby("ano").agua_mensal_ha.mean().values
t=t.merge(a,on="ano",validate="one_to_one")
for c in ["agua_mensal_media_ha","agua_seca_ha","agua_anual_ha","chuva_ano_mm","pastagem_ha"]:
 t["d_"+c]=t[c].diff()
for k in range(11): t[f"p{k}"]=t.d_pastagem_ha.shift(k)/100
t["rain0"]=t.d_chuva_ano_mm/100
t["rain1"]=t.rain0.shift(1)
t["waterprev"]=t.d_agua_mensal_media_ha.shift(1)/1000
for k in (3,5):
 for c in ["agua_mensal_media_ha","pastagem_ha"]:
  t[f"rolling{k}_{c}"]=t[c].rolling(k,min_periods=k).mean()
t.to_csv(P/"SERIE_ANUAL_ANALISE_LAG_HOTSPOT.csv",index=False,encoding="utf-8-sig")
rows=[]
targets=[("Água média mensal","d_agua_mensal_media_ha"),("Água na seca","d_agua_seca_ha"),("Água anual","d_agua_anual_ha")]
for label,col in targets:
 for lag in range(11):
  data=t[t.ano>=1996].copy()
  data["y"]=data[col]/1000
  data["y1"]=t[col].shift(1).loc[data.index]/1000
  data["past"]=data[f"p{lag}"]
  data=data.dropna(subset=["y","y1","past","rain0","rain1"])
  if len(data)!=30:raise RuntimeError(f"Amostra desigual: {label} lag {lag} n={len(data)}")
  mod=OLS(data.y,add_constant(data[["past","rain0","rain1","y1"]])).fit(cov_type="HAC",cov_kwds={"maxlags":2})
  lo,hi=mod.conf_int().loc["past"]
  rows.append({"indicador":label,"lag_anos":lag,"n":len(data),
     "beta_mil_ha_por_100_ha_past":float(mod.params["past"]),
     "ic95_inf":float(lo),"ic95_sup":float(hi),
     "p_HAC":float(mod.pvalues["past"]),"R2_ajustado":float(mod.rsquared_adj)})
out=pd.DataFrame(rows)
rej,adj,_,_=multipletests(out.p_HAC,method="fdr_bh",alpha=.05)
out["p_fdr_33"]=adj;out["fdr_significativo"]=rej
out.to_csv(P/"DEFASAGENS_0_A_10_ANOS_HOTSPOT.csv",index=False,encoding="utf-8-sig")
# Correlação móvel de 15 anos: apenas descritiva, mesmos dados não são independentes.
rolling=[]
for lag in (0,2,3,5):
 for end in range(1999,2026):
  sample=t[(t.ano>=(end-14))&(t.ano<=end)].dropna(subset=[f"p{lag}","d_agua_mensal_media_ha"])
  if len(sample)>=10 and sample[f"p{lag}"].std()>0:
   corr=pearsonr(sample[f"p{lag}"],sample.d_agua_mensal_media_ha).statistic
   rolling.append({"lag_anos":lag,"ano_fim":end,"n":len(sample),"r":float(corr)})
pd.DataFrame(rolling).to_csv(P/"JANELA_MOVEL_15_ANOS_HOTSPOT.csv",index=False,encoding="utf-8-sig")
plt.rcParams.update({"font.family":"DejaVu Sans","figure.facecolor":"white","axes.spines.top":False,
 "axes.spines.right":False,"axes.grid":True,"grid.alpha":.15})
# Figure 1: land transformation + surface water trajectories, same years.
fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,layout="constrained")
axes[0].plot(t.ano,t.pastagem_ha,color="#C08F56",lw=1.6,alpha=.6,label="Pastagem anual")
axes[0].plot(t.ano,t.rolling5_pastagem_ha,color="#8F6237",lw=2.5,label="Média móvel 5 anos")
axes[0].set_ylabel("Pastagem plantada (ha)");axes[0].legend(frameon=False)
axes[1].plot(t.ano,t.agua_mensal_media_ha,color="#237BA4",alpha=.55,label="Água mensal média por ano")
axes[1].plot(t.ano,t.rolling5_agua_mensal_media_ha,color="#124C72",lw=2.6,label="Média móvel 5 anos")
axes[1].set_ylabel("Área média mensal com água (ha)");axes[1].set_xlabel("Ano");axes[1].legend(frameon=False)
fig.suptitle("Entorno Ressaca | 3.600 ha em 41 anos (1985–2025)",fontsize=17,fontweight="bold")
fig.savefig(P/"FIGURA_RESSACA_SERIES_1985_2025.png",dpi=205,bbox_inches="tight");plt.close(fig)
# Figure 2: annual lag effects ± HAC 95%.
primary=out[out.indicador=="Água média mensal"].sort_values("lag_anos")
fig,ax=plt.subplots(figsize=(11.5,5.5),layout="constrained")
x=primary.lag_anos.to_numpy();y=primary.beta_mil_ha_por_100_ha_past.to_numpy()
ax.axhline(0,color="#59646D",lw=1)
ax.errorbar(x,y,yerr=np.vstack([y-primary.ic95_inf.to_numpy(),primary.ic95_sup.to_numpy()-y]),
 fmt="o-",color="#25779B",capsize=3,linewidth=2)
sig=primary[primary.fdr_significativo]
if len(sig):ax.scatter(sig.lag_anos,sig.beta_mil_ha_por_100_ha_past,s=130,facecolors="none",edgecolors="#A14844",linewidths=2)
ax.set_xticks(range(11));ax.set_xlabel("Defasagem da mudança de pastagem (anos)")
ax.set_ylabel("Δ água (mil ha) por Δ pastagem (100 ha) | IC95% HAC")
ax.set_title("Lag 0–10 anos no hotspot | Mesmos 30 anos comparáveis",loc="left",fontweight="bold",fontsize=15)
fig.savefig(P/"FIGURA_RESSACA_DEFASAGEM_0_10.png",dpi=205,bbox_inches="tight");plt.close(fig)
# Figure 3: first year of persistent 2-year pasture in native->pasture2025 pixels.
hist=status["ano_primeira_pastagem_2anos_persistente"]["firstyear"]
periods=[("1986–1994",1986,1994),("1995–2004",1995,2004),("2005–2014",2005,2014),("2015–2024",2015,2024)]
counts=[sum(float(v) for yr,v in hist.items() if yr.isdigit() and int(yr)>=lo and int(yr)<=hi) for _,lo,hi in periods]
tot=sum(counts)
fig,ax=plt.subplots(figsize=(10,4.6),layout="constrained")
ax.bar([s[0] for s in periods],[v/tot*100 for v in counts],color=["#A6BD8C","#DDB578","#C98B5B","#A25D4C"])
ax.set_ylim(0,100);ax.set_ylabel("Proporção dos pixels elegíveis (%)")
ax.set_title("Primeira classificação persistente como pastagem (2 anos consecutivos)",loc="left",fontweight="bold",fontsize=13)
fig.savefig(P/"FIGURA_RESSACA_ANO_CONVERSAO_PIXELS.png",dpi=205,bbox_inches="tight");plt.close(fig)
best=primary.sort_values("p_HAC").iloc[0]
summary={"status":"concluido","recorte":"3x3 células de 2km no entorno do centro cadastral da Fazenda Ressaca, não propriedade",
"n_anos":41,"n_para_lag":30,"n_testes_fdr":33,"significativos_fdr":int(rej.sum()),
"lag_menor_p_primario":int(best.lag_anos),"p_hac_menor":round(float(best.p_HAC),6),
"p_fdr_menor":round(float(best.p_fdr_33),6),
"pastagem_1985_ha":round(float(t.pastagem_ha.iloc[0]),2),
"pastagem_2005_ha":round(float(t[t.ano==2005].pastagem_ha.iloc[0]),2),
"pastagem_2025_ha":round(float(t.pastagem_ha.iloc[-1]),2),
"agua_media_mensal_1985_ha":round(float(t.agua_mensal_media_ha.iloc[0]),2),
"agua_media_mensal_2025_ha":round(float(t.agua_mensal_media_ha.iloc[-1]),2),
"conversao_decadas_percent":[round(v/tot*100,1) for v in counts],
"cautela":"Controles apenas de precipitação e memória hidrológica; sem conectividade, solo, manejo, vazão local ou perímetro validado. Associação não causal."}
(P/"RESUMO_RESULTADOS_HOTSPOT.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
