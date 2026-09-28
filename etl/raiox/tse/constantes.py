"""Constantes do domínio eleitoral usadas pela coleta do TSE."""

from __future__ import annotations

UFS: tuple[str, ...] = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)

# Código do cargo -> nome (conforme docs/fontes/TSE.md)
CARGOS: dict[int, str] = {
    1: "Presidente",
    3: "Governador",
    5: "Senador",
    6: "Deputado Federal",
    7: "Deputado Estadual",
    8: "Deputado Distrital",
}

CARGOS_MAJORITARIOS = {1, 3, 5}


def ufs_do_cargo(cargo: int) -> tuple[str, ...]:
    """Lista de UFs em que um cargo é disputado.

    Regras (docs/fontes/TSE.md e enunciado do job):
      * 1 (Presidente): não usa UF — usa "BR".
      * 3 (Governador), 5 (Senador), 6 (Dep. Federal): todas as 27 UFs (26 estados + DF).
      * 7 (Dep. Estadual): todas menos o DF (o DF tem Câmara Legislativa, não Assembleia).
      * 8 (Dep. Distrital): só o DF.
    """
    if cargo == 1:
        return ("BR",)
    if cargo == 7:
        return tuple(uf for uf in UFS if uf != "DF")
    if cargo == 8:
        return ("DF",)
    if cargo in (3, 5, 6):
        return UFS
    raise ValueError(f"cargo desconhecido: {cargo}")


def pares_cargo_uf(cargos: tuple[int, ...] = tuple(CARGOS)) -> list[tuple[int, str]]:
    return [(cargo, uf) for cargo in cargos for uf in ufs_do_cargo(cargo)]
