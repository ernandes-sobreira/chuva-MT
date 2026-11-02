# Cáceres — resultados hidrológicos científicos (1985–2025)

Fonte: ANA, MapBiomas C5, MapBiomas C11, CHIRPS v2, HydroBASINS. Reprodução e data no GitHub.

Meses: 492, cota válida: 471, vazão válida: 479.
Correlação bruta cota–vazão: r=0.93841.

## Defasagens pré-definidas (0–6 meses), com mês do ano, tendência linear, HAC(12) e FDR BH

- Chuva montante → cota na estação: maior |β| em lag 1 meses; β=0.484985; IC95%=[0.398577,0.571392]; p_FDR=0.0; n=470.
- Cota em Cáceres → água local: maior |β| em lag 0 meses; β=0.602214; IC95%=[0.370826,0.833601]; p_FDR=0.0; n=471.
- Vazão em Cáceres → água local: maior |β| em lag 0 meses; β=0.574322; IC95%=[0.364117,0.784528]; p_FDR=0.0; n=479.
- Chuva montante → água local: maior |β| em lag 1 meses; β=0.352689; IC95%=[0.196099,0.509279]; p_FDR=7e-05; n=491.

**Não escolher apenas o maior lag para inferência causal.** Os 7 testes por família são exploratórios, mesmo após FDR.

## Reconstrução fora do treino (1985–2014 → 2015–2025)

- Chuva+estação+tempo: RMSE=2.979 mil ha; n treino=357, n teste=132; p_HAC pastagem=None.
- Chuva+cota+estação+tempo: RMSE=3.036 mil ha; n treino=333, n teste=132; p_HAC pastagem=None.
- Chuva+vazão+estação+tempo: RMSE=2.633 mil ha; n treino=337, n teste=132; p_HAC pastagem=None.
- Chuva+cota+pastagem+tempo: RMSE=2.444 mil ha; n treino=333, n teste=132; p_HAC pastagem=0.001751.

## Limitações

- Ausencia de meses ANA nao preenchida\n- Cota e vazao oriundas de serie bruta com possiveis mudancas de secao/curva-chave\n- Area de agua nao representa volume de inundacao\n- Chuva montante CHIRPS, nao redes pluviometricas locais\n- Pastagem e tendencia temporal colineares, coeficiente nao causal\n- Contemporaneidade cota/agua no mesmo mes nao estabelece direcao causal\n- MapBiomas processado a 120m em pesquisa piloto, nao resolucao nativa 30m

**Não existe estimativa confiável de causalidade pecuária → perda de água nesta análise.**