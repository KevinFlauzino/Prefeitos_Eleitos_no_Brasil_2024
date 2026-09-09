# API de Dados de Pesquisa — eDinheiro

> Documentação **completa** para acesso programático aos conjuntos de dados agregados
> disponibilizados para pesquisa.
>
> **Versão do documento:** 1.0 — julho de 2026
> **Consolidado por:** este arquivo reúne o conteúdo do PDF oficial (`API de Dados de Pesquisa — eDinheiro.pdf`)
> e da especificação `openapi.yaml`, para que a pasta original possa ser excluída sem perda de informação.

---

## 1. Endereço base

```
https://dados.edinheiro.org
```

Todo o acesso é feito por **HTTPS**. Requisições em HTTP são redirecionadas.

---

## 2. Autenticação

Todas as rotas de dados exigem um **token**, enviado no cabeçalho `Authorization`:

```
Authorization: Bearer SEU_TOKEN
```

- O token é entregue **separadamente** desta documentação, por canal seguro.
- Ele identifica a **instituição** e **não deve** ser publicado, versionado em repositórios ou compartilhado com terceiros.
- Requisições **sem token** ou com **token inválido** retornam **401**.

> Neste projeto, o token fica no arquivo `.env` (variável `MB_TOKEN`), que está no `.gitignore` e **nunca** deve ser commitado.

---

## 3. Conjuntos de dados

Todas as rotas são `GET`. Todos os conjuntos são **agregados**.

| Endpoint | Conteúdo |
|---|---|
| `GET /v1/indicadores-mensais` | Indicadores mensais por banco comunitário: contas ativas, comércios credenciados, valores emitidos, gastos no comércio local, pagamentos, saques, arrecadação e índices de uso |
| `GET /v1/comercios` | Comércios por bairro, setor e porte, com contagem mensal |
| `GET /v1/beneficios` | Benefícios por programa e mês: beneficiários, pagamentos e valor total |
| `GET /v1/usuarios` | Usuários por bairro, faixa etária, gênero e faixa de renda |
| `GET /v1/transacoes` | Transações intraurbanas agregadas: bairro de origem e destino, tipo, faixa de valor, setor e porte do destino, quantidade e valor total |

**Privacidade / anonimização:**

- Nenhum conjunto contém nome, CPF, número de conta, identificador de transação nem valores individuais.
- No conjunto de **transações**, cada linha corresponde a um grupo com **no mínimo 5 transações**; grupos menores são omitidos para impedir reidentificação.

---

## 4. Formatos

O parâmetro **opcional** `format` aceita três valores:

| Valor | Observação |
|---|---|
| `?format=json` | padrão |
| `?format=csv` | mais compacto (recomendado para conjuntos grandes) |
| `?format=xlsx` | planilha Excel |

Qualquer outro valor retorna **400**.

---

## 5. Exemplos de uso

### curl

```bash
export MB_TOKEN='seu-token'

curl --fail-with-body --max-time 300 \
  'https://dados.edinheiro.org/v1/indicadores-mensais' \
  -H "Authorization: Bearer $MB_TOKEN" \
  --output indicadores.json
```

Para os conjuntos maiores, CSV é bem mais compacto:

```bash
curl --fail-with-body --max-time 300 \
  'https://dados.edinheiro.org/v1/transacoes?format=csv' \
  -H "Authorization: Bearer $MB_TOKEN" \
  --output transacoes.csv
```

### Python (requests, download em streaming)

```python
import os
import requests

TOKEN = os.environ["MB_TOKEN"]
BASE = "https://dados.edinheiro.org"

def baixar(recurso, destino, formato="csv"):
    with requests.get(
        f"{BASE}/v1/{recurso}",
        params={"format": formato},
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=300,
        stream=True,
    ) as resposta:
        resposta.raise_for_status()
        with open(destino, "wb") as arquivo:
            for bloco in resposta.iter_content(chunk_size=1024 * 1024):
                arquivo.write(bloco)

baixar("beneficios", "beneficios.csv")
```

### Python (pandas, para os conjuntos menores)

```python
import pandas as pd

url = "https://dados.edinheiro.org/v1/beneficios?format=csv"
dados = pd.read_csv(url, storage_options={"Authorization": f"Bearer {TOKEN}"})
```

### R

```r
library(httr)
library(readr)

token <- Sys.getenv("MB_TOKEN")

resposta <- GET(
  "https://dados.edinheiro.org/v1/beneficios",
  query = list(format = "csv"),
  add_headers(Authorization = paste("Bearer", token)),
  timeout(300)
)

stop_for_status(resposta)
dados <- read_csv(content(resposta, as = "raw"))
```

---

## 6. Volume e tempo de resposta

Medições reais em **julho de 2026**, formato JSON:

| Endpoint | Tamanho | Primeira chamada |
|---|---:|---:|
| `/v1/comercios` | 27 KB | 7 s |
| `/v1/beneficios` | 335 KB | 4 s |
| `/v1/usuarios` | 625 KB | 13 s |
| `/v1/indicadores-mensais` | 2,7 MB | 44 s |
| `/v1/transacoes` | 363 MB | 161 s |

**Recomendações:**

- Configure o timeout do cliente em pelo menos **300 segundos**.
- Para `/v1/transacoes`, prefira `format=csv` e faça o download em **streaming**.
- Evite repetir o download do mesmo conjunto no mesmo dia — os dados são atualizados periodicamente, não a cada requisição.

O conjunto de **transações** cobre de **abril de 2015 a julho de 2026**, com **1.470.535 linhas agregadas** representando cerca de **21,4 milhões de transações**.

---

## 7. Atualização e cache

- Os resultados são armazenados em **cache por 1 hora**.
- Se o cache expirou, a **versão anterior é entregue imediatamente** enquanto uma atualização ocorre em segundo plano (padrão *stale-while-revalidate*).

Cada resposta traz cabeçalhos que permitem saber a idade do dado:

| Cabeçalho | Significado |
|---|---|
| `X-Cache` | `HIT` dado em cache · `MISS` consultado na hora · `STALE` versão anterior enquanto atualiza |
| `X-Cache-Age` | Idade do dado, em segundos |
| `X-Data-Generated-At` | Momento da extração, em ISO 8601 |
| `X-Request-Id` | Identificador da requisição (UUID), útil ao relatar problemas |

> Apenas o caso `MISS` é lento, porque consulta a base no momento da chamada.

---

## 8. Códigos de resposta

| Código | Significado | Ação sugerida |
|---:|---|---|
| `200` | Sucesso | — |
| `400` | Formato inválido | Use `json`, `csv` ou `xlsx` |
| `401` | Token ausente ou inválido | Verifique o cabeçalho `Authorization` |
| `404` | Endpoint inexistente | Confira a lista da seção 3 |
| `429` | Limite de uso excedido | Aguarde o tempo indicado em `Retry-After` |
| `502` | Falha temporária na origem dos dados | Tente novamente |
| `504` | Tempo excedido na origem dos dados | Tente novamente mais tarde |

**Limite de uso:** 60 requisições por minuto.

---

## 9. Verificação de disponibilidade (health check)

Endpoint **público**, sem autenticação e sem dados:

```bash
curl https://dados.edinheiro.org/health
```

Resposta esperada:

```json
{"status":"ok","version":"main-be8d84a4"}
```

---

## 10. Contrato técnico (OpenAPI)

A especificação **OpenAPI 3.1** está disponível no arquivo `openapi.yaml` (incluído neste projeto).
Ele pode ser importado em **Postman, Insomnia, Swagger UI** ou usado para gerar clientes automaticamente.

Resumo da spec:

- **Servidor:** `https://dados.edinheiro.org`
- **Segurança:** `bearerAuth` (HTTP Bearer) em todas as rotas de dados; `/health` é aberto.
- **Parâmetro comum:** `format` (query, opcional) — enum `[json, csv, xlsx]`, padrão `json`.
- **Rotas:** `/health`, `/v1/indicadores-mensais`, `/v1/comercios`, `/v1/beneficios`, `/v1/usuarios`, `/v1/transacoes`.
- **Respostas de erro modeladas:** `401` (unauthorized), `429` (rateLimit), `502` (upstreamFailure), `504` (upstreamTimeout).
- **Cabeçalhos de resposta de dados:** `X-Cache`, `X-Cache-Age`, `X-Data-Generated-At`, `X-Request-Id`.

---

## 11. Suporte

Em caso de erro, informe:

- o endpoint chamado e o formato solicitado;
- o horário aproximado;
- o código de resposta;
- o valor do cabeçalho `X-Request-Id`.

Esse identificador permite localizar a requisição nos registros do servidor. Os registros **não** armazenam tokens nem conteúdo dos dados.

---

## 12. Condições de uso

Os dados são fornecidos de forma **agregada**, para finalidade de **pesquisa**. **Não é permitido**:

- tentar reidentificar pessoas, comércios ou contas individuais a partir dos agregados;
- redistribuir o token de acesso.

---

## Anexo — especificação OpenAPI (`openapi.yaml`)

```yaml
openapi: 3.1.0
info:
  title: API mb-dados
  version: 1.0.0
  description: API autenticada para os dados da coleção UFRJ no Metabase.
servers:
  - url: https://dados.edinheiro.org
security:
  - bearerAuth: []
paths:
  /health:
    get:
      security: []
      summary: Verifica a saúde do processo
      responses:
        "200":
          description: Serviço disponível
          content:
            application/json:
              schema:
                type: object
                required: [status, version]
                properties:
                  status:
                    type: string
                    const: ok
                  version:
                    type: string
  /v1/indicadores-mensais:
    get:
      summary: Retorna os indicadores mensais do banco
      operationId: getIndicadoresMensais
      parameters:
        - $ref: "#/components/parameters/format"
      responses:
        "200": { $ref: "#/components/responses/data" }
        "401": { $ref: "#/components/responses/unauthorized" }
        "429": { $ref: "#/components/responses/rateLimit" }
        "502": { $ref: "#/components/responses/upstreamFailure" }
        "504": { $ref: "#/components/responses/upstreamTimeout" }
  /v1/comercios:
    get:
      summary: Retorna comércios por setor e bairro
      operationId: getComercios
      parameters:
        - $ref: "#/components/parameters/format"
      responses:
        "200": { $ref: "#/components/responses/data" }
        "401": { $ref: "#/components/responses/unauthorized" }
        "429": { $ref: "#/components/responses/rateLimit" }
        "502": { $ref: "#/components/responses/upstreamFailure" }
        "504": { $ref: "#/components/responses/upstreamTimeout" }
  /v1/beneficios:
    get:
      summary: Retorna benefícios por programa e mês
      operationId: getBeneficios
      parameters:
        - $ref: "#/components/parameters/format"
      responses:
        "200": { $ref: "#/components/responses/data" }
        "401": { $ref: "#/components/responses/unauthorized" }
        "429": { $ref: "#/components/responses/rateLimit" }
        "502": { $ref: "#/components/responses/upstreamFailure" }
        "504": { $ref: "#/components/responses/upstreamTimeout" }
  /v1/usuarios:
    get:
      summary: Retorna dados demográficos de usuários por bairro
      operationId: getUsuarios
      parameters:
        - $ref: "#/components/parameters/format"
      responses:
        "200": { $ref: "#/components/responses/data" }
        "401": { $ref: "#/components/responses/unauthorized" }
        "429": { $ref: "#/components/responses/rateLimit" }
        "502": { $ref: "#/components/responses/upstreamFailure" }
        "504": { $ref: "#/components/responses/upstreamTimeout" }
  /v1/transacoes:
    get:
      summary: Retorna transações intraurbanas
      operationId: getTransacoes
      parameters:
        - $ref: "#/components/parameters/format"
      responses:
        "200": { $ref: "#/components/responses/data" }
        "401": { $ref: "#/components/responses/unauthorized" }
        "429": { $ref: "#/components/responses/rateLimit" }
        "502": { $ref: "#/components/responses/upstreamFailure" }
        "504": { $ref: "#/components/responses/upstreamTimeout" }
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
  parameters:
    format:
      name: format
      in: query
      required: false
      schema:
        type: string
        enum: [json, csv, xlsx]
        default: json
  responses:
    data:
      description: Dados solicitados
      headers:
        X-Cache:
          schema:
            type: string
            enum: [HIT, MISS, STALE]
        X-Cache-Age:
          schema:
            type: integer
        X-Data-Generated-At:
          schema:
            type: string
            format: date-time
        X-Request-Id:
          schema:
            type: string
            format: uuid
      content:
        application/json: {}
        text/csv: {}
        application/vnd.openxmlformats-officedocument.spreadsheetml.sheet: {}
    unauthorized:
      description: Token ausente ou inválido
    rateLimit:
      description: Limite de requisições excedido
    upstreamFailure:
      description: Falha ao consultar o Metabase
    upstreamTimeout:
      description: Timeout ao consultar o Metabase
```
