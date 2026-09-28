"""Job `tse_contas`: prestação de contas consolidada (endpoint `prestador/consulta`) de
todas as candidaturas titulares de 2026 já coletadas por `tse_candidaturas`.

Uso:
    python -m raiox tse_contas
    python -m raiox tse_contas --limite 100 --concorrencia 8

Grava `contas_campanha` (dados consolidados + JSON bruto sanitizado) e, quando o TSE expõe
o ranking (`rankingDoadores`), os maiores doadores em `maior_doador` (sem CPF/CNPJ — ver
`raiox.tse.mapeamento.CAMPOS_SENSIVEIS_CONTAS`). Registra evidência do JSON (sanitizado).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

import orjson
import psycopg

from raiox.common import evidencia
from raiox.common.config import ANO_ELEICAO, ELEICAO_2026
from raiox.common.db import Jsonb, conectar, upsert
from raiox.common.job import executar
from raiox.common.tse import API, ClienteTSE
from raiox.tse import mapeamento as m

log = logging.getLogger("raiox.tse_contas")

LOTE_COMMIT = 100


def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="tse_contas")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--concorrencia", type=int, default=8)
    return ap.parse_args(argv)


def _candidaturas_alvo(conn: psycopg.Connection, limite: int | None) -> list[dict[str, Any]]:
    sql = (
        "select id, uf, cargo_codigo, numero, partido_numero from candidatura "
        "where eleicao_id = %s and titular = true and numero is not null and partido_numero is not null "
        "order by id"
    )
    if limite:
        sql += " limit %s"
        rows = conn.execute(sql, (ELEICAO_2026, limite)).fetchall()
    else:
        rows = conn.execute(sql, (ELEICAO_2026,)).fetchall()
    return rows


def _url_prestador(c: dict[str, Any]) -> str:
    return (
        f"/prestador/consulta/{ELEICAO_2026}/{ANO_ELEICAO}/{c['uf']}/{c['cargo_codigo']}/"
        f"{c['partido_numero']}/{c['numero']}/{c['id']}"
    )


async def _buscar_todas(
    candidaturas: list[dict[str, Any]], concorrencia: int
) -> list[tuple[dict[str, Any], Any, Exception | None]]:
    resultados: list[tuple[dict[str, Any], Any, Exception | None]] = []
    async with ClienteTSE(concorrencia=concorrencia) as tse:
        TAM_LOTE = 300
        for i in range(0, len(candidaturas), TAM_LOTE):
            lote = candidaturas[i : i + TAM_LOTE]

            async def um(c: dict[str, Any]) -> tuple[dict[str, Any], Any, Exception | None]:
                try:
                    dados = await tse.json(_url_prestador(c))
                    return c, dados, None
                except Exception as e:  # noqa: BLE001
                    return c, None, e

            resultados.extend(await asyncio.gather(*(um(c) for c in lote)))
            log.info("Contas buscadas: %d/%d", len(resultados), len(candidaturas))
    return resultados


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    with executar("tse_contas") as ex:
        with conectar() as conn:
            candidaturas = _candidaturas_alvo(conn, args.limite)
        ex.detalhes["candidaturas_alvo"] = len(candidaturas)
        if not candidaturas:
            log.warning("Nenhuma candidatura elegível — rode tse_candidaturas primeiro.")
            return

        resultados = asyncio.run(_buscar_todas(candidaturas, args.concorrencia))

        sem_prestacao = 0
        erros: list[str] = []
        with conectar() as conn:
            n_no_lote = 0
            for c, contas, erro in resultados:
                if erro is not None:
                    erros.append(f"{c['id']} -> {erro}")
                    continue
                if contas is None:
                    sem_prestacao += 1
                    continue
                try:
                    url = f"{API}{_url_prestador(c)}"
                    sanitizado = m.remover_sensiveis(contas, extra={"cpfCnpj"})
                    conteudo = bytes(orjson.dumps(sanitizado, option=orjson.OPT_SORT_KEYS))
                    evidencia.registrar(
                        conn, tipo_fonte="tse", url_original=url, conteudo=conteudo, mime="application/json"
                    )

                    linha = m.linha_contas_campanha(c["id"], contas, sanitizado)
                    linha["bruto"] = Jsonb(linha["bruto"])
                    upsert(conn, "contas_campanha", [linha], chave=["candidatura_id"])

                    conn.execute("delete from maior_doador where candidatura_id = %s", (c["id"],))
                    doadores = m.linhas_maior_doador(c["id"], contas)
                    if doadores:
                        with conn.cursor() as cur:
                            cur.executemany(
                                "insert into maior_doador (candidatura_id, posicao, nome, tipo, valor) "
                                "values (%(candidatura_id)s,%(posicao)s,%(nome)s,%(tipo)s,%(valor)s)",
                                doadores,
                            )
                    ex.conta(1)
                    n_no_lote += 1
                    if n_no_lote >= LOTE_COMMIT:
                        conn.commit()
                        n_no_lote = 0
                except Exception as e:  # noqa: BLE001
                    conn.rollback()
                    erros.append(f"{c['id']} -> {e}")
            conn.commit()

        ex.detalhes["sem_prestacao_ainda"] = sem_prestacao
        ex.detalhes["erros"] = erros[:100]
        ex.detalhes["total_erros"] = len(erros)
        log.info("Contas gravadas: %d | sem prestação: %d | erros: %d", ex.registros, sem_prestacao, len(erros))


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
