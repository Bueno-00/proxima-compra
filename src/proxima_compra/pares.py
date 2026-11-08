"""Quanto a base permite montar um "compre junto": pares de produtos comprados no mesmo pedido.

Não é uma medida de acerto. É só a contagem do que existe nos pedidos que o modelo conhece (antes do teste),
para dizer com honestidade se há pares repetidos o bastante para sugerir um combo.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .dados import conectar


def resumo_pares(interim: Path, ate: dt.date = dt.date(2016, 5, 1)) -> dict:
    """Conta pedidos e pares (comprados juntos; visto e comprado na mesma visita) antes de `ate`."""
    interim = Path(interim)
    compras, views = interim / "compras.parquet", interim / "views.parquet"
    con = conectar()
    filtro = f"dia < date '{ate.isoformat()}'"
    base = f"(select distinct pedido, item from '{compras}' where {filtro})"
    pedidos, com_2, maior = con.execute(f"""
        with p as (select pedido, count(*) n from {base} group by 1)
        select count(*), coalesce(sum(case when n >= 2 then 1 else 0 end), 0), coalesce(max(n), 0) from p
    """).fetchone()
    pares, pares_2, pares_3 = con.execute(f"""
        with b as {base},
        pr as (select a.item i, c.item j, count(*) n from b a join b c on a.pedido = c.pedido and a.item < c.item
               group by 1, 2)
        select count(*), coalesce(sum(case when n >= 2 then 1 else 0 end), 0),
               coalesce(sum(case when n >= 3 then 1 else 0 end), 0)
        from pr
    """).fetchone()
    visto = {"pares": 0, "pares_2": 0, "pares_3": 0}
    if views.exists():
        v = con.execute(f"""
            with vv as (select distinct sessao, item from '{views}' where {filtro}),
            cc as (select distinct sessao, item from '{compras}' where {filtro}),
            pr as (select vv.item i, cc.item j, count(*) n from vv join cc on vv.sessao = cc.sessao
                   and vv.item <> cc.item group by 1, 2)
            select count(*), coalesce(sum(case when n >= 2 then 1 else 0 end), 0),
                   coalesce(sum(case when n >= 3 then 1 else 0 end), 0)
            from pr
        """).fetchone()
        visto = {"pares": int(v[0]), "pares_2": int(v[1]), "pares_3": int(v[2])}
    con.close()
    return {
        "ate": ate.isoformat(),
        "pedidos": int(pedidos),
        "pedidos_2_ou_mais": int(com_2),
        "maior_pedido": int(maior),
        "pares_no_mesmo_pedido": {"pares": int(pares), "pares_2": int(pares_2), "pares_3": int(pares_3)},
        "visto_e_comprado_na_visita": visto,
    }
