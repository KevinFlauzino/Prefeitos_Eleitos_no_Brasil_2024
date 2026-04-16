import pandas as pd
import unicodedata

def normalizar_texto(texto):
    """Remove acentos, espaços extras e coloca tudo em maiúsculas para padronizar a comparação."""
    if pd.isna(texto):  # Evita erro caso haja valores nulos
        return ''
    texto = texto.strip().upper()  # Remove espaços extras e coloca em maiúsculas
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')  # Remove acentos
    return texto

def comparar_municipios(csv_file, txt_file, output_excel):
    # Carregar os municípios do CSV e garantir que são strings
    with open(csv_file, 'r', encoding='latin1') as f:
        municipios_csv = [normalizar_texto(line.strip()) for line in f]

    # Carregar os municípios do TXT e garantir que são strings
    with open(txt_file, 'r', encoding='latin1') as f:
        municipios_txt = {normalizar_texto(line.strip()) for line in f}  # Usamos set() para busca rápida

    # Lista para armazenar os municípios que não foram encontrados no TXT
    municipios_faltantes = []

    # Comparação linha por linha
    for municipio in municipios_csv:
        if municipio not in municipios_txt:
            municipios_faltantes.append(municipio)

    # Criar DataFrame com os municípios faltantes
    df_faltantes = pd.DataFrame(municipios_faltantes, columns=['municipio'])

    # Separar nome e UF
    df_faltantes[['nome', 'uf']] = df_faltantes['municipio'].str.split(',', expand=True)

    # Remover a coluna auxiliar
    df_faltantes = df_faltantes[['nome', 'uf']]

    # Salvar os municípios faltantes no Excel
    df_faltantes.to_excel(output_excel, index=False)

    # Exibir a quantidade total de municípios faltantes
    print(f"Total de municípios faltantes: {len(df_faltantes)}")
    print(f"Arquivo gerado: {output_excel}")

# Exemplo de uso
comparar_municipios('municipios_brasil.csv', 'municipios_obtidos.txt', 'municipios_faltantes.xlsx')
