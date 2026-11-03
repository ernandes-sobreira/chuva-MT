# Cabeceiras do Pantanal — quanto de água está deixando de chegar aos rios?

**Piloto científico reproduzível (02/11/2026).** Objetivo: medir a vazão que passa por estações de cabeceiras, em vez de inferir volume perdido a partir da superfície de água do Pantanal.

## Conjunto de dados

- **ANA HidroSerieHistorica**, 1985–2025, seleção de `MediaDiaria=1`. Prioridade a `NivelConsistencia=2` (consistido), usando nível 1 onde 2 não estiver disponível, com identificador por dia em CSV. Excluem-se dias marcados como estimados/duvidosos; lacunas preservadas.
- **ANA HidroInventario** para coordenadas e áreas contribuintes: Jauru Água Suja (2.860 km²), Porto Esperidião (5.660 km²); Sepotuba São José (8.090 km²); Cabaçal MT-125 (3.620 km²); Paraguai Cáceres (32.400 km²).
- **HydroBASINS L10**, área contribuinte recalculada por conectividade `NEXT_DOWN`. Divergências relativas entre área da ANA e HydroBASINS: aproximadamente 0,6% a 1,8% nos cinco exutórios testados.
- **CHIRPS v2**, 41 anos de chuva recortada às cinco bacias, total anual e período úmido de outubro anterior a junho atual, imediatamente antes da estiagem julho–outubro.

## Resultados preliminares

Tendências de vazão seca (Theil–Sen, m³/s/ano, sem controle da chuva):

- Sepotuba/São José: **−1,57**; 33 anos válidos.
- Jauru/Água Suja: **−0,47**; 30 anos.
- Jauru/Porto Esperidião: **−0,42**; 34 anos.
- Cabaçal/MT-125: **−0,29**; 32 anos.
- Paraguai/Cáceres: **−3,33**; 37 anos.

Comparações descritivas, considerando exclusivamente os anos válidos de vazão seca:

- **Sepotuba**, mediana em 1995–2005: 156,4 m³/s (10 anos); em 2015–2025: 129,4 m³/s (11 anos), **−17,3%**. A mediana da chuva úmida antecedente nas mesmas amostras foi de 1.572 para 1.703 mm, **+8,3%**. Isso NÃO significa que evapotranspiração ou pastagens causaram a mudança.
- **Cáceres**, mediana de vazão seca: 284,6 m³/s (8 anos em 1995–2005) para 224,1 m³/s (11 anos em 2015–2025), **−21,3%**. A mediana da chuva úmida antecedente variou 1.523 para 1.549 mm, **+1,7%**. Lacunas no primeiro período exigem cautela.

Ajuste exploratório da vazão seca específica (`L s⁻¹ km⁻²`) por chuva úmida atual, chuva do ano antecedente e tempo, com erros HAC(2), apresentou tendência residual negativa nas cinco estações. **Esse resíduo não é a “água perdida pela pecuária”**: permanecem ET, temperatura, retirada de água, uso do solo, armazenamento subterrâneo, obras hidráulicas e mudanças de curva-chave.

## Material

- [Figura — vazão na estiagem](resultados/FIGURA_CABECEIRAS_VAZAO_NA_SECA.png)
- [Figura — Q90, quatro estações](resultados/FIGURA_CABECEIRAS_Q90_4_ESTACOES.png)
- [Figura — chuva nas bacias versus vazão seca específica](resultados/FIGURA_CHUVA_E_VAZAO_SECA_CABECEIRAS.png)
- [Figura — tendência residual após ajuste por chuva](resultados/FIGURA_RESIDUAL_VAZAO_SECA_CONTROLE_CHUVA.png)
- [Dados diários de vazão ANA](resultados/ANA_CABECEIRAS_VAZAO_DIARIA_1985_2025.csv)
- [Dados anuais de vazão ANA](resultados/ANA_CABECEIRAS_VAZAO_ANUAL_1985_2025.csv)
- [Dados de precipitação CHIRPS](resultados/PRECIPITACAO_CABECEIRAS_CHIRPS_1985_2025.csv)
- [Base integrada chuva e vazão](resultados/BASE_CHUVA_VAZAO_CABECEIRAS_1985_2025.csv)
- [Auditoria de exutórios](resultados/AUDITORIA_BACIAS_CHUVA_ANA.json)
- [Testes de ajuste por chuva](resultados/TESTE_VAZAO_SECA_AJUSTADA_CHUVA.csv)

## Próximo teste necessário antes de atribuição

1. Estimar **ET real por bacia** (GLEAM / TerraClimate; fontes e resolução registradas), e conferir tendências de temperatura e VPD. Simples redução da descarga com chuva semelhante não separa ET, captação, armazenamento e alterações na cobertura vegetal.
2. Quantificar **Q de base** por separação de hidrograma, com sensibilidade aos parâmetros, e indicadores Q90 e Q7; auditar mudanças de curva-chave e consistência da ANA.
3. Obter **outorgas/captações**, barramentos/PCHs, histórico de áreas irrigadas e pastagens no mesmo recorte geográfico.
4. Medir o balanço hídrico **P – ET – Q – ΔS – demais fluxos** sem denominar o resíduo automaticamente como perda.
5. Realizar pares de sub-bacias com mudanças contrastantes de pastagens, escalas de 1–10 anos e controles; o Jauru entra no Paraguai **a jusante** da estação urbana de Cáceres.

Referências: ANA (HidroInventario, HidroSerieHistorica), CHIRPS v2, WWF HydroBASINS L10, Coelho et al. (2025), *Water*, DOI 10.3390/w17101549. Todo o processamento permanece no ramo de pesquisa, sem alterar o Chuva-MT publicado.
