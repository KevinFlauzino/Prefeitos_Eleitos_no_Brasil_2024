# Explorador da API eDinheiro

Painel local (Python + Flask) para **testar e analisar** a API de dados de pesquisa do
eDinheiro, e servir de base para o dashboard mais adiante.

- 📄 Documentação completa da API: [`DOCUMENTACAO_API_EDINHEIRO.md`](DOCUMENTACAO_API_EDINHEIRO.md)
- 🔑 Token: coloque no arquivo [`.env`](.env) (variável `MB_TOKEN`) — **nunca** commitado.

## O que dá pra fazer

- ✅ Health check da API (mostra online/offline no topo).
- 🔍 **Prévia** de qualquer endpoint — lê só as primeiras N linhas via CSV em *streaming*,
  então até `/v1/transacoes` (363 MB) fica rápido para inspecionar.
- 📊 Estatísticas automáticas por coluna (numéricas: mín/máx/média/soma; categóricas: top valores).
- 📈 Gráfico rápido (barras/histograma) de qualquer coluna, em canvas puro (sem CDN).
- ⬇️ Download do dataset completo em JSON, CSV ou XLSX.
- 🧾 Metadados de cache da resposta (`X-Cache`, idade, `X-Request-Id`, tempo).

## Como rodar

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

2. Edite o `.env` e cole seu token:

```
MB_TOKEN="seu-token-aqui"
```

3. Suba o servidor:

```bash
python app.py
```

4. Abra no navegador: <http://localhost:5000>

> O token fica só no servidor Python. O front-end nunca recebe o token — ele chama as rotas
> internas `/api/preview` e `/api/download`, que anexam o `Authorization` do lado do servidor.

## Estrutura

```
edinheiro_api/
├── app.py                        # backend Flask (proxy + estatísticas)
├── templates/index.html          # UI
├── static/style.css              # visual (tema escuro)
├── static/app.js                 # lógica, tabelas e gráficos
├── .env                          # SEU TOKEN (gitignored)
├── .env.example                  # modelo
├── requirements.txt
├── openapi.yaml                  # contrato OpenAPI 3.1 (importável no Postman/Insomnia)
└── DOCUMENTACAO_API_EDINHEIRO.md # toda a doc oficial consolidada
```

## Próximos passos (dashboard)

O `app.py` já isola bem a camada de acesso (token, cache-headers, streaming). Para o dashboard
final, dá pra reaproveitar as rotas `/api/preview` e `/api/download`, ou extrair as funções de
estatística para um módulo compartilhado.
