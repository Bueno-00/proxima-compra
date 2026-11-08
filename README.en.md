# Next purchase

[Português](README.md) · **English** · **Demo:** https://bueno-00.github.io/proxima-compra/

Recommends the **next 10 products** a person should buy using what they **viewed, bought and searched for**, and
shows why each one was suggested ("you searched for this", "people who viewed what you viewed bought this").
Seven recommenders compared on **the same time-split test** over public data from a real online store.

> **Result (May 2016 test, 3,985 visits with a purchase).** The hybrid with search gets at least 1 of the 10 right in **84%** of visits (recall@10 77.3%). **Search adds +7.0 points** of recall@10 over the same hybrid without search (interval +6.1 to +7.8) and **+20.7 points on products the person had not seen yet** (11.7% to 32.3%). Time per person: 25 ms on CPU. Cost: zero (no paid API, no GPU).

---

## For online stores and grocery shops

**The problem.** Customers come to your site, open a few products, search and often leave with nothing, or only with
what they came for. Your store already records all of this (what they viewed, searched for and bought), but almost
always shows the same shop window to everyone.

**What this project does.** It builds, on the spot, a list of 10 products for each person, with the reason for each
one, combining what they **viewed**, **bought** and **searched for**.

### An example, step by step (illustrative)

> The customer and the products in this example are made up, just to show the idea. The way of choosing and the kinds
> of reasons are the same ones the model uses on the real data.

1. **Two weeks ago** she bought a chocolate protein drink in your store. She was logged in, so the purchase is in her
   history.
2. **Today** she types "whey" in the search, clicks the 900 g vanilla whey and also opens a protein bar.
3. **In about 25 milliseconds** the model puts the clues together (what she bought before, what she viewed now, what
   she searched for and what other people on the same path bought), scores each product and keeps the top 10.
4. **The list shows up** in the cart or on the product page, each item with its reason:

| # | Suggestion | Reason she sees | Where the clue comes from |
|---|---|---|---|
| 1 | Whey 900 g vanilla | You clicked it in your search for "whey" | search |
| 2 | Whey 900 g chocolate | Ranked #2 in your search for "whey" | search |
| 3 | Chocolate protein drink, 6 pack | You bought it 2 weeks ago | earlier purchase |
| 4 | Strawberry protein drink | People who bought the chocolate one also bought this | bought together (item to item) |
| 5 | Peanut protein bar | You viewed it a moment ago | what she viewed |
| 6 | Shaker 600 ml | Usually viewed right after whey | sequence (SASRec) |

5. **She buys the 900 g chocolate whey**, which she never opened. This is the new sale, the one the "new products
   only" reading measures, and it is where search helped the most in the test (hit rate from 11.7% to 32.3%).
6. **The following week** the chocolate drink goes on sale and she gets an alert by email or WhatsApp. (In the project
   this part runs on simulated prices, because the public data has no daily prices.)

Why not just show the best sellers? Because they are the same for everyone: in the test, the best sellers list got
only 0.6% of what people bought.

### What your store gains (measured)

| | Number | What it means |
|---|---|---|
| Hit on the list | **84%** | in 84 out of every 100 visits that ended in a purchase, the person bought at least 1 of the 10 suggested |
| New sales | **+20.7 points** | on products they had not seen yet, using search raised the hit rate from 11.7% to 32.3% |
| Speed | **25 ms** | to build one person's list on a regular computer, no graphics card |
| Cost | **R$ 0** | no paid API and no graphics card; the whole test ran on a simple 2-core server |

**Where the numbers come from:** public data from a European online store, January to June 2016 (Diginetica, CIKM
Cup 2016), tested on 3,985 visits with a purchase in May. The store replaced each product name with a number before
releasing the data; that is why the demo shows "Product #25911" and not "Whey 900 g chocolate". It is a test on the
past: in your store the numbers will differ.

### What it takes to do this in your store

- **The data you already have:** visits (which products each person opened, and when), searches (what they typed,
  what the search showed and what they clicked) and purchases (ideally with the customer logged in). Optional: each
  day's price, for the sale alert. Most online stores already record this, in the platform itself or in an analytics
  tool such as Google Analytics. A few months of history is enough to start (this test used 4).
- **Where the list shows up:** product page ("people who viewed this also bought"), cart ("before you pay, don't
  forget"), email or WhatsApp ("what you buy is on sale") and home page ("picked for you").
- **How to know it worked (A/B test):** a random half of customers sees the new list; the other half sees the store
  as it is today. After 2 to 4 weeks you compare sales per visit, average order value and how many people click the
  list. Keep the list only if it wins.

### Quick glossary

- **Visit:** one trip to the store, from arrival to leaving. The test only counts visits with a purchase.
- **Product #25911:** the product code. The store replaced names with numbers before releasing the data.
- **Search:** when the person types something or opens a category. The store shows a list and they click some items.
- **The 7 approaches:** 7 ways to choose the 10 products, from the simplest (best sellers, the same for everyone) to
  the most complete (the hybrid with search).
- **Hybrid:** combines the suggestions of the simpler approaches, and a model (LightGBM) learns the best order. "With
  search" also uses the search clues.
- **Everything bought:** getting any product bought in the visit right counts, including ones they had already opened.
- **New products only:** only getting right what they bought without having seen it before counts. This is the new
  sale, the hardest one.
- **Recall@10 (hit rate):** of the products they bought, how many were among the 10 suggested.
- **Hit 1+:** the list had at least 1 product the person bought in that visit.
- **Points:** the difference between two percentages. From 70.3% to 77.3% is +7.0 points.
- **95% interval:** the range where the true number should be, computed by resampling the visits 1,000 times.

---

## The question

The idea behind the project: a good recommender should use not only what the person bought, but also what they
**searched for**. Someone who bought a protein drink and searched for whey should see other flavors, the whey and
what they already looked for, not the store's best sellers. The question measured here is simple: **does adding
search signals to the model improve the suggestions? By how much?**

## The data, and why this dataset

| Dataset | Purchases | Search | Linked to the same person or visit | License | Decision |
|---|---|---|---|---|---|
| **Diginetica (CIKM Cup 2016, track 2)** | yes | yes (typed terms and category pages, with the list shown and the clicks) | yes | released for research in the competition; no license text found | **chosen** |
| Retailrocket (Kaggle) | yes | no | yes | CC BY-NC-SA 4.0 | no search |
| Instacart Market Basket | orders only | no | yes | competition terms | no search |
| Coveo SIGIR eCom 2021 | yes | yes (vectors) | session only | research only, registration and signed agreement | closed access |
| OTTO (Kaggle) | yes | no | yes | CC BY 4.0 | no search |

Diginetica is the only open dataset where the same visit has **search, viewed products and a purchase**, with
the time of each event. It has 1,235,380 product views, 923,127 searches and 18,025 purchases from
January to June 2016. Two things work against it, and they show in the numbers:

- **Product names and search terms are encrypted** (each word became a number). We can tell that a search and a
  product name share a word, but not which word. That is why the demo shows "Product #25911".
- **Almost nobody is logged in.** The "bought before" signal shows up in few visits. In an app like iFood
  everyone is logged in, and that signal would be the strongest.

**Raw data is not in this repository.** `make baixar` fetches a public copy on Kaggle; the original source is the
CIKM Cup 2016. The page uses only a derived sample of 36 visits (numeric codes).

## How it was measured

- **Split by date.** Hybrid fitting: models trained on everything up to 03/31/2016 and cases from April. Test:
  models trained on everything up to 04/30/2016 and cases from **May** (3,985 visits with a purchase,
  5,445 products bought). No model sees the test month.
- **Each case is a visit with a purchase, cut at the moment of paying.** Input: what the person viewed and
  searched before paying in this visit and, if logged in, in visits from previous days. Correct answer: what
  they bought in this visit.
- **Two readings of the same test.** *Everything bought*: any purchased product counts. *New products only*
  (discovery): products the person had already viewed are removed from the list and from the answer; only buying
  something they had not seen before counts, which is the "other flavors, whey" case.
- **Metrics.** Recall@10 (of the products bought, how many were among the 10), NDCG@10 (the same, with hits at
  the top counting more), hit@10 (at least 1 of the 10 bought), coverage (how much of the catalog shows up in some
  list) and time to build one person's list on CPU. 95% intervals by bootstrap (visits resampled 1,000 times).
- **How much search helps:** the same hybrid trained twice, with and without search signals, compared visit by
  visit (paired difference with an interval).

## The 7 approaches

| Model | What it does | Uses search |
|---|---|---|
| Best sellers | top 10 sellers of the last 28 days, the same for everyone | no |
| Repeat what you viewed or bought | products the person viewed or bought, most recent first | no |
| Item to item | "people who viewed what you viewed bought this": counts (viewed, bought) pairs in training visits | no |
| Sequential (SASRec) | small transformer (2 layers, 64 dimensions) that reads the order of viewed products and predicts the next one; trained on CPU | no |
| Search only | products the store showed in the searches (weighted by position), the clicked ones and the ones whose name has the typed terms (BM25) | yes |
| Hybrid without search | merges the candidates of the first 4 and reranks them with LightGBM (LambdaRank), 17 signals | no |
| Hybrid with search | the same, plus 9 search signals (position in the list, clicks, terms, searched category) | yes |

## Results (May 2016 test)

| Model | Recall@10 | NDCG@10 | Hit 1+ | Recall@10 new only | NDCG@10 new only | Coverage | Time per person |
|---|---|---|---|---|---|---|---|
| Best sellers | 0.6% (0.3 to 0.8) | 0.003 | 1% | 0.5% (0.2 to 0.9) | 0.003 | 0.01% | < 0.1 ms |
| Repeat what you viewed or bought | 67.3% (65.9 to 68.6) | 0.603 | 73% | 0.5% (0.2 to 0.9) | 0.003 | 10.38% | < 0.1 ms |
| Item to item | 24.1% (22.9 to 25.4) | 0.185 | 27% | 2.8% (2.0 to 3.5) | 0.020 | 4.83% | 0.4 ms |
| Sequential (SASRec) | 34.2% (32.8 to 35.6) | 0.220 | 38% | 7.9% (6.7 to 9.2) | 0.045 | 7.85% | 3.0 ms |
| Search only | 59.2% (57.8 to 60.7) | 0.521 | 66% | 26.5% (24.4 to 28.6) | 0.213 | 12.31% | 0.1 ms |
| Hybrid without search | 70.3% (68.9 to 71.6) | 0.616 | 77% | 11.7% (10.2 to 13.3) | 0.066 | 15.45% | 16.9 ms |
| **Hybrid with search** | 77.3% (76.1 to 78.3) | 0.672 | 84% | 32.3% (30.1 to 34.6) | 0.258 | 17.35% | 24.6 ms |

Test: 3,985 visits with a purchase; "new only": 1,499 visits with at least 1 bought product the person had not viewed. In parentheses, 95% interval. Coverage over 104,874 products viewed or bought up to 04/30. Time: median per person, on CPU, on a shared 2-core VPS.


## What the numbers say

- **Search helps, and it helps most where it is hard.** In the same hybrid, search signals add **+7.0 points** of recall@10 counting everything bought (70.3% to 77.3%) and **+20.7 points on products the person had not seen yet** (11.7% to 32.3%). Both intervals stay far from zero. In the 276 visits where the person typed terms, the hybrid went from 57.6% to 66.4%.
- **Repeating what the person viewed is hard to beat:** 67.3% just by listing what they viewed, most recent first. People who buy almost always looked at the product before. That is why the hybrid uses this signal and adds the others on top.
- **Best sellers do not work here** (0.6%): the list is the same for everyone and covers 10 products out of 104,874.
- **The sequential model (SASRec) beats item to item** (34.2% vs 24.1%; 7.9% vs 2.8% on new products), but on its own it loses to "repeat": it learned to predict the next *viewed* product, which is almost never a repeat.
- **What weighs most in the hybrid with search** (LightGBM gain): what they viewed and how recently, the click coming from search and the search score (position in the list shown).
- **Cost:** the best model takes 25 ms per person on CPU; repeating what was viewed takes under 0.1 ms.


## The sale alert

"What you usually buy is on sale" lives in `src/proxima_compra/promocao.py`: it takes the person's usual products
(purchases weigh 3, older visits 1, today's 0.5) and flags the ones at least 10% below the normal price. **The
dataset has no daily prices**, so this is not part of the measurement; on the page it runs on simulated prices,
labeled as a simulation.

## Honest limits

- Offline test: it shows what would have worked in the past. It does not replace an A/B test with real people.
- "Search" here is mostly opening a category page; few visits typed terms (276 of the 3,985 test visits).
  Most of the search gain comes from the list the store showed.
- Few logged-in people (83 test visits with an earlier purchase): the "bought before" signal barely exists here.
- A European store in 2016, not a food delivery app in Brazil. The method carries over; the numbers do not.
- The sequential model was trained on CPU for few epochs (zero budget). With a GPU and more time it would likely
  improve.

## How to run

```bash
make instalar          # venv + PyTorch CPU + dependencies
make baixar            # needs a Kaggle token (public copy of Diginetica)
make preparar          # CSV -> Parquet (DuckDB)
make avaliar           # trains, measures, writes reports/ and docs/index.html
make testes            # pytest + ruff
python3 tests/pagina_playwright.py   # checks the page at 1440 px and 390 px (needs Playwright)
```

A full run (`make avaliar`, not counting the cached sequential training) took 6 min on a 2-core VPS.

## Layout

```
src/proxima_compra/
  dados.py       Diginetica CSV -> Parquet
  casos.py       time split and cases (visit cut at payment)
  modelos.py     best sellers, repeat, item to item, search (BM25 over encrypted terms)
  sequencial.py  SASRec in PyTorch (CPU)
  ranker.py      LightGBM LambdaRank hybrids, with and without search
  metricas.py    recall@10, NDCG@10, hit@10, coverage, bootstrap
  promocao.py    "what you buy is on sale" alert
  avaliar.py     runs everything and writes reports/resultados.json and .md
  demo.py        exports the sample and builds docs/index.html
site/modelo.html page template (data is embedded; no server needed)
reports/         resultados.json, resultados.md, demo.json
```

## References

- CIKM Cup 2016, track 2: Personalized E-Commerce Search Challenge (DIGINETICA data).
- Kang and McAuley, *Self-Attentive Sequential Recommendation* (SASRec), ICDM 2018.
- Burges, *From RankNet to LambdaRank to LambdaMART*, 2010; LightGBM.
- iFood, *Personalized Recommendation of Dish and Restaurant Collections on iFood* (RED), arXiv 2508.03670, 2025:
  user embeddings from search plus LightGBM on top, the same idea at production scale.

---

Portfolio project by Rafael Bueno, built with AI assistance. Code under the MIT license; the data keeps its
original terms.
