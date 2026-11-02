# Pastagens e água: defasagens de 0 a 10 anos — bacia ANA Cáceres 66070004

**Recorte:** bacia HydroBASINS L10 com 32752.7 km²; água na intersecção com o bioma Pantanal (958.4 km²). Não é todo o Pantanal.
**Fonte:** MapBiomas Água C5, Cobertura C11, CHIRPS v2 e vazões ANA, 1985–2025.
**Método:** expansão anual de pastagens (ΔP_t), diferença anual da média mensal de água (ΔW_t) e desfechos de seca e água anual. 11 defasagens (k=0…10), janela fixa 1996–2025, ajustes por Δchuva_t, Δchuva_(t−1), Δágua_(t−1), erros HAC(2), IC95%, correção FDR-BH em 33 testes. Janela móvel de 15 anos e média móvel 3/5 anos.

## Teste primário por defasagem

| Lag (anos) | Coef. Δágua (mil ha / 100 mil ha pastagem) | IC95% | p HAC | p FDR (33 testes) |
|---:|---:|---:|---:|---:|
| 0 | 0.604 | [-0.283; 1.492] | 0.182 | 0.682 |
| 1 | 0.809 | [-0.170; 1.789] | 0.105 | 0.682 |
| 2 | 0.752 | [-0.346; 1.849] | 0.179 | 0.682 |
| 3 | 0.047 | [-1.184; 1.278] | 0.941 | 0.991 |
| 4 | 0.544 | [-0.564; 1.652] | 0.336 | 0.843 |
| 5 | 0.694 | [-0.199; 1.586] | 0.128 | 0.682 |
| 6 | 0.005 | [-0.979; 0.990] | 0.991 | 0.991 |
| 7 | 0.346 | [-0.679; 1.371] | 0.508 | 0.917 |
| 8 | 0.705 | [-0.297; 1.708] | 0.168 | 0.682 |
| 9 | -0.278 | [-1.352; 0.795] | 0.611 | 0.917 |
| 10 | -0.324 | [-1.532; 0.885] | 0.600 | 0.917 |

**Menor p bruto do teste primário:** lag 1 anos (p=0.1052, FDR=0.6816).
**Total de resultados FDR significativos entre 33 testes:** 0.

## Interpretação

Um lag estatisticamente significativo não demonstra efeito causal: pastagens e clima seguem trajetórias próprias, há poucos anos, potenciais fatores omitidos e múltiplas hipóteses. Correlações em janelas móveis são **descritivas**, não p-valores causais.

## Testes de robustez

- Três desfechos físicos diferentes (média mensal, seca, área anual).
- Diferenças anuais para mitigar tendência comum; mesma janela temporal para todos os lags.
- Sensibilidade com Δvazão (possível mediador hidrológico), tendência e acumulados de 1, 3 e 5 anos.
- Validação de reconstrução fora da amostra em blocos temporais; chuva do próprio ano observada, não previsão climática.
- Não interpretar janelas sobrepostas como observações independentes.

## Limitações fundamentais

A pastagem foi mapeada anualmente no mesmo limite, sem informação sobre lotação bovina ou manejo. A área com água não é volume. O bioma Pantanal dentro da bacia da estação abrange apenas um pequeno setor, não a planície inteira. É necessário estudar várias sub-bacias, conectividade, solo, barragens e clima para atribuição causal.

Arquivos de reprodução, tabelas e gráficos disponíveis neste diretório do ramo de pesquisa.