"""
Monta a distribuicao pronta para uso do Mapeador de Politicas Publicas
Municipais: um executavel do Windows que dispensa instalar Python.

    python empacotar.py

O resultado sai em dist/Mapeador/ e tambem como um unico arquivo .zip, que e o
que se publica na pagina de versoes do repositorio. A pasta contem:

    Mapeador.exe                 o programa
    dados/prefeitos2024.db       base dos planos de 2024
    dados/eleicoes2026.db        base das propostas de 2026
    PDFs/.../*.png               capturas que comprovam as ausencias
    LEIA-ME.txt                  instrucoes de uso

Os PDFs dos planos nao entram: sao mais de tres gigabytes. Sem eles o
aplicativo funciona normalmente, apenas o botao que abre o documento original
avisa que o arquivo nao esta presente. Quem quiser os PDFs clona o repositorio.
"""
import io
import os
import shutil
import subprocess
import sys
import zipfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(RAIZ, "dist")
PASTA = os.path.join(DIST, "Mapeador")
NOME = "Mapeador"

LEIA_ME = """MAPEADOR DE POLITICAS PUBLICAS MUNICIPAIS - versao 3.0

COMO USAR
  1. Extraia esta pasta inteira em qualquer lugar do computador.
  2. De dois cliques em Mapeador.exe.

  Nao e preciso instalar nada. O programa ja vem com a base pronta: 5.468
  planos de governo dos prefeitos eleitos em 2024 e as propostas dos
  candidatos a governador e a presidente em 2026.

  Mantenha o Mapeador.exe e a pasta dados lado a lado. Se separar os dois, o
  programa nao encontra a base e avisa na abertura.

O QUE VEM AQUI
  Mapeador.exe    o programa
  dados/          as duas bases de dados
  PDFs/           as capturas de tela que comprovam quais municipios nao
                  publicaram plano de governo

O QUE NAO VEM
  Os arquivos PDF dos planos de governo, que somam mais de tres gigabytes. O
  texto de todos eles esta dentro da base e pode ser pesquisado e lido dentro
  do programa. So o botao "Abrir plano original" precisa do PDF; sem ele, o
  programa avisa que o arquivo nao esta presente. Para ter os PDFs, clone o
  repositorio completo.

REQUISITOS
  Windows 10 ou 11, 4 GB de memoria e cerca de 1 GB livre em disco.

CODIGO-FONTE, DOCUMENTACAO E OS PDFS
  https://github.com/KevinFlauzino/Prefeitos_Eleitos_no_Brasil_2024

AUTOR
  Kevin Flauzino do Nascimento, Engenharia de Controle e Automacao, UFRJ.
  Orientacao: professor Eduardo Diniz, FGV EAESP.
"""


def executar(comando):
    print("  $", " ".join(comando[:3]), "...")
    resultado = subprocess.run(comando, cwd=RAIZ)
    if resultado.returncode != 0:
        raise SystemExit(f"falhou: {' '.join(comando)}")


def construir_executavel():
    print("1. gerando o executavel")
    executar([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", NOME,
        "--distpath", DIST,
        "--workpath", os.path.join(RAIZ, "build"),
        "--specpath", os.path.join(RAIZ, "build"),
        "--paths", os.path.join(RAIZ, "app"),
        # importados so quando o usuario exporta ou abre uma ficha com foto,
        # entao o PyInstaller nao os enxerga sozinho
        "--hidden-import", "openpyxl",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageTk",
        # nada disso e usado pela interface, e o pandas sozinho pesa dezenas
        # de megabytes por arrastar o numpy
        "--exclude-module", "pandas",
        "--exclude-module", "numpy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "fitz",
        "--exclude-module", "selenium",
        "--exclude-module", "rapidocr_onnxruntime",
        "--exclude-module", "onnxruntime",
        os.path.join(RAIZ, "app", "gui.py"),
    ])


def montar_pasta():
    print("2. montando a pasta da distribuicao")
    if os.path.isdir(PASTA):
        shutil.rmtree(PASTA)
    os.makedirs(os.path.join(PASTA, "dados"))

    origem_exe = os.path.join(DIST, NOME + ".exe")
    shutil.move(origem_exe, os.path.join(PASTA, NOME + ".exe"))
    print(f"     {NOME}.exe  "
          f"{os.path.getsize(os.path.join(PASTA, NOME + '.exe')) / 1e6:.0f} MB")

    for banco in ("prefeitos2024.db", "eleicoes2026.db"):
        origem = os.path.join(RAIZ, "dados", banco)
        if not os.path.exists(origem):
            raise SystemExit(f"base ausente: {origem}\n"
                             "rode antes: python app/construir_bd.py")
        shutil.copy2(origem, os.path.join(PASTA, "dados", banco))
        print(f"     dados/{banco}  {os.path.getsize(origem) / 1e6:.0f} MB")

    # so as capturas que comprovam ausencia de plano; os PDFs ficam de fora
    copiadas = 0
    for pasta, _, arquivos in os.walk(os.path.join(RAIZ, "PDFs")):
        for arquivo in arquivos:
            if not arquivo.lower().endswith(".png"):
                continue
            origem = os.path.join(pasta, arquivo)
            relativo = os.path.relpath(origem, RAIZ)
            destino = os.path.join(PASTA, relativo)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            shutil.copy2(origem, destino)
            copiadas += 1
    print(f"     PDFs/ capturas de comprovacao  {copiadas} arquivos")

    with io.open(os.path.join(PASTA, "LEIA-ME.txt"), "w",
                 encoding="utf-8") as arquivo:
        arquivo.write(LEIA_ME)


def compactar():
    print("3. compactando")
    destino = os.path.join(DIST, f"{NOME}-3.0-windows.zip")
    if os.path.exists(destino):
        os.remove(destino)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=6) as pacote:
        for pasta, _, arquivos in os.walk(PASTA):
            for arquivo in arquivos:
                caminho = os.path.join(pasta, arquivo)
                pacote.write(caminho, os.path.relpath(caminho, DIST))
    print(f"     {os.path.basename(destino)}  "
          f"{os.path.getsize(destino) / 1e6:.0f} MB")
    return destino


def main():
    construir_executavel()
    montar_pasta()
    pacote = compactar()
    print()
    print("pronto. publique o arquivo abaixo na pagina de versoes:")
    print(" ", pacote)


if __name__ == "__main__":
    main()
