"""Identidade de pessoas: HMAC de CPF e geração de slug."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata

from .config import config


def so_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


def cpf_hmac(cpf: str | None) -> str | None:
    """HMAC-SHA256 do CPF. O CPF em claro nunca é persistido."""
    digitos = so_digitos(cpf)
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return None
    return hmac.new(config().cpf_hmac_secret.encode(), digitos.encode(), hashlib.sha256).hexdigest()


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def slugify(texto: str) -> str:
    base = sem_acento(texto).lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return re.sub(r"-{2,}", "-", base)


def formata_cnj(numero: str | None) -> str | None:
    """20 dígitos → NNNNNNN-DD.AAAA.J.TR.OOOO"""
    d = so_digitos(numero)
    if len(d) != 20:
        return None
    return f"{d[0:7]}-{d[7:9]}.{d[9:13]}.{d[13]}.{d[14:16]}.{d[16:20]}"


def titulo_nome(texto: str | None) -> str | None:
    """Converte NOME EM CAIXA ALTA para Nome em Título, respeitando preposições."""
    if not texto:
        return texto
    minusculas = {"da", "de", "do", "das", "dos", "e", "di", "du", "del"}
    partes = texto.strip().lower().split()
    return " ".join(p if (p in minusculas and i > 0) else p.capitalize() for i, p in enumerate(partes))
