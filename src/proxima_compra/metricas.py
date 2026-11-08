"""Métricas de recomendação: recall@k, NDCG@k, acerto@k, cobertura de catálogo e intervalo por bootstrap."""

from __future__ import annotations

import math

import numpy as np


def recall_at_k(sugeridos: list[int], alvo: set[int], k: int = 10) -> float:
    if not alvo:
        return 0.0
    return len(set(sugeridos[:k]) & alvo) / len(alvo)


def ndcg_at_k(sugeridos: list[int], alvo: set[int], k: int = 10) -> float:
    if not alvo:
        return 0.0
    dcg = sum(1.0 / math.log2(r + 2) for r, i in enumerate(sugeridos[:k]) if i in alvo)
    ideal = sum(1.0 / math.log2(r + 2) for r in range(min(len(alvo), k)))
    return dcg / ideal


def acerto_at_k(sugeridos: list[int], alvo: set[int], k: int = 10) -> float:
    """1 se pelo menos um dos k sugeridos foi comprado."""
    return 1.0 if set(sugeridos[:k]) & alvo else 0.0


def cobertura(listas: list[list[int]], tamanho_catalogo: int, k: int = 10) -> float:
    """Fração do catálogo que aparece em pelo menos uma lista de k sugestões."""
    distintos = {i for lista in listas for i in lista[:k]}
    return len(distintos) / max(tamanho_catalogo, 1)


def por_caso(listas: list[list[int]], alvos: list[set[int]], k: int = 10) -> dict[str, np.ndarray]:
    return {
        "recall": np.array([recall_at_k(s, a, k) for s, a in zip(listas, alvos)]),
        "ndcg": np.array([ndcg_at_k(s, a, k) for s, a in zip(listas, alvos)]),
        "acerto": np.array([acerto_at_k(s, a, k) for s, a in zip(listas, alvos)]),
    }


def bootstrap_ic(valores: np.ndarray, n: int = 1000, semente: int = 42) -> tuple[float, float]:
    """Intervalo de 95% da média, sorteando os casos com reposição."""
    rng = np.random.default_rng(semente)
    idx = rng.integers(0, len(valores), size=(n, len(valores)))
    medias = valores[idx].mean(axis=1)
    return float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5))


def bootstrap_diferenca(a: np.ndarray, b: np.ndarray, n: int = 1000, semente: int = 42) -> dict:
    """Diferença pareada (a - b) com intervalo de 95% e a fração de sorteios em que a <= b."""
    rng = np.random.default_rng(semente)
    d = a - b
    idx = rng.integers(0, len(d), size=(n, len(d)))
    medias = d[idx].mean(axis=1)
    return {
        "media": float(d.mean()),
        "ic95": [float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5))],
        "p_sem_ganho": float((medias <= 0).mean()),
    }
