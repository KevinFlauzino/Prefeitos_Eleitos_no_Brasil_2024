"""
Importa dados oficiais do TSE: cadastro de candidatos e fotos.

Complementa o banco construido a partir dos PDFs com informacoes que so existem
no cadastro oficial: partido, numero na urna, situacao final da apuracao e a
fotografia do candidato.

Fonte: Portal de Dados Abertos do TSE (dadosabertos.tse.jus.br), arquivos
publicos distribuidos por cdn.tse.jus.br.

    consulta_cand_2024_BRASIL.zip   cadastro de todas as candidaturas
    foto_cand2024_<UF>_div.zip      fotos, uma por candidatura

O cruzamento com o banco local usa municipio + UF + cargo (Prefeito) + situacao
"ELEITO". A foto e localizada pelo numero sequencial da candidatura
(SQ_CANDIDATO), que e o nome do arquivo dentro do ZIP.

Uso:
    python app/importar_tse.py                 # baixa o que faltar e importa
    python app/importar_tse.py --somente-cadastro
    python app/importar_tse.py --somente-fotos
    python app/importar_tse.py --sem-baixar    # usa o que ja esta em dados/tse/
"""

import argparse
import csv
import io
import os
import sqlite3
import sys
import unicodedata
import zipfile

_ORIGEM = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ORIGEM)
import busca  # noqa: E402
busca.configurar_console()
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "app"))

BANCO = os.path.join(RAIZ, "dados", "prefeitos2024.db")
PASTA_TSE = os.path.join(RAIZ, "dados", "tse")
PASTA_FOTOS = os.path.join(RAIZ, "dados", "fotos")

CDN = "https://cdn.tse.jus.br/estatistica/sead"
URL_CADASTRO = f"{CDN}/odsele/consulta_cand/consulta_cand_2024_BRASIL.zip"
URL_FOTOS = CDN + "/eleicoes/eleicoes2024/fotos/foto_cand2024_{uf}_div.zip"

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "ES", "GO", "MA", "MG", "MS", "MT",
       "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE",
       "SP", "TO"]

CABECALHOS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Referer": "https://dadosabertos.tse.jus.br/",
}



def normalizar(texto):
    if not texto:
        return ""
    texto = unicodedata.normalize("NFD", str(texto))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return " ".join(texto.upper().replace("-", " ").split())


def baixar(url, destino):
    """Baixa o arquivo se ainda nao existir. Devolve True se esta disponivel."""
    if os.path.exists(destino) and os.path.getsize(destino) > 1024:
        return True
    try:
        import requests
    except ImportError:
        print("  ERRO: biblioteca 'requests' ausente (pip install requests)")
        return False

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    try:
        with requests.get(url, headers=CABECALHOS, stream=True, timeout=300) as resposta:
            if resposta.status_code != 200:
                print(f"  FALHA {resposta.status_code} em {os.path.basename(destino)}")
                if resposta.status_code == 403:
                    print("     O CDN do TSE recusou a conexao. Isso costuma ser "
                          "bloqueio geografico:\n"
                          "     rode este script em uma rede brasileira, ou baixe o "
                          "arquivo manualmente\n"
                          f"     de {url}\n"
                          f"     e salve em {destino}")
                return False
            total = int(resposta.headers.get("Content-Length", 0))
            baixado = 0
            with open(destino, "wb") as arquivo:
                for pedaco in resposta.iter_content(chunk_size=1 << 20):
                    arquivo.write(pedaco)
                    baixado += len(pedaco)
                    if total:
                        print(f"\r  {os.path.basename(destino)}: "
                              f"{100 * baixado / total:.0f}%", end="", flush=True)
            print()
        return True
    except Exception as erro:
        print(f"  ERRO ao baixar {os.path.basename(destino)}: {str(erro)[:120]}")
        return False


def ler_cadastro(caminho_zip):
    """
    Le o CSV de candidaturas e devolve os prefeitos eleitos,
    indexados por (municipio normalizado, UF).
    """
    eleitos = {}
    with zipfile.ZipFile(caminho_zip) as pacote:
        nomes = [n for n in pacote.namelist() if n.lower().endswith(".csv")]
        for nome in nomes:
            with pacote.open(nome) as bruto:
                texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
                leitor = csv.DictReader(texto, delimiter=";")
                for linha in leitor:
                    if (linha.get("DS_CARGO") or "").strip().upper() != "PREFEITO":
                        continue
                    situacao = (linha.get("DS_SIT_TOT_TURNO") or "").strip().upper()
                    if situacao not in ("ELEITO", "ELEITO POR QP", "ELEITO POR MEDIA"):
                        continue
                    uf = (linha.get("SG_UF") or "").strip().upper()
                    municipio = normalizar(linha.get("NM_UE"))
                    if not uf or not municipio:
                        continue
                    eleitos[(municipio, uf)] = {
                        "sq_candidato": (linha.get("SQ_CANDIDATO") or "").strip(),
                        "nome_urna": (linha.get("NM_URNA_CANDIDATO") or "").strip(),
                        "nome_completo": (linha.get("NM_CANDIDATO") or "").strip(),
                        "partido": (linha.get("SG_PARTIDO") or "").strip(),
                        "numero": (linha.get("NR_CANDIDATO") or "").strip(),
                        "situacao": situacao,
                    }
    return eleitos


def importar_cadastro(eleitos):
    """Grava partido, numero e situacao oficial no banco."""
    con = sqlite3.connect(BANCO)
    colunas = {linha[1] for linha in con.execute("PRAGMA table_info(municipios)")}
    for coluna, tipo in [("sq_candidato", "TEXT"), ("numero_urna", "TEXT"),
                         ("nome_urna", "TEXT"), ("situacao_tse", "TEXT"),
                         ("foto", "TEXT")]:
        if coluna not in colunas:
            con.execute(f"ALTER TABLE municipios ADD COLUMN {coluna} {tipo} DEFAULT ''")
    con.commit()

    registros = con.execute(
        "SELECT id, municipio_norm, uf FROM municipios").fetchall()
    casados = 0
    for identificador, municipio_norm, uf in registros:
        dados = eleitos.get((municipio_norm, uf))
        if not dados:
            continue
        con.execute("""
            UPDATE municipios
               SET partido = ?, sq_candidato = ?, numero_urna = ?,
                   nome_urna = ?, situacao_tse = ?
             WHERE id = ?
        """, (dados["partido"], dados["sq_candidato"], dados["numero"],
              dados["nome_urna"], dados["situacao"], identificador))
        casados += 1
    con.commit()
    con.close()
    print(f"  Cadastro cruzado com o banco: {casados} municipios")
    return casados


def importar_fotos(baixar_arquivos=True):
    """Extrai as fotos dos eleitos e registra o caminho no banco."""
    os.makedirs(PASTA_FOTOS, exist_ok=True)
    con = sqlite3.connect(BANCO)
    colunas = {linha[1] for linha in con.execute("PRAGMA table_info(municipios)")}
    if "sq_candidato" not in colunas:
        print("  Rode a importacao do cadastro antes das fotos.")
        con.close()
        return 0

    # sequencial da candidatura -> id do municipio no banco
    por_sequencial = {}
    for identificador, sequencial, uf in con.execute(
            "SELECT id, sq_candidato, uf FROM municipios WHERE sq_candidato != ''"):
        por_sequencial.setdefault(uf, {})[str(sequencial)] = identificador

    total = 0
    for uf in UFS:
        alvos = por_sequencial.get(uf, {})
        if not alvos:
            continue
        caminho_zip = os.path.join(PASTA_TSE, f"foto_cand2024_{uf}_div.zip")
        if baixar_arquivos and not baixar(URL_FOTOS.format(uf=uf), caminho_zip):
            continue
        if not os.path.exists(caminho_zip):
            continue

        achadas = 0
        try:
            with zipfile.ZipFile(caminho_zip) as pacote:
                for nome in pacote.namelist():
                    base = os.path.basename(nome)
                    if not base.lower().endswith((".jpg", ".jpeg", ".png")):
                        continue
                    # padrao: F<UF><SQ_CANDIDATO>.jpg  ou  <SQ_CANDIDATO>.jpg
                    miolo = os.path.splitext(base)[0]
                    digitos = "".join(c for c in miolo if c.isdigit())
                    identificador = None
                    for sequencial, id_municipio in alvos.items():
                        if sequencial and sequencial in digitos:
                            identificador = id_municipio
                            break
                    if identificador is None:
                        continue
                    destino_rel = f"dados/fotos/{uf}_{identificador}.jpg"
                    destino = os.path.join(RAIZ, destino_rel.replace("/", os.sep))
                    with pacote.open(nome) as origem, open(destino, "wb") as saida:
                        saida.write(origem.read())
                    con.execute("UPDATE municipios SET foto = ? WHERE id = ?",
                                (destino_rel, identificador))
                    achadas += 1
        except zipfile.BadZipFile:
            print(f"  {uf}: arquivo ZIP invalido, refaca o download")
            continue

        con.commit()
        total += achadas
        print(f"  {uf}: {achadas} fotos")

    con.close()
    print(f"  Fotos importadas: {total}")
    return total


def executar(baixar_arquivos, cadastro, fotos):
    if not os.path.exists(BANCO):
        print("ERRO: banco nao encontrado. Rode app/construir_bd.py antes.")
        return
    os.makedirs(PASTA_TSE, exist_ok=True)

    if cadastro:
        print("1) Cadastro oficial de candidaturas")
        caminho = os.path.join(PASTA_TSE, "consulta_cand_2024_BRASIL.zip")
        if baixar_arquivos and not baixar(URL_CADASTRO, caminho):
            print("  Sem o cadastro, o partido e as fotos nao podem ser importados.")
            return
        if not os.path.exists(caminho):
            print(f"  Arquivo ausente: {caminho}")
            return
        print("  Lendo o cadastro...")
        eleitos = ler_cadastro(caminho)
        print(f"  Prefeitos eleitos no cadastro: {len(eleitos)}")
        importar_cadastro(eleitos)

    if fotos:
        print("\n2) Fotos dos prefeitos eleitos")
        importar_fotos(baixar_arquivos)

    con = sqlite3.connect(BANCO)
    with_partido = con.execute(
        "SELECT COUNT(*) FROM municipios WHERE partido != ''").fetchone()[0]
    colunas = {linha[1] for linha in con.execute("PRAGMA table_info(municipios)")}
    with_foto = con.execute(
        "SELECT COUNT(*) FROM municipios WHERE foto != ''").fetchone()[0] \
        if "foto" in colunas else 0
    con.close()
    print("\n" + "=" * 56)
    print(f"Municipios com partido preenchido... {with_partido}")
    print(f"Municipios com foto................. {with_foto}")
    print("=" * 56)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sem-baixar", action="store_true",
                        help="usa apenas arquivos ja presentes em dados/tse/")
    parser.add_argument("--somente-cadastro", action="store_true")
    parser.add_argument("--somente-fotos", action="store_true")
    argumentos = parser.parse_args()

    quer_cadastro = not argumentos.somente_fotos
    quer_fotos = not argumentos.somente_cadastro
    executar(not argumentos.sem_baixar, quer_cadastro, quer_fotos)
