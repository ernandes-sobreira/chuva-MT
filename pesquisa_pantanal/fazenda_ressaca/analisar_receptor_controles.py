#!/usr/bin/env python3
"""Comparação observacional pré/pós e lags com área receptora D8 vs controles locais.
Sem atribuição causal: MERIT de 90 m é unidirecional; várzea pode bifurcar, inundar de montante, ter remanso.
A exposição foi selecionada por uso do solo, e a resposta por critérios hidrológicos e água basal.
"""
from pathlib import Path
import json,math, warnings
import numpy as np,pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.formula.api import ols
from statsmodels.api import OLS,add_constant
from statsmodels.stats.multitest import multipletests
from scipy.stats import pearsonr

P=Path("pesquisa_pantanal/fazenda_ressaca")
R=P/"jusante"
status=json.loads((R/"STATUS_PAREAMENTO_HIDROLOGICO.json").read_text(encoding="utf-8"))
if status["status"]!="concluido":raise SystemExit("Pares não extraídos")
w=pd.read_csv(R/"GRUPOS_PILOTO_MENSAL_1985_2025.csv",encoding="utf-8-sig")
a=pd.read_csv(R/"GRUPOS_PILOTO_ANUAL_1985_2025.csv",encoding="utf-8-sig")
assert len(w)==4*492 and len(a)==4*41 and all(w.groupby("grupo").size()==492)
grps=["FONTE_PASTAGEM","RECEPTOR_D8","CONTROLE_NORTE","CONTROLE_SENSIBILIDADE"]
assert set(w.grupo.unique())==set(grps)
M={}
for k in ["agua_mensal_ha","chuva_mensal_mm","pastagem_anual_ha"]:
 tab=w.pivot(index=["ano","mes"],columns="grupo",values=k)
 tab=tab.reindex(columns=grps)
 tab.columns=[k+"_"+col for col in tab.columns]
 M[k]=tab
df=pd.concat(M.values(),axis=1).reset_index().sort_values(["ano","mes"]).reset_index(drop=True)
assert len(df)==492
# Must hold for all groups; amount mapped in 2km cells; source larger.
for g in grps:
 area=3600 if g=="FONTE_PASTAGEM" else 1200
 assert df[f"agua_mensal_ha_{g}"].max()<area*1.02
 assert df[f"pastagem_anual_ha_{g}"].max()<area*1.02

for control in grps[2:]:
 df[f"diff_pct_{control}"]=(df.agua_mensal_ha_RECEPTOR_D8-df[f"agua_mensal_ha_{control}"])/1200*100
df["year_frac"]=df.ano+(df.mes-1)/12
df["t"]=np.arange(len(df))/12
df["period"]=np.select([df.ano<=1994,df.ano<=2004],["pre","transition"],default="post")
df["rain"]=df["chuva_mensal_mm_FONTE_PASTAGEM"]
s=pd.read_csv("pesquisa_pantanal/hidrologia/resultados/cota_mensal_ana_caceres_1985_2025.csv",encoding="utf-8-sig")
df=df.merge(s[["ano","mes","cota_media_m"]],on=["ano","mes"],validate="one_to_one")
df["post"]=(df.ano>=2005).astype(int);df["transition"]=((df.ano>=1995)&(df.ano<=2004)).astype(int)
df.to_csv(R/"SERIE_INTEGRADA_JUSANTE_CONTROLES.csv",index=False,encoding="utf-8-sig")
annual=pd.DataFrame({"ano":list(range(1985,2026))})
for g in grps:
 annual=annual.merge(df.groupby("ano",as_index=False).agg(
 **{f"agua_media_{g}":(f"agua_mensal_ha_{g}","mean"),
 f"chuva_{g}":(f"chuva_mensal_mm_{g}","sum"),
 f"pastagem_{g}":(f"pastagem_anual_ha_{g}","first")}),on="ano",validate="one_to_one")
for control in grps[2:]:
 annual[f"D_{control}"] = annual[f"agua_media_RECEPTOR_D8"] - annual[f"agua_media_{control}"]
for g in grps:
 annual[f"agua_seca_{g}"]=df[df.mes.isin([7,8,9,10])].groupby("ano")[f"agua_mensal_ha_{g}"].mean().to_numpy()
for control in grps[2:]:
 annual[f"seca_D_{control}"]=annual.agua_seca_RECEPTOR_D8-annual[f"agua_seca_{control}"]
annual.to_csv(R/"SERIE_ANUAL_JUSANTE_CONTROLES.csv",index=False,encoding="utf-8-sig")

# Make baseline and post descriptives; no 'causal difference in differences'.
descr=[]
for control in grps[2:]:
 x=df[f"diff_pct_{control}"]
 for period in ["pre","transition","post"]:
  sample=df[df.period==period]
  descr.append({"controle":control,"periodo":period,"n_meses":len(sample),
   "agua_receptor_media_ha":float(sample.agua_mensal_ha_RECEPTOR_D8.mean()),
   "agua_controle_media_ha":float(sample[f"agua_mensal_ha_{control}"].mean()),
   "diferenca_receptor_menos_controle_pontos_percentuais":float(sample[f"diff_pct_{control}"].mean())})
pd.DataFrame(descr).to_csv(R/"PRE_TRANSICAO_POS_DESCRITIVO.csv",index=False,encoding="utf-8-sig")
# Pretrends and paired series correlation in 1985–1994 before large conversion
baselines=[]
for ctrl in grps[2:]:
 pre=df[df.ano<=1994].copy()
 pre["gap"]=pre[f"diff_pct_{ctrl}"]
 m=ols("gap ~ t + C(mes)",data=pre).fit(cov_type="HAC",cov_kwds={"maxlags":12})
 ci=m.conf_int().loc["t"].to_list()
 r=pearsonr(pre.agua_mensal_ha_RECEPTOR_D8,pre[f"agua_mensal_ha_{ctrl}"])
 baselines.append({"controle":ctrl,"n_meses":len(pre),"r_mensal_pre":float(r.statistic),
   "p_r_pre":float(r.pvalue),"gap_medio_pre_pp":float(pre.gap.mean()),
   "dif_tendencia_pp_ano":float(m.params["t"]),"ic95_inf":float(ci[0]),"ic95_sup":float(ci[1]),
   "p_hac_tendencia_pre":float(m.pvalues["t"])})
pd.DataFrame(baselines).to_csv(R/"PARALELISMO_PRE_1985_1994.csv",index=False,encoding="utf-8-sig")
# Monthly regression interrupted time series in physical and climatic context:
# Difference of receptor - control: common time and stage controls are exploratory.
monthly_models=[]
for ctrl in grps[2:]:
 d=df.dropna(subset=["cota_media_m"]).copy()
 d["gap"]=d[f"diff_pct_{ctrl}"]
 models={
  "clima_sazonal": "gap ~ post + transition + C(mes) + rain + t",
  "clima_sazonal_cota": "gap ~ post + transition + C(mes) + rain + cota_media_m + t"
 }
 for name,f in models.items():
  sub=d if "cota" in name else df.copy()
  if "gap" not in sub:sub["gap"]=sub[f"diff_pct_{ctrl}"]
  mod=ols(f,data=sub).fit(cov_type="HAC",cov_kwds={"maxlags":12})
  c=mod.conf_int().loc["post"]
  monthly_models.append({"controle":ctrl,"modelo":name,"n":len(sub),
   "coef_post_2005_pp":float(mod.params["post"]),"ci95_inf":float(c.iloc[0]),
   "ci95_sup":float(c.iloc[1]),"p_HAC":float(mod.pvalues["post"]),
   "R2ajustado":float(mod.rsquared_adj)})
pd.DataFrame(monthly_models).to_csv(R/"MODELOS_INTERROMPIDOS_EXPLORATORIOS.csv",index=False,encoding="utf-8-sig")

# Lag annual 0..10 over SAME window 1996–2025, source expansion annual Δpasture, water difference Δ(R−C).
# p correction simultaneously over 2 controls x two hydrological water endpoints x 11 lag=44 tests.
lagrows=[]
annual["d_pasture_source"]=annual.pastagem_FONTE_PASTAGEM.diff()
annual["rain_source"]=annual.chuva_FONTE_PASTAGEM
annual["dRain"]=annual.rain_source.diff()/100
annual["dRain_prev"]=annual.dRain.shift(1)
for ctrl in grps[2:]:
 for label,column in [("ano",f"D_{ctrl}"),("seca",f"seca_D_{ctrl}")]:
  annual["y_change"]=annual[column].diff()/100 # 100 ha units
  annual["y_change_prev"]=annual["y_change"].shift(1)
  for lag in range(11):
   annual["x"]=annual.d_pasture_source.shift(lag)/100 # 100 ha source expansion units
   d=annual[annual.ano>=1996].dropna(subset=["x","y_change","dRain","dRain_prev","y_change_prev"])
   assert len(d)==30,(ctrl,label,lag,len(d))
   fit=OLS(d.y_change,add_constant(d[["x","dRain","dRain_prev","y_change_prev"]])).fit(
      cov_type="HAC",cov_kwds={"maxlags":2})
   ci=fit.conf_int().loc["x"]
   lagrows.append({"controle":ctrl,"desfecho":label,"lag_anos":lag,"n":len(d),
     "beta_delta_agua_100ha_por_delta_past100ha":float(fit.params["x"]),
     "ic95_inf":float(ci.iloc[0]),"ic95_sup":float(ci.iloc[1]),
     "p_hac":float(fit.pvalues["x"]),"r2adj":float(fit.rsquared_adj)})
lag=pd.DataFrame(lagrows)
sig,padj,_,_=multipletests(lag.p_hac,method="fdr_bh")
lag["p_fdr_44"]=padj;lag["significativo_fdr"]=sig
lag.to_csv(R/"LAGS_RECEPTOR_VS_CONTROLE_0_10_ANOS.csv",index=False,encoding="utf-8-sig")
# figures
plt.rcParams.update({"font.family":"DejaVu Sans","figure.facecolor":"white","axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,"grid.alpha":.16})
c={"rec":"#146A8C","ctrl":"#8E9A60","source":"#B78244","other":"#8E78AA"}
fig,axes=plt.subplots(2,1,figsize=(12.2,8),sharex=True,layout="constrained")
ax=axes[0]
ax.plot(annual.ano,annual.pastagem_FONTE_PASTAGEM,color=c["source"],lw=2.5,label="Pastagem na área de conversão (3.600 ha)")
ax.axvspan(1995,2004,color="#D8D3C3",alpha=.38);ax.legend(frameon=False)
ax.set_ylabel("Pastagem plantada (ha)")
ax=axes[1]
for g,color,lab in [("RECEPTOR_D8",c["rec"],"Receptor na drenagem (1.200 ha)"),
 ("CONTROLE_NORTE",c["ctrl"],"Controle norte (1.200 ha)"),
 ("CONTROLE_SENSIBILIDADE",c["other"],"Segundo controle (1.200 ha)")]:
 ax.plot(annual.ano,annual[f"agua_media_{g}"],marker="o",ms=2.2,lw=1.6,color=color,label=lab)
ax.axvspan(1995,2004,color="#D8D3C3",alpha=.38)
ax.set_ylabel("Água superficial média mensal (ha)");ax.set_xlabel("Ano")
ax.legend(frameon=False,ncol=2,fontsize=9)
fig.suptitle("Expansão de pastagem e água a jusante | Entorno Ressaca, 1985–2025",fontweight="bold",fontsize=16)
fig.savefig(R/"FIGURA_SERIES_RECEPTOR_CONTROLES.png",dpi=205,bbox_inches="tight");plt.close(fig)
fig,ax=plt.subplots(figsize=(12,5),layout="constrained")
for ctrl,color in [("CONTROLE_NORTE",c["rec"]),("CONTROLE_SENSIBILIDADE",c["other"])]:
 d=lag[(lag.controle==ctrl)&(lag.desfecho=="ano")].sort_values("lag_anos")
 xx=d.lag_anos.to_numpy();yy=d.beta_delta_agua_100ha_por_delta_past100ha.to_numpy()
 err=(d.ic95_sup-d.ic95_inf).to_numpy()/2
 ax.plot(xx,yy,marker="o",color=color,lw=2,label=ctrl)
 ax.fill_between(xx,d.ic95_inf,d.ic95_sup,color=color,alpha=.12)
ax.axhline(0,lw=.9,color="#555")
ax.set_xticks(range(11));ax.set_xlabel("Defasagem da mudança de pastagens (anos)")
ax.set_ylabel("Δ diferença de água receptor–controle\npor Δ 100 ha de pastagem (100 ha)")
ax.set_title("Defasagem 0–10 anos: sinais observacionais e intervalos de confiança",loc="left",fontweight="bold")
ax.legend(frameon=False)
fig.savefig(R/"FIGURA_LAGS_RECEPTOR_CONTROLE.png",dpi=205,bbox_inches="tight");plt.close(fig)

# Annual difference observed relative to pre-window.
fig,ax=plt.subplots(figsize=(12,5),layout="constrained")
for ctrl,color in [("CONTROLE_NORTE",c["rec"]),("CONTROLE_SENSIBILIDADE",c["other"])]:
 ax.plot(annual.ano,annual[f"D_{ctrl}"],color=color,lw=2,label="Receptor menos "+ctrl.replace("_"," ").lower())
ax.axvspan(1995,2004,color="#D8D3C3",alpha=.38,label="Conversão principal da pastagem")
ax.axhline(0,color="#777",lw=.8);ax.set_ylabel("Diferença de superfície mensal de água (ha)")
ax.set_xlabel("Ano");ax.legend(frameon=False)
ax.set_title("Água do receptor menos áreas-controle | Mesma área por grupo",loc="left",fontweight="bold")
fig.savefig(R/"FIGURA_DIFERENCA_AGUA_RECEPTORES.png",dpi=205,bbox_inches="tight");plt.close(fig)

summary={"grupos":status["groups"],"area_fonte_ha":3600,"area_receptor_ha":1200,"area_controle_ha":1200,
 "n_months":len(df),"n_years":len(annual),"pre_anos":"1985-1994","transicao":"1995-2004","post":"2005-2025",
 "pareamento_pre":baselines,"comparacao_pre_pos":descr,"modelo_interrompido":monthly_models,
 "lag_primeiro_controle":lag[(lag.controle=="CONTROLE_NORTE")&(lag.desfecho=="ano")].to_dict("records"),
 "n_testes_lag":len(lag),"n_fdr_sig":int(lag.significativo_fdr.sum()),
 "melhor_lag_bruto":{"p":float(lag.p_hac.min()),"linha":lag.iloc[lag.p_hac.argmin()].to_dict()},
 "limites":["Não são verdadeiros imóveis nem bacias oficiais, mas células de 2km.",
 "Trajetória de escoamento MERIT D8 na planície pantaneira é aproximada e pode perder bifurcações.",
 "Controles podem compartilhar enchentes regionais, ser influenciados por remanso e não serem independentes.",
 "Modelos com cota ANA são análises de sensibilidade, não controles causais independentes se a vazão for mediadora.",
 "A pré-tendência deve ser avaliada antes de qualquer contraste pré/pós, e falta replicação espacial."],
 "conclusao_nao_causal":True}
def cvt(x):
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,)):return float(x)
 return str(x)
(R/"RESUMO_PILOTO_JUSANTE_CONTROLES.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=cvt),encoding="utf-8")
lines=["# Piloto receptor e controles — entorno Fazenda Ressaca","",
"**Recorte:** 3.600 ha da área com expansão de pastagens; 1.200 ha do receptor atravessado por caminhos MERIT D8; dois grupos-controle de 1.200 ha. Nenhum deles é perímetro fundiário. Cota ANA e chuva CHIRPS são dados observados.",
"**Ressalva:** MERIT é aproximação monodirecional, insuficiente para comprovar conectividade hidráulica na planície alagável.","",
"## Comparabilidade prévia (1985–1994)",""]
for x in baselines:lines.append(f"- {x['controle']}: r pré={x['r_mensal_pre']:.3f}; tendência de diferença={x['dif_tendencia_pp_ano']:.3f} pp/ano (IC95% {x['ic95_inf']:.3f}–{x['ic95_sup']:.3f}), p HAC={x['p_hac_tendencia_pre']:.4g}.")
lines+=["","## Mudança pré/pós ajustada em modelos observacionais",""]
for x in monthly_models:lines.append(f"- {x['controle']} / {x['modelo']}: coef pós={x['coef_post_2005_pp']:.3f} pp, IC95% {x['ci95_inf']:.3f}–{x['ci95_sup']:.3f}, p HAC={x['p_HAC']:.4g}.")
lines+=["",f"## Defasagem anual: {len(lag)} testes, FDR significativos: {summary['n_fdr_sig']}.","",
"Sem inferência causal: controles podem partilhar processos hidrológicos, e o sistema responde a chuvas e vazões de toda a BAP.",
"","## Dados e reprodução", "No mesmo diretório: CSV mensal, anual, testes de pretrend, regressões HAC, lags 0–10, mapas, códigos e dados MERIT D8."]
(R/"RELATORIO_RECEPTOR_E_CONTROLES.md").write_text("\n".join(lines),encoding="utf-8")
print(json.dumps({"n_fdr_sig":summary["n_fdr_sig"],"pretrends":baselines,
"models":monthly_models,"descriptive":descr,"best":summary["melhor_lag_bruto"]},ensure_ascii=False,default=cvt,indent=2)[:11000])
