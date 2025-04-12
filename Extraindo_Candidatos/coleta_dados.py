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
import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread
from tkinter import Tk, Label, Button, Entry, Checkbutton, IntVar, BooleanVar, StringVar, ttk


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
for_rondonia = 52
for_roraima = 15
for_tocantins = 139
estados_norte = [for_acre, for_amazonas, for_amapa, for_para, for_rondonia, for_roraima, for_tocantins]

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

estados = {
    "AC": for_acre, "AL": for_alagoas, "AM": for_amazonas, "AP": for_amapa,
    "BA": for_bahia, "CE": for_ceara, "DF": 1, "ES": for_espiritosanto,
    "GO": for_goias, "MA": for_maranhao, "MG": for_minasa_gerais, "MS": for_mato_grosso_do_sul,
    "MT": for_mato_grosso, "PA": for_para, "PB": for_paraiba, "PE": for_pernambuco,
    "PI": for_piaui, "PR": for_parana, "RJ": for_rio_de_janeiro, "RN": for_rio_grande_do_norte,
    "RO": for_rondonia, "RR": for_roraima, "RS": for_rio_grande_do_sul,
    "SC": for_santa_catarina, "SE": for_sergipe, "SP": for_sao_paulo, "TO": for_tocantins
}


# Lista para armazenar os resultados
results = []

func = ""
i = 0
j = 0
k = 0

# Lista de palavras-chave em minúsculo
keywords_lower = [k.lower() for k in keywords]
#----------------------------------------------- Definindo caminhos e pastas (Início)
# Obtém o diretório onde o script está localizado
dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))

# Concatena o caminho com a pasta "Resultados"
output_dir = os.path.join(dir, "Resultados")

# Concatena o caminho com a pasta "Pds_downloads"
download_dir = os.path.join(dir, "pdf_downloads")

#Auxiliar para corrigir erro 504 de URL
ultima_url = None
#----------------------------------------------- Definindo caminhos e pastas (Fim)
#----------------------------------------------- Setando Variáveis Auxiliares (Fim)

#----------------------------------------------- Funções (Início)
def exibir_tempo_execucao(inicio_time):
    fim_time = time.strftime("%H:%M:%S")
    print(f"\nInício: {inicio_time}  | Fim: {fim_time}\n")

def salvar_resultados(results, output_dir):
    if results:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        excel_path = os.path.join(output_dir, "resultados.xlsx")
        df = pd.DataFrame(results)
        df.to_excel(excel_path, index=False)

        print("\nResultados salvos com sucesso!")
        print("Arquivos serão salvos em:", output_dir)
    else:
        print("\nNenhum resultado para salvar.")

def finalizar_driver(driver, download_dir):
    time.sleep(5)
    driver.quit()

    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)
    os.makedirs(download_dir)

def acessar_proposta(driver):
    try:
        time.sleep(1)
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(1)

        proposta_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="mat-expansion-panel-header-11"]/span[1]'))
        )

        # Confirma se o texto do botão é "Propostas"
        if "Propostas" in proposta_btn.text:
            time.sleep(1)
            proposta_btn.click()        

    except Exception as e:
        print("Candidato sem propostas.")
        
def clicar_candidato_eleito(driver):
    time.sleep(1)
    driver.execute_script("window.scrollBy(0, 1000);")
    time.sleep(1)
    candidatos = driver.find_elements(By.XPATH, "//*[@id='basicInformationSection']/div[2]/div[contains(@class, 'list-group ng-star-inserted')]")
    time.sleep(1)
    
    index = verificar_eleitos(driver)[0]
    registrar_url(driver.current_url)
    
    if index < 99:
        try:
            candidatos = driver.find_elements(By.XPATH, "//*[@id='basicInformationSection']/div[2]/div[contains(@class, 'list-group ng-star-inserted')]")
            candidato = candidatos[(index - 1)]
            driver.execute_script("arguments[0].scrollIntoView();", candidato)
            candidato.click()
        except:
            return False
    return True

def pesquisar_prefeito(driver):
    prefeito = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="cargo"]/option[2]')))
    try:
        prefeito.click()
    except StaleElementReferenceException:
        prefeito = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="cargo"]/option[2]')))
        prefeito.click()

    pesquisar = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="basicInformationSection"]/div[3]/button[1]')))
    pesquisar.click()

def selecionar_municipio(driver, k):
    limpar_pasta()
    try:
        municipio = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, f'//*[@id="codigoMunicipio"]/option[{k}]')))
        municipio.click()
    except:
        driver.back()
        time.sleep(1)
        limpar_pasta()
        municipio = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, f'//*[@id="codigoMunicipio"]/option[{k}]')))
        municipio.click()

def clicar_candidatura(driver, i, j, for_start):
    if i == 5:
        print("\nFOI DISTRITO FEDERAL!\n")
        cand_aux = j - for_start + 2
    else:
        cand_aux = j - for_start + 1

    try:
        botao = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, f"(//button[contains(., 'Candidaturas')])[{cand_aux}]")))
        botao.click()
    except:
        pass

def selecionar_estado(driver, j):
    driver.refresh()
    time.sleep(1)
    estado = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"span.ng-tns-c21-{j}:nth-child(1)")))
    estado.click()

def obter_dados_regiao(i):
    if i == 3:
        return for_norte, estados_norte
    elif i == 4:
        return for_nordeste, estados_nordeste
    elif i == 5:
        return for_centro, estados_centro_oeste
    elif i == 6:
        return for_sudeste, estados_sudeste
    elif i == 7:
        return for_sul, estados_sul

def selecionar_regiao(driver, i):
    regiao_select = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#regiao")))
    time.sleep(1)
    option = regiao_select.find_element(By.CSS_SELECTOR, f"option.ng-star-inserted:nth-child({i})")
    option.click()

def abrir_site(driver): # Abre o site
    driver.get("https://divulgacandcontas.tse.jus.br/divulga/#/home")

    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".navbar-toggler"))).click()
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.LINK_TEXT, "Eleições"))).click()
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.list-group:nth-child(1) > a:nth-child(1) > div:nth-child(1)"))).click()

    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".row-cols-lg-6 > div:nth-child(1)"))).click()
    except:
        driver.execute_script("window.scrollBy(0, 400);")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".row-cols-lg-6 > div:nth-child(1)"))).click()

def configurar_chrome(download_dir="pdf_downloads"):
    chrome_options = Options()
    
    # Caminho do diretório de download
    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,  # Permite o download automático
        "safebrowsing.disable_download_protection": True  # Desativa o bloqueio de arquivos "suspeitos"
    }

    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    # Adiciona o zoom de 75%
    chrome_options.add_argument("--force-device-scale-factor=0.75")

    driver = webdriver.Chrome(options=chrome_options)
    driver = ajustar_tamanho_janela_chrome(driver)
    return driver

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
    pasta = os.path.join(os.getcwd(), "pdf_downloads")
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

def obter_nome_candidato(driver):
    try:
        elemento = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="basicInformationSection"]/div[2]/dvg-candidato-dados/div/div[1]/label[2]'))
        )
        return unidecode(elemento.text)
    except Exception as e:
        print(f"Erro ao obter nome do candidato: {e}")
        return "Nome não encontrado"

def obter_municipio_cargo(driver):
    try:
        elemento = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '/html/body/dvg-root/main/dvg-canditado-detalhe/div/div/div[1]/dvg-candidato-header/div/div/div/span/label[1]'))
        )
        return unidecode(elemento.text)
    except Exception as e:
        print(f"Erro ao obter município/cargo: {e}")
        return "Município/Cargo não encontrado"

def obter_partido(driver):
    try:
        elemento = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '/html/body/dvg-root/main/dvg-canditado-detalhe/div/div/div[1]/dvg-candidato-header/div/div/div/span/label[2]'))
        )
        return unidecode(elemento.text)
    except Exception as e:
        print(f"Erro ao obter partido: {e}")
        return "Partido não encontrado"
    
def toggle_municipios():
    if varrer_todos_var.get():
        inicio_entry.config(state="disabled")
        fim_entry.config(state="disabled")
    else:
        inicio_entry.config(state="normal")
        fim_entry.config(state="normal")

def atualizar_progresso(atual, total):
    progresso["maximum"] = total
    progresso["value"] = atual
    status_label.config(text=f"{atual} de {total} candidatos varridos")

def iniciar():
    # Obter o intervalo de varreduras antes de salvar
    intervalo_varredura = varreduras_intervalo_var.get()

    # Obter os outros dados necessários da interface
    estados_selecionados = {e: v.get() for e, v in estado_vars.items()}
    inicio = inicio_var.get()
    fim = fim_var.get()
    salvar = salvar_auto_var.get()

    if not any(estados_selecionados.values()):
        messagebox.showwarning("Seleção de estados", "Selecione pelo menos um estado.")
        return

    # Passar o intervalo de varreduras para a função main
    main(estados_selecionados, inicio, fim, salvar, intervalo_varredura)


def extrair_proposta_pdf(driver, download_dir, keywords_lower):
    try:
        # Tentar clicar no botão do PDF
        botao_pdf = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "/html/body/dvg-root/main/dvg-canditado-detalhe/div/div/div[2]/form/div/div[2]/div/div/mat-accordion/mat-expansion-panel[4]/div/div/dvg-candidato-proposta/ol/li/div/div"
            ))
        )
        botao_pdf.click()
    except Exception as e:
        print("❌ Erro ao clicar no botão do PDF:", e)
        return None   
    
    # Acessar PDF baixado    
    time.sleep(5)   
    pdf_files = [f for f in os.listdir(download_dir) if f.endswith(".pdf")]    
    if not pdf_files:
        print("❌ Nenhum arquivo PDF encontrado na pasta de download.")
        return None

    pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), reverse=True)
    pdf_path = os.path.join(download_dir, pdf_files[0])

    # Ler e extrair o texto do PDF
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
    except Exception as e:
        print("❌ Erro ao ler o PDF:", e)
        return None

    # Se não extraiu nada, talvez o PDF seja só imagem
    if not text.strip():
        print("⚠️ PDF sem texto extraível.")
        return "Proposta não contém texto acessível (pode ser imagem escaneada)."

    # Limpar e tratar o texto
    text = unidecode(text.replace("ç", "c")).lower()

    # Procurar palavras-chave
    encontrou_palavra_chave = False
    trechos = []

    for kw in keywords_lower:
        matches = list(re.finditer(rf'\b{kw}\b', text, re.IGNORECASE))
        for match in matches:
            encontrou_palavra_chave = True
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            novo_trecho = formatar_trecho(text[start:end])
            if deve_adicionar_trecho(trechos, novo_trecho):
                trechos.append(novo_trecho)

    # Apagar o PDF depois de processar
    os.remove(pdf_path)

    if encontrou_palavra_chave:
        return "".join(trechos)
    else:
        return ""

def main(estados_selecionados, inicio, fim, salvar, intervalo_varredura):
    driver = configurar_chrome()
    abrir_site(driver)

    contador_candidatos = 0  # Contador de candidatos varridos
    results = []
    total_candidatos = (fim - inicio + 1) * len(estados_selecionados)  # Estimativa de candidatos para mostrar progresso
    progresso_atual = 0

    for i, estado_selecionado in enumerate(estados_selecionados):
        if not estado_selecionado:
            continue  # Pular estados não selecionados

        selecionar_regiao(driver, i)  # Seleciona a região com base no índice

        for_reg, estados_for = obter_dados_regiao(i)

        for j in range(for_reg, for_reg * 2):
            if j < inicio or j > fim:
                continue  # Ignorar municípios fora do intervalo configurado

            selecionar_estado(driver, j)
            clicar_candidatura(driver, i, j, for_reg)

            for k in range(2, estados_for[j - for_reg] + 2):
                selecionar_municipio(driver, k)
                pesquisar_prefeito(driver)

                if clicar_candidato_eleito(driver):
                    # Extrair informações antes de acessar proposta
                    candidato_nome = obter_nome_candidato(driver)
                    municipio_cargo = obter_municipio_cargo(driver)
                    partido = obter_partido(driver)

                    # Tenta acessar a proposta
                    acessar_proposta(driver)

                    # Tenta extrair a proposta via PDF
                    proposta = extrair_proposta_pdf(driver, download_dir, keywords_lower)

                    if proposta:
                        trecho_literal = proposta
                        palavras_chave = ", ".join([kw for kw in keywords_lower if kw in proposta.lower()])
                    else:                        
                        trecho_literal = ""
                        palavras_chave = ""

                    results.append({
                        "Nome do Candidato": candidato_nome,
                        "Municipio": municipio_cargo,
                        "Partido": partido,
                        "Palavras-Chave": palavras_chave,
                        "Texto Literal": trecho_literal
                    })

                    contador_candidatos += 1
                    progresso_atual += 1
                    atualizar_progresso(progresso_atual, total_candidatos)

                    print("\n---------------------")
                    print(f"Último candidato ---> Região={i-2}/5, Estados={j-for_reg+1}, Municípios={k-1}")
                    print(f"Contador de candidatos: {contador_candidatos}")
                    print("---------------------")

                    # Salvar a cada X candidatos, conforme intervalo configurado
                    if salvar and contador_candidatos % intervalo_varredura == 0:
                        salvar_resultados(results, output_dir)

    # Salvar resultados ao final
    salvar_resultados(results, output_dir)
    finalizar_driver(driver, download_dir)
    exibir_tempo_execucao(inicio_time)
#----------------------------------------------- Funções (Fim) 

# Criar janela principal
janela = tk.Tk()
janela.title("Varredura de Prefeitos 2024")
janela.geometry("700x500")

# Título
titulo = tk.Label(janela, text="Varredura de Prefeitos Eleitos - 2024", font=("Arial", 16))
titulo.pack(pady=10)

# Frame principal
frame = tk.Frame(janela)
frame.pack()

# Frame dos estados com scroll
frame_estados = tk.LabelFrame(frame, text="Estados para varredura", padx=10, pady=10)
frame_estados.grid(row=0, column=0, padx=10, pady=10)

canvas = tk.Canvas(frame_estados, width=200, height=200)
scrollbar = tk.Scrollbar(frame_estados, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

estado_vars = {}
for estado in estados:
    var = BooleanVar()
    tk.Checkbutton(scrollable_frame, text=estado, variable=var).pack(anchor="w")
    estado_vars[estado] = var

canvas.pack(side="left")
scrollbar.pack(side="right", fill="y")

# Frame para controle de municípios
frame_municipios = tk.LabelFrame(frame, text="Intervalo de municípios", padx=10, pady=10)
frame_municipios.grid(row=0, column=1, padx=10, pady=10, sticky="n")

inicio_label = tk.Label(frame_municipios, text="Início:")
inicio_label.grid(row=0, column=0)
inicio_var = IntVar(value=1)
inicio_entry = tk.Entry(frame_municipios, textvariable=inicio_var, width=5)
inicio_entry.grid(row=0, column=1)

fim_label = tk.Label(frame_municipios, text="Fim:")
fim_label.grid(row=1, column=0)
fim_var = IntVar(value=10)
fim_entry = tk.Entry(frame_municipios, textvariable=fim_var, width=5)
fim_entry.grid(row=1, column=1)

# Checkbox para "Varrer todos os municípios"
varrer_todos_var = BooleanVar()
varrer_todos_check = tk.Checkbutton(frame_municipios, text="Varrer todos os municípios", variable=varrer_todos_var, command=toggle_municipios)
varrer_todos_check.grid(row=2, column=0, columnspan=2, pady=5)

# Checkbox para salvamento automático
salvar_auto_var = BooleanVar(value=True)
check_salvar = tk.Checkbutton(frame_municipios, text="Salvar automaticamente", variable=salvar_auto_var)
check_salvar.grid(row=3, column=0, columnspan=2, pady=10)

# Novo campo para definir a quantidade de varreduras antes de salvar o arquivo
varreduras_label = tk.Label(frame_municipios, text="De quantos em quantos candidatos varridos salvar o arquivo:")
varreduras_label.grid(row=4, column=0, columnspan=2, pady=5)

varreduras_intervalo_var = IntVar(value=5)  # Valor inicial do intervalo (pode ser ajustado)
varreduras_intervalo_entry = tk.Entry(frame_municipios, textvariable=varreduras_intervalo_var, width=5)
varreduras_intervalo_entry.grid(row=5, column=0, columnspan=2, pady=5)

# Barra de progresso
progresso = ttk.Progressbar(janela, orient="horizontal", length=600, mode="determinate")
progresso.pack(pady=20)

status_label = tk.Label(janela, text="Aguardando início da varredura...")
status_label.pack()

# Botão iniciar
botao_iniciar = tk.Button(janela, text="Iniciar Varredura", bg="green", fg="white", width=20, command=iniciar)
botao_iniciar.pack(pady=5)

# Botão sair
botao_sair = tk.Button(janela, text="Sair", command=janela.quit, bg="red", fg="white", width=20)
botao_sair.pack(pady=5)

# Iniciar GUI
janela.mainloop()
