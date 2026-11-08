"""Modelo sequencial (estilo SASRec, Kang e McAuley, 2018) em PyTorch, só CPU.

Lê a sequência de produtos que a pessoa viu (e comprou), na ordem, e prevê o próximo.
Um "transformer" pequeno: cada produto vira um vetor de 64 números, 2 camadas de atenção
olham só para trás (máscara causal) e a última posição dá uma nota para cada produto do catálogo.
Treino: entropia cruzada com amostragem (o produto certo contra 2.048 produtos sorteados), só nas
posições que têm produto; assim cabe em CPU. Na hora de recomendar, nota para o catálogo inteiro.
"""

from __future__ import annotations

import heapq
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .casos import Caso
from .dados import conectar


class SASRec(nn.Module):
    def __init__(self, n_itens: int, dim: int = 64, max_len: int = 50, camadas: int = 2, cabecas: int = 2,
                 dropout: float = 0.2):
        super().__init__()
        self.itens = nn.Embedding(n_itens + 1, dim, padding_idx=0)
        self.posicoes = nn.Embedding(max_len, dim)
        bloco = nn.TransformerEncoderLayer(dim, cabecas, dim * 2, dropout, batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(bloco, camadas, enable_nested_tensor=False)
        self.norma = nn.LayerNorm(dim)
        self.drop = nn.Dropout(dropout)
        self.max_len = max_len
        nn.init.normal_(self.itens.weight, std=0.05)
        nn.init.normal_(self.posicoes.weight, std=0.05)
        with torch.no_grad():
            self.itens.weight[0].zero_()

    def forward(self, seq: torch.Tensor) -> torch.Tensor:
        n = seq.shape[1]
        pos = torch.arange(n, device=seq.device).unsqueeze(0)
        x = self.drop(self.itens(seq) + self.posicoes(pos))
        mascara = torch.triu(torch.ones(n, n, dtype=torch.bool, device=seq.device), diagonal=1)
        x = self.encoder(x, mask=mascara, src_key_padding_mask=(seq == 0))
        return self.norma(x)

    def notas(self, h: torch.Tensor) -> torch.Tensor:
        return h @ self.itens.weight[1:].T  # sem o índice 0 (vazio)


def _sequencias(interim: Path, corte, min_ocorrencias: int = 2) -> tuple[list[list[int]], dict[int, int]]:
    con = conectar()
    linhas = con.execute(
        f"""with ev as (
              select sessao, item, t, 0 tipo from '{Path(interim) / 'views.parquet'}' where dia < '{corte}'
              union all
              select sessao, item, t, 1 tipo from '{Path(interim) / 'compras.parquet'}' where dia < '{corte}'),
            freq as (select item from ev group by item having count(*) >= {min_ocorrencias})
            select sessao, list(item order by t, tipo) from ev where item in (select item from freq)
            group by sessao order by sessao"""
    ).fetchall()
    con.close()
    limpas = []
    for _s, itens in linhas:
        limpos = [i for k, i in enumerate(itens) if k == 0 or i != itens[k - 1]]
        if len(limpos) >= 2:
            limpas.append(limpos)
    # vocabulário em ordem de código do produto: o mesmo a cada execução
    vocab = {item: k + 1 for k, item in enumerate(sorted({i for s in limpas for i in s}))}
    return [[vocab[i] for i in s] for s in limpas], vocab


def _hash_vocab(vocab: dict[int, int]) -> str:
    import hashlib

    return hashlib.sha256(",".join(f"{i}:{k}" for i, k in sorted(vocab.items())).encode()).hexdigest()[:16]


class Sequencial:
    nome = "sequencial"

    def __init__(self, dim: int = 64, max_len: int = 50, epocas: int = 4, lote: int = 256, lr: float = 1e-3,
                 semente: int = 42, threads: int = 2, negativos: int = 2048):
        self.dim, self.max_len, self.epocas, self.lote, self.lr = dim, max_len, epocas, lote, lr
        self.semente, self.threads, self.negativos = semente, threads, negativos
        self.log: list[str] = []

    def ajustar(self, interim: Path, corte, cache: Path | None = None) -> Sequencial:
        torch.set_num_threads(self.threads)
        torch.manual_seed(self.semente)
        rng = np.random.default_rng(self.semente)
        seqs, self.vocab = _sequencias(interim, corte)
        self.inverso = np.zeros(len(self.vocab) + 1, dtype=np.int64)
        for item, k in self.vocab.items():
            self.inverso[k] = item
        self.modelo = SASRec(len(self.vocab), self.dim, self.max_len)
        if cache is not None and Path(cache).exists():
            salvo = torch.load(cache, map_location="cpu")
            if salvo.get("vocab_hash") != _hash_vocab(self.vocab):
                raise ValueError(f"{cache} foi treinado com outro vocabulário; apague o arquivo e treine de novo")
            self.modelo.load_state_dict(salvo["pesos"])
            self.modelo.eval()
            self.log = list(salvo.get("log", [])) + [f"carregado de {Path(cache).name}"]
            return self
        otim = torch.optim.Adam(self.modelo.parameters(), lr=self.lr)
        perda_f = nn.CrossEntropyLoss()
        inicio = time.time()
        # lotes com sequências de tamanho parecido: quase nada de enchimento (bem mais rápido em CPU)
        por_tamanho = np.argsort([min(len(x), self.max_len + 1) for x in seqs], kind="stable")
        lotes = [por_tamanho[b:b + self.lote] for b in range(0, len(por_tamanho), self.lote)]
        for epoca in range(self.epocas):
            self.modelo.train()
            total, n = 0.0, 0
            for b in rng.permutation(len(lotes)):
                lote = [seqs[k][-(self.max_len + 1):] for k in lotes[b]]
                tam = max(len(s) for s in lote) - 1
                entrada = torch.zeros(len(lote), tam, dtype=torch.long)
                alvo = torch.zeros(len(lote), tam, dtype=torch.long)
                for r, s in enumerate(lote):
                    x, y = s[:-1], s[1:]
                    entrada[r, tam - len(x):] = torch.tensor(x)
                    alvo[r, tam - len(y):] = torch.tensor(y)
                h = self.modelo(entrada)
                validos = alvo > 0
                hv, yv = h[validos], alvo[validos]
                neg = torch.randint(1, len(self.vocab) + 1, (self.negativos,))
                e_pos = self.modelo.itens(yv)
                e_neg = self.modelo.itens(neg)
                logit_pos = (hv * e_pos).sum(-1, keepdim=True)
                logit_neg = hv @ e_neg.T
                logit_neg = logit_neg.masked_fill(neg.unsqueeze(0) == yv.unsqueeze(1), -1e9)
                logits = torch.cat([logit_pos, logit_neg], dim=1)
                perda = perda_f(logits, torch.zeros(len(yv), dtype=torch.long))
                otim.zero_grad()
                perda.backward()
                otim.step()
                total += perda.item()
                n += 1
            self.log.append(f"época {epoca + 1}: perda {total / max(n, 1):.3f} ({time.time() - inicio:.0f} s)")
        self.modelo.eval()
        self.segundos_treino = time.time() - inicio
        if cache is not None:
            Path(cache).parent.mkdir(parents=True, exist_ok=True)
            torch.save({"pesos": self.modelo.state_dict(), "vocab_hash": _hash_vocab(self.vocab), "log": self.log},
                       cache)
        return self

    def _entrada(self, caso: Caso) -> list[int]:
        itens = [self.vocab[i] for i in caso.itens_vistos() if i in self.vocab]
        limpos = [i for k, i in enumerate(itens) if k == 0 or i != itens[k - 1]]
        return limpos[-self.max_len:]

    @torch.no_grad()
    def estado(self, caso: Caso) -> np.ndarray | None:
        cache = getattr(self, "_cache", None)
        if cache is not None and caso.sessao in cache:
            return cache[caso.sessao]
        seq = self._entrada(caso)
        if not seq:
            return None
        h = self.modelo(torch.tensor([seq]))[0, -1]
        return h.numpy()

    @torch.no_grad()
    def preparar(self, casos: list[Caso], lote: int = 256) -> None:
        """Calcula o estado de muitos casos de uma vez (só para acelerar a avaliação em lote).

        O tempo por pessoa que vai no relatório é medido sem este atalho, um caso por vez."""
        self._cache = {}
        # agrupa por tamanho para não precisar de enchimento: no modo de avaliação o PyTorch devolve NaN
        # nas linhas só de enchimento, e isso contamina o lote inteiro
        grupos: dict[int, list] = {}
        for c in casos:
            e = self._entrada(c)
            if e:
                grupos.setdefault(len(e), []).append((c.sessao, e))
        for parte_toda in grupos.values():
            for b in range(0, len(parte_toda), lote):
                parte = parte_toda[b:b + lote]
                h = self.modelo(torch.tensor([e for _, e in parte]))[:, -1].numpy()
                for r, (sessao, _) in enumerate(parte):
                    self._cache[sessao] = h[r].copy()
        for c in casos:
            self._cache.setdefault(c.sessao, None)

    def limpar_cache(self) -> None:
        self._cache = None

    def notas_itens(self, h: np.ndarray | None, itens: list[int]) -> np.ndarray:
        if h is None:
            return np.zeros(len(itens), dtype=np.float32)
        pesos = self.modelo.itens.weight.detach().numpy()
        idx = np.array([self.vocab.get(i, 0) for i in itens], dtype=np.int64)
        notas = pesos[idx] @ h
        notas[idx == 0] = -1e9
        return notas

    @torch.no_grad()
    def pontuar(self, caso: Caso, k: int = 100) -> dict[int, float]:
        return self.pontuar_estado(self.estado(caso), k)

    @torch.no_grad()
    def pontuar_estado(self, h: np.ndarray | None, k: int = 100) -> dict[int, float]:
        if h is None:
            return {}
        notas = self.modelo.notas(torch.from_numpy(h)).numpy()
        top = np.argpartition(-notas, k)[:k]
        return {int(self.inverso[j + 1]): float(notas[j]) for j in top}

    def motivo(self, caso: Caso, item: int) -> dict:
        ultimos = list(dict.fromkeys(reversed(caso.itens_vistos())))[:2]
        return {"cod": "seq", "itens": [int(i) for i in ultimos]}


def top_k_dict(notas: dict[int, float], k: int) -> list[int]:
    return [i for i, _ in heapq.nlargest(k, notas.items(), key=lambda x: x[1])]
