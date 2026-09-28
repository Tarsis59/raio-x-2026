"""Funções puras (sem I/O) que transformam o JSON do TSE em linhas de tabela.

Nenhuma função aqui toca rede ou banco — o objetivo é poder testar com fixtures reais
(anonimizadas) sem precisar do Chromium nem do Postgres.
"""

from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any

# Campos que NUNCA podem ir para evidência, cache ou qualquer outro lugar persistido.
CAMPOS_SENSIVEIS = {"cpf", "tituloEleitor"}

# Campos adicionais removidos da evidência de prestação de contas (tse_contas): o ranking de
# doadores/fornecedores do TSE traz CPF/CNPJ da pessoa física/jurídica. É dado público por lei
# (prestação de contas eleitoral), mas por princípio de privacidade por design do projeto o
# identificador não é necessário em lugar nenhum do nosso banco — só nome, tipo e valor
# (tabela `maior_doador`) — então também não vai para a evidência arquivada.
CAMPOS_SENSIVEIS_CONTAS = CAMPOS_SENSIVEIS | {"cpfCnpj"}


def remover_sensiveis(detalhe: dict[str, Any], extra: set[str] | None = None) -> dict[str, Any]:
    """Retorna uma cópia profunda do JSON sem `cpf`/`tituloEleitor` (+ `extra`), em qualquer nível.

    O contrato dos endpoints do TSE só documenta esses campos num nível específico, mas a
    remoção é recursiva por segurança (defesa em profundidade: se um campo desses aparecer
    aninhado ele também é removido).
    """
    proibidos = CAMPOS_SENSIVEIS | (extra or set())

    def _limpa(valor: Any) -> Any:
        if isinstance(valor, dict):
            return {k: _limpa(v) for k, v in valor.items() if k not in proibidos}
        if isinstance(valor, list):
            return [_limpa(v) for v in valor]
        return valor

    return _limpa(copy.deepcopy(detalhe))


def parse_data(valor: str | None) -> date | None:
    """'YYYY-MM-DD' -> date. None/vazio -> None."""
    if not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


def parse_data_hora(valor: str | None) -> datetime | None:
    """'YYYY-MM-DD HH:MM' (horário de Brasília, como o TSE publica) -> datetime naive."""
    if not valor:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor, fmt)
        except ValueError:
            continue
    return None


def parse_epoch_ms(valor: int | float | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromtimestamp(valor / 1000)
    except (ValueError, OSError, OverflowError):
        return None


def _num(valor: Any) -> float | None:
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _int(valor: Any) -> int | None:
    if valor is None or valor == "":
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def linha_pessoa_titular(detalhe: dict[str, Any]) -> dict[str, Any]:
    """Campos de `pessoa` extraídos do detalhe do candidato titular.

    Inclui `cpf` em claro no dicionário de retorno — quem chama esta função usa
    `raiox.common.identidade.cpf_hmac` para gerar o hash e DESCARTA o valor original
    antes de persistir (nunca gravar `cpf` em pessoa/evidência/cache).
    """
    foto_publicavel = bool(detalhe.get("fotoUrlPublicavel"))
    return {
        "nome_urna": (detalhe.get("nomeUrna") or "").strip(),
        "nome_civil": (detalhe.get("nomeCompleto") or detalhe.get("nomeUrna") or "").strip(),
        "data_nascimento": parse_data(detalhe.get("dataDeNascimento")),
        "uf_nascimento": detalhe.get("sgUfNascimento"),
        "municipio_nascimento": detalhe.get("nomeMunicipioNascimento"),
        "genero": detalhe.get("descricaoSexo"),
        "cor_raca": detalhe.get("descricaoCorRaca"),
        "grau_instrucao": detalhe.get("grauInstrucao"),
        "ocupacao": detalhe.get("ocupacao"),
        "cpf": detalhe.get("cpf"),
        "foto_url": detalhe.get("fotoUrl") if foto_publicavel else None,
    }


def linha_pessoa_vice(vice: dict[str, Any]) -> dict[str, Any]:
    """Campos de `pessoa` para um vice/suplente — o bloco `vices[]` não traz CPF nem
    data de nascimento, então a identidade só pode ser resolvida por nome (ver
    `raiox.jobs.tse_candidaturas.resolver_pessoa`)."""
    foto_publicavel = bool(vice.get("urlFotoPublicavel"))
    return {
        "nome_urna": (vice.get("nm_URNA") or "").strip(),
        "nome_civil": (vice.get("nm_CANDIDATO") or vice.get("nm_URNA") or "").strip(),
        "data_nascimento": None,
        "uf_nascimento": None,
        "municipio_nascimento": None,
        "genero": None,
        "cor_raca": None,
        "grau_instrucao": None,
        "ocupacao": None,
        "cpf": None,
        "foto_url": vice.get("urlFoto") if foto_publicavel else None,
    }


def linha_candidatura_titular(
    detalhe: dict[str, Any], *, eleicao_id: int, ano: int, uf: str, municipio: str | None = None
) -> dict[str, Any]:
    cargo = detalhe.get("cargo") or {}
    partido = detalhe.get("partido") or {}
    sites = [s for s in (detalhe.get("sites") or []) if s]
    return {
        "id": _int(detalhe["id"]),
        "eleicao_id": eleicao_id,
        "ano": ano,
        "cargo_codigo": _int(cargo.get("codigo")),
        "cargo_nome": cargo.get("nome") or "",
        "uf": uf,
        "municipio": municipio,
        "numero": _int(detalhe.get("numero")),
        "partido_numero": _int(partido.get("numero")),
        "partido_sigla": partido.get("sigla"),
        "partido_nome": partido.get("nome"),
        "coligacao_nome": detalhe.get("nomeColigacao"),
        "coligacao_composicao": detalhe.get("composicaoColigacao"),
        "titular": True,
        "candidatura_titular_id": None,
        "situacao_registro": detalhe.get("descricaoSituacao"),
        "situacao_totalizacao": detalhe.get("descricaoTotalizacao"),
        "reeleicao": detalhe.get("st_REELEICAO"),
        "limite_gasto_1t": _num(detalhe.get("gastoCampanha1T")),
        "limite_gasto_2t": _num(detalhe.get("gastoCampanha2T")),
        "total_bens": _num(detalhe.get("totalDeBens")),
        "processo_registro": detalhe.get("numeroProcesso"),
        "processo_drap": detalhe.get("numeroProcessoDrap"),
        "processo_contas": detalhe.get("numeroProcessoPrestContas"),
        "sites": sites,
        "atualizado_tse_em": parse_data_hora(detalhe.get("dataUltimaAtualizacao")),
    }


# ds_CARGO do vice costuma vir como "Vice-presidente", "Vice-governador", "1º Suplente",
# "2º Suplente" (senador). Não há um código numérico de cargo próprio no payload do TSE
# para essas linhas — por decisão de modelagem, herdam o cargo_codigo do titular (mesma
# disputa/eleição), e o texto distintivo ("Vice-...", "Suplente") fica em cargo_nome.
def linhas_candidatura_vices(
    detalhe: dict[str, Any], *, eleicao_id: int, ano: int, uf_padrao: str
) -> list[dict[str, Any]]:
    cargo_codigo_titular = _int((detalhe.get("cargo") or {}).get("codigo"))
    titular_id = _int(detalhe["id"])
    linhas = []
    for vice in detalhe.get("vices") or []:
        sq = vice.get("sq_CANDIDATO")
        if sq is None:
            continue
        atualizado = parse_epoch_ms(vice.get("dt_ULTIMA_ATUALIZACAO")) or parse_data(
            vice.get("DT_ULTIMA_ATUALIZACAO")
        )
        linhas.append(
            {
                "id": _int(sq),
                "eleicao_id": eleicao_id,
                "ano": ano,
                "cargo_codigo": cargo_codigo_titular,
                "cargo_nome": vice.get("ds_CARGO") or "",
                "uf": vice.get("sg_UE") or uf_padrao,
                "municipio": None,
                "numero": _int(vice.get("nr_CANDIDATO")),
                "partido_numero": None,
                "partido_sigla": vice.get("sg_PARTIDO"),
                "partido_nome": vice.get("nm_PARTIDO"),
                "coligacao_nome": vice.get("nomeColigacao"),
                "coligacao_composicao": vice.get("composicaoColigacao"),
                "titular": False,
                "candidatura_titular_id": titular_id,
                "situacao_registro": vice.get("stRegistro"),
                "situacao_totalizacao": vice.get("descricaoTotalizacao"),
                "reeleicao": None,
                "limite_gasto_1t": None,
                "limite_gasto_2t": None,
                "total_bens": None,
                "processo_registro": None,
                "processo_drap": None,
                "processo_contas": None,
                "sites": [],
                "atualizado_tse_em": atualizado,
                "_vice_pessoa": linha_pessoa_vice(vice),
            }
        )
    return linhas


def linhas_bens(candidatura_id: int, detalhe: dict[str, Any]) -> list[dict[str, Any]]:
    linhas = []
    for bem in detalhe.get("bens") or []:
        ordem = _int(bem.get("ordem"))
        valor = _num(bem.get("valor"))
        if ordem is None or valor is None:
            continue
        linhas.append(
            {
                "candidatura_id": candidatura_id,
                "ordem": ordem,
                "tipo": bem.get("descricaoDeTipoDeBem"),
                "descricao": bem.get("descricao"),
                "valor": valor,
                "atualizado_tse": parse_data(bem.get("dataUltimaAtualizacao")),
            }
        )
    return linhas


def linhas_arquivos(candidatura_id: int, detalhe: dict[str, Any]) -> list[dict[str, Any]]:
    linhas = []
    for arq in detalhe.get("arquivos") or []:
        id_arquivo = _int(arq.get("idArquivo"))
        cod_tipo = _int(arq.get("codTipo"))
        if id_arquivo is None or cod_tipo is None:
            continue
        anon = arq.get("anonimizado")
        linhas.append(
            {
                "id": id_arquivo,
                "candidatura_id": candidatura_id,
                "cod_tipo": cod_tipo,
                "nome": arq.get("nome"),
                "anonimizado": None if anon is None else anon == "S",
            }
        )
    return linhas


def parse_data_br(valor: str | None) -> date | None:
    """'DD/MM/AAAA' (formato usado pela prestação de contas) -> date."""
    if not valor:
        return None
    try:
        return datetime.strptime(valor[:10], "%d/%m/%Y").date()
    except ValueError:
        return None


def _tipo_doador(cpf_cnpj: str | None, nome: str | None) -> str:
    """Heurística: 11 dígitos = pessoa física, 14 = pessoa jurídica; nomes de órgão
    partidário (direção/diretório/comitê) viram 'partido' mesmo vindo de um CNPJ."""
    nome_up = (nome or "").upper()
    if any(p in nome_up for p in ("DIREÇÃO", "DIRECAO", "DIRETÓRIO", "DIRETORIO", "COMITÊ", "COMITE", "PARTIDO")):
        return "partido"
    digitos = "".join(c for c in (cpf_cnpj or "") if c.isdigit())
    if len(digitos) == 11:
        return "PF"
    if len(digitos) == 14:
        return "PJ"
    return "outro"


def linha_contas_campanha(
    candidatura_id: int, contas: dict[str, Any], bruto_sanitizado: dict[str, Any]
) -> dict[str, Any]:
    consolidados = contas.get("dadosConsolidados") or {}
    despesas = contas.get("despesas") or {}
    return {
        "candidatura_id": candidatura_id,
        "cnpj_campanha": contas.get("cnpj"),
        "total_recebido": _num(consolidados.get("totalRecebido")),
        "receita_pf": _num(consolidados.get("totalReceitaPF")),
        "receita_pj": _num(consolidados.get("totalReceitaPJ")),
        "receita_partidos": _num(consolidados.get("totalPartidos")),
        "receita_propria": _num(consolidados.get("totalProprios")),
        "receita_fundo_especial": _num(consolidados.get("graphVrReceitaFinFefc")),
        "receita_fundo_partidario": None,  # TSE não separa no consolidado — ver `bruto`
        "receita_internet": _num(consolidados.get("totalInternet")),
        "receita_outros_candidatos": _num(consolidados.get("totalReceitaOutCand")),
        "receita_estimada": _num(consolidados.get("totalEstimados")),
        "total_despesas": _num(despesas.get("totalDespesasContratadas")),
        "atualizado_tse_em": parse_data_br(contas.get("dataUltimaAtualizacaoContas")),
        "bruto": bruto_sanitizado,
    }


def linhas_maior_doador(candidatura_id: int, contas: dict[str, Any], limite: int = 10) -> list[dict[str, Any]]:
    doadores = contas.get("rankingDoadores") or []
    ordenados = sorted(doadores, key=lambda d: _num(d.get("valor")) or 0.0, reverse=True)[:limite]
    linhas = []
    for i, d in enumerate(ordenados, start=1):
        valor = _num(d.get("valor"))
        if valor is None:
            continue
        linhas.append(
            {
                "candidatura_id": candidatura_id,
                "posicao": i,
                "nome": d.get("nome") or "(não identificado)",
                "tipo": _tipo_doador(d.get("cpfCnpj"), d.get("nome")),
                "valor": valor,
            }
        )
    return linhas


def variacao_patrimonio_suspeita(anterior: float | None, atual: float | None, fator: float = 1000.0) -> bool:
    """True se o patrimônio total variou mais que `fator`x entre coletas (alerta, não bloqueia)."""
    if not anterior or not atual or anterior <= 0 or atual <= 0:
        return False
    razao = atual / anterior if atual > anterior else anterior / atual
    return razao > fator
