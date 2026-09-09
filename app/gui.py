"""
Mapeador de Politicas Publicas - Prefeitos Eleitos 2024

Interface grafica para pesquisar mencoes a moedas sociais, renda basica e
economia solidaria nos planos de governo dos prefeitos eleitos em 2024.

Permite escolher livremente as palavras-chave, recortar por regiao e estado,
ler os trechos literais encontrados, abrir o plano original e exportar os
resultados para Excel ou CSV.

Uso:
    python app/gui.py
"""

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import busca      # noqa: E402
import exportar   # noqa: E402

RAIZ = busca.raiz_do_aplicativo()

# Grupo de termos marcado quando a aba de pesquisa abre. Se o nome nao existir
# mais em busca.GRUPOS_PADRAO, cai para o primeiro grupo disponivel, para a aba
# nunca abrir sem termo nenhum.
GRUPO_INICIAL = ("Moeda social e municipal"
                 if "Moeda social e municipal" in busca.GRUPOS_PADRAO
                 else next(iter(busca.GRUPOS_PADRAO), ""))

COR_FUNDO = "#f4f6f8"
COR_PAINEL = "#ffffff"
COR_DESTAQUE = "#1f4e79"
COR_TEXTO_FRACO = "#5a6772"


class Aplicacao(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mapeador de Politicas Publicas - Prefeitos Eleitos 2024")
        self.geometry("1280x780")
        self.minsize(1050, 640)
        self.configure(bg=COR_FUNDO)

        self.con = None
        self.resultados = []
        self.pesquisando = False

        self._configurar_estilo()
        self._montar_cabecalho()
        self._montar_abas()
        self._montar_rodape()

        self.after(100, self.conectar_banco)

    # ------------------------------------------------------------------ estilo
    def _configurar_estilo(self):
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("TFrame", background=COR_FUNDO)
        estilo.configure("Painel.TFrame", background=COR_PAINEL, relief="flat")
        estilo.configure("TLabel", background=COR_FUNDO, font=("Segoe UI", 10))
        estilo.configure("Painel.TLabel", background=COR_PAINEL, font=("Segoe UI", 10))
        estilo.configure("Titulo.TLabel", background=COR_FUNDO,
                         font=("Segoe UI Semibold", 15), foreground=COR_DESTAQUE)
        estilo.configure("Sub.TLabel", background=COR_FUNDO,
                         font=("Segoe UI", 9), foreground=COR_TEXTO_FRACO)
        estilo.configure("Numero.TLabel", background=COR_PAINEL,
                         font=("Segoe UI Semibold", 20), foreground=COR_DESTAQUE)
        estilo.configure("Rotulo.TLabel", background=COR_PAINEL,
                         font=("Segoe UI", 9), foreground=COR_TEXTO_FRACO)
        estilo.configure("TButton", font=("Segoe UI", 10), padding=6)
        estilo.configure("Acao.TButton", font=("Segoe UI Semibold", 10), padding=8)
        estilo.configure("TNotebook", background=COR_FUNDO)
        estilo.configure("TNotebook.Tab", font=("Segoe UI", 10), padding=(16, 8))
        estilo.configure("Treeview", font=("Segoe UI", 9), rowheight=24)
        estilo.configure("Treeview.Heading", font=("Segoe UI Semibold", 9))

    def _montar_cabecalho(self):
        topo = ttk.Frame(self, padding=(16, 12, 16, 4))
        topo.pack(fill="x")
        ttk.Label(topo, text="Mapeador de Politicas Publicas Municipais",
                  style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(topo, text="Planos de governo dos prefeitos eleitos em 2024  ·  "
                             "PIBIC FGV EAESP  ·  moedas sociais, renda basica e economia solidaria",
                  style="Sub.TLabel").pack(anchor="w")

    def _montar_abas(self):
        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="both", expand=True, padx=16, pady=10)
        self.aba_painel = ttk.Frame(self.abas, padding=14)
        self.aba_pesquisa = ttk.Frame(self.abas, padding=14)
        self.aba_municipio = ttk.Frame(self.abas, padding=14)
        self.aba_sem_proposta = ttk.Frame(self.abas, padding=14)
        self.aba_ajuda = ttk.Frame(self.abas, padding=14)
        self.aba_sobre = ttk.Frame(self.abas, padding=14)
        self.abas.add(self.aba_painel, text="  Visao geral  ")
        self.abas.add(self.aba_pesquisa, text="  Pesquisa por palavras-chave  ")
        self.abas.add(self.aba_municipio, text="  Consultar municipio  ")
        self.abas.add(self.aba_sem_proposta, text="  Sem proposta  ")
        self.abas.add(self.aba_ajuda, text="  Como usar  ")
        self.abas.add(self.aba_sobre, text="  Sobre o app  ")
        self._montar_aba_painel()
        self._montar_aba_pesquisa()
        self._montar_aba_municipio()
        self._montar_aba_sem_proposta()
        self._montar_aba_ajuda()
        self._montar_aba_sobre()

    def _montar_rodape(self):
        rodape = ttk.Frame(self, padding=(16, 0, 16, 10))
        rodape.pack(fill="x")
        self.rotulo_status = ttk.Label(rodape, text="Iniciando...", style="Sub.TLabel")
        self.rotulo_status.pack(side="left")
        self.progresso = ttk.Progressbar(rodape, mode="indeterminate", length=180)

    def status(self, mensagem):
        self.rotulo_status.config(text=mensagem)
        self.update_idletasks()

    # ------------------------------------------------------------------ painel
    def _montar_aba_painel(self):
        quadro = ttk.Frame(self.aba_painel)
        quadro.pack(fill="x")
        self.cartoes = {}
        for chave, titulo in [
            ("total", "Municipios no banco"),
            ("COM_PROPOSTA", "Com plano de governo"),
            ("ilegiveis", "Planos escaneados (sem texto)"),
            ("SEM_PROPOSTA", "Eleito sem plano"),
            ("SEM_ELEITO", "Sem candidato eleito"),
            ("cobertura", "Cobertura"),
        ]:
            cartao = ttk.Frame(quadro, style="Painel.TFrame", padding=14)
            cartao.pack(side="left", fill="both", expand=True, padx=(0, 10))
            valor = ttk.Label(cartao, text="--", style="Numero.TLabel")
            valor.pack(anchor="w")
            ttk.Label(cartao, text=titulo, style="Rotulo.TLabel").pack(anchor="w")
            self.cartoes[chave] = valor

        acoes = ttk.Frame(self.aba_painel)
        acoes.pack(fill="x", pady=(14, 0))
        ttk.Button(acoes, text="Atualizar numeros",
                   command=self.conectar_banco).pack(side="left")

        caixa = ttk.Frame(self.aba_painel, style="Painel.TFrame", padding=16)
        caixa.pack(fill="both", expand=True, pady=(12, 0))
        ttk.Label(caixa, text="O que este banco cobre", style="Painel.TLabel",
                  font=("Segoe UI Semibold", 12)).pack(anchor="w")
        self.rotulo_resumo = tk.Label(
            caixa, text="", justify="left", anchor="w", background=COR_PAINEL,
            font=("Segoe UI", 10), foreground="#333c44")
        self.rotulo_resumo.pack(anchor="w", pady=(10, 0), fill="x")

        ttk.Label(caixa, text="Por onde comecar", style="Painel.TLabel",
                  font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(18, 0))
        atalho = tk.Label(
            caixa, justify="left", anchor="w", background=COR_PAINEL,
            font=("Segoe UI", 10), foreground="#333c44",
            text=("1.  Abra a aba 'Pesquisa por palavras-chave'.\n"
                  "2.  Marque um grupo de termos pronto ou digite os seus.\n"
                  "3.  Clique em 'Pesquisar' e depois em qualquer municipio\n"
                  "     da tabela para ler os trechos literais do plano.\n\n"
                  "O passo a passo completo, com exemplos de cada recurso,\n"
                  "esta na aba 'Como usar'."))
        atalho.pack(anchor="w", pady=(10, 0))

    # ---------------------------------------------------------------- pesquisa
    def _montar_aba_pesquisa(self):
        painel = ttk.Frame(self.aba_pesquisa)
        painel.pack(fill="x")

        # --- grupos prontos
        caixa_grupos = ttk.LabelFrame(painel, text=" Grupos de termos ", padding=10)
        caixa_grupos.pack(side="left", fill="y")
        self.grupos = {}
        for nome in busca.GRUPOS_PADRAO:
            # Marcado por padrao o grupo central da pesquisa. Comparar com uma
            # constante evita que renomear um grupo deixe a aba abrindo vazia.
            variavel = tk.BooleanVar(value=(nome == GRUPO_INICIAL))
            ttk.Checkbutton(caixa_grupos, text=nome, variable=variavel,
                            command=self._sincronizar_termos).pack(anchor="w", pady=2)
            self.grupos[nome] = variavel

        # --- termos livres
        caixa_termos = ttk.LabelFrame(painel, text=" Termos (um por linha) ", padding=10)
        caixa_termos.pack(side="left", fill="both", expand=True, padx=10)
        self.campo_termos = tk.Text(caixa_termos, height=8, width=40,
                                    font=("Consolas", 9), wrap="none")
        self.campo_termos.pack(fill="both", expand=True)

        # --- filtros
        caixa_filtros = ttk.LabelFrame(painel, text=" Recorte territorial ", padding=10)
        caixa_filtros.pack(side="left", fill="y")

        ttk.Label(caixa_filtros, text="Regiao").grid(row=0, column=0, sticky="w")
        self.lista_regioes = tk.Listbox(caixa_filtros, selectmode="multiple",
                                        height=6, exportselection=False,
                                        font=("Segoe UI", 9))
        self.lista_regioes.grid(row=1, column=0, padx=(0, 10), sticky="ns")

        ttk.Label(caixa_filtros, text="Estado (UF)").grid(row=0, column=1, sticky="w")
        self.lista_ufs = tk.Listbox(caixa_filtros, selectmode="multiple",
                                    height=6, exportselection=False,
                                    font=("Segoe UI", 9))
        self.lista_ufs.grid(row=1, column=1, sticky="ns")

        self.exigir_todos = tk.BooleanVar(value=False)
        ttk.Checkbutton(caixa_filtros, text="Exigir todos os termos",
                        variable=self.exigir_todos).grid(row=2, column=0, columnspan=2,
                                                         sticky="w", pady=(8, 0))
        ttk.Button(caixa_filtros, text="Limpar filtros",
                   command=self._limpar_filtros).grid(row=3, column=0, columnspan=2,
                                                      sticky="ew", pady=(6, 0))

        # --- botoes
        barra = ttk.Frame(self.aba_pesquisa)
        barra.pack(fill="x", pady=10)
        self.barra_botoes = barra
        self.botao_pesquisar = ttk.Button(barra, text="Pesquisar", style="Acao.TButton",
                                          command=self.pesquisar)
        self.botao_pesquisar.pack(side="left")
        ttk.Button(barra, text="Exportar resultados",
                   command=self.exportar).pack(side="left", padx=8)
        ttk.Button(barra, text="Abrir plano original",
                   command=self.abrir_pdf).pack(side="left")
        self.rotulo_achados = ttk.Label(barra, text="", style="Sub.TLabel")
        self.rotulo_achados.pack(side="right")

        # Aviso permanente: parte dos planos e imagem escaneada e nao pode ser
        # pesquisada por texto. Sem isso, o usuario leria ausencia de mencao
        # onde na verdade ha um documento ilegivel.
        self.rotulo_alerta = tk.Label(self.aba_pesquisa, text="", anchor="w",
                                      font=("Segoe UI", 9), background="#fff4ce",
                                      foreground="#6b5300", padx=10, pady=6)

        # --- resultados + trechos
        divisor = ttk.PanedWindow(self.aba_pesquisa, orient="vertical")
        divisor.pack(fill="both", expand=True)

        quadro_tabela = ttk.Frame(divisor)
        colunas = ("municipio", "uf", "regiao", "candidato", "termos", "ocorrencias")
        titulos = {"municipio": "Municipio", "uf": "UF", "regiao": "Regiao",
                   "candidato": "Prefeito eleito", "termos": "Termos encontrados",
                   "ocorrencias": "Mencoes"}
        larguras = {"municipio": 190, "uf": 45, "regiao": 105, "candidato": 240,
                    "termos": 330, "ocorrencias": 75}
        self.tabela = ttk.Treeview(quadro_tabela, columns=colunas, show="headings")
        for coluna in colunas:
            self.tabela.heading(coluna, text=titulos[coluna],
                                command=lambda c=coluna: self._ordenar(c))
            self.tabela.column(coluna, width=larguras[coluna],
                               anchor="center" if coluna in ("uf", "ocorrencias") else "w")
        barra_v = ttk.Scrollbar(quadro_tabela, orient="vertical",
                                command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=barra_v.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        barra_v.pack(side="right", fill="y")
        self.tabela.bind("<<TreeviewSelect>>", self._mostrar_trechos)
        divisor.add(quadro_tabela, weight=3)

        quadro_trechos = ttk.LabelFrame(divisor, text=" Trechos literais do plano de governo ",
                                        padding=8)
        self.campo_trechos = tk.Text(quadro_trechos, height=9, wrap="word",
                                     font=("Segoe UI", 10), background="#fffdf5")
        barra_t = ttk.Scrollbar(quadro_trechos, orient="vertical",
                                command=self.campo_trechos.yview)
        self.campo_trechos.configure(yscrollcommand=barra_t.set, state="disabled")
        self.campo_trechos.pack(side="left", fill="both", expand=True)
        barra_t.pack(side="right", fill="y")
        divisor.add(quadro_trechos, weight=2)

        self._sincronizar_termos()

    def _sincronizar_termos(self):
        """Preenche o campo de termos com os grupos marcados."""
        termos = []
        for nome, variavel in self.grupos.items():
            if variavel.get():
                termos += busca.GRUPOS_PADRAO[nome]
        self.campo_termos.delete("1.0", "end")
        self.campo_termos.insert("1.0", "\n".join(termos))

    def _limpar_filtros(self):
        self.lista_regioes.selection_clear(0, "end")
        self.lista_ufs.selection_clear(0, "end")
        self.exigir_todos.set(False)

    def _selecionados(self, lista):
        return [lista.get(i) for i in lista.curselection()]

    def _ordenar(self, coluna):
        if not self.resultados:
            return
        numerica = coluna == "ocorrencias"
        self.resultados.sort(key=lambda r: r[coluna], reverse=numerica)
        self._preencher_tabela()

    def pesquisar(self):
        if self.pesquisando:
            return
        if not self.con:
            messagebox.showwarning("Banco indisponivel",
                                   "O banco de dados ainda nao foi criado.\n"
                                   "Use 'Reconstruir banco a partir dos PDFs'.")
            return
        termos = [t.strip() for t in
                  self.campo_termos.get("1.0", "end").splitlines() if t.strip()]
        if not termos:
            messagebox.showinfo("Sem termos",
                                "Informe ao menos um termo ou marque um grupo.")
            return

        self.pesquisando = True
        self.botao_pesquisar.config(state="disabled")
        self.progresso.pack(side="right")
        self.progresso.start(12)
        self.status("Pesquisando nos planos de governo...")

        regioes = self._selecionados(self.lista_regioes)
        ufs = self._selecionados(self.lista_ufs)
        exigir = self.exigir_todos.get()

        self.termos_da_busca = termos

        def tarefa():
            try:
                con = busca.conectar()
                # Sem trechos: eles sao calculados so para a linha selecionada.
                achados = busca.pesquisar(con, termos, regioes=regioes, ufs=ufs,
                                          exigir_todos=exigir, com_trechos=False)
                ilegiveis = busca.contar_ilegiveis(con, regioes=regioes, ufs=ufs)
                con.close()
                self.after(0, lambda: self._concluir_pesquisa(
                    achados, len(termos), ilegiveis))
            except Exception as falha:
                # A variavel do 'except' e apagada ao fim do bloco; sem esta
                # copia a lambda quebraria com NameError e a interface ficaria
                # travada, sem nunca mostrar o erro.
                erro = falha
                self.after(0, lambda: self._falhar_pesquisa(erro))

        threading.Thread(target=tarefa, daemon=True).start()

    def _concluir_pesquisa(self, achados, quantidade_termos, ilegiveis=0):
        self.resultados = achados
        self._preencher_tabela()
        self.progresso.stop()
        self.progresso.pack_forget()
        self.botao_pesquisar.config(state="normal")
        self.pesquisando = False
        total_mencoes = sum(r["ocorrencias"] for r in achados)
        self.rotulo_achados.config(
            text=f"{len(achados)} municipios  ·  {total_mencoes} mencoes")

        if ilegiveis:
            self.rotulo_alerta.config(
                text=f"Atencao: {ilegiveis} planos deste recorte sao PDFs "
                     f"escaneados (imagem) e nao entram na busca por texto. "
                     f"O resultado acima e um piso, nao o total.")
            self.rotulo_alerta.pack(fill="x", pady=(0, 8), after=self.barra_botoes)
        else:
            self.rotulo_alerta.pack_forget()

        self.status(f"Busca concluida: {len(achados)} municipios citam "
                    f"ao menos um de {quantidade_termos} termos.")

    def _falhar_pesquisa(self, erro):
        self.progresso.stop()
        self.progresso.pack_forget()
        self.botao_pesquisar.config(state="normal")
        self.pesquisando = False
        self.status("Falha na pesquisa.")
        messagebox.showerror("Erro na pesquisa", str(erro))

    def _preencher_tabela(self):
        self.tabela.delete(*self.tabela.get_children())
        for item in self.resultados:
            self.tabela.insert("", "end", iid=str(item["id"]), values=(
                item["municipio"], item["uf"], item["regiao"],
                item["candidato"], item["termos"], item["ocorrencias"]))

    def _item_selecionado(self):
        selecao = self.tabela.selection()
        if not selecao:
            return None
        identificador = int(selecao[0])
        return next((r for r in self.resultados if r["id"] == identificador), None)

    def _mostrar_trechos(self, _evento=None):
        item = self._item_selecionado()
        self.campo_trechos.config(state="normal")
        self.campo_trechos.delete("1.0", "end")
        if not item:
            self.campo_trechos.config(state="disabled")
            return

        cabecalho = (f"{item['municipio']} / {item['uf']}  —  "
                     f"{item['candidato']}\n"
                     f"Termos: {item['termos']}\n"
                     f"{'-' * 96}\n\n")

        # Recorte sob demanda: so o municipio clicado e processado.
        # Uma falha aqui NAO e memorizada em item["trechos"], senao o erro
        # viraria cache permanente e acabaria gravado na planilha exportada.
        if not item.get("trechos"):
            try:
                achados = busca.trechos_do_municipio(
                    self.con, item["id"],
                    item.get("lista_termos") or [item["termos"]])
                item["trechos"] = "\n---\n".join(
                    recorte for recortes in achados.values() for recorte in recortes)
            except Exception as falha:
                self.campo_trechos.insert(
                    "1.0", cabecalho
                    + f"Nao foi possivel recortar os trechos agora: {falha}\n\n"
                      "Selecione o municipio novamente para tentar de novo.")
                self.campo_trechos.config(state="disabled")
                return

        corpo = (item["trechos"] or "(nenhum trecho recortado)").replace("\n---\n", "\n\n• ")
        self.campo_trechos.insert("1.0", cabecalho + "• " + corpo)
        self.campo_trechos.config(state="disabled")

    def abrir_pdf(self):
        item = self._item_selecionado()
        if not item:
            messagebox.showinfo("Nenhuma linha", "Selecione um municipio na tabela.")
            return
        caminho = os.path.join(RAIZ, item["arquivo"].replace("/", os.sep))
        if not os.path.exists(caminho):
            messagebox.showwarning("Arquivo ausente", f"Nao encontrado:\n{caminho}")
            return
        self._abrir_no_sistema(caminho)

    def _abrir_no_sistema(self, caminho):
        """Abre o arquivo no programa padrao do sistema operacional."""
        try:
            if sys.platform.startswith("win"):
                os.startfile(caminho)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.run(["open", caminho], check=False)
            else:
                subprocess.run(["xdg-open", caminho], check=False)
        except Exception as erro:
            messagebox.showerror("Erro ao abrir", str(erro))

    def exportar(self):
        if not self.resultados:
            messagebox.showinfo("Nada a exportar", "Faca uma pesquisa primeiro.")
            return
        caminho = filedialog.asksaveasfilename(
            title="Salvar resultados",
            defaultextension=".xlsx",
            initialfile="mapeamento_politicas_2024.xlsx",
            filetypes=[("Planilha Excel", "*.xlsx"), ("CSV", "*.csv")])
        if not caminho:
            return

        # Recortar os trechos de milhares de municipios leva minutos. Feito na
        # thread da interface, a janela congelaria sem progresso e o Windows a
        # marcaria como "nao respondendo". Por isso vai para uma thread propria,
        # com contagem visivel.
        pendentes = [r for r in self.resultados if not r.get("trechos")]
        if pendentes:
            self.progresso.config(mode="determinate", maximum=len(pendentes), value=0)
            self.progresso.pack(side="right")
            self.status(f"Recortando trechos de {len(pendentes)} municipios...")

            def preparar():
                conexao = busca.conectar()
                try:
                    for indice, registro in enumerate(pendentes, 1):
                        try:
                            achados = busca.trechos_do_municipio(
                                conexao, registro["id"], registro.get("lista_termos")
                                or [registro["termos"]])
                            registro["trechos"] = "\n---\n".join(
                                r for lista in achados.values() for r in lista)
                        except Exception:
                            # Sem trecho e melhor que um trecho falso; nao
                            # gravamos mensagem de erro na planilha.
                            registro["trechos"] = ""
                        if indice % 10 == 0:
                            self.after(0, lambda v=indice: self.progresso.config(value=v))
                finally:
                    conexao.close()
                self.after(0, lambda: self._gravar_exportacao(caminho))

            threading.Thread(target=preparar, daemon=True).start()
            return

        self._gravar_exportacao(caminho)

    def _gravar_exportacao(self, caminho):
        self.progresso.stop()
        self.progresso.pack_forget()
        self.progresso.config(mode="indeterminate")
        try:
            exportar.gravar(
                caminho, self.resultados,
                ["municipio", "uf", "regiao", "candidato", "partido", "status",
                 "termos", "qtd_termos", "ocorrencias", "paginas", "arquivo",
                 "trechos"],
                ["Municipio", "UF", "Regiao", "Prefeito eleito", "Partido",
                 "Situacao", "Termos encontrados", "Qtd. termos", "Mencoes",
                 "Paginas", "Arquivo do plano", "Trechos literais"])
            self.status(f"Exportado: {caminho}")
            messagebox.showinfo("Exportado",
                                f"{len(self.resultados)} registros salvos em:\n{caminho}")
        except Exception as erro:
            messagebox.showerror("Erro ao exportar", str(erro))

    # --------------------------------------------------------------- municipio
    def _montar_aba_municipio(self):
        barra = ttk.Frame(self.aba_municipio)
        barra.pack(fill="x")
        ttk.Label(barra, text="Nome do municipio:").pack(side="left")
        self.campo_municipio = ttk.Entry(barra, width=36, font=("Segoe UI", 10))
        self.campo_municipio.pack(side="left", padx=8)
        self.campo_municipio.bind("<Return>", lambda e: self.consultar_municipio())
        ttk.Button(barra, text="Consultar", style="Acao.TButton",
                   command=self.consultar_municipio).pack(side="left")

        divisor = ttk.PanedWindow(self.aba_municipio, orient="horizontal")
        divisor.pack(fill="both", expand=True, pady=10)

        quadro_lista = ttk.Frame(divisor)
        colunas = ("municipio", "uf", "candidato", "status", "qualidade")
        self.tabela_municipio = ttk.Treeview(quadro_lista, columns=colunas,
                                             show="headings", height=20)
        for coluna, titulo, largura in [
            ("municipio", "Municipio", 160), ("uf", "UF", 40),
            ("candidato", "Prefeito eleito", 210), ("status", "Situacao", 120),
            ("qualidade", "Texto", 100)]:
            self.tabela_municipio.heading(coluna, text=titulo)
            self.tabela_municipio.column(coluna, width=largura)
        self.tabela_municipio.pack(side="left", fill="both", expand=True)
        barra_m = ttk.Scrollbar(quadro_lista, orient="vertical",
                                command=self.tabela_municipio.yview)
        self.tabela_municipio.configure(yscrollcommand=barra_m.set)
        barra_m.pack(side="right", fill="y")
        self.tabela_municipio.bind("<<TreeviewSelect>>", self._mostrar_plano)
        divisor.add(quadro_lista, weight=2)

        quadro_direita = ttk.Frame(divisor)

        # Ficha do prefeito eleito: foto, partido e numero na urna
        self.ficha = ttk.Frame(quadro_direita, style="Painel.TFrame", padding=10)
        self.ficha.pack(fill="x", pady=(0, 8))
        self.painel_foto = tk.Label(self.ficha, background="#dfe5ea", width=12,
                                    height=6, text="sem\nfoto",
                                    foreground=COR_TEXTO_FRACO,
                                    font=("Segoe UI", 8))
        self.painel_foto.pack(side="left", padx=(0, 12))
        self.rotulo_ficha = tk.Label(self.ficha, justify="left", anchor="nw",
                                     background=COR_PAINEL, font=("Segoe UI", 10),
                                     foreground="#2b3238", text="")
        self.rotulo_ficha.pack(side="left", fill="both", expand=True)
        self._imagem_foto = None

        quadro_texto = ttk.LabelFrame(quadro_direita,
                                      text=" Plano de governo (texto integral) ",
                                      padding=8)
        quadro_texto.pack(fill="both", expand=True)
        self.campo_plano = tk.Text(quadro_texto, wrap="word", font=("Segoe UI", 10))
        barra_p = ttk.Scrollbar(quadro_texto, orient="vertical",
                                command=self.campo_plano.yview)
        self.campo_plano.configure(yscrollcommand=barra_p.set, state="disabled")
        self.campo_plano.pack(side="left", fill="both", expand=True)
        barra_p.pack(side="right", fill="y")
        divisor.add(quadro_direita, weight=3)

    def _preencher_ficha(self, dados):
        """Foto e dados do prefeito eleito, quando disponiveis."""
        if not dados:
            self.rotulo_ficha.config(text="")
            self._imagem_foto = None
            self.painel_foto.config(image="", text="sem\nfoto")
            return

        partido = dados.get("partido") or ""
        numero = dados.get("numero_urna") or ""
        urna = dados.get("nome_urna") or ""
        linhas = [f"{dados['municipio']} / {dados['uf']}"]
        if dados.get("candidato"):
            linhas.append(f"Prefeito eleito: {dados['candidato']}")
        if urna and urna.upper() != (dados.get("candidato") or "").upper():
            linhas.append(f"Nome na urna: {urna}")
        if partido:
            linhas.append(f"Partido: {partido}" + (f"  ·  numero {numero}" if numero else ""))
        elif dados.get("status") == "COM_PROPOSTA":
            linhas.append("Partido: (rode app/importar_tse.py para preencher)")
        if dados.get("regiao"):
            linhas.append(f"Regiao: {dados['regiao']}")
        self.rotulo_ficha.config(text="\n".join(linhas))

        caminho_foto = dados.get("foto") or ""
        completo = os.path.join(RAIZ, caminho_foto.replace("/", os.sep)) if caminho_foto else ""
        if not completo or not os.path.exists(completo):
            self._imagem_foto = None
            self.painel_foto.config(image="", text="sem\nfoto")
            return
        try:
            from PIL import Image, ImageTk
            imagem = Image.open(completo)
            imagem.thumbnail((110, 150), Image.LANCZOS)
            self._imagem_foto = ImageTk.PhotoImage(imagem)
            self.painel_foto.config(image=self._imagem_foto, text="")
        except Exception:
            self._imagem_foto = None
            self.painel_foto.config(image="", text="sem\nfoto")

    def consultar_municipio(self):
        if not self.con:
            return
        termo = self.campo_municipio.get().strip()
        if not termo:
            return
        achados = busca.buscar_municipio(self.con, termo)
        self.tabela_municipio.delete(*self.tabela_municipio.get_children())
        for item in achados:
            self.tabela_municipio.insert("", "end", iid=str(item["id"]), values=(
                item["municipio"], item["uf"], item["candidato"], item["status"],
                item.get("qualidade_texto", "")))
        self.status(f"{len(achados)} municipios encontrados para '{termo}'.")

    def _mostrar_plano(self, _evento=None):
        selecao = self.tabela_municipio.selection()
        if not selecao or not self.con:
            return
        dados = busca.texto_do_municipio(self.con, int(selecao[0]))
        self._preencher_ficha(dados)
        self.campo_plano.config(state="normal")
        self.campo_plano.delete("1.0", "end")
        if dados:
            qualidade = dados.get("qualidade_texto", "")
            cabecalho = (f"{dados['municipio']} / {dados['uf']}\n"
                         f"Prefeito eleito: {dados['candidato']}\n"
                         f"{'=' * 90}\n\n")

            if qualidade in ("OCR_PARCIAL", "OCR_VAZIO"):
                texto = (
                    "ESTE PLANO PASSOU POR OCR E CONTINUA ILEGIVEL.\n\n"
                    f"O documento tem {dados['paginas']} paginas escaneadas. O "
                    "reconhecimento optico\n"
                    f"conseguiu extrair apenas {dados['caracteres']} caracteres, "
                    "muito abaixo do\n"
                    "esperado para um plano desse tamanho.\n\n"
                    "IMPORTANTE: a ausencia deste municipio em uma busca NAO\n"
                    "significa que o plano nao trata do tema.\n\n"
                    "O pouco que foi reconhecido aparece abaixo, apenas para\n"
                    "conferencia. Para leitura, abra o PDF original:\n"
                    f"    {dados['arquivo']}\n\n"
                    f"{'-' * 60}\n\n" + (dados["texto"] or ""))
            elif qualidade in ("ESCANEADO", "VAZIO"):
                texto = (
                    "ESTE PLANO E UM PDF ESCANEADO (IMAGEM).\n\n"
                    f"O arquivo existe e tem {dados['paginas']} paginas, mas foi\n"
                    "enviado ao TSE como imagem, sem camada de texto. Por isso\n"
                    "nao aparece nas buscas por palavra-chave e nao pode ser lido\n"
                    "aqui.\n\n"
                    "IMPORTANTE: a ausencia deste municipio em uma busca NAO\n"
                    "significa que o plano nao trata do tema. Significa apenas\n"
                    "que o documento e ilegivel para o computador.\n\n"
                    "Para ler o conteudo, use o botao 'Abrir plano original' na\n"
                    "aba de pesquisa, ou aplique OCR ao arquivo:\n"
                    f"    {dados['arquivo']}\n")
            elif qualidade == "CURTO":
                texto = (
                    "ATENCAO: extracao parcial.\n\n"
                    f"Foram lidos apenas {dados['caracteres']} caracteres em "
                    f"{dados['paginas']} paginas.\n"
                    "Parte do documento pode estar em imagem. Confira o PDF "
                    "original.\n\n"
                    f"{'-' * 60}\n\n" + (dados["texto"] or ""))
            elif dados["status"] != "COM_PROPOSTA":
                texto = (f"Situacao: {dados['status']}\n\n"
                         "Nao ha plano de governo publicado para este municipio.")
            else:
                texto = dados["texto"] or "(sem texto extraido)"

            self.campo_plano.insert("1.0", cabecalho + texto)
        self.campo_plano.config(state="disabled")

    # -------------------------------------------------------- sem proposta
    def _montar_aba_sem_proposta(self):
        topo = ttk.Frame(self.aba_sem_proposta)
        topo.pack(fill="x")
        ttk.Label(topo, text="Municipios sem plano de governo disponivel",
                  font=("Segoe UI Semibold", 12), foreground=COR_DESTAQUE,
                  background=COR_FUNDO).pack(anchor="w")
        ttk.Label(topo, style="Sub.TLabel", text=(
            "Cada registro traz o print capturado no portal do TSE no momento "
            "da coleta, comprovando a ausencia da proposta."
        )).pack(anchor="w", pady=(2, 10))

        barra = ttk.Frame(self.aba_sem_proposta)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Filtrar por municipio ou nome:").pack(side="left")
        self.campo_sem = ttk.Entry(barra, width=30, font=("Segoe UI", 10))
        self.campo_sem.pack(side="left", padx=8)
        self.campo_sem.bind("<Return>", lambda e: self.listar_sem_proposta())
        ttk.Button(barra, text="Filtrar",
                   command=self.listar_sem_proposta).pack(side="left")
        ttk.Button(barra, text="Mostrar todos",
                   command=lambda: (self.campo_sem.delete(0, "end"),
                                    self.listar_sem_proposta())).pack(side="left", padx=6)
        ttk.Button(barra, text="Exportar lista",
                   command=self.exportar_sem_proposta).pack(side="left")
        self.rotulo_sem = ttk.Label(barra, text="", style="Sub.TLabel")
        self.rotulo_sem.pack(side="right")

        divisor = ttk.PanedWindow(self.aba_sem_proposta, orient="horizontal")
        divisor.pack(fill="both", expand=True)

        quadro_lista = ttk.Frame(divisor)
        colunas = ("municipio", "uf", "candidato", "situacao")
        self.tabela_sem = ttk.Treeview(quadro_lista, columns=colunas,
                                       show="headings", height=22)
        for coluna, titulo, largura in [
            ("municipio", "Municipio", 175), ("uf", "UF", 40),
            ("candidato", "Prefeito eleito", 215), ("situacao", "Situacao", 125)]:
            self.tabela_sem.heading(coluna, text=titulo)
            self.tabela_sem.column(coluna, width=largura)
        self.tabela_sem.pack(side="left", fill="both", expand=True)
        rolagem = ttk.Scrollbar(quadro_lista, orient="vertical",
                                command=self.tabela_sem.yview)
        self.tabela_sem.configure(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.tabela_sem.bind("<<TreeviewSelect>>", self._mostrar_print)
        divisor.add(quadro_lista, weight=2)

        quadro_print = ttk.LabelFrame(divisor, text=" Print de comprovacao ",
                                      padding=8)
        self.rotulo_print_info = ttk.Label(quadro_print, text="", style="Sub.TLabel")
        self.rotulo_print_info.pack(anchor="w", pady=(0, 6))
        self.painel_print = tk.Label(quadro_print, background="#e9edf1",
                                     text="Selecione um municipio para ver o print.",
                                     foreground=COR_TEXTO_FRACO,
                                     font=("Segoe UI", 10))
        self.painel_print.pack(fill="both", expand=True)
        ttk.Button(quadro_print, text="Abrir imagem em tamanho real",
                   command=self.abrir_print).pack(anchor="w", pady=(8, 0))
        divisor.add(quadro_print, weight=3)

        self._imagem_print = None
        self._registros_sem = []

    def listar_sem_proposta(self):
        if not self.con:
            return
        filtro = self.campo_sem.get().strip()
        self._registros_sem = busca.sem_proposta(self.con, filtro)
        self.tabela_sem.delete(*self.tabela_sem.get_children())
        rotulos = {"SEM_PROPOSTA": "Eleito sem plano",
                   "SEM_ELEITO": "Sem candidato eleito"}
        for item in self._registros_sem:
            self.tabela_sem.insert("", "end", iid=str(item["id"]), values=(
                item["municipio"], item["uf"], item["candidato"] or "—",
                rotulos.get(item["status"], item["status"])))
        self.rotulo_sem.config(text=f"{len(self._registros_sem)} municipios")

    def _registro_sem_selecionado(self):
        selecao = self.tabela_sem.selection()
        if not selecao:
            return None
        identificador = int(selecao[0])
        return next((r for r in self._registros_sem if r["id"] == identificador), None)

    def _mostrar_print(self, _evento=None):
        item = self._registro_sem_selecionado()
        if not item:
            return
        caminho = os.path.join(RAIZ, (item["arquivo"] or "").replace("/", os.sep))
        self.rotulo_print_info.config(
            text=f"{item['municipio']} / {item['uf']}  ·  "
                 f"{item['candidato'] or 'sem candidato eleito'}")

        if not item["arquivo"] or not os.path.exists(caminho):
            self._imagem_print = None
            self.painel_print.config(image="", text="Print nao encontrado no disco.")
            return
        try:
            from PIL import Image, ImageTk
            imagem = Image.open(caminho)
            largura_max = max(self.painel_print.winfo_width(), 520)
            altura_max = max(self.painel_print.winfo_height(), 380)
            imagem.thumbnail((largura_max, altura_max), Image.LANCZOS)
            self._imagem_print = ImageTk.PhotoImage(imagem)
            self.painel_print.config(image=self._imagem_print, text="")
        except Exception:
            try:
                self._imagem_print = tk.PhotoImage(file=caminho)
                self.painel_print.config(image=self._imagem_print, text="")
            except Exception as erro:
                self._imagem_print = None
                self.painel_print.config(image="", text=f"Nao foi possivel exibir:\n{erro}")

    def abrir_print(self):
        item = self._registro_sem_selecionado()
        if not item:
            messagebox.showinfo("Nenhuma linha", "Selecione um municipio na lista.")
            return
        caminho = os.path.join(RAIZ, (item["arquivo"] or "").replace("/", os.sep))
        if not os.path.exists(caminho):
            messagebox.showwarning("Arquivo ausente", f"Nao encontrado:\n{caminho}")
            return
        self._abrir_no_sistema(caminho)

    def exportar_sem_proposta(self):
        if not self._registros_sem:
            messagebox.showinfo("Lista vazia", "Nada para exportar.")
            return
        caminho = filedialog.asksaveasfilename(
            title="Salvar lista", defaultextension=".xlsx",
            initialfile="municipios_sem_proposta.xlsx",
            filetypes=[("Planilha Excel", "*.xlsx"), ("CSV", "*.csv")])
        if not caminho:
            return
        try:
            exportar.gravar(
                caminho, self._registros_sem,
                ["municipio", "uf", "regiao", "candidato", "status", "arquivo"],
                ["Municipio", "UF", "Regiao", "Prefeito eleito", "Situacao",
                 "Print de comprovacao"])
            messagebox.showinfo("Exportado", f"Lista salva em:\n{caminho}")
        except Exception as erro:
            messagebox.showerror("Erro ao exportar", str(erro))

    # ------------------------------------------------------------ como usar
    def _texto_rolavel(self, pai):
        """Area de texto somente leitura, com rolagem e estilos de titulo."""
        quadro = ttk.Frame(pai)
        quadro.pack(fill="both", expand=True)
        campo = tk.Text(quadro, wrap="word", font=("Segoe UI", 10),
                        background=COR_PAINEL, foreground="#2b3238",
                        relief="flat", padx=22, pady=18, spacing1=1, spacing3=3,
                        cursor="arrow")
        barra = ttk.Scrollbar(quadro, orient="vertical", command=campo.yview)
        campo.configure(yscrollcommand=barra.set)
        campo.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

        campo.tag_configure("h1", font=("Segoe UI Semibold", 15),
                            foreground=COR_DESTAQUE, spacing1=6, spacing3=10)
        campo.tag_configure("h2", font=("Segoe UI Semibold", 12),
                            foreground=COR_DESTAQUE, spacing1=16, spacing3=8)
        campo.tag_configure("passo", font=("Segoe UI Semibold", 10),
                            foreground="#1b1f23", spacing1=8)
        campo.tag_configure("corpo", font=("Segoe UI", 10), lmargin1=16,
                            lmargin2=16, spacing3=4)
        campo.tag_configure("exemplo", font=("Consolas", 10),
                            background="#eef2f6", foreground="#14304a",
                            lmargin1=16, lmargin2=16, spacing1=4, spacing3=6)
        campo.tag_configure("nota", font=("Segoe UI", 10), foreground="#6b5300",
                            background="#fff4ce", lmargin1=16, lmargin2=16,
                            spacing1=6, spacing3=6)
        return campo

    def _escrever(self, campo, blocos):
        campo.config(state="normal")
        campo.delete("1.0", "end")
        for estilo, texto in blocos:
            campo.insert("end", texto + "\n", estilo)
        campo.config(state="disabled")

    def _montar_aba_ajuda(self):
        campo = self._texto_rolavel(self.aba_ajuda)
        self._escrever(campo, [
            ("h1", "Como usar o Mapeador"),
            ("corpo",
             "Este guia cobre todos os recursos do aplicativo, na ordem em que "
             "voce vai precisar deles. Nao e necessario saber programar: tudo "
             "e feito por botoes e campos."),

            ("h2", "Aba 1 - Visao geral"),
            ("corpo",
             "Mostra o tamanho e a qualidade da base. Sao seis indicadores:"),
            ("corpo",
             "•  Municipios no banco - total de registros.\n"
             "•  Com plano de governo - municipios cujo prefeito eleito "
             "publicou o plano no portal do TSE.\n"
             "•  Planos escaneados (sem texto) - PDFs enviados como imagem. "
             "Existem, mas o computador nao consegue ler. Veja a nota "
             "importante no fim deste guia.\n"
             "•  Eleito sem plano - houve prefeito eleito, mas nenhum arquivo "
             "de proposta foi publicado.\n"
             "•  Sem candidato eleito - nao houve eleito no municipio.\n"
             "•  Cobertura - porcentagem dos municipios que elegem prefeito e "
             "que estao cobertos pela base."),
            ("corpo",
             "O botao 'Atualizar numeros' recarrega os indicadores. Use se "
             "abrir o app com o banco em atualizacao."),

            ("h2", "Aba 2 - Pesquisa por palavras-chave"),
            ("corpo", "E o coracao do aplicativo. A tela tem quatro partes."),

            ("passo", "2.1  Grupos de termos (caixa da esquerda)"),
            ("corpo",
             "Conjuntos de termos ja prontos, usados na pesquisa do PIBIC: "
             + ", ".join(busca.GRUPOS_PADRAO) + ". "
             "Marque quantos quiser. Ao marcar, os termos do grupo aparecem "
             "automaticamente no campo do meio, onde podem ser editados."),

            ("passo", "2.2  Termos (campo do meio)"),
            ("corpo",
             "Aqui voce digita o que quiser procurar, um termo por linha. "
             "Pode apagar os termos vindos dos grupos e usar apenas os seus. "
             "A acentuacao e ignorada, entao 'economia solidaria' encontra "
             "tambem 'economia solidária'. Maiusculas e minusculas tambem nao "
             "importam."),
            ("exemplo",
             "Exemplo - procurar formas de horta comunitaria:\n"
             "    horta comunitaria\n"
             "    agricultura urbana\n"
             "    agroecologia"),
            ("corpo",
             "Atencao: o termo e procurado exatamente como escrito. "
             "'moeda social' nao encontra 'moedas sociais'. Por isso os grupos "
             "prontos ja trazem as variacoes no singular e no plural. Faca o "
             "mesmo com os seus termos."),

            ("passo", "2.3  Recorte territorial (caixa da direita)"),
            ("corpo",
             "Duas listas: Regiao e Estado (UF). Clique para selecionar; "
             "segure Ctrl para escolher varios; clique de novo para "
             "desmarcar. Se nao selecionar nada, a busca cobre o Brasil "
             "inteiro. O botao 'Limpar filtros' desmarca tudo de uma vez."),
            ("exemplo",
             "Exemplo - so o Nordeste:      marque Nordeste na lista Regiao\n"
             "Exemplo - so RJ, SP e MG:     marque as tres siglas na lista UF"),

            ("passo", "2.4  Exigir todos os termos"),
            ("corpo",
             "Desmarcado (padrao): traz o municipio que citar QUALQUER um dos "
             "termos. Marcado: traz apenas quem citar TODOS eles. Use marcado "
             "para cruzamentos restritos."),
            ("exemplo",
             "Exemplo - planos que falem de moeda social E de reciclagem:\n"
             "    moeda social\n"
             "    reciclagem\n"
             "  ... e marque 'Exigir todos os termos'."),

            ("passo", "2.5  Botao Pesquisar"),
            ("corpo",
             "Executa a busca. O resultado aparece na tabela com: municipio, "
             "UF, regiao, prefeito eleito, quais termos foram encontrados e "
             "quantas mencoes ao todo. No canto direito da barra aparece o "
             "total de municipios e de mencoes."),
            ("corpo",
             "Clique no titulo de qualquer coluna para reordenar a tabela. "
             "Clicar em 'Mencoes' ordena do mais citado para o menos citado."),

            ("passo", "2.6  Trechos literais (painel de baixo)"),
            ("corpo",
             "Clique em qualquer linha da tabela para ver, no painel "
             "inferior, os trechos do plano onde os termos aparecem, com o "
             "texto ao redor. Sao trechos prontos para citar no seu trabalho. "
             "O app mostra ate tres trechos por termo."),

            ("passo", "2.7  Botao Exportar resultados"),
            ("corpo",
             "Salva tudo o que esta na tabela. Escolha .xlsx para Excel ou "
             ".csv para outros programas. A planilha inclui doze colunas, "
             "entre elas os trechos literais completos e o caminho do arquivo "
             "PDF de origem, para conferencia."),

            ("passo", "2.8  Botao Abrir plano original"),
            ("corpo",
             "Selecione um municipio na tabela e clique. O PDF do plano de "
             "governo abre no leitor padrao do computador. Serve para "
             "conferir o contexto completo de um trecho."),

            ("h2", "Aba 3 - Consultar municipio"),
            ("corpo",
             "Para quando voce ja sabe qual cidade quer ver. Digite o nome "
             "(ou parte dele) e clique em 'Consultar', ou aperte Enter. A "
             "lista da esquerda traz os municipios encontrados, com a "
             "situacao e a qualidade do texto."),
            ("exemplo",
             "Exemplo - digitar 'santo' lista Santo Andre, Santo Antonio...\n"
             "Exemplo - digitar 'niteroi' abre o plano do prefeito eleito."),
            ("passo", "3.1  Ficha do prefeito eleito"),
            ("corpo",
             "Ao selecionar um municipio, o painel da direita mostra no topo "
             "a ficha do prefeito: foto, nome, nome na urna, partido, numero "
             "e regiao. A foto e o partido vem do cadastro oficial do TSE. Se "
             "aparecer o aviso de que o partido nao foi preenchido, e porque "
             "essa importacao complementar ainda nao foi executada."),
            ("passo", "3.2  Texto integral do plano"),
            ("corpo",
             "Abaixo da ficha vem o plano de governo completo. Se o documento "
             "for um PDF escaneado, o app explica a situacao em vez de exibir "
             "uma tela em branco. Se a leitura tiver sido parcial, ele avisa "
             "quantos caracteres conseguiu ler."),

            ("h2", "Aba 4 - Sem proposta"),
            ("corpo",
             "Reune os municipios onde nao ha plano de governo para pesquisar, "
             "em duas situacoes: o prefeito foi eleito mas nao publicou "
             "proposta, ou nao houve candidato eleito. Para cada um existe o "
             "print capturado no portal do TSE no momento da coleta, que serve "
             "como comprovacao documental da ausencia."),
            ("corpo",
             "•  Campo de filtro - digite parte do nome do municipio ou do "
             "candidato e clique em 'Filtrar' (ou aperte Enter).\n"
             "•  Mostrar todos - limpa o filtro e volta a lista completa.\n"
             "•  Clique em uma linha - o print aparece no painel da direita.\n"
             "•  Abrir imagem em tamanho real - abre o print no visualizador "
             "do computador, util para ler detalhes.\n"
             "•  Exportar lista - salva a relacao completa em Excel ou CSV, "
             "com o caminho de cada print."),
            ("corpo",
             "Esta aba e importante metodologicamente: ela documenta que a "
             "ausencia de dados foi verificada, e nao apenas presumida."),

            ("h2", "Nota importante sobre planos escaneados"),
            ("nota",
             "Parte dos planos foi enviada ao TSE como imagem escaneada, sem "
             "camada de texto. Esses documentos existem e podem ate falar do "
             "tema pesquisado, mas sao invisiveis para a busca por palavra.\n\n"
             "Por isso o aplicativo avisa, abaixo dos botoes, quantos planos "
             "do recorte estao nessa condicao. Trate todo resultado como um "
             "PISO, nunca como o total definitivo. Ao consultar um municipio "
             "assim na aba 3, o app explica a situacao em vez de mostrar uma "
             "tela vazia."),

            ("h2", "Ficha tecnica da base"),
            ("corpo",
             "Fonte: portal de Divulgacao de Candidaturas e Contas Eleitorais "
             "do TSE, eleicoes municipais de 2024. Todos os dados sao "
             "publicos.\n"
             "Universo: os municipios brasileiros que elegem prefeito. "
             "Brasilia e Fernando de Noronha nao entram porque nao elegem.\n"
             "A base ja vem pronta com o aplicativo. Nao e preciso baixar nem "
             "processar nada."),
        ])

    def _montar_aba_sobre(self):
        campo = self._texto_rolavel(self.aba_sobre)
        self._escrever(campo, [
            ("h1", "Sobre o aplicativo"),
            ("corpo",
             "O Mapeador de Politicas Publicas Municipais reune, em um unico "
             "lugar, os planos de governo dos prefeitos eleitos nas eleicoes "
             "municipais de 2024 e permite pesquisar neles por qualquer "
             "palavra-chave."),
            ("corpo",
             "A ferramenta nasceu de uma pergunta simples: o que os prefeitos "
             "brasileiros prometeram sobre moedas sociais, renda basica e "
             "economia solidaria? Responder isso exigia ler milhares de "
             "documentos espalhados pelo portal do TSE. O aplicativo "
             "automatiza essa leitura e devolve os trechos literais, com a "
             "fonte, prontos para analise academica."),
            ("corpo",
             "O objetivo maior e permitir comparar o compromisso politico "
             "assumido na campanha com a execucao real das politicas de moeda "
             "social nos territorios, tema da pesquisa em que a ferramenta se "
             "insere."),

            ("h2", "Como citar"),
            ("corpo",
             "Ao usar dados desta ferramenta em trabalhos academicos, "
             "referencie a fonte primaria (portal do TSE) e o aplicativo."),

            ("h2", "Autor"),
            ("corpo",
             "Kevin Flauzino do Nascimento\n"
             "Estudante de Engenharia de Controle e Automacao - UFRJ\n"
             "Universidade Federal do Rio de Janeiro"),

            ("h2", "Contexto da pesquisa"),
            ("corpo",
             "Desenvolvido no ambito do Programa Institucional de Bolsas de "
             "Iniciacao Cientifica (PIBIC) da FGV EAESP, ciclo 2025-2026, sob "
             "orientacao do Prof. Eduardo Diniz, no projeto 'Dashboard para "
             "Monitoramento da Circulacao de Moedas Sociais no Brasil'."),
            ("corpo",
             "O codigo tem origem em trabalho da disciplina Computadores e "
             "Sociedade da UFRJ, do Laboratorio de Informatica e Sociedade "
             "(LabIS), e foi ampliado do estado do Rio de Janeiro para todo o "
             "territorio nacional."),

            ("h2", "Dados e licenca"),
            ("corpo",
             "Todos os dados provem de fontes publicas oficiais. O projeto e "
             "publico e sem fins lucrativos."),
        ])

    # ------------------------------------------------------------------- banco
    def conectar_banco(self):
        if self.con:
            try:
                self.con.close()
            except Exception:
                pass
            self.con = None

        if not busca.banco_existe():
            self.status("Banco de dados nao encontrado em dados/prefeitos2024.db")
            for rotulo in self.cartoes.values():
                rotulo.config(text="--")
            self.rotulo_resumo.config(text=(
                "O arquivo do banco nao foi encontrado.\n\n"
                "Ele acompanha o aplicativo e deve ficar em "
                "dados/prefeitos2024.db.\n"
                "Sem ele, a pesquisa e a consulta por municipio nao funcionam."))
            return

        # Um banco corrompido ou em atualizacao nao pode deixar a janela num
        # estado meio pronto: sem conexao, mas com os filtros preenchidos.
        try:
            self.con = busca.conectar()
            dados = busca.resumo(self.con)
        except Exception as falha:
            self.con = None
            for rotulo in self.cartoes.values():
                rotulo.config(text="--")
            self.rotulo_resumo.config(
                text=f"Nao foi possivel abrir o banco de dados.\n\n{falha}")
            self.status("Falha ao abrir o banco de dados.")
            return
        elegiveis = dados["total"] - dados.get("SEM_PREFEITO", 0)
        cobertos = sum(dados.get(s, 0) for s in
                       ("COM_PROPOSTA", "SEM_PROPOSTA", "SEM_ELEITO"))
        for chave, rotulo in self.cartoes.items():
            if chave == "cobertura":
                # Duas casas, e nao uma: com uma so, 5.568 de 5.569 vira
                # "100,0%" e o municipio que falta desaparece do painel.
                rotulo.config(
                    text=f"{100 * cobertos / elegiveis:.2f}%".replace(".", ",")
                    if elegiveis else "--")
            else:
                rotulo.config(text=f"{dados.get(chave, 0):,}".replace(",", "."))

        com_proposta = dados.get("COM_PROPOSTA", 0)
        ilegiveis = dados.get("ilegiveis", 0)
        legiveis = com_proposta - ilegiveis
        self.rotulo_resumo.config(text=(
            f"A base cobre {cobertos} dos {elegiveis} municipios brasileiros que "
            f"elegem prefeito, a partir dos planos de governo publicados no portal "
            f"do TSE nas eleicoes de 2024.\n\n"
            f"Dos {com_proposta} planos publicados, {legiveis} tem texto "
            f"pesquisavel e {ilegiveis} sao PDFs escaneados (imagem), que o "
            f"computador nao consegue ler.\n"
            f"Outros {dados.get('SEM_PROPOSTA', 0)} municipios elegeram prefeito "
            f"sem publicar plano, e em {dados.get('SEM_ELEITO', 0)} nao houve "
            f"candidato eleito."))

        opcoes = busca.opcoes_filtro(self.con)
        self.lista_regioes.delete(0, "end")
        for regiao in opcoes["regioes"]:
            self.lista_regioes.insert("end", regiao)
        self.lista_ufs.delete(0, "end")
        for uf in opcoes["ufs"]:
            self.lista_ufs.insert("end", uf)

        self.listar_sem_proposta()

        self.status(f"Banco carregado: {dados['total']} municipios, "
                    f"{dados['com_texto']} com texto indexado.")

if __name__ == "__main__":
    Aplicacao().mainloop()
