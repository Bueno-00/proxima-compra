"""Aviso "o que você costuma comprar está em promoção".

A base pública não tem histórico de preço nem promoção, então isto NÃO entra na medição.
A função está pronta para receber a tabela de preços de uma loja real; na página de demonstração
ela roda com preços simulados (marcados como simulação).
"""

from __future__ import annotations

import hashlib
from collections import Counter

from .casos import Caso

PESO_COMPRA, PESO_VISTA_ANTES, PESO_VISTA_AGORA = 3.0, 1.0, 0.5


def habituais(caso: Caso) -> Counter:
    """Quanto cada produto 'é da pessoa': compras pesam mais que visitas antigas, que pesam mais que a de hoje."""
    c: Counter = Counter()
    for item, _dia in caso.compras_antes:
        c[item] += PESO_COMPRA
    for item, _dia, _t, atual in caso.vistos:
        c[item] += PESO_VISTA_AGORA if atual else PESO_VISTA_ANTES
    return c


def alertas_promocao(caso: Caso, preco_hoje: dict[int, float], preco_normal: dict[int, float],
                     desconto_minimo: float = 0.10, maximo: int = 3) -> list[dict]:
    """Produtos habituais da pessoa com preço de hoje pelo menos `desconto_minimo` abaixo do normal."""
    alertas = []
    for item, peso in habituais(caso).most_common():
        normal, hoje = preco_normal.get(item), preco_hoje.get(item)
        if not normal or hoje is None or normal <= 0:
            continue
        desconto = 1 - hoje / normal
        if desconto >= desconto_minimo:
            alertas.append({"item": item, "desconto": round(desconto, 3), "peso": peso,
                            "comprou": any(i == item for i, _ in caso.compras_antes)})
        if len(alertas) >= maximo:
            break
    return alertas


def precos_simulados(itens: list[int], fracao_em_promocao: float = 0.25, semente: str = "proxima-compra"):
    """Preços de mentira, estáveis entre execuções: uma fração dos itens ganha 10% a 30% de desconto."""
    normal, hoje = {}, {}
    for item in itens:
        h = int(hashlib.sha256(f"{semente}:{item}".encode()).hexdigest()[:8], 16)
        base = 5 + (h % 9000) / 100  # R$ 5,00 a R$ 94,99
        normal[item] = round(base, 2)
        if (h >> 8) % 1000 < fracao_em_promocao * 1000:
            hoje[item] = round(base * (1 - (0.10 + ((h >> 4) % 21) / 100)), 2)
        else:
            hoje[item] = normal[item]
    return hoje, normal
