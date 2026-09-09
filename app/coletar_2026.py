"""
Coleta as propostas de governo da eleicao geral de 2026.

Base complementar do projeto ("base 2"). Por exigencia da Lei 9.504/1997,
art. 11, paragrafo 1, inciso IX, apenas candidatos a **Prefeito, Governador e
Presidente** entregam proposta de governo. Como 2026 e eleicao geral, o universo
aqui e pequeno e integralmente coberto:

    Presidente ....... 13 candidaturas
    Governador ....... 200 candidaturas

Estrategia em duas etapas:

1. A API publica do portal de Divulgacao de Candidaturas fornece a lista de
   candidatos e, no detalhe de cada um, a relacao de arquivos entregues. A
   proposta de governo e o arquivo com codTipo = "5".
2. O download usa a rota /divulga/rest/arquivo/doc/{idArquivo}. O caminho que
   aparece nos metadados do arquivo NAO serve para baixar (devolve 403); a rota
   correta foi extraida do pacote JavaScript do proprio portal. O conteudo vem
   em base64 pela pagina, o que dispensa o gerenciador de downloads.

IMPORTANTE: o portal do TSE recusa conexoes de fora do Brasil. Rode este script
em uma rede brasileira.

Uso:
    python app/coletar_2026.py                  # tudo
    python app/coletar_2026.py --cargo presidente
    python app/coletar_2026.py --uf RJ
    python app/coletar_2026.py --somente-listar  # so o levantamento, sem baixar
"""

import argparse
import io
import json
import os
import sqlite3
import sys
import time

_ORIGEM = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ORIGEM)
import busca  # noqa: E402
busca.configurar_console()
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "app"))

PASTA = os.path.join(RAIZ, "PDFs_2026")
BANCO = os.path.join(RAIZ, "dados", "eleicoes2026.db")
ID_ELEICAO = "20322002026"
BASE_API = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1"
PORTAL = "https://divulgacandcontas.tse.jus.br/divulga/"

CARGOS = {"presidente": ("1", ["BR"]), "governador": ("3", None)}
COD_PROPOSTA = "5"

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO"]



# --------------------------------------------------------------- navegador
def abrir_navegador(pasta_download=None, visivel=False):
    """
    Chrome controlado por Selenium.

    O sinalizador --no-proxy-server e necessario quando o script roda dentro de
    um ambiente com proxy: sem ele, a borda do TSE devolve 403.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opcoes = Options()
    if not visivel:
        opcoes.add_argument("--headless=new")
    for sinalizador in ("--disable-gpu", "--log-level=3", "--no-proxy-server",
                        "--proxy-bypass-list=*", "--disable-dev-shm-usage"):
        opcoes.add_argument(sinalizador)
    opcoes.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

    if pasta_download:
        os.makedirs(pasta_download, exist_ok=True)
        opcoes.add_experimental_option("prefs", {
            "download.default_directory": pasta_download,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        })

    navegador = webdriver.Chrome(options=opcoes)
    navegador.set_page_load_timeout(90)
    return navegador


def consultar_api(navegador, caminho):
    """Chama a API a partir da origem do portal e devolve o JSON."""
    bruto = navegador.execute_async_script("""
        const retorno = arguments[arguments.length - 1];
        const caminho = arguments[0];
        fetch(caminho)
            .then(resposta => resposta.text())
            .then(texto => retorno(texto))
            .catch(erro => retorno('ERRO ' + erro));
    """, caminho)
    if not bruto or bruto.startswith("ERRO"):
        raise RuntimeError(f"falha ao consultar {caminho}: {str(bruto)[:120]}")
    if "Access Denied" in bruto[:400]:
        raise RuntimeError(
            "o portal do TSE recusou a conexao (Access Denied).\n"
            "     Rode este script em uma rede brasileira.")
    return json.loads(bruto)


# ----------------------------------------------------------------- coleta
def listar_candidatos(navegador, cargo, ufs):
    """Levanta os candidatos do cargo nas UFs pedidas."""
    codigo, ufs_fixas = CARGOS[cargo]
    alvos = ufs_fixas if ufs_fixas else (ufs or UFS)
    candidatos = []
    for uf in alvos:
        caminho = (f"/divulga/rest/v1/candidatura/listar/2026/{uf}/"
                   f"{ID_ELEICAO}/{codigo}/candidatos")
        try:
            dados = consultar_api(navegador, caminho)
        except Exception as erro:
            print(f"  {uf}: {str(erro)[:110]}")
            continue
        for item in dados.get("candidatos", []):
            candidatos.append({
                "id": item.get("id"),
                "uf": uf,
                "cargo": cargo,
                "nome_urna": item.get("nomeUrna", ""),
                "nome": item.get("nomeCompleto", "") or item.get("nomeUrna", ""),
                "numero": item.get("numero", ""),
                "partido": (item.get("partido") or {}).get("sigla", ""),
                "situacao": item.get("descricaoSituacao", ""),
            })
        print(f"  {uf}: {len(dados.get('candidatos', []))} candidatos", flush=True)
    return candidatos


def detalhar(navegador, candidato):
    """Busca o detalhe e localiza a proposta de governo (codTipo 5)."""
    caminho = (f"/divulga/rest/v1/candidatura/buscar/2026/{candidato['uf']}/"
               f"{ID_ELEICAO}/candidato/{candidato['id']}")
    dados = consultar_api(navegador, caminho)
    candidato["foto_url"] = dados.get("fotoUrl", "")
    arquivos = dados.get("arquivos") or []

    # O codigo do tipo e a unica identificacao confiavel da proposta de governo.
    # Casar pelo nome como alternativa de mesmo peso e perigoso: entre os
    # documentos da candidatura ha peticoes e certidoes cujo titulo contem a
    # palavra "proposta", e a primeira que casasse entraria no lugar do plano.
    # Por isso o nome so e consultado quando NENHUM arquivo traz o codigo.
    proposta = next((a for a in arquivos
                     if str(a.get("codTipo")) == COD_PROPOSTA), None)
    if proposta is None:
        proposta = next((a for a in arquivos
                         if "PLANO DE GOVERNO" in (a.get("nome") or "").upper()), None)
    candidato["proposta_por_nome"] = bool(proposta) and \
        str(proposta.get("codTipo")) != COD_PROPOSTA
    if proposta:
        candidato["arquivo_id"] = proposta.get("idArquivo")
        candidato["arquivo_nome"] = proposta.get("nome")
        candidato["arquivo_url"] = proposta.get("url")
    candidato["tem_proposta"] = bool(proposta)
    candidato["total_arquivos"] = len(arquivos)
    return candidato


ROTA_DOCUMENTO = "/divulga/rest/arquivo/doc/{id}"

BAIXAR_EM_BASE64 = """
const retorno = arguments[arguments.length - 1];
fetch(arguments[0])
  .then(async resposta => {
      if (!resposta.ok) return retorno(JSON.stringify({status: resposta.status}));
      const dados = new Uint8Array(await resposta.arrayBuffer());
      let binario = '';
      const passo = 8192;
      for (let i = 0; i < dados.length; i += passo) {
          binario += String.fromCharCode.apply(null, dados.subarray(i, i + passo));
      }
      retorno(JSON.stringify({status: 200, base64: btoa(binario)}));
  })
  .catch(erro => retorno(JSON.stringify({erro: String(erro).slice(0, 90)})));
"""


def baixar_proposta(navegador, candidato, destino):
    """
    Baixa o PDF da proposta e grava em `destino`.

    O portal nao serve o arquivo pelo caminho que aparece nos metadados: aquele
    endereco devolve 403. A rota real e /divulga/rest/arquivo/doc/{idArquivo},
    extraida do proprio pacote JavaScript do portal. O conteudo e trazido em
    base64 pela pagina, o que dispensa depender do gerenciador de downloads do
    navegador. Devolve True se gravou.
    """
    if not candidato.get("tem_proposta") or not candidato.get("arquivo_id"):
        return False

    url = ("https://divulgacandcontas.tse.jus.br"
           + ROTA_DOCUMENTO.format(id=candidato["arquivo_id"]))
    try:
        bruto = navegador.execute_async_script(BAIXAR_EM_BASE64, url)
        resposta = json.loads(bruto)
    except Exception as erro:
        candidato["erro_download"] = str(erro)[:90]
        return False

    if resposta.get("status") != 200 or not resposta.get("base64"):
        candidato["erro_download"] = f"HTTP {resposta.get('status', resposta.get('erro'))}"
        return False

    import base64
    conteudo = base64.b64decode(resposta["base64"])
    if len(conteudo) < 1000:
        candidato["erro_download"] = f"arquivo muito pequeno ({len(conteudo)} bytes)"
        return False

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as arquivo:
        arquivo.write(conteudo)
    return True


# ------------------------------------------------------------------ banco
def gravar(candidatos):
    os.makedirs(os.path.dirname(BANCO), exist_ok=True)
    con = sqlite3.connect(BANCO)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS candidatos2026 (
            id             TEXT PRIMARY KEY,
            uf             TEXT,
            cargo          TEXT,
            nome           TEXT,
            nome_urna      TEXT,
            numero         TEXT,
            partido        TEXT,
            situacao       TEXT,
            tem_proposta   INTEGER DEFAULT 0,
            total_arquivos INTEGER DEFAULT 0,
            arquivo_nome   TEXT,
            arquivo        TEXT,
            foto_url       TEXT,
            texto          TEXT DEFAULT ''
        );
    """)
    for c in candidatos:
        con.execute("""
            INSERT INTO candidatos2026
                (id, uf, cargo, nome, nome_urna, numero, partido, situacao,
                 tem_proposta, total_arquivos, arquivo_nome, arquivo, foto_url, texto)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                -- Uma reexecucao parcial (por exemplo, so uma UF, ou com falha
                -- de rede no detalhamento) nao pode REBAIXAR o que ja se sabe.
                -- Sem os MAX/COALESCE abaixo, um candidato ja coletado com
                -- proposta voltaria a constar como se nao tivesse nenhuma.
                tem_proposta   = MAX(candidatos2026.tem_proposta, excluded.tem_proposta),
                total_arquivos = MAX(candidatos2026.total_arquivos, excluded.total_arquivos),
                arquivo_nome   = COALESCE(NULLIF(excluded.arquivo_nome, ''),
                                          candidatos2026.arquivo_nome),
                arquivo        = COALESCE(NULLIF(excluded.arquivo, ''),
                                          candidatos2026.arquivo),
                foto_url       = COALESCE(NULLIF(excluded.foto_url, ''),
                                          candidatos2026.foto_url),
                texto          = COALESCE(NULLIF(excluded.texto, ''),
                                          candidatos2026.texto)
        """, (str(c.get("id")), c.get("uf"), c.get("cargo"), c.get("nome"),
              c.get("nome_urna"), c.get("numero"), c.get("partido"),
              c.get("situacao"), int(bool(c.get("tem_proposta"))),
              c.get("total_arquivos", 0), c.get("arquivo_nome", ""),
              c.get("arquivo", ""), c.get("foto_url", ""), c.get("texto", "")))
    con.commit()
    con.close()


def extrair_texto(caminho):
    try:
        import fitz
        with fitz.open(caminho) as documento:
            return "\n".join(pagina.get_text() for pagina in documento)
    except Exception:
        return ""


# --------------------------------------------------------------- execucao
def executar(cargos, ufs, somente_listar, visivel):
    navegador = abrir_navegador(None, visivel)
    navegador.set_script_timeout(180)
    try:
        navegador.get(PORTAL)
        time.sleep(2)

        todos = []
        for cargo in cargos:
            print(f"\nLevantando candidatos a {cargo}...")
            todos += listar_candidatos(navegador, cargo, ufs)
        print(f"\nTotal de candidatos: {len(todos)}")
        if not todos:
            print("Nenhum candidato retornado. Confira a conexao com o portal.")
            return

        print("\nConsultando os arquivos entregues por cada candidatura...")
        com_proposta = 0
        for indice, candidato in enumerate(todos, 1):
            try:
                detalhar(navegador, candidato)
                com_proposta += int(bool(candidato.get("tem_proposta")))
            except Exception as erro:
                print(f"  [{indice}] {candidato['nome_urna']}: {str(erro)[:90]}")
            if indice % 25 == 0:
                print(f"  {indice}/{len(todos)}", flush=True)
        print(f"Candidatos com proposta publicada: {com_proposta} de {len(todos)}")

        gravar(todos)
        if somente_listar:
            print(f"\nLevantamento gravado em {BANCO}")
            return

        print("\nBaixando as propostas...")
        baixados = 0
        for indice, candidato in enumerate(todos, 1):
            if not candidato.get("tem_proposta"):
                continue
            destino_pasta = os.path.join(PASTA, candidato["cargo"], candidato["uf"])
            os.makedirs(destino_pasta, exist_ok=True)
            seguro = "".join(ch for ch in candidato["nome_urna"]
                             if ch.isalnum() or ch in " -_")[:60].strip()
            destino = os.path.join(destino_pasta, f"{seguro}.pdf")
            if os.path.exists(destino):
                candidato["arquivo"] = os.path.relpath(destino, RAIZ).replace("\\", "/")
                if not candidato.get("texto"):
                    candidato["texto"] = extrair_texto(destino)
                baixados += 1
                continue
            if baixar_proposta(navegador, candidato, destino):
                candidato["arquivo"] = os.path.relpath(destino, RAIZ).replace("\\", "/")
                candidato["texto"] = extrair_texto(destino)
                baixados += 1
                print(f"  [{indice}] {candidato['nome_urna']}/{candidato['uf']}: "
                      f"ok ({os.path.getsize(destino) // 1024} KB)", flush=True)
            else:
                print(f"  [{indice}] {candidato['nome_urna']}/{candidato['uf']}: "
                      f"falhou ({candidato.get('erro_download', '?')})", flush=True)

        gravar(todos)
        print(f"\nPropostas baixadas: {baixados} de {com_proposta}")
        print(f"Arquivos em {PASTA}")
        print(f"Banco em {BANCO}")
    finally:
        try:
            navegador.quit()
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cargo", choices=["presidente", "governador", "todos"],
                        default="todos")
    parser.add_argument("--uf", action="append",
                        help="restringe a UF (pode repetir)")
    parser.add_argument("--somente-listar", action="store_true")
    parser.add_argument("--visivel", action="store_true",
                        help="mostra o navegador (util para diagnosticar)")
    argumentos = parser.parse_args()

    escolhidos = (["presidente", "governador"] if argumentos.cargo == "todos"
                  else [argumentos.cargo])
    executar(escolhidos, argumentos.uf, argumentos.somente_listar, argumentos.visivel)
