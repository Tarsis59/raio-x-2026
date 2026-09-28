"""Saldo mensal de empregos formais (CAGED), via republicação do IPEADATA.

O Novo CAGED (MTE/PDET, desde jan/2020) não expõe uma API pública de série temporal —
só microdados brutos (um registro por admissão/desligamento) via FTP
(`ftp://ftp.mtps.gov.br/pdet/microdados/NOVO CAGED/`), inviáveis de processar por UF
dentro de uma execução deste job. O IPEADATA republica o indicador oficial (mesma fonte,
MTE/SEPRT/Novo Caged) como série agregada **somente para o Brasil** — sem recorte por UF.

Por isso `caged_saldo` é coletado aqui **apenas para uf='BR'**; a UF fica como lacuna
documentada (ver relatório do job `economia`). Duas séries são concatenadas, com quebra
metodológica clara em jan/2020:

- `CAGED12_SALDO12` — "Empregados - saldo - INATIVA" (CAGED antigo, série descontinuada
  pela fonte; mai/1999 a dez/2019).
- `CAGED12_SALDON12` — "Empregados - saldo - sem ajuste - novo Caged" (desde jan/2020).

API: https://www.ipeadata.gov.br/api/odata4/ — pública, sem chave, protocolo OData v4.
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

import httpx
import orjson

from ..common.http import get_bytes

BASE = "http://www.ipeadata.gov.br/api/odata4"
SERIE_ANTIGA = "CAGED12_SALDO12"
SERIE_NOVA = "CAGED12_SALDON12"
DATA_QUEBRA = date(2020, 1, 1)


class PontoCaged(NamedTuple):
    data: date
    valor: float
    serie: str  # 'antiga' | 'nova'


def _metadado(c: httpx.Client, codigo: str) -> tuple[str, bytes]:
    url = f"{BASE}/Metadados('{codigo}')"
    conteudo, _ = get_bytes(c, url)
    linhas = orjson.loads(conteudo)["value"]
    if not linhas:
        return "", conteudo
    return linhas[0]["SERNOME"], conteudo


def _valores(c: httpx.Client, codigo: str) -> tuple[list[dict], bytes]:
    url = f"{BASE}/ValoresSerie(SERCODIGO='{codigo}')"
    conteudo, _ = get_bytes(c, url)
    return orjson.loads(conteudo)["value"], conteudo


def coletar(c: httpx.Client) -> tuple[list[PontoCaged], dict[str, str], dict[str, bytes]]:
    """Coleta as duas séries (antiga + nova) já concatenadas e ordenadas por data.

    Retorna `(pontos, nomes_oficiais, brutos)` — `nomes_oficiais` e `brutos` por código de
    série (para validação de metadado e evidência).
    """
    pontos: list[PontoCaged] = []
    nomes: dict[str, str] = {}
    brutos: dict[str, bytes] = {}

    for codigo, rotulo in ((SERIE_ANTIGA, "antiga"), (SERIE_NOVA, "nova")):
        nome, bruto_meta = _metadado(c, codigo)
        nomes[codigo] = nome
        valores, bruto_valores = _valores(c, codigo)
        brutos[codigo] = bruto_meta + b"\n" + bruto_valores
        for v in valores:
            if v["VALVALOR"] is None:
                continue
            d = date.fromisoformat(v["VALDATA"][:10])
            pontos.append(PontoCaged(d, float(v["VALVALOR"]), rotulo))

    pontos.sort(key=lambda p: p.data)
    return pontos, nomes, brutos
