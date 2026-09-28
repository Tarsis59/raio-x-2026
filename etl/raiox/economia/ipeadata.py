"""Cliente para o IPEADATA (api.bcb-like OData4) — usado só para republicar o CAGED antigo
(pré-2020, descontinuado), que não tem mais fonte primária oficial com API.

http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{codigo}') devolve
[{"VALDATA": "1999-05-01T00:00:00-03:00", "VALVALOR": 123456.0, ...}, ...].
"""

from __future__ import annotations

import datetime as dt

import httpx

from ..common.http import get_json

BASE = "http://www.ipeadata.gov.br/api/odata4"


def metadados(c: httpx.Client, codigo: str) -> dict:
    r = get_json(c, f"{BASE}/Metadados('{codigo}')")
    return r["value"][0] if isinstance(r, dict) and r.get("value") else r


def coletar_serie_bruta(c: httpx.Client, codigo: str) -> list[dict]:
    r = get_json(c, f"{BASE}/ValoresSerie(SERCODIGO='{codigo}')")
    return r["value"] if isinstance(r, dict) else r


def parse_pontos(bruto: list[dict]) -> list[tuple[dt.date, float]]:
    """Converte VALDATA (ISO 8601 com timezone) + VALVALOR em (date, float), ignorando pontos
    sem valor (VALVALOR None, comum no início/fim de séries do IPEADATA)."""
    pontos = []
    for p in bruto:
        if p.get("VALVALOR") is None:
            continue
        data = dt.date.fromisoformat(p["VALDATA"][:10])
        pontos.append((data, float(p["VALVALOR"])))
    pontos.sort(key=lambda x: x[0])
    return pontos
