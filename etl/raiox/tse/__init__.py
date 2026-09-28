"""Subpacote com regras de negócio da coleta do TSE (DivulgaCandContas).

Mantido separado de `raiox.common` porque é específico da fonte TSE — funções puras
(sem I/O de rede/banco) que os jobs `raiox.jobs.tse_*` usam e os testes exercitam
diretamente com fixtures JSON reais (anonimizadas).
"""
