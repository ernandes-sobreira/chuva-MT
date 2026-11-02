# Resultado corrigido: bacia contribuinte de Cáceres — ANA 66070004

Área HydroBASINS L10 a montante: 32752.7 km². Pantanal dentro da bacia: 958.43 km².
Meses MapBiomas/CHIRPS: 492; meses cotas ANA: 471; meses vazão: 479.

## Pastagem na bacia e água superficial no bioma Pantanal a montante
Pastagem: 455149.0 ha (1985) a 1262482.0 ha (2025).
Água anual (apenas intersecção Pantanal a montante): 10976.9 ha a 10990.1 ha.
Pastagem x ano: r = 0.825.

## Defasagens exploratórias (HAC 12 meses, efeitos de mês e tendência, FDR BH)

- Chuva → cota: maior |β| em 1 meses, β=0.482, IC95%=[0.396, 0.567], p_FDR=1.93839e-27 (n=470).
- Chuva → vazão: maior |β| em 1 meses, β=0.588, IC95%=[0.480, 0.696], p_FDR=7.57375e-26 (n=478).
- Cota → água: maior |β| em 0 meses, β=0.496, IC95%=[0.209, 0.783], p_FDR=0.00488085 (n=471).
- Vazão → água: maior |β| em 0 meses, β=0.474, IC95%=[0.205, 0.744], p_FDR=0.00391221 (n=479).
- Chuva → água: maior |β| em 1 meses, β=0.252, IC95%=[0.086, 0.419], p_FDR=0.0103405 (n=491).

## Pastagens: consistência entre especificações

- Chuva e sazonalidade: β=-0.925, IC95%=[-2.078, 0.228], p_HAC=0.11594.
- Chuva + tendência: β=1.846, IC95%=[-0.013, 3.704], p_HAC=0.051599.
- Chuva + tendência + cota: β=2.121, IC95%=[0.175, 4.067], p_HAC=0.032627.
- Chuva + tendência + vazão: β=1.240, IC95%=[-0.454, 2.934], p_HAC=0.15136.

Primeiras diferenças anuais, n=34: β=4.100; IC95%=[-10.25740443304603, 18.457648763810017]; p=0.57568.

## Validação 1985–2014 contra 2015–2025

- chuva: RMSE 1.811 mil ha (mesma amostra, n treino=337, teste=132).
- chuva_vazao: RMSE 1.647 mil ha (mesma amostra, n treino=337, teste=132).
- chuva_vazao_pastagem: RMSE 1.550 mil ha (mesma amostra, n treino=337, teste=132).

**AVISO:** toda esta análise é observacional, espacialmente restrita ao pequeno setor do bioma Pantanal **a montante** da estação. Não atribuir causalidade nem extrapolar para todo o Pantanal.

Fontes oficiais e scripts documentados no ramo pesquisa-pantanal-extracao-2026.