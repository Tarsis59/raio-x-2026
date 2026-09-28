"""Resolução de identidade de pessoas e geração de slug (com acesso ao banco).

Fica separado de `mapeamento.py` (que é puro) porque precisa de uma conexão para
verificar duplicidade. A lógica de resolução é testada indiretamente pelos testes de
`tse_candidaturas` com um banco de testes; aqui documentamos as regras:

1. CPF (via HMAC) é a chave forte — quando presente, sempre decide.
2. Sem CPF (ou CPF inválido): nome civil + data de nascimento, quando ambos batem
   com exatamente uma pessoa existente.
3. Vices/suplentes não trazem CPF nem data de nascimento no bloco `vices[]` do
   detalhe do titular — nesse caso o único fallback possível é nome civil exato;
   se houver mais de uma pessoa com esse nome, cria uma pessoa nova (evita fundir
   identidades de homônimos) e registra a ambiguidade em `ex.detalhes`.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from raiox.common.identidade import cpf_hmac, slugify

from .mapeamento import parse_data


@dataclass
class ResultadoResolucao:
    pessoa_id: str
    criada: bool
    metodo: str  # cpf | nome_dob | nome_apenas | novo | nome_dob_ambiguo | nome_apenas_ambiguo


def resolver_pessoa(conn: psycopg.Connection, dados: dict) -> ResultadoResolucao:
    """`dados` é o dict de `linha_pessoa_titular`/`linha_pessoa_vice` (contém `cpf` em claro,
    que é usado só para o HMAC e nunca persistido)."""
    hmac_ = cpf_hmac(dados.get("cpf"))
    if hmac_:
        row = conn.execute("select id from pessoa where cpf_hmac = %s", (hmac_,)).fetchone()
        if row:
            return ResultadoResolucao(str(row["id"]), False, "cpf")

    nome_civil = dados["nome_civil"]
    data_nasc = dados.get("data_nascimento")
    if data_nasc:
        rows = conn.execute(
            "select id from pessoa where nome_civil = %s and data_nascimento = %s",
            (nome_civil, data_nasc),
        ).fetchall()
        if len(rows) == 1:
            return ResultadoResolucao(str(rows[0]["id"]), False, "nome_dob")
        if len(rows) > 1:
            return ResultadoResolucao(_criar(conn, dados, hmac_), True, "nome_dob_ambiguo")
    else:
        rows = conn.execute(
            "select id from pessoa where nome_civil = %s and data_nascimento is null",
            (nome_civil,),
        ).fetchall()
        if len(rows) == 1:
            return ResultadoResolucao(str(rows[0]["id"]), False, "nome_apenas")
        if len(rows) > 1:
            return ResultadoResolucao(_criar(conn, dados, hmac_), True, "nome_apenas_ambiguo")

    return ResultadoResolucao(_criar(conn, dados, hmac_), True, "novo")


def _criar(conn: psycopg.Connection, dados: dict, hmac_: str | None) -> str:
    slug = gerar_slug_unico(conn, dados["nome_urna"] or dados["nome_civil"], dados.get("uf_nascimento"))
    row = conn.execute(
        "insert into pessoa (slug, nome_urna, nome_civil, data_nascimento, uf_nascimento, "
        "municipio_nascimento, genero, cor_raca, grau_instrucao, ocupacao, cpf_hmac, foto_url) "
        "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id",
        (
            slug,
            dados["nome_urna"],
            dados["nome_civil"],
            dados.get("data_nascimento"),
            dados.get("uf_nascimento"),
            dados.get("municipio_nascimento"),
            dados.get("genero"),
            dados.get("cor_raca"),
            dados.get("grau_instrucao"),
            dados.get("ocupacao"),
            hmac_,
            dados.get("foto_url"),
        ),
    ).fetchone()
    return str(row["id"])


def gerar_slug_unico(conn: psycopg.Connection, nome_urna: str, uf: str | None) -> str:
    base = slugify(nome_urna) or "candidato"

    def livre(candidato: str) -> bool:
        return conn.execute("select 1 from pessoa where slug = %s", (candidato,)).fetchone() is None

    if livre(base):
        return base
    if uf:
        com_uf = f"{base}-{uf.lower()}"
        if livre(com_uf):
            return com_uf
    n = 2
    while True:
        candidato = f"{base}-{n}"
        if livre(candidato):
            return candidato
        n += 1


def atualizar_pessoa_existente(conn: psycopg.Connection, pessoa_id: str, dados: dict) -> None:
    """Atualiza campos que podem mudar entre coletas (foto, ocupação, grau de instrução…),
    mas NUNCA o slug (estável) nem o nome (guardado como o TSE publicou na 1ª coleta é aceitável
    trocar se o TSE corrigiu grafia — por isso nome_urna/nome_civil também são atualizados)."""
    conn.execute(
        "update pessoa set nome_urna = %s, nome_civil = %s, "
        "data_nascimento = coalesce(%s, data_nascimento), "
        "uf_nascimento = coalesce(%s, uf_nascimento), "
        "municipio_nascimento = coalesce(%s, municipio_nascimento), "
        "genero = coalesce(%s, genero), cor_raca = coalesce(%s, cor_raca), "
        "grau_instrucao = coalesce(%s, grau_instrucao), ocupacao = coalesce(%s, ocupacao), "
        "foto_url = coalesce(%s, foto_url) "
        "where id = %s",
        (
            dados["nome_urna"] or None,
            dados["nome_civil"] or None,
            dados.get("data_nascimento"),
            dados.get("uf_nascimento"),
            dados.get("municipio_nascimento"),
            dados.get("genero"),
            dados.get("cor_raca"),
            dados.get("grau_instrucao"),
            dados.get("ocupacao"),
            dados.get("foto_url"),
            pessoa_id,
        ),
    )


__all__ = ["resolver_pessoa", "gerar_slug_unico", "atualizar_pessoa_existente", "ResultadoResolucao", "parse_data"]
