"""
Explorador da API eDinheiro
===========================

Servidor local (Flask) que funciona como um "painel de teste" para a API de
dados de pesquisa do eDinheiro (https://dados.edinheiro.org).

O que ele faz:
  - Le o token do arquivo .env (variavel MB_TOKEN) — o token nunca vai para o navegador.
  - Faz o health check da API.
  - Busca uma previa de qualquer endpoint (streaming de CSV, so as primeiras N linhas),
    o que deixa ate a rota gigante /v1/transacoes (363 MB) rapida para inspecionar.
  - Calcula estatisticas basicas por coluna (numericas e categoricas) para analise.
  - Permite baixar o dataset completo em json/csv/xlsx.

Rode com:  python app.py
E abra:    http://localhost:5000
"""

from __future__ import annotations

import csv
import io
import os
import time

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

load_dotenv()

BASE_URL = os.getenv("MB_BASE_URL", "https://dados.edinheiro.org").rstrip("/")
TOKEN = (os.getenv("MB_TOKEN") or "").strip()
PORT = int(os.getenv("PORT", "5000"))

# Timeout generoso — a doc recomenda pelo menos 300s (MISS de cache consulta a base na hora).
REQUEST_TIMEOUT = 300

# Metadados dos conjuntos de dados (da documentacao oficial).
ENDPOINTS = {
    "indicadores-mensais": {
        "titulo": "Indicadores mensais",
        "descricao": "Indicadores mensais por banco comunitario: contas ativas, "
                     "comercios credenciados, valores emitidos, gastos no comercio "
                     "local, pagamentos, saques, arrecadacao e indices de uso.",
        "tamanho": "2,7 MB",
        "tempo": "44 s",
        "grande": False,
    },
    "comercios": {
        "titulo": "Comercios",
        "descricao": "Comercios por bairro, setor e porte, com contagem mensal.",
        "tamanho": "27 KB",
        "tempo": "7 s",
        "grande": False,
    },
    "beneficios": {
        "titulo": "Beneficios",
        "descricao": "Beneficios por programa e mes: beneficiarios, pagamentos e valor total.",
        "tamanho": "335 KB",
        "tempo": "4 s",
        "grande": False,
    },
    "usuarios": {
        "titulo": "Usuarios",
        "descricao": "Usuarios por bairro, faixa etaria, genero e faixa de renda.",
        "tamanho": "625 KB",
        "tempo": "13 s",
        "grande": False,
    },
    "transacoes": {
        "titulo": "Transacoes",
        "descricao": "Transacoes intraurbanas agregadas: bairro de origem e destino, "
                     "tipo, faixa de valor, setor e porte do destino, quantidade e valor "
                     "total. Cobre abr/2015 a jul/2026 (~1,47 mi de linhas). Cada linha "
                     "agrega no minimo 5 transacoes.",
        "tamanho": "363 MB",
        "tempo": "161 s",
        "grande": True,
    },
}

app = Flask(__name__)


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def coletar_meta(resp: requests.Response, elapsed: float) -> dict:
    """Extrai os cabecalhos uteis da resposta da API."""
    return {
        "status": resp.status_code,
        "elapsed_s": round(elapsed, 2),
        "x_cache": resp.headers.get("X-Cache"),
        "x_cache_age": resp.headers.get("X-Cache-Age"),
        "x_data_generated_at": resp.headers.get("X-Data-Generated-At"),
        "x_request_id": resp.headers.get("X-Request-Id"),
        "content_type": resp.headers.get("Content-Type"),
        "retry_after": resp.headers.get("Retry-After"),
    }


def _num(valor: str):
    """Tenta converter uma celula para numero (aceita virgula decimal)."""
    if valor is None:
        return None
    v = valor.strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        pass
    # tenta padrao brasileiro: 1.234,56
    try:
        return float(v.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def calcular_stats(colunas: list[str], linhas: list[list[str]]) -> list[dict]:
    """Estatisticas simples por coluna sobre as linhas carregadas."""
    stats = []
    n = len(linhas)
    for i, nome in enumerate(colunas):
        valores = [linha[i] if i < len(linha) else "" for linha in linhas]
        nums = [_num(v) for v in valores]
        validos = [x for x in nums if x is not None]
        preenchidos = [v for v in valores if v is not None and v.strip() != ""]
        # Numerica se a maioria das celulas preenchidas vira numero.
        eh_numerica = len(preenchidos) > 0 and len(validos) >= 0.8 * len(preenchidos)

        col = {
            "nome": nome,
            "tipo": "numerica" if eh_numerica else "categorica",
            "preenchidos": len(preenchidos),
            "vazios": n - len(preenchidos),
            "distintos": len(set(preenchidos)),
        }

        if eh_numerica and validos:
            col.update({
                "min": min(validos),
                "max": max(validos),
                "media": sum(validos) / len(validos),
                "soma": sum(validos),
            })
        else:
            contagem: dict[str, int] = {}
            for v in preenchidos:
                contagem[v] = contagem.get(v, 0) + 1
            top = sorted(contagem.items(), key=lambda kv: kv[1], reverse=True)[:12]
            col["top"] = [{"valor": k, "contagem": c} for k, c in top]

        stats.append(col)
    return stats


@app.route("/")
def index():
    return render_template(
        "index.html",
        endpoints=ENDPOINTS,
        base_url=BASE_URL,
        token_configurado=bool(TOKEN),
    )


@app.route("/api/token-status")
def token_status():
    return jsonify({
        "configurado": bool(TOKEN),
        "base_url": BASE_URL,
        # so mostra o tamanho, nunca o valor
        "tamanho": len(TOKEN) if TOKEN else 0,
    })


@app.route("/api/health")
def health():
    try:
        t0 = time.time()
        resp = requests.get(f"{BASE_URL}/health", timeout=30)
        elapsed = time.time() - t0
        try:
            corpo = resp.json()
        except ValueError:
            corpo = {"raw": resp.text[:500]}
        return jsonify({
            "ok": resp.status_code == 200,
            "status": resp.status_code,
            "elapsed_s": round(elapsed, 2),
            "body": corpo,
        })
    except requests.RequestException as e:
        return jsonify({"ok": False, "erro": str(e)}), 502


@app.route("/api/preview")
def preview():
    """Previa em streaming: le apenas as primeiras `limit` linhas via CSV."""
    recurso = request.args.get("recurso", "")
    if recurso not in ENDPOINTS:
        return jsonify({"erro": f"Recurso desconhecido: {recurso}"}), 400
    if not TOKEN:
        return jsonify({"erro": "Token nao configurado. Preencha MB_TOKEN no arquivo .env."}), 401

    try:
        limit = int(request.args.get("limit", "500"))
    except ValueError:
        limit = 500
    limit = max(1, min(limit, 20000))

    url = f"{BASE_URL}/v1/{recurso}"
    t0 = time.time()
    try:
        resp = requests.get(
            url,
            params={"format": "csv"},
            headers=auth_headers(),
            timeout=REQUEST_TIMEOUT,
            stream=True,
        )
    except requests.RequestException as e:
        return jsonify({"erro": f"Falha ao chamar a API: {e}"}), 502

    if resp.status_code != 200:
        meta = coletar_meta(resp, time.time() - t0)
        texto = ""
        try:
            texto = resp.text[:500]
        except Exception:
            pass
        resp.close()
        return jsonify({"erro": f"HTTP {resp.status_code}", "meta": meta, "corpo": texto}), resp.status_code

    # Le linhas suficientes para header + limit registros.
    buffer_linhas: list[str] = []
    try:
        for linha in resp.iter_lines(decode_unicode=True):
            if linha is None:
                continue
            buffer_linhas.append(linha)
            if len(buffer_linhas) >= limit + 1:
                break
    finally:
        elapsed = time.time() - t0
        meta = coletar_meta(resp, elapsed)
        resp.close()

    if not buffer_linhas:
        return jsonify({"erro": "Resposta vazia da API.", "meta": meta}), 502

    leitor = csv.reader(io.StringIO("\n".join(buffer_linhas)))
    todas = list(leitor)
    colunas = todas[0] if todas else []
    linhas = todas[1:] if len(todas) > 1 else []

    stats = calcular_stats(colunas, linhas)

    return jsonify({
        "recurso": recurso,
        "colunas": colunas,
        "linhas": linhas,
        "linhas_retornadas": len(linhas),
        "truncado": len(buffer_linhas) >= limit + 1,
        "meta": meta,
        "stats": stats,
    })


@app.route("/api/download")
def download():
    """Baixa o dataset completo no formato escolhido, repassando o stream ao navegador."""
    recurso = request.args.get("recurso", "")
    formato = request.args.get("format", "csv")
    if recurso not in ENDPOINTS:
        return jsonify({"erro": f"Recurso desconhecido: {recurso}"}), 400
    if formato not in ("json", "csv", "xlsx"):
        return jsonify({"erro": "Formato invalido. Use json, csv ou xlsx."}), 400
    if not TOKEN:
        return jsonify({"erro": "Token nao configurado."}), 401

    url = f"{BASE_URL}/v1/{recurso}"
    try:
        upstream = requests.get(
            url,
            params={"format": formato},
            headers=auth_headers(),
            timeout=REQUEST_TIMEOUT,
            stream=True,
        )
    except requests.RequestException as e:
        return jsonify({"erro": f"Falha ao chamar a API: {e}"}), 502

    if upstream.status_code != 200:
        texto = upstream.text[:500]
        upstream.close()
        return jsonify({"erro": f"HTTP {upstream.status_code}", "corpo": texto}), upstream.status_code

    ext = {"json": "json", "csv": "csv", "xlsx": "xlsx"}[formato]
    content_type = {
        "json": "application/json",
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }[formato]

    def gerar():
        try:
            for bloco in upstream.iter_content(chunk_size=1024 * 1024):
                if bloco:
                    yield bloco
        finally:
            upstream.close()

    headers = {
        "Content-Disposition": f'attachment; filename="{recurso}.{ext}"',
    }
    return Response(stream_with_context(gerar()), content_type=content_type, headers=headers)


if __name__ == "__main__":
    print(f"  eDinheiro API Explorer  ->  http://localhost:{PORT}")
    print(f"  Base: {BASE_URL}  |  Token configurado: {'sim' if TOKEN else 'NAO (edite o .env)'}")
    app.run(host="127.0.0.1", port=PORT, debug=True)
