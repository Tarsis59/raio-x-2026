# Fonte: TSE — DivulgaCandContas (mapeada em 27/09/2026)

## Acesso
- Os domínios `divulgacandcontas.tse.jus.br`, `cdn.tse.jus.br` e `dadosabertos.tse.jus.br` ficam atrás do **Akamai Bot Manager**.
  - `curl`, `requests`/`httpx` e `Invoke-WebRequest` recebem **403 Access Denied**, mesmo a partir de IP brasileiro.
  - **Chromium real (Playwright) funciona.** A coleta usa `page.evaluate(fetch(...))` dentro de uma aba já aberta no domínio.
- Base: `https://divulgacandcontas.tse.jus.br/divulga/rest/v1`
- Eleição Geral 2026: `idEleicao = 20322002026`, data `2026-10-04`.

## Endpoints
| Uso | Método e caminho |
|---|---|
| Eleições | `GET /eleicao/ordinarias` |
| Lista por cargo/UF | `GET /candidatura/listar/{ano}/{UF\|BR}/{idEleicao}/{cargo}/candidatos` |
| Detalhe | `GET /candidatura/buscar/{ano}/{UF\|BR}/{idEleicao}/candidato/{idCandidato}` |
| Contas (consolidado) | `GET /prestador/consulta/{idEleicao}/{ano}/{UF}/{cargo}/{nrPartido}/{nrCandidato}/{idCandidato}` |
| Arquivo (PDF) | `GET /divulga/rest/arquivo/doc/{idArquivo}` (fora de `/v1`) |
| Foto | valor de `fotoUrl` (`/divulga/rest/arquivo/img/{idEleicao}/{idCandidato}/{UF}`), usar só se `fotoUrlPublicavel = true` |

Códigos de cargo: 1 Presidente · 3 Governador · 5 Senador · 6 Dep. Federal · 7 Dep. Estadual · 8 Dep. Distrital (vices e suplentes vêm dentro do titular).

## Volume em 2026 (27/09)
Presidente 14 · Governador 201 · Senador 318 · Dep. Federal 7.803 · Dep. Estadual 11.293 · Dep. Distrital 433 = **20.062**.
A listagem completa (131 chamadas em paralelo) leva cerca de 5 s.

## Campos do detalhe (principais)
- Identificação: `id`, `nomeUrna`, `nomeCompleto`, `numero`, `partido{numero,sigla,nome}`, `nomeColigacao`, `composicaoColigacao`, `cargo{codigo,nome}`, `ufCandidatura`.
- Pessoais: `dataDeNascimento`, `descricaoSexo`, `descricaoCorRaca`, `grauInstrucao`, `ocupacao`, `sgUfNascimento`, `nomeMunicipioNascimento`, `descricaoEstadoCivil`.
- **`cpf` e `tituloEleitor` vêm abertos → NUNCA publicar.** Guardar só `HMAC-SHA256(cpf, segredo)` para resolver identidade entre eleições.
- Situação: `descricaoSituacao` (Deferido/Indeferido…), `descricaoTotalizacao` (Concorrendo/Eleito…), `st_REELEICAO`, `motivos`.
- Processos TSE: `numeroProcesso` (registro), `numeroProcessoDrap`, `numeroProcessoPrestContas` (20 dígitos, formato CNJ).
- `bens[]`: `ordem`, `descricaoDeTipoDeBem`, `descricao`, `valor`, `dataUltimaAtualizacao`; `totalDeBens`.
- `gastoCampanha1T` e `gastoCampanha2T`: limites de gasto.
- `vices[]`: vice ou suplentes (`sq_CANDIDATO`, `nm_URNA`, `urlFoto`).
- `sites[]`: redes sociais declaradas.
- `eleicoesAnteriores[]`: `nrAno`, `id`, `idEleicao`, `sgUe`, `cargo`, `partido`, `situacaoTotalizacao` → usar para puxar os bens e cargos históricos (mesmo endpoint de detalhe com o ano e a eleição antigos).
- `arquivos[]`: `idArquivo`, `nome`, `codTipo`, `anonimizado`.

## codTipo de arquivos
| codTipo | Documento |
|---|---|
| 5 | Proposta de Governo (Presidente e Governador) |
| 11 | Certidão criminal — Justiça Federal 1º grau |
| 12 | Certidão criminal — Justiça Federal 2º grau |
| 13 | Certidão criminal — Justiça Estadual 1º grau |
| 14 | Certidão criminal — Justiça Estadual 2º grau |
| 15 | Certidão criminal — foro por prerrogativa de função |
| 1 | Certidão (genérica) |

O arquivo pode responder 404 enquanto aguarda anonimização. Nesse caso, tentar de novo no próximo ciclo.

## Links públicos do site do TSE (SPA Angular)
- Perfil do candidato: `https://divulgacandcontas.tse.jus.br/divulga/#/candidato/{regiao}/{UF}/{idEleicao}/{idCandidato}/{ano}/{sgUe}`.
  Validado com `regiao=BR` para Presidente (`.../candidato/BR/BR/20322002026/280002551975/2026/BR`).
- Subrotas do perfil: `/prestacao/receitas`, `/prestacao/despesas`, `/extratos`, `/historico`, `/nfes`, `/concentracao/despesas`, `/viceSuplente`.
- Comparativo: `#/comparativo/candidatos/{idEleicao}/{abrangencia}/{ano}`.
