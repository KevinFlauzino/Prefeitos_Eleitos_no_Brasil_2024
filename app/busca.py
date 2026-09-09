"""
Motor de busca sobre o banco de planos de governo.

Permite consultar os 5.570 municipios por regiao, UF, status e por qualquer
conjunto de palavras-chave definido pelo usuario, devolvendo os trechos
literais onde cada termo aparece.
"""

import io
import os
import re
import sqlite3
import sys
import unicodedata

def raiz_do_aplicativo():
    """
    Pasta onde estao 'dados' e 'PDFs'.

    Rodando pelo codigo-fonte, e a raiz do repositorio. Dentro do executavel
    gerado pelo PyInstaller, __file__ aponta para a pasta temporaria onde o
    programa se descompacta, que nao contem o banco; nesse caso vale a pasta do
    proprio executavel, onde a distribuicao coloca 'dados' ao lado dele.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


RAIZ = raiz_do_aplicativo()
BANCO = os.path.join(RAIZ, "dados", "prefeitos2024.db")

# Conjuntos de termos usados na pesquisa PIBIC. O usuario pode editar,
# adicionar e remover grupos livremente pela interface.
# Os grupos separam o que DESIGNA UMA MOEDA do que apenas menciona o tema.
# A distincao e essencial: "reciclagem" aparece em quase todo plano de governo
# sem que exista qualquer moeda envolvida. Misturar os dois inflava a contagem
# de "moeda verde" de 26 para mais de 3.000 municipios.
GRUPOS_PADRAO = {
    "Moeda social e municipal": [
        "moeda social", "moedas sociais", "moeda local", "moedas locais",
        "moeda municipal", "moedas municipais", "moeda comunitaria",
        "moedas comunitarias", "moeda propria",
    ],
    "Moeda verde": [
        "moeda verde", "moedas verdes", "moeda ecologica", "moeda ambiental",
        "cambio verde", "moeda sustentavel",
    ],
    "Bancos comunitarios": [
        "banco comunitario", "bancos comunitarios", "banco municipal",
        "banco de desenvolvimento comunitario", "banco do povo",
    ],
    "Renda basica e transferencia": [
        "renda basica", "renda minima", "renda cidada", "transferencia de renda",
        "renda complementar", "renda social", "auxilio municipal",
        "programa de renda",
    ],
    "Economia solidaria": [
        "economia solidaria", "cooperativismo", "empreendimento solidario",
        "financas solidarias", "comercio justo", "associativismo",
    ],
    "Meio ambiente e reciclagem": [
        "reciclagem", "material reciclavel", "residuos solidos",
        "logistica reversa", "coleta seletiva", "compostagem",
    ],
}

# Definicao usada nas estatisticas do artigo: municipios que propoem alguma
# moeda municipal, somando os dois modelos (transferencia de renda e verde).
TERMOS_MOEDA_MUNICIPAL = (GRUPOS_PADRAO["Moeda social e municipal"]
                          + GRUPOS_PADRAO["Moeda verde"])


# Fonte unica de verdade sobre o que continua ilegivel para a busca.
# ESCANEADO/CURTO/VAZIO vem da auditoria; OCR_PARCIAL e OCR_VAZIO vem do
# reconhecimento optico e significam que o documento seguiu ilegivel mesmo
# depois do OCR. Qualquer modulo que precise contar ou sinalizar documentos
# ilegiveis deve usar estas constantes, e nunca uma lista propria.
QUALIDADES_ILEGIVEIS = ("ESCANEADO", "CURTO", "VAZIO", "OCR_PARCIAL", "OCR_VAZIO")
QUALIDADES_PESQUISAVEIS = ("OK", "OCR")

_console_ajustado = False


def configurar_console():
    """
    Faz o console do Windows aceitar acentos.

    Precisa ser feito UMA unica vez: cada modulo que reenvolvesse sys.stdout
    fecharia o envoltorio anterior, e a primeira mensagem impressa depois disso
    quebraria com "I/O operation on closed file".
    """
    global _console_ajustado
    if _console_ajustado or not hasattr(sys.stdout, "buffer"):
        return
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace", line_buffering=True)
        _console_ajustado = True
    except (AttributeError, ValueError):
        pass


def normalizar(texto):
    """Minusculas, sem acento. Usado para comparar termos e texto."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFD", str(texto))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.lower()


def conectar(caminho=None):
    con = sqlite3.connect(caminho or BANCO)
    con.row_factory = sqlite3.Row
    return con


def banco_existe(caminho=None):
    return os.path.exists(caminho or BANCO)


def opcoes_filtro(con):
    """Valores disponiveis para preencher os menus da interface."""
    regioes = [r[0] for r in con.execute(
        "SELECT DISTINCT regiao FROM municipios WHERE regiao != '' ORDER BY regiao")]
    ufs = [r[0] for r in con.execute(
        "SELECT DISTINCT uf FROM municipios WHERE uf != '' ORDER BY uf")]
    status = [r[0] for r in con.execute(
        "SELECT DISTINCT status FROM municipios ORDER BY status")]
    return {"regioes": regioes, "ufs": ufs, "status": status}


def resumo(con):
    """Numeros gerais do banco, para o painel de status."""
    dados = {"total": con.execute("SELECT COUNT(*) FROM municipios").fetchone()[0]}
    for linha in con.execute("SELECT status, COUNT(*) c FROM municipios GROUP BY status"):
        dados[linha["status"]] = linha["c"]
    dados["com_texto"] = con.execute(
        "SELECT COUNT(*) FROM municipios WHERE caracteres > 0").fetchone()[0]
    dados["ilegiveis"] = contar_ilegiveis(con)
    return dados


def colunas_existentes(con):
    return {info[1] for info in con.execute("PRAGMA table_info(municipios)")}


def tem_auditoria(con):
    """A coluna de qualidade so existe apos rodar auditar_qualidade.py."""
    return "qualidade_texto" in colunas_existentes(con)


def _opcional(con, coluna, existentes=None):
    """
    Devolve o nome da coluna se ela existir, ou um literal vazio com o mesmo
    apelido. Permite que o app funcione antes e depois das importacoes
    complementares (auditoria de qualidade, cadastro do TSE, fotos).
    """
    existentes = existentes if existentes is not None else colunas_existentes(con)
    return coluna if coluna in existentes else f"'' AS {coluna}"


def contar_ilegiveis(con, regioes=None, ufs=None):
    """
    Planos que existem em PDF mas nao produzem texto pesquisavel
    (documentos escaneados). Sao invisiveis para a busca ate passarem por OCR.
    """
    parametros = []
    if not tem_auditoria(con):
        # Sem auditoria, usa a assinatura de PDF escaneado como aproximacao
        condicoes = ["status = 'COM_PROPOSTA'", "caracteres < 1000"]
    else:
        condicoes = ["qualidade_texto IN (%s)"
                     % ",".join("?" * len(QUALIDADES_ILEGIVEIS))]
        parametros += list(QUALIDADES_ILEGIVEIS)
    if regioes:
        condicoes.append("regiao IN (%s)" % ",".join("?" * len(regioes)))
        parametros += list(regioes)
    if ufs:
        condicoes.append("uf IN (%s)" % ",".join("?" * len(ufs)))
        parametros += list(ufs)
    return con.execute(
        f"SELECT COUNT(*) FROM municipios WHERE {' AND '.join(condicoes)}",
        parametros).fetchone()[0]


def dobrar(texto):
    """
    Devolve (dobrado, composto): uma versao do texto sem acento e em minusculas
    com o MESMO comprimento da versao composta, para que uma posicao encontrada
    no primeiro valha tambem no segundo.

    normalizar() nao serve para localizar trechos: ela aplica NFD e descarta as
    marcas de acentuacao, encurtando a string quando o PDF entrega os acentos ja
    decompostos. Os deslocamentos ficariam adiantados e o trecho exibido
    apontaria para outro ponto do documento.
    """
    if not texto:
        return "", ""
    composto = unicodedata.normalize("NFC", texto)
    letras = []
    for caractere in composto:
        decomposto = unicodedata.normalize("NFD", caractere)
        base = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
        letras.append((base[:1] or caractere).lower())
    return "".join(letras), composto


def padrao_do_termo(termo):
    """
    Expressao regular do termo tolerante a espacos e quebras de linha.

    O texto extraido do PDF preserva as quebras inseridas na diagramacao, entao
    'economia solidaria' aparece muitas vezes como 'economia \\nsolidaria'. Uma
    comparacao literal perderia essas ocorrencias sem avisar o pesquisador.
    """
    palavras = [re.escape(p) for p in normalizar(termo).split()]
    if not palavras:
        return None
    return re.compile(r"\s+".join(palavras))


def contar(texto_norm, termo_norm, padrao=None):
    """Quantas vezes o termo aparece no texto, tolerando quebras de linha."""
    if not termo_norm:
        return 0
    regra = padrao if padrao is not None else padrao_do_termo(termo_norm)
    if regra is None:
        return 0
    return sum(1 for _ in regra.finditer(texto_norm))


def _trechos(texto, termos, janela=160, maximo=3):
    """
    Recorta trechos ao redor das ocorrencias, no texto original.

    Recebe a lista completa de termos e dobra o texto UMA unica vez: a versao
    anterior refazia a normalizacao do documento inteiro a cada termo, o que
    levava a busca ampla de 13 s para mais de cinco minutos.
    """
    if not texto:
        return {}
    dobrado, composto = dobrar(texto)
    achados = {}
    for termo in termos:
        regra = padrao_do_termo(termo)
        if regra is None:
            continue
        recortes = []
        for encontro in regra.finditer(dobrado):
            if len(recortes) >= maximo:
                break
            de = max(0, encontro.start() - janela // 2)
            ate = min(len(composto), encontro.end() + janela // 2)
            trecho = re.sub(r"\s+", " ", composto[de:ate]).strip()
            recortes.append(("..." if de > 0 else "") + trecho
                            + ("..." if ate < len(composto) else ""))
        if recortes:
            achados[termo] = recortes
    return achados


def _tem_indice(con):
    """Confere se o indice de texto completo (FTS5) esta disponivel."""
    linha = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='busca'"
    ).fetchone()
    return linha is not None


def _candidatos_pelo_indice(con, termos):
    """
    Reduz o universo antes da contagem exata, sem descartar municipio valido.

    O indice FTS5 nao serve para este papel. Ele casa por palavra inteira,
    enquanto a contagem casa por trecho em qualquer posicao: um plano cujo
    reconhecimento optico grudou "socioeconomia solidaria" contem "economia
    solidaria" para a contagem e nao contem para o indice, e o municipio
    desaparecia em silencio. Foi assim que Portao/RS ficou de fora da lista de
    municipios que propoem moeda municipal.

    O filtro abaixo exige apenas que cada palavra do termo apareca em algum
    lugar do texto normalizado. Essa e uma condicao necessaria para o
    casamento exato, o que torna o conjunto devolvido um superconjunto seguro.

    Devolve o conjunto de ids candidatos, ou None quando o filtro nao puder ser
    aplicado, caso em que a busca varre todos os planos.
    """
    colunas = {info[1] for info in con.execute("PRAGMA table_info(municipios)")}
    if "texto_norm" not in colunas:
        return None

    blocos, parametros = [], []
    for termo in termos:
        palavras = [p for p in normalizar(termo).split() if p]
        if not palavras:
            continue
        # Basta a palavra mais longa do termo: exigir uma so ja e condicao
        # necessaria, mantem o conjunto como superconjunto e corta pela metade
        # o numero de comparacoes por linha, que e o que domina o custo.
        blocos.append("instr(texto_norm, ?) > 0")
        parametros.append(max(palavras, key=len))
    if not blocos:
        return None

    try:
        candidatos = {linha[0] for linha in con.execute(
            "SELECT id FROM municipios WHERE caracteres > 0 AND ("
            + " OR ".join(blocos) + ")", parametros)}
    except sqlite3.OperationalError:
        return None

    # Conjunto vazio aqui significa ausencia real, porque o filtro e um
    # superconjunto. Devolvemos o conjunto vazio para a busca encerrar cedo.
    return candidatos


def pesquisar(con, termos, regioes=None, ufs=None, status=None,
              exigir_todos=False, com_trechos=True, limite=None):
    """
    Procura os `termos` no texto dos planos de governo.

    termos        lista de expressoes (a acentuacao e ignorada)
    regioes/ufs   filtros opcionais de recorte territorial
    status        filtro opcional pela situacao do municipio
    exigir_todos  True  = o municipio precisa conter todos os termos
                  False = basta conter um deles
    Devolve lista de dicionarios prontos para a tabela e para exportacao.
    """
    termos = [t.strip() for t in termos if t and t.strip()]
    termos_norm = [(t, normalizar(t)) for t in termos]

    condicoes, parametros = ["caracteres > 0"], []

    # Pre-filtro pelo indice de texto completo: evita varrer os 5.500 planos
    # inteiros a cada consulta (31s -> menos de 1s).
    candidatos = _candidatos_pelo_indice(con, termos)
    if candidatos is not None:
        if not candidatos:
            return []
        condicoes.append("id IN (%s)" % ",".join("?" * len(candidatos)))
        parametros += list(candidatos)

    if regioes:
        condicoes.append("regiao IN (%s)" % ",".join("?" * len(regioes)))
        parametros += list(regioes)
    if ufs:
        condicoes.append("uf IN (%s)" % ",".join("?" * len(ufs)))
        parametros += list(ufs)
    if status:
        condicoes.append("status IN (%s)" % ",".join("?" * len(status)))
        parametros += list(status)

    # Usa a coluna pre-normalizada quando ela existe (ver migrar_texto_norm.py)
    colunas = {info[1] for info in con.execute("PRAGMA table_info(municipios)")}
    tem_norm = "texto_norm" in colunas
    campo_norm = "texto_norm" if tem_norm else "texto"

    # O texto integral so e carregado quando os trechos forem exibidos;
    # nas agregacoes basta a coluna normalizada.
    campo_texto = "texto" if (com_trechos or not tem_norm) else "''"

    consulta = f"""
        SELECT id, municipio, uf, regiao, candidato, partido, status,
               arquivo, paginas, caracteres, {campo_texto} AS texto,
               {campo_norm} AS norm
        FROM municipios
        WHERE {' AND '.join(condicoes)}
        ORDER BY regiao, uf, municipio
    """

    # Compila uma vez os padroes tolerantes a quebra de linha. Termos que nao
    # produzem padrao (so pontuacao, por exemplo) sao DESCARTADOS aqui, e nao
    # no laco: mante-los faria exigir_todos comparar com um total inatingivel
    # e zerar a busca inteira.
    padroes = [(termo, padrao_do_termo(termo_norm))
               for termo, termo_norm in termos_norm]
    padroes = [(termo, regra) for termo, regra in padroes if regra is not None]
    if not padroes:
        return []

    resultados = []
    for linha in con.execute(consulta, parametros):
        texto = linha["texto"] or ""
        texto_norm = linha["norm"] if tem_norm else normalizar(texto)

        # Se a coluna pre-normalizada existe mas esta vazia para este municipio
        # (migracao interrompida), normalizamos na hora. Sem isso o plano
        # sumiria da busca silenciosamente.
        if tem_norm and not texto_norm and linha["caracteres"]:
            bruto = texto
            if not bruto:
                recuperado = con.execute(
                    "SELECT texto FROM municipios WHERE id = ?",
                    (linha["id"],)).fetchone()
                bruto = (recuperado[0] if recuperado else "") or ""
            texto_norm = normalizar(bruto)

        # Guarda so a posicao inicial de cada ocorrencia: termos que descrevem
        # a mesma passagem (por exemplo "moeda social" e "moeda") contariam a
        # passagem duas vezes. Usar o inicio, e nao o par (inicio, fim), evita
        # criar milhares de tuplas nas buscas amplas.
        encontrados, inicios = [], set()
        for termo, regra in padroes:
            achou = False
            for encontro in regra.finditer(texto_norm):
                inicios.add(encontro.start())
                achou = True
            if achou:
                encontrados.append(termo)

        if not encontrados:
            continue
        if exigir_todos and len(encontrados) != len(padroes):
            continue

        total_ocorrencias = len(inicios)

        # O texto e dobrado uma unica vez por municipio, e nao a cada termo
        trechos = []
        if com_trechos:
            for recortes in _trechos(texto, encontrados).values():
                trechos += recortes

        resultados.append({
            "id": linha["id"],
            "municipio": linha["municipio"],
            "uf": linha["uf"],
            "regiao": linha["regiao"],
            "candidato": linha["candidato"],
            "partido": linha["partido"] or "",
            "status": linha["status"],
            "arquivo": linha["arquivo"],
            "paginas": linha["paginas"],
            # "termos" e o texto para exibir; "lista_termos" preserva os termos
            # separados, porque reconstrui-los quebrando a string por virgula
            # partiria qualquer termo que contenha virgula.
            "lista_termos": list(encontrados),
            "termos": ", ".join(encontrados),
            "qtd_termos": len(encontrados),
            "ocorrencias": total_ocorrencias,
            "trechos": "\n---\n".join(trechos),
        })
        if limite and len(resultados) >= limite:
            break

    resultados.sort(key=lambda r: (-r["ocorrencias"], r["uf"], r["municipio"]))
    return resultados


def trechos_do_municipio(con, id_municipio, termos, maximo=3):
    """
    Trechos literais de um unico municipio, calculados sob demanda.

    A pesquisa devolve centenas ou milhares de linhas; dobrar o texto de todas
    elas custaria minutos. Como o pesquisador le os trechos de um municipio de
    cada vez, o recorte e feito apenas quando ele seleciona a linha.
    """
    linha = con.execute("SELECT texto FROM municipios WHERE id = ?",
                        (id_municipio,)).fetchone()
    if not linha or not linha["texto"]:
        return {}
    return _trechos(linha["texto"], termos, maximo=maximo)


def buscar_municipio(con, termo):
    """Busca municipios pelo nome (para a aba de consulta individual)."""
    alvo = f"%{normalizar(termo).upper()}%"
    extras = ", ".join(_opcional(con, c)
                       for c in ("qualidade_texto", "partido", "foto", "nome_urna"))
    return [dict(linha) for linha in con.execute(f"""
        SELECT id, municipio, uf, regiao, candidato, status, arquivo,
               paginas, caracteres, {extras}
        FROM municipios
        WHERE UPPER(municipio_norm) LIKE ?
        ORDER BY municipio LIMIT 200
    """, (alvo,))]


def sem_proposta(con, filtro=""):
    """
    Municipios sem plano de governo disponivel, com o print de comprovacao
    capturado pelo coletor no momento da consulta ao portal do TSE.

    Cobre dois casos: o prefeito foi eleito mas nao publicou proposta
    (SEM_PROPOSTA) e o municipio nao teve candidato eleito (SEM_ELEITO).
    """
    condicoes = ["status IN ('SEM_PROPOSTA','SEM_ELEITO')"]
    parametros = []
    if filtro:
        condicoes.append("(UPPER(municipio_norm) LIKE ? OR UPPER(candidato) LIKE ?)")
        alvo = f"%{normalizar(filtro).upper()}%"
        parametros += [alvo, alvo]
    return [dict(linha) for linha in con.execute(f"""
        SELECT id, municipio, uf, regiao, candidato, status, arquivo
        FROM municipios
        WHERE {' AND '.join(condicoes)}
        ORDER BY status, uf, municipio
    """, parametros)]


def texto_do_municipio(con, id_municipio):
    extras = ", ".join(_opcional(con, c)
                       for c in ("qualidade_texto", "partido", "foto",
                                 "nome_urna", "numero_urna"))
    linha = con.execute(
        f"""SELECT municipio, uf, regiao, candidato, status, arquivo, paginas,
                   caracteres, {extras}, texto
            FROM municipios WHERE id = ?""",
        (id_municipio,)).fetchone()
    return dict(linha) if linha else None


def estatisticas_por_uf(con, termos):
    """Agrega os municipios que citam os termos, por UF e regiao."""
    achados = pesquisar(con, termos, com_trechos=False)
    por_uf, por_regiao = {}, {}
    for item in achados:
        por_uf[item["uf"]] = por_uf.get(item["uf"], 0) + 1
        por_regiao[item["regiao"]] = por_regiao.get(item["regiao"], 0) + 1
    return {"total": len(achados), "por_uf": por_uf, "por_regiao": por_regiao,
            "resultados": achados}
