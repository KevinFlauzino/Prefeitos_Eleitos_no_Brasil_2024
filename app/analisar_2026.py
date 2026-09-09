"""
Analisa as propostas da eleicao geral de 2026 com o mesmo vocabulario usado
para os planos municipais de 2024.

Permite responder, com a mesma regua, o que candidatos a Governador e a
Presidente prometem sobre moedas sociais, renda basica e economia solidaria.

Uso:
    python app/analisar_2026.py
"""

import collections
import io
import os
import sqlite3
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "app"))
import busca  # noqa: E402

busca.configurar_console()

BANCO = os.path.join(RAIZ, "dados", "eleicoes2026.db")



def carregar():
    con = sqlite3.connect(BANCO)
    con.row_factory = sqlite3.Row
    registros = con.execute("""
        SELECT id, uf, cargo, nome_urna, partido, situacao, arquivo, texto
        FROM candidatos2026 WHERE texto != ''
    """).fetchall()
    con.close()

    # Texto nao vazio nao prova legibilidade: uma proposta escaneada devolve
    # poucas dezenas de caracteres e seria contada como "nao menciona o tema".
    # Separamos as duas situacoes para nao transformar lacuna em ausencia.
    legiveis = [r for r in registros if len(r["texto"] or "") >= 1000]
    ilegiveis = [r for r in registros if len(r["texto"] or "") < 1000]
    return legiveis, ilegiveis


def procurar(registros, termos):
    """Aplica os mesmos padroes tolerantes a quebra de linha usados em 2024."""
    padroes = [(t, busca.padrao_do_termo(t)) for t in termos]
    achados = []
    for registro in registros:
        texto_norm = busca.normalizar(registro["texto"])
        encontrados, total = [], 0
        for termo, regra in padroes:
            if regra is None:
                continue
            quantidade = sum(1 for _ in regra.finditer(texto_norm))
            if quantidade:
                encontrados.append(termo)
                total += quantidade
        if encontrados:
            achados.append({
                "uf": registro["uf"], "cargo": registro["cargo"],
                "nome": registro["nome_urna"], "partido": registro["partido"],
                "termos": ", ".join(encontrados), "ocorrencias": total,
                "id": registro["id"],
            })
    achados.sort(key=lambda a: -a["ocorrencias"])
    return achados


def trecho(registros, id_candidato, termo, janela=190):
    for registro in registros:
        if registro["id"] != id_candidato:
            continue
        recortes = busca._trechos(registro["texto"], [termo], janela=janela, maximo=1)
        for lista in recortes.values():
            return lista[0] if lista else ""
    return ""


def main():
    if not os.path.exists(BANCO):
        print("Banco de 2026 nao encontrado. Rode app/coletar_2026.py antes.")
        return

    registros, ilegiveis = carregar()
    por_cargo = collections.Counter(r["cargo"] for r in registros)
    print(f"Propostas com texto pesquisavel: {len(registros)}")
    if ilegiveis:
        print(f"Propostas ilegiveis (escaneadas): {len(ilegiveis)}")
        for r in ilegiveis:
            print(f"   {r['nome_urna']}/{r['uf']} ({len(r['texto'] or '')} chars)")
        print("   -> a ausencia destes candidatos nas contagens abaixo NAO")
        print("      significa que suas propostas nao tratam do tema.")
    for cargo, quantidade in por_cargo.items():
        print(f"  {cargo}: {quantidade}")

    eixos = {
        "Moeda municipal/social": busca.TERMOS_MOEDA_MUNICIPAL,
        "Bancos comunitarios": busca.GRUPOS_PADRAO["Bancos comunitarios"],
        "Renda basica e transferencia": busca.GRUPOS_PADRAO["Renda basica e transferencia"],
        "Economia solidaria": busca.GRUPOS_PADRAO["Economia solidaria"],
    }

    print("\n" + "=" * 70)
    print("ELEICAO GERAL 2026 - MENCOES POR EIXO")
    print("=" * 70)
    resultados = {}
    for eixo, termos in eixos.items():
        achados = procurar(registros, termos)
        resultados[eixo] = achados
        gov = sum(1 for a in achados if a["cargo"] == "governador")
        pres = sum(1 for a in achados if a["cargo"] == "presidente")
        print(f"{eixo:.<34} {len(achados):>3}  "
              f"(governador {gov}, presidente {pres})")

    print("\n" + "-" * 70)
    print("QUEM CITA MOEDA SOCIAL/MUNICIPAL")
    print("-" * 70)
    for achado in resultados["Moeda municipal/social"]:
        print(f"  {achado['nome'][:26]:<28}{achado['uf']:<4}{achado['partido']:<10}"
              f"{achado['ocorrencias']:>2}x  [{achado['termos'][:40]}]")
        recorte = trecho(registros, achado["id"], achado["termos"].split(",")[0].strip())
        if recorte:
            print(f"      {recorte[:180]}")

    print("\n" + "-" * 70)
    print("ECONOMIA SOLIDARIA - top 12")
    print("-" * 70)
    for achado in resultados["Economia solidaria"][:12]:
        print(f"  {achado['nome'][:26]:<28}{achado['uf']:<4}{achado['partido']:<10}"
              f"{achado['ocorrencias']:>3}x")

    print("\n" + "-" * 70)
    print("RENDA BASICA - top 12")
    print("-" * 70)
    for achado in resultados["Renda basica e transferencia"][:12]:
        print(f"  {achado['nome'][:26]:<28}{achado['uf']:<4}{achado['partido']:<10}"
              f"{achado['ocorrencias']:>3}x")

    # exportacao
    import csv
    saida = os.path.join(RAIZ, "dados", "correlacao", "eleicoes2026_mencoes.csv")
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    with open(saida, "w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(["Eixo", "Cargo", "UF", "Candidato", "Partido",
                           "Termos", "Mencoes"])
        for eixo, achados in resultados.items():
            for a in achados:
                escritor.writerow([eixo, a["cargo"], a["uf"], a["nome"],
                                   a["partido"], a["termos"], a["ocorrencias"]])
    print(f"\nGravado: {os.path.relpath(saida, RAIZ)}")


if __name__ == "__main__":
    main()
