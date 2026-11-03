#!/usr/bin/env python3
"""Diagnóstico histórico 1985–2025: vazão média, estiagem, Q90 e vazão específica.
ANO = civil. Jul–out conforme janela hidrológica local; requer testes com outras janelas.
Não atribui perdas a pastagens, não mede fontes individuais nem inventa balanço de massa.
"""
from pathlib import Path
import json, numpy as np,pandas as pd,math
from scipy.stats import kendalltau,theilslopes
from statsmodels.stats.multitest import multipletests
from statsmodels.api import OLS,add_constant
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

P=Path("pesquisa_pantanal/cabeceiras")
R=P/"resultados"
A=pd.read_csv(R/"ANA_CABECEIRAS_VAZAO_ANUAL_1985_2025.csv",encoding="utf-8-sig")
D=pd.read_csv(R/"ANA_CABECEIRAS_VAZAO_DIARIA_1985_2025.csv",encoding="utf-8-sig")
M=pd.read_csv(R/"ANA_CABECEIRAS_VAZAO_MENSAL_1985_2025.csv",encoding="utf-8-sig")
meta=json.loads((R/"RELATORIO_PROSPECCAO_ANA.json").read_text(encoding="utf8"))
assert len(A)==8*41 and not meta["erros"]
info={x["codigo"]:x for x in meta["estacoes"]}
stations={
 66071400:("Jauru - Água Suja","#B27843"),
 66072000:("Jauru - Porto Esperidião","#D5A15A"),
 66055000:("Sepotuba - São José","#146F8F"),
 66065000:("Cabaçal - MT-125","#5C9178"),
 66070004:("Paraguai - Cáceres","#6470A4"),
 66090000:("Paraguai - Descalvados","#9A8C74"),
 66120000:("Paraguai - Porto Conceição","#A86E8A")}
A["codigo"]=A.codigo.astype(int)
metrics=[
 ("q_media_m3_s","Vazão média anual (m³/s)"),
 ("q_seca_jul_out_m3_s","Vazão média julho–outubro (m³/s)"),
 ("q90_m3_s","Q90 diário anual (m³/s), vazão excedida em 90% dos dias")]
rows=[]
for code,(name,color) in stations.items():
 data=A[A.codigo==code].copy()
 for field,label in metrics:
  x=data[["ano",field]].dropna()
  if len(x)<15:continue
  years=x.ano.to_numpy(dtype=float);vals=x[field].to_numpy(dtype=float)
  slope,intercept,lo,hi=theilslopes(vals,years,alpha=0.95)
  tau,p=kendalltau(years,vals)
  mod=OLS(vals,add_constant(years-years.mean())).fit(cov_type="HAC",cov_kwds={"maxlags":2})
  coeff=mod.params[1];ci=mod.conf_int()[1]
  rlag=np.corrcoef(vals[:-1],vals[1:])[0,1] if len(vals)>5 else np.nan
  rows.append({"codigo":code,"estacao":name,"metrica":field,"n_anos":len(x),
  "primeiro_ano":int(years.min()),"ultimo_ano":int(years.max()),
  "mediana_m3_s":float(np.median(vals)),"mk_tau":float(tau),"p_kendall_sem_autocorr":float(p),
  "theil_sen_m3_s_por_ano":float(slope),"slope_ci95_inf":float(lo),"slope_ci95_sup":float(hi),
  "ols_hac_slope_m3_s_ano":float(coeff),"ols_hac_p":float(mod.pvalues[1]),
  "ols_hac_ci95_inf":float(ci[0]),"ols_hac_ci95_sup":float(ci[1]),
  "lag1_amostral":float(rlag) if np.isfinite(rlag) else None})
T=pd.DataFrame(rows)
rej,adj,_,_=multipletests(T.ols_hac_p,method="fdr_bh",alpha=.05)
T["p_fdr_21_HAC"]=adj;T["significativo_fdr"]=rej
T.to_csv(R/"TENDENCIAS_ANA_CABECEIRAS_SECA_Q90.csv",index=False,encoding="utf-8-sig")
# Climatological reference periods differ by station; use matching calendar-period n count, no infill.
clim=[]
for code,name in [(c,v[0]) for c,v in stations.items()]:
 subset=A[A.codigo==code]
 for k in ["q_media_m3_s","q_seca_jul_out_m3_s","q90_m3_s"]:
  vals=[]
  for title,(i,j) in [("1985-1999",(1985,1999)),("2000-2010",(2000,2010)),("2011-2025",(2011,2025))]:
   d=subset[(subset.ano>=i)&(subset.ano<=j)][k].dropna()
   vals.append({"codigo":code,"estacao":name,"metrica":k,"periodo":title,
                "n_anos":len(d),"mediana_m3_s":round(float(d.median()),3) if len(d)>=5 else None})
  clim+=vals
pd.DataFrame(clim).to_csv(R/"COMPARACAO_PERIODOS_Q90_E_SECA.csv",index=False,encoding="utf-8-sig")

plt.rcParams.update({"font.family":"DejaVu Sans","axes.spines.top":False,"axes.spines.right":False,
"figure.facecolor":"white","axes.grid":True,"grid.alpha":.16})
fig,ax=plt.subplots(figsize=(11.6,5.5),layout="constrained")
for code in [66071400,66072000,66055000,66065000]:
 name,color=stations[code];dd=A[(A.codigo==code)&A.q_seca_jul_out_m3_s.notna()]
 if len(dd)<10:continue
 ax.plot(dd.ano,dd.q_seca_jul_out_m3_s,lw=1.4,alpha=.4,marker="o",markersize=2.3,color=color)
 ax.plot(dd.ano,dd.q_seca_jul_out_m3_s.rolling(5,min_periods=3).median(),label=name+" (mediana móvel 5 anos)",lw=2.1,color=color)
ax.set_xlabel("Ano");ax.set_ylabel("Vazão média na estiagem, jul–out (m³/s)")
ax.set_title("Cabeceiras do Pantanal | Descarga fluvial na estiagem 1985–2025",loc="left",fontweight="bold",fontsize=14)
ax.legend(frameon=False,fontsize=8,ncol=2)
fig.savefig(R/"FIGURA_CABECEIRAS_VAZAO_NA_SECA.png",dpi=205,bbox_inches="tight");plt.close(fig)

fig,axes=plt.subplots(2,2,figsize=(12,8),layout="constrained")
focus=[66071400,66072000,66055000,66065000]
for ax,code in zip(axes.flat,focus):
 name,color=stations[code]
 v=A[(A.codigo==code)&A.q90_m3_s.notna()]
 ax.plot(v.ano,v.q90_m3_s,color=color,lw=1.7,marker="o",markersize=2.5,alpha=.62)
 if len(v)>=15:
  slope,intercept,_,_=theilslopes(v.q90_m3_s,v.ano)
  ax.plot(v.ano,intercept+slope*v.ano,color="#233B4C",lw=2,ls="--")
  st=T[(T.codigo==code)&(T.metrica=="q90_m3_s")].iloc[0]
  ax.text(.03,.95,f"Theil–Sen {slope:+.2f} m³/s/ano\np FDR(HAC)={st.p_fdr_21_HAC:.3g}",
  transform=ax.transAxes,va="top",fontsize=9,color="#294356")
 ax.set_title(name,loc="left",fontweight="bold",fontsize=11)
 ax.set_ylabel("Q90, m³/s (excedida 90% dos dias)")
 ax.set_xlabel("Ano")
fig.suptitle("Q90: água disponível na maior parte do tempo",fontweight="bold",fontsize=15)
fig.savefig(R/"FIGURA_CABECEIRAS_Q90_4_ESTACOES.png",dpi=205,bbox_inches="tight");plt.close(fig)

# Normalizar tendências na vazão específica, cuja área de drenagem publicada precisa validação.
fig,ax=plt.subplots(figsize=(11,5.7),layout="constrained")
sortedrows=T[T.metrica=="q_seca_jul_out_m3_s"].sort_values("theil_sen_m3_s_por_ano")
labels=sortedrows.estacao.tolist()
y=np.arange(len(labels))
x=sortedrows.theil_sen_m3_s_por_ano.to_numpy()
ax.axvline(0,c="#6E7880",lw=1)
ax.errorbar(x,y,xerr=[x-sortedrows.slope_ci95_inf.to_numpy(),
sortedrows.slope_ci95_sup.to_numpy()-x],fmt="o",capsize=4,color="#266A81",lw=2)
ax.set_yticks(y,labels=labels);ax.invert_yaxis()
ax.set_xlabel("Tendência Theil–Sen de vazão seca (m³/s por ano) ± IC95%")
ax.set_title("Quais estações perdem vazão na estiagem?",loc="left",fontsize=14,fontweight="bold")
fig.savefig(R/"FIGURA_TENDENCIA_ESTIAGEM_IC95.png",dpi=205,bbox_inches="tight");plt.close(fig)
# Compare nested Jauru stations on same years: not literal volume lost; positive upstream-downstream difference can represent lateral inflow.
a=A[A.codigo==66071400][["ano","q_media_m3_s","q_seca_jul_out_m3_s"]].rename(columns={"q_media_m3_s":"Q_agua_suja","q_seca_jul_out_m3_s":"Qseca_agua_suja"})
b=A[A.codigo==66072000][["ano","q_media_m3_s","q_seca_jul_out_m3_s"]].rename(columns={"q_media_m3_s":"Q_porto_esperidiao","q_seca_jul_out_m3_s":"Qseca_porto_esperidiao"})
joined=a.merge(b,on="ano")
joined["Q_incremental_m3_s"]=joined.Q_porto_esperidiao-joined.Q_agua_suja
joined["Qseca_incremental_m3_s"]=joined.Qseca_porto_esperidiao-joined.Qseca_agua_suja
joined["area_incremental_km2_ref"]=4970-1710
joined["Qseca_incremental_especifica_Ls_km2"]=joined.Qseca_incremental_m3_s*1000/(4970-1710)
joined.to_csv(R/"JAURU_GAUGES_PARES_INCREMENTS_EXPLORATORIOS.csv",index=False,encoding="utf-8-sig")
stats={
 "window":"1985-2025","series_ana_estacoes":len(stations),"n_estacao_ano":int(len(A)),
 "n_fdr_hac_significativo":int(T.significativo_fdr.sum()),
 "station_trends_q_seca":[r for r in T[T.metrica=="q_seca_jul_out_m3_s"].to_dict("records")],
 "station_trends_q90":[r for r in T[T.metrica=="q90_m3_s"].to_dict("records")],
 "cautelas":["HidroSerieHistorica pode retornar séries de diferentes níveis de consistência; prioriza consistido e registra nível por dia.",
 "Tendências não foram ajustadas por chuva, irrigação ou mudanças na curva-chave.",
 "Kendall tau sem correção para autocorrelação; inferência exploratória.",
 "Áreas de drenagem da compilação antiga ainda precisam ser validadas com BHO/ANA.",
 "Q90 é vazão observada excedida em 90% dos dias, não baseflow hidrologicamente separado.",
 "Incremento entre dois postos Jauru só faz sentido quando a topologia a montante–jusante e propagação de cheia estiverem certificadas.",
 "Rio Jauru entra no Paraguai A JUSANTE da estação urbana de Cáceres."]}
def json_default(o):
 if isinstance(o,(np.bool_,)):return bool(o)
 if isinstance(o,(np.integer,)):return int(o)
 if isinstance(o,(np.floating,)):return float(o)
 return str(o)
(R/"RESUMO_CABECEIRAS_VAZAO_SECA.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2,default=json_default),encoding="utf8")
lines=["# Água que chega ao Pantanal: diagnóstico da vazão das cabeceiras, 1985–2025","",
"Esta análise usa vazão efetivamente medida pela ANA, **não** área inundada ou água virtual.",
"",
"## Tendências por estação na estiagem (julho–outubro)","",
"| Estação | Anos | Theil–Sen m³/s/ano | IC95% | p ajustado HAC/FDR |",
"|---|---:|---:|---|---:|"]
for row in stats["station_trends_q_seca"]:
 lines.append(f"| {row['estacao']} | {row['n_anos']} | {row['theil_sen_m3_s_por_ano']:+.3f} | [{row['slope_ci95_inf']:+.3f}, {row['slope_ci95_sup']:+.3f}] | {row['p_fdr_21_HAC']:.4g} |")
lines+=["","## Limitações",""]
lines += ["- "+l for l in stats["cautelas"]]
lines+=["","**Conclusão científica atual:** diminuição de vazão observada em parte das estações, mas 'a água sumiu' é incorreto até fechar balanço P–ET–Q–ΔS e validar ações humanas. A descarga específica e Q90, quando controladas por chuva, são passos indispensáveis."]
(R/"RELATORIO_CABECEIRAS_VAZAO_SECA.md").write_text("\n".join(lines),encoding="utf8")
print(json.dumps({"N":len(T),"q_seca":stats["station_trends_q_seca"],"q90":stats["station_trends_q90"]},ensure_ascii=False,default=json_default)[:14000])
