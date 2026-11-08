"""Testes com uma base minúscula inventada no formato da Diginetica (não precisa baixar nada)."""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
import pytest

from proxima_compra.casos import Busca as EventoBusca
from proxima_compra.casos import Caso, Divisao, montar_casos
from proxima_compra.dados import converter
from proxima_compra.metricas import acerto_at_k, bootstrap_diferenca, cobertura, ndcg_at_k, recall_at_k
from proxima_compra.modelos import Busca, Coocorrencia, Popularidade, Visto, completar, top_k
from proxima_compra.pares import resumo_pares
from proxima_compra.promocao import alertas_promocao, precos_simulados


def _escrever(raw: Path, nome: str, linhas: list[str]) -> None:
    (raw / nome).write_text("\n".join(linhas) + "\n")


@pytest.fixture(scope="module")
def base(tmp_path_factory) -> Path:
    raw = tmp_path_factory.mktemp("raw")
    # sessões 1 a 3 em março (treino), sessão 10 em abril (caso), sessão 11 em abril sem compra
    _escrever(raw, "train-item-views.csv", [
        "sessionId;userId;itemId;timeframe;eventdate",
        "1;NA;100;10;2016-03-20", "1;NA;101;20;2016-03-20",
        "2;NA;100;10;2016-03-21", "2;NA;102;20;2016-03-21",
        "3;7;101;10;2016-03-22", "3;7;103;20;2016-03-22",
        "10;7;100;10;2016-04-02", "10;7;104;20;2016-04-02", "10;7;105;900;2016-04-02",
        "11;NA;100;10;2016-04-03",
    ])
    _escrever(raw, "train-purchases.csv", [
        "sessionId;userId;timeframe;eventdate;ordernumber;itemId",
        "1;NA;30;2016-03-20;1;101", "2;NA;30;2016-03-21;2;101", "3;7;30;2016-03-22;3;103",
        "10;7;500;2016-04-02;4;101", "10;7;500;2016-04-02;4;104",
    ])
    _escrever(raw, "train-queries.csv", [
        "queryId;sessionId;userId;timeframe;duration;eventdate;searchstring.tokens;categoryId;items;is.test",
        "1;1;NA;5;10;2016-03-20;;9;100,101,102;FALSE",
        "2;10;7;15;10;2016-04-02;55,66;0;104,106,101;FALSE",
        "3;10;7;800;10;2016-04-02;;9;105,100;FALSE",
        "4;3;7;5;10;2016-03-22;77;0;103,101;FALSE",
    ])
    _escrever(raw, "train-clicks.csv", ["queryId;timeframe;itemId", "2;16;104", "3;801;105"])
    _escrever(raw, "products.csv", [
        "itemId;pricelog2;product.name.tokens",
        "100;5;1,2", "101;6;2,3", "102;5;4", "103;7;77,8", "104;6;55,9", "105;4;10", "106;6;66,11",
    ])
    _escrever(raw, "product-categories.csv", [
        "itemId;categoryId", "100;9", "101;9", "102;9", "103;8", "104;8", "105;9", "106;8",
    ])
    interim = raw.parent / "interim"
    linhas = converter(raw, interim)
    assert linhas["views"] == 10 and linhas["compras"] == 5 and linhas["buscas"] == 4
    return interim


DIV = Divisao("t", dt.date(2016, 4, 1), dt.date(2016, 4, 1), dt.date(2016, 4, 30))


def test_caso_corta_no_pagamento_e_nao_ve_o_futuro(base):
    casos = montar_casos(base, DIV)
    assert [c.sessao for c in casos] == [10]  # a sessão 11 não comprou
    c = casos[0]
    assert c.alvo == {101, 104}
    atuais = [v[0] for v in c.vistos if v[3]]
    assert atuais == [100, 104]  # o 105 foi visto depois de pagar (t=900 > 500)
    antes = [v[0] for v in c.vistos if not v[3]]
    assert sorted(antes) == [101, 103]  # visita de março da mesma pessoa
    assert c.compras_antes and c.compras_antes[0][0] == 103
    buscas_atuais = [b for b in c.buscas if b.atual]
    assert len(buscas_atuais) == 1 and buscas_atuais[0].termos == [55, 66]  # a busca 3 foi depois de pagar
    assert buscas_atuais[0].cliques == [104]


def test_modelos_e_metricas(base):
    c = montar_casos(base, DIV)[0]
    pop = Popularidade().ajustar(base, DIV.corte)
    assert pop.ranking[0] == 101  # comprado 2 vezes em março
    visto = top_k(Visto().pontuar(c), 10)
    assert visto[0] == 104  # o mais recente desta visita
    cooc = Coocorrencia(a=1.0, b=0.0).ajustar(base, DIV.corte)
    notas = cooc.pontuar(c)
    assert notas.get(101, 0) > 0  # quem viu o 100 comprou o 101
    assert cooc.motivo(c, 101)["cod"] in {"cooc_comprou", "conversao"}
    busca = Busca().ajustar(base, DIV.corte)
    nb = busca.pontuar(c)
    assert top_k(nb, 1) == [104]  # mostrado em 1º e clicado
    assert busca.motivo(c, 104)["cod"] == "busca_clique"
    assert busca.motivo(c, 106)["cod"] == "busca_lista"
    assert 105 not in nb  # a busca 3 aconteceu depois de pagar
    lista = completar(top_k(nb, 10), pop.ranking)
    assert len(lista) == len(set(lista))
    assert recall_at_k(lista, c.alvo) == 1.0


def test_metricas_valores_conhecidos():
    assert recall_at_k([1, 2, 3], {2, 9}) == 0.5
    assert math.isclose(ndcg_at_k([1, 2], {1}), 1.0)
    assert math.isclose(ndcg_at_k([2, 1], {1}), 1 / math.log2(3))
    assert acerto_at_k([5, 6], {6}) == 1.0 and acerto_at_k([5], {6}) == 0.0
    assert cobertura([[1, 2], [2, 3]], 10) == 0.3
    d = bootstrap_diferenca(np.ones(50), np.zeros(50))
    assert d["media"] == 1.0 and d["ic95"][0] == 1.0 and d["p_sem_ganho"] == 0.0


def test_aviso_de_promocao():
    caso = Caso(1, 7, dt.date(2016, 5, 2), 100, {9},
                vistos=[(5, dt.date(2016, 4, 1), 1, False), (6, dt.date(2016, 5, 2), 1, True)],
                buscas=[EventoBusca(1, dt.date(2016, 5, 2), True, [], 3, [5, 6], [])],
                compras_antes=[(5, dt.date(2016, 4, 1))])
    alertas = alertas_promocao(caso, {5: 8.0, 6: 10.0}, {5: 10.0, 6: 10.0})
    assert [a["item"] for a in alertas] == [5] and alertas[0]["comprou"] and alertas[0]["desconto"] == 0.2
    hoje, normal = precos_simulados(list(range(1000)))
    em_promo = [i for i in normal if hoje[i] < normal[i]]
    assert 150 < len(em_promo) < 350  # cerca de 25%
    assert precos_simulados([1, 2]) == precos_simulados([1, 2])  # estável


def test_pagina_tem_marcador_e_sem_travessao():
    html = (Path(__file__).resolve().parents[1] / "site" / "modelo.html").read_text()
    assert "__DADOS__" in html
    assert "—" not in html and "–" not in html


def test_demo_json_se_existir():
    demo = Path(__file__).resolve().parents[1] / "reports" / "demo.json"
    if not demo.exists():
        pytest.skip("rode `pc avaliar` para gerar reports/demo.json")
    dados = json.loads(demo.read_text())
    assert len(dados["visitas"]) >= 30
    for v in dados["visitas"]:
        for leitura in ("geral", "descoberta"):
            for nome in dados["ordem"]:
                lista = v[leitura][nome]
                assert len(lista) == 10 and len({x["item"] for x in lista}) == 10
                assert all(str(x["item"]) in dados["produtos"] for x in lista)
                assert all((x["item"] in v["comprou"]) == x["ok"] for x in lista)


def test_pares_de_compra_contam_so_antes_do_corte(base):
    r = resumo_pares(base, dt.date(2016, 5, 1))
    assert r["pedidos"] == 4 and r["pedidos_2_ou_mais"] == 1 and r["maior_pedido"] == 2
    assert r["pares_no_mesmo_pedido"] == {"pares": 1, "pares_2": 0, "pares_3": 0}
    v = r["visto_e_comprado_na_visita"]
    assert v["pares"] > 0 and v["pares_2"] >= 1  # 100 visto e 101 comprado aparece nas sessões 1 e 10
    cedo = resumo_pares(base, dt.date(2016, 4, 1))
    assert cedo["pedidos"] == 3 and cedo["pedidos_2_ou_mais"] == 0
