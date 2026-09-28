"""Validador literal de citações (PLANO_FINAL.md §7, passo 3).

Regra de ouro: **tolerância zero para palavras diferentes**. Todo trecho que a IA cita como
vindo do documento precisa existir, ao pé da letra, no texto extraído da página indicada
(`arquivo_pagina.texto`). A normalização aqui trata só artefatos de formatação — nunca
corrige grafia, sinônimos ou paráfrase:

- Unicode NFKC (formas equivalentes de um mesmo caractere).
- Aspas e travessões tipográficos → formas retas (" ' -).
- Hifenização de quebra de linha ("desenvolvi-\\nmento" → "desenvolvimento").
- Sequências de espaço/quebra de linha → um único espaço.

Um trecho que não valida é descartado (nunca "corrigido" ou "aproximado") e o descarte é
registrado em log — ver `docs/metodologia/ia.md`.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("raiox.ia.validador")

_ASPAS_TRAVESSOES = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "«": '"',
        "»": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "‹": "'",
        "›": "'",
        "–": "-",
        "—": "-",
        " ": " ",  # espaço não separável
    }
)

# junta palavra quebrada por hífen de fim de linha: "desenvolvi-\n mento" -> "desenvolvimento"
_QUEBRA_HIFEN = re.compile(r"(\w)-\s*\n\s*(\w)")
_ESPACOS = re.compile(r"\s+")


def normaliza(texto: str | None) -> str:
    """Normaliza um texto para comparação literal — preserva grafia e ordem das palavras."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKC", texto)
    t = t.translate(_ASPAS_TRAVESSOES)
    t = _QUEBRA_HIFEN.sub(r"\1\2", t)
    t = _ESPACOS.sub(" ", t)
    return t.strip()


def trecho_existe(trecho: str, texto_pagina: str) -> bool:
    """True se `trecho` existe literalmente (após normalização de formatação) em `texto_pagina`."""
    alvo = normaliza(trecho)
    if not alvo:
        return False
    return alvo in normaliza(texto_pagina)


def pagina_do_trecho(trecho: str, paginas: dict[int, str]) -> int | None:
    """Varre `paginas` (nº → texto) e devolve a primeira página onde `trecho` existe literalmente."""
    for pagina in sorted(paginas):
        if trecho_existe(trecho, paginas[pagina]):
            return pagina
    return None


@dataclass(frozen=True)
class Descarte:
    trecho: dict[str, Any]
    motivo: str


def valida_trechos(
    trechos: list[dict[str, Any]],
    paginas: dict[int, str],
    *,
    on_descarte: Callable[[Descarte], None] | None = None,
) -> list[dict[str, Any]]:
    """Filtra `trechos` ([{"texto": str, "pagina": int}, ...]), mantendo só os que existem
    literalmente na página informada. Retorna a lista de trechos válidos, na mesma forma.
    """
    validos: list[dict[str, Any]] = []
    for t in trechos:
        pagina = t.get("pagina")
        texto = (t.get("texto") or "").strip()
        motivo: str | None = None
        if not texto:
            motivo = "trecho vazio"
        elif pagina not in paginas:
            motivo = f"página {pagina} não faz parte do documento"
        elif not trecho_existe(texto, paginas[pagina]):
            motivo = "trecho não encontrado literalmente no texto da página citada"
        if motivo:
            d = Descarte(trecho=t, motivo=motivo)
            if on_descarte:
                on_descarte(d)
            else:
                log.warning("Trecho descartado (%s): %r", motivo, texto[:160])
            continue
        validos.append({"texto": texto, "pagina": pagina})
    return validos
