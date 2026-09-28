"""Núcleo de IA do Raio-X 2026 — guardrails determinísticos + integração com a API Anthropic.

Escopo (decisão do dono, 2026-09-27): a plataforma cobre apenas os 14 candidatos a
Presidente 2026 (titulares e vices). Todos os jobs deste subpacote filtram por
``candidatura.cargo_codigo = 1`` e ``candidatura.ano = raiox.common.config.ANO_ELEICAO``.

Nada aqui publica dado nenhum sozinho: todo registro sai como ``rascunho``/``em_revisao`` e
depende da regra dos 4 olhos já imposta pelo banco (ver `valida_quatro_olhos` no esquema).
"""
