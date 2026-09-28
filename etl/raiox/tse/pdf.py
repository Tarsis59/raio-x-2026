"""Extração de texto de PDFs (certidões, propostas de governo) com `pypdfium2`.

`pypdfium2` extrai texto por linha visual (sem noção de parágrafo). A normalização abaixo
reconstrói parágrafos com uma heurística simples e documentada:
  * linha em branco = quebra de parágrafo (preservada como `\n\n`);
  * linha terminada em hífen seguida de letra minúscula = hifenização de fim de linha
    (palavra quebrada entre linhas) -> junta as duas partes sem hífen e sem espaço;
  * demais linhas consecutivas (sem linha em branco entre elas) = mesmo parágrafo,
    unidas por espaço.
Não é uma reconstrução perfeita de layout (isso exigiria as coordenadas dos blocos de
texto), mas preserva o essencial para citação literal por IA: nenhuma palavra é alterada,
só a pontuação de junção de linha/parágrafo.
"""

from __future__ import annotations

import hashlib
import re

import pypdfium2 as pdfium

SEPARADOR_PAGINA = "\f"


def normalizar_texto(bruto: str) -> str:
    linhas = bruto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    paragrafos: list[str] = []
    atual: list[str] = []

    def fecha_paragrafo() -> None:
        if atual:
            paragrafos.append(" ".join(atual))
            atual.clear()

    for linha in linhas:
        linha_limpa = linha.strip()
        if not linha_limpa:
            fecha_paragrafo()
            continue
        if atual and atual[-1].endswith("-") and re.match(r"^[a-zà-ú]", linha_limpa):
            atual[-1] = atual[-1][:-1] + linha_limpa
        else:
            atual.append(linha_limpa)
    fecha_paragrafo()
    return "\n\n".join(paragrafos)


def extrair_paginas(conteudo_pdf: bytes) -> list[str]:
    """Retorna o texto normalizado de cada página (índice 0 = página 1)."""
    doc = pdfium.PdfDocument(conteudo_pdf)
    try:
        paginas = []
        for i in range(len(doc)):
            pagina = doc.get_page(i)
            try:
                textpage = pagina.get_textpage()
                try:
                    bruto = textpage.get_text_range()
                finally:
                    textpage.close()
                paginas.append(normalizar_texto(bruto))
            finally:
                pagina.close()
        return paginas
    finally:
        doc.close()


def hash_texto(paginas: list[str]) -> str:
    conteudo = SEPARADOR_PAGINA.join(paginas).encode("utf-8")
    return hashlib.sha256(conteudo).hexdigest()


def pdf_sem_texto(paginas: list[str]) -> bool:
    """True se nenhuma página tem texto extraível (indício de PDF escaneado — precisa de OCR)."""
    return all(not p.strip() for p in paginas)
