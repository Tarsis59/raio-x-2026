"""Repositório imutável de evidências.

Cada documento coletado recebe um SHA-256, fica em cache local e, quando o arquivamento
está ativado (RAIOX_ARQUIVAR=1), recebe uma cópia pública e permanente no Internet Archive
(archive.org, API S3 gratuita). A linha em `evidencia` nunca é alterada depois de criada
(trigger no banco), exceto os campos de arquivamento e de verificação de link.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
from pathlib import Path

import httpx
import psycopg
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import config

log = logging.getLogger("raiox.evidencia")

IA_S3 = "https://s3.us.archive.org"
PREFIXO_ITEM = "raiox2026-evidencias"


def sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _extensao(mime: str | None) -> str:
    base = (mime or "").split(";")[0].strip()
    if base == "application/json":
        return ".json"
    if base == "application/pdf":
        return ".pdf"
    return mimetypes.guess_extension(base) or ".bin"


def caminho_cache(hash_: str, mime: str | None) -> Path:
    p = config().cache_dir / "evidencias" / hash_[:2] / f"{hash_}{_extensao(mime)}"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _item_ia(tipo_fonte: str, hash_: str) -> str:
    return f"{PREFIXO_ITEM}-{tipo_fonte}-{hash_[:2]}"


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30), reraise=True)
def _envia_ia(item: str, nome: str, conteudo: bytes, mime: str | None, tipo_fonte: str) -> str:
    cfg = config()
    headers = {
        "authorization": f"LOW {cfg.ia_s3_access}:{cfg.ia_s3_secret}",
        "x-archive-auto-make-bucket": "1",
        "x-archive-meta-mediatype": "data",
        "x-archive-meta-collection": "opensource_media",
        "x-archive-meta-title": f"Raio-X 2026 - evidencias ({tipo_fonte})",
        "x-archive-meta-description": "Copias de documentos publicos oficiais usados como fonte pelo Raio-X 2026.",
        "x-archive-keep-old-version": "0",
        "content-type": (mime or "application/octet-stream").split(";")[0],
    }
    r = httpx.put(f"{IA_S3}/{item}/{nome}", content=conteudo, headers=headers, timeout=180)
    r.raise_for_status()
    return f"https://archive.org/download/{item}/{nome}"


def registrar(
    conn: psycopg.Connection,
    *,
    tipo_fonte: str,
    url_original: str,
    conteudo: bytes,
    mime: str | None,
) -> str:
    """Registra (ou reaproveita) uma evidência. Retorna o id (uuid) em texto."""
    hash_ = sha256(conteudo)
    existente = conn.execute(
        "select id from evidencia where url_original = %s and sha256 = %s",
        (url_original, hash_),
    ).fetchone()
    if existente:
        return str(existente["id"])

    cache = caminho_cache(hash_, mime)
    if not cache.exists():
        cache.write_bytes(conteudo)

    url_arquivo = None
    cfg = config()
    if cfg.arquivar_evidencias and cfg.ia_s3_access and cfg.ia_s3_secret:
        try:
            url_arquivo = _envia_ia(_item_ia(tipo_fonte, hash_), cache.name, conteudo, mime, tipo_fonte)
        except Exception as e:  # noqa: BLE001 — reprocessado depois por arquivar_pendentes()
            log.warning("Falha ao arquivar %s no archive.org: %s", url_original, e)

    linha = conn.execute(
        "insert into evidencia (tipo_fonte, url_original, url_arquivo, sha256, mime, bytes) "
        "values (%s, %s, %s, %s, %s, %s) returning id",
        (tipo_fonte, url_original, url_arquivo, hash_, mime, len(conteudo)),
    ).fetchone()
    return str(linha["id"])


def arquivar_pendentes(conn: psycopg.Connection, limite: int = 500) -> int:
    """Envia ao archive.org as evidências ainda sem cópia permanente (quando o cache local existe)."""
    cfg = config()
    if not (cfg.ia_s3_access and cfg.ia_s3_secret):
        log.info("Chaves do archive.org ausentes — arquivamento ignorado")
        return 0
    pendentes = conn.execute(
        "select id, tipo_fonte, sha256, mime from evidencia where url_arquivo is null "
        "order by capturado_em limit %s",
        (limite,),
    ).fetchall()
    feitos = 0
    for ev in pendentes:
        cache = caminho_cache(ev["sha256"], ev["mime"])
        if not cache.exists():
            continue
        try:
            url = _envia_ia(_item_ia(ev["tipo_fonte"], ev["sha256"]), cache.name, cache.read_bytes(),
                            ev["mime"], ev["tipo_fonte"])
        except Exception as e:  # noqa: BLE001
            log.warning("Arquivamento falhou para %s: %s", ev["id"], e)
            continue
        conn.execute("update evidencia set url_arquivo = %s where id = %s", (url, ev["id"]))
        conn.commit()
        feitos += 1
    return feitos
