"""Exporta os dados PUBLICÁVEIS do banco para os JSONs estáticos do site.

Contrato: packages/core/src/contrato.ts (qualquer mudança lá exige mudança aqui).

Regras de publicação aplicadas aqui (defesa em profundidade, além do banco):
  * processo / checagem / proposta / quiz_posicao: somente status_revisao = 'aprovado'.
  * CPF, título de eleitor e cpf_hmac nunca saem do banco (verificação final varre os arquivos).
  * Posições da Bússola derivadas de votações nominais são calculadas aqui, a partir do
    mapeamento revisado pergunta ↔ votação (quiz_pergunta_votacao) — o próprio voto é a evidência.

Uso:  python -m raiox exportar --saida ../apps/web/public/dados
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import orjson

from raiox.common.config import ANO_ELEICAO, ELEICAO_2026, RAIZ_REPO
from raiox.common.db import conectar
from raiox.common.identidade import titulo_nome
from raiox.common.job import executar

log = logging.getLogger("raiox.exportar")

NUM_BUCKETS = 5000  # igual a contrato.ts
LIMITE_ARQUIVOS = 18_000  # Cloudflare Pages: 20.000 por deploy (margem para o site)

CARGOS: dict[int, dict[str, Any]] = {
    1: {"slug": "presidente", "majoritario": True},
    3: {"slug": "governador", "majoritario": True},
    5: {"slug": "senador", "majoritario": True},
    6: {"slug": "deputado-federal", "majoritario": False},
    7: {"slug": "deputado-estadual", "majoritario": False},
    8: {"slug": "deputado-distrital", "majoritario": False},
}

DESCRICAO_CERTIDAO = {
    11: "Certidão criminal da Justiça Federal de 1º grau",
    12: "Certidão criminal da Justiça Federal de 2º grau",
    13: "Certidão criminal da Justiça Estadual de 1º grau",
    14: "Certidão criminal da Justiça Estadual de 2º grau",
    15: "Certidão criminal de foro por prerrogativa de função",
    1: "Certidão",
}

STATUS_TEXTO = {
    "reu_acao_penal": "Réu em ação penal — sem condenação",
    "condenado_1a_instancia": "Condenado em 1ª instância — cabe recurso",
    "condenado_orgao_colegiado": "Condenado por órgão colegiado — cabe recurso",
    "condenado_transito_julgado": "Condenação definitiva",
    "absolvido": "Absolvido",
    "anulado": "Processo anulado",
    "punibilidade_extinta": "Punibilidade extinta",
    "acao_civel_em_curso": "Ação cível em andamento",
    "acao_civel_procedente": "Ação cível julgada procedente",
    "acao_civel_improcedente": "Ação cível julgada improcedente",
}
STATUS_ATIVOS = {"reu_acao_penal", "condenado_1a_instancia", "condenado_orgao_colegiado", "acao_civel_em_curso"}

ROTULO_FONTE = {
    "tse": "TSE — DivulgaCandContas",
    "camara": "Câmara dos Deputados — Dados Abertos",
    "senado": "Senado Federal — Dados Abertos",
    "cgu": "Portal da Transparência (CGU)",
    "datajud": "CNJ — DataJud",
    "bcb": "Banco Central — SGS",
    "ibge": "IBGE — SIDRA",
    "caged": "MTE — Novo CAGED",
    "factcheck": "Agência de checagem (ClaimReview)",
}

FONTES_META = [
    ("tse", "Tribunal Superior Eleitoral (DivulgaCandContas)", "https://divulgacandcontas.tse.jus.br",
     ["tse_candidaturas", "tse_contas", "tse_arquivos", "tse_historico"]),
    ("camara", "Câmara dos Deputados", "https://dadosabertos.camara.leg.br", ["camara"]),
    ("senado", "Senado Federal", "https://legis.senado.leg.br/dadosabertos", ["senado"]),
    ("cgu", "Portal da Transparência (CGU)", "https://portaldatransparencia.gov.br", ["cgu_emendas"]),
    ("cnj", "CNJ — DataJud", "https://datajud-wiki.cnj.jus.br", ["datajud"]),
    ("economia", "BCB, IBGE e MTE", "https://dadosabertos.bcb.gov.br", ["economia"]),
    ("checagens", "Agências de checagem signatárias da IFCN", "https://ifcncodeofprinciples.poynter.org",
     ["factcheck"]),
]

# Escopo do produto (decisão de 28/09/2026): somente a eleição presidencial.
CARGOS_PUBLICADOS = (1,)

CAMPOS_PROIBIDOS = re.compile(rb'"(cpf|tituloEleitor|titulo_eleitor|cpf_hmac)"\s*:')


# ---------------------------------------------------------------------------
# utilitários
# ---------------------------------------------------------------------------
def _default(o: Any) -> Any:
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, datetime):
        return o.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(type(o))


def _grava(caminho: Path, dados: Any) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(orjson.dumps(dados, default=_default))


def _num(v: Any) -> float | None:
    return None if v is None else float(v)


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    return _default(v) if isinstance(v, date | datetime) else str(v)


def _nome(v: str | None) -> str:
    return titulo_nome(v) or ""


def _evidencia(ev: dict[str, Any] | None, rotulo: str | None = None) -> dict[str, Any] | None:
    if not ev or not ev.get("id"):
        return None
    return {
        "id": str(ev["id"]),
        "rotulo": rotulo or ROTULO_FONTE.get(ev["tipo_fonte"], ev["tipo_fonte"]),
        "urlOriginal": ev["url_original"],
        "urlArquivo": ev.get("url_arquivo"),
        "sha256": ev["sha256"],
        "capturadoEm": _iso(ev["capturado_em"]),
    }


def _url_tse(c: dict[str, Any]) -> str:
    uf = c["uf"]
    return (f"https://divulgacandcontas.tse.jus.br/divulga/#/candidato/BR/{uf}/{c['eleicao_id']}/"
            f"{c['id']}/{c['ano']}/{uf}")


def _resumo(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": c["id"],
        "slug": c["slug"] if CARGOS[c["cargo_codigo"]]["majoritario"] else None,
        "nomeUrna": _nome(c["nome_urna"]),
        "numero": c["numero"],
        "partido": {"sigla": c["partido_sigla"] or "", "nome": _nome(c["partido_nome"])},
        "cargo": c["cargo_codigo"],
        "uf": c["uf"],
        "foto": c["foto_url"],
        "situacaoRegistro": c["situacao_registro"] or "",
        "situacaoTotalizacao": c["situacao_totalizacao"] or "",
        "reeleicao": bool(c["reeleicao"]),
    }


def _ordem_alfabetica(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from raiox.common.identidade import sem_acento

    return sorted(itens, key=lambda x: (sem_acento(x["nomeUrna"]).lower(), x["id"]))


# ---------------------------------------------------------------------------
# correção monetária (IPCA)
# ---------------------------------------------------------------------------
class CorrecaoIPCA:
    """Fator de correção pelo IPCA mensal (SGS 433).

    Base: agosto do ano da eleição (mês de entrega das declarações de bens ao TSE).
    Fator = produto de (1 + ipca/100) de setembro do ano-base até o último mês disponível.
    """

    def __init__(self, serie: list[tuple[date, float]]):
        self.serie = sorted(serie)
        self.referencia = self.serie[-1][0] if self.serie else None

    def fator(self, ano_base: int) -> float | None:
        if not self.serie:
            return None
        inicio = date(ano_base, 9, 1)
        if inicio < self.serie[0][0]:
            return None
        f = 1.0
        for d, v in self.serie:
            if d >= inicio:
                f *= 1 + v / 100
        return f


# ---------------------------------------------------------------------------
# exportação
# ---------------------------------------------------------------------------
def exportar(saida: Path) -> dict[str, int]:
    with conectar() as conn:
        q = lambda sql, *p: conn.execute(sql, p).fetchall()  # noqa: E731

        evidencias = {str(r["id"]): r for r in q("select * from evidencia")}
        ev = lambda i, rot=None: _evidencia(evidencias.get(str(i)) if i else None, rot)  # noqa: E731

        # --- candidaturas 2026 (titulares) ---
        cands = q(
            """select c.*, p.slug, p.nome_urna, p.nome_civil, p.data_nascimento, p.genero, p.cor_raca,
                      p.grau_instrucao, p.ocupacao, p.uf_nascimento, p.municipio_nascimento, p.foto_url
               from candidatura c join pessoa p on p.id = c.pessoa_id
               where c.eleicao_id = %s and c.titular and c.cargo_codigo = any(%s)""",
            ELEICAO_2026, list(CARGOS_PUBLICADOS),
        )
        log.info("candidaturas 2026 publicadas: %s", len(cands))
        ids = [c["id"] for c in cands]
        pessoas = list({c["pessoa_id"] for c in cands})

        vices = defaultdict(list)
        for v in q(
            """select c.candidatura_titular_id, c.cargo_nome, c.partido_sigla, p.nome_urna, p.foto_url
               from candidatura c join pessoa p on p.id = c.pessoa_id
               where c.eleicao_id = %s and not c.titular and c.candidatura_titular_id is not null""",
            ELEICAO_2026,
        ):
            vices[v["candidatura_titular_id"]].append({
                "nomeUrna": _nome(v["nome_urna"]), "cargo": v["cargo_nome"] or "",
                "partido": v["partido_sigla"] or "", "foto": v["foto_url"],
            })

        bens = defaultdict(list)
        for b in q("select * from bem where candidatura_id = any(%s) order by candidatura_id, ordem", ids):
            bens[b["candidatura_id"]].append({"tipo": b["tipo"] or "", "descricao": b["descricao"] or "",
                                              "valor": float(b["valor"])})

        ipca = CorrecaoIPCA([(r["data"], float(r["valor"])) for r in q(
            "select data, valor from indicador_valor where indicador_id = 'ipca_mensal' and uf = 'BR'")])

        historico = defaultdict(list)
        eleicoes_disputadas = defaultdict(list)
        for h in q(
            """select c.id, c.pessoa_id, c.ano, c.cargo_nome, c.uf, c.municipio, c.partido_sigla,
                      c.situacao_totalizacao,
                      coalesce((select sum(valor) from bem b where b.candidatura_id = c.id), c.total_bens) as total
               from candidatura c where c.pessoa_id = any(%s) and c.titular
               order by c.ano""",
            pessoas,
        ):
            local = h["municipio"] or h["uf"]
            eleicoes_disputadas[h["pessoa_id"]].append({
                "ano": h["ano"], "cargo": h["cargo_nome"], "local": _nome(local) if len(local or "") > 2 else local,
                "partido": h["partido_sigla"] or "", "resultado": h["situacao_totalizacao"] or "",
                "candidaturaId": h["id"],
            })
            if h["total"] is not None:
                fator = ipca.fator(h["ano"])
                historico[h["pessoa_id"]].append({
                    "ano": h["ano"], "cargo": h["cargo_nome"], "uf": h["uf"], "total": float(h["total"]),
                    "totalCorrigido": round(float(h["total"]) * fator, 2) if fator else None,
                })

        mandatos = defaultdict(list)
        for m in q("select * from mandato where pessoa_id = any(%s) order by inicio", pessoas):
            mandatos[m["pessoa_id"]].append({
                "cargo": m["cargo"], "esfera": m["esfera"],
                "local": _nome(m["municipio"]) if m["municipio"] else m["uf"],
                "inicio": _iso(m["inicio"]), "fim": _iso(m["fim"]), "origem": m["origem"],
            })

        contas = {r["candidatura_id"]: r
                  for r in q("select * from contas_campanha where candidatura_id = any(%s)", ids)}
        doadores = defaultdict(list)
        for d in q("select * from maior_doador where candidatura_id = any(%s) order by posicao", ids):
            doadores[d["candidatura_id"]].append({"nome": d["nome"], "tipo": d["tipo"], "valor": float(d["valor"])})

        # --- legislativo ---
        parl = defaultdict(list)
        for p in q(
            """select * from parlamentar where pessoa_id = any(%s)
               and (vinculo_confianca >= 90 or vinculo_revisado)""",
            pessoas,
        ):
            parl[p["pessoa_id"]].append(p)
        chaves_parl = [(p["casa"], p["id_externo"]) for lst in parl.values() for p in lst]
        casas = [c for c, _ in chaves_parl]
        ext = [e for _, e in chaves_parl]

        presenca = defaultdict(list)
        cota = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        votos_chave = defaultdict(list)
        votos_todos: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
        if chaves_parl:
            filtro = "(casa, id_externo) in (select * from unnest(%s::text[], %s::text[]))"
            for r in q(f"select * from presenca where {filtro} order by ano", casas, ext):
                presenca[(r["casa"], r["id_externo"])].append({
                    "ano": r["ano"], "sessoes": r["sessoes"], "presencas": r["presencas"],
                    "ausenciasJustificadas": r["ausencias_justificadas"],
                })
            for r in q(f"select casa, id_externo, ano, categoria, sum(valor) v from despesa_cota where {filtro} "
                       "group by 1,2,3,4", casas, ext):
                cota[(r["casa"], r["id_externo"])][r["ano"]][r["categoria"]] += float(r["v"])
            for r in q(
                """select v.casa, v.id_externo, v.voto, vt.id, vt.data, vt.descricao, vt.resultado, vt.url,
                           vt.tema_id, pr.sigla_tipo, pr.numero, pr.ano
                    from voto v join votacao vt on vt.id = v.votacao_id
                    left join proposicao pr on pr.id = vt.proposicao_id
                    where vt.chave and (v.casa, v.id_externo) in (select * from unnest(%s::text[], %s::text[]))
                    order by vt.data desc""",
                casas, ext,
            ):
                prop = f"{r['sigla_tipo']} {r['numero']}/{r['ano']}" if r["sigla_tipo"] else ""
                votos_chave[(r["casa"], r["id_externo"])].append({
                    "votacaoId": r["id"], "data": _iso(r["data"]), "proposicao": prop,
                    "descricao": r["descricao"] or "", "temaId": r["tema_id"], "voto": r["voto"],
                    "resultado": r["resultado"] or "", "url": r["url"] or "",
                })
            for r in q(
                """select v.casa, v.id_externo, v.votacao_id, v.voto from voto v
                    where v.votacao_id in (select votacao_id from quiz_pergunta_votacao)
                    and (v.casa, v.id_externo) in (select * from unnest(%s::text[], %s::text[]))""",
                casas, ext,
            ):
                votos_todos[(r["casa"], r["id_externo"])][r["votacao_id"]] = r["voto"]

        emendas = defaultdict(list)
        for r in q(
            """select pessoa_id, ano, coalesce(sum(valor_empenhado),0) e, coalesce(sum(valor_pago),0) p, count(*) n
               from emenda where pessoa_id = any(%s) group by 1,2 order by 2""",
            pessoas,
        ):
            emendas[r["pessoa_id"]].append({"ano": r["ano"], "empenhado": float(r["e"]), "pago": float(r["p"]),
                                            "quantidade": r["n"]})

        # --- justiça ---
        analises = {r["arquivo_id"]: r for r in q("select * from certidao_analise")}
        certidoes = defaultdict(list)
        documentos_plano: dict[int, dict[str, Any] | None] = {}
        for a in q("select * from arquivo_tse where candidatura_id = any(%s) order by cod_tipo, id", ids):
            if a["cod_tipo"] == 5:
                documentos_plano[a["candidatura_id"]] = ev(a["evidencia_id"], "Proposta de governo (TSE)")
                continue
            if a["cod_tipo"] not in DESCRICAO_CERTIDAO:
                continue
            an = analises.get(a["id"])
            certidoes[a["candidatura_id"]].append({
                "tipo": DESCRICAO_CERTIDAO[a["cod_tipo"]],
                "resultado": an["resultado"] if an else "nao_analisada",
                "documento": ev(a["evidencia_id"], DESCRICAO_CERTIDAO[a["cod_tipo"]]),
            })

        processos = defaultdict(list)
        for p in q(
            """select pr.*, pp.pessoa_id, pp.evidencia_id as ev_vinculo
               from processo pr join processo_parte pp on pp.processo_id = pr.id
               where pr.status_revisao = 'aprovado' and pr.status is not null and pp.pessoa_id = any(%s)""",
            pessoas,
        ):
            evs = [e for e in (ev(p["evidencia_id"]), ev(p["ev_vinculo"])) if e]
            processos[p["pessoa_id"]].append({
                "numeroCnj": p["numero_cnj"], "tribunal": p["tribunal"], "classe": p["classe"],
                "assuntos": p["assuntos"] or [], "status": p["status"],
                "statusDescricao": p["status_descricao"] or STATUS_TEXTO[p["status"]],
                "ativo": p["status"] in STATUS_ATIVOS,
                "ultimaMovimentacao": ({"data": _iso(p["ultima_movimentacao_em"]),
                                        "descricao": p["ultima_movimentacao"] or ""}
                                       if p["ultima_movimentacao_em"] else None),
                "consultaUrl": evs[0]["urlOriginal"] if evs else "",
                "evidencias": evs,
                "publicadoEm": _iso(p["publicado_em"]),
            })

        agencias = {r["id"]: r["nome"] for r in q("select id, nome from agencia_checagem")}
        checagens = defaultdict(list)
        for c in q(
            """select * from checagem where status_revisao = 'aprovado' and pessoa_id = any(%s)
               order by data_publicacao desc nulls last""",
            pessoas,
        ):
            checagens[c["pessoa_id"]].append({
                "agencia": agencias.get(c["agencia_id"], c["agencia_id"]), "url": c["url"], "titulo": c["titulo"],
                "alegacao": c["alegacao"], "avaliacaoOriginal": c["avaliacao_original"],
                "dataPublicacao": _iso(c["data_publicacao"]), "relacao": c["relacao"], "temaId": c["tema_id"],
            })

        temas = q("select * from tema order by ordem")
        propostas = defaultdict(dict)
        for p in q("select * from proposta where status_revisao = 'aprovado' and candidatura_id = any(%s)", ids):
            propostas[p["candidatura_id"]][p["tema_id"]] = {
                "temaId": p["tema_id"], "resumo": p["resumo"], "trechos": p["trechos"] or [],
                "semMencao": p["sem_mencao"], "geradoPorIa": p["gerado_por_ia"],
                "documento": documentos_plano.get(p["candidatura_id"]),
            }

        changelog = defaultdict(list)
        for r in q("select * from changelog_publico where pessoa_id = any(%s) order by created_at desc", pessoas):
            changelog[r["pessoa_id"]].append({"data": _iso(r["created_at"]), "tipo": r["tipo"],
                                              "descricao": r["descricao"]})

        # --- bússola ---
        perguntas = q("select * from quiz_pergunta where ativa order by ordem")
        mapa_pv = defaultdict(list)
        votacoes_info = {}
        for r in q(
            """select qpv.pergunta_id, qpv.votacao_id, qpv.direcao, vt.data, vt.url, vt.descricao,
                      pr.sigla_tipo, pr.numero, pr.ano
               from quiz_pergunta_votacao qpv join votacao vt on vt.id = qpv.votacao_id
               left join proposicao pr on pr.id = vt.proposicao_id"""
        ):
            mapa_pv[r["pergunta_id"]].append((r["votacao_id"], r["direcao"]))
            votacoes_info[r["votacao_id"]] = r
        posicoes_rev = defaultdict(dict)
        for r in q("select * from quiz_posicao where status_revisao = 'aprovado' and pessoa_id = any(%s)", pessoas):
            posicoes_rev[r["pessoa_id"]][r["pergunta_id"]] = {
                "valor": r["valor"], "fonte": r["fonte_tipo"], "justificativa": r["justificativa"],
                "evidencia": ev(r["evidencia_id"]),
            }

        def posicoes_de(pessoa_id: Any) -> dict[str, Any]:
            res: dict[str, Any] = {}
            votos_pessoa: dict[str, str] = {}
            for p in parl.get(pessoa_id, []):
                votos_pessoa.update(votos_todos.get((p["casa"], p["id_externo"]), {}))
            for pg in perguntas:
                pid = pg["id"]
                if pid in posicoes_rev.get(pessoa_id, {}):
                    res[pid] = posicoes_rev[pessoa_id][pid]
                    continue
                sinais, partes, ultima = [], [], None
                for vid, direcao in mapa_pv.get(pid, []):
                    voto = votos_pessoa.get(vid)
                    if voto not in ("Sim", "Não"):
                        continue
                    sinais.append(direcao * (1 if voto == "Sim" else -1))
                    info = votacoes_info[vid]
                    prop = f"{info['sigla_tipo']} {info['numero']}/{info['ano']}" if info["sigla_tipo"] else "votação"
                    partes.append(f"votou {voto} em {prop} ({_iso(info['data'])[:10]})")
                    ultima = info
                if not sinais:
                    continue
                media = sum(sinais) / len(sinais)
                valor = max(-2, min(2, round(media * 2)))
                res[pid] = {
                    "valor": valor, "fonte": "voto",
                    "justificativa": "Com base em votações nominais: " + "; ".join(partes) + ".",
                    "evidencia": {"id": f"votacao:{ultima['votacao_id']}", "rotulo": "Votação nominal",
                                  "urlOriginal": ultima["url"] or "", "urlArquivo": None, "sha256": "",
                                  "capturadoEm": _iso(ultima["data"])} if ultima else None,
                }
            return res

        # --- economia ---
        indicadores = q("select * from indicador order by id")
        valores = defaultdict(lambda: defaultdict(list))
        for r in q("select indicador_id, uf, data, valor from indicador_valor order by data"):
            valores[r["indicador_id"]][r["uf"]].append([_iso(r["data"]), float(r["valor"])])
        periodos = q("select * from periodo_governo order by uf, inicio")

        execucoes = {r["job"]: r["fim"] for r in q(
            "select job, max(fim) fim from etl_execucao where status = 'sucesso' group by job")}
        correcoes_log = q(
            """select cl.*, p.nome_urna, p.slug,
                      (select c.id from candidatura c where c.pessoa_id = p.id and c.eleicao_id = %s
                       and c.titular limit 1) as cand_id,
                      (select c.cargo_codigo from candidatura c where c.pessoa_id = p.id and c.eleicao_id = %s
                       and c.titular limit 1) as cargo
               from changelog_publico cl left join pessoa p on p.id = cl.pessoa_id
               where cl.tipo in ('correcao', 'remocao') order by cl.created_at desc limit 1000""",
            ELEICAO_2026, ELEICAO_2026,
        )

    # ------------------------------------------------------------------
    # montagem e gravação
    # ------------------------------------------------------------------
    tmp = saida.with_name(saida.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    agora = datetime.now(UTC)
    buckets: dict[int, dict[str, Any]] = defaultdict(dict)
    listas: dict[str, list[dict[str, Any]]] = defaultdict(list)
    busca: list[list[Any]] = []
    por_cargo: dict[str, int] = defaultdict(int)
    resumo_por_id: dict[int, dict[str, Any]] = {}
    posicoes_por_pessoa: dict[Any, dict[str, Any]] = {}

    for c in cands:
        r = _resumo(c)
        resumo_por_id[c["id"]] = r
        slug_cargo = CARGOS[c["cargo_codigo"]]["slug"]
        listas[f"{slug_cargo}-{c['uf'].lower()}"].append(r)
        por_cargo[slug_cargo] += 1
        busca.append([c["id"], r["slug"], r["nomeUrna"], _nome(c["nome_civil"]), r["partido"]["sigla"],
                      c["cargo_codigo"], c["uf"], c["numero"]])

        pid = c["pessoa_id"]
        leg = []
        for p in parl.get(pid, []):
            chave = (p["casa"], p["id_externo"])
            leg.append({
                "casa": p["casa"], "idExterno": p["id_externo"],
                "urlPerfilOficial": (f"https://www.camara.leg.br/deputados/{p['id_externo']}" if p["casa"] == "camara"
                                     else f"https://www25.senado.leg.br/web/senadores/senador/-/perfil/{p['id_externo']}"),
                "presenca": presenca.get(chave, []),
                "votacoesChave": votos_chave.get(chave, []),
                "cota": [{"ano": ano, "total": round(sum(cats.values()), 2),
                          "porCategoria": sorted(({"categoria": k, "valor": round(v, 2)} for k, v in cats.items()),
                                                 key=lambda x: -x["valor"])}
                         for ano, cats in sorted(cota.get(chave, {}).items())],
                "emendas": emendas.get(pid, []) if p["casa"] else [],
            })

        conta = contas.get(c["id"])
        campanha = None
        if conta or c["limite_gasto_1t"] is not None:
            receitas = []
            if conta:
                for rotulo, campo in (
                    ("Fundo Especial (FEFC)", "receita_fundo_especial"),
                    ("Fundo Partidário", "receita_fundo_partidario"),
                    ("Partidos", "receita_partidos"), ("Pessoas físicas", "receita_pf"),
                    ("Recursos próprios", "receita_propria"), ("Outros candidatos", "receita_outros_candidatos"),
                    ("Financiamento coletivo (internet)", "receita_internet"), ("Pessoas jurídicas", "receita_pj"),
                    ("Estimáveis em dinheiro", "receita_estimada"),
                ):
                    v = _num(conta.get(campo))
                    if v:
                        receitas.append({"origem": rotulo, "valor": v})
            campanha = {
                "limiteGasto1T": _num(c["limite_gasto_1t"]), "limiteGasto2T": _num(c["limite_gasto_2t"]),
                "totalRecebido": _num(conta["total_recebido"]) if conta else None,
                "totalDespesas": _num(conta["total_despesas"]) if conta else None,
                "receitas": receitas, "maioresDoadores": doadores.get(c["id"], []),
                "atualizadoEm": _iso(conta["atualizado_tse_em"]) if conta else None,
            }

        props = None
        if c["cargo_codigo"] in (1, 3):
            props = [propostas[c["id"]][t["id"]] for t in temas if t["id"] in propostas.get(c["id"], {})]

        fontes = [e for e in (ev(c["evidencia_id"], "TSE — registro de candidatura"),) if e]
        for cert in certidoes.get(c["id"], []):
            if cert["documento"]:
                fontes.append(cert["documento"])
        if documentos_plano.get(c["id"]):
            fontes.append(documentos_plano[c["id"]])

        naturalidade = None
        if c["municipio_nascimento"] or c["uf_nascimento"]:
            naturalidade = " / ".join(x for x in (_nome(c["municipio_nascimento"]), c["uf_nascimento"]) if x)

        perfil = {
            **r,
            "nomeCivil": _nome(c["nome_civil"]),
            "partido": {**r["partido"], "numero": c["partido_numero"] or 0},
            "coligacao": {"nome": c["coligacao_nome"], "composicao": c["coligacao_composicao"]},
            "dadosPessoais": {
                "nascimento": _iso(c["data_nascimento"]), "genero": c["genero"], "corRaca": c["cor_raca"],
                "grauInstrucao": c["grau_instrucao"], "ocupacao": c["ocupacao"], "naturalidade": naturalidade,
            },
            "vices": vices.get(c["id"], []),
            "sites": c["sites"] or [],
            "patrimonio": {
                "total": sum(b["valor"] for b in bens.get(c["id"], [])) or float(c["total_bens"] or 0),
                "bens": bens.get(c["id"], []),
                "historico": historico.get(pid, []),
                "referenciaCorrecao": _iso(ipca.referencia),
            },
            "trajetoria": {"eleicoes": eleicoes_disputadas.get(pid, []), "mandatos": mandatos.get(pid, [])},
            "campanha": campanha,
            "legislativo": leg,
            "justica": {"certidoes": certidoes.get(c["id"], []), "processos": processos.get(pid, [])},
            "checagens": checagens.get(pid, []),
            "propostas": props,
            "fontes": fontes,
            "changelog": changelog.get(pid, []),
            "urlTse": _url_tse(c),
            "atualizadoEm": _iso(c["atualizado_tse_em"] or c["coletado_em"]),
        }
        buckets[c["id"] % NUM_BUCKETS][str(c["id"])] = perfil
        posicoes_por_pessoa[c["id"]] = posicoes_de(pid)

    for b, conteudo in buckets.items():
        _grava(tmp / "c" / f"{b}.json", conteudo)
    for chave, itens in listas.items():
        _grava(tmp / "lista" / f"{chave}.json", _ordem_alfabetica(itens))
    _grava(tmp / "busca.json", busca)

    temas_pub = [{"id": t["id"], "eixo": t["eixo"], "nome": t["nome"], "descricao": t["descricao"] or ""}
                 for t in temas]
    perguntas_pub = [{"id": p["id"], "temaId": p["tema_id"], "texto": p["texto"], "contexto": p["contexto"],
                      "argumentoFavor": p["argumento_favor"], "argumentoContra": p["argumento_contra"]}
                     for p in perguntas]
    for chave, itens in listas.items():
        cargo = itens[0]["cargo"]
        uf = itens[0]["uf"]
        ordenados = _ordem_alfabetica(itens)
        if cargo in (1, 3, 5):
            _grava(tmp / "comparar" / f"{chave}.json", {
                "cargo": cargo, "uf": uf, "temas": temas_pub,
                "candidatos": [{**i, "propostas": buckets[i["id"] % NUM_BUCKETS][str(i["id"])]["propostas"] or []}
                               for i in ordenados],
            })
        if perguntas_pub:
            _grava(tmp / "bussola" / f"{chave}.json", {
                "cargo": cargo, "uf": uf, "perguntas": perguntas_pub,
                "candidatos": [{**i, "posicoes": posicoes_por_pessoa.get(i["id"], {})} for i in ordenados],
            })

    _grava(tmp / "economia.json", {
        "atualizadoEm": _iso(execucoes.get("economia")) or _iso(agora),
        "indicadores": [{
            "id": i["id"], "nome": i["nome"], "unidade": i["unidade"], "fonte": i["fonte"],
            "descricao": i["descricao"], "periodicidade": i["periodicidade"], "urlFonte": i["url_fonte"],
            "porUf": i["por_uf"], "serie": valores[i["id"]].get("BR", []),
            **({"seriesUf": {uf: s for uf, s in valores[i["id"]].items() if uf != "BR"}} if i["por_uf"] else {}),
        } for i in indicadores],
        "periodos": [{"cargo": p["cargo"], "uf": p["uf"], "nome": p["nome"], "inicio": _iso(p["inicio"]),
                      "fim": _iso(p["fim"]), "fonteUrl": p["fonte_url"]} for p in periodos],
    })

    _grava(tmp / "correcoes.json", {
        "atualizadoEm": _iso(agora),
        "itens": [{
            "data": _iso(r["created_at"]),
            "pessoa": ({"nomeUrna": _nome(r["nome_urna"]),
                        "slug": r["slug"] if r["cargo"] and CARGOS[r["cargo"]]["majoritario"] else None,
                        "id": r["cand_id"]} if r["nome_urna"] and r["cand_id"] else None),
            "tipo": r["tipo"], "descricao": r["descricao"],
        } for r in correcoes_log],
    })

    def ultima(jobs: list[str]) -> str | None:
        datas = [execucoes[j] for j in jobs if execucoes.get(j)]
        return _iso(max(datas)) if datas else None

    _grava(tmp / "meta.json", {
        "geradoEm": _iso(agora),
        "eleicao": {"id": ELEICAO_2026, "ano": ANO_ELEICAO, "data": "2026-10-04", "segundoTurno": "2026-10-25"},
        "totais": {"candidaturas": len(cands), "porCargo": dict(por_cargo)},
        "fontes": [{"id": i, "nome": n, "atualizadoEm": ultima(jobs), "url": u} for i, n, u, jobs in FONTES_META],
    })

    # ---------------- verificações finais ----------------
    arquivos = [p for p in tmp.rglob("*.json")]
    for p in arquivos:
        if CAMPOS_PROIBIDOS.search(p.read_bytes()):
            raise RuntimeError(f"Campo proibido (CPF/título) encontrado em {p}")
    if len(arquivos) > LIMITE_ARQUIVOS:
        raise RuntimeError(f"{len(arquivos)} arquivos excede o limite de {LIMITE_ARQUIVOS}")

    if saida.exists():
        shutil.rmtree(saida)
    tmp.rename(saida)
    return {"arquivos": len(arquivos), "candidaturas": len(cands), "buckets": len(buckets), "listas": len(listas)}


def main(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(prog="raiox exportar", description=__doc__)
    ap.add_argument("--saida", type=Path, default=RAIZ_REPO / "apps" / "web" / "public" / "dados")
    ap.add_argument("--minimo", type=int, default=10,
                    help="Mínimo de candidaturas 2026 exigido (portão de qualidade). Use 0 em desenvolvimento.")
    args = ap.parse_args(argv)
    with executar("exportar") as ex:
        stats = exportar(args.saida.resolve())
        ex.detalhes.update(stats)
        ex.conta(stats["arquivos"])
        ex.exige(stats["candidaturas"] >= args.minimo,
                 f"Só {stats['candidaturas']} candidaturas exportadas (mínimo {args.minimo})")
        log.info("Exportação concluída: %s", stats)
