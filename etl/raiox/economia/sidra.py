"""Cliente da API SIDRA do IBGE (apisidra.ibge.gov.br).

Tabelas usadas (validadas em 27-28/09/2026 contra `servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados`):

- **4099** — "Taxas de desocupação e de subutilização da força de trabalho..." (PNAD Contínua
  trimestral). Variável **4099** = "Taxa de desocupação, na semana de referência, das pessoas
  de 14 anos ou mais de idade" (%). Níveis territoriais N1 (Brasil) e N3 (UF) disponíveis.
  Sem classificação adicional.
- **5932** — "Taxa de variação do índice de volume trimestral" (Contas Nacionais Trimestrais).
  Variável **6562** = "Taxa acumulada em quatro trimestres (em relação ao mesmo período do ano
  anterior)". Classificação 11255 "Setores e subsetores", categoria **90707** = "PIB a preços de
  mercado". Só nível N1 (Brasil) disponível nesta tabela.

O nome da variável/categoria vem no próprio payload (`D2N`, `D4N`) — validado em tempo de
execução pelo job `economia` (`raiox.jobs.economia`), não apenas nesta constante.
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

import httpx
import orjson

from ..common.http import get_bytes

TABELA_DESOCUPACAO = 4099
VARIAVEL_DESOCUPACAO = 4099
TABELA_PIB = 5932
VARIAVEL_PIB_ACUM_4T = 6562
CLASSIFICACAO_SETOR = 11255
CATEGORIA_PIB_MERCADO = 90707

# Código IBGE de UF (2 dígitos) -> sigla.
UF_POR_CODIGO_IBGE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}

_VAZIOS = {None, "...", "-", "X", ".."}


class PontoSidra(NamedTuple):
    uf: str  # 'BR' ou sigla de UF
    data: date
    valor: float


def data_do_trimestre(codigo: str) -> date:
    """'202602' (2º trimestre de 2026) -> 2026-06-01 (representado pelo 1º dia do último
    mês do trimestre civil)."""
    ano = int(codigo[:4])
    trimestre = int(codigo[4:6])
    mes = trimestre * 3
    return date(ano, mes, 1)


def _get(c: httpx.Client, url: str) -> tuple[list[dict], bytes]:
    conteudo, _ = get_bytes(c, url)
    linhas = orjson.loads(conteudo)
    return linhas[1:], conteudo  # primeira linha é o cabeçalho de descrição das colunas


def desocupacao_brasil(c: httpx.Client) -> tuple[list[PontoSidra], str, bytes, set[str]]:
    url = (f"https://apisidra.ibge.gov.br/values/t/{TABELA_DESOCUPACAO}/n1/all"
           f"/v/{VARIAVEL_DESOCUPACAO}/p/all?formato=json")
    linhas, bruto = _get(c, url)
    pontos = [
        PontoSidra("BR", data_do_trimestre(row["D3C"]), float(row["V"]))
        for row in linhas if row["V"] not in _VAZIOS
    ]
    nomes_variavel = {row["D2N"] for row in linhas}
    return pontos, url, bruto, nomes_variavel


def desocupacao_uf(c: httpx.Client) -> tuple[list[PontoSidra], str, bytes, set[str]]:
    url = (f"https://apisidra.ibge.gov.br/values/t/{TABELA_DESOCUPACAO}/n3/all"
           f"/v/{VARIAVEL_DESOCUPACAO}/p/all?formato=json")
    linhas, bruto = _get(c, url)
    pontos = []
    for row in linhas:
        sigla = UF_POR_CODIGO_IBGE.get(row["D1C"])
        if sigla and row["V"] not in _VAZIOS:
            pontos.append(PontoSidra(sigla, data_do_trimestre(row["D3C"]), float(row["V"])))
    nomes_variavel = {row["D2N"] for row in linhas}
    return pontos, url, bruto, nomes_variavel


def pib_variacao_acumulada(c: httpx.Client) -> tuple[list[PontoSidra], str, bytes, set[str], set[str]]:
    url = (f"https://apisidra.ibge.gov.br/values/t/{TABELA_PIB}/n1/all"
           f"/v/{VARIAVEL_PIB_ACUM_4T}/p/all/c{CLASSIFICACAO_SETOR}/{CATEGORIA_PIB_MERCADO}?formato=json")
    linhas, bruto = _get(c, url)
    pontos = [
        PontoSidra("BR", data_do_trimestre(row["D3C"]), float(row["V"]))
        for row in linhas if row["V"] not in _VAZIOS
    ]
    nomes_variavel = {row["D2N"] for row in linhas}
    nomes_categoria = {row["D4N"] for row in linhas}
    return pontos, url, bruto, nomes_variavel, nomes_categoria
