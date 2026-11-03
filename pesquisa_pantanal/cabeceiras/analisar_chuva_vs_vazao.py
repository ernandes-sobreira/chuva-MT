#!/usr/bin/env python3
"""Diagnóstico cabeceiras: teste de se a redução de vazão acompanha a chuva.
Risco de confusão por temperatura/PET, captações, barramentos, usos do solo e
mudanças na curva-chave. Sem alegar causa por pastagens ou nascentes secas.
"""
from pathlib import Path
import json,numpy as np,pandas as pd
from scipy.stats import kendalltau,theilslopes
from statsmodels.api import OLS,add_constant
from statsmodels.stats.multitest import multipletests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R=Path("pesquisa_pantanal/cabeceiras/resultados")
Q=pd.read_csv(R/"ANA_CABECEIRAS_VAZAO_ANUAL_1985_2025.csv",encoding="utf-8-sig")
P=pd.read_csv(R/"PRECIPITACAO_CABECEIRAS_CHIRPS_1985_2025.csv",encoding="utf-8-sig")
I=json.loads((R/"AUDITORIA_BACIAS_CHUVA_ANA.json").read_text(encoding="utf8"))
assert all(x["status"]=="concluido" for x in I["stations"]),"Um exutório não foi validado"
Q["codigo"]=Q.codigo.astype(int);P["codigo"]=P.codigo.astype(int)
merged=Q.merge(P[["codigo","ano","chuva_ano_mm","chuva_recarga_out_jun_mm","area_ana_km2","area_hydro_km2"]],
 on=["codigo","ano"],how="inner",validate="one_to_one").sort_values(["codigo","ano"])
merged["p_wet_minus1"]=merged.groupby("codigo").chuva_recarga_out_jun_mm.shift(1)
merged["p_year_minus1"]=merged.groupby("codigo").chuva_ano_mm.shift(1)
merged["qseco_espec_L_s_km2"]=merged.q_seca_jul_out_m3_s*1000/merged.area_ana_km2
merged["ano_centro"]=merged.ano-2005
merged.to_csv(R/"BASE_CHUVA_VAZAO_CABECEIRAS_1985_2025.csv",encoding="utf-8-sig",index=False)
out=[]
for code,df in merged.groupby("codigo"):
 gauge=df.iloc[0]["estacao"]
 # consistent enough annual q and at least one wet-season antecedent year.
 d=df.dropna(subset=["q_seca_jul_out_m3_s","chuva_recarga_out_jun_mm","p_wet_minus1"])
 if len(d)<20:continue
 x=add_constant(pd.DataFrame({"p_wet":(d.chuva_recarga_out_jun_mm-1500)/100,
 "p_prev":(d.p_wet_minus1-1500)/100,
 "year":d.ano_centro}),has_constant="add")
 fit=OLS(d.qseco_espec_L_s_km2,x).fit(cov_type="HAC",cov_kwds={"maxlags":2})
 ci=fit.conf_int().loc["year"]
 mm=merged[merged.codigo==code]
 py=mm.dropna(subset=["chuva_recarga_out_jun_mm"])
 slope,intercept,lo,hi=theilslopes(py.chuva_recarga_out_jun_mm,py.ano)
 tau,p=kendalltau(py.ano,py.chuva_recarga_out_jun_mm)
 # More conservative: flag high serial autocorrelation and distribution changes
 out.append({"codigo":int(code),"estacao":gauge,"n_qdry_anos":len(d),
 "periodo":[int(d.ano.min()),int(d.ano.max())],
 "p_chuva_recarga_slope_mm_ano":float(slope),
 "p_chuva_kendall_p":float(p),
 "qseco_especifica_trend_control_chuva_L_s_km2_ano":float(fit.params["year"]),
 "ic95_inf":float(ci[0]),"ic95_sup":float(ci[1]),
 "p_hac_trend":float(fit.pvalues["year"]),
 "coef_Q_por_100mm":float(fit.params["p_wet"]),
 "coef_Q_por_100mm_ano_anterior":float(fit.params["p_prev"]),
 "n_rain_years":len(py),"r2_ajustado":float(fit.rsquared_adj),
 "aviso":"Trend residual de Q seca ajustado apenas por chuva, NAO atribuição causal a pastagens."})
assert len(out)>=3, "Menos de 3 estações com cobertura para ajuste"
rej,adj,_,_=multipletests([x["p_hac_trend"] for x in out],alpha=.05,method="fdr_bh")
for item,p,r in zip(out,adj,rej):
 item["p_fdr_hac"]=float(p);item["sig_fdr"]=bool(r)
report={"metodo":"Q seca específica Jul–Out ~ chuva Out(y-1)–Jun(y) + chuva úmida ano anterior + tendência linear, HAC(2).",
        "Fonte_P":"CHIRPS v2, bacias HydroBASINS L10 conferidas com área de drenagem ANA","Fonte_Q":"ANA HidroSerieHistorica nível 2 preferido, 1 quando indisponível",
        "estacoes":out,
        "interpretacao":"Um coeficiente de tendência residual não identifica destino da água nem causa. Temperatura, ET, retiradas, barramentos, armazenamento subterrâneo e curvas-chave não entraram.",
        "proximos_controles":["Evapotranspiração real (TerraClimate/GLEAM)","mudanças de pastagens na bacia","dados de captação/outorgas","reservatórios e PCHs","baseflow separação do hidrograma diário","comparação bacias controles e mudanças de curva-chave"]}
(R/"RELATORIO_CHUVA_AJUSTADA_CABECEIRAS.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
pd.DataFrame(out).to_csv(R/"TESTE_VAZAO_SECA_AJUSTADA_CHUVA.csv",encoding="utf-8-sig",index=False)

plt.rcParams.update({"font.family":"DejaVu Sans","figure.facecolor":"white","axes.spines.top":False,"axes.spines.right":False,
 "axes.grid":True,"grid.alpha":.13})
fig,axs=plt.subplots(3,1,figsize=(12.2,9),layout="constrained")
palette={66055000:"#227D9C",66065000:"#59967F",66071400:"#AA7A42",66072000:"#CF9B5D",66070004:"#6472A2"}
for c,col in palette.items():
 dat=merged[(merged.codigo==c)&merged.qseco_espec_L_s_km2.notna()]
 datr=merged[merged.codigo==c]
 axs[0].plot(datr.ano,datr.chuva_recarga_out_jun_mm,lw=1.5,color=col,alpha=.83,label=datr.estacao.iloc[0])
 axs[1].plot(dat.ano,dat.qseco_espec_L_s_km2,lw=1.7,marker="o",ms=2.2,color=col,alpha=.85)
axs[0].set_ylabel("Chuva úmida antecedente (mm)")
axs[1].set_ylabel("Vazão seca específica (L/s/km²)")
axs[0].legend(frameon=False,ncol=2,fontsize=9)
fig.suptitle("Cabeceiras do Pantanal: chuva e a água efetivamente descarregada nos rios",fontsize=16,fontweight="bold")
# rainfall vs q specific scatter for core Sepotuba, point color mapped by time without colorbar
code=66055000
sep=merged[(merged.codigo==code)&merged.qseco_espec_L_s_km2.notna()]
axs[2].scatter(sep.chuva_recarga_out_jun_mm,sep.qseco_espec_L_s_km2,
 c=sep.ano,cmap="viridis",edgecolors="white",linewidths=.5,s=45)
axs[2].set_xlabel("Chuva da estação úmida anterior à seca (mm), bacia Sepotuba")
axs[2].set_ylabel("Q seca específica (L/s/km²)")
axs[2].set_title("Sepotuba: comparar vazão sob diferentes quantidades de chuva",loc="left",fontweight="bold")
axs[1].set_xlabel("Ano")
fig.savefig(R/"FIGURA_CHUVA_E_VAZAO_SECA_CABECEIRAS.png",dpi=190,bbox_inches="tight")
plt.close(fig)
# Summary chart after controls - per station residual time trend with robust HAC CI
fig,ax=plt.subplots(figsize=(10.7,5.0),layout="constrained")
y=np.arange(len(out))
val=np.array([o["qseco_especifica_trend_control_chuva_L_s_km2_ano"] for o in out])
lower=np.array([o["ic95_inf"] for o in out]);upper=np.array([o["ic95_sup"] for o in out])
ax.axvline(0,c="#69757C",lw=1)
ax.errorbar(val,y,xerr=[val-lower,upper-val],fmt="o",capsize=4,color="#2B7594",lw=2)
ax.set_yticks(y,labels=[o["estacao"] for o in out]);ax.invert_yaxis()
ax.set_xlabel("Mudança anual de vazão seca específica após controle da chuva (L/s/km²/ano)")
ax.set_title("Sinal hidrológico após controlar chuva | Ainda NÃO é efeito de pastagens",loc="left",fontweight="bold")
fig.savefig(R/"FIGURA_RESIDUAL_VAZAO_SECA_CONTROLE_CHUVA.png",dpi=190,bbox_inches="tight");plt.close(fig)
print(json.dumps(out,ensure_ascii=False,indent=2)[:13000])
