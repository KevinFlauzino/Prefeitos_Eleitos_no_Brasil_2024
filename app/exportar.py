"""
Gravacao das listas em planilha, sem depender do pandas.

O pandas era usado apenas para montar uma tabela a partir de uma lista de
dicionarios e grava-la. Ele arrasta o numpy junto e, no executavel distribuido
aos usuarios, respondia por dezenas de megabytes que nenhuma outra parte do
aplicativo aproveita. As duas funcoes abaixo fazem o mesmo com a biblioteca
padrao e com o openpyxl, que ja era necessario para escrever .xlsx.
"""
import csv
import io


def _linhas(registros, campos):
    """Extrai, de cada registro, os campos pedidos, na ordem pedida."""
    for registro in registros:
        yield ["" if registro.get(campo) is None else str(registro.get(campo))
               for campo in campos]


def _gravar_csv(caminho, titulos, registros, campos):
    # utf-8-sig faz o Excel reconhecer os acentos ao abrir o arquivo,
    # e o ponto e virgula e o separador que ele espera no Brasil.
    with io.open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";",
                              quoting=csv.QUOTE_MINIMAL)
        escritor.writerow(titulos)
        escritor.writerows(_linhas(registros, campos))


def _gravar_xlsx(caminho, titulos, registros, campos):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    livro = Workbook()
    planilha = livro.active
    planilha.title = "Resultados"

    planilha.append(titulos)
    for celula in planilha[1]:
        celula.font = Font(bold=True)

    # O Excel recusa celula acima de 32.767 caracteres, e o campo de trechos
    # literais pode passar disso quando o municipio tem muitas ocorrencias.
    limite = 32000
    for linha in _linhas(registros, campos):
        planilha.append([valor[:limite] for valor in linha])

    planilha.freeze_panes = "A2"
    for coluna, titulo in enumerate(titulos, start=1):
        largura = min(60, max(12, len(titulo) + 4))
        planilha.column_dimensions[
            planilha.cell(row=1, column=coluna).column_letter].width = largura

    livro.save(caminho)


def gravar(caminho, registros, campos, titulos):
    """
    Grava os registros em .csv ou .xlsx, conforme a extensao do caminho.

    campos   nomes das chaves a extrair de cada registro, na ordem desejada
    titulos  cabecalho a escrever, na mesma ordem
    """
    if len(campos) != len(titulos):
        raise ValueError("campos e titulos precisam ter o mesmo tamanho")
    if caminho.lower().endswith(".csv"):
        _gravar_csv(caminho, titulos, registros, campos)
    else:
        _gravar_xlsx(caminho, titulos, registros, campos)
    return len(registros)
