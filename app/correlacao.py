"""
Cruzamento entre compromissos politicos e execucao financeira.

De um lado, os planos de governo dos prefeitos eleitos em 2024 (banco local,
construido por construir_bd.py). Do outro, os dados operacionais da plataforma
e-Dinheiro usados no dashboard do Arariboia.

Os dois projetos permanecem separados: este modulo apenas LE as duas bases e
produz o cruzamento, sem alterar nenhuma delas.

Uso:
    python app/correlacao.py
    python app/correlacao.py --dados "E:/DASHBOARD PIBIC FGV/dashboard-arariboia/dados_edinheiro/Dados_Edinheiro"
"""

import argparse
import collections
import csv
import io
import json
import os
import sqlite3
import sys

# O console do Windows nao usa UTF-8 por padrao e corrompe os acentos

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import busca  # noqa: E402

busca.configurar_console()

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS_EDINHEIRO_PADRAO = r"E:/DASHBOARD PIBIC FGV/dashboard-arariboia/dados_edinheiro/Dados_Edinheiro"
SAIDA = os.path.join(RAIZ, "dados", "correlacao")

# idestado da plataforma e-Dinheiro segue a ordem alfabetica das UFs.
# Validado com Palmas/CE, BEM/ES, Pila/RS, Arariboia e Mumbuca/RJ, Tupinamba/PA.
UFS_POR_ID = {i + 1: uf for i, uf in enumerate([
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO"])}

# Municipios confirmados por evidencia documental e por consistencia do
# idcidade (todos os bancos do codigo pertencem, comprovadamente, ao mesmo
# municipio). Usados no cruzamento em nivel municipal.
MUNICIPIO_POR_IDCIDADE = {
    3641: ("Niterói", "RJ"),
    3634: ("Maricá", "RJ"),
    3674: ("Saquarema", "RJ"),
    3605: ("Cabo Frio", "RJ"),
    3621: ("Iguaba Grande", "RJ"),
    882: ("Vitória", "ES"),
    5403: ("Nossa Senhora do Socorro", "SE"),
    5382: ("Indiaroba", "SE"),
}

# Codigos que a plataforma usa como guarda-chuva: reunem bancos de municipios
# diferentes (678 junta Banco Palmas/Fortaleza, Juazeiro e Sao Goncalo do
# Amarante, entre outros). Nao permitem atribuicao municipal confiavel, entao
# esses bancos entram apenas na analise por UF.
IDCIDADE_AMBIGUO = {678}

# Termos que caracterizam compromisso com moeda social / renda / economia solidaria
TERMOS_MOEDA = busca.TERMOS_MOEDA_MUNICIPAL          # os dois modelos de moeda
TERMOS_RENDA = busca.GRUPOS_PADRAO["Renda basica e transferencia"]
TERMOS_SOLIDARIA = busca.GRUPOS_PADRAO["Economia solidaria"]
TERMOS_VERDE = busca.GRUPOS_PADRAO["Moeda verde"]


def carregar_bancos(pasta):
    """Le indicadores-mensais.json -> um registro por banco da plataforma."""
    caminho = os.path.join(pasta, "indicadores-mensais.json")
    with open(caminho, encoding="utf-8") as arquivo:
        registros = json.load(arquivo)

    bancos = {}
    for registro in registros:
        nome = registro.get("nome_banco")
        if not nome:
            continue
        chave = registro.get("idempresa")
        if chave not in bancos:
            bancos[chave] = {
                "idempresa": chave,
                "banco": nome,
                "idestado": registro.get("idestado"),
                "idcidade": registro.get("idcidade"),
                "uf": UFS_POR_ID.get(registro.get("idestado"), ""),
                "meses": 0,
                "contas_ativas": 0,
                "comercios": 0,
                "emitido": 0.0,
            }
        item = bancos[chave]
        item["meses"] += 1
        item["contas_ativas"] = max(item["contas_ativas"],
                                    registro.get("qtd_contas_ativas") or 0)
        item["comercios"] = max(item["comercios"],
                                registro.get("qtd_comercios_credenciados_ativos") or 0)
        item["emitido"] += registro.get("total_emitido_valor") or 0.0

    for item in bancos.values():
        if item["idcidade"] in IDCIDADE_AMBIGUO:
            item["municipio"] = ""
            continue
        municipio = MUNICIPIO_POR_IDCIDADE.get(item["idcidade"])
        item["municipio"] = municipio[0] if municipio else ""
        if municipio:
            item["uf"] = municipio[1]
    return list(bancos.values())


def carregar_programas(pasta):
    """Programas de beneficio pagos via plataforma (nome_programa)."""
    caminho = os.path.join(pasta, "beneficios.json")
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as arquivo:
        registros = json.load(arquivo)
    por_empresa = collections.defaultdict(collections.Counter)
    for registro in registros:
        nome = (registro.get("nome_programa") or "").strip()
        if nome:
            por_empresa[registro.get("idempresa")][nome] += registro.get("valor_total") or 0
    return por_empresa


def promessas(con):
    """Municipios cujo plano de governo cita cada eixo tematico."""
    eixos = {
        "moeda_social": TERMOS_MOEDA,
        "renda": TERMOS_RENDA,
        "economia_solidaria": TERMOS_SOLIDARIA,
        "moeda_verde": TERMOS_VERDE,
    }
    resultado = {}
    for eixo, termos in eixos.items():
        achados = busca.pesquisar(con, termos, com_trechos=False)
        resultado[eixo] = {(a["municipio"], a["uf"]): a for a in achados}
    return resultado


def montar(pasta_dados):
    if not busca.banco_existe():
        print("ERRO: banco dos prefeitos nao encontrado. Rode app/construir_bd.py")
        return
    if not os.path.isdir(pasta_dados):
        print(f"ERRO: pasta de dados e-Dinheiro nao encontrada:\n  {pasta_dados}")
        return

    os.makedirs(SAIDA, exist_ok=True)
    con = busca.conectar()

    print("Lendo compromissos nos planos de governo...")
    eixos = promessas(con)
    for eixo, itens in eixos.items():
        print(f"  {eixo:.<24} {len(itens)} municipios")

    print("\nLendo bancos da plataforma e-Dinheiro...")
    bancos = carregar_bancos(pasta_dados)
    programas = carregar_programas(pasta_dados)
    print(f"  {len(bancos)} bancos comunitarios em "
          f"{len({b['uf'] for b in bancos if b['uf']})} UFs")

    # ---------------------------------------------------------- cruzamento UF
    bancos_por_uf = collections.Counter(b["uf"] for b in bancos if b["uf"])
    municipios_por_uf = {linha["uf"]: linha["n"] for linha in con.execute(
        "SELECT uf, COUNT(*) n FROM municipios WHERE status != 'SEM_PREFEITO' GROUP BY uf")}

    # O percentual precisa dividir por planos EFETIVAMENTE PESQUISAVEIS: o
    # numerador so pode vir de documentos legiveis, entao usar o total de
    # municipios como denominador subestimaria a adesao em UFs com muitos
    # documentos escaneados.
    legiveis_por_uf = {}
    try:
        for linha in con.execute("""
            SELECT uf, COUNT(*) n FROM municipios
            WHERE qualidade_texto IN ('OK','OCR') GROUP BY uf
        """):
            legiveis_por_uf[linha["uf"]] = linha["n"]
    except sqlite3.Error:
        legiveis_por_uf = dict(municipios_por_uf)

    linhas_uf = []
    for uf in sorted(set(list(bancos_por_uf) + list(municipios_por_uf))):
        promete_moeda = sum(1 for (_, u) in eixos["moeda_social"] if u == uf)
        promete_renda = sum(1 for (_, u) in eixos["renda"] if u == uf)
        promete_solid = sum(1 for (_, u) in eixos["economia_solidaria"] if u == uf)
        promete_verde = sum(1 for (_, u) in eixos["moeda_verde"] if u == uf)
        total = municipios_por_uf.get(uf, 0)
        legiveis = legiveis_por_uf.get(uf, 0)
        linhas_uf.append({
            "UF": uf,
            "Municipios": total,
            "Planos pesquisaveis": legiveis,
            "Bancos e-Dinheiro": bancos_por_uf.get(uf, 0),
            "Promete moeda social": promete_moeda,
            "Promete renda": promete_renda,
            "Promete economia solidaria": promete_solid,
            "Promete moeda verde": promete_verde,
            "% dos planos pesquisaveis que prometem moeda":
                round(100 * promete_moeda / legiveis, 2) if legiveis else 0,
        })

    # ------------------------------------------------- cruzamento por municipio
    # Qualidade do plano de cada municipio: sem isso, um documento escaneado
    # seria reportado como "nao promete", quando na verdade e ilegivel.
    qualidade_por_municipio = {}
    try:
        for linha in con.execute("""
            SELECT municipio, uf, status, qualidade_texto FROM municipios
        """):
            qualidade_por_municipio[(linha["municipio"], linha["uf"])] = (
                linha["status"], linha["qualidade_texto"] or "")
    except sqlite3.Error:
        pass

    ILEGIVEIS = set(busca.QUALIDADES_ILEGIVEIS)

    def responder(achado, chave):
        """SIM, nao, ou uma marca explicita de que a resposta e desconhecida."""
        if achado:
            return "SIM"
        status, qualidade = qualidade_por_municipio.get(chave, ("", ""))
        if qualidade in ILEGIVEIS:
            return "ILEGIVEL"
        if status and status != "COM_PROPOSTA":
            return "SEM PLANO"
        return "nao"

    linhas_caso = []
    for banco in sorted(bancos, key=lambda b: (b["uf"], b["banco"])):
        if not banco["municipio"]:
            continue
        chave = (banco["municipio"], banco["uf"])
        achado_moeda = eixos["moeda_social"].get(chave)
        achado_renda = eixos["renda"].get(chave)
        achado_solid = eixos["economia_solidaria"].get(chave)
        principais = programas.get(banco["idempresa"], collections.Counter())
        linhas_caso.append({
            "Municipio": banco["municipio"],
            "UF": banco["uf"],
            "Banco comunitario": banco["banco"],
            "Meses de dados": banco["meses"],
            "Contas ativas (pico)": banco["contas_ativas"],
            "Comercios (pico)": banco["comercios"],
            "Plano legivel": "nao" if qualidade_por_municipio.get(chave, ("", ""))[1]
                             in ILEGIVEIS else "sim",
            "Promete moeda social": responder(achado_moeda, chave),
            "Promete renda": responder(achado_renda, chave),
            "Promete economia solidaria": responder(achado_solid, chave),
            "Termos no plano": (achado_moeda or achado_renda or {}).get("termos", ""),
            "Prefeito eleito": (achado_moeda or achado_renda or {}).get("candidato", ""),
            "Programas pagos na plataforma": ", ".join(
                nome for nome, _ in principais.most_common(5)),
        })

    # ------------------------------------------------------------------ saidas
    _salvar_csv(os.path.join(SAIDA, "cruzamento_por_uf.csv"), linhas_uf)
    _salvar_csv(os.path.join(SAIDA, "casos_municipais.csv"), linhas_caso)
    _salvar_csv(os.path.join(SAIDA, "bancos_edinheiro.csv"), [
        {"Banco": b["banco"], "UF": b["uf"], "Municipio": b["municipio"],
         "idempresa": b["idempresa"], "Meses": b["meses"],
         "Contas ativas (pico)": b["contas_ativas"],
         "Comercios (pico)": b["comercios"]}
        for b in sorted(bancos, key=lambda b: (b["uf"], b["banco"]))])

    _relatorio(linhas_uf, linhas_caso, eixos, bancos)
    con.close()


def _salvar_csv(caminho, linhas):
    if not linhas:
        return
    with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
    print(f"  gravado: {os.path.relpath(caminho, RAIZ)}")


def _relatorio(linhas_uf, linhas_caso, eixos, bancos):
    print("\n" + "=" * 74)
    print("CRUZAMENTO  compromisso politico (TSE 2024)  x  execucao (e-Dinheiro)")
    print("=" * 74)

    print("\nUFs com mais bancos comunitarios e o que os prefeitos prometeram:")
    print(f"{'UF':<4}{'Bancos':>7}{'Munic.':>8}{'Moeda':>7}{'Renda':>7}"
          f"{'Ec.Sol':>8}{'Verde':>7}")
    for linha in sorted(linhas_uf, key=lambda x: -x["Bancos e-Dinheiro"])[:12]:
        print(f"{linha['UF']:<4}{linha['Bancos e-Dinheiro']:>7}{linha['Municipios']:>8}"
              f"{linha['Promete moeda social']:>7}{linha['Promete renda']:>7}"
              f"{linha['Promete economia solidaria']:>8}{linha['Promete moeda verde']:>7}")

    print("\nEstudos de caso (municipio com banco na plataforma):")
    for caso in linhas_caso:
        resposta = caso["Promete moeda social"]
        marca = "*" if resposta == "SIM" else ("?" if resposta == "ILEGIVEL" else " ")
        print(f" {marca} {caso['Municipio']:<26}/{caso['UF']}  {caso['Banco comunitario']:<22}"
              f" moeda={resposta:<9} renda={caso['Promete renda']}")
        if caso["Programas pagos na plataforma"]:
            print(f"     programas: {caso['Programas pagos na plataforma'][:96]}")

    total_moeda = len(eixos["moeda_social"])
    print("\n" + "-" * 74)
    print(f"Municipios que citam moeda social/local/comunitaria... {total_moeda}")
    print(f"Municipios que citam renda basica/transferencia....... {len(eixos['renda'])}")
    print(f"Municipios que citam economia solidaria.............. {len(eixos['economia_solidaria'])}")
    print(f"Municipios que citam moeda verde/reciclagem.......... {len(eixos['moeda_verde'])}")
    print(f"Bancos comunitarios ativos na plataforma............. {len(bancos)}")
    print("-" * 74)
    print(f"\nArquivos em: {os.path.relpath(SAIDA, RAIZ)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dados", default=DADOS_EDINHEIRO_PADRAO,
                        help="pasta Dados_Edinheiro do dashboard")
    montar(parser.parse_args().dados)
