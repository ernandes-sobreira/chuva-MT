#!/usr/bin/env python3
"""Estatistica aplicada SOMENTE ao novo recorte ANA 66070004 verificado.
Resultados exploratórios; espaço de inferência = bacia a montante de Cáceres, não BAP completa.
"""
from pathlib import Path
import json,math
import pandas as pd,numpy as np
from scipy.stats import pearsonr
from statsmodels.formula.api import ols
from statsmodels.stats.multitest import multipletests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

R=Path("pesquisa_pantanal/recorte_cientifico/resultados")
A=Path("pesquisa_pantanal/recorte_cientifico/analise")
A.mkdir(parents=True,exist_ok=True)
qc=json.loads((R/"STATUS_EXTRAÇÃO_RECORTE_VALIDADO.json").read_text(encoding="utf-8"))
if qc.get("status")!="concluido" or qc.get("total_meses")!=492:raise SystemExit("Nao produzir estatistica sem 492 meses validados")
w=pd.read_csv(R/"SERIE_CORRIGIDA_BACIA_ANA_66070004_1985_2025.csv",encoding="utf-8-sig")
P=Path("pesquisa_pantanal/hidrologia/resultados")
stage=pd.read_csv(P/"cota_mensal_ana_caceres_1985_2025.csv",encoding="utf-8-sig")
flow=pd.read_csv(P/"vazao_mensal_ana_caceres_1985_2025.csv",encoding="utf-8-sig")
d=w.merge(stage[["ano","mes","cota_media_m"]],on=["ano","mes"],validate="one_to_one")
d=d.merge(flow[["ano","mes","vazao_media_m3_s"]],on=["ano","mes"],validate="one_to_one")
d=d.sort_values(["ano","mes"]).reset_index(drop=True)
assert len(d)==492 and not d.duplicated(subset=["ano","mes"]).any()
d["t"]=np.arange(len(d))
d["water_kha"]=d.agua_superficial_bioma_pantanal_montante_ha/1e3
d["rain_mm"]=d.chuva_na_bacia_mm
d["pasture_mha"]=d.pastagem_plantada_bacia_ha/1e6
d["stage_m"]=d.cota_media_m
d["flow_cms"]=d.vazao_media_m3_s
for col in ["rain_mm","stage_m","flow_cms"]:
 for lag in range(1,7):
  d[f"{col}_lag{lag}"]=d[col].shift(lag)
d.to_csv(A/"serie_integrada_corrigida_1985_2025.csv",index=False,encoding="utf-8-sig")
def nice(v):return None if v is None or not np.isfinite(v) else float(v)
def fit_beta(df,y,x,extra="C(mes) + t"):
 use=df[[y,x,"mes","t"]].dropna().copy()
 if len(use)<100:return None
 for z,n in [(y,"Y"),(x,"X")]:use[n]=(use[z]-use[z].mean())/use[z].std()
 m=ols("Y ~ X + "+extra,data=use).fit(cov_type="HAC",cov_kwds={"maxlags":12})
 lo,hi=m.conf_int().loc["X"]
 return {"n":len(use),"beta":nice(m.params["X"]),"ic95_inf":nice(lo),"ic95_sup":nice(hi),
 "p":nice(m.pvalues["X"]),"r2":nice(m.rsquared)}
relations=[("Chuva → cota","stage_m","rain_mm"),("Chuva → vazão","flow_cms","rain_mm"),
           ("Cota → água","water_kha","stage_m"),("Vazão → água","water_kha","flow_cms"),
           ("Chuva → água","water_kha","rain_mm")]
lags=[]
for name,y,x in relations:
 rows=[]
 for lag in range(7):
  label=x if lag==0 else f"{x}_lag{lag}"
  r=fit_beta(d,y,label)
  if r:rows.append({"relacao":name,"lag":lag,**r})
 if rows:
  mask,padj,_,_=multipletests([q["p"] for q in rows],method="fdr_bh")
  for a,b,c in zip(rows,padj,mask):a.update(p_fdr=nice(b),fdr_significativo=bool(c))
  lags.extend(rows)
pd.DataFrame(lags).to_csv(A/"defasagens_corrigidas_HAC_FDR.csv",index=False,encoding="utf-8-sig")
# Testar pastagem com e sem tendência temporal e com estágio/vazão.
d["rain1"]=d.rain_mm.shift(1);d["rain2"]=d.rain_mm.shift(2);d["rain3"]=d.rain_mm.shift(3)
d["flow1"]=d.flow_cms.shift(1)
d["stage1"]=d.stage_m.shift(1)
base="water_kha ~ C(mes) + rain_mm + rain1 + rain2 + rain3 + pasture_mha"
formulas={
 "Chuva e sazonalidade":base,
 "Chuva + tendência":base+" + t",
 "Chuva + tendência + cota":base+" + t + stage_m + stage1",
 "Chuva + tendência + vazão":base+" + t + flow_cms + flow1"}
est=[]
for name,formula in formulas.items():
 vars_req=["water_kha","rain_mm","rain1","rain2","rain3","pasture_mha"]
 if "cota" in name:vars_req+=["stage_m","stage1"]
 if "vazão" in name:vars_req+=["flow_cms","flow1"]
 use=d.dropna(subset=vars_req)
 m=ols(formula,data=use).fit(cov_type="HAC",cov_kwds={"maxlags":12})
 ci=m.conf_int().loc["pasture_mha"]
 est.append({"modelo":name,"n_meses":len(use),"beta_kha_por_mha":nice(m.params["pasture_mha"]),
 "ic95_inf":nice(ci.iloc[0]),"ic95_sup":nice(ci.iloc[1]),
 "p_HAC":nice(m.pvalues["pasture_mha"]),"R2_adjusted":nice(m.rsquared_adj)})
pd.DataFrame(est).to_csv(A/"sensibilidade_pastagens_bacia_corrigida.csv",index=False,encoding="utf-8-sig")
# Primeiras diferenças ANUAIS -> evita tratar 12 meses com mesma pastagem como independentes.
an=d.groupby("ano",as_index=False).agg(water_kha=("water_kha","mean"),rain_mm=("rain_mm","sum"),
flow_cms=("flow_cms","mean"),n_flow=("flow_cms","count"),stage_m=("stage_m","mean"),n_stage=("stage_m","count"),
pasture_mha=("pasture_mha","first"))
an.loc[an.n_flow<10,"flow_cms"]=np.nan
an.loc[an.n_stage<10,"stage_m"]=np.nan
for col in ["water_kha","rain_mm","flow_cms","stage_m","pasture_mha"]:
 an["diff_"+col]=an[col].diff()
annual=an.dropna(subset=["diff_water_kha","diff_rain_mm","diff_flow_cms","diff_pasture_mha"])
m=ols("diff_water_kha ~ diff_rain_mm + diff_flow_cms + diff_pasture_mha",data=annual).fit(cov_type="HAC",cov_kwds={"maxlags":2})
ci=m.conf_int().loc["diff_pasture_mha"]
fchange={"n_anos":len(annual),"beta_pastagem":nice(m.params["diff_pasture_mha"]),"p_HAC":nice(m.pvalues["diff_pasture_mha"]),
"ic95":list(map(nice,ci))}
an.to_csv(A/"serie_anual_recorte_corrigido.csv",index=False,encoding="utf-8-sig")
# Previsão fora amostra temporal, mesma amostra para comparar chuva, vazão, pastagem
valid=d.dropna(subset=["water_kha","rain_mm","rain1","rain2","rain3","flow_cms","flow1","pasture_mha"])
forms={
 "chuva":"water_kha ~ C(mes) + t + rain_mm + rain1 + rain2 + rain3",
 "chuva_vazao":"water_kha ~ C(mes) + t + rain_mm + rain1 + rain2 + rain3 + flow_cms + flow1",
 "chuva_vazao_pastagem":"water_kha ~ C(mes) + t + rain_mm + rain1 + rain2 + rain3 + flow_cms + flow1 + pasture_mha"}
train=valid[valid.ano<=2014];test=valid[valid.ano>=2015]
forecast=[]
for label,form in forms.items():
 mod=ols(form,data=train).fit()
 pred=mod.predict(test)
 forecast.append({"modelo":label,"n_treino":len(train),"n_teste":len(test),
   "RMSE_kha":float(np.sqrt(np.mean((pred-test.water_kha)**2))),"MAE_kha":float(np.mean(np.abs(pred-test.water_kha)))})
pd.DataFrame(forecast).to_csv(A/"validacao_temporal_recorte_corrigido.csv",index=False,encoding="utf-8-sig")
corr_pasture_time=float(np.corrcoef(d["pasture_mha"],d["t"])[0,1])
summary={"recorte":"ANA 66070004, HydroBASINS L10, bioma Pantanal a montante","meses":len(d),
"cota_meses_validos":int(d.stage_m.notna().sum()),"vazao_meses_validos":int(d.flow_cms.notna().sum()),
"area_bacia_km2":qc["area_bacia_km2"],"area_pantanal_intersecao_km2":qc["area_pantanal_intersecao_km2"],
"pastagem_1985_ha":float(d.loc[d.ano==1985,"pastagem_plantada_bacia_ha"].iloc[0]),
"pastagem_2025_ha":float(d.loc[d.ano==2025,"pastagem_plantada_bacia_ha"].iloc[0]),
"agua_anual_1985_ha":float(d.loc[d.ano==1985,"agua_anual_bioma_pantanal_montante_ha"].iloc[0]),
"agua_anual_2025_ha":float(d.loc[d.ano==2025,"agua_anual_bioma_pantanal_montante_ha"].iloc[0]),
"corr_pastagem_tempo":corr_pasture_time,
"defasagens":lags,"pastagem_modelos":est,"primeiras_diferencas":fchange,"validacao_temporal":forecast,
"avisos":["Recorte novo e menor; não reutilizar resultados de mapas do HydroBASINS L6.",
"Pastagem é medida em 41 anos, replicada apenas para o alinhamento mensal; os 492 meses não são 492 estimativas independentes de área de pastagem.",
"Resultados HAC/FDR são associações, não impactos causais.",
"O bioma Pantanal a montante não representa a planície pantaneira a jusante.",
"Área inundada não significa volume de água perdida."]}
(A/"RESUMO_NOVO_RECORTE.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
plt.rcParams.update({"font.family":"DejaVu Sans","figure.facecolor":"white",
"axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,"grid.alpha":.15})
colors=["#318268","#3C83AC","#B69257","#646B91"]
fig,axs=plt.subplots(2,2,figsize=(13,9),layout="constrained")
series=[("rain_mm","Chuva nas cabeceiras (mm/ano)"),
("stage_m","Cota média Cáceres (m)"),
("pasture_mha","Pastagem plantada na bacia (milhão ha)"),
("water_kha","Água média mensal no recorte pantaneiro (mil ha)")]
for ax,(c,lab),color in zip(axs.flat,series,colors):
 aa=an.copy()
 if c=="rain_mm":y=aa[c]
 else:y=aa[c]
 ax.plot(aa.ano,y,marker="o",ms=2.8,lw=2.2,color=color)
 ax.set_ylabel(lab,fontsize=10);ax.set_xlim(1985,2025)
 ax.set_title(lab,loc="left",fontweight="bold",fontsize=12)
fig.suptitle("Bacia da estação ANA 66070004 | Séries no recorte corrigido (1985–2025)",fontsize=16,fontweight="bold")
fig.text(.05,-.008,"Água na intersecção do bioma Pantanal com bacia a montante; pastagem e chuva em toda a bacia. MapBiomas/CHIRPS/ANA.",fontsize=8,color="#53646A")
fig.savefig(A/"FIGURA_CORRIGIDA_01_SERIES.png",dpi=200,bbox_inches="tight");plt.close(fig)
fig,ax=plt.subplots(figsize=(11,5),layout="constrained")
v=pd.DataFrame(est)
y=np.arange(len(v))
ax.errorbar(v.beta_kha_por_mha,y,
  xerr=[v.beta_kha_por_mha-v.ic95_inf,v.ic95_sup-v.beta_kha_por_mha],
  fmt="o",capsize=4,color="#286D8C",lw=2,ms=7)
ax.axvline(0,color="#555555",lw=.9)
ax.set_yticks(y,labels=v.modelo);ax.invert_yaxis()
ax.set_xlabel("Coeficiente de pastagem ± IC 95% HAC (mil ha de água por milhão ha de pastagem)")
ax.set_title("Sensibilidade da associação, sem inferência causal",loc="left",fontweight="bold",fontsize=15)
fig.savefig(A/"FIGURA_CORRIGIDA_02_SENSIBILIDADE.png",dpi=200,bbox_inches="tight");plt.close(fig)
fig,ax=plt.subplots(figsize=(11,5),layout="constrained")
rr=pd.DataFrame([r for r in lags if r["relacao"] in ["Chuva → vazão","Vazão → água","Chuva → água"]])
for name,grp in rr.groupby("relacao"):
 ax.plot(grp.lag,grp.beta,marker="o",lw=2,label=name)
ax.axhline(0,lw=.8,color="#777")
ax.set_xticks(range(7));ax.set_xlabel("Defasagem (meses)");ax.set_ylabel("Coeficiente padronizado")
ax.set_title("Defasagens hidrológicas no recorte corrigido",loc="left",fontsize=15,fontweight="bold")
ax.legend(frameon=False)
fig.savefig(A/"FIGURA_CORRIGIDA_03_DEFASAGENS.png",dpi=200,bbox_inches="tight");plt.close(fig)
report=["# Resultado corrigido: bacia contribuinte de Cáceres — ANA 66070004","",
 f"Área HydroBASINS L10 a montante: {qc['area_bacia_km2']} km². Pantanal dentro da bacia: {qc['area_pantanal_intersecao_km2']} km².",
 f"Meses MapBiomas/CHIRPS: {len(d)}; meses cotas ANA: {summary['cota_meses_validos']}; meses vazão: {summary['vazao_meses_validos']}.","",
 "## Pastagem na bacia e água superficial no bioma Pantanal a montante",
 f"Pastagem: {summary['pastagem_1985_ha']:.1f} ha (1985) a {summary['pastagem_2025_ha']:.1f} ha (2025).",
 f"Água anual (apenas intersecção Pantanal a montante): {summary['agua_anual_1985_ha']:.1f} ha a {summary['agua_anual_2025_ha']:.1f} ha.",
 f"Pastagem x ano: r = {corr_pasture_time:.3f}.",
 "", "## Defasagens exploratórias (HAC 12 meses, efeitos de mês e tendência, FDR BH)", ""]
for name,y,x in relations:
 rr=[a for a in lags if a["relacao"]==name]
 if rr:
  best=max(rr,key=lambda z:abs(z["beta"]))
  report.append(f"- {name}: maior |β| em {best['lag']} meses, β={best['beta']:.3f}, IC95%=[{best['ic95_inf']:.3f}, {best['ic95_sup']:.3f}], p_FDR={best['p_fdr']:.6g} (n={best['n']}).")
report+=["","## Pastagens: consistência entre especificações",""]
for i in est:report.append(f"- {i['modelo']}: β={i['beta_kha_por_mha']:.3f}, IC95%=[{i['ic95_inf']:.3f}, {i['ic95_sup']:.3f}], p_HAC={i['p_HAC']:.5g}.")
report+=["",f"Primeiras diferenças anuais, n={fchange['n_anos']}: β={fchange['beta_pastagem']:.3f}; IC95%={fchange['ic95']}; p={fchange['p_HAC']:.5g}.","",
"## Validação 1985–2014 contra 2015–2025",""]
for x in forecast:report.append(f"- {x['modelo']}: RMSE {x['RMSE_kha']:.3f} mil ha (mesma amostra, n treino={x['n_treino']}, teste={x['n_teste']}).")
report+=["","**AVISO:** toda esta análise é observacional, espacialmente restrita ao pequeno setor do bioma Pantanal **a montante** da estação. Não atribuir causalidade nem extrapolar para todo o Pantanal.","",
"Fontes oficiais e scripts documentados no ramo pesquisa-pantanal-extracao-2026."]
(A/"RELATORIO_REANALISE_BACIA_CORRIGIDA.md").write_text("\n".join(report),encoding="utf-8")
print(json.dumps({k:summary[k] for k in ["meses","cota_meses_validos","vazao_meses_validos","area_bacia_km2","pastagem_1985_ha","pastagem_2025_ha","agua_anual_1985_ha","agua_anual_2025_ha","primeiras_diferencas","validacao_temporal"]},ensure_ascii=False,indent=2))
