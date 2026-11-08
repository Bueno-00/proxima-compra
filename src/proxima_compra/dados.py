"""Leitura da base Diginetica (CIKM Cup 2016, trilha 2) e conversão para Parquet.

Os CSVs originais ficam em data/raw/ (não vão para o git). Este módulo só lê, tipa e grava
cópias em Parquet em data/interim/, para as outras etapas consultarem rápido com DuckDB.

Arquivos de origem (separador ";", nulo = "NA"):
  train-item-views.csv   sessionId;userId;itemId;timeframe;eventdate
  train-purchases.csv    sessionId;userId;timeframe;eventdate;ordernumber;itemId
  train-queries.csv      queryId;sessionId;userId;timeframe;duration;eventdate;searchstring.tokens;
                         categoryId;items;is.test
  train-clicks.csv       queryId;timeframe;itemId
  products.csv           itemId;pricelog2;product.name.tokens
  product-categories.csv itemId;categoryId

"timeframe" é o tempo em milissegundos desde o início da sessão; "eventdate" é o dia.
As palavras dos nomes e das buscas vêm trocadas por números (a loja cifrou para proteger os dados).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

ARQUIVOS = [
    "train-item-views.csv",
    "train-purchases.csv",
    "train-queries.csv",
    "train-clicks.csv",
    "products.csv",
    "product-categories.csv",
]


def conectar(memoria: str = "2GB", threads: int = 2) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{memoria}'; SET threads={threads}; SET preserve_insertion_order=false")
    con.execute("SET enable_progress_bar=false")
    return con


def _csv(raw: Path, nome: str, tipos: str = "") -> str:
    extra = f", types={{{tipos}}}" if tipos else ""
    return f"read_csv('{raw / nome}', delim=';', header=true, nullstr='NA'{extra})"


def converter(raw: Path, interim: Path, forcar: bool = False) -> dict[str, int]:
    """Grava os 6 Parquets em `interim`. Devolve o número de linhas de cada um."""
    raw, interim = Path(raw), Path(interim)
    faltando = [a for a in ARQUIVOS if not (raw / a).exists()]
    if faltando:
        raise FileNotFoundError(f"Faltam arquivos em {raw}: {faltando}. Rode `make baixar`.")
    interim.mkdir(parents=True, exist_ok=True)
    con = conectar()
    consultas = {
        "views": f"""select sessionId::BIGINT sessao, userId::BIGINT usuario, itemId::BIGINT item,
                     timeframe::BIGINT t, eventdate::DATE dia
                     from {_csv(raw, 'train-item-views.csv', "'userId':'BIGINT'")}""",
        "compras": f"""select sessionId::BIGINT sessao, userId::BIGINT usuario, itemId::BIGINT item,
                       timeframe::BIGINT t, eventdate::DATE dia, ordernumber::BIGINT pedido
                       from {_csv(raw, 'train-purchases.csv', "'userId':'BIGINT'")}""",
        "buscas": f"""select queryId::BIGINT busca, sessionId::BIGINT sessao, userId::BIGINT usuario,
                      timeframe::BIGINT t, eventdate::DATE dia,
                      case when "searchstring.tokens" is null or "searchstring.tokens" = '' then []::BIGINT[]
                           else string_split("searchstring.tokens", ',')::BIGINT[] end termos,
                      categoryId::BIGINT categoria,
                      case when items is null or items = '' then []::BIGINT[]
                           else string_split(items, ',')::BIGINT[] end mostrados
                      from {_csv(raw, 'train-queries.csv',
                                 "'userId':'BIGINT','searchstring.tokens':'VARCHAR','items':'VARCHAR'")}""",
        "cliques": f"""select queryId::BIGINT busca, timeframe::BIGINT t, itemId::BIGINT item
                       from {_csv(raw, 'train-clicks.csv')}""",
        "produtos": f"""select p.itemId::BIGINT item, p.pricelog2::INT preco_nivel,
                        case when p."product.name.tokens" is null then []::BIGINT[]
                             else string_split(p."product.name.tokens", ',')::BIGINT[] end nome,
                        c.categoryId::BIGINT categoria
                        from {_csv(raw, 'products.csv', "'product.name.tokens':'VARCHAR'")} p
                        left join {_csv(raw, 'product-categories.csv')} c using (itemId)""",
    }
    linhas = {}
    for nome, sql in consultas.items():
        destino = interim / f"{nome}.parquet"
        if forcar or not destino.exists():
            con.execute(f"copy ({sql}) to '{destino}' (format parquet, compression zstd)")
        linhas[nome] = con.execute(f"select count(*) from '{destino}'").fetchone()[0]
    con.close()
    return linhas
