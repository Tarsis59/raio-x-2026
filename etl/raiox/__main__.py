"""Ponto de entrada: `python -m raiox <job> [opções]`.

Cada job é um módulo em `raiox.jobs` com uma função `main(argv: list[str]) -> None`.
Rode `python -m raiox --lista` para ver os jobs disponíveis.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import sys

from raiox import jobs


def _jobs() -> list[str]:
    return sorted(m.name.replace("_", "-") for m in pkgutil.iter_modules(jobs.__path__) if not m.name.startswith("_"))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "--lista"):
        print("Jobs disponíveis:\n  " + "\n  ".join(_jobs()))
        return
    nome = sys.argv[1].replace("-", "_")
    try:
        modulo = importlib.import_module(f"raiox.jobs.{nome}")
    except ModuleNotFoundError:
        print(f"Job desconhecido: {sys.argv[1]}. Use --lista.", file=sys.stderr)
        sys.exit(2)
    modulo.main(sys.argv[2:])


if __name__ == "__main__":
    main()
