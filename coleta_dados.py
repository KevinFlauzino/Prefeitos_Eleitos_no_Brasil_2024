from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import os
import re
import time
import shutil
import PyPDF2
import pandas as pd
from unidecode import unidecode
from selenium.common.exceptions import StaleElementReferenceException
import threading
import difflib
from screeninfo import get_monitors

###---------------------------------------------------------------
###---------------------------------------------------------------
###---------------------------------------------------------------
inicio_time = time.strftime("%H:%M:%S")  # Captura o horário de início  

#----------------------------------------------- Setando Variáveis Auxiliares (Início)
#REGIÕES
for_norte = 7
for_nordeste = 9
for_centro = 5
for_sudeste = 4
for_sul = 3

#ESTADOS
for_acre = 22
for_amazonas = 62
for_amapa = 16
for_para = 144
for_randonia = 52
for_roraima = 15
for_tocantins = 139
estados_norte = [for_acre, for_amazonas, for_amapa, for_para, for_randonia, for_roraima, for_tocantins]

for_alagoas = 102
for_bahia = 417
for_ceara = 184
for_maranhao = 217
for_paraiba = 223
for_pernambuco = 184
for_piaui = 224
for_rio_grande_do_norte = 167
for_sergipe = 75
estados_nordeste = [for_alagoas, for_bahia, for_ceara, for_maranhao, for_paraiba, for_pernambuco, for_piaui, for_rio_grande_do_norte, for_sergipe]

for_goias = 246
for_mato_grosso_do_sul = 79
for_mato_grosso = 142
estados_centro_oeste = [for_goias, for_mato_grosso_do_sul, for_mato_grosso]


for_espiritosanto = 78
for_minasa_gerais = 853
for_rio_de_janeiro = 92
for_sao_paulo = 645
estados_sudeste = [for_espiritosanto, for_minasa_gerais, for_rio_de_janeiro, for_sao_paulo]


for_parana = 399
for_rio_grande_do_sul = 497
for_santa_catarina = 295
estados_sul = [for_parana, for_rio_grande_do_sul, for_santa_catarina]

# Lista de frases-chave
keywords = [
    "mudança climática", "alteração climática", "transformação climática",
    "adaptação climática", "ajuste climático", "resposta climática",
    "aquecimento global", "elevação da temperatura global", "mudança de temperatura",
    "crise climática", "emergência climática", "colapso climático",
    "variabilidade climática", "flutuação climática", "instabilidade climática",
    "mitigação climática", "redução de impactos climáticos", "contenção climática",
    "resiliência climática", "sustentabilidade climática", "fortalecimento climático",
    "descarbonização", "redução de emissões", "eliminação do carbono",
    "efeito estufa", "gases de efeito estufa", "aquecimento atmosférico",
    "neutralidade de carbono", "carbono neutro", "balanço de carbono zero",
    "pegada de carbono", "emissão de carbono", "impacto de carbono"
]


# Lista para armazenar os resultados
results = []

func = ""
i = 0
j = 0
k = 0

#----------------------------------------------- Definindo caminhos e pastas (Início)
# Obtém o diretório onde o script está localizado
script_dir = os.path.dirname(os.path.abspath(__file__))

# Concatena o caminho com a pasta "Resultados"
output_dir = os.path.join(script_dir, "Resultados")
#Auxiliar para corrigir erro 504 de URL
ultima_url = None
#----------------------------------------------- Definindo caminhos e pastas (Fim)
#----------------------------------------------- Setando Variáveis Auxiliares (Fim)

#----------------------------------------------- Funções (Início)
def obter_resolucao_tela(): # Pega a resolução da tela do dispositivo    
    monitor = get_monitors()[0]  # Pegando o primeiro monitor
    return monitor.width, monitor.height

def ajustar_tamanho_janela_chrome(driver):
    # Resolução da tela de 23.8" (Full HD comum)
    resolucao_238 = (1920, 1080)

    # Obter a resolução atual da tela
    resolucao_atual = obter_resolucao_tela()
    largura_atual, altura_atual = resolucao_atual
    largura_238, altura_238 = resolucao_238

    # Calcular as proporções entre a resolução atual e a de 23.8"
    escala_largura = largura_atual / largura_238
    escala_altura = altura_atual / altura_238

    # Ajustar o tamanho da janela com base na proporção
    nova_largura = int(largura_238 * escala_largura)
    nova_altura = int(altura_238 * escala_altura)

    driver.set_window_size(nova_largura, nova_altura)  # Ajusta o tamanho da janela

    return driver

def similaridade_entre_strings(str1, str2): # Calcula a similaridade entre duas strings (percentual)    
    seq = difflib.SequenceMatcher(None, str1, str2)
    return seq.ratio()  # Retorna um valor entre0 e 1

def deve_adicionar_trecho(trechos_armazenados, novo_trecho): # Comparar o novo trecho com os existentes  
    for trecho in trechos_armazenados:        
        if similaridade_entre_strings(novo_trecho, trecho) > 0.5:  # 50% de similaridade
            return False  # O trecho é similar o suficiente, não adicionar    
    return True  # O novo trecho é distinto o suficiente para ser adicionado

def registrar_url(url): #Registra a última URL acessada    
    global ultima_url
    ultima_url = url
    print(f"Última URL acessada: {ultima_url}")

def limpar_pasta(): #Remove todos os arquivos PDF dentro da pasta ./pdf/    
    pasta = os.path.join(os.getcwd(), "pdf")
    if os.path.exists(pasta):
        for arquivo in os.listdir(pasta):
            if arquivo.endswith('.pdf'):
                try:
                    os.remove(os.path.join(pasta, arquivo))
                    print(f"Arquivo {arquivo} removido com sucesso.")
                except PermissionError:
                    print(f"Erro: O arquivo {arquivo} está em uso e não pode ser removido.")
    else:
        os.makedirs(pasta)
        print(f"Pasta {pasta} criada.")

def verificar_eleitos(driver): #Indica apenas o candidato eleito, se ele existir
    candidatos = driver.find_elements(By.CSS_SELECTOR, "#basicInformationSection > div.card-body > div")
    eleitos = []  

    for index, candidato in enumerate(candidatos, start=1):  
        try:
            seletor = f"#basicInformationSection > div.card-body > div:nth-child({index}) div.centered.badge"

            div_element = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, seletor))
            )

            texto = div_element.text.strip().upper() 

            if texto == "ELEITO":
                eleitos.append(index)
        except:
            continue
          
    if eleitos:
        return eleitos
    else:
        return [100] 

import re

def formatar_trecho(trecho):
    if not isinstance(trecho, str):
        raise ValueError("O input deve ser uma string.")

    trecho_original = trecho.strip()  # Armazena o trecho original para comparação
    
    # Encontrar o primeiro '.' ou ';' e iniciar o trecho logo após ele
    match_inicio = re.search(r'[.;]\s*(.*)', trecho)
    if match_inicio:
        trecho = match_inicio.group(1).strip()

    # Encontrar a última ocorrência de '.' ou ';' e cortar o trecho até ali
    ultima_posicao = max(trecho.rfind('.'), trecho.rfind(';'))
    if ultima_posicao != -1:
        trecho = trecho[:ultima_posicao + 1]

    # Se após a formatação o trecho ficou com menos de 200 caracteres, retorna o original
    if len(trecho) < 200:
        return trecho_original.strip()

    # Agora que já ajustamos o início e o fim, podemos limpar caracteres indesejados
    trecho = re.sub(r'\s+', ' ', trecho)  # Remove espaços extras
    trecho = re.sub(r'[^a-zA-ZÀ-ÖØ-öø-ÿ0-9.,;!?()"\' ]', '', trecho)  # Remove caracteres indesejados

    return trecho.strip()

def monitorar_comando(results, func): #Aguarda o comando "s" e salva os dados atuais
    while True:
        comando = input("Digite algo: ")
        print(results)
        
        if comando.lower() == "s" or func == "s":
            print("Comando 'stop' detectado! Salvando dados")             
            excel_path = os.path.join(output_dir, "resultados.xlsx")          
            
            # Salvar os resultados em uma planilha Excel
            df = pd.DataFrame(results)
            df.to_excel(excel_path, index=False)
            
            print("\nResultados salvos com sucesso!")
            print("Arquivos serão salvos em:", output_dir)
    
        else:
            print("Comando não reconhecido, continue digitando...")

def monitorar_url(driver, i, j, k, intervalo=1): #Salva os dados atuais caso tenha alteração da URL para erro 504     
    url_atual = driver.current_url  

    while True:
        time.sleep(intervalo)  

        try:            
            url_atual = driver.current_url            
            if url_atual == 'https://divulgacandcontas.tse.jus.br/divulga/#/504':
                print("ERRO 504 - CORRIGINDO ERRO")

                i = i - 1
                j = j - 1
                k = k - 1
                
                time.sleep(2)           
                driver.get(str(ultima_url)) 
                time.sleep(2)  
                monitorar_comando(results, "s")
                print("Erro 504 Corrigido")
        except:
            print("Erro 504 não foi corrigido.")
            monitorar_comando(results, "s")
            continue  
        
        return i, j, k
             
#----------------------------------------------- Funções (Fim)  

#----------------------------------------------- AConfigurando Chrome (Início)
chrome_options = Options()
# Define o diretório de download desejado com base no local do arquivo atual
download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf")

# Cria a pasta "pdf" se não existir
if not os.path.exists(download_dir):
    os.makedirs(download_dir)

# Adiciona as preferências para configurar o download
prefs = {
    "download.default_directory": download_dir,
    "profile.default_content_settings.popups": 0,
    "download.prompt_for_download": False,
    "directory_upgrade": True,
    "safebrowsing.enabled": True
}

chrome_options.add_experimental_option("prefs", prefs)
driver = webdriver.Chrome(options=chrome_options)
driver = ajustar_tamanho_janela_chrome(driver) #Ajusta o tamanho do chrome para o tamanho da tela do dispositivo

# Inicia o monitoramento em segundo plano
thread_504 = threading.Thread(target=monitorar_url, args=(driver, i, j, k,), daemon=True)
thread_504.start()

#Monitoramento de entrada STOP
thread_stop = threading.Thread(target=monitorar_comando, args=(results, func,), daemon=True)
thread_stop.start()
    #----------------------------------------------- AConfigurando Chrome (Fim)

    #----------------------------------------------- Abrindo site (Início)
while True:    
    limpar_pasta()

    # Abrir o site
    driver.get("https://divulgacandcontas.tse.jus.br/divulga/#/home")

    # Esperar que o elemento do índice (símbolo de três traços) esteja disponível e clicar nele
    menu_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".navbar-toggler"))
    )
    menu_button.click()

    # Esperar e clicar em "Eleições"
    eleicoes_link = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.LINK_TEXT, "Eleições"))
    )
    eleicoes_link.click()

    # Clicar em "Eleições Municipais 2024"
    eleicoes_municipais_link = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "div.list-group:nth-child(1) > a:nth-child(1) > div:nth-child(1)"))
    )
    eleicoes_municipais_link.click()

    try:    # Selecionar Brasil e Região
        elemento_seletor = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".row-cols-lg-6 > div:nth-child(1)"))
        )
        elemento_seletor.click()
    except:
        try:
            time.sleep(1)
            driver.execute_script("window.scrollBy(0, 400);")  # Rolar para baixo
            time.sleep(1)            
            elemento_seletor = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".row-cols-lg-6 > div:nth-child(1)"))
            )
            elemento_seletor.click()
        except:
            print("Erro ao clicar no elemento Brasil e Região.")


    time.sleep(1)
    #----------------------------------------------- Abrindo site (Fim)

    #----------------------------------------------- Selecionando Região (Início)
    '''
    #---- Selecionar específico (Início)
    #For substituto, caso queira uma quantidade diferente
    for p in range(0, 1):
        i = 4 #3=norte, 4=nordeste, 5=centro-oeste, 6=sudeste, 7=sul
    #---- Selecionar específico (Fim)    
    '''
    for i in range(3, 7): #Inicia em 3 pois é o primeiro na lista suspensa do site "Norte" 
        #Abrir bandeja de seleção
        regiao_select = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#regiao"))
        ) 

        time.sleep(1)

        #Selecionar a Regiões
        sub_option = "option.ng-star-inserted:nth-child("+str(i)+")"        
        option = regiao_select.find_element(By.CSS_SELECTOR, sub_option)  
        option.click()   
    #----------------------------------------------- Selecionando Região (Fim)        

        #----------------------------------------------- Setando variáveis auxiliares (Início)      
        if   i == 3:
            for_reg = for_norte            
            estados_for = estados_norte                                
        elif i == 4:
            for_reg = for_nordeste            
            estados_for = estados_nordeste 
        elif i == 5:
            for_reg = for_centro            
            estados_for = estados_centro_oeste
        elif i == 6:
            for_reg = for_sudeste            
            estados_for = estados_sudeste
        elif i == 7:            
            for_reg = for_sul            
            estados_for = estados_sul

        for_start = for_reg
        for_end = (for_start*2)    
        #----------------------------------------------- Setando variáveis auxiliares (Fim)

        #----------------------------------------------- Selecionando Estado (Início)
        '''
        #---- Selecionar específico (Início)
        #For substituto, caso queira uma quantidade diferente
        for q in range(0, 1):
            j = for_start+1
        #---- Selecionar específico (Fim)
        '''
        for j in range (for_start, for_end): 
            driver.refresh()
            time.sleep(1)
            
            # Escolher o estado    
            estado = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, f"span.ng-tns-c21-"+str(j)+":nth-child(1)"))  #EX: Rio de Janeiro ###c21-$, onde $ define qual bandeja abre
            )
            estado.click()            
            #time.sleep(1)
            
            if i == 5:
                # Clicar no botão "Candidatura"
                cand_aux = j - for_start + 2 
                print("\nFOI DISTRITO FEDERAL!\n")

            else:
                # Clicar no botão "Candidatura"
                cand_aux = j - for_start + 1     

            try:
                candidatura_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "(//button[contains(., 'Candidaturas')])["+str(cand_aux)+"]"))
                )
                candidatura_button.click()
            except:
                pass  

            municipio_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, """//*[@id="codigoMunicipio"]"""))
            )
            municipio_button.click()
        #----------------------------------------------- Selecionando Estado (Fim)        
            
        #----------------------------------------------- Selecionando Município (Início)    
            # Iterar através dos municípios
            municipio_end = j-for_start 
            
            '''
            #---- Selecionar específico (Início)
            #For substituto, caso queira uma quantidade diferente
            for k in range(294, ((estados_for[municipio_end]) + 2)): #Sempre começa no 2
            #---- Selecionar específico (Fim)
            '''
            for k in range(2, ((estados_for[municipio_end]) + 2)):  # Ajustar o número de municípios conforme necessário -> 2, 94 (Ex: RJ tem 92 municípios, começamos no 2 e o range vai até 2+quantidade_municípios)
                try:
                    limpar_pasta()
                    municipio = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.XPATH,  f'//*[@id="codigoMunicipio"]/option[{k}]'))
                    )
                    municipio.click()
                except:                
                    driver.back()
                    time.sleep(1)
                    limpar_pasta()
                    municipio = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.XPATH,  f'//*[@id="codigoMunicipio"]/option[{k}]'))
                    )
                    municipio.click()

                
                #APAGAR (Início)
                time.sleep(1)
                #APAGAR (Fim)

                prefeito = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="cargo"]/option[2]'))
                )
                try:
                    prefeito.click()
                except StaleElementReferenceException:
                    prefeito = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="cargo"]/option[2]'))
                    )
                    prefeito.click()         

                pesquisar = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="basicInformationSection"]/div[3]/button[1]'))
                )
                pesquisar.click()   
        
        #----------------------------------------------- Selecionando Município (Fim) 

        #----------------------------------------------- Navegando por Candidatos (Início)     
                #Auxiliar(Inicio)
                time.sleep(1)            
                driver.execute_script("window.scrollBy(0, 1000);")  # Rolar para baixo
                time.sleep(1)                        
                #Auxiliar(Fim)
                                
                # Obtenha a lista de candidatos novamente para cada iteração
                candidatos = driver.find_elements(By.XPATH, "//*[@id='basicInformationSection']/div[2]/div[contains(@class, 'list-group ng-star-inserted')]")
            
                time.sleep(1)  
                index = verificar_eleitos(driver)
                index = index[0]    

                #Grava a URL
                registrar_url(driver.current_url)

                if index<99:
                    #---------- For apenas para clicar no candidato eleito (Início)
                    #for j in range(1, len(candidatos) + 1):  
                    try:                 
                        # Carregar a lista de candidatos novamente para evitar "stale element exception"
                        candidatos = driver.find_elements(By.XPATH, "//*[@id='basicInformationSection']/div[2]/div[contains(@class, 'list-group ng-star-inserted')]")
                        
                        #Clicando no candidato ELEITO                        
                        candidato = candidatos[(index - 1)] ####Clica no candidato ELEITO
                        driver.execute_script("arguments[0].scrollIntoView();", candidato)  # Garantir que o elemento está visível
                        candidato.click()
                    except:
                        continue
                    #---------- For apenas para clicar no candidato eleito (Fim)

                    try:
                        time.sleep(1)
                        driver.execute_script("window.scrollBy(0, 500);")  # Rolar para baixo
                        time.sleep(2)
                        # Interagir com o elemento dentro da página do candidato                    
                        proposta = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"/html/body/dvg-root/main/dvg-canditado-detalhe/div/div/div[2]/form/div/div[2]/div/div/mat-accordion/mat-expansion-panel[4]/mat-expansion-panel-header/span[1]"))
                        )   
                        time.sleep(1.5)                 
                        proposta.click() 
                    except:
                        monitorar_comando(results, "s")                   
                    
                    try:
                        #------ Baixando arquivo (Início) 
                        pdf = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, f"/html/body/dvg-root/main/dvg-canditado-detalhe/div/div/div[2]/form/div/div[2]/div/div/mat-accordion/mat-expansion-panel[4]/div/div/dvg-candidato-proposta/ol/li/div/div"))
                        )
                        pdf.click()
                        time.sleep(4)  
                        print("PDF baixado.")              
                        #------ Baixando arquivo (Fim)
                                    
                        # Verificar o PDF baixado                
                        pdf_files = [f for f in os.listdir(download_dir) if f.endswith('.pdf')]
                    
                        # Converter lista de palavras-chave para minúsculas
                        keywords_lower = [kw.lower() for kw in keywords]                        
                    
                        for pdf_file in pdf_files:                        
                            pdf_path = os.path.join(download_dir, pdf_file)  
                            print(f"PDF --> {pdf_path}")
                            
                            with open(pdf_path, 'rb') as file:
                                reader = PyPDF2.PdfReader(file)
                                num_pages = len(reader.pages)
                                text = ""
                    
                                # Extrair texto de todas as páginas do PDF
                                for page_num in range(num_pages):
                                    page = reader.pages[page_num]
                                    text += page.extract_text() or ""
                    
                                # Remover acentos, substituir 'ç' por 'c' e converter para minúsculas
                                text = unidecode(text.replace('ç', 'c')).lower()
                    
                                #----------------------- Texto Literal (Início)
                                trecho = []  # Lista para armazenar os trechos encontrados
                                encontrou_palavra_chave = False  # Flag para verificar se encontrou alguma palavra-chave
                    
                                # Procurar todas as ocorrências das palavras-chave (sem diferenciar maiúsculas/minúsculas)
                                for kw in keywords_lower:
                                    matches = list(re.finditer(rf'\b{kw}\b', text, re.IGNORECASE))  # Encontrar todas as ocorrências
                    
                                    for match in matches:
                                        encontrou_palavra_chave = True  # Marca que encontrou pelo menos uma palavra-chave
                                        # Definir trecho e quantidade de caracteres
                                        start = max(0, match.start() - 500)
                                        end = min(len(text), match.end() + 500)
                                        novo_trecho = formatar_trecho(text[start:end])                                     
                                        if deve_adicionar_trecho(trecho, novo_trecho):
                                            trecho.append(novo_trecho)
                                            print("Trecho adicionado!")
                                        else:
                                            print("Trecho similar encontrado, não será adicionado.")                                                                            
                    
                                # Adicionar os trechos encontrados apenas se houver pelo menos um, senão adicionar ""
                                trecho_literal = "".join(trecho) if encontrou_palavra_chave else ""
                                #----------------------- Texto Literal (Fim)

                                # Coletar informações do site
                                situacao = unidecode(driver.find_element(By.XPATH, "/html/body/dvg-root/main/dvg-canditado-detalhe/div/div/div[1]/dvg-candidato-header/div/div/div/div/div/div").text)
                                candidato_nome = unidecode(driver.find_element(By.XPATH, '//*[@id="basicInformationSection"]/div[2]/dvg-candidato-dados/div/div[1]/label[2]').text)
                                municipio_cargo = unidecode(driver.find_element(By.XPATH, '/html/body/dvg-root/main/dvg-canditado-detalhe/div/div/div[1]/dvg-candidato-header/div/div/div/span/label[1]').text)
                                partido = unidecode(driver.find_element(By.XPATH, '/html/body/dvg-root/main/dvg-canditado-detalhe/div/div/div[1]/dvg-candidato-header/div/div/div/span/label[2]').text)

                                # Adicionar os resultados à lista
                                results.append({
                                    "Nome do Candidato": candidato_nome,
                                    "Municipio": municipio_cargo,
                                    "Partido": partido,
                                    # "Situacao": situacao,  
                                    "Palavras-Chave": ", ".join([phrase for phrase in keywords_lower if phrase in text]),                                    
                                    "Texto Literal": trecho_literal
                                })

                                # Apagar o PDF após cada leitura
                                time.sleep(0.5)
                                print(pdf_path)                                                
                                print("Quantidade de resultados encontrados (i=", i, "):", len(results), " --> j=", j-1, "| K=", k-1)
                                time.sleep(0.5)
                                  
                                # Voltar para a página de lista de candidatos
                                driver.back()
                                time.sleep(5)  # Pausa para carregar a lista novamente  
                                print("\n-----------------------------\n")


                    except:
                        # Voltar para a página de lista de candidatos
                        driver.back()
                        time.sleep(1)  # Pausa para carregar a lista novamente
                    
                else:
                    print("\n--NENHUM CANDIDATO ELEITO--\n")
                    pass                 

            #------------------------------------------- Resetando site (Início)    
            driver.back()  #Retorna para a lista de estados 
            driver.refresh() 
            #------------------------------------------- Resetando site (Fim)      
        #----------------------------------------------- Navegando por Candidatos (Fim)   
    
    time.sleep(5)        
    # Fechar o chrome
    driver.quit()

    # Apagar e criar a pasta pdf -> limpar memoria
    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)
    os.makedirs(download_dir) 

    # Salvar os resultados em uma planilha Excel, em um arquivo CSV e em um txt
    if results: 
        
        # Certificar que o diretório existe
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Criar o caminho completo para os arquivos
        excel_path = os.path.join(output_dir, "resultados.xlsx")        
        
        # Salvar os resultados em uma planilha Excel
        df = pd.DataFrame(results)
        df.to_excel(excel_path, index=False)

    print("\nResultados salvos com sucesso!")
    print("Arquivos serão salvos em:", output_dir)

    fim_time = time.strftime("%H:%M:%S")
    print(f"\nInício: {inicio_time}  | Fim: {fim_time}\n")