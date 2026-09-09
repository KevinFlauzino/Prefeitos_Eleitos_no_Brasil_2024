"""
Constroi o banco de dados completo dos planos de governo dos prefeitos eleitos em 2024.

Le a pasta PDFs/ (organizada por Regiao/Estado), extrai o texto de cada plano,
reconcilia com a lista oficial do IBGE (5.570 municipios) e grava tudo em SQLite
com indice de busca em texto completo (FTS5).

Uso:
    python app/construir_bd.py
    python app/construir_bd.py --sem-texto     (so metadados, mais rapido)
"""

import argparse
import difflib
import os
import re
import sqlite3
import time
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_PDFS = os.path.join(RAIZ, "PDFs")
CSV_OFICIAL = os.path.join(RAIZ, "Municípios Ausentes", "municipios_brasil.csv")
BANCO = os.path.join(RAIZ, "dados", "prefeitos2024.db")

# Pasta de estado -> sigla da UF
UF_POR_ESTADO = {
    "Acre": "AC", "Amapa": "AP", "Amazonas": "AM", "Para": "PA",
    "Rondonia": "RO", "Roraima": "RR", "Tocantins": "TO",
    "Alagoas": "AL", "Bahia": "BA", "Ceara": "CE", "Maranhao": "MA",
    "Paraiba": "PB", "Pernambuco": "PE", "Piaui": "PI",
    "Rio Grande do Norte": "RN", "Sergipe": "SE",
    "Goias": "GO", "Mato Grosso": "MT", "Mato Grosso do Sul": "MS",
    "Espirito Santo": "ES", "Minas Gerais": "MG",
    "Rio de Janeiro": "RJ", "Sao Paulo": "SP",
    "Parana": "PR", "Rio Grande do Sul": "RS", "Santa Catarina": "SC",
}

STATUS_COM_PROPOSTA = "COM_PROPOSTA"
STATUS_SEM_PROPOSTA = "SEM_PROPOSTA"
STATUS_SEM_ELEITO = "SEM_ELEITO"
STATUS_NAO_COLETADO = "NAO_COLETADO"
STATUS_SEM_PREFEITO = "SEM_PREFEITO"

# Divergencias de nomenclatura entre a lista do IBGE e o portal do TSE que a
# similaridade nao resolve (nomes historicos/alternativos do mesmo municipio).
# chave = (nome oficial normalizado, UF) -> nome normalizado usado pelo TSE
APELIDOS = {
    ("ACU", "RN"): "ASSU",                      # Açu tambem grafado Assú
    ("ARES", "RN"): "AREZ",                     # Arês / Arez
    ("JANUARIO CICCO", "RN"): "BOA SAUDE",      # Januário Cicco (ex-Boa Saúde)
}

# Unidades sem eleicao para prefeito: o DF elege governador e Fernando de
# Noronha e distrito estadual de Pernambuco.
SEM_PREFEITO = {("BRASILIA", "DF"), ("FERNANDO DE NORONHA", "PE")}


def normalizar(texto):
    """Maiusculas, sem acento, espacos colapsados. Usado como chave de cruzamento."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFD", str(texto))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.upper().replace("-", " ").replace("'", "").replace("`", "")
    texto = re.sub(r"[^A-Z0-9 ]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def carregar_lista_oficial():
    """Le municipios_brasil.csv (latin-1) -> lista de (nome, uf)."""
    registros = []
    with open(CSV_OFICIAL, "r", encoding="latin-1") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha or "," not in linha:
                continue
            nome, _, uf = linha.rpartition(",")
            nome, uf = nome.strip(), uf.strip().upper()
            if len(uf) == 2 and nome:
                registros.append((nome, uf))
    return registros


def interpretar_arquivo(caminho_rel, nome_arquivo, uf):
    """
    Extrai (municipio, candidato, status) do nome do arquivo.

    Padroes:
        MUNICIPIO_CANDIDATO.pdf                 -> COM_PROPOSTA
        MUNICIPIO_CANDIDATO-SEM_PROPOSTA.png    -> SEM_PROPOSTA
        MUNICIPIO-SEM_ELEITO.png                -> SEM_ELEITO
    """
    base = os.path.splitext(nome_arquivo)[0]

    if base.endswith("-SEM_ELEITO"):
        municipio = base[: -len("-SEM_ELEITO")]
        return limpar_municipio(municipio, uf), "", STATUS_SEM_ELEITO

    status = STATUS_COM_PROPOSTA
    if base.endswith("-SEM_PROPOSTA"):
        base = base[: -len("-SEM_PROPOSTA")]
        status = STATUS_SEM_PROPOSTA

    if "_" in base:
        municipio, _, candidato = base.partition("_")
    else:
        municipio, candidato = base, ""

    return limpar_municipio(municipio, uf), candidato.strip(), status


def limpar_municipio(nome, uf):
    """Remove sufixo de UF que as vezes vem colado no nome ('Barro Alto GO')."""
    nome = nome.strip()
    if uf and nome.upper().endswith(" " + uf):
        nome = nome[: -3].strip()
    return nome


def extrair_texto(caminho):
    """Texto integral do PDF. Retorna (texto, n_paginas)."""
    try:
        import fitz
    except ImportError:
        return "", 0
    try:
        with fitz.open(caminho) as doc:
            partes = [pagina.get_text() for pagina in doc]
            return "\n".join(partes), len(partes)
    except Exception:
        return "", 0


def varrer_pdfs(com_texto=True):
    """Percorre PDFs/ e devolve a lista de registros coletados."""
    coletados = []
    if not os.path.isdir(PASTA_PDFS):
        print(f"ERRO: pasta nao encontrada: {PASTA_PDFS}")
        return coletados

    total = sum(len(arqs) for _, _, arqs in os.walk(PASTA_PDFS))
    processados = 0
    inicio = time.time()

    for regiao in sorted(os.listdir(PASTA_PDFS)):
        caminho_regiao = os.path.join(PASTA_PDFS, regiao)
        if not os.path.isdir(caminho_regiao):
            continue
        for estado in sorted(os.listdir(caminho_regiao)):
            caminho_estado = os.path.join(caminho_regiao, estado)
            if not os.path.isdir(caminho_estado):
                continue
            uf = UF_POR_ESTADO.get(estado, "")
            for nome_arquivo in sorted(os.listdir(caminho_estado)):
                caminho = os.path.join(caminho_estado, nome_arquivo)
                if not os.path.isfile(caminho):
                    continue

                processados += 1
                municipio, candidato, status = interpretar_arquivo(
                    caminho, nome_arquivo, uf
                )

                texto, paginas = "", 0
                if com_texto and status == STATUS_COM_PROPOSTA:
                    texto, paginas = extrair_texto(caminho)

                coletados.append({
                    "municipio": municipio,
                    "municipio_norm": normalizar(municipio),
                    "uf": uf,
                    "regiao": regiao,
                    "estado": estado,
                    "candidato": candidato,
                    "status": status,
                    "arquivo": os.path.relpath(caminho, RAIZ).replace("\\", "/"),
                    "paginas": paginas,
                    "caracteres": len(texto),
                    "texto": texto,
                })

                if processados % 250 == 0:
                    decorrido = time.time() - inicio
                    print(f"  {processados}/{total} arquivos ({decorrido:.0f}s)", flush=True)

    print(f"  {processados}/{total} arquivos concluidos", flush=True)
    return coletados


def criar_esquema(con):
    con.executescript("""
        DROP TABLE IF EXISTS municipios;
        DROP TABLE IF EXISTS busca;

        CREATE TABLE municipios (
            id              INTEGER PRIMARY KEY,
            municipio       TEXT NOT NULL,
            municipio_norm  TEXT NOT NULL,
            uf              TEXT NOT NULL,
            regiao          TEXT,
            estado          TEXT,
            candidato       TEXT,
            partido         TEXT,
            status          TEXT NOT NULL,
            arquivo         TEXT,
            paginas         INTEGER DEFAULT 0,
            caracteres      INTEGER DEFAULT 0,
            texto           TEXT DEFAULT ''
        );

        CREATE INDEX idx_uf      ON municipios(uf);
        CREATE INDEX idx_regiao  ON municipios(regiao);
        CREATE INDEX idx_status  ON municipios(status);
        CREATE INDEX idx_norm    ON municipios(municipio_norm, uf);
    """)
    # Indice de texto completo (opcional: algumas builds nao trazem FTS5)
    try:
        con.executescript("""
            CREATE VIRTUAL TABLE busca USING fts5(
                texto,
                content='municipios',
                content_rowid='id',
                tokenize="unicode61 remove_diacritics 2"
            );
        """)
        return True
    except sqlite3.OperationalError as erro:
        print(f"  AVISO: FTS5 indisponivel ({erro}); busca usara LIKE.")
        return False


def trabalho_que_seria_perdido():
    """
    Reconstruir apaga a tabela e leva junto tudo o que foi acrescentado depois:
    OCR, auditoria de qualidade, partido e fotos do TSE. Antes de destruir,
    conferimos o que existe para avisar.
    """
    if not os.path.exists(BANCO):
        return {}
    perdas = {}
    try:
        con = sqlite3.connect(BANCO)
        colunas = {linha[1] for linha in con.execute("PRAGMA table_info(municipios)")}
        if "qualidade_texto" in colunas:
            n = con.execute("SELECT COUNT(*) FROM municipios "
                            "WHERE qualidade_texto = 'OCR'").fetchone()[0]
            if n:
                perdas["planos recuperados por OCR"] = n
            n = con.execute("SELECT COUNT(*) FROM municipios "
                            "WHERE qualidade_texto != ''").fetchone()[0]
            if n:
                perdas["classificacoes de qualidade"] = n
        for coluna, rotulo in [("partido", "partidos importados do TSE"),
                               ("foto", "fotos de prefeitos")]:
            if coluna in colunas:
                n = con.execute(f"SELECT COUNT(*) FROM municipios "
                                f"WHERE {coluna} != ''").fetchone()[0]
                if n:
                    perdas[rotulo] = n
        con.close()
    except sqlite3.Error:
        return {}
    return perdas


def construir(com_texto=True, forcar=False):
    perdas = trabalho_que_seria_perdido()
    if perdas and not forcar:
        print("ATENCAO: o banco atual contem trabalho que sera APAGADO:")
        for rotulo, quantidade in perdas.items():
            print(f"   - {quantidade} {rotulo}")
        print("\nReconstruir recria a tabela do zero a partir dos PDFs.")
        print("Se e isso mesmo que voce quer, rode de novo com --forcar.")
        print("Os textos ja reconhecidos continuam em dados/ocr/ e podem ser")
        print("reaplicados depois com: python app/ocr_planos.py --somente-juntar")
        return

    os.makedirs(os.path.dirname(BANCO), exist_ok=True)

    print("1/4  Lendo lista oficial do IBGE...")
    oficiais = carregar_lista_oficial()
    print(f"     {len(oficiais)} municipios oficiais")

    print("2/4  Varrendo PDFs e extraindo texto...")
    coletados = varrer_pdfs(com_texto=com_texto)
    print(f"     {len(coletados)} arquivos lidos")

    # Indexa coletados por (nome normalizado, uf)
    por_chave = {}
    duplicados = 0
    for registro in coletados:
        chave = (registro["municipio_norm"], registro["uf"])
        if chave in por_chave:
            duplicados += 1
            # mantem o que tem proposta / mais texto
            atual = por_chave[chave]
            if registro["caracteres"] > atual["caracteres"]:
                por_chave[chave] = registro
        else:
            por_chave[chave] = registro

    print("3/4  Reconciliando com a lista oficial...")

    # Passo 1: casamento exato. Passo 2: casamento aproximado dentro da mesma UF,
    # para absorver divergencias de grafia entre IBGE e TSE
    # (Arez/Ares, Assu/Acu, Espigao do Oeste/Espigao D'Oeste, Dona Eusebia/Euzebia...).
    pendentes_por_uf = {}
    for (nome_norm, uf), registro in por_chave.items():
        pendentes_por_uf.setdefault(uf, {})[nome_norm] = registro

    aproximados = []
    recusados = []

    # Nomes oficiais da UF: um coletado que bate exatamente com algum deles
    # pertence aquele municipio e nao pode ser cedido a outro por semelhanca.
    oficiais_por_uf = {}
    for nome_oficial, uf_oficial in oficiais:
        oficiais_por_uf.setdefault(uf_oficial, set()).add(normalizar(nome_oficial))

    consumidos = set()

    def casar(nome_norm, uf):
        """
        Devolve (registro, chave_usada) por igualdade, apelido ou semelhanca.

        A semelhanca e o ultimo recurso e vem cercada de tres travas, porque
        municipios diferentes da mesma UF podem ter nomes parecidissimos
        (GOIANIA e GOIANIRA ficam em 0,93; MARINOPOLIS e MARTINOPOLIS em 0,96).
        Sem elas, o plano de uma cidade seria atribuido a outra.
        """
        exato = por_chave.get((nome_norm, uf))
        if exato:
            consumidos.add((nome_norm, uf))
            return exato, (nome_norm, uf)

        apelido = APELIDOS.get((nome_norm, uf))
        if apelido:
            registro = por_chave.get((apelido, uf))
            if registro:
                consumidos.add((apelido, uf))
                return registro, (apelido, uf)

        candidatos = pendentes_por_uf.get(uf, {})
        if not candidatos:
            return None, None

        taxas = []
        for outro in candidatos:
            # Trava 1: nao disputar um coletado que ja pertence a outro
            # municipio oficial, por nome identico ou por ja ter sido usado.
            if outro in oficiais_por_uf.get(uf, ()) or (outro, uf) in consumidos:
                continue
            taxas.append((difflib.SequenceMatcher(None, nome_norm, outro).ratio(), outro))

        if not taxas:
            return None, None
        taxas.sort(reverse=True)
        melhor_taxa, melhor = taxas[0]
        segunda = taxas[1][0] if len(taxas) > 1 else 0.0

        # Trava 2: exigir semelhanca alta. Trava 3: exigir que o primeiro
        # colocado se destaque do segundo, para nao escolher no empate.
        if melhor_taxa >= 0.92 and (melhor_taxa - segunda) >= 0.04:
            consumidos.add((melhor, uf))
            aproximados.append((nome_norm, melhor, uf, melhor_taxa))
            return candidatos[melhor], (melhor, uf)
        if melhor_taxa >= 0.86:
            recusados.append((nome_norm, melhor, uf, melhor_taxa, segunda))
        return None, None

    linhas = []
    usados = set()
    for nome, uf in oficiais:
        nome_norm = normalizar(nome)
        registro, chave = casar(nome_norm, uf)
        if registro:
            usados.add(chave)
            linhas.append((
                nome, chave[0], uf, registro["regiao"], registro["estado"],
                registro["candidato"], "", registro["status"], registro["arquivo"],
                registro["paginas"], registro["caracteres"], registro["texto"],
            ))
        else:
            ausente = (STATUS_SEM_PREFEITO if (nome_norm, uf) in SEM_PREFEITO
                       else STATUS_NAO_COLETADO)
            linhas.append((
                nome, nome_norm, uf, "", "", "", "", ausente,
                "", 0, 0, "",
            ))

    # Coletados que nao casaram com nenhum municipio oficial
    orfaos = [r for c, r in por_chave.items() if c not in usados]
    for registro in orfaos:
        linhas.append((
            registro["municipio"], registro["municipio_norm"], registro["uf"],
            registro["regiao"], registro["estado"], registro["candidato"], "",
            registro["status"], registro["arquivo"], registro["paginas"],
            registro["caracteres"], registro["texto"],
        ))

    print("4/4  Gravando banco de dados...")
    con = sqlite3.connect(BANCO)
    tem_fts = criar_esquema(con)
    con.executemany("""
        INSERT INTO municipios
            (municipio, municipio_norm, uf, regiao, estado, candidato, partido,
             status, arquivo, paginas, caracteres, texto)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, linhas)
    if tem_fts:
        con.execute("INSERT INTO busca(rowid, texto) SELECT id, texto FROM municipios")
    con.commit()

    # Relatorio
    print("\n" + "=" * 58)
    print("RESUMO DO BANCO")
    print("=" * 58)
    print(f"Municipios oficiais (IBGE)........ {len(oficiais)}")
    print(f"Arquivos lidos da pasta PDFs...... {len(coletados)}")
    print(f"Duplicados descartados............ {duplicados}")
    print(f"Casados por similaridade.......... {len(aproximados)}")
    print(f"Coletados sem par oficial......... {len(orfaos)}")
    print(f"Linhas gravadas................... {len(linhas)}")
    print("-" * 58)
    for status, quantidade in con.execute(
        "SELECT status, COUNT(*) FROM municipios GROUP BY status ORDER BY COUNT(*) DESC"
    ):
        print(f"{status:.<33} {quantidade}")
    print("-" * 58)
    # Cobertura considera apenas municipios que de fato elegem prefeito
    cobertos = con.execute("""
        SELECT COUNT(*) FROM municipios WHERE status IN (?,?,?)
    """, (STATUS_COM_PROPOSTA, STATUS_SEM_PROPOSTA, STATUS_SEM_ELEITO)).fetchone()[0]
    elegiveis = con.execute(
        "SELECT COUNT(*) FROM municipios WHERE status != ?", (STATUS_SEM_PREFEITO,)
    ).fetchone()[0]
    # "Coberto" significa situacao VERIFICADA, o que inclui os municipios em que
    # se constatou nao haver plano. E diferente de "plano disponivel para
    # pesquisa": misturar os dois inflaria o que a base efetivamente permite
    # analisar.
    com_plano = con.execute(
        "SELECT COUNT(*) FROM municipios WHERE status = ?",
        (STATUS_COM_PROPOSTA,)).fetchone()[0]
    print(f"Municipios que elegem prefeito.... {elegiveis}")
    print(f"Situacao verificada............... {cobertos}/{elegiveis} "
          f"({100 * cobertos / elegiveis:.2f}%)")
    print(f"Com plano de governo publicado.... {com_plano}/{elegiveis} "
          f"({100 * com_plano / elegiveis:.2f}%)")
    faltantes = con.execute(
        "SELECT municipio, uf FROM municipios WHERE status = ? ORDER BY uf",
        (STATUS_NAO_COLETADO,)
    ).fetchall()
    if faltantes:
        print(f"Ainda sem dado.................... "
              + ", ".join(f"{m}/{u}" for m, u in faltantes))
    com_texto_n = con.execute(
        "SELECT COUNT(*) FROM municipios WHERE caracteres > 0"
    ).fetchone()[0]
    print(f"Com texto extraido................ {com_texto_n}")
    print("=" * 58)

    if aproximados:
        print("\nCasamentos por similaridade (IBGE <- TSE):")
        for oficial, coletado, uf, taxa in sorted(aproximados, key=lambda x: x[3]):
            print(f"  {taxa:.0%}  {oficial} / {uf}  <-  {coletado}")

    if orfaos:
        print("\nColetados sem par na lista oficial (checar grafia):")
        for registro in orfaos[:20]:
            print(f"  - {registro['municipio']} / {registro['uf']} ({registro['estado']})")
        if len(orfaos) > 20:
            print(f"  ... e mais {len(orfaos) - 20}")

    con.close()
    print(f"\nBanco gravado em: {BANCO}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sem-texto", action="store_true",
                        help="nao extrai texto dos PDFs (bem mais rapido)")
    parser.add_argument("--forcar", action="store_true",
                        help="reconstroi mesmo apagando OCR, auditoria e dados do TSE")
    argumentos = parser.parse_args()
    construir(com_texto=not argumentos.sem_texto, forcar=argumentos.forcar)
