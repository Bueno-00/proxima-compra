"""Roda a comparação completa e grava reports/resultados.json e reports/resultados.md.

Duas leituras do mesmo teste (maio de 2016, modelos treinados só com dados até 30/04/2016):
  geral:      acertar os produtos que a pessoa comprou na visita
  descoberta: só os produtos comprados que ela ainda NÃO tinha visto (o "outros sabores, whey");
              os já vistos saem da lista de sugestões e da resposta
"""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path

import numpy as np

from .casos import TESTE, VALIDACAO, Caso, Divisao, montar_casos, resumo_casos
from .dados import conectar
from .metricas import bootstrap_diferenca, bootstrap_ic, cobertura, por_caso
from .modelos import Busca, Coocorrencia, Popularidade, Visto, completar, top_k
from .ranker import Catalogo, Hibrido
from .sequencial import Sequencial

ORDEM = ["popularidade", "visto", "coocorrencia", "sequencial", "busca", "hibrido_sem_busca", "hibrido_com_busca"]
USA_BUSCA = {"busca", "hibrido_com_busca"}


def ajustar_base(interim: Path, div: Divisao, modelos_dir: Path, busca: Busca | None = None) -> dict:
    t = time.time()
    base = {
        "popularidade": Popularidade().ajustar(interim, div.corte),
        "visto": Visto().ajustar(interim, div.corte),
        "coocorrencia": Coocorrencia(a=5.0, b=0.0).ajustar(interim, div.corte),
        "busca": (busca or Busca(peso_clique=2.0, peso_texto=0.3, decaimento=0.8)).ajustar(interim, div.corte),
        "sequencial": Sequencial().ajustar(interim, div.corte, cache=modelos_dir / f"seq_{div.nome}.pt"),
    }
    base["_segundos"] = round(time.time() - t, 1)
    return base


def vistos_do_caso(c: Caso) -> set[int]:
    return {v[0] for v in c.vistos} | {i for i, _ in c.compras_antes}


def tamanho_catalogo(interim: Path, corte) -> int:
    con = conectar()
    n = con.execute(
        f"""select count(distinct item) from (
              select item from '{interim / 'views.parquet'}' where dia < '{corte}'
              union all select item from '{interim / 'compras.parquet'}' where dia < '{corte}')"""
    ).fetchone()[0]
    con.close()
    return int(n)


def gerar_listas(modelo, casos: list[Caso], reserva: list[int]) -> dict:
    geral, descoberta, latencias = [], [], []
    for c in casos:
        t = time.perf_counter()
        notas = modelo.pontuar(c)
        lista = completar(top_k(notas, 10), reserva)
        latencias.append((time.perf_counter() - t) * 1000)
        geral.append(lista)
        vistos = vistos_do_caso(c)
        descoberta.append(completar(top_k(notas, 10, vistos), [i for i in reserva if i not in vistos]))
    return {"geral": geral, "descoberta": descoberta, "latencia_ms": np.array(latencias)}


def medir_latencia(modelos: dict, casos: list[Caso], seq: Sequencial, n: int = 300, semente: int = 3) -> dict:
    """Tempo para montar a lista de UMA pessoa, um caso por vez, sem atalho de lote nem cache."""
    import random

    import torch

    torch.set_num_threads(1)
    amostra = random.Random(semente).sample(casos, min(n, len(casos)))
    seq.limpar_cache()
    saida = {}
    for nome in ORDEM:
        reserva = modelos["popularidade"].ranking
        tempos = []
        for c in amostra:
            t = time.perf_counter()
            completar(top_k(modelos[nome].pontuar(c), 10), reserva)
            tempos.append((time.perf_counter() - t) * 1000)
        saida[nome] = np.array(tempos)
    return saida


def _resumo_metricas(m: dict[str, np.ndarray]) -> dict:
    saida = {}
    for nome, valores in m.items():
        lo, hi = bootstrap_ic(valores)
        saida[nome] = {"media": round(float(valores.mean()), 4), "ic95": [round(lo, 4), round(hi, 4)]}
    return saida


def rodar(interim: Path, saida: Path, modelos_dir: Path) -> dict:
    interim, saida, modelos_dir = Path(interim), Path(saida), Path(modelos_dir)
    saida.mkdir(parents=True, exist_ok=True)
    inicio = time.time()
    catalogo = Catalogo(interim)

    # 1) validação: ajusta a base até 31/03 e treina os dois híbridos nos casos de abril
    casos_val = montar_casos(interim, VALIDACAO)
    base_val = ajustar_base(interim, VALIDACAO, modelos_dir)
    base_val["sequencial"].preparar(casos_val)
    hibridos = {}
    treino_info = {}
    for com_busca in (False, True):
        h = Hibrido(com_busca, base_val["popularidade"], base_val["visto"], base_val["coocorrencia"],
                    base_val["sequencial"], base_val["busca"], catalogo)
        treino_info[h.nome] = h.treinar(casos_val)
        hibridos[h.nome] = h

    # 2) teste: base ajustada até 30/04, híbridos já treinados, casos de maio
    casos = montar_casos(interim, TESTE)
    base = ajustar_base(interim, TESTE, modelos_dir, busca=base_val["busca"])
    for h in hibridos.values():
        h.trocar_base(base["popularidade"], base["visto"], base["coocorrencia"], base["sequencial"], base["busca"])
    modelos = {**{k: base[k] for k in ORDEM[:5]}, **hibridos}
    reserva = base["popularidade"].ranking
    latencias = medir_latencia(modelos, casos, base["sequencial"])
    base["sequencial"].preparar(casos)
    n_catalogo = tamanho_catalogo(interim, TESTE.corte)

    alvos = [c.alvo for c in casos]
    novos = [c.alvo - vistos_do_caso(c) for c in casos]
    idx_desc = [k for k, a in enumerate(novos) if a]
    resultados, por_caso_geral, por_caso_desc, listas_teste = {}, {}, {}, {}
    for nome in ORDEM:
        listas = gerar_listas(modelos[nome], casos, reserva)
        listas_teste[nome] = listas["geral"]
        mg = por_caso(listas["geral"], alvos)
        md = por_caso([listas["descoberta"][k] for k in idx_desc], [novos[k] for k in idx_desc])
        por_caso_geral[nome], por_caso_desc[nome] = mg, md
        lat = latencias[nome]
        resultados[nome] = {
            "usa_busca": nome in USA_BUSCA,
            "geral": _resumo_metricas(mg),
            "descoberta": _resumo_metricas(md),
            "cobertura": round(cobertura(listas["geral"], n_catalogo), 4),
            "itens_distintos": len({i for lista in listas["geral"] for i in lista}),
            "latencia_ms": {"mediana": round(float(np.median(lat)), 2), "p95": round(float(np.percentile(lat, 95)), 2)},
        }
        print(f"{nome:20s} geral R@10 {mg['recall'].mean():.4f} N@10 {mg['ndcg'].mean():.4f} | "
              f"descoberta R@10 {md['recall'].mean():.4f} N@10 {md['ndcg'].mean():.4f} | "
              f"{np.median(lat):.1f} ms", flush=True)

    # 3) quanto a busca ajuda: diferença pareada, caso a caso
    efeito = {}
    for leitura, pc in (("geral", por_caso_geral), ("descoberta", por_caso_desc)):
        efeito[leitura] = {
            m: bootstrap_diferenca(pc["hibrido_com_busca"][m], pc["hibrido_sem_busca"][m]) for m in ("recall", "ndcg")
        }
    # recortes: com e sem busca por texto
    texto = np.array([any(b.texto for b in c.buscas) for c in casos])
    recortes = {}
    for rotulo, mascara in (("com_busca_texto", texto), ("sem_busca_texto", ~texto)):
        recortes[rotulo] = {
            "casos": int(mascara.sum()),
            **{m: {"sem_busca": round(float(por_caso_geral["hibrido_sem_busca"]["recall"][mascara].mean()), 4),
                   "com_busca": round(float(por_caso_geral["hibrido_com_busca"]["recall"][mascara].mean()), 4)}
               for m in ("recall",)},
        }

    relatorio = {
        "base": "Diginetica, CIKM Cup 2016 trilha 2 (loja online real, nomes e buscas cifrados)",
        "protocolo": {
            "validacao": {"corte": str(VALIDACAO.corte), "casos": resumo_casos(casos_val)},
            "teste": {"corte": str(TESTE.corte), "casos": resumo_casos(casos),
                      "casos_descoberta": len(idx_desc), "itens_descoberta": int(sum(len(novos[k]) for k in idx_desc))},
            "catalogo_ativo": n_catalogo,
            "k": 10,
        },
        "modelos": resultados,
        "efeito_da_busca": efeito,
        "recortes": recortes,
        "treino_hibridos": treino_info,
        "sequencial_log": {"validacao": base_val["sequencial"].log, "teste": base["sequencial"].log},
        "maquina": {"cpu": platform.processor() or platform.machine(), "python": platform.python_version()},
        "segundos_total": round(time.time() - inicio, 1),
    }
    (saida / "resultados.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2))
    (saida / "resultados.md").write_text(tabela_md(relatorio))
    return {"relatorio": relatorio, "casos": casos, "modelos": modelos, "listas": listas_teste,
            "por_caso": por_caso_geral, "catalogo": catalogo}


NOMES_PT = {
    "popularidade": "Mais vendidos", "visto": "Repetir o que viu ou comprou", "coocorrencia": "Item a item",
    "sequencial": "Sequencial (SASRec)", "busca": "Só a busca", "hibrido_sem_busca": "Híbrido sem busca",
    "hibrido_com_busca": "Híbrido com busca",
}


def tabela_md(r: dict) -> str:
    p = r["protocolo"]["teste"]
    linhas = [
        "# Resultados (teste: maio de 2016)",
        "",
        (f"Casos de teste: {p['casos']['casos']} visitas com compra ({p['casos']['itens_alvo']} produtos comprados). "
         f"Descoberta: {p['casos_descoberta']} visitas com pelo menos 1 produto comprado que a pessoa não tinha visto. "
         f"Catálogo ativo: {r['protocolo']['catalogo_ativo']} produtos."),
        "",
        ("| Modelo | Usa busca | Recall@10 | NDCG@10 | Acerto@10 | Recall@10 descoberta | NDCG@10 descoberta | "
         "Cobertura | Latência (mediana) |"),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for nome, m in r["modelos"].items():
        g, d = m["geral"], m["descoberta"]
        linhas.append(
            f"| {NOMES_PT[nome]} | {'sim' if m['usa_busca'] else 'não'} | {g['recall']['media']:.3f} "
            f"({g['recall']['ic95'][0]:.3f} a {g['recall']['ic95'][1]:.3f}) | {g['ndcg']['media']:.3f} | "
            f"{g['acerto']['media']:.3f} | {d['recall']['media']:.3f} | {d['ndcg']['media']:.3f} | "
            f"{m['cobertura'] * 100:.2f}% | {m['latencia_ms']['mediana']:.1f} ms |"
        )
    e = r["efeito_da_busca"]
    linhas += [
        "",
        "## Quanto a busca ajuda (híbrido com busca menos híbrido sem busca, pareado por visita)",
        "",
        (f"- Geral: recall@10 {e['geral']['recall']['media']:+.4f} (IC 95% {e['geral']['recall']['ic95'][0]:+.4f} "
         f"a {e['geral']['recall']['ic95'][1]:+.4f}); NDCG@10 {e['geral']['ndcg']['media']:+.4f}."),
        (f"- Descoberta: recall@10 {e['descoberta']['recall']['media']:+.4f} (IC 95% "
         f"{e['descoberta']['recall']['ic95'][0]:+.4f} a {e['descoberta']['recall']['ic95'][1]:+.4f}); "
         f"NDCG@10 {e['descoberta']['ndcg']['media']:+.4f}."),
        "",
    ]
    return "\n".join(linhas) + "\n"
