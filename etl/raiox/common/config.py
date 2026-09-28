"""Configuração central do ETL (lida do ambiente / .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

RAIZ_REPO = Path(__file__).resolve().parents[3]
load_dotenv(RAIZ_REPO / ".env")

ELEICAO_2026 = 20322002026
ANO_ELEICAO = 2026


@dataclass(frozen=True)
class Config:
    database_url: str
    cpf_hmac_secret: str
    anthropic_api_key: str | None
    ia_s3_access: str | None  # Internet Archive (archive.org) — chaves S3 gratuitas
    ia_s3_secret: str | None
    google_factcheck_key: str | None
    portal_transparencia_key: str | None
    datajud_key: str | None
    cache_dir: Path
    arquivar_evidencias: bool  # False em dev para não publicar no archive.org


@lru_cache
def config() -> Config:
    cache = Path(os.getenv("RAIOX_CACHE_DIR", RAIZ_REPO / "etl" / ".cache"))
    cache.mkdir(parents=True, exist_ok=True)
    return Config(
        database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"),
        cpf_hmac_secret=os.getenv("CPF_HMAC_SECRET", "dev-somente-local"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        ia_s3_access=os.getenv("IA_S3_ACCESS_KEY"),
        ia_s3_secret=os.getenv("IA_S3_SECRET_KEY"),
        google_factcheck_key=os.getenv("GOOGLE_FACTCHECK_API_KEY"),
        portal_transparencia_key=os.getenv("PORTAL_TRANSPARENCIA_API_KEY"),
        # Chave pública divulgada pelo CNJ na documentação do DataJud (pode ser rotacionada pelo CNJ).
        datajud_key=os.getenv("DATAJUD_API_KEY"),
        cache_dir=cache,
        arquivar_evidencias=os.getenv("RAIOX_ARQUIVAR", "0") == "1",
    )
