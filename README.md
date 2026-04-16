# Projeto de Coleta de Dados de Candidatos Eleitos para Prefeito - 2024

## 1. Introdução

Este codigo foi desenvolvido para capturar dados do site de candidaturas de prefeitos de 2024 (versao 2.4.15) (https://divulgacandcontas.tse.jus.br/divulga/#/home) e foi projetado para funcionar com a quantidade de municipios existentes no Brasil em fevereiro de 2025. O projeto tem suas origens no codigo base criado pelos alunos da disciplina *Computadores e Sociedade* (2024.2) na UFRJ, ministrada pelo professor Luiz Arthur, coordenador do *LabIS* (Laboratorio de Informatica e Sociedade).

O codigo inicial foi elaborado a pedido do professor Eduardo Diniz da FGV para auxiliar sua pesquisa sobre moedas sociais e bancos comunitarios no estado do Rio de Janeiro. Em 2025, o professor Eduardo Diniz desejou expandir a pesquisa para abranger todo o Brasil, o que levou a adaptacao do codigo original para abranger o territorio nacional.

## 2. Diferenças entre o codigo base e a versao atual

As principais diferenças entre o codigo base e a versao atual:

- O codigo coleta dados de **todos os 5.570 municipios do Brasil**, organizados por regiao (Norte, Nordeste, Centro-Oeste, Sudeste e Sul), em vez de apenas o estado do Rio de Janeiro.
- Coleta apenas os dados dos **candidatos eleitos** de cada municipio. O codigo original coletava informacoes de todos os candidatos.
- A estrutura do codigo foi reorganizada para iterar pelas regioes, estados e municipios do Brasil, utilizando variaveis intuitivas para facilitar ajustes e adaptacoes futuras.

### Funcoes Implementadas:

- **esperar_loader(driver)** 
  Aguarda o loader do site desaparecer antes de interagir com elementos, evitando erros de clique interceptado.

- **registrar_url(url)**  
  Registra a ultima URL acessada para referencia futura.

- **limpar_pasta()**  
  Remove todos os arquivos PDF dentro da pasta `./pdf/`, garantindo que a pasta esteja limpa antes de novas coletas de dados.

- **verificar_eleitos(driver)**  
  Identifica os candidatos eleitos no site e retorna apenas os dados desses candidatos.

- **formatar_trecho(trecho)**  
  Normaliza trechos de texto, removendo caracteres indesejados e ajustando a formatacao para melhorar a legibilidade.

- **salvar_resultados(results)**  
  Salva os resultados coletados em um arquivo Excel na pasta `./Resultados/`.

- **monitorar_comando(results, func)**  
  Permite que o usuario salve os dados manualmente ao digitar "s", garantindo a preservacao das informacoes coletadas ate o momento.

- **monitorar_url(driver, i, j, k, intervalo=1)**  
  Monitora mudancas de URL e trata automaticamente erros 504, tentando recuperar a execucao do codigo e salvando os dados sempre que necessario.

## 3. Codigo Auxiliar - `Ausentes.py`

O codigo auxiliar, denominado **Ausentes.py**, esta localizado na pasta **Municipios Ausentes**. Ele recebe um arquivo CSV com todos os municipios do Brasil disponibilizado pelo IBGE e compara com uma lista em Excel, indicando quais municipios estao ausentes.

Esse codigo foi crucial para identificar os municipios faltantes na coleta de dados pelo codigo principal. As principais razoes para os municipios estarem ausentes incluem:

- **Erro de Codigo:** Falhas no codigo principal que impediram a coleta de dados para alguns municipios.
- **Candidatos sem Arquivo de Proposta:** Alguns candidatos nao possuiam arquivo de proposta disponivel no site, o que impediu a coleta de suas informacoes.
- **Nenhum Candidato Eleito:** Em alguns municipios, nenhum candidato foi eleito, o que resultou na ausencia de dados a serem coletados.

## 4. Estrutura do Projeto

```
Prefeitos_Eleitos_no_Brasil_2024/
├── coleta_dados.py              # Script principal de web scraping
├── requirements.txt             # Dependencias do projeto
├── CITATION.cff                 # Arquivo de citacao academica
├── README.md                    # Este arquivo
├── .gitignore                   # Arquivos ignorados pelo Git
├── Municipios Ausentes/         # Codigo auxiliar
│   ├── Ausentes.py              # Script que identifica municipios faltantes
│   ├── municipios_brasil.csv    # Lista completa de municipios (IBGE)
│   ├── municipios_faltantes.xlsx# Resultado: municipios ausentes
│   └── municipios_obtidos.txt   # Lista de municipios ja coletados
├── pdf/                         # (criada automaticamente) PDFs baixados temporariamente
└── Resultados/                  # (criada automaticamente) Planilhas com resultados
```

## 5. Como Executar

### Requisitos:
- Python 3.12+
- Google Chrome instalado

### Passos para Execucao:
1. Clone o repositorio:
   ```bash
   git clone https://github.com/KevinFlauzino/Prefeitos_Eleitos_no_Brasil_2024.git
   cd Prefeitos_Eleitos_no_Brasil_2024
   ```

2. Instale as dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Execute o script:
   ```bash
   python coleta_dados.py
   ```

4. Os resultados serao salvos automaticamente na pasta `./Resultados/` em formato Excel.

**Nota:** Durante a execucao, voce pode digitar "s" no terminal para salvar os resultados coletados ate o momento.

## 6. Creditos
Todas as informacoes do codigo base utilizado esta no GitHub com a seguinte URL --> https://github.com/guilherme-hu/Projeto-CompSoc/tree/main.

## 7. Licenca
Este projeto e publico e nao possui uma licenca especifica.
