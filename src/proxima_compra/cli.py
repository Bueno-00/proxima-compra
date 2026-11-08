"""Linha de comando: `pc preparar`, `pc avaliar`, `pc pagina`."""

from __future__ import annotations

import argparse
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pc", description="Próxima compra: compara recomendadores com e sem busca")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preparar", help="converte os CSVs de data/raw para Parquet em data/interim")
    sub.add_parser("avaliar", help="treina, mede no teste de maio e grava reports/ e a página")
    sub.add_parser("pagina", help="remonta docs/index.html a partir de reports/demo.json")
    args = ap.parse_args(argv)

    raw, interim = RAIZ / "data" / "raw", RAIZ / "data" / "interim"
    if args.cmd == "preparar":
        from .dados import converter

        for nome, n in converter(raw, interim).items():
            print(f"{nome}: {n:,} linhas".replace(",", "."))
    elif args.cmd == "avaliar":
        from .avaliar import rodar
        from .demo import exportar, montar_pagina

        res = rodar(interim, RAIZ / "reports", RAIZ / "data" / "modelos")
        exportar(res, RAIZ / "reports" / "demo.json")
        tam = montar_pagina(RAIZ / "reports" / "demo.json", RAIZ / "site" / "modelo.html", RAIZ / "docs" / "index.html")
        print(f"página: docs/index.html ({tam / 1024:.0f} KB)")
    elif args.cmd == "pagina":
        from .demo import montar_pagina

        tam = montar_pagina(RAIZ / "reports" / "demo.json", RAIZ / "site" / "modelo.html", RAIZ / "docs" / "index.html")
        print(f"página: docs/index.html ({tam / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
