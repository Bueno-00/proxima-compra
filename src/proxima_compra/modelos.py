"""Modelos simples de recomendação (sem rede neural).

Todos seguem a mesma interface:
  ajustar(interim, corte)            usa só eventos com dia < corte
  pontuar(caso) -> dict[item, nota]  nota maior = recomendar antes
  motivo(caso, item) -> dict         o "porquê" de cada sugestão (código + dados), para a página

Os motivos são códigos com parâmetros; a página traduz para português ou inglês.
"""

from __future__ import annotations

import heapq
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from .casos import Caso
from .dados import conectar

DIAS_POPULARIDADE = 28


def top_k(notas: dict[int, float], k: int = 10, excluir: set[int] | None = None) -> list[int]:
    if excluir:
        notas = {i: s for i, s in notas.items() if i not in excluir}
    return [i for i, _ in heapq.nlargest(k, notas.items(), key=lambda x: (x[1], -x[0]))]


def completar(lista: list[int], reserva: list[int], k: int = 10) -> list[int]:
    """Completa a lista com a reserva (mais vendidos) até ter k itens, sem repetir."""
    vistos = set(lista)
    saida = list(lista)
    for i in reserva:
        if len(saida) >= k:
            break
        if i not in vistos:
            saida.append(i)
            vistos.add(i)
    return saida


class Popularidade:
    nome = "popularidade"

    def ajustar(self, interim: Path, corte) -> Popularidade:
        con = conectar()
        compras = con.execute(
            f"""select item, count(*) from '{Path(interim) / 'compras.parquet'}'
                where dia < '{corte}' and dia >= date '{corte}' - interval {DIAS_POPULARIDADE} day
                group by item"""
        ).fetchall()
        views = con.execute(
            f"""select item, count(*) from '{Path(interim) / 'views.parquet'}'
                where dia < '{corte}' and dia >= date '{corte}' - interval {DIAS_POPULARIDADE} day
                group by item"""
        ).fetchall()
        con.close()
        self.compras = Counter(dict(compras))
        self.views = Counter(dict(views))
        notas = {i: self.compras.get(i, 0) + 1e-4 * self.views.get(i, 0) for i in set(self.compras) | set(self.views)}
        self.ranking = top_k(notas, 500)
        self.posicao = {i: r for r, i in enumerate(self.ranking)}
        return self

    def pontuar(self, caso: Caso) -> dict[int, float]:
        return {i: 1.0 / (1 + r) for r, i in enumerate(self.ranking[:50])}

    def motivo(self, caso: Caso, item: int) -> dict:
        return {"cod": "pop", "pos": self.posicao.get(item, 999) + 1, "n": self.compras.get(item, 0)}


class Visto:
    """'O que você já viu ou comprou': repete o histórico, mais recente primeiro."""

    nome = "visto"

    def ajustar(self, interim: Path, corte) -> Visto:
        return self

    def pontuar(self, caso: Caso) -> dict[int, float]:
        notas: dict[int, float] = defaultdict(float)
        atuais = [v[0] for v in caso.vistos if v[3]]
        recentes = list(dict.fromkeys(reversed(atuais)))  # distintos, do mais recente ao mais antigo
        for r, item in enumerate(recentes):
            notas[item] += 2.0 / (1 + r)
        for item, _dia, _t, atual in caso.vistos:
            notas[item] += 1.0 if atual else 0.3
        for item, _dia in caso.compras_antes:
            notas[item] += 0.5
        return dict(notas)

    def motivo(self, caso: Caso, item: int) -> dict:
        n_atual = sum(1 for v in caso.vistos if v[0] == item and v[3])
        n_antes = sum(1 for v in caso.vistos if v[0] == item and not v[3])
        comprou = [d for i, d in caso.compras_antes if i == item]
        if comprou:
            return {"cod": "comprou", "dia": comprou[-1].isoformat(), "n": len(comprou)}
        if n_atual:
            return {"cod": "viu_agora", "n": n_atual}
        if n_antes:
            ultimo = max(v[1] for v in caso.vistos if v[0] == item)
            return {"cod": "viu_antes", "n": n_antes, "dia": ultimo.isoformat()}
        return {"cod": "pop"}


def _peso_vistos(caso: Caso) -> dict[int, float]:
    """Peso de cada item visto: visita atual pesa mais, e os mais recentes pesam mais."""
    pesos: dict[int, float] = defaultdict(float)
    atuais = [v[0] for v in caso.vistos if v[3]]
    recentes = list(dict.fromkeys(reversed(atuais)))
    for r, item in enumerate(recentes):
        pesos[item] += 1.0 / (1 + 0.3 * r)
    for item, _d, _t, atual in caso.vistos:
        if not atual:
            pesos[item] = max(pesos[item], 0.3)
    for item, _d in caso.compras_antes:
        pesos[item] = max(pesos[item], 0.5)
    return dict(pesos)


class Coocorrencia:
    """Item a item: 'quem viu o que você viu também comprou (ou viu) isto'.

    VP[h, i] = sessões em que h foi visto e i foi comprado (inclui h = i: taxa de conversão de h).
    VV[h, i] = sessões em que h e i foram vistos juntos (h != i), normalizado como cosseno.
    nota(i) = soma sobre os itens h do histórico de peso(h) * (VP[h,i] / (n_vistas(h) + a) + b * VV_cos[h,i])
    """

    nome = "coocorrencia"

    def __init__(self, a: float = 5.0, b: float = 0.3, max_itens_sessao: int = 100):
        self.a, self.b, self.max_itens = a, b, max_itens_sessao

    def ajustar(self, interim: Path, corte) -> Coocorrencia:
        interim = Path(interim)
        con = conectar()
        n_itens = con.execute(f"select max(item) + 1 from '{interim / 'produtos.parquet'}'").fetchone()[0]
        vistas = con.execute(
            f"""select sessao, list(distinct item) from '{interim / 'views.parquet'}'
                where dia < '{corte}' group by sessao"""
        ).fetchall()
        compras = dict(
            con.execute(
                f"""select sessao, list(distinct item) from '{interim / 'compras.parquet'}'
                    where dia < '{corte}' group by sessao"""
            ).fetchall()
        )
        con.close()
        sessoes = sorted({s for s, _ in vistas} | set(compras))
        idx = {s: k for k, s in enumerate(sessoes)}
        lin_v, col_v, lin_p, col_p = [], [], [], []
        for s, itens in vistas:
            itens = itens[: self.max_itens]
            lin_v.extend([idx[s]] * len(itens))
            col_v.extend(itens)
        for s, itens in compras.items():
            lin_p.extend([idx[s]] * len(itens))
            col_p.extend(itens)
        shape = (len(sessoes), n_itens)
        xv = sp.csr_matrix((np.ones(len(lin_v), np.float32), (lin_v, col_v)), shape=shape)
        xp = sp.csr_matrix((np.ones(len(lin_p), np.float32), (lin_p, col_p)), shape=shape)
        xv.data[:] = 1.0
        xp.data[:] = 1.0
        self.n_vistas = np.asarray(xv.sum(axis=0)).ravel()
        self.n_compras = np.asarray(xp.sum(axis=0)).ravel()
        vp = (xv.T @ xp).tocsr()
        vv = (xv.T @ xv).tocsr()
        vv.setdiag(0)
        vv.eliminate_zeros()
        self.vp_bruto = vp
        inv = 1.0 / (self.n_vistas + self.a)
        self.vp = sp.diags(inv.astype(np.float32)) @ vp
        raiz = np.sqrt(np.maximum(self.n_vistas, 1)).astype(np.float32)
        self.vv = (sp.diags(1 / raiz) @ vv @ sp.diags(1 / raiz)).tocsr()
        self.vv_bruto = vv
        self.matriz = (self.vp + self.b * self.vv).tocsr()
        return self

    def pontuar(self, caso: Caso) -> dict[int, float]:
        pesos = _peso_vistos(caso)
        if not pesos:
            return {}
        itens = np.fromiter(pesos.keys(), dtype=np.int64)
        w = np.fromiter(pesos.values(), dtype=np.float32)
        validos = itens < self.matriz.shape[0]
        itens, w = itens[validos], w[validos]
        if len(itens) == 0:
            return {}
        linha = sp.csr_matrix(w[None, :]) @ self.matriz[itens]
        linha = linha.tocoo()
        return dict(zip(linha.col.tolist(), linha.data.tolist()))

    def motivo(self, caso: Caso, item: int) -> dict:
        pesos = _peso_vistos(caso)
        melhor, valor, tipo = None, 0.0, "cooc_viu"
        for h, w in pesos.items():
            if h >= self.matriz.shape[0]:
                continue
            vp = self.vp[h, item] * w
            vv = self.b * self.vv[h, item] * w
            if vp > valor:
                melhor, valor, tipo = h, vp, ("conversao" if h == item else "cooc_comprou")
            if vv > valor:
                melhor, valor, tipo = h, vv, "cooc_viu"
        if melhor is None:
            return {"cod": "pop"}
        if tipo == "conversao":
            return {"cod": "conversao", "n": int(self.vp_bruto[item, item]), "de": int(self.n_vistas[item])}
        if tipo == "cooc_comprou":
            return {"cod": "cooc_comprou", "item": int(melhor), "n": int(self.vp_bruto[melhor, item])}
        return {"cod": "cooc_viu", "item": int(melhor), "n": int(self.vv_bruto[melhor, item])}


class IndiceTexto:
    """BM25 simples entre os termos (cifrados) da busca e os termos (cifrados) do nome do produto."""

    def __init__(self, interim: Path, k1: float = 1.2, b: float = 0.75):
        con = conectar()
        linhas = con.execute(f"select item, nome from '{Path(interim) / 'produtos.parquet'}'").fetchall()
        con.close()
        self.postings: dict[int, list[tuple[int, int]]] = defaultdict(list)
        tamanhos = {}
        self.nomes: dict[int, set[int]] = {}
        for item, nome in linhas:
            tamanhos[item] = len(nome)
            self.nomes[item] = set(nome)
            for termo, tf in Counter(nome).items():
                self.postings[termo].append((item, tf))
        n = len(linhas)
        self.media = sum(tamanhos.values()) / max(n, 1)
        self.tamanhos = tamanhos
        self.idf = {t: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}
        self.k1, self.b = k1, b

    def buscar(self, termos: list[int], k: int = 50) -> dict[int, float]:
        chave = (tuple(sorted(set(termos))), k)
        cache = self.__dict__.setdefault("_cache", {})
        if chave not in cache:
            cache[chave] = self._buscar(termos, k)
        return cache[chave]

    def _buscar(self, termos: list[int], k: int) -> dict[int, float]:
        notas: dict[int, float] = defaultdict(float)
        for termo in set(termos):
            if termo not in self.postings or len(self.postings[termo]) > 20000:
                continue
            idf = self.idf[termo]
            for item, tf in self.postings[termo]:
                norm = self.k1 * (1 - self.b + self.b * self.tamanhos[item] / self.media)
                notas[item] += idf * tf * (self.k1 + 1) / (tf + norm)
        return dict(heapq.nlargest(k, notas.items(), key=lambda x: x[1]))


class Busca:
    """'O que você pesquisou': produtos que a loja mostrou nas suas buscas, os que você clicou
    e os que têm no nome os termos que você digitou."""

    nome = "busca"

    def __init__(self, peso_clique: float = 2.0, peso_texto: float = 0.3, decaimento: float = 0.7):
        self.peso_clique, self.peso_texto, self.decaimento = peso_clique, peso_texto, decaimento
        self.indice: IndiceTexto | None = None

    def ajustar(self, interim: Path, corte) -> Busca:
        if self.peso_texto > 0 and self.indice is None:
            self.indice = IndiceTexto(interim)
        return self

    def _pesos_buscas(self, caso: Caso) -> list[float]:
        n = len(caso.buscas)
        pesos = []
        for j, b in enumerate(caso.buscas):
            base = 1.0 if b.atual else 0.3
            pesos.append(base * self.decaimento ** (n - 1 - j) if b.atual else base)
        return pesos

    def pontuar(self, caso: Caso) -> dict[int, float]:
        notas: dict[int, float] = defaultdict(float)
        for b, w in zip(caso.buscas, self._pesos_buscas(caso)):
            for pos, item in enumerate(b.mostrados, start=1):
                notas[item] += w / math.log2(pos + 1)
            for item in b.cliques:
                notas[item] += w * self.peso_clique
            if b.texto and self.indice is not None and self.peso_texto > 0:
                achados = self.indice.buscar(b.termos, 30)
                if achados:
                    maior = max(achados.values())
                    for item, s in achados.items():
                        notas[item] += w * self.peso_texto * s / maior
        return dict(notas)

    def motivo(self, caso: Caso, item: int) -> dict:
        melhor = None
        for b, w in zip(caso.buscas, self._pesos_buscas(caso)):
            if item in b.cliques:
                return {"cod": "busca_clique", "dia": b.dia.isoformat(), "atual": b.atual,
                        "termos": b.termos[:4], "cat": b.categoria}
            if item in b.mostrados:
                pos = b.mostrados.index(item) + 1
                valor = w / math.log2(pos + 1)
                if melhor is None or valor > melhor[0]:
                    melhor = (valor, {"cod": "busca_lista", "pos": pos, "dia": b.dia.isoformat(),
                                      "atual": b.atual, "termos": b.termos[:4], "cat": b.categoria})
        if melhor:
            return melhor[1]
        termos = [t for b in caso.buscas if b.texto for t in b.termos]
        if self.indice is not None and item in self.indice.nomes:
            comuns = [t for t in dict.fromkeys(termos) if t in self.indice.nomes[item]]
            if comuns:
                return {"cod": "busca_texto", "termos": comuns[:4]}
        return {"cod": "pop"}
