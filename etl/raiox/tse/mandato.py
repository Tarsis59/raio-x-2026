"""Regras de posse e duração de mandato por cargo (usadas por `tse_historico`).

Fontes das regras:
  * Presidente e Governador: posse em 1º de janeiro do ano seguinte à eleição.
    A partir de 2027 (EC 111/2021): Presidente toma posse em 5 de janeiro e
    Governador em 6 de janeiro (mudança feita para separar a posse do Legislativo,
    em 1º/fev, da do Executivo, dando mais tempo de transição).
  * Senador, Deputado Federal, Deputado Estadual, Deputado Distrital: posse em
    1º de fevereiro do ano seguinte (mesma data da instalação do Congresso/
    Assembleias/Câmara Legislativa).
  * Prefeito e Vereador: posse em 1º de janeiro do ano seguinte (regra municipal,
    inalterada pela EC 111/2021).
  * Duração: 4 anos para todos os cargos, EXCETO Senador, cujo mandato é de 8 anos
    (dois períodos legislativos).

`situacao_totalizacao` vira mandato somente quando indica efetivamente eleito:
"Eleito", "Eleito por QP" (quociente partidário), "Eleito por média". "Suplente"
NÃO é mandato (só assume se o titular sair).
"""

from __future__ import annotations

from datetime import date, timedelta

PREFIXOS_ELEITO = ("eleito",)
NAO_ELEITO = {"suplente"}

ESFERA_POR_CARGO = {
    "Presidente": "federal",
    "Senador": "federal",
    "Deputado Federal": "federal",
    "Governador": "estadual",
    "Deputado Estadual": "estadual",
    "Deputado Distrital": "estadual",  # sem enum próprio p/ distrital no schema atual
    "Prefeito": "municipal",
    "Vereador": "municipal",
}

DURACAO_ANOS = {
    "Presidente": 4,
    "Governador": 4,
    "Senador": 8,
    "Deputado Federal": 4,
    "Deputado Estadual": 4,
    "Deputado Distrital": 4,
    "Prefeito": 4,
    "Vereador": 4,
}


def foi_eleito(situacao_totalizacao: str | None) -> bool:
    if not situacao_totalizacao:
        return False
    texto = situacao_totalizacao.strip().lower()
    if texto in NAO_ELEITO:
        return False
    return texto.startswith(PREFIXOS_ELEITO)


def data_posse(cargo_nome: str, ano_eleicao: int) -> date:
    ano_posse = ano_eleicao + 1
    if cargo_nome == "Presidente":
        return date(ano_posse, 1, 5) if ano_posse >= 2027 else date(ano_posse, 1, 1)
    if cargo_nome == "Governador":
        return date(ano_posse, 1, 6) if ano_posse >= 2027 else date(ano_posse, 1, 1)
    if cargo_nome in ("Senador", "Deputado Federal", "Deputado Estadual", "Deputado Distrital"):
        return date(ano_posse, 2, 1)
    if cargo_nome in ("Prefeito", "Vereador"):
        return date(ano_posse, 1, 1)
    raise ValueError(f"cargo sem regra de posse: {cargo_nome}")


def data_fim_mandato(inicio: date, cargo_nome: str) -> date:
    anos = DURACAO_ANOS.get(cargo_nome, 4)
    proxima_posse = date(inicio.year + anos, inicio.month, inicio.day)
    return proxima_posse - timedelta(days=1)


def deriva_mandato(
    *, cargo_nome: str, uf: str | None, municipio: str | None, ano_eleicao: int, situacao_totalizacao: str | None
) -> dict | None:
    """Retorna a linha de `mandato` (sem pessoa_id/candidatura_id/origem/evidencia_id,
    preenchidos pelo chamador) ou None se a candidatura não foi eleita."""
    if not foi_eleito(situacao_totalizacao):
        return None
    if cargo_nome not in ESFERA_POR_CARGO:
        return None
    inicio = data_posse(cargo_nome, ano_eleicao)
    fim = data_fim_mandato(inicio, cargo_nome)
    esfera = ESFERA_POR_CARGO[cargo_nome]
    return {
        "cargo": cargo_nome,
        "esfera": esfera,
        "uf": uf if esfera != "municipal" else uf,
        "municipio": municipio,
        "inicio": inicio,
        "fim": fim,
    }
