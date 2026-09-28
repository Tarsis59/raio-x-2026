# Retomada — IA / Justiça / Checagens (área: `etl/raiox/ia/`, `jobs/ia_*`, `jobs/datajud.py`, `jobs/factcheck.py`, `jobs/ifcn.py`)

Pausa solicitada pelo dono em 27/09/2026 durante o levantamento inicial. Nenhuma transação de
banco ficou aberta (todas as leituras usaram `with conectar()`, que fecha/commita ao sair do
bloco) e nenhuma chamada de rede/API ficou pendente. Nada foi commitado (não há repositório git
inicializado na raiz — ver nota em "Ambiente" abaixo).

## Mudança de escopo já incorporada ao plano (decisão do dono, prevalece sobre o `PLANO_FINAL.md`)

A plataforma cobre **apenas os 14 candidatos a Presidente 2026 (titulares e vices)**:

- `ia_propostas` / `ia_bussola` (novo job, ver abaixo): só os planos de governo dos 14
  presidenciáveis **titulares** (`candidatura.cargo_codigo = 1 and candidatura.titular = true`;
  o vice não protocola plano de governo próprio).
- `ia_certidoes` / `datajud`: certidões e processos de titulares **e vices** da chapa
  presidencial (`candidatura.cargo_codigo = 1`, titular ou vice).
- `factcheck`: só presidenciáveis e vices (mesmo filtro de `factcheck`/`ifcn`).
- Novo job **`ia_bussola`**: para cada `quiz_pergunta` ativa e cada presidenciável titular,
  sugerir `valor` (-2..+2 ou `null`) em `quiz_posicao` com `fonte_tipo='proposta'`,
  `status_revisao='em_revisao'`, reaproveitando os `trechos` **já validados** de `proposta`
  (não é feita uma nova chamada de citação sobre o PDF — o modelo só pode escolher entre os
  trechos que a `ia_propostas` já validou literalmente, nunca inventar um novo; se o trecho
  devolvido não bater exatamente com um dos fornecidos, a posição vira `null` e é descartada).
  `justificativa` (NOT NULL no schema) sempre carrega a citação literal + página, ou a frase
  neutra "O plano de governo protocolado no TSE não trata deste tema." quando `valor is null`.
  O `on conflict` do upsert em `quiz_posicao` tem `where quiz_posicao.fonte_tipo = 'proposta'`
  para nunca sobrescrever uma posição curada a partir de voto/declaração.

## PRONTO

- Lido e mapeado todo o contexto necessário: `PLANO_FINAL.md` (§2, §2.2, §2.3, §7),
  `supabase/migrations/20260928000000_esquema_inicial.sql`, `supabase/seed.sql`,
  `packages/core/src/contrato.ts`, `docs/fontes/TSE.md`, `etl/raiox/common/*` (não alterado).
- Skill `claude-api` carregada e lida (Python): modelos/preços confirmados na tabela cacheada
  da skill (2026-06-24) — `claude-sonnet-5` ($2/$10 por MTok) e `claude-haiku-4-5` ($1/$5 por
  MTok, **sem** sufixo de data — a skill proíbe explicitamente `claude-haiku-4-5-20251001`).
  Batches = 50% de desconto. Citations em documento `text` devolvem `char_location`
  (`start_char_index`/`end_char_index`), não página — por isso o desenho abaixo mapeia offset
  de caractere → página nós mesmos (concatenamos as páginas com offsets conhecidos).
- Algoritmo do dígito verificador CNJ (módulo 97, ISO 7064 MOD 97-10, Res. CNJ 65/2008)
  **confirmado contra um número real e público**: `5063130-17.2016.4.04.7000` (TRF4, caso
  amplamente noticiado) → DV calculado bate exatamente com `17`. Fórmula: para
  `N7+AAAA+J+TR+OOOO` (18 dígitos), `dv = 98 - ((N7AAAAJTROOOO * 100) % 97)`.
- Mapeamento segmento(J)+tribunal(TR) → alias de índice do DataJud **confirmado via wiki real**
  (`datajud-wiki.cnj.jus.br/api-publica/endpoints/`, obtida com sucesso via proxy de leitura
  depois que o fetch direto teve 403 — mesma proteção anti-bot do TSE): lista completa de
  aliases (`trf1..6`, `trt1..24`, `tj{uf}`, `tjdft`, `tre-{uf}`, `tre-dft`, `tjmmg`, `tjmrs`,
  `tjmsp`, `stj`, `stm`, `tse`, `tst`) e a **chave pública vigente**:
  `cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==` (documentada como sujeita a
  rotação pelo CNJ a qualquer momento — o job deve sempre preferir `config().datajud_key`
  quando definida, com esse valor só como *fallback* documentado no código, nunca hardcoded
  como definitivo).
- Ordem oficial de UF usada pelo CNJ nos segmentos 6/8/9 (`ac,al,am,ap,ba,ce,df,es,go,ma,mg,ms,
  mt,pa,pb,pe,pi,pr,rj,rn,ro,rr,rs,sc,se,sp,to`) **verificada por 3 casos reais independentes**
  (TJSP com TR=26→SP, e os aliases `tjmmg`/`tjmrs`/`tjmsp` batendo com MG=11/RS=23/SP=26).
- Desenho completo (no papel, revisado neste documento) de todos os módulos e jobs — ver
  "PRÓXIMOS PASSOS" para a lista exata de arquivos e a lógica de cada um.
- Implementados e **com lint limpo** (`ruff check raiox/ia` → *All checks passed!*):
  - `etl/raiox/ia/__init__.py` — docstring do subpacote e da mudança de escopo.
  - `etl/raiox/ia/validador.py` — validador literal determinístico completo:
    `normaliza()` (NFKC + aspas/travessões tipográficos + hifenização de quebra de linha +
    colapso de espaços), `trecho_existe()`, `pagina_do_trecho()`, `valida_trechos()` (com
    callback `on_descarte` para log/auditoria). **Sem testes ainda** (ver pendências).
  - `etl/raiox/ia/neutralidade.py` — linter de neutralidade completo: `LIMITE_CARACTERES=280`,
    dicionário `TERMOS_PROIBIDOS` (~35 radicais documentados, com a razão de cada termo
    inclusive os "juízo de resultado" como eficaz/eficiente e os que julgam a pessoa como
    corrupto/incompetente), `termos_encontrados()`, `menciona()` (outros
    candidatos/partidos/coligações, ignora siglas de 1-2 letras para evitar falso-positivo),
    `avalia_resumo()` → `ResultadoNeutralidade(aprovado, motivos)`. **Sem testes ainda**.

## EM ANDAMENTO / NÃO INICIADO (nenhum outro arquivo da minha área existe ainda)

Nada mais da minha área foi escrito. Confirmado por busca no disco antes de pausar:
`etl/raiox/ia/` só tem os 3 arquivos acima; não existe `cnj.py`, `datajud_tribunais.py`,
`anthropic_cliente.py`, `propostas.py`, `certidoes.py`, `bussola.py`; não existem
`etl/raiox/jobs/ia_propostas.py`, `ia_certidoes.py`, `ia_bussola.py`, `datajud.py`,
`factcheck.py`, `ifcn.py`; não existe nenhuma migração `20260928040000_ia_*.sql`; não existe
nenhum `etl/tests/test_ia_*` / `test_cnj*` / `test_datajud*` / `test_factcheck*` nem
`etl/tests/fixtures/ia/`; não existe `docs/metodologia/ia.md`.

### Estado do banco local (`postgresql://postgres:postgres@127.0.0.1:54322/postgres`) agora

Outro agente está enchendo `candidatura`/`arquivo_tse` em paralelo — conferido pela última vez
nesta pausa:

| tabela | linhas |
|---|---|
| `candidatura` | 10 |
| `arquivo_tse` | 51 |
| `arquivo_pagina` | **0** — ainda sem texto extraído de nenhum PDF |
| `tema` | 9 (seed) |
| `agencia_checagem` | 7 (seed) |
| `processo` | 0 |
| `proposta` | 0 |
| `certidao_analise` | 0 |
| `checagem` | 0 |
| `quiz_pergunta` | 0 |

**Nenhum job de IA pode processar dado real ainda** porque `arquivo_pagina` está vazia (é a
tabela de onde vem o texto por página usado pelo validador literal) e `quiz_pergunta` também
está vazia (bússola depende de perguntas cadastradas, que não são desta área). `ia_certidoes`
em modo determinístico já poderia rodar sobre `arquivo_tse` cod_tipo 11-15/1 assim que
`arquivo_pagina` tiver linhas para esses arquivos.

## PRÓXIMOS PASSOS (ordem exata para retomar sem erro)

1. **Reler este arquivo e reconferir a contagem das tabelas acima** (comando abaixo) antes de
   escrever qualquer coisa — se `arquivo_pagina` continuar 0, os jobs ainda vão rodar "0
   registros" contra o banco real, mas o código e os testes com fixtures devem ser concluídos
   de qualquer forma (não dependem do banco populado).
   ```bash
   cd "/c/Users/User/Downloads/Projeto Eleicoes 2026/etl"
   PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -c "
   import psycopg
   from psycopg.rows import dict_row
   conn = psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres', row_factory=dict_row)
   for t in ['candidatura','arquivo_tse','arquivo_pagina','tema','processo','proposta','certidao_analise','checagem','quiz_pergunta']:
       print(t, conn.execute(f'select count(*) c from {t}').fetchone()['c'])
   "
   ```

2. **`etl/raiox/ia/cnj.py`** — dígito verificador + parsing:
   - `digitos_verificadores(n7, aaaa, j, tr, oooo) -> str` (fórmula confirmada acima).
   - `decompoe(numero) -> dict|None` (aceita formatado `NNNNNNN-DD.AAAA.J.TR.OOOO` ou 20
     dígitos corridos).
   - `valido(numero) -> bool`, `formata(numero) -> str|None`.
   - `extrai_numeros(texto) -> list[str]` (regex ampla + `formata()` para normalizar cada
     achado; deduplicar preservando ordem).
   - Teste: usar `5063130-17.2016.4.04.7000` (real, confirmado) como caso válido; variações
     com um dígito trocado como inválidas; e alguns números sintéticos gerados pela própria
     `digitos_verificadores()` para cobrir mais casos (round-trip).

3. **`etl/raiox/ia/datajud_tribunais.py`** — mapear (J, TR) → alias `api_publica_<alias>` e
   URL completa. Usar a lista de aliases e a ordem de UF já confirmadas neste documento.
   `alias_indice("1", ...) -> None` (STF não está no DataJud — comentar o motivo, citando
   PLANO_FINAL.md §2.2). Testar STJ (`3`/`00`→`stj`), TRF (`4`/`03`→`trf3`), TJ (`8`/`26`→
   `tjsp`, `8`/`07`→`tjdft`), TRE (`6`/`26`→`tre-sp`, `6`/`07`→`tre-dft`), Justiça Militar
   estadual (`9`/`11`→`tjmmg`), segmento desconhecido → `None`.

4. **`etl/raiox/ia/anthropic_cliente.py`** — constantes de modelo/preço e helpers:
   ```python
   MODELO_EXTRACAO = "claude-sonnet-5"       # ia_propostas, ia_bussola (citações)
   MODELO_CLASSIFICACAO = "claude-haiku-4-5"  # ia_certidoes (casos ambíguos), factcheck (matching)
   PRECOS = {"claude-sonnet-5": {"input": 2.00, "output": 10.00},
             "claude-haiku-4-5": {"input": 1.00, "output": 5.00}}  # US$/MTok
   DESCONTO_BATCH = 0.5
   ```
   `custo_usd(modelo, tokens_entrada, tokens_saida, *, batch=False)`, `cliente()` (lazy
   `import anthropic`; `anthropic.Anthropic(api_key=config().anthropic_api_key)`),
   `sem_chave() -> bool` (`not config().anthropic_api_key`), `heuristica_tokens(texto) ->
   int` (fallback sem API: `max(1, len(texto)//4)`, documentar que é heurística — NUNCA usar
   tiktoken, ver skill `claude-api` → `shared/token-counting.md`).

5. **`etl/raiox/ia/propostas.py`** (núcleo, sem I/O de rede — testável com cliente mockado) +
   **`etl/raiox/jobs/ia_propostas.py`** (CLI fino: `--limite`, `--candidatura`, `--batch`,
   `--estimar`). Filtro: `candidatura.cargo_codigo = 1 and candidatura.titular = true and
   candidatura.ano = raiox.common.config.ANO_ELEICAO`, `arquivo_tse.cod_tipo = 5`,
   `status='baixado'`, `texto_sha256 is not null`. PDF > 100 páginas → marcar para revisão
   manual (log + `ex.detalhes["marcados_revisao_manual"]`), não chamar a API. Desenho da
   extração (revisado e fechado neste documento):
   - Concatenar `arquivo_pagina.texto` por página com offsets conhecidos
     (`monta_documento_texto`/`pagina_do_offset`).
   - Um único `client.messages.create` por arquivo cobrindo todos os temas pendentes daquele
     arquivo (eficiência de custo), `content=[{"type":"document","source":{"type":"text",
     "media_type":"text/plain","data":doc_texto},"citations":{"enabled":true},"title":...},
     {"type":"text","text":instrucao_usuario}]`; `system` com as 6 regras absolutas (nunca
     opinar, sempre 3ª pessoa, sempre citar literal, etc.); modelo `claude-sonnet-5`,
     `thinking={"type":"disabled"}` + `temperature=0` (Sonnet 5 aceita `disabled` — ver
     tabela da skill; NÃO usar `budget_tokens`, está removido nesse modelo).
   - Formato de resposta (texto livre, não JSON — citations é incompatível com
     `output_config.format`): blocos `###TEMA <id>` / `SEM_MENCAO: true|false` / `RESUMO: ...`
     / `TRECHO: "..."` (0+ linhas) / `###FIM`. Parser via regex (`_RE_BLOCO`, `_RE_TRECHO`).
   - Página de cada `TRECHO`: 1º tenta casar com uma citação devolvida pela API (`cited_text`
     normalizado == trecho normalizado) e mapear `start_char_index` → página via os offsets;
     se não achar citação correspondente, varre todas as páginas com
     `validador.pagina_do_trecho` como *fallback*. **Em qualquer caso**, confirma no final com
     `validador.trecho_existe(trecho, paginas[pagina])` antes de aceitar — é a autoridade
     final, nunca confiar cegamente na citação da API.
   - Regra especial (⚠️ já decidida, não reabrir): se o modelo disse `SEM_MENCAO: false` mas
     **nenhum** trecho sobra depois da validação, a proposta inteira daquele tema é
     **descartada** (não grava `sem_mencao=true`, porque isso afirmaria algo não verificado)
     — só loga um aviso. `sem_mencao=true` só é gravado quando o próprio modelo disse isso.
   - Neutralidade: `neutralidade.avalia_resumo(resumo, proibidos=nomes_outros_candidatos)`;
     se reprovar, até 2 tentativas de regeneração (`regenera_resumo`, nova chamada pequena
     reaproveitando o cache do documento) antes de descartar o tema inteiro.
   - Idempotência **sem migração nova**: antes de reprocessar um tema, checar
     `select 1 from proposta p join arquivo_tse a on a.id=p.arquivo_id where
     p.candidatura_id=%s and p.tema_id=%s and a.texto_sha256=%s` — se existir, pular (o hash
     já está em `arquivo_tse.texto_sha256`, não precisa coluna nova em `proposta`).
   - `--estimar`: soma tokens de entrada (heurística ou `count_tokens` se houver chave) de
     todos os arquivos/temas pendentes (agora só ~14 planos, todos presidenciáveis) + heurística
     de ~220 tokens de saída por tema, imprime JSON com o custo total em US$
     (`anthropic_cliente.custo_usd`). Deve funcionar **sem chave** (heurística).
   - Sem chave configurada: job real (fora do `--estimar`) loga aviso claro e sai com sucesso
     e 0 registros (não é falha).

6. **`etl/raiox/ia/bussola.py`** (núcleo) + **`etl/raiox/jobs/ia_bussola.py`** — job NOVO
   pedido na mudança de escopo. Não chama a API sobre o PDF de novo: para cada candidatura
   titular presidencial, busca as `proposta` já gravadas (por tema) e as `quiz_pergunta`
   ativas; um único `client.messages.create` (Sonnet 5, texto simples, sem citations — os
   trechos fornecidos já são de confiança) por candidatura, listando cada pergunta
   (id/texto/contexto/argumento_favor/argumento_contra/tema) e, para o tema dela, o resumo +
   `trechos` já validados da proposta (ou "sem menção"). Resposta no mesmo estilo de blocos:
   `###PERGUNTA <id>` / `VALOR: -2|-1|0|1|2|null` / `TRECHO: <cópia exata de um dos trechos
   fornecidos>` / `###FIM`. **Guardrail central**: o `TRECHO` devolvido só é aceito se bater
   (via `validador.normaliza`) com **exatamente um** dos trechos que foram fornecidos àquela
   pergunta — nunca um trecho novo. Se não bater, ou se `VALOR` vier fora de -2..2/null,
   `valor=null` e `justificativa` vira a frase neutra padrão. Grava em `quiz_posicao` com
   `on conflict (pergunta_id, pessoa_id) do update ... where quiz_posicao.fonte_tipo =
   'proposta'` (nunca sobrescreve posição de outra origem). `status_revisao='em_revisao'`.

7. **`etl/raiox/ia/certidoes.py`** (classificador determinístico + core) +
   **`etl/raiox/jobs/ia_certidoes.py`**. Filtro: `candidatura.cargo_codigo = 1` (titular OU
   vice — chapa presidencial inteira), `arquivo_tse.cod_tipo in (11,12,13,14,15,1)`,
   `status='baixado'`, sem linha em `certidao_analise` ainda (idempotência trivial via PK
   `arquivo_id`). Regras determinísticas (regex, ver rascunho revisado):
   - Padrões de **negativa**: `nada\s+consta`, `certid(ao|ão)[^.]{0,80}negativa`,
     `n(a|ã)o\s+constam?\s+ante?cedentes`, `inexist(e|em)\s+(registro|processo|ante?cedente)`,
     `n(a|ã)o\s+h(a|á)\s+registros?`.
   - Padrões de **positiva**: `consta\s+(o\s+)?(seguinte\s+)?registro`, `certid(ao|ão)
     positiva`, `r(e|é)u\s+em\s+a(c|ç)(a|ã)o\s+penal`, `condenad[oa]`, `den(u|ú)ncia\s+
     recebida`, ou presença de nº CNJ válido (`cnj.extrai_numeros` + `cnj.valido`).
   - Ambos batem → `inconclusiva` (`precisa_ia=True`). Nenhum bate → `inconclusiva`
     (`precisa_ia=True`). Texto vazio/curto demais → `ilegivel`.
   - `trechos`: recorta a **linha original** (não normalizada) da página onde o padrão bateu
     — garante trivialmente que é literal (fatia direta do texto real), sem precisar mapear
     índices de volta de um texto normalizado.
   - `--usar-ia`: só para `inconclusiva`, só se `config().anthropic_api_key` existir, usa
     `claude-haiku-4-5`, mesmas regras de neutralidade/citação literal não se aplicam aqui
     (é classificação, não resumo), mas a saída ainda passa pelo validador literal para os
     trechos que a IA apontar.
   - Certidão `positiva` com nº CNJ válido → cria `processo` (`status_revisao='rascunho'`,
     `status` nulo, `tribunal` = alias do `datajud_tribunais` ou "desconhecido") +
     `processo_parte` (`origem='certidao_tse'`, `arquivo_id`, `polo='passivo'`,
     `pessoa_id` = `candidatura.pessoa_id` do arquivo). Não cria duplicata
     (`numero_cnj` é `unique` no schema — usar `on conflict do nothing` ou checar antes).
   - Ao final do job, contar e logar a distribuição (`Counter` por `resultado`) — é o que o
     "Execução real" pede para ser reportado (não precisa de chave).

8. **Migração `supabase/migrations/20260928040000_ia_datajud.sql`** (aplicar via psycopg, não
   `supabase db reset`):
   ```sql
   alter table processo
     add column if not exists status_sugerido status_regua,
     add column if not exists status_sugerido_motivo text,
     add column if not exists revisao_pendente boolean not null default false;
   -- comentários explicando a decisão de nunca reabrir revisão de processo já publicado
   -- automaticamente (ver docs/metodologia/ia.md e PRÓXIMOS PASSOS item 9 abaixo).
   ```
   Aplicar com:
   ```bash
   cd "/c/Users/User/Downloads/Projeto Eleicoes 2026/etl"
   PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -c "
   import psycopg, pathlib
   sql = pathlib.Path('../supabase/migrations/20260928040000_ia_datajud.sql').read_text(encoding='utf-8')
   conn = psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres')
   conn.execute(sql); conn.commit(); print('ok')
   "
   ```

9. **`etl/raiox/ia/datajud_parse.py`** (parsing puro, testável com fixtures) +
   **`etl/raiox/jobs/datajud.py`**. Endpoint: `POST https://api-publica.datajud.cnj.jus.br/
   api_publica_<alias>/_search`, header `Authorization: APIKey <chave>` —
   `config().datajud_key or CHAVE_PUBLICA_DOCUMENTADA` (a chave confirmada acima; comentar
   que pode rotacionar e a wiki é a fonte de verdade). Corpo: `{"query": {"match":
   {"numeroProcesso": <20 dígitos sem pontuação>}}}`. `extrai_primeiro_hit(resposta) ->
   dict|None` (`hits.hits[0]._source`). `mapeia_processo(fonte) -> dict` (classe, assuntos,
   orgaoJulgador, dataAjuizamento, lista de movimentos ordenada, última movimentação).
   `sugere_status(movimentos) -> (status_regua|None, motivo)` — **decisão já tomada**: usar
   *matching por texto* do nome do movimento (não por código TPU numérico memorizado, para
   não arriscar inventar um código errado num projeto que se vende como juridicamente
   blindado); o `motivo` sempre ecoa o nome, código e data literais devolvidos pelo DataJud,
   para o revisor auditar. Regra de "processo já publicado" (**decisão já tomada, documentar
   em `docs/metodologia/ia.md`, não reabrir discussão**): se `status_revisao='aprovado'` e a
   nova última movimentação é diferente da armazenada, **não** mexe em `status`/
   `status_descricao`/`ultima_movimentacao` (o que está publicado continua publicado);
   só atualiza `datajud_bruto`, `datajud_atualizado_em`, `status_sugerido`,
   `status_sugerido_motivo`, marca `revisao_pendente=true` e insere uma linha em
   `changelog_publico` (`tipo='atualizacao_automatica'`). Se **não** estava aprovado, atualiza
   `status`/`status_descricao`/`ultima_movimentacao` livremente (rascunho ainda não publicado).
   `status_descricao` deve sempre incluir a frase fixa de presunção de inocência quando o
   status não for trânsito em julgado/absolvição (ver PLANO_FINAL.md §2.2).

10. **`etl/raiox/jobs/factcheck.py`**: Google Fact Check Tools API `claims:search`
    (`config().google_factcheck_key`; sem chave → pulado, sucesso, 0 registros). Só
    presidenciáveis+vices (`cargo_codigo=1`). Busca por nome de urna e nome civil,
    `languageCode=pt-BR`. Filtra por `agencia_checagem` `ativa and ifcn_signataria`, casando
    pelo domínio da URL do `claimReview[].url` (usar `urllib.parse.urlsplit`, comparar
    `netloc` normalizado contra `agencia_checagem.dominio`, aceitando subdomínio). Grava
    `checagem` (`status_revisao='rascunho'`, `avaliacao_original` = `textualRating` tal e
    qual, `relacao` por heurística simples: se o nome buscado aparece como sujeito da
    alegação → `autor_da_alegacao`, senão `alvo_da_alegacao` — deixar claro no código que é
    heurística e depende de revisão humana, nunca publicar sozinho).

11. **`etl/raiox/jobs/ifcn.py`**: usa Playwright (`from playwright.sync_api import
    sync_playwright`) para abrir `https://ifcncodeofprinciples.poynter.org/signatories`
    (confirmado nesta pausa que a página é renderizada via JS — precisa de browser real, como
    o TSE). Extrai nome + domínio de cada organização listada, casa por domínio normalizado
    contra `agencia_checagem.dominio`, atualiza `ifcn_signataria` e `ifcn_verificado_em =
    current_date`. Logar claramente qualquer `agencia_checagem` **não encontrada** na lista
    (não desativa sozinho — só loga um aviso para checagem manual, é uma tabela pequena e
    curada). **Verificar antes de rodar de verdade**: `playwright install chromium` já foi
    rodado nesse `.venv`? (checar com `python -m uv run python -c "from playwright.sync_api
    import sync_playwright; sync_playwright().start()"` ou similar; se faltar o browser, rodar
    a instalação primeiro — não tentei isso ainda nesta sessão).

12. **Testes** (`etl/tests/`, todos determinísticos, sem precisar de chave nem de rede):
    - `test_validador.py`: casos positivos/negativos com acento, hifenização de quebra de
      linha, aspas tipográficas, trecho que não existe.
    - `test_neutralidade.py`: termos proibidos (com flexão), limite de 280, menção a outro
      candidato/partido, resumo neutro aprovado.
    - `test_cnj.py`: `5063130-17.2016.4.04.7000` válido; dígito trocado inválido; formatos
      (20 dígitos corridos vs. formatado); alguns gerados via round-trip.
    - `test_datajud_tribunais.py`: os casos do item 3 acima.
    - `test_datajud_parse.py`: fixture JSON de resposta `_search` (criar
      `etl/tests/fixtures/ia/datajud_resposta.json` com um hit sintético plausível — CPF/nome
      não aplicável aqui pois DataJud não expõe partes, então não há dado sensível a
      anonimizar) + fixture de "sem resultado".
    - `test_ia_certidoes.py`: textos sintéticos (não reais — `arquivo_pagina` está vazia no
      banco agora, então não há texto real de certidão disponível para fixture; se ao retomar
      `arquivo_pagina` já tiver linhas de certidões, preferir 1-2 exemplos reais anonimizados
      como a instrução original pedia) cobrindo negativa/positiva/inconclusiva/ilegível.
    - `test_ia_propostas.py`: cliente Anthropic **mockado** (`unittest.mock` ou um objeto
      `SimpleNamespace` imitando `response.content`), cobrindo (a) fluxo feliz com citação
      válida, (b) **trecho inventado → descartado** (pedido explícito da tarefa original),
      (c) `SEM_MENCAO: false` sem nenhum trecho sobrevivente → proposta inteira descartada,
      (d) neutralidade reprovando e sendo regenerada, (e) idempotência (hash igual → pula).
    - `test_ia_bussola.py`: trecho fornecido vs. trecho devolvido pela IA não batendo →
      `valor=null`; trecho batendo → grava com página certa.
    - `test_factcheck.py`: fixture de resposta `claims:search` (criar
      `etl/tests/fixtures/ia/claimreview_resposta.json`), casando domínio com
      `agencia_checagem`, ignorando publicador fora da allowlist.
    - Rodar com `cd etl && PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run pytest -q`.

13. **`docs/metodologia/ia.md`** — escrever por último, depois que as decisões de design acima
    estiverem implementadas de fato (para não documentar algo que mudou na implementação).
    Deve cobrir, em linguagem simples para o público: como e onde a IA é usada (só extração +
    resumo descritivo de planos de governo e classificação de certidões/checagens — nunca
    opinião), os guardrails (validador literal, linter de neutralidade, regra dos 4 olhos já
    do banco), o rótulo de conteúdo por IA (Res. TSE 23.610/2019 alt. 23.732/2024), o que a IA
    **nunca** faz (não avalia viabilidade, não compara candidatos, não decide status jurídico
    sozinha — só sugere, humano decide), como corrigir um erro (canal de correção, SLA 24h).

## Comandos de verificação (lint + testes) — última execução nesta pausa

```
cd "/c/Users/User/Downloads/Projeto Eleicoes 2026/etl"
PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run ruff check raiox/ia
# -> All checks passed!  (só os 3 arquivos desta área existem; não rodei ruff no repo
#    inteiro para não reportar erros de arquivos de outros agentes como se fossem meus —
#    conferido separadamente que os erros do `ruff check raiox tests` completo são todos em
#    raiox/jobs/tse_candidaturas.py, raiox/jobs/tse_contas.py e raiox/tse/mapeamento.py,
#    arquivos de outro agente, fora da minha área)

PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run pytest -q
# -> "no tests ran in 0.02s" (nenhum arquivo de teste da minha área foi criado ainda —
#    etl/tests/ está vazio)
```

## Pendências que dependem de coisas fora do meu controle

- **`ANTHROPIC_API_KEY`**: ausente neste ambiente. `ia_propostas` (fora de `--estimar`),
  `ia_bussola` e o modo `--usar-ia` de `ia_certidoes` não podem ser exercitados de ponta a
  ponta contra a API real enquanto isso — o design já prevê saída limpa ("pulado", sucesso, 0
  registros) e os testes usam cliente mockado, então a ausência da chave não bloqueia
  desenvolvimento nem testes, só a execução real com IA de verdade e o `--estimar` real
  (que funciona sem chave via heurística de tokens, mas fica mais preciso com
  `count_tokens` se a chave existir).
- **`arquivo_pagina` vazia**: enquanto o agente paralelo não terminar a extração de texto dos
  PDFs, `ia_propostas`/`ia_certidoes`/`ia_bussola` não têm o que processar de verdade no banco
  local — o código deve ser terminado e testado com fixtures mesmo assim; a "Execução real"
  pedida (rodar `ia_certidoes` determinístico e `datajud` e reportar números) só produz
  resultado não-trivial depois que isso estiver populado.
- **`quiz_pergunta` vazia**: `ia_bussola` depende de perguntas cadastradas (fora desta área) —
  o job deve ser escrito e testado com fixture, mas não roda de verdade contra o banco até
  existirem perguntas ativas.
- **Chave pública do DataJud pode rotacionar**: usar sempre `config().datajud_key` primeiro; o
  valor documentado neste arquivo é só o fallback capturado em 27/09/2026.
- **Playwright para `ifcn.py`**: não confirmei ainda se os browsers do Playwright já estão
  instalados neste `.venv` (`playwright install chromium`) — checar antes de tentar rodar o
  job de verdade.

## Ambiente

`Is a git repository: false` para a raiz do projeto neste ambiente — não há como "não
commitar" no sentido de git porque não há repositório git aqui; nenhum arquivo foi de qualquer
forma publicado/enviado a lugar nenhum, só gravado em disco local, como pedido.
