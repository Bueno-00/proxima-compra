"""Confere a página no navegador (Chromium sem janela): 1440 px e 390 px (e 1024, 820, 360), PT e EN, cliques.

Uso: python3 tests/pagina_playwright.py [docs/index.html] [pasta_das_capturas]
Não roda no pytest (precisa de navegador). Sai com código 1 se algo falhar.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "index.html"
CAPTURAS = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / ".tmp" / "capturas"
CHROMIUM = os.environ.get("CHROMIUM_PATH") or None


def main() -> int:
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    falhas: list[str] = []
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=CHROMIUM)
        for largura in (1024, 820, 360):
            pg = nav.new_page(viewport={"width": largura, "height": 800})
            pg.goto(PAGINA.resolve().as_uri())
            pg.wait_for_selector("#tabela tbody tr")
            lateral = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if lateral > 0:
                falhas.append(f"{largura} px: rolagem lateral de {lateral} px")
            pg.close()
        for largura, altura, nome in ((1440, 900, "pc"), (390, 844, "celular")):
            pg = nav.new_page(viewport={"width": largura, "height": altura}, device_scale_factor=1)
            erros: list[str] = []
            pg.on("pageerror", lambda e, erros=erros: erros.append(str(e)))
            pg.on("console", lambda m, erros=erros: erros.append(m.text) if m.type == "error" else None)
            pg.goto(PAGINA.resolve().as_uri())
            pg.wait_for_selector("#tabela tbody tr")
            linhas = pg.locator("#tabela tbody tr").count()
            if linhas != 7:
                falhas.append(f"{nome}: tabela com {linhas} linhas")
            lateral = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if lateral > 0:
                falhas.append(f"{nome}: rolagem lateral de {lateral} px")
            if pg.locator("ol.recs li").count() != 10:
                falhas.append(f"{nome}: lista sem 10 sugestões")
            # parte para o dono de loja: abertura, exemplo ilustrativo, ganhos medidos, como fazer, glossário
            if "Mostre a cada cliente" not in pg.inner_text("#loja h1:visible"):
                falhas.append(f"{nome}: abertura para a loja não apareceu")
            if "ilustrativo" not in pg.inner_text("#exemplo").lower():
                falhas.append(f"{nome}: o exemplo não diz que é ilustrativo")
            for sel in ("#exemplo", "#ganho", "#implementar", "#glossario"):
                if not pg.locator(sel).is_visible():
                    falhas.append(f"{nome}: seção {sel} não aparece")
            vazios = pg.evaluate(
                "[...document.querySelectorAll('[data-v]')].filter(e => e.offsetParent && !e.textContent.trim()).length"
            )
            if vazios:
                falhas.append(f"{nome}: {vazios} número(s) sem valor")
            ganho = pg.inner_text("#ganho")
            for esperado in ("84%", "+20,7", "25 ms", "R$ 0", "Produto #25911"):
                if esperado not in ganho:
                    falhas.append(f"{nome}: falta {esperado!r} em 'o que a loja ganha'")
            if pg.locator("#glossario dl:visible .gl").count() < 10:
                falhas.append(f"{nome}: glossário com menos de 10 termos")
            pg.screenshot(path=str(CAPTURAS / f"{nome}-inicio.png"), full_page=False)
            pg.screenshot(path=str(CAPTURAS / f"{nome}-inteira.png"), full_page=True)
            for sel, arq in (("#exemplo", "exemplo"), ("#ganho", "ganho"), ("#implementar", "implementar"),
                             ("#glossario", "glossario"), ("#comparacao", "tabela")):
                pg.locator(sel).screenshot(path=str(CAPTURAS / f"{nome}-{arq}.png"))
            # troca de modelo, de visita e de leitura
            for modelo in ("popularidade", "visto", "coocorrencia", "sequencial", "busca", "hibrido_sem_busca",
                           "hibrido_com_busca"):
                pg.click(f"[data-modelo='{modelo}']")
                if pg.locator("ol.recs li").count() != 10:
                    falhas.append(f"{nome}: {modelo} sem 10 sugestões")
            pg.click("#prox")
            pg.click("#seg-leitura-2 [data-leitura='descoberta']")
            if "novos" not in pg.inner_text("#recs").lower():
                falhas.append(f"{nome}: leitura descoberta não mudou o texto")
            pg.locator("#visita").screenshot(path=str(CAPTURAS / f"{nome}-visita-descoberta.png"))
            pg.click("#seg-leitura-2 [data-leitura='geral']")
            pg.click("[data-lang='en']")
            if "Look at a real visit" not in pg.inner_text("#visita h2"):
                falhas.append(f"{nome}: inglês não aplicou")
            if "Show each customer" not in pg.inner_text("#loja h1:visible"):
                falhas.append(f"{nome}: abertura em inglês não aplicou")
            if "illustrative" not in pg.inner_text("#exemplo").lower():
                falhas.append(f"{nome}: exemplo em inglês não diz que é ilustrativo")
            texto_en = pg.inner_text("body")
            for proibido in ("—", "–", "undefined", "NaN", "{"):
                if proibido in texto_en:
                    falhas.append(f"{nome}: texto em inglês com {proibido!r}")
            lateral = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if lateral > 0:
                falhas.append(f"{nome}: rolagem lateral de {lateral} px em inglês")
            pg.screenshot(path=str(CAPTURAS / f"{nome}-en.png"), full_page=False)
            pg.locator("#exemplo").screenshot(path=str(CAPTURAS / f"{nome}-exemplo-en.png"))
            pg.locator("#visita").screenshot(path=str(CAPTURAS / f"{nome}-visita-en.png"))
            pg.click("[data-lang='pt']")
            texto = pg.inner_text("body")
            for proibido in ("—", "–", "undefined", "NaN", "{"):
                if proibido in texto:
                    falhas.append(f"{nome}: texto com {proibido!r}")
            if erros:
                falhas.append(f"{nome}: erros no console: {erros[:3]}")
            pg.close()
        # tema escuro
        ctx = nav.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        pg = ctx.new_page()
        pg.goto(PAGINA.resolve().as_uri())
        pg.wait_for_selector("#tabela tbody tr")
        pg.screenshot(path=str(CAPTURAS / "pc-escuro.png"), full_page=False)
        ctx.close()
        nav.close()
    if falhas:
        print("FALHAS:\n- " + "\n- ".join(falhas))
        return 1
    print(f"ok: 1440 px e 390 px, PT e EN, 7 modelos, sem rolagem lateral; capturas em {CAPTURAS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
