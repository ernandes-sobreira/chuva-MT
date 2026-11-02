# Piloto receptor e controles — entorno Fazenda Ressaca

**Recorte:** 3.600 ha da área com expansão de pastagens; 1.200 ha do receptor atravessado por caminhos MERIT D8; dois grupos-controle de 1.200 ha. Nenhum deles é perímetro fundiário. Cota ANA e chuva CHIRPS são dados observados.
**Ressalva:** MERIT é aproximação monodirecional, insuficiente para comprovar conectividade hidráulica na planície alagável.

## Comparabilidade prévia (1985–1994)

- CONTROLE_NORTE: r pré=0.738; tendência de diferença=0.062 pp/ano (IC95% -0.109–0.234), p HAC=0.4775.
- CONTROLE_SENSIBILIDADE: r pré=0.702; tendência de diferença=0.083 pp/ano (IC95% -0.094–0.260), p HAC=0.3568.

## Mudança pré/pós ajustada em modelos observacionais

- CONTROLE_NORTE / clima_sazonal: coef pós=-0.752 pp, IC95% -2.255–0.751, p HAC=0.3266.
- CONTROLE_NORTE / clima_sazonal_cota: coef pós=-0.771 pp, IC95% -2.312–0.769, p HAC=0.3266.
- CONTROLE_SENSIBILIDADE / clima_sazonal: coef pós=-0.007 pp, IC95% -1.444–1.430, p HAC=0.9925.
- CONTROLE_SENSIBILIDADE / clima_sazonal_cota: coef pós=0.127 pp, IC95% -1.301–1.556, p HAC=0.8612.

## Defasagem anual: 44 testes, FDR significativos: 1.

Sem inferência causal: controles podem partilhar processos hidrológicos, e o sistema responde a chuvas e vazões de toda a BAP.

## Dados e reprodução
No mesmo diretório: CSV mensal, anual, testes de pretrend, regressões HAC, lags 0–10, mapas, códigos e dados MERIT D8.