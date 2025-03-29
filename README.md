# Projeto de Coleta de Dados de Candidatos Eleitos para Prefeito - 2024

## 1. Introdução

Este código foi desenvolvido para capturar dados do site de candidaturas de prefeitos de 2024 (versão 2.4.15) (https://divulgacandcontas.tse.jus.br/divulga/#/home) e foi projetado para funcionar com a quantidade de municípios existentes no Brasil em fevereiro de 2025. O projeto tem suas origens no código base criado pelos alunos da disciplina *Computadores e Sociedade* (2024.2) na UFRJ, ministrada pelo professor Luiz Arthur, coordenador do *LabIS* (Laboratório de Informática e Sociedade).

O código inicial foi elaborado a pedido do professor Eduardo Diniz da FGV para auxiliar sua pesquisa sobre moedas sociais e bancos comunitários no estado do Rio de Janeiro. Em 2025, o professor Eduardo Diniz desejou expandir a pesquisa para abranger todo o Brasil, o que levou à adaptação do código original para abranger o território nacional. 

Esta versão aprimorada será documentada em detalhes em um relatório que será disponibilizado no repositório.

## 2. Diferenças entre o código base e a versão atual

As principais diferenças entre o código base e a versão atual é que agora o código coleta dados do Brasil todos, invés de apenas o estado do Rio de Janeito e coleta apenas os dados dos candidatos eleitos de cada município. O código original, por outro lado, coletava informações de todos os candidatos de cada município.

Além disso, a estrutura do código foi reorganizada para iterar pelas regiões, estados e municípios do Brasil, utilizando variáveis intuitivas no início do código para facilitar ajustes e adaptações futuras. Outras melhorias e novas funcionalidades foram implementadas, conforme descrito abaixo.

### Novas Funções Implementadas:

- **registrar_url(url)**  
  Registra a última URL acessada para referência futura.

- **limpar_pasta()**  
  Remove todos os arquivos PDF da pasta `./pdf/`, garantindo que a pasta esteja limpa antes de novas coletas de dados.

- **verificar_eleitos(driver)**  
  Identifica os candidatos eleitos no site e retorna apenas os dados desses candidatos.

- **formatar_trecho(trecho)**  
  Normaliza trechos de texto, removendo caracteres indesejados e ajustando a formatação para melhorar a legibilidade.

- **monitorar_comando(results, func)**  
  Permite que o usuário salve os dados manualmente ao digitar "s", garantindo a preservação das informações coletadas até o momento.

- **monitorar_url(driver, i, j, k, intervalo=1)**  
  Monitora mudanças de URL e trata automaticamente erros 504, tentando recuperar a execução do código e salvando os dados sempre que necessário.

Essas modificações tornam o código mais eficiente, confiável e adaptável para pesquisas futuras em diferentes cenários. A documentação detalhada sobre a implementação será fornecida no relatório que acompanhará o projeto.

## 3. Código Auxiliar - `Ausentes.py`

O código auxiliar, denominado **Ausentes.py**, está localizado na pasta **Municípios Ausentes**. Ele recebe um arquivo CSV com todos os municípios do Brasil disponibilizado pelo IBGE e compara com uma lista em Excel, indicando quais municípios estão ausentes.

Esse código foi crucial para identificar os municípios faltantes na coleta de dados pelo código principal. As principais razões para os municípios estarem ausentes incluem:

- **Erro de Código:** Falhas no código principal que impediram a coleta de dados para alguns municípios.
- **Candidatos sem Arquivo de Proposta:** Alguns candidatos não possuíam arquivo de proposta disponível no site, o que impediu a coleta de suas informações.
- **Nenhum Candidato Eleito:** Em alguns municípios, nenhum candidato foi eleito, o que resultou na ausência de dados a serem coletados.

O código `Ausentes.py` facilitou a identificação dessas falhas, permitindo uma análise mais detalhada e a correção dos problemas para uma coleta de dados mais precisa.

## 4. Estrutura do Código

O código está organizado de maneira modular para facilitar a manutenção e a expansão. A seguir, as principais seções do código:

- **Configuração Inicial:**  
  Variáveis e parâmetros globais são definidos para controlar a iteração através dos estados e municípios do Brasil. Isso facilita ajustes futuros em diferentes cenários, como a inclusão de novos estados ou alterações na estrutura do site.

- **Coleta de Dados:**  
  O código foi projetado para iterar por todos os municípios e coletar dados apenas dos candidatos eleitos. Isso evita sobrecarga de dados e otimiza o processo de coleta.

- **Monitoramento e Recuperação de Erros:**  
  Funções como `monitorar_url` e `monitorar_comando` garantem que o código seja robusto, capaz de lidar com erros de rede e permitir o salvamento manual dos dados.

## 5. Como Executar

### Requisitos:
- Python 3.12.9  

### Passos para Execução:
1. Clone o repositório      

2. Instale as dependências:   
    pip install -r requirements.txt

3. Execute o script:
    python coleta_dados.py

## 6. Créditos
Todas as informações do código base utilizado está no GitHub com a seguinte URL --> https://github.com/guilherme-hu/Projeto-CompSoc/tree/main.

## 7. Observações
Readme referente ao commit denominado "Dando os créditos do código base"

## 8. Licença
Este projeto é público e não possui uma licença específica.
