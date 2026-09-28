"""Cliente do Sistema Gerenciador de Séries Temporais (SGS) do Banco Central.

Documentação: https://dadosabertos.bcb.gov.br/dataset/sgs — API pública, sem chave.
Formato: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa`.

Séries de periodicidade diária (ex.: câmbio, meta Selic) aceitam no máximo uma janela de
10 anos por consulta — o BCB responde com um erro explícito acima disso (verificado em
27/09/2026). Séries mensais/trimestrais aceitam o histórico completo numa única chamada.
O cliente pagina automaticamente quando `diario=True`.

Não há, na própria resposta da série, um campo com o nome/metadado oficial — por isso o
código de cada série usado por este ETL foi validado manualmente contra
https://dadosabertos.bcb.gov.br/dataset/{codigo}-... antes de ser fixado aqui (ver
relatório do job `economia`). A validação automática de regressão é feita por faixas de
valor plausíveis (`raiox.jobs.economia`), não pelo nome.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple

import httpx
import orjson

from ..common.http import get_bytes

BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"


class PontoSGS(NamedTuple):
    data: date
    valor: float


def _parse_data(txt: str) -> date:
    d, m, a = txt.split("/")
    return date(int(a), int(m), int(d))


def _parse_valor(txt: str) -> float:
    # A API do SGS usa ponto decimal, mas o parser aceita vírgula defensivamente.
    return float(txt.replace(",", "."))


def _parse_payload(bruto: list[dict]) -> list[PontoSGS]:
    return [PontoSGS(_parse_data(item["data"]), _parse_valor(item["valor"])) for item in bruto]


def url_serie(codigo: int, data_inicial: str | None = None, data_final: str | None = None) -> str:
    url = BASE.format(codigo=codigo) + "?formato=json"
    if data_inicial:
        url += f"&dataInicial={data_inicial}"
    if data_final:
        url += f"&dataFinal={data_final}"
    return url


def coletar(
    c: httpx.Client,
    codigo: int,
    *,
    diario: bool,
    inicio: date = date(1995, 1, 1),
    fim: date | None = None,
) -> tuple[list[PontoSGS], str, bytes]:
    """Coleta o histórico completo de uma série SGS.

    Retorna `(pontos, url_representativa, bruto_concatenado)`. `bruto_concatenado` é o
    JSON de todos os pontos coletados (uma ou mais páginas), serializado de novo — usado
    como payload de evidência da série nesta execução.
    """
    fim = fim or date.today()
    pontos: list[PontoSGS] = []
    url_base = url_serie(codigo)

    if not diario:
        url = url_serie(codigo, inicio.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"))
        conteudo, _ = get_bytes(c, url)
        pontos.extend(_parse_payload(orjson.loads(conteudo)))
        return pontos, url, conteudo

    # Série diária: janela máxima de 10 anos por chamada.
    janela_ini = inicio
    while janela_ini <= fim:
        janela_fim = min(date(janela_ini.year + 10, 1, 1) - timedelta(days=1), fim)
        url = url_serie(codigo, janela_ini.strftime("%d/%m/%Y"), janela_fim.strftime("%d/%m/%Y"))
        conteudo, _ = get_bytes(c, url)
        pontos.extend(_parse_payload(orjson.loads(conteudo)))
        janela_ini = janela_fim + timedelta(days=1)

    bruto_concat = orjson.dumps([{"data": p.data.strftime("%d/%m/%Y"), "valor": str(p.valor)} for p in pontos])
    return pontos, url_base, bruto_concat


def reduzir_mensal_ultimo(pontos: list[PontoSGS]) -> list[PontoSGS]:
    """Reduz uma série diária ao último valor observado em cada mês.

    Usado para a meta Selic: representa a meta vigente ao final de cada mês (não
    necessariamente a data exata de uma decisão do Copom — decisões passam a valer no
    dia seguinte à reunião e podem não coincidir com o fim do mês).
    """
    por_mes: dict[tuple[int, int], PontoSGS] = {}
    for p in sorted(pontos, key=lambda x: x.data):
        por_mes[(p.data.year, p.data.month)] = p
    return [PontoSGS(date(a, m, 1), v.valor) for (a, m), v in sorted(por_mes.items())]


def reduzir_mensal_media(pontos: list[PontoSGS]) -> list[PontoSGS]:
    """Reduz uma série diária à média aritmética simples de cada mês (ex.: câmbio)."""
    soma: dict[tuple[int, int], list[float]] = {}
    for p in pontos:
        soma.setdefault((p.data.year, p.data.month), []).append(p.valor)
    return [PontoSGS(date(a, m, 1), sum(vs) / len(vs)) for (a, m), vs in sorted(soma.items())]
