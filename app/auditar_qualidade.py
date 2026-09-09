"""
Audita a qualidade do texto extraido de cada plano de governo.

Nem todo PDF do TSE tem camada de texto: parte dos planos foi enviada como
imagem escaneada. Esses arquivos existem e tem paginas, mas nao produzem texto
pesquisavel - e, sem sinalizacao, apareceriam como "sem mencao ao tema" quando
na verdade sao ilegiveis para a busca.

Este script classifica cada municipio e grava o resultado na coluna
`qualidade_texto`:

    OK          texto extraido normalmente
    ESCANEADO   PDF de imagem, precisa de OCR para ser pesquisavel
    CURTO       tem texto, mas pouco (possivel extracao parcial)
    VAZIO       sem texto e sem imagem aproveitavel
    SEM_ARQUIVO nao ha plano publicado (SEM_PROPOSTA / SEM_ELEITO / etc.)

Uso:
    python app/auditar_qualidade.py
"""

import io
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import busca  # noqa: E402

busca.configurar_console()


RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Um plano de governo real dificilmente tem menos que isto.
LIMITE_CURTO = 1000

# Densidade minima de texto por pagina. Um plano digitado tem alguns milhares de
# caracteres por pagina; abaixo deste piso o documento e imagem com, no maximo,
# uma capa ou um sumario digitais.
CARACTERES_POR_PAGINA = 120


def parece_escaneado(caracteres, paginas):
    """
    Reconhece o PDF de imagem por duas assinaturas.

    A primeira e o caso puro: o texto se resume a uma quebra de linha por
    pagina. A segunda pega o documento escaneado que traz capa ou sumario com
    camada de texto - sem ela, um arquivo como Paulo Afonso/BA (127 paginas e
    1.998 caracteres, 16 por pagina) passaria como legivel, escaparia do OCR e
    seria lido pelo pesquisador como um plano que nao trata do tema.
    """
    if paginas <= 0:
        return False
    if caracteres <= max(5 * paginas, 40):
        return True
    return paginas >= 3 and (caracteres / paginas) < CARACTERES_POR_PAGINA


def auditar():
    if not busca.banco_existe():
        print("ERRO: banco nao encontrado. Rode app/construir_bd.py antes.")
        return

    con = sqlite3.connect(busca.BANCO)
    con.row_factory = sqlite3.Row

    colunas = {linha[1] for linha in con.execute("PRAGMA table_info(municipios)")}
    if "qualidade_texto" not in colunas:
        print("Criando coluna qualidade_texto...")
        con.execute("ALTER TABLE municipios ADD COLUMN qualidade_texto TEXT DEFAULT ''")
        con.commit()

    registros = con.execute("""
        SELECT id, municipio, uf, status, arquivo, paginas, caracteres,
               COALESCE(qualidade_texto, '') AS qualidade_texto
        FROM municipios
    """).fetchall()

    print(f"Auditando {len(registros)} municipios...")
    inicio = time.time()
    contagem, suspeitos, atualizacoes = {}, [], []

    for registro in registros:
        status = registro["status"]
        caracteres = registro["caracteres"] or 0
        paginas = registro["paginas"] or 0
        atual = registro["qualidade_texto"] or ""

        # Um plano ja processado pelo OCR nao pode ser reclassificado pela
        # regra de densidade: o texto agora vem do reconhecimento, e reauditar
        # o devolveria para a fila do OCR indefinidamente.
        if atual in ("OCR", "OCR_PARCIAL", "OCR_VAZIO"):
            contagem[atual] = contagem.get(atual, 0) + 1
            continue

        if status != "COM_PROPOSTA":
            qualidade = "SEM_ARQUIVO"
        elif parece_escaneado(caracteres, paginas):
            # Testado ANTES do limite absoluto: um documento longo e escaneado
            # pode passar dos 1.000 caracteres so pela capa digital.
            qualidade = "ESCANEADO"
            suspeitos.append(registro)
        elif caracteres >= LIMITE_CURTO:
            qualidade = "OK"
        elif caracteres > 0:
            qualidade = "CURTO"
            suspeitos.append(registro)
        else:
            qualidade = "VAZIO"
            suspeitos.append(registro)

        contagem[qualidade] = contagem.get(qualidade, 0) + 1
        atualizacoes.append((qualidade, registro["id"]))

    con.executemany("UPDATE municipios SET qualidade_texto = ? WHERE id = ?",
                    atualizacoes)
    con.commit()

    # Confirma a natureza dos suspeitos abrindo os PDFs (so os poucos casos)
    print(f"Conferindo {len(suspeitos)} arquivos suspeitos nos PDFs...")
    try:
        import fitz
    except ImportError:
        fitz = None

    com_imagem = 0
    if fitz:
        for registro in suspeitos:
            caminho = os.path.join(RAIZ, (registro["arquivo"] or "").replace("/", os.sep))
            if not os.path.exists(caminho):
                continue
            try:
                with fitz.open(caminho) as documento:
                    if any(pagina.get_images(full=True) for pagina in documento):
                        com_imagem += 1
            except Exception:
                continue

    print("\n" + "=" * 62)
    print("QUALIDADE DO TEXTO DOS PLANOS DE GOVERNO")
    print("=" * 62)
    total_planos = sum(v for k, v in contagem.items() if k != "SEM_ARQUIVO")
    rotulos = ("OK", "OCR", "OCR_PARCIAL", "OCR_VAZIO",
               "ESCANEADO", "CURTO", "VAZIO", "SEM_ARQUIVO")
    legendas = {
        "OK": "texto extraido direto do PDF",
        "OCR": "recuperado por reconhecimento optico",
        "OCR_PARCIAL": "OCR insuficiente, segue ilegivel",
        "OCR_VAZIO": "OCR nao devolveu texto",
        "ESCANEADO": "imagem, ainda sem OCR",
        "CURTO": "extracao parcial",
        "VAZIO": "sem texto",
    }
    for qualidade in rotulos:
        quantidade = contagem.get(qualidade, 0)
        if not quantidade and qualidade not in ("OK", "SEM_ARQUIVO"):
            continue
        if qualidade == "SEM_ARQUIVO":
            print(f"{qualidade:.<24} {quantidade:>5}   (sem plano publicado)")
        else:
            print(f"{qualidade:.<24} {quantidade:>5}   "
                  f"({100 * quantidade / total_planos:>4.1f}%)  "
                  f"{legendas.get(qualidade, '')}")

    pesquisaveis = sum(contagem.get(q, 0) for q in busca.QUALIDADES_PESQUISAVEIS)
    ilegiveis = sum(contagem.get(q, 0) for q in busca.QUALIDADES_ILEGIVEIS)
    print("-" * 62)
    print(f"Planos com PDF publicado......... {total_planos}")
    print(f"Pesquisaveis por texto........... {pesquisaveis} "
          f"({100 * pesquisaveis / total_planos:.1f}%)")
    print(f"Ainda ilegiveis.................. {ilegiveis} "
          f"({100 * ilegiveis / total_planos:.1f}%)")
    print(f"Suspeitos com imagem no PDF...... {com_imagem} de {len(suspeitos)}")
    print("=" * 62)

    print("\nMunicipios maiores afetados (amostra):")
    for linha in con.execute("""
        SELECT municipio, uf, paginas, caracteres, qualidade_texto
        FROM municipios
        WHERE qualidade_texto IN ('ESCANEADO','VAZIO','CURTO')
        ORDER BY paginas DESC LIMIT 15
    """):
        print(f"  {linha['municipio'][:26]:<26}/{linha['uf']}  "
              f"{linha['paginas']:>3} pgs  {linha['caracteres']:>5} chars  "
              f"{linha['qualidade_texto']}")

    por_uf = con.execute("""
        SELECT uf, COUNT(*) n FROM municipios
        WHERE qualidade_texto IN ('ESCANEADO','VAZIO','CURTO')
        GROUP BY uf ORDER BY n DESC LIMIT 10
    """).fetchall()
    print("\nUFs com mais planos ilegiveis:")
    for linha in por_uf:
        print(f"  {linha['uf']}: {linha['n']}")

    con.close()
    print(f"\nConcluido em {time.time() - inicio:.0f}s")


if __name__ == "__main__":
    auditar()
