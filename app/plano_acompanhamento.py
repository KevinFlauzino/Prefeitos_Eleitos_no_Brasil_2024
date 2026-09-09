"""
Monta o plano de acompanhamento das promessas de moeda social.

O cruzamento entre plano de governo e plataforma responde "quem prometeu" e
"onde ja circula". Ele nao responde, sozinho, se a promessa avancou. Este
modulo transforma o cruzamento em uma serie de indicadores mensais que podem
ser reexecutados ao longo do mandato para acompanhar cada compromisso.

Indicadores por municipio com banco na plataforma:

    Alcance      contas ativas e comercios credenciados
    Injecao      valor total emitido no periodo
    Retencao     gasto no comercio local sobre (gasto local + saques)
    Uso          grau_uso_comunitario, publicado pela propria plataforma
    Atividade    grau_atividade_comercio
    Permanencia  grau_permanencia_moeda

Uso:
    python app/plano_acompanhamento.py
    python app/plano_acompanhamento.py --desde 2024-01
"""

import argparse
import collections
import csv
import io
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "app"))
import busca            # noqa: E402
import correlacao       # noqa: E402

busca.configurar_console()

SAIDA = os.path.join(RAIZ, "dados", "correlacao")



def serie_mensal(pasta, desde=None):
    """Indicadores mensais por banco, a partir de indicadores-mensais.json."""
    caminho = os.path.join(pasta, "indicadores-mensais.json")
    with open(caminho, encoding="utf-8") as arquivo:
        registros = json.load(arquivo)

    por_banco = collections.defaultdict(list)
    for r in registros:
        ano, mes = r.get("ano"), r.get("mes")
        if not ano or not mes:
            continue
        periodo = f"{ano}-{str(mes).zfill(2)}"
        if desde and periodo < desde:
            continue
        por_banco[r.get("idempresa")].append({
            "periodo": periodo,
            "banco": r.get("nome_banco"),
            "idestado": r.get("idestado"),
            "idcidade": r.get("idcidade"),
            "contas_ativas": r.get("qtd_contas_ativas") or 0,
            "comercios": r.get("qtd_comercios_credenciados_ativos") or 0,
            "comercios_com_venda": r.get("qtd_comercios_com_venda") or 0,
            "emitido": r.get("total_emitido_valor") or 0.0,
            "gasto_local": r.get("gasto_comercio_local_valor") or 0.0,
            "saques": r.get("saques_valor") or 0.0,
            "grau_uso": r.get("grau_uso_comunitario"),
            "grau_atividade": r.get("grau_atividade_comercio"),
            "grau_permanencia": r.get("grau_permanencia_moeda"),
        })
    # O ultimo periodo de cada banco corresponde ao mes em andamento e vem
    # incompleto: no Arariboia, agosto/2026 registra 48.286 contas ativas contra
    # 66.681 em julho. Incluir esse mes produziria uma queda inexistente.
    # O recorte por empresa (indicadores-mensais_empresa_131.json, que alimenta
    # o painel) atribui 4.274 ao mesmo mes. As duas extracoes concordam em 73
    # dos 75 meses e divergem justamente no mes aberto, o que confirma que ele
    # nao e comparavel.
    for chave, lista in por_banco.items():
        lista.sort(key=lambda x: x["periodo"])
        if len(lista) > 1:
            por_banco[chave] = lista[:-1]
    return por_banco


def retencao(item):
    """
    Parcela do valor que ficou no comercio local em vez de virar saque.

    ATENCAO: calculada sobre `gasto_comercio_local_valor`, campo agregado da
    plataforma que NAO coincide com o que as transacoes mostram. No Arariboia,
    o acumulado desse campo e de R$ 14,6 milhoes, enquanto a soma das
    transacoes de pessoa fisica para pessoa juridica local chega a R$ 119,2
    milhoes - uma diferenca de oito vezes. Use este indicador apenas para
    comparar o mesmo banco ao longo do tempo, nunca como medida absoluta de
    circulacao local, e jamais o compare com indicadores calculados a partir
    da base de transacoes.
    """
    denominador = (item["gasto_local"] or 0) + (item["saques"] or 0)
    if not denominador:
        return None
    return round(100 * item["gasto_local"] / denominador, 2)


def montar(pasta_dados, desde):
    if not busca.banco_existe():
        print("ERRO: banco dos prefeitos nao encontrado.")
        return
    if not os.path.isdir(pasta_dados):
        print(f"ERRO: pasta de dados nao encontrada:\n  {pasta_dados}")
        return

    os.makedirs(SAIDA, exist_ok=True)
    con = busca.conectar()

    print("Identificando os compromissos assumidos...")
    prometem = {(a["municipio"], a["uf"]): a for a in
                busca.pesquisar(con, busca.TERMOS_MOEDA_MUNICIPAL, com_trechos=False)}
    print(f"  {len(prometem)} municipios prometem moeda municipal")

    print("Lendo a serie mensal da plataforma...")
    bancos = correlacao.carregar_bancos(pasta_dados)
    series = serie_mensal(pasta_dados, desde)
    print(f"  {len(bancos)} bancos, {sum(len(v) for v in series.values())} registros mensais")

    linhas = []
    for banco in bancos:
        if not banco["municipio"]:
            continue
        serie = series.get(banco["idempresa"]) or []
        if not serie:
            continue
        chave = (banco["municipio"], banco["uf"])
        promessa = prometem.get(chave)
        for item in serie:
            linhas.append({
                "Municipio": banco["municipio"],
                "UF": banco["uf"],
                "Banco": banco["banco"],
                "Periodo": item["periodo"],
                "Prometeu moeda no plano": "SIM" if promessa else "nao",
                "Termos do compromisso": promessa["termos"] if promessa else "",
                "Contas ativas": item["contas_ativas"],
                "Comercios credenciados": item["comercios"],
                "Comercios com venda": item["comercios_com_venda"],
                "Valor emitido": round(item["emitido"], 2),
                "Gasto no comercio local": round(item["gasto_local"], 2),
                "Saques": round(item["saques"], 2),
                "Retencao local (%) [campo agregado, ver ressalva]": retencao(item),
                "Grau de uso comunitario": item["grau_uso"],
                "Grau de atividade do comercio": item["grau_atividade"],
                "Grau de permanencia da moeda": item["grau_permanencia"],
            })

    if not linhas:
        print("Nenhuma serie disponivel para os municipios identificados.")
        con.close()
        return

    caminho = os.path.join(SAIDA, "plano_acompanhamento.csv")
    with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
    print(f"\nGravado: {os.path.relpath(caminho, RAIZ)}  ({len(linhas)} linhas)")

    # ------------------------------------------------------------- resumo
    print("\n" + "=" * 78)
    print("PLANO DE ACOMPANHAMENTO - retrato mais recente por municipio")
    print("=" * 78)
    print(f"{'Municipio':<24}{'Banco':<16}{'Periodo':<10}{'Contas':>8}"
          f"{'Comerc':>8}{'Reten%*':>8}  Prometeu")
    ultimos = {}
    for linha in linhas:
        chave = (linha["Municipio"], linha["Banco"])
        if chave not in ultimos or linha["Periodo"] > ultimos[chave]["Periodo"]:
            ultimos[chave] = linha
    for linha in sorted(ultimos.values(),
                        key=lambda x: (-x["Contas ativas"], x["Municipio"])):
        valor_ret = linha["Retencao local (%) [campo agregado, ver ressalva]"]
        retencao_txt = f"{valor_ret:.1f}" if valor_ret is not None else "  -"
        print(f"{linha['Municipio'][:22]:<24}{linha['Banco'][:14]:<16}"
              f"{linha['Periodo']:<10}{linha['Contas ativas']:>8}"
              f"{linha['Comercios credenciados']:>8}{retencao_txt:>8}  "
              f"{linha['Prometeu moeda no plano']}")

    print("\n" + "-" * 78)
    print("COMO USAR ESTE PLANO")
    print("-" * 78)
    print("""
1. Rode este script novamente a cada atualizacao dos dados da plataforma.
2. Compare, para cada municipio que prometeu, a evolucao de:
   contas ativas (alcance), comercios credenciados (rede) e retencao local
   (a moeda fica no territorio ou vira saque?).
3. O compromisso e considerado em avanco quando alcance e rede crescem SEM
   queda da retencao. Crescimento de emissao com retencao em queda indica
   que a moeda esta sendo convertida, nao circulando.
4. Municipios que prometeram e NAO tem banco na plataforma sao a fila de
   observacao: a promessa exige criar a infraestrutura antes de circular.

RESSALVAS DE LEITURA
* A coluna de retencao usa o campo agregado gasto_comercio_local_valor, que
  diverge da base de transacoes em cerca de oito vezes no Arariboia. Serve para
  comparar o MESMO banco ao longo do tempo; nao serve como medida absoluta nem
  para comparacao com indicadores calculados das transacoes (como o LM3).
* O mes em andamento e descartado de cada serie, porque chega incompleto.
""")

    fila = [chave for chave in prometem
            if chave not in {(b["municipio"], b["uf"]) for b in bancos if b["municipio"]}]
    print(f"Municipios que prometeram e ainda nao aparecem na plataforma: {len(fila)}")
    for municipio, uf in sorted(fila)[:15]:
        print(f"   {municipio}/{uf}")
    if len(fila) > 15:
        print(f"   ... e mais {len(fila) - 15}")
    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dados", default=correlacao.DADOS_EDINHEIRO_PADRAO)
    parser.add_argument("--desde", default=None,
                        help="periodo inicial no formato AAAA-MM")
    argumentos = parser.parse_args()
    montar(argumentos.dados, argumentos.desde)
