# Chuva MT

Chuva mensal por município de Mato Grosso, com mapa no tempo, comparação entre anos, análise por local e estatística.

**Idealizado por Ernandes Sobreira.**

Site: `https://ernandes-sobreira.github.io/chuva-mt/`

## Fonte dos dados

- **Chuva:** CHIRPS v3 (Climate Hazards Center, Universidade da Califórnia em Santa Barbara), coleção `UCSB-CHC/CHIRPS/V3/DAILY_SAT` do Google Earth Engine, somada por mês e reduzida à média espacial de cada município.
- **Série de referência:** janeiro de 1996 a dezembro de 2025, 142 municípios, embutida no `index.html`.
- **Malha municipal, mesorregiões, regiões intermediárias e biomas:** IBGE.

## Como a atualização automática funciona

1. Nos dias 3, 13 e 23 de cada mês, o GitHub Actions executa `scripts/atualizar_chuva.py`.
2. O script autentica no Earth Engine com uma conta de serviço e verifica quais meses, a partir de janeiro de 2026, já estão completos no CHIRPS.
3. Antes de gravar, ele recalcula quatro meses de 2025 e compara com a série de referência (`dados/validacao_referencia.csv`). Se o desvio mediano passar de 5%, nada é gravado.
4. Os meses novos vão para `dados/meses.json` (lido pelo site) e para `dados/mensal/AAAA-MM.csv`.

Nenhum valor é estimado ou preenchido. Mês incompleto no Earth Engine não entra.

## Arquivos

| Arquivo | Função |
|---|---|
| `index.html` | O site inteiro, em arquivo único |
| `dados/meses.json` | Meses posteriores a 2025, lidos pelo site |
| `dados/mensal/` | Um CSV por mês, para consulta |
| `dados/municipios_mt.geojson` | Malha dos 142 municípios usada no cálculo |
| `dados/validacao_referencia.csv` | Quatro meses de 2025 da série original, para a trava de validação |
| `scripts/atualizar_chuva.py` | Cálculo no Earth Engine |
| `.github/workflows/atualizar-chuva.yml` | Agendamento |

## Configuração (uma vez)

1. **Google Cloud:** no projeto já registrado no Earth Engine, ativar a Earth Engine API, criar uma conta de serviço com os papéis *Earth Engine Resource Viewer* e *Service Usage Consumer* e gerar uma chave JSON.
2. **GitHub, Settings, Secrets and variables, Actions:** criar o segredo `EE_SERVICE_ACCOUNT_KEY` com o conteúdo inteiro do arquivo JSON da chave.
3. **GitHub, Settings, Pages:** publicar a partir da branch `main`, pasta raiz.
4. **GitHub, Actions:** abrir "Atualizar chuva mensal" e clicar em "Run workflow" para a primeira execução.

A chave JSON nunca deve ser enviada para o repositório.

Variáveis opcionais (Settings, Variables): `EE_PROJECT` (id do projeto, se for diferente do da chave) e `CHIRPS_COLECAO` (para trocar a coleção; a trava de validação acusa se ela não reproduzir a série).

## Limites

- São estimativas de satélite, não medições de pluviômetro.
- O Earth Engine recebe o CHIRPS com algumas semanas de atraso, então o mês anterior pode demorar a aparecer.
- A malha usada aqui é a do IBGE de 2024, simplificada. Pequenas diferenças em relação à série original são esperadas e medidas pela trava de validação.
- O GitHub suspende agendamentos de repositórios sem atividade por 60 dias. As gravações mensais mantêm o repositório ativo.


## Atualização diária

A aba **Diário / Agora** usa uma série separada do histórico CHIRPS:

- Fonte: **JAXA GSMaP v8 operational (NRT)** no Earth Engine, coleção `JAXA/GPM_L3/GSMaP/v8/operational`.
- Banda: `hourlyPrecipRate` em mm/h.
- O dia civil de Mato Grosso é agregado em UTC-4; só entram dias com 24 imagens horárias.
- A primeira execução carrega os 120 dias completos mais recentes; depois a rotina acrescenta dias novos e recalcula os 14 dias mais recentes para incorporar revisões NRT.
- O arquivo publicado é `dados/diario.json` e a página mantém uma janela móvel de até 180 dias.
- Essa série é operacional/provisória e **não entra nos recordes, anomalias ou tendências da série histórica CHIRPS**.

O workflow `.github/workflows/atualizar-diario.yml` verifica a fonte diariamente.
