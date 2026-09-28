# Retomada — job `economia` e `periodos_governo`

> Pausa geral pedida pelo dono do projeto em 27/09/2026, durante a implementação. Nenhuma
> transação de banco ficou aberta (todos os scripts usaram `with psycopg.connect(...)` /
> `with conectar()`, que fecham/commitam sozinhos). Nenhum commit git foi feito por mim
> (`git status` mostra mudanças não staged — não fiz `git add`/`git commit`).

## ⚠️ CONFLITO DETECTADO — outro processo editou os mesmos arquivos durante esta sessão

Durante a pausa, percebi que **`etl/raiox/economia/__init__.py` e `etl/raiox/economia/bcb.py`
foram reescritos por outro processo/agente** enquanto eu ainda trabalhava — não fui eu quem
fez essas mudanças. O conteúdo atual em disco de `bcb.py` é uma API **diferente** da que eu
tinha escrito (outra convenção: `PontoSGS(NamedTuple)`, função `coletar(c, codigo, *,
diario, inicio, fim)` que já devolve `(pontos, url, bruto)` prontos para evidência, reduções
chamadas `reduzir_mensal_ultimo`/`reduzir_mensal_media`, usa `orjson`+`get_bytes` em vez de
`get_json`). Testei e o `ruff check` passa nessa versão nova também, então não é um estado
quebrado — é só uma **implementação concorrente e incompatível com a que eu vinha fazendo**.

**Isso indica que pode haver mais de um agente/sessão trabalhando na mesma área
(`etl/raiox/economia/`, e possivelmente também em `raiox/jobs/periodos_governo.py` e
`dados/periodos_governo.json`, que eu não conferi de novo depois de perceber o conflito).**
Antes de continuar, **quem retomar precisa checar o estado atual real dos arquivos em disco**
(não confiar neste documento para o conteúdo exato de `bcb.py`/`__init__.py`) e decidir qual
das duas implementações manter — elas não são compatíveis (nomes de função diferentes), então
`raiox/jobs/economia.py` (ainda não escrito) só pode ser feito depois de resolver qual API de
`bcb.py` é a definitiva. `ipeadata.py` e `jobs/periodos_governo.py`, até o momento em que
percebi o conflito, ainda tinham só o conteúdo que eu escrevi (não confirmar sem reler antes
de usar).

**Atualização (checagem final antes de encerrar):** apareceu também um novo arquivo
`etl/raiox/economia/sidra.py` (não escrito por mim) — cliente SIDRA da implementação
concorrente. `ruff check raiox/economia` aponta **7 erros `E741` (nome de variável ambíguo
`l`)** nesse arquivo, linhas 73, 75, 84, 88, 98, 100, 101. Não corrigi (não é meu código e a
ordem foi pausar, não editar trabalho de outro processo). Quem retomar precisa rodar
`ruff check raiox/economia raiox/jobs/periodos_governo.py` de novo para ver o estado real no
momento em que for continuar.

## MUDANÇA DE ESCOPO EM VIGOR (decisão do dono, prevalece sobre o prompt original)

A plataforma cobre **apenas a eleição presidencial 2026**. Consequências diretas para esta área:

- O dashboard `/economia` é **só nacional**. Não há mais recorte por UF em nenhuma série
  (`desocupacao`, `caged_saldo`, etc. — os campos `por_uf` desses indicadores devem virar
  `false` na migração/seed).
- `periodos_governo` coleta **só mandatos de Presidente da República desde 1995**. **Não**
  coletar governadores — isso foi removido do escopo. Se um ex-governador for candidato a
  presidente em 2026, a trajetória dele aparece via os dados do TSE que o job
  `tse_candidaturas` (de outro agente) já está coletando — não é responsabilidade deste job.

Todo o trabalho de pesquisa/código sobre governadores feito antes dessa mudança foi
descartado do JSON final (não há resíduo em `etl/dados/periodos_governo.json`, que hoje só
tem `presidentes`).

## PRONTO

1. **`etl/dados/periodos_governo.json`** — mandatos de Presidente da República 1995–hoje,
   curados com fonte oficial (galeria de presidentes do Planalto + Senado Federal para o
   impeachment de 2016). Inclui a representação correta de:
   - Dilma Rousseff: 2011-01-01 a 2015-01-01 (1º mandato) e 2015-01-01 a 2016-05-12 (2º
     mandato, interrompido pelo afastamento).
   - Michel Temer (interino): 2016-05-12 a 2016-08-31.
   - Michel Temer (efetivo): 2016-08-31 a 2019-01-01.
   - Lula 2023-2026: `fim: null` (mandato em curso).
   Todas as 10 entradas têm `fonte_url`.

2. **`etl/raiox/jobs/periodos_governo.py`** — job completo e funcional:
   - Carrega e valida o JSON (`validar()`: rejeita `fim <= inicio` e sobreposição de mandatos
     — testado manualmente via smoke test, ainda sem pytest formal).
   - Resolve `pessoa_id` por nome civil normalizado (`normaliza()` do banco) contra a tabela
     `pessoa`, com fallback para o nome sem sufixo de status (ex.: "Michel Temer" a partir de
     "Michel Temer (interino)"). Só vincula quando o nome bate com exatamente uma pessoa.
   - Faz upsert em `periodo_governo` (chave `cargo, uf, inicio`).
   - **Ainda não foi executado de fato contra o banco local** (import e `validar()` testados
     via smoke test isolado, mas `main()` completo — que abre conexão e grava — não rodou
     ainda). Ver "Próximos passos" item 1.

3. **`etl/raiox/economia/bcb.py`** — cliente e parsing do BCB SGS, completo:
   - `coletar_serie_bruta`: pagina em janelas de 10 anos.
   - `parse_data` (dd/mm/aaaa → date), `parse_valor` (decimal BR → float).
   - `ultimo_por_mes` (para a meta Selic — documentado no docstring que é uma aproximação:
     "último valor do mês", não "vigência de cada reunião do Copom").
   - `media_por_mes` (para o dólar venda).
   - Lint limpo (`ruff check raiox/economia` passa). Smoke-testado manualmente (sem pytest
     formal ainda).

4. **`etl/raiox/economia/ipeadata.py`** — cliente do IPEADATA OData4, completo e **testado
   contra a API real**: `coletar_serie_bruta('CAGED12_SALDO12')` devolve 248 pontos mensais,
   1999-05 a 2019-12. `parse_pontos` filtra `VALVALOR: None`.

5. **Códigos de série validados contra as APIs reais** (via 3 agentes de pesquisa em paralelo
   + verificação direta minha para IBGE) — ver seção dedicada abaixo.

## EM ANDAMENTO / ESTADO EXATO

### Banco local (`postgresql://postgres:postgres@127.0.0.1:54322/postgres`)

```
pessoa            10   (outro agente — job tse_candidaturas já rodou)
indicador          9   (do seed.sql original — códigos ainda NÃO corrigidos/ajustados)
indicador_valor    0   (job economia.py não existe ainda — nunca rodou)
periodo_governo    0   (job pronto mas ainda não executado)
```

`etl_execucao` mais recentes: `exportar` (sucesso, 11), `tse_contas` (sucesso, 5),
`tse_candidaturas` (sucesso, 5) — todos de outros agentes trabalhando em paralelo.

### Arquivos criados nesta sessão

```
etl/raiox/economia/__init__.py
etl/raiox/economia/bcb.py
etl/raiox/economia/ipeadata.py
etl/raiox/jobs/periodos_governo.py
etl/dados/periodos_governo.json
docs/retomada/economia.md        (este arquivo)
```

**Ainda não criados por mim** (faltam para fechar a tarefa — mas ver aviso de conflito acima:
`etl/raiox/economia/sidra.py` já apareceu, escrito por outro processo, cobrindo parte do que
seria `ibge.py`; tem 7 erros de lint não corrigidos):

```
etl/raiox/economia/ibge.py                 # cliente SIDRA — não escrito por mim (ver sidra.py no aviso de conflito)
etl/raiox/economia/caged.py                # opcional: orquestra ipeadata + gap pós-2020
etl/raiox/jobs/economia.py                 # job principal — NÃO EXISTE AINDA
supabase/migrations/20260928030000_economia_indicadores.sql   # não criada
etl/tests/test_economia_bcb.py
etl/tests/test_economia_ibge.py
etl/tests/test_economia_ipeadata.py (ou test_economia_caged.py)
etl/tests/test_periodos_governo.py
etl/tests/fixtures/economia/*.json
```

`supabase/seed.sql` ainda não foi editado (os códigos de `indicador` lá são os originais,
com `por_uf=true` em `desocupacao` e `caged_saldo` — **precisa mudar para `false`** por causa
da mudança de escopo).

### Lint + testes (última rodada, literalmente antes de encerrar)

```
cd etl && PYTHONUTF8=1 python -m uv run ruff check raiox/economia raiox/jobs/periodos_governo.py
→ Found 7 errors (todos E741 em raiox/economia/sidra.py, arquivo de outro processo — ver aviso de conflito)
```

`raiox/jobs/periodos_governo.py` sozinho está limpo (1 erro B905 que eu tinha, já corrigido:
`zip(..., strict=False)`). Os 7 erros atuais são todos em `sidra.py`, que não é meu.

```
cd etl && PYTHONUTF8=1 python -m uv run pytest
→ collected 0 items (nenhum arquivo de teste existe ainda em etl/tests/)
```

Lint em `raiox/jobs/tse_candidaturas.py`, `raiox/jobs/tse_contas.py`,
`raiox/tse/mapeamento.py` tem 10 erros/avisos pré-existentes — **não são meus, são de outro
agente** (tse_*), não mexi nesses arquivos.

## Códigos de série — confirmados contra API real

| Indicador | Fonte | Código/params confirmados | Status |
|---|---|---|---|
| IPCA mensal | BCB SGS | `433` | ✅ confirmado (últimos pontos batem: 08/2026 = -0,32%) |
| IPCA 12m | BCB SGS | `13522` | ✅ confirmado (08/2026 = 4,22%) |
| Meta Selic | BCB SGS | `432`, diária (reduzir com `ultimo_por_mes`) | ✅ confirmado, degrau em 13,75% out-nov/2026 |
| DBGG % PIB | BCB SGS | `13762`, mensal | ✅ confirmado (07/2026 = 82,56%) |
| Dólar venda | BCB SGS | `1`, diária (reduzir com `media_por_mes`) | ✅ confirmado |
| Resultado primário 12m % PIB | BCB SGS | `5793` | ✅ **CONFIRMADO CORRETO** — a suspeita do prompt original de que 5793 estaria errado **não procede**. Fonte: dadosabertos.bcb.gov.br/dataset/5793 — "NFSP sem desvalorização cambial (% PIB) - Fluxo acumulado em 12 meses - Resultado primário - Total - Setor público consolidado". Valores reais 02–07/2026: 0,41 a 1,19% PIB. **Nenhuma migração necessária para este código.** |
| Desocupação | IBGE SIDRA | tabela `4099`, variável `4099` ("Taxa de desocupação..."), nível `n1` (Brasil — UF não é mais escopo) | ✅ confirmado por mim diretamente: `apisidra.ibge.gov.br/values/t/4099/n1/all/v/4099/p/last%206?formato=json` devolve 6 trimestres plausíveis (7,0% a 5,4%, 1º tri/2025 a 2º tri/2026). Período vem como `D3C` = `AAAAQQ` (ex.: `202602` = 2º trimestre de 2026) — **não é `AAAAMM`**, precisa de parser específico (mapear trimestre → data, ex.: usar o último mês do trimestre). |
| PIB var. acumulada 4 trimestres | IBGE SIDRA | tabela `5932`, variável `6562` ("Taxa acumulada em quatro trimestres"), classificação `11255` categoria `90707` ("PIB a preços de mercado") | ✅ confirmado por mim diretamente: `.../t/5932/n1/all/v/6562/p/last%204/c11255/90707?formato=json` devolve 1,9% a 2,7% (3º tri/2025 a 2º tri/2026), plausível. |
| CAGED saldo (pré-2020) | IPEADATA OData4 | série `CAGED12_SALDO12` | ✅ confirmado contra API real: 248 pontos mensais, 1999-05 a 2019-12. Metadado da própria fonte confirma a quebra: `SERSTATUS: "I"`, `SERCOMENTARIO: "...Série descontinuada pela fonte."` — **citar isso como aviso de quebra metodológica no site.** |
| CAGED saldo (Novo CAGED, pós-2020) | — | **sem fonte machine-readable estável dentro das restrições do projeto** | ❌ **GAP não resolvido** — ver pendência 1 abaixo. |

## PENDÊNCIAS (decisão do dono ou trabalho adicional necessário)

1. **Novo CAGED (2020+) não tem API/arquivo agregado estável e automatizável** dentro das
   restrições (`uv add` proibido, sem lib de `.7z`, FTP do PDET só tem microdados brutos em
   `.7z`, e o XLSX agregado mensal que existia numa URL fixa (`pdet.mte.gov.br/images/
   Novo_CAGED/{ano}/{aaaamm}/3-tabelas.xlsx`) está 404 — o MTE passou a distribuir isso por
   link do Google Drive que muda todo mês). Duas opções para o dono decidir:
   - (a) Publicar `caged_saldo` só até dez/2019 (IPEADATA), com aviso de quebra/série
     encerrada — dashboard fica sem o dado mais relevante (últimos anos).
   - (b) Investir em processar manualmente o XLSX do Drive todo mês fora do ETL automatizado
     (fere a promessa de job idempotente/cron do PLANO_FINAL §10), ou negociar suporte a
     `.7z` (precisaria de `uv add py7zr` ou equivalente, hoje proibido).
   Nenhuma decisão foi tomada — o job `economia.py` (ainda não escrito) deveria, no mínimo,
   publicar a parte pré-2020 e deixar registrado no `etl_execucao.detalhes` que o trecho
   2020+ está ausente por falta de fonte, sem falhar o portão de qualidade por causa disso
   (a recência exigida para as outras séries não deveria se aplicar a `caged_saldo`).

2. **`periodos_governo.py` nunca rodou de fato contra o banco** — falta executar
   `python -m raiox periodos_governo` e conferir contagens/vínculos de `pessoa_id` (agora que
   `pessoa` já tem 10 linhas de outro agente).

3. `supabase/seed.sql` ainda reflete o schema antigo (`por_uf=true` em 2 indicadores) — precisa
   de ajuste + migração espelhando isso no banco local.

## PRÓXIMOS PASSOS (na ordem, com comandos exatos)

1. **Rodar `periodos_governo` pela primeira vez** e conferir:
   ```
   cd etl && PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -m raiox periodos_governo
   ```
   Depois checar no banco: `select cargo, nome, inicio, fim, pessoa_id from periodo_governo order by inicio;`
   (esperar 10 linhas, `pessoa_id` provavelmente `null` na maioria — só 10 pessoas no banco
   ainda, prováveis candidatos de 2026, não necessariamente com o nome civil de FHC/Lula/etc.)

2. **Escrever `etl/raiox/economia/ibge.py`** — cliente SIDRA genérico, incluindo parser de
   período `AAAAQQ` (ver códigos confirmados acima). Modelo: espelhar a estrutura de
   `bcb.py` (`coletar`, `parse_periodo`, remover linha de cabeçalho do SIDRA — a resposta
   sempre traz um dict de cabeçalho no índice 0 com `NC: "Nível Territorial (Código)"` etc.,
   que precisa ser descartado).

3. **Escrever `etl/raiox/jobs/economia.py`**:
   - Para cada indicador da tabela acima (exceto Novo CAGED pós-2020, que fica pendente),
     baixar desde 1995 (ou desde o início disponível da série), aplicar as reduções
     (`ultimo_por_mes` para Selic, `media_por_mes` para dólar), validar contra o metadado
     esperado (nome/unidade — usar `ex.exige(...)` do `Execucao` para abortar com mensagem
     clara se não bater) e fazer upsert em `indicador_valor` com `uf='BR'` sempre (não há
     mais recorte por UF).
   - Registrar `evidencia.registrar(conn, tipo_fonte='bcb'|'ibge'|'caged', url_original=...,
     conteudo=<payload bruto serializado>, mime='application/json')` uma vez por série por
     execução.
   - Atualizar `indicador` (nome/unidade/codigo_fonte/url_fonte) via upsert, incluindo o
     ajuste do `codigo_fonte`/`url_fonte` do SIDRA (tabela+variável+classificação, não só a
     tabela) e do CAGED (deixar claro no `descricao` que é pré-2020, fonte IPEADATA, com
     aviso de quebra).
   - Portões de qualidade: série não vazia; último ponto dentro do prazo esperado por
     periodicidade (IPCA ≤70 dias, mensal ≤60 dias, trimestral ≤120 dias — exceto
     `caged_saldo`, que fica sem esse gate enquanto só tiver dados até 2019); `ipca_mensal`
     dentro de `[-5, 30]`.

4. **Criar a migração** `supabase/migrations/20260928030000_economia_indicadores.sql`:
   ```sql
   update indicador set por_uf = false where id in ('desocupacao', 'caged_saldo');
   -- + ajustar codigo_fonte/url_fonte/descricao dos indicadores SIDRA e CAGED conforme a
   --   tabela de códigos confirmados acima.
   ```
   Aplicar no banco local via psycopg (não usar `supabase db reset`). Depois **espelhar as
   mesmas mudanças em `supabase/seed.sql`** (instrução explícita do projeto: toda mudança de
   seed via migração + seed.sql atualizado).

5. **Escrever os testes** (`etl/tests/test_economia_bcb.py`, `test_economia_ibge.py`,
   `test_economia_ipeadata.py`, `test_periodos_governo.py`) com fixtures em
   `etl/tests/fixtures/economia/` — usar como base os payloads reais já capturados nesta
   sessão (amostras estão nos comandos acima, ex.: os JSONs de `apisidra.ibge.gov.br` e
   `ipeadata.gov.br` mostrados na tabela de códigos). Cobrir: parse SGS (data + decimal),
   agregação mensal (Selic/dólar), parse SIDRA (período `AAAAQQ`), validação de metadados,
   validação de `periodos_governo.json` (sobreposição, datas coerentes — já há a função
   `validar()` pronta em `periodos_governo.py`, só falta o arquivo de teste chamando-a com
   casos válidos/inválidos).

6. **Rodar os dois jobs de verdade** e coletar números reais para o relatório final:
   ```
   cd etl && PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -m raiox economia
   cd etl && PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -m raiox periodos_governo
   cd etl && PYTHONUTF8=1 python -m uv run pytest
   cd etl && PYTHONUTF8=1 python -m uv run ruff check raiox tests
   ```
   Depois consultar `indicador_valor` (contagem por indicador, último valor/data) e
   `periodo_governo` para montar o relatório final pedido (números reais, não estimativas).

## Notas de pesquisa já feitas (não repetir)

- TSE DivulgaCandContas **não tem dados da eleição de 2002** nem de nenhum ano antes de 2006
  (`/eleicao/ordinarias` retorna só 13 pleitos, o mais antigo é 2006) — irrelevante agora
  que governadores saíram do escopo, mas fica registrado caso o escopo volte a mudar.
- Toda a pesquisa de substituições de governadores (RJ, SP, AL, RN, RR) feita antes da
  mudança de escopo **não é mais necessária** — não foi persistida em nenhum arquivo de
  dados final (o JSON atual só tem `presidentes`).
