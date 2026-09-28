"""Linter de neutralidade dos resumos gerados por IA (PLANO_FINAL.md §1 e §7, passo 4).

Um resumo é reprovado se:
  1. Passar de `LIMITE_CARACTERES` caracteres.
  2. Contiver algum termo da lista de adjetivos valorativos/juízo de valor (`TERMOS_PROIBIDOS`).
  3. Mencionar outro candidato, partido ou coligação (lista fornecida pelo chamador — nomes e
     siglas dos demais candidatos ao mesmo cargo, resolvidos a partir do banco).

A lista de termos é propositalmente ampla e conservadora: é melhor reprovar um resumo neutro
por engano (o pipeline pede nova tentativa) do que publicar um juízo de valor. A normalização
remove acentos e ignora maiúsculas/minúsculas; cada termo cobre as flexões de gênero e número
mais comuns (o radical é comparado com uma folga de poucos caracteres).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

LIMITE_CARACTERES = 280

# Cada entrada é o radical (sem acento, minúsculo) de um termo valorativo/juízo de valor.
# A folga de sufixo (`_SUFIXO_MAX`) cobre flexões comuns de gênero/número/grau
# (ousado/ousada/ousados/ousadas, irresponsavel/irresponsaveis, melhor/melhores...).
# Termos com plural irregular (radical + "vel"/"al" -> "veis"/"ais") são listados por extenso.
TERMOS_PROIBIDOS: dict[str, str] = {
    "ousad": "ousado/ousada/ousadia",
    "irresponsav": "irresponsável",
    "irresponsabilidade": "irresponsabilidade",
    "populist": "populista/populismo",
    "melhor": "melhor/melhores",
    "pior": "pior/piores",
    "radical": "radical/radicais",
    "extremist": "extremista/extremismo",
    "ambicios": "ambicioso",
    "corajos": "corajoso",
    "polemic": "polêmico",
    "inviav": "inviável/inviabilidade",
    "genial": "genial/geniais",
    "desastr": "desastroso/desastre",
    "absurd": "absurdo",
    "escandalos": "escandaloso",
    "vergonhos": "vergonhoso",
    "ingenu": "ingênuo",
    "levian": "leviano",
    "insensat": "insensato",
    "sensat": "sensato",
    "demagog": "demagógico/demagogia",
    "autoritari": "autoritário",
    "messianic": "messiânico",
    "utopic": "utópico",
    "heroic": "heroico",
    "brilhant": "brilhante",
    "fantastic": "fantástico",
    "pessim": "péssimo",
    "otim": "ótimo",
    "horrivel": "horrível",
    "terrivel": "terrível",
    "lamentavel": "lamentável",
    "bizarr": "bizarro",
    "insan": "insano",
    "corrupt": "corrupto/corrupção (juízo sobre pessoa, não sobre proposta)",
    "incompetent": "incompetente",
    "competent": "competente",
    "eficaz": "eficaz/ineficaz (juízo de resultado)",
    "eficient": "eficiente/ineficiente (juízo de resultado)",
    "revolucionari": "revolucionário",
    "audacios": "audacioso",
}

# folga de caracteres após o radical para cobrir flexões (ex.: ousad+o/a/os/as/ia)
_SUFIXO_MAX = 4


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _normaliza_busca(texto: str) -> str:
    return _sem_acento((texto or "").lower())


_PADROES = {
    radical: re.compile(rf"\b{re.escape(radical)}\w{{0,{_SUFIXO_MAX}}}\b")
    for radical in TERMOS_PROIBIDOS
}


def termos_encontrados(resumo: str) -> list[str]:
    """Lista os radicais de `TERMOS_PROIBIDOS` encontrados no resumo (normalizado)."""
    alvo = _normaliza_busca(resumo)
    return sorted(radical for radical, padrao in _PADROES.items() if padrao.search(alvo))


def menciona(resumo: str, nomes_proibidos: list[str]) -> list[str]:
    """Lista quais `nomes_proibidos` (outros candidatos/partidos/coligações) aparecem no resumo."""
    alvo = _normaliza_busca(resumo)
    achados = []
    for nome in nomes_proibidos:
        nome = (nome or "").strip()
        if len(nome) < 3:  # evita falso-positivo com siglas de 1-2 letras
            continue
        if _normaliza_busca(nome) in alvo:
            achados.append(nome)
    return achados


@dataclass
class ResultadoNeutralidade:
    aprovado: bool
    motivos: list[str] = field(default_factory=list)


def avalia_resumo(resumo: str | None, *, proibidos: list[str] | None = None) -> ResultadoNeutralidade:
    """Avalia um resumo contra as três regras de neutralidade. `proibidos` é a lista de nomes
    de urna, nomes civis e siglas partidárias/de coligação de outros candidatos — nunca do
    próprio candidato do resumo em análise."""
    motivos: list[str] = []
    if not resumo:
        return ResultadoNeutralidade(aprovado=False, motivos=["resumo vazio"])
    if len(resumo) > LIMITE_CARACTERES:
        motivos.append(f"resumo com {len(resumo)} caracteres (limite {LIMITE_CARACTERES})")
    termos = termos_encontrados(resumo)
    if termos:
        rotulos = ", ".join(TERMOS_PROIBIDOS[t] for t in termos)
        motivos.append(f"termo(s) valorativo(s)/juízo de valor: {rotulos}")
    mencoes = menciona(resumo, proibidos or [])
    if mencoes:
        motivos.append(f"menciona outro candidato/partido/coligação: {', '.join(mencoes)}")
    return ResultadoNeutralidade(aprovado=not motivos, motivos=motivos)
