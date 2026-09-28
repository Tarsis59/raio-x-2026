"""Acesso ao Postgres (psycopg 3)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import config

__all__ = ["conectar", "upsert", "Jsonb"]


@contextmanager
def conectar() -> Iterator[psycopg.Connection]:
    with psycopg.connect(config().database_url, row_factory=dict_row, autocommit=False) as conn:
        yield conn


def upsert(
    conn: psycopg.Connection,
    tabela: str,
    linhas: Iterable[dict[str, Any]],
    chave: Sequence[str],
    atualizar: Sequence[str] | None = None,
    lote: int = 1000,
) -> int:
    """INSERT ... ON CONFLICT (chave) DO UPDATE, em lotes. Retorna o nº de linhas enviadas.

    `atualizar=None` atualiza todas as colunas que não fazem parte da chave;
    `atualizar=[]` vira DO NOTHING.
    """
    total = 0
    buffer: list[dict[str, Any]] = []
    colunas: list[str] | None = None

    def flush() -> None:
        nonlocal total
        if not buffer:
            return
        assert colunas is not None
        cols = ", ".join(colunas)
        marcadores = ", ".join(f"%({c})s" for c in colunas)
        alvo = [c for c in (atualizar if atualizar is not None else colunas) if c not in chave]
        if alvo:
            sets = ", ".join(f"{c} = excluded.{c}" for c in alvo)
            conflito = f"on conflict ({', '.join(chave)}) do update set {sets}"
        else:
            conflito = f"on conflict ({', '.join(chave)}) do nothing"
        sql = f"insert into {tabela} ({cols}) values ({marcadores}) {conflito}"
        with conn.cursor() as cur:
            cur.executemany(sql, buffer)
        total += len(buffer)
        buffer.clear()

    for linha in linhas:
        if colunas is None:
            colunas = list(linha.keys())
        buffer.append(linha)
        if len(buffer) >= lote:
            flush()
    flush()
    return total
