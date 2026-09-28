"""Job `periodos_governo`: mandatos de Presidente da República desde 1995 — usados no
dashboard `/economia` para sombrear as faixas de governo.

Escopo do Raio-X 2026 é só a eleição presidencial (decisão do dono do projeto): este job NÃO
coleta governadores. Se um ex-governador for candidato a presidente em 2026, sua trajetória
aparece no perfil dele via os dados do TSE coletados pelo job de candidaturas — isso não é
responsabilidade deste job.

Fonte: fatos históricos estáveis (galeria oficial da Presidência/Planalto; atas do Senado
para o impeachment de 2016), curados em `etl/dados/periodos_governo.json` — não há API para
isso, então os dados são carregados do JSON, validados (datas coerentes, sem sobreposição) e
gravados em `periodo_governo`.

`pessoa_id` é preenchido por melhor esforço (nome civil normalizado, via a função `normaliza`
do banco) contra a tabela `pessoa`, povoada em paralelo pelo job de candidaturas do TSE 2026 —
só vincula quando o nome bate com exatamente uma pessoa (evita vínculo errado por homônimos).
Rode este job de novo depois que `pessoa` estiver povoada para atualizar os vínculos.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import psycopg

from ..common.db import conectar, upsert
from ..common.job import executar

DADOS = Path(__file__).resolve().parents[2] / "dados" / "periodos_governo.json"


def carregar_dados() -> dict[str, Any]:
    return json.loads(DADOS.read_text(encoding="utf-8"))


def linhas_presidentes(presidentes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    saida = []
    for item in presidentes:
        saida.append(
            {
                "cargo": "presidente",
                "uf": "BR",
                "nome": item["nome"],
                "nome_civil": item.get("nome_civil"),
                "inicio": dt.date.fromisoformat(item["inicio"]),
                "fim": dt.date.fromisoformat(item["fim"]) if item.get("fim") else None,
                "fonte_url": item["fonte_url"],
            }
        )
    return saida


def resolver_pessoa_id(conn: psycopg.Connection, nome_civil: str | None, nome_urna: str) -> str | None:
    """Casa por nome civil normalizado (unaccent/lower) contra `pessoa`. Tenta primeiro o nome
    civil quando informado (ex.: "Luiz Inácio Lula da Silva"); senão tenta o nome de urna sem
    a marcação de status ("(interino)" etc.). Só vincula quando o nome bate com exatamente uma
    pessoa — evita vínculo errado por homônimos."""
    for candidato in (nome_civil, nome_urna.split(" (")[0]):
        if not candidato:
            continue
        linhas = conn.execute(
            "select id from pessoa where normaliza(nome_civil) = normaliza(%s)", (candidato,)
        ).fetchall()
        if len(linhas) == 1:
            return str(linhas[0]["id"])
    return None


def validar(presidentes: list[dict[str, Any]]) -> None:
    """Portão de qualidade: datas coerentes e sem sobreposição de mandatos."""
    linhas = linhas_presidentes(presidentes)
    for linha in linhas:
        if linha["fim"] is not None and linha["fim"] <= linha["inicio"]:
            raise ValueError(f"Período inválido (fim <= início): {linha}")
    ordenados = sorted(linhas, key=lambda p: p["inicio"])
    for anterior, atual in zip(ordenados, ordenados[1:], strict=False):
        fim_anterior = anterior["fim"] or dt.date.max
        if atual["inicio"] < fim_anterior:
            raise ValueError(f"Sobreposição de mandatos: {anterior} x {atual}")


def main(argv: list[str]) -> None:
    dados = carregar_dados()
    validar(dados["presidentes"])

    with executar("periodos_governo") as ex:
        presidentes = linhas_presidentes(dados["presidentes"])
        ex.exige(len(presidentes) > 0, "Nenhum período de presidente carregado")

        with conectar() as conn:
            vinculados = 0
            for linha in presidentes:
                nome_civil = linha.pop("nome_civil", None)
                pessoa_id = resolver_pessoa_id(conn, nome_civil, linha["nome"])
                linha["pessoa_id"] = pessoa_id
                if pessoa_id:
                    vinculados += 1
            n = upsert(
                conn,
                "periodo_governo",
                presidentes,
                chave=["cargo", "uf", "inicio"],
                atualizar=["nome", "fim", "fonte_url", "pessoa_id"],
            )
            conn.commit()
        ex.conta(n)
        ex.detalhes["presidentes"] = len(presidentes)
        ex.detalhes["pessoa_id_vinculado"] = vinculados


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
