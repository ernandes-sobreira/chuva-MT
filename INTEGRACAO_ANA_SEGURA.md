# Integração experimental ANA — Chuva MT

Esta branch prepara a consulta autenticada à API HidroWebService, **sem alterar a página publicada nem misturar fontes**.

## Sistema atual
- CHIRPS v3 via Earth Engine: total mensal de chuva por município, 142 municípios, histórico 1996–2025 e atualização posterior.
- GSMaP v8 operacional: chuva diária estimada por satélite, série provisória separada.

## Papel da ANA
A ANA disponibiliza medições pontuais em estações pluviométricas e telemétricas. Elas **não substituem** a média espacial CHIRPS por município nem a cobertura GSMaP. Na evolução da interface, criar camada independente de estações, com localização, código, medida, data/hora e qualidade; permitir comparação pontual com o pixel/município sob regras explícitas de escala e período.

## Segurança
Configure os GitHub Actions Secrets `ANA_IDENTIFICADOR` e `ANA_SENHA`, sem valores no repositório. O workflow manual `testar-ana-hidrowebservice.yml` roda consulta isolada e imprime apenas a contagem de registros, sem gravar resposta ou transmitir senha ao navegador. Ao validar formato/unidades/condições de uso, adicionar pipeline com cache, retries limitados, frequência autorizada, sanitização e metadados de procedência; não ativar scraping ou token na página pública.

**Importante:** a rotina CHIRPS/GSMaP já existente fica intacta. Nenhum dado ANA foi ainda publicado ou validado nesta branch.
