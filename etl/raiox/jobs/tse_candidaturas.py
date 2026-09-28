"""Job `tse_candidaturas`: coleta completa de candidaturas 2026 no DivulgaCandContas (TSE).

Uso:
    python -m raiox tse_candidaturas
    python -m raiox tse_candidaturas --cargos 1,3 --ufs SP,RJ --limite 50 --concorrencia 8

Fluxo:
  1. Lista candidatos por (cargo, UF) — endpoint `listar` (rápido, 1 chamada por par).
  2. Decide, por candidato, se pode pular o processamento pesado (incremental: já temos
     o registro e `dataUltimaAtualizacao` não mudou) — nesse caso só atualiza
     situação/totalização a partir da própria listagem.
  3. Busca o detalhe (endpoint `buscar`) dos que faltam, com concorrência controlada
     (gerida pelo pool de abas do `ClienteTSE`).
  4. Grava pessoa, eleição, candidatura (titular + vices/suplentes), bens (substitui o
     conjunto a cada coleta), arquivo_tse (metadados) e a evidência do JSON do detalhe
     — sempre SEM `cpf`/`tituloEleitor`.

Nada de rede roda dentro de uma transação de banco: primeiro busca tudo (fase async),
depois grava tudo (fase síncrona, em lotes com commit periódico).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import orjson
import psycopg

from raiox.common import evidencia
from raiox.common.config import ANO_ELEICAO, ELEICAO_2026
from raiox.common.db import conectar, upsert
from raiox.common.job import executar
from raiox.common.tse import API, ClienteTSE, ErroTSE
from raiox.tse import mapeamento as m
from raiox.tse import pessoa as p
from raiox.tse.constantes import CARGOS, pares_cargo_uf, ufs_do_cargo

log = logging.getLogger("raiox.tse_candidaturas")

LOTE_COMMIT = 100  # candidatos titulares por transação


def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="tse_candidaturas")
    ap.add_argument("--cargos", type=str, default=None, help="ex.: 1,3,5")
    ap.add_argument("--ufs", type=str, default=None, help="ex.: SP,RJ")
    ap.add_argument("--limite", type=int, default=None, help="limita o nº de candidatos (testes)")
    ap.add_argument("--concorrencia", type=int, default=8)
    return ap.parse_args(argv)


def _garante_eleicao(conn: psycopg.Connection) -> None:
    conn.execute(
        "insert into eleicao (id, ano, nome, data, abrangencia) values (%s,%s,%s,%s,%s) "
        "on conflict (id) do nothing",
        (ELEICAO_2026, ANO_ELEICAO, "Eleições Gerais 2026", "2026-10-04", "F"),
    )


async def _listar(tse: ClienteTSE, cargo: int, uf: str) -> list[dict[str, Any]]:
    caminho = f"/candidatura/listar/{ANO_ELEICAO}/{uf}/{ELEICAO_2026}/{cargo}/candidatos"
    try:
        dados = await tse.json(caminho)
    except ErroTSE as e:
        log.error("Falha ao listar cargo=%s uf=%s: %s", cargo, uf, e)
        return []
    if not dados:
        return []
    candidatos = dados.get("candidatos") or []
    for c in candidatos:
        c["_cargo_codigo"] = cargo
        c["_uf"] = uf
    return candidatos


async def _buscar_detalhe(tse: ClienteTSE, cargo: int, uf: str, id_candidato: int) -> dict[str, Any] | None:
    caminho = f"/candidatura/buscar/{ANO_ELEICAO}/{uf}/{ELEICAO_2026}/candidato/{id_candidato}"
    return await tse.json(caminho)


async def _fase_async(
    cargos: list[int], ufs_filtro: set[str] | None, concorrencia: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    contagem_por_par: dict[str, int] = {}
    async with ClienteTSE(concorrencia=concorrencia) as tse:
        pares = pares_cargo_uf(tuple(cargos))
        if ufs_filtro is not None:
            pares = [(c, uf) for c, uf in pares if uf in ufs_filtro]
        log.info("Listando %d pares (cargo, UF)...", len(pares))
        listas = await asyncio.gather(*(_listar(tse, cargo, uf) for cargo, uf in pares))
        stubs: list[dict[str, Any]] = []
        for (cargo, uf), lista in zip(pares, listas, strict=True):
            contagem_por_par[f"{cargo}:{uf}"] = len(lista)
            stubs.extend(lista)
        log.info("Total de candidatos titulares na listagem: %d", len(stubs))
        return stubs, contagem_por_par


async def _fase_detalhes(
    stubs_para_buscar: list[dict[str, Any]], concorrencia: int
) -> list[tuple[dict[str, Any], dict[str, Any] | None, Exception | None]]:
    resultados: list[tuple[dict[str, Any], dict[str, Any] | None, Exception | None]] = []
    async with ClienteTSE(concorrencia=concorrencia) as tse:
        TAM_LOTE = 300
        for i in range(0, len(stubs_para_buscar), TAM_LOTE):
            lote = stubs_para_buscar[i : i + TAM_LOTE]

            async def um(stub: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, Exception | None]:
                try:
                    det = await _buscar_detalhe(tse, stub["_cargo_codigo"], stub["_uf"], stub["id"])
                    return stub, det, None
                except Exception as e:  # noqa: BLE001
                    return stub, None, e

            resultados.extend(await asyncio.gather(*(um(s) for s in lote)))
            log.info("Detalhes buscados: %d/%d", len(resultados), len(stubs_para_buscar))
    return resultados


def _grava_candidato(
    conn: psycopg.Connection,
    *,
    cargo: int,
    uf: str,
    detalhe: dict[str, Any],
    existentes: dict[int, dict[str, Any]],
    alertas_patrimonio: list[str],
) -> None:
    url = f"{API}/candidatura/buscar/{ANO_ELEICAO}/{uf}/{ELEICAO_2026}/candidato/{detalhe['id']}"
    sanitizado = m.remover_sensiveis(detalhe)
    conteudo = orjson.dumps(sanitizado, option=orjson.OPT_SORT_KEYS)
    ev_id = evidencia.registrar(
        conn, tipo_fonte="tse", url_original=url, conteudo=bytes(conteudo), mime="application/json"
    )

    dados_pessoa = m.linha_pessoa_titular(detalhe)
    res = p.resolver_pessoa(conn, dados_pessoa)
    if not res.criada:
        p.atualizar_pessoa_existente(conn, res.pessoa_id, dados_pessoa)

    cand_id = int(detalhe["id"])
    linha_cand = m.linha_candidatura_titular(detalhe, eleicao_id=ELEICAO_2026, ano=ANO_ELEICAO, uf=uf)
    linha_cand["pessoa_id"] = res.pessoa_id
    linha_cand["evidencia_id"] = ev_id
    linha_cand["coletado_em"] = datetime.now(UTC)

    anterior = existentes.get(cand_id)
    if anterior and m.variacao_patrimonio_suspeita(anterior.get("total_bens"), linha_cand["total_bens"]):
        alertas_patrimonio.append(
            f"candidatura {cand_id} ({detalhe.get('nomeUrna')}): "
            f"{anterior.get('total_bens')} -> {linha_cand['total_bens']}"
        )

    upsert(conn, "candidatura", [linha_cand], chave=["id"])

    conn.execute("delete from bem where candidatura_id = %s", (cand_id,))
    bens = m.linhas_bens(cand_id, detalhe)
    if bens:
        with conn.cursor() as cur:
            cur.executemany(
                "insert into bem (candidatura_id, ordem, tipo, descricao, valor, atualizado_tse) "
                "values (%(candidatura_id)s,%(ordem)s,%(tipo)s,%(descricao)s,%(valor)s,%(atualizado_tse)s)",
                bens,
            )

    arquivos = m.linhas_arquivos(cand_id, detalhe)
    if arquivos:
        upsert(
            conn, "arquivo_tse", arquivos, chave=["id"],
            atualizar=["candidatura_id", "cod_tipo", "nome", "anonimizado"],
        )

    for linha_vice in m.linhas_candidatura_vices(detalhe, eleicao_id=ELEICAO_2026, ano=ANO_ELEICAO, uf_padrao=uf):
        dados_vice_pessoa = linha_vice.pop("_vice_pessoa")
        res_vice = p.resolver_pessoa(conn, dados_vice_pessoa)
        if not res_vice.criada:
            p.atualizar_pessoa_existente(conn, res_vice.pessoa_id, dados_vice_pessoa)
        linha_vice["pessoa_id"] = res_vice.pessoa_id
        linha_vice["evidencia_id"] = ev_id
        linha_vice["coletado_em"] = datetime.now(UTC)
        upsert(conn, "candidatura", [linha_vice], chave=["id"])


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    cargos = [int(x) for x in args.cargos.split(",")] if args.cargos else list(CARGOS)
    ufs_filtro = {x.strip().upper() for x in args.ufs.split(",")} if args.ufs else None
    execucao_completa = not (args.cargos or args.ufs or args.limite)

    with executar("tse_candidaturas") as ex:
        stubs, contagem_por_par = asyncio.run(_fase_async(cargos, ufs_filtro, args.concorrencia))
        ex.detalhes["contagem_listagem"] = contagem_por_par
        ex.detalhes["total_listagem"] = len(stubs)

        if execucao_completa:
            ex.exige(len(stubs) >= 19000, f"total de candidaturas na listagem abaixo do esperado: {len(stubs)}")
            for cargo_dep in (6, 7):
                for uf in ufs_do_cargo(cargo_dep):
                    n = contagem_por_par.get(f"{cargo_dep}:{uf}", 0)
                    ex.exige(n > 0, f"UF {uf} sem candidatos a {CARGOS[cargo_dep]} (cargo {cargo_dep})")
            n_pres_listagem = contagem_por_par.get("1:BR", 0)
            ex.detalhes["pres_listagem"] = n_pres_listagem

        if args.limite:
            stubs = stubs[: args.limite]

        with conectar() as conn:
            _garante_eleicao(conn)
            conn.commit()
            existentes_rows = conn.execute(
                "select id, atualizado_tse_em, total_bens from candidatura where eleicao_id = %s", (ELEICAO_2026,)
            ).fetchall()
            existentes = {r["id"]: r for r in existentes_rows}

        para_buscar: list[dict[str, Any]] = []
        pulados = 0
        for stub in stubs:
            cand_id = stub["id"]
            existente = existentes.get(cand_id)
            atualizado_listagem = m.parse_data_hora(stub.get("dataUltimaAtualizacao"))
            if existente and atualizado_listagem and existente["atualizado_tse_em"] == atualizado_listagem:
                pulados += 1
                continue
            para_buscar.append(stub)
        ex.detalhes["pulados_incremental"] = pulados
        log.info("Candidatos a buscar detalhe: %d (pulados por incremental: %d)", len(para_buscar), pulados)
        ids_para_buscar = {s["id"] for s in para_buscar}

        if pulados:
            with conectar() as conn:
                for stub in stubs:
                    if stub["id"] in existentes and stub["id"] not in ids_para_buscar:
                        conn.execute(
                            "update candidatura set situacao_registro = %s, situacao_totalizacao = %s "
                            "where id = %s",
                            (stub.get("descricaoSituacao"), stub.get("descricaoTotalizacao"), stub["id"]),
                        )
                conn.commit()

        resultados = asyncio.run(_fase_detalhes(para_buscar, args.concorrencia)) if para_buscar else []

        erros: list[str] = []
        alertas_patrimonio: list[str] = []
        processados_por_cargo: dict[int, int] = {}
        with conectar() as conn:
            n_no_lote = 0
            for stub, detalhe, erro in resultados:
                if erro is not None or detalhe is None:
                    erros.append(f"{stub.get('_cargo_codigo')}:{stub.get('_uf')}:{stub.get('id')} -> {erro}")
                    continue
                try:
                    _grava_candidato(
                        conn,
                        cargo=stub["_cargo_codigo"],
                        uf=stub["_uf"],
                        detalhe=detalhe,
                        existentes=existentes,
                        alertas_patrimonio=alertas_patrimonio,
                    )
                    cc = stub["_cargo_codigo"]
                    processados_por_cargo[cc] = processados_por_cargo.get(cc, 0) + 1
                    ex.conta(1)
                    n_no_lote += 1
                    if n_no_lote >= LOTE_COMMIT:
                        conn.commit()
                        n_no_lote = 0
                except Exception as e:  # noqa: BLE001
                    conn.rollback()
                    erros.append(f"{stub.get('id')} -> {e}")
            conn.commit()

        ex.detalhes["erros"] = erros[:100]
        ex.detalhes["total_erros"] = len(erros)
        ex.detalhes["alertas_patrimonio"] = alertas_patrimonio[:50]
        ex.detalhes["total_alertas_patrimonio"] = len(alertas_patrimonio)
        ex.detalhes["processados_por_cargo"] = processados_por_cargo

        if execucao_completa:
            n_pres_processado = processados_por_cargo.get(1, 0) + sum(
                1 for s in stubs if s["_cargo_codigo"] == 1 and s["id"] in existentes and s["id"] not in ids_para_buscar
            )
            ex.detalhes["pres_processado_ou_ja_existente"] = n_pres_processado
            ex.exige(
                n_pres_processado == ex.detalhes["pres_listagem"],
                f"contagem de presidenciáveis processados ({n_pres_processado}) difere da listagem "
                f"({ex.detalhes['pres_listagem']})",
            )

        if erros:
            log.warning("%d candidatos falharam ao processar (ver ex.detalhes.erros)", len(erros))


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
