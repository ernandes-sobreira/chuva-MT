# RETIFICAÇÃO CIENTÍFICA — Hidrologia do Pantanal de Cáceres

**Esta página prevalece sobre as interpretações espaciais feitas no piloto da unidade HydroBASINS nível 6.**

## 1. O que estava incorreto

A unidade local HydroBASINS 6060634290 (nível 6, 8.906,9 km²) e sua drenagem acumulada de **35.427,2 km²** foram apresentadas com a denominação simplificada “Cáceres”. Ela **não é o município** de Cáceres, **não é** a planície pantaneira inteira e **não constitui uma delimitação validada** para o exutório da estação ANA 66070004.

O ponto usado inicialmente (-57,681; -16,075) não foi documentado como coordenada da estação hidrométrica. As regressões e mapas daquele piloto permanecem apenas como exploração do recorte antigo. **Não transportar coeficientes, taxas de perda de água ou conclusões causais do piloto para a nova área.**

## 2. Delimitação auditada

- **Exutório:** estação ANA **66070004 — Cáceres (DNPVN)**, rio Paraguai.
- **Coordenada operativa:** -57,6877778; -16,0630556 (posição publicada em trabalho acadêmico da estação, não confirmada em inventário atual ANA). Outra referência publicada: -57,7022222; -16,0758333 (SAD69). Ambas foram verificadas em HydroBASINS e caem na mesma sub-bacia nível 10.
- **HydroBASINS L10:** exutório HYBAS_ID **6100630200**; área acumulada UP_AREA **32.752,7 km²**.
- **Conectividade:** 222 sub-bacias identificadas recursivamente por NEXT_DOWN; soma de SUB_AREA **32.752,8 km²** (desvio interno ~0,0003%).
- **Confronto independente:** estação com **32.774 km²** em publicação hidrológica, desvio de **−0,065%**. Outra publicação usa 32.393 km² (diferença ~1,11%). **Concordância numérica não dispensa verificação da geometria pela ANA/BHO**.
- **Intersecção com biomas IBGE 2025, usando geometria geodésica:** Amazônia 21.025,78 km² (64,4%), Cerrado 10.651,14 km² (32,6%) e Pantanal 959,72 km² (2,9%). Estes percentuais são **composição territorial**, não contribuição de vazão de cada bioma.

## 3. Dois objetivos distintos

**A. Hidrologia da estação de Cáceres:** usar apenas a bacia conectada ao exutório 66070004 para chuva e uso do solo. Isto não inclui necessariamente afluentes que desembocam a jusante da estação.

**B. Perda de água em todo o Pantanal:** usar a delimitação completa da Bacia do Alto Paraguai e distinguir planalto da planície e sub-bacias afluentes. A bacia de Cáceres não substitui esse segundo recorte. Bioma Pantanal não equivale necessariamente à planície geomorfológica.

## 4. Novas análises

A nova série deve reprocessar CHIRPS na bacia a montante, pastagens MapBiomas na mesma bacia, e superfície de água dentro da intersecção do bioma Pantanal com essa bacia. **São 959,72 km² de recorte pantaneiro local, não o Pantanal inteiro**. O retorno da estação (cotas/vazões ANA) não deve ser usado como equivalência de volume perdido na planície.

Mapas, GeoJSON e scripts estão em `pesquisa_pantanal/recorte_cientifico/` e `pesquisa_pantanal/cartografia/`.

**Uso em artigo:** requer validação dos polígonos com a Base Hidrográfica Ottocodificada da ANA, documentação do ponto atual da estação, dados hidrométricos auditados e comparação entre várias sub-bacias. Nenhuma associação observacional é prova de causalidade da pecuária.

## Referências

- ANA/SGB, estação 66070004; artigos: https://files.abrhidro.org.br/Eventos/Trabalhos/4/PAP019973.pdf e https://ocs.ige.unicamp.br/ojs/sbgfa/article/download/2488/2130
- HydroBASINS nível 10: WWF/HydroSHEDS/v1/Basins/hybas_10 (Earth Engine).
- IBGE Biomas 2025: https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/biomas/vetores/2025_Biomas-e-Sistema-Costeiro-Marinho-do-Brasil-1-250000_shp.zip
- MapBiomas Água C5, MapBiomas Cobertura C11, CHIRPS v2.

## 5. Dados reprocessados em 2 de novembro de 2026

A extração sobre o limite **novo** foi executada com sucesso e validada quanto à integridade de 492 meses de água e chuva, de 1985–2025. Os arquivos reprocessados estão em:

- `recorte_cientifico/resultados/SERIE_CORRIGIDA_BACIA_ANA_66070004_1985_2025.csv` — área mensal com água apenas na parte do **bioma Pantanal situada a montante da estação**, precipitação mensal em toda a bacia e pastagem anual na mesma bacia.
- `recorte_cientifico/analise/RELATORIO_REANALISE_BACIA_CORRIGIDA.md` — testes HAC/FDR, sensibilidade e validação fora da amostra.
- `cartografia/MAPA_BACIA_REAL_ESTACAO_CACERES_BIOMAS.png` — mapa com os três biomas e o exutório, distinguindo limites municipais de limites de drenagem.

A porção pantaneira efetivamente analisada mede cerca de **958–960 km²** conforme a simplificação vetorial empregada; não representa toda a planície. Em 1985 e 2025, a superfície anual de água nesse recorte foi aproximadamente 10.977 e 10.990 ha, respectivamente. Não há conclusão de estabilidade ou tendência para toda a série apenas a partir desses extremos.

No teste de **primeiras diferenças anuais** (34 observações com dados hidrométricos suficientes), a associação ajustada de expansão de pastagem com variação da superfície de água não foi significativa (**p HAC = 0,576**). Os coeficientes mensais variaram entre especificações. A chuva e a vazão mantiveram associações com a dinâmica da água, mas nenhuma delas constitui atribuição causal automática.

**Decisão de controle de qualidade:** as figuras e as regressões do piloto HydroBASINS nível 6 permanecem como histórico exploratório, não como evidência final; não devem ser apresentadas sem esta nota de retificação.
