"""Exporta as visitas de exemplo e os números para a página estática (docs/index.html).

A página não chama servidor nenhum: os dados vão embutidos no próprio HTML.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .avaliar import NOMES_PT, ORDEM, vistos_do_caso
from .casos import Caso
from .modelos import completar, top_k
from .promocao import alertas_promocao, habituais, precos_simulados

RAIZ = Path(__file__).resolve().parents[2]


def _historico(c: Caso) -> dict:
    atuais = [v for v in c.vistos if v[3]]
    antes = [v for v in c.vistos if not v[3]]
    return {
        "vistos_agora": [v[0] for v in atuais][-15:],
        "vistos_antes": [{"item": v[0], "dia": v[1].isoformat()} for v in antes][-10:],
        "buscas": [
            {"dia": b.dia.isoformat(), "atual": b.atual, "termos": b.termos[:6], "cat": b.categoria,
             "n_mostrados": len(b.mostrados), "cliques": list(dict.fromkeys(b.cliques))[:5],
             "primeiros": b.mostrados[:3]}
            for b in c.buscas
        ][-8:],
        "compras_antes": [{"item": i, "dia": d.isoformat()} for i, d in c.compras_antes][-6:],
        "n_vistos_agora": len(atuais), "n_buscas": len(c.buscas),
    }


def _lista(modelo, c: Caso, reserva: list[int], descoberta: bool) -> list[dict]:
    notas = modelo.pontuar(c)
    vistos = vistos_do_caso(c)
    if descoberta:
        itens = completar(top_k(notas, 10, vistos), [i for i in reserva if i not in vistos])
    else:
        itens = completar(top_k(notas, 10), reserva)
    saida = []
    for i in itens:
        motivo = modelo.motivo(c, i) if i in notas else {"cod": "pop"}
        if motivo.get("cod") == "pop" and "pos" not in motivo:
            motivo = {"cod": "pop", "pos": reserva.index(i) + 1 if i in reserva[:50] else None}
        saida.append({"item": int(i), "m": motivo, "ok": i in c.alvo, "novo": i not in vistos})
    return saida


def exportar(resultado: dict, destino: Path, n: int = 36, semente: int = 7) -> dict:
    casos: list[Caso] = resultado["casos"]
    modelos = resultado["modelos"]
    catalogo = resultado["catalogo"]
    reserva = modelos["popularidade"].ranking
    rng = random.Random(semente)
    elegiveis = [k for k, c in enumerate(casos) if c.vistos and c.buscas]
    com_texto = [k for k in elegiveis if any(b.texto for b in casos[k].buscas)]
    logados = [k for k in elegiveis if casos[k].compras_antes and k not in com_texto]
    escolha = rng.sample(com_texto, min(8, len(com_texto)))
    escolha += rng.sample(logados, min(6, len(logados)))
    resto = [k for k in elegiveis if k not in set(escolha)]
    escolha += rng.sample(resto, n - len(escolha))
    escolha.sort(key=lambda k: (casos[k].dia, casos[k].sessao))

    visitas, itens_usados = [], set()
    for k in escolha:
        c = casos[k]
        hab = habituais(c)
        hoje, normal = precos_simulados(list(hab))
        v = {
            "sessao": c.sessao, "dia": c.dia.isoformat(), "logado": c.usuario is not None,
            "texto": any(b.texto for b in c.buscas),
            "hist": _historico(c), "comprou": sorted(c.alvo), "novos": sorted(c.alvo - vistos_do_caso(c)),
            "geral": {nome: _lista(modelos[nome], c, reserva, False) for nome in ORDEM},
            "descoberta": {nome: _lista(modelos[nome], c, reserva, True) for nome in ORDEM},
            "promo": [
                {**a, "normal": normal[a["item"]], "hoje": hoje[a["item"]]}
                for a in alertas_promocao(c, hoje, normal)
            ],
        }
        visitas.append(v)
        h = v["hist"]
        itens_usados |= set(h["vistos_agora"]) | {x["item"] for x in h["vistos_antes"]} | set(v["comprou"])
        itens_usados |= {x["item"] for x in h["compras_antes"]}
        for b in h["buscas"]:
            itens_usados |= set(b["cliques"]) | set(b["primeiros"])
        for leitura in ("geral", "descoberta"):
            for lista in v[leitura].values():
                for x in lista:
                    itens_usados.add(x["item"])
                    if "item" in x["m"]:
                        itens_usados.add(x["m"]["item"])
                    itens_usados |= set(x["m"].get("itens", []))
        itens_usados |= {a["item"] for a in v["promo"]}

    nomes = {}
    if modelos["busca"].indice is not None:
        nomes = modelos["busca"].indice.nomes
    produtos = {
        str(i): {"c": catalogo.categoria.get(i, 0), "p": catalogo.preco.get(i, 0), "n": sorted(nomes.get(i, []))[:5]}
        for i in sorted(itens_usados)
    }
    r = resultado["relatorio"]
    dados = {
        "nomes_modelos": NOMES_PT, "ordem": ORDEM,
        "resultados": {k: r[k] for k in ("protocolo", "modelos", "efeito_da_busca", "recortes")},
        "visitas": visitas, "produtos": produtos,
        "amostra": {"n": len(visitas), "semente": semente, "com_texto": min(8, len(com_texto)),
                    "logados_com_historico": min(6, len(logados))},
    }
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    return dados


def montar_pagina(dados_json: Path, modelo_html: Path, saida_html: Path) -> int:
    dados = Path(dados_json).read_text()
    html = Path(modelo_html).read_text()
    if "__DADOS__" not in html:
        raise ValueError("o modelo da página precisa ter o marcador __DADOS__")
    html = html.replace("__DADOS__", dados.replace("</", "<\\/"))
    Path(saida_html).parent.mkdir(parents=True, exist_ok=True)
    Path(saida_html).write_text(html)
    return len(html.encode())
