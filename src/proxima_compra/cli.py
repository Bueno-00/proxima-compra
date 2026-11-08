"""Linha de comando: `pc preparar`, `pc avaliar`, `pc pagina`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pc", description="Próxima compra: compara recomendadores com e sem busca")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preparar", help="converte os CSVs de data/raw para Parquet em data/interim")
    sub.add_parser("avaliar", help="treina, mede no teste de maio e grava reports/ e a página")
    sub.add_parser("pagina", help="remonta docs/index.html a partir de reports/demo.json")
    sub.add_parser("pares", help="conta os pares de produtos comprados juntos e grava reports/pares.json")
    args = ap.parse_args(argv)

    raw, interim = RAIZ / "data" / "raw", RAIZ / "data" / "interim"
    arq_pares = RAIZ / "reports" / "pares.json"

    def extras() -> dict | None:
        return {"pares": json.loads(arq_pares.read_text())} if arq_pares.exists() else None
    if args.cmd == "preparar":
        from .dados import converter

        for nome, n in converter(raw, interim).items():
            print(f"{nome}: {n:,} linhas".replace(",", "."))
    elif args.cmd == "avaliar":
        from .avaliar import rodar
        from .demo import exportar, montar_pagina

        res = rodar(interim, RAIZ / "reports", RAIZ / "data" / "modelos")
        from .pares import resumo_pares

        exportar(res, RAIZ / "reports" / "demo.json")
        arq_pares.write_text(json.dumps(resumo_pares(interim), ensure_ascii=False, indent=2) + "\n")
        tam = montar_pagina(RAIZ / "reports" / "demo.json", RAIZ / "site" / "modelo.html", RAIZ / "docs" / "index.html",
                            extras())
        print(f"página: docs/index.html ({tam / 1024:.0f} KB)")
    elif args.cmd == "pares":
        from .pares import resumo_pares

        arq_pares.write_text(json.dumps(resumo_pares(interim), ensure_ascii=False, indent=2) + "\n")
        print(arq_pares.read_text())
    elif args.cmd == "pagina":
        from .demo import montar_pagina

        tam = montar_pagina(RAIZ / "reports" / "demo.json", RAIZ / "site" / "modelo.html", RAIZ / "docs" / "index.html",
                            extras())
        print(f"página: docs/index.html ({tam / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
