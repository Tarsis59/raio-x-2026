"""Execução de jobs com registro em etl_execucao e portão de qualidade."""

from __future__ import annotations

import logging
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from .db import Jsonb, conectar

log = logging.getLogger("raiox")


class FalhaQualidade(Exception):
    """Dados não passaram no portão de qualidade — nada deve ser publicado."""


@dataclass
class Execucao:
    job: str
    id: int | None = None
    registros: int = 0
    detalhes: dict[str, Any] = field(default_factory=dict)

    def conta(self, n: int = 1) -> None:
        self.registros += n

    def exige(self, condicao: bool, mensagem: str) -> None:
        if not condicao:
            raise FalhaQualidade(mensagem)


@contextmanager
def executar(job: str) -> Iterator[Execucao]:
    ex = Execucao(job=job)
    inicio = time.monotonic()
    with conectar() as conn:
        ex.id = conn.execute("insert into etl_execucao (job) values (%s) returning id", (job,)).fetchone()["id"]
        conn.commit()
    log.info("▶ %s (execução %s)", job, ex.id)
    status, mensagem = "sucesso", None
    try:
        yield ex
    except FalhaQualidade as e:
        status, mensagem = "bloqueado_qualidade", str(e)
        log.error("⛔ %s bloqueado pelo portão de qualidade: %s", job, e)
        raise
    except Exception as e:  # noqa: BLE001
        status, mensagem = "falha", f"{e}\n{traceback.format_exc()[-4000:]}"
        log.exception("✖ %s falhou", job)
        raise
    finally:
        ex.detalhes["duracao_s"] = round(time.monotonic() - inicio, 1)
        with conectar() as conn:
            conn.execute(
                "update etl_execucao set fim = now(), status = %s, registros = %s, mensagem = %s, detalhes = %s "
                "where id = %s",
                (status, ex.registros, mensagem, Jsonb(ex.detalhes), ex.id),
            )
            conn.commit()
        if status == "sucesso":
            log.info("✔ %s: %s registros em %ss", job, ex.registros, ex.detalhes["duracao_s"])
