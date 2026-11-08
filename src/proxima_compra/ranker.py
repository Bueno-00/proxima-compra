"""Híbrido: junta os candidatos de todos os modelos e reordena com LightGBM (LambdaRank).

Duas versões, treinadas do mesmo jeito, para medir o efeito da busca:
  sem busca: candidatos e sinais de "o que viu/comprou", item a item, sequencial e mais vendidos
  com busca: os mesmos + candidatos e sinais das buscas (lista mostrada, clique, termos digitados)

Treina nos casos de validação (abril) e é medido nos casos de teste (maio).
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path

import lightgbm as lgb
import numpy as np

from .casos import Caso
from .dados import conectar
from .modelos import Busca, Coocorrencia, Popularidade, Visto, top_k
from .sequencial import Sequencial

FEATURES_BASE = [
    "visto_nota", "vistas_atual", "vistas_antes", "recencia", "comprou_antes",
    "cooc_vp", "cooc_vv", "cooc_rank", "seq_nota", "seq_rank",
    "pop_compras", "pop_vistas", "conversao", "preco_nivel", "mesma_categoria_vista",
    "caso_n_vistos", "caso_logado",
]
FEATURES_BUSCA = [
    "busca_nota", "busca_melhor_pos", "busca_vezes", "busca_clique", "busca_texto",
    "busca_ultima", "categoria_buscada", "caso_n_buscas", "caso_n_buscas_texto",
]


class Catalogo:
    def __init__(self, interim: Path):
        con = conectar()
        linhas = con.execute(f"select item, categoria, preco_nivel from '{Path(interim) / 'produtos.parquet'}'").fetchall()
        con.close()
        self.categoria = {i: int(c or 0) for i, c, _ in linhas}
        self.preco = {i: int(p or 0) for i, _, p in linhas}


class Hibrido:
    def __init__(self, com_busca: bool, pop: Popularidade, visto: Visto, cooc: Coocorrencia, seq: Sequencial,
                 busca: Busca, catalogo: Catalogo, n_cand: int = 50):
        self.com_busca = com_busca
        self.nome = "hibrido_com_busca" if com_busca else "hibrido_sem_busca"
        self.pop, self.visto, self.cooc, self.seq, self.busca = pop, visto, cooc, seq, busca
        self.catalogo, self.n_cand = catalogo, n_cand
        self.features = FEATURES_BASE + (FEATURES_BUSCA if com_busca else [])
        self.modelo: lgb.Booster | None = None
        self._fontes: dict[tuple[int, int], dict[str, int]] = {}

    def trocar_base(self, pop, visto, cooc, seq, busca) -> Hibrido:
        """Usa os modelos de base ajustados até outro corte (o LightGBM treinado continua o mesmo)."""
        self.pop, self.visto, self.cooc, self.seq, self.busca = pop, visto, cooc, seq, busca
        self._fontes = {}
        return self

    def candidatos(self, caso: Caso) -> tuple[list[int], np.ndarray, dict[int, dict[str, int]]]:
        notas_visto = self.visto.pontuar(caso)
        notas_cooc = self.cooc.pontuar(caso)
        h = self.seq.estado(caso)
        notas_seq = self.seq.pontuar_estado(h, self.n_cand) if h is not None else {}
        listas = {
            "visto": top_k(notas_visto, self.n_cand),
            "cooc": top_k(notas_cooc, self.n_cand),
            "seq": top_k(notas_seq, self.n_cand),
            "pop": self.pop.ranking[:20],
        }
        notas_busca = {}
        if self.com_busca:
            notas_busca = self.busca.pontuar(caso)
            listas["busca"] = top_k(notas_busca, self.n_cand)
        itens = list(dict.fromkeys(i for lista in listas.values() for i in lista))
        fontes: dict[int, dict[str, int]] = defaultdict(dict)
        for fonte, lista in listas.items():
            for r, i in enumerate(lista):
                fontes[i][fonte] = r
        return itens, self._matriz(caso, itens, notas_visto, notas_cooc, h, notas_busca, fontes), fontes

    def _matriz(self, caso, itens, notas_visto, notas_cooc, h, notas_busca, fontes) -> np.ndarray:
        cat = self.catalogo.categoria
        vistas_atual = Counter(v[0] for v in caso.vistos if v[3])
        vistas_antes = Counter(v[0] for v in caso.vistos if not v[3])
        compras_antes = Counter(i for i, _ in caso.compras_antes)
        recentes = {i: r for r, i in enumerate(dict.fromkeys(reversed([v[0] for v in caso.vistos if v[3]])))}
        cats_vistas = Counter(cat.get(v[0], 0) for v in caso.vistos if v[3])
        seq_notas = self.seq.notas_itens(h, itens)
        ordem_seq = {i: r for r, i in enumerate(np.array(itens)[np.argsort(-seq_notas)])}
        n_vistas_fit = self.cooc.n_vistas
        n_compras_fit = self.cooc.n_compras
        vp, vv = self._cooc_separado(caso, itens)
        linhas = []
        if self.com_busca:
            melhor_pos: dict[int, int] = {}
            vezes: Counter = Counter()
            cliques: Counter = Counter()
            ultima = set(caso.buscas[-1].mostrados) if caso.buscas else set()
            cats_buscadas = Counter(b.categoria for b in caso.buscas if b.categoria)
            texto: dict[int, float] = defaultdict(float)
            for b in caso.buscas:
                for pos, i in enumerate(b.mostrados, start=1):
                    vezes[i] += 1
                    if pos < melhor_pos.get(i, 10**6):
                        melhor_pos[i] = pos
                for i in b.cliques:
                    cliques[i] += 1
                if b.texto and self.busca.indice is not None:
                    for i, s in self.busca.indice.buscar(b.termos, 30).items():
                        texto[i] = max(texto[i], s)
            n_buscas = len(caso.buscas)
            n_texto = sum(1 for b in caso.buscas if b.texto)
        for k, i in enumerate(itens):
            f = fontes.get(i, {})
            nv = n_vistas_fit[i] if i < len(n_vistas_fit) else 0
            nc = n_compras_fit[i] if i < len(n_compras_fit) else 0
            linha = [
                notas_visto.get(i, 0.0), vistas_atual.get(i, 0), vistas_antes.get(i, 0), recentes.get(i, 99),
                compras_antes.get(i, 0), vp[k], vv[k], f.get("cooc", 99), float(seq_notas[k]) if h is not None else -50.0,
                ordem_seq.get(i, 999) if h is not None else 999,
                math.log1p(self.pop.compras.get(i, 0)), math.log1p(self.pop.views.get(i, 0)),
                (nc + 0.1) / (nv + 5), self.catalogo.preco.get(i, 0), cats_vistas.get(cat.get(i, -1), 0),
                len({v[0] for v in caso.vistos}), 1 if caso.usuario is not None else 0,
            ]
            if self.com_busca:
                linha += [
                    notas_busca.get(i, 0.0), melhor_pos.get(i, 999), vezes.get(i, 0), cliques.get(i, 0),
                    texto.get(i, 0.0), 1 if i in ultima else 0, cats_buscadas.get(cat.get(i, -1), 0),
                    n_buscas, n_texto,
                ]
            linhas.append(linha)
        return np.asarray(linhas, dtype=np.float32)

    def _cooc_separado(self, caso: Caso, itens: list[int]) -> tuple[np.ndarray, np.ndarray]:
        import scipy.sparse as sp

        from .modelos import _peso_vistos

        pesos = _peso_vistos(caso)
        hs = [h for h in pesos if h < self.cooc.vp.shape[0]]
        if not hs:
            return np.zeros(len(itens)), np.zeros(len(itens))
        w = sp.csr_matrix(np.array([[pesos[h] for h in hs]], dtype=np.float32))
        idx = np.array([i if i < self.cooc.vp.shape[1] else 0 for i in itens])
        vp = (w @ self.cooc.vp[hs]).toarray().ravel()[idx]
        vv = (w @ self.cooc.vv[hs]).toarray().ravel()[idx]
        return vp, vv

    def treinar(self, casos: list[Caso], semente: int = 42) -> dict:
        xs, ys, grupos = [], [], []
        for c in casos:
            itens, x, _ = self.candidatos(c)
            y = np.array([1 if i in c.alvo else 0 for i in itens])
            if y.sum() == 0:
                continue  # sem acerto possível: não ensina nada ao LambdaRank
            xs.append(x)
            ys.append(y)
            grupos.append(len(itens))
        rng = np.random.default_rng(semente)
        ordem = rng.permutation(len(grupos))
        corte = int(0.8 * len(ordem))
        treino, valid = sorted(ordem[:corte]), sorted(ordem[corte:])

        def juntar(ids):
            return (np.vstack([xs[k] for k in ids]), np.concatenate([ys[k] for k in ids]), [grupos[k] for k in ids])

        xt, yt, gt = juntar(treino)
        xv, yv, gv = juntar(valid)
        params = {
            "objective": "lambdarank", "metric": "ndcg", "ndcg_eval_at": [10], "learning_rate": 0.05,
            "num_leaves": 31, "min_data_in_leaf": 50, "feature_fraction": 0.8, "bagging_fraction": 0.8,
            "bagging_freq": 1, "lambda_l2": 1.0, "verbose": -1, "seed": semente, "num_threads": 2,
        }
        dt = lgb.Dataset(xt, yt, group=gt, feature_name=self.features)
        dv = lgb.Dataset(xv, yv, group=gv, reference=dt)
        self.modelo = lgb.train(params, dt, num_boost_round=600, valid_sets=[dv],
                                callbacks=[lgb.early_stopping(50, verbose=False)])
        importancia = dict(zip(self.features, self.modelo.feature_importance("gain").round(1).tolist()))
        return {"casos_treino": len(treino), "casos_valid": len(valid), "linhas": int(len(yt) + len(yv)),
                "arvores": self.modelo.best_iteration, "importancia": importancia}

    def pontuar(self, caso: Caso) -> dict[int, float]:
        itens, x, fontes = self.candidatos(caso)
        if not itens:
            return {}
        notas = self.modelo.predict(x, num_iteration=self.modelo.best_iteration, num_threads=1)
        for i in itens:
            self._fontes[(caso.sessao, i)] = fontes[i]
        return dict(zip(itens, notas.tolist()))

    def motivo(self, caso: Caso, item: int) -> dict:
        fontes = self._fontes.get((caso.sessao, item))
        if fontes is None:
            self.pontuar(caso)
            fontes = self._fontes.get((caso.sessao, item), {})
        if "visto" in fontes and fontes["visto"] < 50:
            m = self.visto.motivo(caso, item)
            if m["cod"] != "pop":
                return m
        ordem = sorted(fontes.items(), key=lambda kv: kv[1])
        for fonte, _r in ordem:
            if fonte == "busca":
                m = self.busca.motivo(caso, item)
            elif fonte == "cooc":
                m = self.cooc.motivo(caso, item)
            elif fonte == "seq":
                m = self.seq.motivo(caso, item)
            else:
                continue
            if m["cod"] != "pop":
                return m
        return self.pop.motivo(caso, item)
