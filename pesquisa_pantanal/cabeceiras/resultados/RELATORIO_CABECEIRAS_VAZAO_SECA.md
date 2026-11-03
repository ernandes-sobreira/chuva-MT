# Água que chega ao Pantanal: diagnóstico da vazão das cabeceiras, 1985–2025

Esta análise usa vazão efetivamente medida pela ANA, **não** área inundada ou água virtual.

## Tendências por estação na estiagem (julho–outubro)

| Estação | Anos | Theil–Sen m³/s/ano | IC95% | p ajustado HAC/FDR |
|---|---:|---:|---|---:|
| Jauru - Água Suja | 30 | -0.470 | [-0.707, -0.234] | 3.198e-05 |
| Jauru - Porto Esperidião | 34 | -0.419 | [-0.617, -0.242] | 1.683e-06 |
| Sepotuba - São José | 33 | -1.568 | [-1.880, -1.220] | 4.477e-16 |
| Cabaçal - MT-125 | 32 | -0.293 | [-0.466, -0.072] | 0.001658 |
| Paraguai - Cáceres | 37 | -3.333 | [-4.394, -2.451] | 1.122e-10 |
| Paraguai - Descalvados | 21 | -3.547 | [-4.840, -2.195] | 3.733e-09 |
| Paraguai - Porto Conceição | 26 | -5.189 | [-7.541, -3.391] | 1.022e-11 |

## Limitações

- HidroSerieHistorica pode retornar séries de diferentes níveis de consistência; prioriza consistido e registra nível por dia.
- Tendências não foram ajustadas por chuva, irrigação ou mudanças na curva-chave.
- Kendall tau sem correção para autocorrelação; inferência exploratória.
- Áreas de drenagem da compilação antiga ainda precisam ser validadas com BHO/ANA.
- Q90 é vazão observada excedida em 90% dos dias, não baseflow hidrologicamente separado.
- Incremento entre dois postos Jauru só faz sentido quando a topologia a montante–jusante e propagação de cheia estiverem certificadas.
- Rio Jauru entra no Paraguai A JUSANTE da estação urbana de Cáceres.

**Conclusão científica atual:** diminuição de vazão observada em parte das estações, mas 'a água sumiu' é incorreto até fechar balanço P–ET–Q–ΔS e validar ações humanas. A descarga específica e Q90, quando controladas por chuva, são passos indispensáveis.