"""Monta os casos de teste com divisão temporal.

Um "caso" é uma visita (sessão) em que a pessoa comprou. Cortamos a visita no momento da
primeira compra: tudo o que ela viu e pesquisou ANTES de pagar (nesta visita e, se estava
logada, nas visitas de dias anteriores) é a entrada; os produtos comprados nesta visita são a
resposta que o modelo precisa acertar.

Divisão temporal (nenhum modelo vê o futuro):
  validação: modelos treinados com tudo antes de 01/04/2016, casos de 01/04 a 30/04/2016
  teste:     modelos treinados com tudo antes de 01/05/2016, casos de 01/05 a 31/05/2016
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from .dados import conectar

MAX_MOSTRADOS = 200  # busca por texto registra ~20 itens; página de categoria registra até 200


@dataclass(frozen=True)
class Divisao:
    nome: str
    corte: dt.date  # treino usa dia < corte
    inicio: dt.date  # casos com dia em [inicio, fim]
    fim: dt.date


VALIDACAO = Divisao("validacao", dt.date(2016, 4, 1), dt.date(2016, 4, 1), dt.date(2016, 4, 30))
TESTE = Divisao("teste", dt.date(2016, 5, 1), dt.date(2016, 5, 1), dt.date(2016, 5, 31))


@dataclass
class Busca:
    t: int
    dia: dt.date
    atual: bool  # feita nesta visita (True) ou numa visita anterior (False)
    termos: list[int]
    categoria: int
    mostrados: list[int]
    cliques: list[int]

    @property
    def texto(self) -> bool:
        return len(self.termos) > 0


@dataclass
class Caso:
    sessao: int
    usuario: int | None
    dia: dt.date
    t0: int
    alvo: set[int]
    vistos: list[tuple[int, dt.date, int, bool]] = field(default_factory=list)  # (item, dia, t, atual)
    buscas: list[Busca] = field(default_factory=list)
    compras_antes: list[tuple[int, dt.date]] = field(default_factory=list)

    def itens_vistos(self) -> list[int]:
        """Itens vistos, do mais antigo ao mais recente (com repetição)."""
        return [v[0] for v in self.vistos]


def _ordenar_vistos(vistos):
    return sorted(vistos, key=lambda v: (v[1], 0 if not v[3] else 1, v[2]))


def montar_casos(interim: Path, divisao: Divisao) -> list[Caso]:
    interim = Path(interim)
    con = conectar()
    for nome in ("views", "compras", "buscas", "cliques"):
        con.execute(f"create view {nome} as select * from '{interim / (nome + '.parquet')}'")
    con.execute(
        f"""create temp table casos as
        select sessao, any_value(usuario) usuario, min(dia) dia, min(t) t0, list(distinct item) alvo
        from compras where dia between '{divisao.inicio}' and '{divisao.fim}' group by sessao"""
    )
    casos: dict[int, Caso] = {}
    for sessao, usuario, dia, t0, alvo in con.execute("select * from casos order by sessao").fetchall():
        casos[sessao] = Caso(sessao, usuario, dia, t0, set(alvo))

    # 1) o que ela viu nesta visita antes de pagar
    for sessao, item, dia, t in con.execute(
        "select v.sessao, v.item, v.dia, v.t from views v join casos c using (sessao) where v.t < c.t0"
    ).fetchall():
        casos[sessao].vistos.append((item, dia, t, True))

    # 2) buscas desta visita antes de pagar (com os cliques feitos antes de pagar)
    sql_buscas = f"""
        select c.sessao caso, b.busca, b.t, b.dia, b.termos, b.categoria,
               b.mostrados[1:{MAX_MOSTRADOS}] mostrados,
               coalesce((select list(k.item) from cliques k where k.busca = b.busca and k.t < c.t0), []) cliques,
               true atual
        from buscas b join casos c using (sessao) where b.t < c.t0"""
    # 3) visitas anteriores da mesma pessoa (só quem estava logada), em dias anteriores ao caso
    sql_buscas_antes = f"""
        select c.sessao caso, b.busca, b.t, b.dia, b.termos, b.categoria,
               b.mostrados[1:{MAX_MOSTRADOS}] mostrados,
               coalesce((select list(k.item) from cliques k where k.busca = b.busca), []) cliques,
               false atual
        from buscas b join casos c on b.usuario = c.usuario and b.dia < c.dia
        where c.usuario is not null"""
    for caso, _busca, t, dia, termos, cat, mostrados, cliques, atual in con.execute(
        f"{sql_buscas} union all {sql_buscas_antes}"
    ).fetchall():
        casos[caso].buscas.append(Busca(t, dia, atual, list(termos), int(cat or 0), list(mostrados), list(cliques)))

    for caso, item, dia, t in con.execute(
        """select c.sessao, v.item, v.dia, v.t from views v
           join casos c on v.usuario = c.usuario and v.dia < c.dia where c.usuario is not null"""
    ).fetchall():
        casos[caso].vistos.append((item, dia, t, False))
    for caso, item, dia in con.execute(
        """select c.sessao, p.item, p.dia from compras p
           join casos c on p.usuario = c.usuario and p.dia < c.dia where c.usuario is not null"""
    ).fetchall():
        casos[caso].compras_antes.append((item, dia))
    con.close()

    saida = []
    for c in casos.values():
        c.vistos = _ordenar_vistos(c.vistos)
        c.buscas.sort(key=lambda b: (b.dia, 0 if not b.atual else 1, b.t))
        c.compras_antes.sort(key=lambda x: x[1])
        if c.vistos or c.buscas or c.compras_antes:
            saida.append(c)
    return saida


def resumo_casos(casos: list[Caso]) -> dict:
    n = len(casos)
    return {
        "casos": n,
        "itens_alvo": sum(len(c.alvo) for c in casos),
        "logados": sum(1 for c in casos if c.usuario is not None),
        "com_compra_anterior": sum(1 for c in casos if c.compras_antes),
        "com_busca": sum(1 for c in casos if c.buscas),
        "com_busca_texto": sum(1 for c in casos if any(b.texto for b in c.buscas)),
        "com_visto": sum(1 for c in casos if c.vistos),
    }
