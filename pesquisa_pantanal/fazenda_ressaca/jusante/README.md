# Piloto espacial — entorno da Fazenda Ressaca, Cáceres (MT)

**Situação em 02/11/2026: extração e testes concluídos, inferência causal NÃO demonstrada.**

Este estudo não representa os limites legais da Fazenda Ressaca. A tentativa de obter as quatro parcelas recentes no espelho SIGEF não retornou os perímetros. Todos os polígonos são células de amostragem espacial de 2 km.

## Onde e o que foi comparado

- **A (fonte de transformação):** 9 células contíguas, ~3.600 ha, pastagem plantada passou de ~159 ha em 1985 para ~1.686 ha em 2025. Transformação principal até 2005.
- **B (receptor provável):** C03_02, C03_03, C03_04, ~1.200 ha, atravessados pelos traçados D8 de 25 amostras da célula de maior conversão. Isso indica conectividade provável **no modelo**, não conexão superficial comprovada em campo.
- **C (controle primário):** C03_09, C03_10, C03_11, ~1.200 ha, selecionadas pela superfície de água basal semelhante e ausência desses trajetos.
- **D (controle de sensibilidade):** C04_08, C04_09, C04_10, ~1.200 ha.

Todos os grupos têm 492 meses de água e chuva mapeados com MapBiomas Água C5 e CHIRPS, e 41 anos de pastagem MapBiomas C11; o MERIT Hydro oferece direção de fluxo D8 e altura sobre drenagem (HAND).

## O que os dados realmente mostraram

- O comportamento mensal de água de B e C foi correlacionado antes da grande conversão (r=0,738 entre 1985–1994). A diferença de tendência na fase prévia não foi estatisticamente detectável (p HAC=0,477); ausência de significância **não prova equivalência**.
- A média mensal de água do receptor caiu de 189,8 ha (1985–1994) para 179,9 ha (2005–2025); o controle C caiu de 176,3 para 173,2 ha.
- Nos modelos exploratórios com sazonalidade, chuva e tendência, a variação pós-2005 **não foi significativa** para o controle norte (p HAC=0,327); com D, também não (p=0,993).
- 44 testes de defasagem (0–10 anos, dois desfechos, dois controles). Apenas uma associação no **mesmo ano** da mudança de pastagem foi significativa após FDR com C (p ajustado=0,027); não se repetiu com D. **Nenhum atraso de 1–10 anos foi robusto.**
- Frequência mensal de água por pixel: B passou de **15,808%** (1985–1994) para **14,623%** (2015–2025), diferença de **−1,186 ponto percentual**. C: de 14,681% para 13,871% (−0,810 pp). D: de 15,504% para 12,529% (−2,975 pp). As diferenças variam conforme o controle.
- O mapa por pixel apresenta faixas de aumento e diminuição próximas aos meandros do canal. Isso é compatível com mudanças espaciais na detecção da água, inclusive deslocamento de canais ou variação do pulso; **não mede volume perdido nem demonstra que a pastagem provocou as mudanças.**

## Figuras

- [Mapa A–D em 1985 e 2025](MAPA_PILOTO_JUSANTE_E_CONTROLES.png)
- [Frequência de água por pixel: diferença 2015–2025 menos 1985–1994](MAPA_DELTA_FREQUENCIA_AGUA_PIXELS_1985_2025.png)
- [Séries de pastagem e água de B/C/D](FIGURA_SERIES_RECEPTOR_CONTROLES.png)
- [Diferenças entre B e controles](FIGURA_DIFERENCA_AGUA_RECEPTORES.png)
- [Lags de 0 a 10 anos](FIGURA_LAGS_RECEPTOR_CONTROLE.png)

## Dados, verificações e códigos

- [MapBiomas/CHIRPS, 492 meses por grupo](GRUPOS_PILOTO_MENSAL_1985_2025.csv)
- [MapBiomas anual, 41 anos por grupo](GRUPOS_PILOTO_ANUAL_1985_2025.csv)
- [Cálculo integrado B–C/D](SERIE_INTEGRADA_JUSANTE_CONTROLES.csv)
- [Pré-tendências 1985–1994](PARALELISMO_PRE_1985_1994.csv)
- [Lags e incertezas](LAGS_RECEPTOR_VS_CONTROLE_0_10_ANOS.csv)
- [Auditoria MERIT Hydro](DIAGNOSTICO_CONECTIVIDADE_MERIT.json)
- [Auditoria de frequência de água por pixel](STATUS_HIDROPERIODO_PIXELS.json)
- [Polígonos de amostragem](POLIGONOS_PILOTO_RECEPTOR_CONTROLES.geojson)

Scripts de extração no diretório superior da [pesquisa Ressaca](../) e resultados históricos no ramo `pesquisa-pantanal-extracao-2026` do repositório Chuva-MT.

## Limitações que devem constar em artigo

1. **MERIT Hydro D8 tem uma única direção por pixel (~90 m), enquanto o Pantanal possui bifurcações e remansos.** Trajeto D8 não comprova conexão hidráulica de A para B e exige verificação contra a rede ANA/BHO e imagens.
2. **Controles não são contrafactuais comprovados.** C e D têm água inicial semelhante, mas posições e HAND diferentes; podem responder de modo distinto a processos regionais.
3. **A classificação da água não é volume, profundidade ou fluxo.** Comparar frequência de pixels não é balanço hídrico.
4. **Dados de 30 m têm autocorrelação espacial.** Não testar milhares de pixels como réplicas independentes.
5. **Área da fazenda não verificada.** Não atribuir a proprietários alteração de uso do solo fora de seus perímetros oficiais.
6. **Há apenas uma região estudada.** Recomenda-se replicar com regiões de cabeceira e múltiplas regiões de controle e observar também vazões, solos e barramentos.

**Conclusão do piloto:** foi possível construir e rodar o fluxo de seleção espacial, séries mensais, pré-tendências, controles e lags. Não houve evidência consistente de perda de água causada por expansão da pastagem a jusante, nem lag plurianual robusto.
