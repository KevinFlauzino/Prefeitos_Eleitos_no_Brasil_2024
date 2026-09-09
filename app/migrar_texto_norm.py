"""
Acrescenta a coluna texto_norm ao banco existente.

A busca compara sempre o texto sem acentos e em minusculas. Guardar essa versao
pronta evita normalizar 176 MB a cada consulta e derruba o tempo de resposta.

Uso:
    python app/migrar_texto_norm.py
"""

import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import busca  # noqa: E402


def migrar():
    if not busca.banco_existe():
        print("ERRO: banco nao encontrado. Rode app/construir_bd.py antes.")
        return

    con = sqlite3.connect(busca.BANCO)
    colunas = {linha[1] for linha in con.execute("PRAGMA table_info(municipios)")}

    if "texto_norm" not in colunas:
        print("Criando coluna texto_norm...")
        con.execute("ALTER TABLE municipios ADD COLUMN texto_norm TEXT DEFAULT ''")
        con.commit()

    pendentes = con.execute("""
        SELECT COUNT(*) FROM municipios
        WHERE caracteres > 0 AND (texto_norm IS NULL OR texto_norm = '')
    """).fetchone()[0]
    print(f"{pendentes} municipios para normalizar.")
    if not pendentes:
        print("Nada a fazer.")
        con.close()
        return

    inicio = time.time()
    feitos = 0
    leitura = con.execute("""
        SELECT id, texto FROM municipios
        WHERE caracteres > 0 AND (texto_norm IS NULL OR texto_norm = '')
    """).fetchall()

    for identificador, texto in leitura:
        con.execute("UPDATE municipios SET texto_norm = ? WHERE id = ?",
                    (busca.normalizar(texto or ""), identificador))
        feitos += 1
        if feitos % 500 == 0:
            print(f"  {feitos}/{pendentes} ({time.time() - inicio:.0f}s)", flush=True)

    con.commit()
    print(f"  {feitos}/{pendentes} concluido em {time.time() - inicio:.0f}s")

    print("Compactando o arquivo (VACUUM)...")
    con.execute("VACUUM")
    con.close()
    tamanho = os.path.getsize(busca.BANCO) / (1024 * 1024)
    print(f"Pronto. Banco com {tamanho:.0f} MB.")


if __name__ == "__main__":
    migrar()
