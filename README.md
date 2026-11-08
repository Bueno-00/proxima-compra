# Próxima compra

**Português** · [English](README.en.md) · **Demonstração:** https://bueno-00.github.io/proxima-compra/

Recomenda os **10 próximos produtos** que a pessoa deve comprar usando o que ela **viu, comprou e pesquisou**, e
mostra o porquê de cada sugestão ("você pesquisou isto", "quem viu o que você viu comprou isto"). Sete jeitos de
recomendar comparados no **mesmo teste, com divisão por data**, numa base pública de uma loja online real.

> **Resultado (teste de maio de 2016, 3.985 visitas com compra).** O híbrido com busca acerta pelo menos 1 dos 10 em **84%** das visitas (recall@10 77,3%). **A busca soma +7,0 pontos** de recall@10 contra o mesmo híbrido sem busca (intervalo +6,1 a +7,8) e **+20,7 pontos nos produtos que a pessoa ainda não tinha visto** (11,7% para 32,3%). Tempo por pessoa: 25 ms em CPU. Gasto: zero (sem API paga, sem GPU).

---

## Para quem tem loja ou mercado online

**O problema.** O cliente entra no seu site, olha alguns produtos, pesquisa e muitas vezes vai embora sem levar
nada, ou leva só o que já veio buscar. Sua loja já registra tudo isso (o que ele viu, pesquisou e comprou), mas
quase sempre mostra a mesma vitrine para todo mundo.

**O que este projeto faz.** Monta, na hora, uma lista de 10 produtos para cada pessoa, com o motivo de cada um,
juntando o que ela **viu**, **comprou** e **pesquisou**.

### Um exemplo, passo a passo (ilustrativo)

> A cliente e os produtos deste exemplo são inventados, só para mostrar a ideia. O jeito de escolher e os tipos de
> motivo são os mesmos que o modelo usa nos dados reais.

1. **Há 2 semanas**, ela comprou bebida proteica sabor chocolate na sua loja. Estava logada, então a compra fica no
   histórico dela.
2. **Hoje** ela digita "whey" na busca, clica no Whey 900 g baunilha e abre também uma barra de proteína.
3. **Em uns 25 milésimos de segundo**, o modelo junta as pistas (o que ela comprou antes, o que viu agora, o que
   pesquisou e o que outras pessoas com o mesmo caminho compraram), dá uma nota para cada produto e fica com os 10
   maiores.
4. **A lista aparece** no carrinho ou na página do produto, cada item com o motivo:

| # | Sugestão | Motivo que aparece para ela | De onde vem a pista |
|---|---|---|---|
| 1 | Whey 900 g baunilha | Você clicou nele na busca por "whey" | busca |
| 2 | Whey 900 g chocolate | Apareceu em 2º na sua busca por "whey" | busca |
| 3 | Bebida proteica chocolate, 6 un. | Você comprou há 2 semanas | compra anterior |
| 4 | Bebida proteica morango | Quem comprou a de chocolate também levou esta | quem comprou também levou (item a item) |
| 5 | Barra de proteína amendoim | Você viu agora há pouco | o que ela viu |
| 6 | Coqueteleira 600 ml | Costuma ser vista logo depois do whey | sequência (SASRec) |

5. **Ela leva o Whey 900 g chocolate**, que nem tinha aberto. Essa é a venda nova, a que a leitura "só produtos
   novos" mede, e é onde a busca mais ajudou no teste (de 11,7% para 32,3% de acerto).
6. **Na semana seguinte**, a bebida de chocolate entra em promoção e ela recebe o aviso por e-mail ou WhatsApp. (No
   projeto, esta parte roda com preços simulados, porque a base pública não tem preço por dia.)

Por que não mostrar os mais vendidos? Porque são iguais para todo mundo: no teste, a lista dos mais vendidos acertou
só 0,6% do que as pessoas compraram.

### O que a sua loja ganha (medido)

| | Número | O que quer dizer |
|---|---|---|
| Acerto na lista | **84%** | em 84 de cada 100 visitas que terminaram em compra, a pessoa levou pelo menos 1 dos 10 sugeridos |
| Venda nova | **+20,7 pontos** | nos produtos que ela ainda não tinha visto, usar a busca subiu o acerto de 11,7% para 32,3% |
| Velocidade | **25 ms** | para montar a lista de uma pessoa num computador comum, sem placa de vídeo |
| Gasto | **R$ 0** | sem API paga e sem placa de vídeo; o teste inteiro rodou num servidor simples de 2 núcleos |

**De onde vêm os números:** dados públicos de uma loja online europeia, de janeiro a junho de 2016 (Diginetica,
CIKM Cup 2016), com teste em 3.985 visitas com compra de maio. A loja trocou o nome de cada produto por um número
antes de liberar os dados; por isso a demonstração mostra "Produto #25911" e não "Whey 900 g chocolate". É um teste
com o passado: na sua loja os números vão ser outros.

### O que precisa para fazer isso na sua loja

- **Os dados que você já tem:** visitas (quais produtos cada pessoa abriu, e quando), buscas (o que ela digitou, o
  que a busca mostrou e onde clicou) e compras (de preferência com o cliente logado). Opcional: o preço de cada dia,
  para o aviso de promoção. A maioria das lojas virtuais já registra isso, na própria plataforma ou numa ferramenta
  de análise como o Google Analytics. Alguns meses de histórico bastam para começar (aqui foram 4).
- **Onde a lista aparece:** página do produto ("quem viu este também levou"), carrinho ("antes de pagar, não
  esqueça"), e-mail ou WhatsApp ("o que você compra entrou em promoção") e página inicial ("escolhidos para você").
- **Como saber se deu certo (teste A/B):** metade dos clientes, sorteada, vê a lista nova; a outra metade vê a loja
  como está hoje. Depois de 2 a 4 semanas, você compara vendas por visita, valor médio do pedido e quantas pessoas
  clicam na lista. Só fica com a lista se ela ganhar.

### Glossário rápido

- **Visita:** uma ida da pessoa à loja, de quando entra até quando sai. No teste, só contam as visitas com compra.
- **Produto #25911:** o código do produto. A loja trocou os nomes por números antes de liberar os dados.
- **Busca:** quando a pessoa digita algo ou abre uma categoria. A loja mostra uma lista e ela clica em alguns.
- **Os 7 jeitos:** 7 maneiras de escolher os 10 produtos, da mais simples (os mais vendidos, iguais para todos) à
  mais completa (o híbrido com busca).
- **Híbrido:** junta as sugestões dos jeitos mais simples e um modelo (LightGBM) aprende a melhor ordem. "Com busca"
  usa também as pistas da busca.
- **Tudo que comprou:** vale acertar qualquer produto comprado na visita, inclusive os que ela já tinha aberto.
- **Só produtos novos:** vale só acertar o que ela comprou sem ter visto antes. É a venda nova, a mais difícil.
- **Recall@10 (acerto):** dos produtos que ela comprou, quantos estavam entre os 10 sugeridos.
- **Acertou 1+:** a lista teve pelo menos 1 produto que a pessoa comprou naquela visita.
- **Pontos:** a diferença entre duas porcentagens. De 70,3% para 77,3% são +7,0 pontos.
- **Intervalo de 95%:** a faixa onde o número verdadeiro deve estar, calculada sorteando as visitas 1.000 vezes.

---

## A pergunta

A ideia que guiou o projeto: recomendação boa não usa só o que a pessoa comprou, usa também o que ela
**pesquisou**. Quem comprou bebida proteica e pesquisou whey deveria ver outros sabores, o whey e o que ela já
procurou, e não os "mais vendidos da loja". A pergunta medida aqui é direta: **colocar os sinais da busca no
modelo melhora a sugestão? Quanto?**

## Os dados, e por que esta base

| Base | Compra | Busca | Ligadas à mesma pessoa ou visita | Licença | Decisão |
|---|---|---|---|---|---|
| **Diginetica (CIKM Cup 2016, trilha 2)** | sim | sim (termos digitados e páginas de categoria, com a lista mostrada e os cliques) | sim | liberada para pesquisa na competição; não achei texto de licença | **escolhida** |
| Retailrocket (Kaggle) | sim | não | sim | CC BY-NC-SA 4.0 | sem busca |
| Instacart Market Basket | só pedidos | não | sim | termos da competição | sem busca |
| Coveo SIGIR eCom 2021 | sim | sim (vetores) | só na sessão | só pesquisa, com cadastro e termo assinado | acesso fechado |
| OTTO (Kaggle) | sim | não | sim | CC BY 4.0 | sem busca |

A Diginetica é a única aberta em que a mesma visita tem **busca, produtos vistos e compra**, com o horário de cada
coisa. Ela tem 1.235.380 visualizações, 923.127 buscas e 18.025 compras de janeiro a junho de 2016.
Duas coisas pesam contra, e estão nos números:

- **Os nomes e os termos de busca vêm cifrados** (cada palavra virou um número). Dá para saber que a busca e o
  nome do produto têm a mesma palavra, mas não qual palavra. Por isso a demonstração mostra "Produto #25911".
- **Quase ninguém está logado.** O sinal "comprou antes" aparece em poucas visitas. Num app como o iFood, todo
  mundo está logado e esse sinal seria o mais forte.

**Os dados brutos não ficam neste repositório.** `make baixar` busca uma cópia pública no Kaggle; a fonte original
é o CIKM Cup 2016. A página usa só uma amostra derivada de 36 visitas (códigos numéricos).

## Como medimos

- **Divisão por data.** Ajuste do híbrido: modelos treinados com tudo até 31/03/2016 e casos de abril. Teste:
  modelos treinados com tudo até 30/04/2016 e casos de **maio** (3.985 visitas com compra, 5.445 produtos
  comprados). Nenhum modelo vê o mês do teste.
- **Cada caso é uma visita com compra, cortada no momento de pagar.** Entrada: o que a pessoa viu e pesquisou
  antes de pagar nesta visita e, se estava logada, nas visitas dos dias anteriores. Resposta certa: o que ela
  comprou nesta visita.
- **Duas leituras do mesmo teste.** *Tudo que comprou*: vale acertar qualquer produto comprado. *Só produtos
  novos* (descoberta): saem da lista e da resposta os produtos que ela já tinha visto; vale só acertar o que ela
  comprou sem ter visto antes, que é o caso "outros sabores, whey".
- **Medidas.** Recall@10 (dos comprados, quantos estavam entre os 10), NDCG@10 (o mesmo, valendo mais acertar no
  topo), acerto@10 (pelo menos 1 dos 10 comprado), cobertura (quanto do catálogo aparece em alguma lista) e tempo
  para montar a lista de uma pessoa, em CPU. Intervalo de 95% por bootstrap (1.000 sorteios das visitas).
- **Quanto a busca ajuda:** o mesmo híbrido treinado duas vezes, com e sem os sinais da busca, comparado
  visita a visita (diferença pareada com intervalo).

## Os 7 jeitos

| Modelo | O que faz | Usa busca |
|---|---|---|
| Mais vendidos | os 10 mais comprados dos últimos 28 dias, iguais para todo mundo | não |
| Repetir o que viu ou comprou | produtos que a pessoa viu ou comprou, do mais recente ao mais antigo | não |
| Item a item | "quem viu o que você viu comprou isto": conta pares (visto, comprado) nas visitas do treino | não |
| Sequencial (SASRec) | transformer pequeno (2 camadas, 64 dimensões) que lê a ordem do que foi visto e prevê o próximo; treinado em CPU | não |
| Só a busca | produtos que a loja mostrou nas buscas (pesa a posição), os clicados e os que têm no nome os termos digitados (BM25) | sim |
| Híbrido sem busca | junta os candidatos dos 4 primeiros e reordena com LightGBM (LambdaRank), 17 sinais | não |
| Híbrido com busca | o mesmo, com mais 9 sinais da busca (posição na lista, cliques, termos, categoria pesquisada) | sim |

## Resultados (teste de maio de 2016)

| Modelo | Recall@10 | NDCG@10 | Acertou 1+ | Recall@10 só novos | NDCG@10 só novos | Cobertura | Tempo por pessoa |
|---|---|---|---|---|---|---|---|
| Mais vendidos | 0,6% (0,3 a 0,8) | 0,003 | 1% | 0,5% (0,2 a 0,9) | 0,003 | 0,01% | < 0,1 ms |
| Repetir o que viu ou comprou | 67,3% (65,9 a 68,6) | 0,603 | 73% | 0,5% (0,2 a 0,9) | 0,003 | 10,38% | < 0,1 ms |
| Item a item | 24,1% (22,9 a 25,4) | 0,185 | 27% | 2,8% (2,0 a 3,5) | 0,020 | 4,83% | 0,4 ms |
| Sequencial (SASRec) | 34,2% (32,8 a 35,6) | 0,220 | 38% | 7,9% (6,7 a 9,2) | 0,045 | 7,85% | 3,0 ms |
| Só a busca | 59,2% (57,8 a 60,7) | 0,521 | 66% | 26,5% (24,4 a 28,6) | 0,213 | 12,31% | 0,1 ms |
| Híbrido sem busca | 70,3% (68,9 a 71,6) | 0,616 | 77% | 11,7% (10,2 a 13,3) | 0,066 | 15,45% | 16,9 ms |
| **Híbrido com busca** | 77,3% (76,1 a 78,3) | 0,672 | 84% | 32,3% (30,1 a 34,6) | 0,258 | 17,35% | 24,6 ms |

Teste: 3.985 visitas com compra; "só novos": 1.499 visitas com pelo menos 1 produto comprado que a pessoa não tinha visto. Entre parênteses, intervalo de 95%. Cobertura sobre 104.874 produtos vistos ou comprados até 30/04. Tempo: mediana por pessoa, em CPU, numa VPS de 2 núcleos dividida com outros processos.


## O que os números dizem

- **A busca ajuda, e ajuda mais onde é difícil.** No mesmo híbrido, os sinais da busca somam **+7,0 pontos** de recall@10 contando tudo (70,3% para 77,3%) e **+20,7 pontos nos produtos que a pessoa ainda não tinha visto** (11,7% para 32,3%). Os dois intervalos ficam longe do zero. Nas 276 visitas em que a pessoa digitou termos, o híbrido foi de 57,6% para 66,4%.
- **Repetir o que a pessoa viu é difícil de bater:** 67,3% só listando o que ela viu, do mais recente ao mais antigo. Quem compra quase sempre olhou o produto antes. Por isso o híbrido usa esse sinal e soma os outros por cima.
- **Mais vendidos não serve para isto** (0,6%): a lista é igual para todo mundo e cobre 10 produtos de 104.874.
- **O sequencial (SASRec) ganha do item a item** (34,2% contra 24,1%; 7,9% contra 2,8% nos produtos novos), mas sozinho perde de "repetir": ele aprendeu a prever o próximo produto *visto*, que quase nunca é um repetido.
- **O que mais pesa no híbrido com busca** (ganho no LightGBM): o que ela viu e quão recente, o clique vindo da busca e a nota da busca (posição na lista mostrada).
- **Custo:** o melhor modelo leva 25 ms por pessoa em CPU; repetir o que viu leva menos de 0,1 ms.


## O aviso de promoção

"O que você costuma comprar está em promoção" está em `src/proxima_compra/promocao.py`: pega os produtos
habituais da pessoa (compras pesam 3, visitas antigas 1, a de hoje 0,5) e avisa os que estão pelo menos 10% abaixo
do preço normal. **A base não tem preço por dia**, então isto não entra na medição; na página ele roda com preços
simulados, marcados como simulação.

## Limites honestos

- Teste offline: mostra o que teria dado certo no passado. Não substitui um teste A/B com gente de verdade.
- "Busca" aqui é quase sempre abrir uma página de categoria; poucas visitas digitaram termos (276 das
  3.985 do teste). O ganho da busca vem principalmente da lista que a loja mostrou.
- Pouca gente logada (83 visitas do teste com compra anterior): o sinal "comprou antes" quase não existe aqui.
- Loja da Europa em 2016, não um app de comida no Brasil. O método serve; os números não se transferem.
- O sequencial foi treinado em CPU com poucas épocas (gasto zero). Com GPU e mais tempo ele provavelmente melhora.

## Como rodar

```bash
make instalar          # venv + PyTorch CPU + dependências
make baixar            # precisa do token do Kaggle (cópia pública da Diginetica)
make preparar          # CSV -> Parquet (DuckDB)
make avaliar           # treina, mede, grava reports/ e docs/index.html
make testes            # pytest + ruff
python3 tests/pagina_playwright.py   # confere a página em 1440 px e 390 px (precisa do Playwright)
```

A rodada completa (`make avaliar`, sem contar o treino do sequencial já guardado) levou 6 min numa VPS de 2 núcleos.

## Estrutura

```
src/proxima_compra/
  dados.py       CSV da Diginetica -> Parquet
  casos.py       divisão por data e os casos (visita cortada no pagamento)
  modelos.py     mais vendidos, repetir, item a item, busca (BM25 nos termos cifrados)
  sequencial.py  SASRec em PyTorch (CPU)
  ranker.py      híbridos com LightGBM LambdaRank, com e sem busca
  metricas.py    recall@10, NDCG@10, acerto@10, cobertura, bootstrap
  promocao.py    aviso "o que você compra está em promoção"
  avaliar.py     roda tudo e grava reports/resultados.json e .md
  demo.py        exporta a amostra e monta docs/index.html
site/modelo.html modelo da página (os dados entram embutidos; não precisa de servidor)
reports/         resultados.json, resultados.md, demo.json
```

## Referências

- CIKM Cup 2016, trilha 2: Personalized E-Commerce Search Challenge (dados da DIGINETICA).
- Kang e McAuley, *Self-Attentive Sequential Recommendation* (SASRec), ICDM 2018.
- Burges, *From RankNet to LambdaRank to LambdaMART*, 2010; LightGBM.
- iFood, *Personalized Recommendation of Dish and Restaurant Collections on iFood* (RED), arXiv 2508.03670, 2025:
  embeddings de usuário vindos da busca e LightGBM por cima, a mesma ideia em escala de produção.

---

Projeto de portfólio de Rafael Bueno, feito com apoio de IA. Código sob licença MIT; os dados seguem os termos
originais.
