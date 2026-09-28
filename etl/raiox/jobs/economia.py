"""Indicadores macroeconômicos (BCB SGS, IBGE SIDRA, CAGED/IPEADATA) → `indicador_valor`.

Roda: `python -m raiox economia`

Séries coletadas (ver `raiox.economia.*` para as notas de validação de cada fonte):
  ipca_mensal, ipca_12m, selic_meta, dbgg_pib, cambio_usd, resultado_primario  — BCB SGS
  desocupacao (Brasil + UF), pib_var                                          — IBGE SIDRA
  caged_saldo (somente Brasil — ver lacuna documentada em `raiox.economia.caged`)

Portão de qualidade por série: histórico não vazio, último ponto dentro do prazo de
defasagem esperado da fonte, valores dentro de faixas plausíveis, e — quando o próprio
payload traz o nome oficial da variável (SIDRA, CAGED/IPEADATA) — o nome bate com o
esperado. Qualquer falha usa `ex.exige(...)` (`FalhaQualidade`), que aborta a transação
inteira: nada é publicado numa execução com dado suspeito.
"""

from __future__ import annotations

import logging
from datetime import date

from ..common.db import conectar, upsert
from ..common.evidencia import registrar as registrar_evidencia
from ..common.http import cliente
from ..common.job import Execucao, executar
from ..economia import bcb, caged, sidra

log = logging.getLogger("raiox.jobs.economia")

HOJE = date.today()
INICIO_HISTORICO = date(1995, 1, 1)


def _upsert_indicador(conn, **campos) -> None:
    upsert(conn, "indicador", [campos], chave=["id"])


def _upsert_valores(conn, indicador_id: str, linhas: list[tuple[str, date, float]]) -> int:
    dados = [{"indicador_id": indicador_id, "uf": uf, "data": d, "valor": v} for uf, d, v in linhas]
    return upsert(conn, "indicador_valor", dados, chave=["indicador_id", "uf", "data"])


def _checa_recencia(ex: Execucao, indicador_id: str, ultima_data: date, dias_max: int) -> int:
    defasagem = (HOJE - ultima_data).days
    ex.exige(
        defasagem <= dias_max,
        f"{indicador_id}: último ponto em {ultima_data.isoformat()} está defasado em {defasagem} dias "
        f"(máximo aceito: {dias_max} — hoje: {HOJE.isoformat()})",
    )
    return defasagem


def _checa_faixa(ex: Execucao, indicador_id: str, pontos, minimo: float, maximo: float) -> None:
    for p in pontos:
        ex.exige(
            minimo <= p.valor <= maximo,
            f"{indicador_id}: valor absurdo em {p.data.isoformat()} = {p.valor} (esperado entre {minimo} e {maximo})",
        )


def _resumo(indicador_id: str, linhas: list[tuple[str, date, float]], nota: str = "") -> dict:
    ultimo = max(linhas, key=lambda x: x[1])
    por_uf = {ln[0] for ln in linhas}
    return {
        "id": indicador_id,
        "pontos": len(linhas),
        "ufs": sorted(por_uf),
        "ultima_data": ultimo[1].isoformat(),
        "ultimo_valor": ultimo[2],
        "nota": nota,
    }


# ---------------------------------------------------------------------------
# BCB SGS
# ---------------------------------------------------------------------------
def _coleta_ipca_mensal(ex: Execucao, c, conn) -> dict:
    pontos, url, bruto = bcb.coletar(c, 433, diario=False, inicio=INICIO_HISTORICO)
    ex.exige(len(pontos) > 0, "ipca_mensal: série vazia")
    _checa_faixa(ex, "ipca_mensal", pontos, -5, 30)
    ultima = max(p.data for p in pontos)
    _checa_recencia(ex, "ipca_mensal", ultima, 70)

    registrar_evidencia(conn, tipo_fonte="bcb", url_original=url, conteudo=bruto, mime="application/json")
    _upsert_indicador(
        conn, id="ipca_mensal", nome="IPCA — variação mensal", unidade="% a.m.",
        fonte="IBGE via BCB SGS", codigo_fonte="SGS 433", periodicidade="mensal",
        descricao="Índice Nacional de Preços ao Consumidor Amplo (IBGE), variação percentual no mês, "
                   "republicado pelo Banco Central no Sistema Gerenciador de Séries Temporais (SGS).",
        por_uf=False, url_fonte=url_sem_datas(433),
    )
    linhas = [("BR", p.data, p.valor) for p in pontos]
    ex.conta(_upsert_valores(conn, "ipca_mensal", linhas))
    return _resumo("ipca_mensal", linhas)


def _coleta_ipca_12m(ex: Execucao, c, conn) -> dict:
    pontos, url, bruto = bcb.coletar(c, 13522, diario=False, inicio=INICIO_HISTORICO)
    ex.exige(len(pontos) > 0, "ipca_12m: série vazia")
    # Faixa ampla: acomoda o período de estabilização do Plano Real (1995), quando o
    # acumulado em 12 meses ainda carregava a hiperinflação de 1994.
    _checa_faixa(ex, "ipca_12m", pontos, -5, 1000)
    ultima = max(p.data for p in pontos)
    _checa_recencia(ex, "ipca_12m", ultima, 70)

    registrar_evidencia(conn, tipo_fonte="bcb", url_original=url, conteudo=bruto, mime="application/json")
    _upsert_indicador(
        conn, id="ipca_12m", nome="IPCA — acumulado em 12 meses", unidade="%",
        fonte="IBGE via BCB SGS", codigo_fonte="SGS 13522", periodicidade="mensal",
        descricao="Inflação (IPCA) acumulada nos últimos 12 meses encerrados no mês de referência.",
        por_uf=False, url_fonte=url_sem_datas(13522),
    )
    linhas = [("BR", p.data, p.valor) for p in pontos]
    ex.conta(_upsert_valores(conn, "ipca_12m", linhas))
    return _resumo("ipca_12m", linhas)


def _coleta_selic_meta(ex: Execucao, c, conn) -> dict:
    diarios, url, bruto = bcb.coletar(c, 432, diario=True, inicio=INICIO_HISTORICO)
    ex.exige(len(diarios) > 0, "selic_meta: série vazia")
    _checa_faixa(ex, "selic_meta", diarios, 0, 100)
    ultima_diaria = max(p.data for p in diarios)
    _checa_recencia(ex, "selic_meta", ultima_diaria, 60)

    mensal = bcb.reduzir_mensal_ultimo(diarios)
    registrar_evidencia(conn, tipo_fonte="bcb", url_original=url, conteudo=bruto, mime="application/json")
    _upsert_indicador(
        conn, id="selic_meta", nome="Selic — meta definida pelo Copom", unidade="% a.a.",
        fonte="BCB SGS", codigo_fonte="SGS 432", periodicidade="mensal (reduzida de série diária)",
        descricao="Taxa básica de juros da economia definida pelo Comitê de Política Monetária (Copom). "
                   "Série original é diária (a meta vale até a próxima decisão); aqui reduzida ao último "
                   "valor observado em cada mês — não necessariamente a data exata de uma reunião do Copom.",
        por_uf=False, url_fonte=url_sem_datas(432),
    )
    linhas = [("BR", p.data, p.valor) for p in mensal]
    ex.conta(_upsert_valores(conn, "selic_meta", linhas))
    return _resumo("selic_meta", linhas, nota=f"reduzida de {len(diarios)} pontos diários")


def _coleta_dbgg(ex: Execucao, c, conn) -> dict:
    pontos, url, bruto = bcb.coletar(c, 13762, diario=False, inicio=INICIO_HISTORICO)
    ex.exige(len(pontos) > 0, "dbgg_pib: série vazia")
    _checa_faixa(ex, "dbgg_pib", pontos, 0, 200)
    ultima = max(p.data for p in pontos)
    _checa_recencia(ex, "dbgg_pib", ultima, 100)

    registrar_evidencia(conn, tipo_fonte="bcb", url_original=url, conteudo=bruto, mime="application/json")
    _upsert_indicador(
        conn, id="dbgg_pib", nome="Dívida Bruta do Governo Geral", unidade="% do PIB",
        fonte="BCB SGS", codigo_fonte="SGS 13762", periodicidade="mensal",
        descricao="Dívida bruta do governo geral em proporção do PIB (metodologia vigente desde dez/2006 — "
                   "não há série do BCB com essa metodologia anterior a essa data).",
        por_uf=False, url_fonte=url_sem_datas(13762),
    )
    linhas = [("BR", p.data, p.valor) for p in pontos]
    ex.conta(_upsert_valores(conn, "dbgg_pib", linhas))
    return _resumo("dbgg_pib", linhas)


def _coleta_cambio(ex: Execucao, c, conn) -> dict:
    diarios, url, bruto = bcb.coletar(c, 1, diario=True, inicio=INICIO_HISTORICO)
    ex.exige(len(diarios) > 0, "cambio_usd: série vazia")
    _checa_faixa(ex, "cambio_usd", diarios, 0, 20)
    ultima_diaria = max(p.data for p in diarios)
    _checa_recencia(ex, "cambio_usd", ultima_diaria, 15)

    mensal = bcb.reduzir_mensal_media(diarios)
    registrar_evidencia(conn, tipo_fonte="bcb", url_original=url, conteudo=bruto, mime="application/json")
    _upsert_indicador(
        conn, id="cambio_usd", nome="Dólar comercial (venda)", unidade="R$",
        fonte="BCB SGS", codigo_fonte="SGS 1", periodicidade="mensal (média de série diária)",
        descricao="Taxa de câmbio livre — dólar americano (venda), PTAX de fechamento. Série original é "
                   "diária; aqui reduzida à média aritmética simples das cotações de cada mês.",
        por_uf=False, url_fonte=url_sem_datas(1),
    )
    linhas = [("BR", p.data, p.valor) for p in mensal]
    ex.conta(_upsert_valores(conn, "cambio_usd", linhas))
    return _resumo("cambio_usd", linhas, nota=f"média de {len(diarios)} pontos diários")


def _coleta_resultado_primario(ex: Execucao, c, conn) -> dict:
    pontos, url, bruto = bcb.coletar(c, 5793, diario=False, inicio=INICIO_HISTORICO)
    ex.exige(len(pontos) > 0, "resultado_primario: série vazia")
    _checa_faixa(ex, "resultado_primario", pontos, -10, 10)
    ultima = max(p.data for p in pontos)
    _checa_recencia(ex, "resultado_primario", ultima, 100)

    registrar_evidencia(conn, tipo_fonte="bcb", url_original=url, conteudo=bruto, mime="application/json")
    _upsert_indicador(
        conn, id="resultado_primario", nome="Resultado primário do setor público consolidado",
        unidade="% do PIB", fonte="BCB SGS", codigo_fonte="SGS 5793", periodicidade="mensal",
        descricao="NFSP (Necessidades de Financiamento do Setor Público) sem desvalorização cambial — "
                   "resultado primário, setor público consolidado, fluxo acumulado em 12 meses, % do PIB. "
                   "Sinal positivo = superávit. Código validado em 27/09/2026 contra "
                   "https://dadosabertos.bcb.gov.br/dataset/5793-... (nome oficial da série bate com o "
                   "metadado aqui descrito).",
        por_uf=False, url_fonte=url_sem_datas(5793),
    )
    linhas = [("BR", p.data, p.valor) for p in pontos]
    ex.conta(_upsert_valores(conn, "resultado_primario", linhas))
    return _resumo("resultado_primario", linhas)


def url_sem_datas(codigo: int) -> str:
    return bcb.url_serie(codigo)


# ---------------------------------------------------------------------------
# IBGE SIDRA
# ---------------------------------------------------------------------------
def _coleta_desocupacao(ex: Execucao, c, conn) -> dict:
    pontos_br, url_br, bruto_br, nomes_br = sidra.desocupacao_brasil(c)
    pontos_uf, url_uf, bruto_uf, nomes_uf = sidra.desocupacao_uf(c)

    ex.exige(len(pontos_br) > 0 and len(pontos_uf) > 0, "desocupacao: série vazia (Brasil ou UF)")
    todos_nomes = nomes_br | nomes_uf
    ex.exige(
        any("desocupação" in n.lower() for n in todos_nomes),
        f"desocupacao: nome da variável não confere — {todos_nomes}",
    )
    _checa_faixa(ex, "desocupacao (BR)", pontos_br, 0, 40)
    _checa_faixa(ex, "desocupacao (UF)", pontos_uf, 0, 45)
    ultima_br = max(p.data for p in pontos_br)
    _checa_recencia(ex, "desocupacao", ultima_br, 120)
    ufs_cobertas = {p.uf for p in pontos_uf}
    ex.exige(len(ufs_cobertas) == 27, f"desocupacao: esperava 27 UFs, veio {len(ufs_cobertas)}: {sorted(ufs_cobertas)}")

    registrar_evidencia(conn, tipo_fonte="ibge", url_original=url_br, conteudo=bruto_br, mime="application/json")
    registrar_evidencia(conn, tipo_fonte="ibge", url_original=url_uf, conteudo=bruto_uf, mime="application/json")
    _upsert_indicador(
        conn, id="desocupacao", nome="Taxa de desocupação", unidade="%",
        fonte="IBGE PNAD Contínua", codigo_fonte="SIDRA 4099 (variável 4099)", periodicidade="trimestral",
        descricao="Taxa de desocupação, na semana de referência, das pessoas de 14 anos ou mais de idade "
                   "(PNAD Contínua trimestral). Disponível para o Brasil desde o 1º trimestre de 2012 e por UF.",
        por_uf=True, url_fonte="https://sidra.ibge.gov.br/tabela/4099",
    )
    linhas = [("BR", p.data, p.valor) for p in pontos_br] + [(p.uf, p.data, p.valor) for p in pontos_uf]
    ex.conta(_upsert_valores(conn, "desocupacao", linhas))
    return _resumo("desocupacao", linhas)


def _coleta_pib_var(ex: Execucao, c, conn) -> dict:
    pontos, url, bruto, nomes_var, nomes_cat = sidra.pib_variacao_acumulada(c)
    ex.exige(len(pontos) > 0, "pib_var: série vazia")
    ex.exige(
        any("acumulada em quatro trimestres" in n.lower() for n in nomes_var),
        f"pib_var: nome da variável não confere — {nomes_var}",
    )
    ex.exige(
        any("pib a preços de mercado" in n.lower() for n in nomes_cat),
        f"pib_var: categoria não confere — {nomes_cat}",
    )
    _checa_faixa(ex, "pib_var", pontos, -20, 20)
    ultima = max(p.data for p in pontos)
    _checa_recencia(ex, "pib_var", ultima, 120)

    registrar_evidencia(conn, tipo_fonte="ibge", url_original=url, conteudo=bruto, mime="application/json")
    _upsert_indicador(
        conn, id="pib_var", nome="PIB — variação acumulada em 4 trimestres", unidade="%",
        fonte="IBGE Contas Nacionais Trimestrais",
        codigo_fonte="SIDRA 5932 (variável 6562, categoria 90707 'PIB a preços de mercado')",
        periodicidade="trimestral",
        descricao="Taxa de variação do PIB a preços de mercado acumulada em quatro trimestres em relação "
                   "ao mesmo período do ano anterior. Disponível desde o 1º trimestre de 1996.",
        por_uf=False, url_fonte="https://sidra.ibge.gov.br/tabela/5932",
    )
    linhas = [("BR", p.data, p.valor) for p in pontos]
    ex.conta(_upsert_valores(conn, "pib_var", linhas))
    return _resumo("pib_var", linhas)


# ---------------------------------------------------------------------------
# CAGED (via IPEADATA)
# ---------------------------------------------------------------------------
def _coleta_caged(ex: Execucao, c, conn) -> dict:
    pontos, nomes, brutos = caged.coletar(c)
    ex.exige(len(pontos) > 0, "caged_saldo: série vazia")
    nome_antiga = nomes.get(caged.SERIE_ANTIGA, "")
    nome_nova = nomes.get(caged.SERIE_NOVA, "")
    ex.exige(
        "saldo" in nome_antiga.lower() and "caged" in nome_antiga.lower(),
        f"caged_saldo: nome da série antiga não confere — {nome_antiga!r}",
    )
    ex.exige(
        "saldo" in nome_nova.lower() and "caged" in nome_nova.lower(),
        f"caged_saldo: nome da série nova não confere — {nome_nova!r}",
    )
    _checa_faixa(ex, "caged_saldo", pontos, -3_000_000, 3_000_000)
    ultima = max(p.data for p in pontos)
    _checa_recencia(ex, "caged_saldo", ultima, 100)

    for codigo, bruto in brutos.items():
        registrar_evidencia(
            conn, tipo_fonte="caged", url_original=f"{caged.BASE}/ValoresSerie(SERCODIGO='{codigo}')",
            conteudo=bruto, mime="application/json",
        )
    _upsert_indicador(
        conn, id="caged_saldo", nome="Saldo de empregos formais (CAGED)", unidade="vagas",
        fonte="MTE Novo CAGED e CAGED (republicados pelo IPEADATA)",
        codigo_fonte=f"IPEADATA {caged.SERIE_ANTIGA} + {caged.SERIE_NOVA}", periodicidade="mensal",
        descricao="Admissões menos desligamentos com carteira assinada. ATENÇÃO — quebra metodológica em "
                   "jan/2020: valores até dez/2019 vêm do CAGED antigo (série descontinuada pela fonte, "
                   "disponível de mai/1999 a dez/2019); valores de jan/2020 em diante vêm do Novo CAGED. "
                   "LACUNA: nem o Novo CAGED nem o CAGED antigo têm API oficial de série temporal por UF — "
                   "só microdados brutos via FTP do PDET/MTE, inviáveis de agregar por UF nesta execução. "
                   "Por isso esta série está disponível apenas para o Brasil (sem recorte por UF).",
        por_uf=False, url_fonte="http://pdet.mte.gov.br/novo-caged",
    )
    linhas = [("BR", p.data, p.valor) for p in pontos]
    ex.conta(_upsert_valores(conn, "caged_saldo", linhas))
    quebra = sum(1 for p in pontos if p.data < caged.DATA_QUEBRA)
    return _resumo("caged_saldo", linhas, nota=f"{quebra} pontos do CAGED antigo (até dez/2019), sem UF")


# ---------------------------------------------------------------------------
def main(argv: list[str]) -> None:
    resumo: list[dict] = []
    with executar("economia") as ex:
        with cliente() as c, conectar() as conn:
            resumo.append(_coleta_ipca_mensal(ex, c, conn))
            resumo.append(_coleta_ipca_12m(ex, c, conn))
            resumo.append(_coleta_selic_meta(ex, c, conn))
            resumo.append(_coleta_dbgg(ex, c, conn))
            resumo.append(_coleta_cambio(ex, c, conn))
            resumo.append(_coleta_resultado_primario(ex, c, conn))
            resumo.append(_coleta_desocupacao(ex, c, conn))
            resumo.append(_coleta_pib_var(ex, c, conn))
            resumo.append(_coleta_caged(ex, c, conn))
            conn.commit()
        ex.detalhes["series"] = resumo

    log.info("Resumo por série:")
    for s in resumo:
        log.info(
            "  %-20s %6d pontos | UFs: %-4d | último: %s = %s | %s",
            s["id"], s["pontos"], len(s["ufs"]), s["ultima_data"], s["ultimo_valor"], s["nota"],
        )
