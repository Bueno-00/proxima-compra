# Resultados (teste: maio de 2016)

Casos de teste: 3985 visitas com compra (5445 produtos comprados). Descoberta: 1499 visitas com pelo menos 1 produto comprado que a pessoa não tinha visto. Catálogo ativo: 104874 produtos.

| Modelo | Usa busca | Recall@10 | NDCG@10 | Acerto@10 | Recall@10 descoberta | NDCG@10 descoberta | Cobertura | Latência (mediana) |
|---|---|---|---|---|---|---|---|---|
| Mais vendidos | não | 0.006 (0.003 a 0.008) | 0.003 | 0.007 | 0.005 | 0.003 | 0.01% | 0.0 ms |
| Repetir o que viu ou comprou | não | 0.673 (0.659 a 0.686) | 0.603 | 0.735 | 0.005 | 0.003 | 10.38% | 0.0 ms |
| Item a item | não | 0.241 (0.229 a 0.254) | 0.185 | 0.275 | 0.028 | 0.020 | 4.83% | 0.4 ms |
| Sequencial (SASRec) | não | 0.342 (0.328 a 0.356) | 0.220 | 0.383 | 0.079 | 0.045 | 7.85% | 3.0 ms |
| Só a busca | sim | 0.592 (0.578 a 0.607) | 0.521 | 0.661 | 0.265 | 0.213 | 12.31% | 0.1 ms |
| Híbrido sem busca | não | 0.703 (0.689 a 0.716) | 0.616 | 0.766 | 0.117 | 0.066 | 15.45% | 16.9 ms |
| Híbrido com busca | sim | 0.773 (0.761 a 0.783) | 0.672 | 0.838 | 0.323 | 0.258 | 17.35% | 24.6 ms |

## Quanto a busca ajuda (híbrido com busca menos híbrido sem busca, pareado por visita)

- Geral: recall@10 +0.0699 (IC 95% +0.0614 a +0.0781); NDCG@10 +0.0554.
- Descoberta: recall@10 +0.2067 (IC 95% +0.1847 a +0.2274); NDCG@10 +0.1922.

