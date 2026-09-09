"""
Aplica OCR aos planos de governo que chegaram ao TSE como imagem escaneada.

Cerca de 7% dos planos nao tem camada de texto: o arquivo existe, tem paginas,
mas nada pode ser pesquisado nele. Sem este passo, esses municipios apareceriam
como "nao mencionam o tema" quando na verdade sao ilegiveis para o computador.

O reconhecimento roda em varios processos ao mesmo tempo. Cada arquivo
processado e gravado em dados/ocr/<id>.txt, entao a execucao pode ser
interrompida e retomada sem refazer o que ja terminou.

Uso:
    python app/ocr_planos.py                 # reconhece e grava no banco
    python app/ocr_planos.py --processos 4   # ajusta o paralelismo
    python app/ocr_planos.py --somente-juntar  # so aplica o que ja foi lido
"""

import argparse
import io
import multiprocessing
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

BANCO = os.path.join(RAIZ, "dados", "prefeitos2024.db")
PASTA_OCR = os.path.join(RAIZ, "dados", "ocr")
DPI = 150
QUALIDADES_ALVO = ("ESCANEADO", "CURTO", "VAZIO")



def listar_alvos():
    """Municipios cujo plano precisa de OCR, do menor para o maior."""
    con = sqlite3.connect(BANCO)
    alvos = con.execute(f"""
        SELECT id, municipio, uf, arquivo, paginas
        FROM municipios
        WHERE qualidade_texto IN ({','.join('?' * len(QUALIDADES_ALVO))})
          AND arquivo != ''
        ORDER BY paginas ASC
    """, QUALIDADES_ALVO).fetchall()
    con.close()
    return alvos


def _saida(identificador):
    return os.path.join(PASTA_OCR, f"{identificador}.txt")


def reconhecer(alvo):
    """
    Executado em processo separado. Le o PDF, rasteriza cada pagina e
    reconhece o texto. Devolve (id, municipio, uf, caracteres, erro).
    """
    identificador, municipio, uf, arquivo, paginas = alvo
    destino = _saida(identificador)
    if os.path.exists(destino):
        try:
            return identificador, municipio, uf, os.path.getsize(destino), None
        except OSError:
            pass

    # Cada processo usa um nucleo: o paralelismo esta entre processos
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("ORT_NUM_THREADS", "1")

    try:
        import fitz
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as erro:
        return identificador, municipio, uf, 0, f"dependencia ausente: {erro}"

    global _MOTOR
    try:
        _MOTOR
    except NameError:
        _MOTOR = RapidOCR()

    caminho = os.path.join(RAIZ, arquivo.replace("/", os.sep))
    if not os.path.exists(caminho):
        return identificador, municipio, uf, 0, "arquivo nao encontrado"

    partes = []
    try:
        with fitz.open(caminho) as documento:
            for pagina in documento:
                imagem = pagina.get_pixmap(dpi=DPI)
                matriz = np.frombuffer(imagem.samples, dtype=np.uint8).reshape(
                    imagem.height, imagem.width, imagem.n)
                if imagem.n == 4:
                    matriz = matriz[:, :, :3]
                resultado, _ = _MOTOR(matriz)
                if resultado:
                    partes.append(" ".join(bloco[1] for bloco in resultado))
    except Exception as erro:
        return identificador, municipio, uf, 0, str(erro)[:120]

    texto = "\n".join(partes)
    os.makedirs(PASTA_OCR, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as arquivo_saida:
        arquivo_saida.write(texto)
    return identificador, municipio, uf, len(texto), None


def juntar_no_banco():
    """Aplica ao banco os textos reconhecidos e reindexa a busca."""
    import busca

    if not os.path.isdir(PASTA_OCR):
        print("Nada reconhecido ainda.")
        return 0

    con = sqlite3.connect(BANCO)
    # A interface pode estar aberta segurando um cursor de leitura. Sem espera,
    # a gravacao falharia com "database is locked" e perderia todo o OCR.
    con.execute("PRAGMA busy_timeout = 30000")
    try:
        con.execute("PRAGMA journal_mode = WAL")
    except sqlite3.Error:
        pass

    colunas = {linha[1] for linha in con.execute("PRAGMA table_info(municipios)")}
    tem_norm = "texto_norm" in colunas
    tem_fts = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='busca'"
    ).fetchone() is not None

    aplicados, vazios, parciais = 0, 0, 0
    for nome_arquivo in os.listdir(PASTA_OCR):
        if not nome_arquivo.endswith(".txt"):
            continue
        identificador = int(nome_arquivo[:-4])
        with open(os.path.join(PASTA_OCR, nome_arquivo), encoding="utf-8") as arquivo:
            texto = arquivo.read().strip()

        if not texto:
            vazios += 1
            con.execute("UPDATE municipios SET qualidade_texto='OCR_VAZIO' WHERE id=?",
                        (identificador,))
            continue

        # A tabela FTS5 e external-content: ela le a linha da tabela de origem
        # para calcular o que apagar. Por isso a remocao do indice antigo TEM
        # de acontecer ANTES do UPDATE; invertido, o delete usaria o texto novo,
        # deixaria os tokens antigos no indice e corromperia a busca.
        if tem_fts:
            antigo = con.execute("SELECT texto FROM municipios WHERE id = ?",
                                 (identificador,)).fetchone()
            con.execute("INSERT INTO busca(busca, rowid, texto) VALUES ('delete', ?, ?)",
                        (identificador, (antigo[0] if antigo else "") or ""))

        # O reconhecimento pode devolver pouquissimo texto (pagina em branco,
        # imagem de baixa qualidade). Marcar tudo como 'OCR' esconderia que o
        # documento continua ilegivel na pratica e o tiraria dos avisos da
        # interface. A densidade por pagina decide.
        paginas = con.execute("SELECT paginas FROM municipios WHERE id = ?",
                              (identificador,)).fetchone()
        paginas = (paginas[0] if paginas else 0) or 0
        denso = len(texto) >= max(200, 120 * paginas) if paginas else len(texto) >= 200
        qualidade = "OCR" if denso else "OCR_PARCIAL"
        if not denso:
            parciais += 1

        campos = "texto = ?, caracteres = ?, qualidade_texto = ?"
        valores = [texto, len(texto), qualidade]
        if tem_norm:
            campos += ", texto_norm = ?"
            valores.append(busca.normalizar(texto))
        valores.append(identificador)
        con.execute(f"UPDATE municipios SET {campos} WHERE id = ?", valores)

        if tem_fts:
            con.execute("INSERT INTO busca(rowid, texto) VALUES (?, ?)",
                        (identificador, texto))
        aplicados += 1

        # Gravacao em lotes: uma unica transacao com centenas de documentos
        # grandes fica muito tempo com o banco travado.
        if aplicados % 25 == 0:
            con.commit()

    con.commit()
    con.close()
    print(f"Aplicados no banco: {aplicados}"
          f"   (reconhecimento parcial: {parciais}, sem texto: {vazios})")
    return aplicados


def executar(processos):
    alvos = listar_alvos()
    pendentes = [a for a in alvos if not os.path.exists(_saida(a[0]))]
    paginas = sum(a[4] or 0 for a in pendentes)

    print(f"Planos que precisam de OCR....... {len(alvos)}")
    print(f"Ja reconhecidos.................. {len(alvos) - len(pendentes)}")
    print(f"Pendentes........................ {len(pendentes)}  ({paginas} paginas)")
    if not pendentes:
        print("Nada a reconhecer.")
        return

    estimativa = paginas * 11.7 / max(processos, 1) / 3600
    print(f"Processos........................ {processos}")
    print(f"Estimativa....................... {estimativa:.1f} h\n")

    os.makedirs(PASTA_OCR, exist_ok=True)
    inicio = time.time()
    concluidos = falhas = 0

    with multiprocessing.Pool(processos) as pool:
        for identificador, municipio, uf, tamanho, erro in pool.imap_unordered(
                reconhecer, pendentes, chunksize=1):
            concluidos += 1
            if erro:
                falhas += 1
                print(f"  [ERRO] {municipio}/{uf}: {erro}", flush=True)
            if concluidos % 10 == 0 or concluidos == len(pendentes):
                decorrido = time.time() - inicio
                ritmo = concluidos / decorrido if decorrido else 0
                restam = (len(pendentes) - concluidos) / ritmo / 60 if ritmo else 0
                print(f"  {concluidos}/{len(pendentes)} arquivos  "
                      f"({decorrido / 60:.0f} min decorridos, faltam ~{restam:.0f} min)",
                      flush=True)

    print(f"\nReconhecimento concluido em {(time.time() - inicio) / 60:.0f} min "
          f"({falhas} falhas).")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processos", type=int,
                        default=max(1, (os.cpu_count() or 4) - 2))
    parser.add_argument("--somente-juntar", action="store_true")
    argumentos = parser.parse_args()

    if not argumentos.somente_juntar:
        executar(argumentos.processos)
    juntar_no_banco()
