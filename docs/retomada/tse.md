# Retomada — ETL do TSE (Raio-X 2026)

> Escrito em pausa solicitada pelo dono do projeto, em 28/09/2026, durante a implementação
> do ETL do TSE (`etl/raiox/jobs/tse_*.py`). Nenhum processo em segundo plano ficou rodando
> e nenhuma transação de banco ficou aberta — todos os jobs executados até aqui terminaram
> (`etl_execucao.status = 'sucesso'`) antes da pausa. Não houve `git commit`.

## Contexto importante: mudança de escopo (decisão do dono, prevalece)

O escopo do produto foi reduzido a meio do trabalho:

> **A plataforma cobre APENAS os candidatos a PRESIDENTE 2026 (cargo 1) — os 14 titulares +
> seus vices.** `tse_candidaturas` deve passar a ter `--cargos 1` como padrão (mantendo a
> opção de outros cargos no código, só não como padrão). Portão de qualidade padrão:
> nº de presidentes processado == nº da listagem, e ≥ 10. `tse_historico` é o foco agora:
> TODAS as eleições anteriores dos 14 + vices (bens históricos e mandatos completos,
> "capriche"). `tse_contas` e `tse_arquivos` (plano de governo + todas as certidões) só
> para esses 14 (+ vices). Outros cargos já gravados no banco local podem ficar (o
> exportador filtra), mas não gastar mais tempo neles.

**Isso NÃO foi aplicado ao código ainda** — é o primeiro passo da retomada (seção
"Próximos passos" abaixo). Também descobri, testando ao vivo, algo que muda o desenho do
job para o bem: **o vice/suplente é, ele mesmo, um "candidato" completo no TSE**, buscável
pelo próprio endpoint `buscar` com o `sq_CANDIDATO` dele (presente em `vices[].sq_CANDIDATO`
no detalhe do titular). Fazendo isso, o vice traz **seu próprio CPF, data de nascimento,
bens, arquivos (certidões) e `eleicoesAnteriores`** — muito melhor do que o que dá pra
extrair do bloco resumido `vices[]` embutido no titular (que não tem CPF nem bens). Como
o escopo agora é pequeno (14 titulares + ~14 vices ≈ 28 pessoas), vale a pena sempre buscar
o detalhe completo do vice também, em vez de só usar o resumo embutido.

Confirmado ao vivo (28/09/2026): ao buscar o detalhe de um vice pelo próprio id, o campo
`vices[]` desse detalhe contém, de volta, o titular (ponteiro reverso) —
`vice_detalhe['vices'][0]['sq_CANDIDATO'] == id_do_titular`. Ou seja, dá para usar a
**mesma função de parsing** para titular e vice; o que muda é só o valor de
`detalhe['cargo']['titular']` (bool) e o link reverso.

## O que está PRONTO

### Arquivos criados (todos novos, nada em `raiox/common/*` foi tocado)

- `etl/raiox/tse/__init__.py` — docstring do subpacote.
- `etl/raiox/tse/constantes.py` — `UFS`, `CARGOS` (código→nome), `ufs_do_cargo(cargo)`,
  `pares_cargo_uf(cargos)`. Testado manualmente, regras corretas (cargo 1 só BR; 3/5/6 em
  todas as 27 UF; 7 em todas menos DF; 8 só DF).
- `etl/raiox/tse/mapeamento.py` — funções **puras** (sem I/O) que transformam o JSON do TSE
  em linhas de tabela:
  - `remover_sensiveis(detalhe, extra=None)` — remove `cpf`/`tituloEleitor` (+ `extra`)
    recursivamente, em cópia profunda. Usado antes de qualquer `evidencia.registrar`.
  - `CAMPOS_SENSIVEIS_CONTAS = {"cpf","tituloEleitor","cpfCnpj"}` — decisão extra de
    privacidade: o `rankingDoadores` da prestação de contas traz CPF/CNPJ do doador (dado
    legalmente público, mas não precisamos guardá-lo em lugar nenhum — nossa tabela
    `maior_doador` só tem nome/tipo/valor).
  - `parse_data`, `parse_data_hora`, `parse_data_br`, `parse_epoch_ms` — parsers de data do
    TSE (formatos `YYYY-MM-DD`, `YYYY-MM-DD HH:MM`, `DD/MM/AAAA`, epoch ms).
  - `linha_pessoa_titular(detalhe)` — **ATENÇÃO: nome a revisar no próximo passo** (ver
    abaixo — deveria virar `linha_pessoa` genérica, pois agora vices também têm detalhe
    completo).
  - `linha_pessoa_vice(vice)` — a partir do bloco resumido `vices[]` (sem CPF/data
    nascimento). **Deve ficar sem uso** depois que o job passar a buscar o detalhe completo
    do vice (próximo passo) — mas não removi ainda, é código funcional e testável.
  - `linha_candidatura_titular(detalhe, ...)` / `linhas_candidatura_vices(detalhe, ...)` —
    idem: funcionam hoje (usadas por `tse_candidaturas.py` atual), mas o plano é
    **unificar** em uma única `linha_candidatura(detalhe, ...)` genérica que lê
    `detalhe['cargo']['titular']` e o ponteiro reverso em `vices[0]['sq_CANDIDATO']` quando
    for vice (ver "Próximos passos", passo 2).
  - `linhas_bens`, `linhas_arquivos` — bens e arquivos (metadados) a partir do detalhe.
  - `variacao_patrimonio_suspeita(anterior, atual, fator=1000)` — alerta (não bloqueia).
  - `linha_contas_campanha`, `linhas_maior_doador`, `_tipo_doador` (heurística PF/PJ/partido
    por tamanho do CPF/CNPJ e por palavras-chave no nome) — para `tse_contas`.
- `etl/raiox/tse/mandato.py` — regras de posse/duração por cargo, **completas e testadas
  manualmente por leitura** (ainda sem pytest — ver pendências):
  - Presidente: 1/jan do ano seguinte; a partir de 2027, 5/jan (EC 111/2021).
  - Governador: 1/jan; a partir de 2027, 6/jan (EC 111/2021).
  - Senador/Dep. Federal/Estadual/Distrital: 1/fev.
  - Prefeito/Vereador: 1/jan.
  - Duração: 4 anos, exceto Senador (8 anos).
  - `foi_eleito(situacao_totalizacao)`: `True` só se começa com "eleito" (case-insensitive)
    e não é exatamente "suplente".
  - `deriva_mandato(...)` retorna `None` ou o dict pronto para a tabela `mandato` (falta só
    `pessoa_id`/`candidatura_id`/`origem`/`evidencia_id`, preenchidos pelo job).
- `etl/raiox/tse/pessoa.py` — resolução de identidade com acesso a banco:
  - `resolver_pessoa(conn, dados)`: 1) CPF via HMAC (forte) → 2) nome_civil + data_nascimento
    (só se exatamente 1 match) → 3) sem data_nascimento, nome_civil sozinho (só 1 match) →
    senão cria pessoa nova e **registra o método usado** (`ResultadoResolucao.metodo`:
    `cpf | nome_dob | nome_apenas | novo | nome_dob_ambiguo | nome_apenas_ambiguo`).
  - `gerar_slug_unico(conn, nome_urna, uf)`: `slugify(nome_urna)` → se colidir, tenta
    `-{uf.lower()}` → se colidir, `-2`, `-3`, ... Só é chamado ao **criar** pessoa nova (slug
    nunca muda depois).
  - `atualizar_pessoa_existente(conn, pessoa_id, dados)`: atualiza campos que podem mudar
    entre coletas (nunca o slug).
- `etl/raiox/tse/pdf.py` — extração de texto com `pypdfium2`:
  - `normalizar_texto(bruto)`: reconstrói parágrafos (linha em branco = quebra de parágrafo;
    hifenização de fim de linha é desfeita quando a linha seguinte começa com minúscula).
  - `extrair_paginas(bytes_pdf)` → lista de texto por página.
  - `hash_texto(paginas)` → sha256 do texto concatenado (separador `\f`).
  - `pdf_sem_texto(paginas)` → `True` se nenhuma página tem texto extraível (PDF escaneado —
    vai para fila de OCR/IA depois, fora do escopo deste job).
  - **Ainda não testado contra um PDF real do TSE** (só a API foi validada com
    `pdfium.PdfDocument.new()` / `new_page()` — ver pendências).
- `etl/raiox/jobs/tse_candidaturas.py` — job principal. **Funciona de ponta a ponta**
  (testado ao vivo — ver "Estado exato do banco" abaixo), mas com o desenho ANTIGO (6
  cargos por padrão, vice só com dados resumidos). Precisa dos ajustes do "Próximos
  passos".
- `etl/raiox/jobs/tse_contas.py` — job de prestação de contas. **Funciona de ponta a ponta**
  (testado ao vivo). Não deve precisar de mudanças estruturais com o novo escopo — só roda
  sobre as candidaturas titulares que já estiverem no banco (hoje só as 5 de teste; depois
  do recorte, as 14 de presidente). Doadores gravados sem CPF/CNPJ (confirmado por grep no
  cache — ver abaixo).

### Arquivos NÃO criados ainda

- `etl/raiox/jobs/tse_historico.py` — **não existe ainda**. É o job mais importante agora
  (foco do "capriche"), e nem foi começado.
- `etl/raiox/jobs/tse_arquivos.py` — **não existe ainda** (download de PDF + extração de
  texto). `raiox/tse/pdf.py` (extração) já existe e está pronto para ser usado por ele.
- Nenhum teste em `etl/tests/` (só a pasta `etl/tests/fixtures/tse/` foi criada, vazia —
  nenhuma fixture JSON foi salva ainda).

### Lint e testes (última execução, 28/09/2026)

```
cd etl && PYTHONUTF8=1 python -m uv run ruff check raiox tests
→ All checks passed!

cd etl && PYTHONUTF8=1 python -m uv run pytest -q
→ no tests ran in 0.02s   (esperado: nenhum arquivo de teste existe ainda)
```

## O que estava EM ANDAMENTO — estado exato

Nenhum processo em segundo plano foi iniciado por mim (nenhum `run_in_background`); os dois
jobs abaixo foram rodados de forma síncrona, **terminaram com sucesso** e a conexão foi
fechada normalmente (confirmado via `pg_stat_activity`: nenhuma query ativa, nenhuma
transação aberta além da minha própria sessão de inspeção, que também já fechou).

`select id, job, status, registros from etl_execucao order by id`:

| id | job | status | registros |
|---|---|---|---|
| 1 | tse_candidaturas | sucesso | 5 |
| 2 | tse_contas | sucesso | 5 |
| 3 | exportar | sucesso | 11 | ← **não fui eu**; outro agente rodando em paralelo em `apps/web`/`jobs/exportar.py`, conforme o próprio enunciado avisa que existem agentes em paralelo. Não mexi nesse job.

Esses 2 runs foram **testes manuais pequenos** (`--cargos 1 --limite 5`), só para validar
o pipeline antes de rodar em escala — não foi feita nenhuma coleta completa ainda (nem da
listagem completa de 14 presidentes, nem de qualquer outro cargo em escala).

Contagens atuais no banco local (`postgresql://postgres:postgres@127.0.0.1:54322/postgres`):

```
candidatura: cargo_codigo=1 'Presidente' titular=true  → 5
             cargo_codigo=1 'Vice-presidente' titular=false → 5
pessoa: 10        (5 titulares + 5 vices, todos com slug único, nenhum CPF em claro)
bem: 81
arquivo_tse: 51   (status = 'pendente' — tse_arquivos ainda não existe, nada foi baixado)
evidencia: 10     (JSON do detalhe de cada um dos 10 candidatos, sem cpf/tituloEleitor)
contas_campanha: 5
maior_doador: 24  (sem cpfCnpj — confirmado por grep no cache, ver abaixo)
mandato: 0        (tse_historico ainda não existe)
eleicao: 1         (id 20322002026, "Eleições Gerais 2026")
```

Verificação de privacidade feita e OK:
```
grep -rl 'cpfCnpj' etl/.cache/evidencias   → nenhum resultado
select count(*) from pessoa where cpf_hmac ~ '^[0-9]{11}$'  → 0  (cpf_hmac é sempre hash, nunca CPF em claro)
```
Isso foi checado com os 5 registros de teste; **precisa ser reconfirmado depois da coleta
real dos 14 presidentes + vices**.

Esses 5+5 registros de teste **podem ficar no banco** — o próximo `tse_candidaturas` (rodado
com o `--cargos 1` já sendo o padrão, sem `--limite`) vai processar os 14 titulares reais
(que incluem parte desses 5 de teste) via upsert e vai também descobrir e gravar os vices
que faltam. Não é necessário limpar a tabela antes.

## Próximos passos (numerados, para retomar sem erro)

1. **Aplicar a mudança de escopo em `tse_candidaturas.py`:**
   - Trocar o default de `--cargos` de "todos os 6 cargos" para `"1"` (mas manter a opção
     de passar outros cargos via CLI — não remover `pares_cargo_uf`/`ufs_do_cargo` nem os
     cargos 3/5/6/7/8 de `constantes.py`).
   - Trocar os portões de qualidade: quando `1` estiver em `cargos` e não houver `--limite`,
     exigir `pres_listagem >= 10` e `pres_processado == pres_listagem` (isso já existe no
     código, só precisa deixar de depender de `execucao_completa = not (cargos or ufs or
     limite)` — com `--cargos` tendo default `"1"`, essa variável nunca vai ficar `True` do
     jeito que está escrita hoje). Sugestão: calcular os gates a partir do conteúdo de
     `cargos` (`1 in cargos`, `{6,7} & set(cargos)`, `set(cargos) == set(CARGOS)`) em vez de
     um único booleano `execucao_completa`.
   - Remover (ou deixar como *no-op* guardado por `if`) o gate "nenhuma UF com 0 deputados"
     quando `6`/`7` não estiverem em `cargos` (senão ele quebra o run padrão, que só pega
     cargo 1).

2. **Unificar titular/vice em `mapeamento.py` e no job** (a descoberta do ponteiro reverso
   torna isso natural e melhora muito a qualidade dos dados do vice):
   - Nova função `id_candidato_titular(detalhe) -> int | None`: se
     `detalhe['cargo']['titular']` for `False`, procura em `detalhe.get('vices') or []` uma
     entrada cujo `sq_CANDIDATO` seja diferente do próprio `detalhe['id']` e retorna esse
     id (é o titular da chapa). Se `titular` for `True`, retorna `None`.
   - Nova função `linha_pessoa(detalhe)` (renomear/generalizar `linha_pessoa_titular` — já
     serve para vice, pois o detalhe completo do vice também tem `cpf`, `dataDeNascimento`,
     `nomeCompleto`, `fotoUrl`, etc.).
   - Nova função `linha_candidatura(detalhe, *, eleicao_id, ano, uf)` (generaliza
     `linha_candidatura_titular`, usando `cargo_codigo`/`cargo_nome`/`titular` **do próprio
     `detalhe['cargo']`**, não mais fixo) + `candidatura_titular_id =
     id_candidato_titular(detalhe)`.
   - Pode manter `linha_pessoa_vice`/`linhas_candidatura_vices` no arquivo por enquanto
     (sem uso) ou remover — checar se algum teste novo depende delas antes de apagar.
   - No job: depois de buscar o detalhe de cada titular (cargo 1, filtrados pelo
     incremental), extrair os ids de vice de `detalhe['vices'][].sq_CANDIDATO` e **buscar o
     detalhe completo de cada vice também** (mesma função `_buscar_detalhe`, mesmo
     tratamento de erro). Não aplicar lógica de incremental aos vices — sempre buscar de
     novo (a escala é pequena: no máx. ~14-28 chamadas extras).
   - Quando o titular for pulado por incremental, ainda é preciso saber os ids dos vices
     dele para atualizá-los: `select id from candidatura where candidatura_titular_id = %s`.
   - Trocar `_grava_candidato` por algo tipo `_grava_detalhe(conn, uf, detalhe, existentes,
     alertas)` que serve tanto para titular quanto para vice (mesma função de gravação,
     porque agora o shape do JSON é o mesmo dos dois lados).
   - Ajustar o gate de contagem "pres_processado == pres_listagem" para contar só
     `cargo_codigo == 1 and titular == True` (não misturar com as linhas de vice, que vão
     ter `cargo_codigo == 2`, "Vice-presidente").

3. **Rodar `tse_candidaturas` de verdade** (sem `--limite`) e conferir no banco:
   ```
   cd etl && PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -m raiox tse_candidaturas
   ```
   Esperado: 14 titulares + N vices (≤14, um por chapa — conferir se todas têm vice
   registrado; pode haver chapa sem vice ainda por indeferimento). Reconferir manualmente
   os 14 perfis (bens, foto, situação, slug) via SQL, um a um — pedido explícito do dono.

4. **Criar `etl/raiox/jobs/tse_historico.py`** (o foco atual, "capriche"):
   - Para cada uma das ~14-28 pessoas (titulares + vices), ler `eleicoesAnteriores[]` do
     detalhe já coletado (pode reler do cache de evidência em vez de rebuscar — ver
     `raiox/common/evidencia.caminho_cache` — ou simplesmente rebuscar, é barato nessa
     escala).
   - Para cada entrada de `eleicoesAnteriores` (exceto a de 2026, já coletada): montar a URL
     `/candidatura/buscar/{nrAno}/{sgUe}/{idEleicao}/candidato/{id}` — **atenção**: para
     eleições municipais, `sgUe` é o código do município (ex.: `"71072"`), não a sigla da
     UF (confirmado ao vivo — ver exemplo real capturado: `ABEL COSTA`, vereador SP em 2020,
     `sgUe="71072"`, `idEleicao="2030402020"`).
   - Buscar o detalhe de cada candidatura antiga, gravar `eleicao` (upsert — precisa criar
     linha de eleição antiga; `abrangencia` = 'F' para federal/estadual, 'M' para
     municipal — inferir por `cargo` in {Prefeito, Vereador}), `candidatura` (reusar
     `linha_candidatura` do passo 2, com `ano`/`eleicao_id`/`uf` antigos; para municipal,
     preencher também `municipio`), `bem` históricos (`linhas_bens`, delete+insert).
   - Usar `raiox/tse/mandato.py` (`deriva_mandato`) para decidir se cria linha em `mandato`
     (checar `situacao_totalizacao` da candidatura antiga — usar o texto vindo do **detalhe**
     da candidatura antiga, não o de `eleicoesAnteriores` que já vem resumido, para
     consistência). `origem = 'tse_eleito'`, `candidatura_id` = id da candidatura antiga,
     `evidencia_id` = evidência do detalhe antigo.
   - Registrar evidência do JSON de cada candidatura antiga (mesma sanitização de
     cpf/tituloEleitor).
   - CLI: como o escopo é só ~14-28 pessoas, não precisa de `--limite`/`--concorrencia`
     sofisticados, mas manter o padrão dos outros jobs por consistência.
   - Priorizar majoritários primeiro é uma instrução do escopo antigo (20 mil candidatos);
     com o escopo novo (só presidentes) isso não se aplica mais — pode processar todos de
     uma vez.

5. **Criar `etl/raiox/jobs/tse_arquivos.py`**:
   - Query: `arquivo_tse` com `status = 'pendente'`, ordenado por prioridade: primeiro
     `cod_tipo = 5` (proposta de governo) das candidaturas de `cargo_codigo = 1`, depois
     `cod_tipo in (11,12,13,14,15,1)` (certidões) de todos. Com o escopo reduzido, isso é
     só uma dúzia de PDFs — dá para baixar tudo numa rodada só.
   - Usar `ClienteTSE.arquivo(id_arquivo)` → `(bytes, mime) | None`. `None` = 404
     (aguardando anonimização): incrementar `tentativas`; se `tentativas + 1 >= 10`, status
     `'indisponivel'`; senão continua `'pendente'`.
   - Quando baixar com sucesso: `evidencia.registrar(tipo_fonte='tse', url_original=
     f"{BASE}/divulga/rest/arquivo/doc/{id}", conteudo=bytes, mime=mime)`; usar
     `raiox.tse.pdf.extrair_paginas` + `hash_texto` + `pdf_sem_texto`; gravar
     `arquivo_pagina` (uma linha por página) e atualizar `arquivo_tse` (`status='baixado'`,
     `evidencia_id`, `paginas`, `texto_sha256`); se `pdf_sem_texto(...)`, registrar em
     `ex.detalhes['escaneados_sem_texto']` (não falha o job).
   - CLI: `--tipos 5` (só propostas) e `--limite`.
   - **Ainda não validei a extração de texto contra um PDF real do TSE** — antes de rodar
     em escala, baixar 1 PDF de teste manualmente (ex.: um `codTipo=5` de um dos 14
     presidentes) e conferir visualmente o texto extraído/normalizado.

6. **Escrever os testes pytest** (nenhum existe ainda):
   - `etl/tests/fixtures/tse/`: salvar 2-3 JSONs reais (usar `remover_sensiveis` antes de
     salvar em disco, mesmo sendo fixture de teste — não versionar cpf/tituloEleitor nunca).
     Sugestão: um detalhe de titular (Presidente), um de vice, um de candidatura histórica
     (para `tse_historico`).
   - `etl/tests/test_tse_mapeamento.py`: `remover_sensiveis` (garante que `cpf`/
     `tituloEleitor`/`cpfCnpj` somem em qualquer nível, incluindo aninhado); `linha_pessoa`;
     `linha_candidatura` (titular e vice, incl. `candidatura_titular_id` via
     `id_candidato_titular`); `linhas_bens`; `linhas_arquivos`; `variacao_patrimonio_
     suspeita`; `linha_contas_campanha`/`linhas_maior_doador`/`_tipo_doador`.
   - `etl/tests/test_tse_mandato.py`: `foi_eleito` (incl. "Suplente" → `False`); `data_posse`
     (antes/depois de 2027 para Presidente e Governador); `data_fim_mandato` (Senador 8
     anos vs. demais 4); `deriva_mandato` (não eleito → `None`).
   - `etl/tests/test_tse_pessoa.py`: `gerar_slug_unico` com uma conexão fake (objeto simples
     com `.execute()` retornando um resultado configurável) simulando colisão de slug →
     confere sufixo `-uf` e depois `-2`, `-3`.
   - `etl/tests/test_tse_pdf.py`: gerar um PDF pequeno (`pypdfium2.PdfDocument.new()` +
     `new_page()` não escreve texto sozinho — **precisa de outra forma de gerar texto**:
     ou usar um PDF real pequeno baixado do TSE e salvo em
     `etl/tests/fixtures/tse/exemplo_certidao.pdf`, ou montar um PDF mínimo à mão (stream
     `BT ... Tj ET`) — decidir na retomada). Testar `normalizar_texto` isoladamente (não
     precisa de PDF: é só uma função de string) e `extrair_paginas`/`pdf_sem_texto` contra
     o PDF de exemplo.

7. **Rodar tudo de verdade, na ordem:** `tse_candidaturas` → `tse_contas` → `tse_arquivos
   --tipos 5` → `tse_arquivos` (certidões) → `tse_historico`. Medir tempos. Conferir
   manualmente os 14 perfis completos no banco (bens, histórico, mandatos, contas,
   documentos) — pedido explícito do dono antes de considerar concluído.

8. **Escrever o relatório final** no formato pedido originalmente (jobs criados e como
   rodar; números reais; tempos; problemas/decisões; migrações — **nenhuma foi necessária
   até agora, o esquema existente cobre tudo**; bugs em `common` — **nenhum encontrado nem
   corrigido**; pendências).

## Decisões e observações que valem a pena preservar

- **Nenhuma migração nova foi necessária.** O esquema em
  `supabase/migrations/20260928000000_esquema_inicial.sql` já cobre tudo que os 4 jobs
  precisam (`candidatura.candidatura_titular_id`, `mandato`, `contas_campanha`,
  `maior_doador`, `arquivo_tse`, `arquivo_pagina` já existiam prontos).
- **Nenhum bug foi encontrado em `raiox/common/*`** — `tse.py`, `db.py`, `job.py`,
  `evidencia.py`, `identidade.py`, `http.py` foram usados como estão, sem alteração.
- **`cargo_codigo` de vice/suplente**: a versão atual do código (antes do passo 2) inventa
  um valor herdando o do titular, com comentário explicando a decisão. Isso fica obsoleto
  assim que o passo 2 for feito — o `cargo_codigo` real do vice vem do próprio detalhe dele
  (`2` para vice-presidente, por exemplo — **não confirmado ainda para outros cargos**, mas
  fora do escopo atual).
- **`idCandidatoSuperior` do TSE não é confiável** para achar o titular a partir do vice —
  vem sempre `0` no detalhe do vice. O caminho certo é `vices[0].sq_CANDIDATO` no detalhe do
  próprio vice (ponteiro reverso, confirmado ao vivo).
- **`dataUltimaAtualizacao` da listagem (`/candidatura/listar/...`) costuma vir `null`**
  mesmo quando o detalhe (`/candidatura/buscar/...`) tem o valor preenchido — nesses casos
  o incremental do job sempre busca de novo (não dá para confiar na listagem para pular).
  Isso é esperado e está tratado no código (`if existente and atualizado_listagem and ...`).
- **Doador (`rankingDoadores`) traz CPF/CNPJ em claro** — é dado legalmente público
  (prestação de contas), mas decidi, por princípio de privacidade do projeto, remover o
  campo `cpfCnpj` também da evidência arquivada (não só do banco), já que a tabela
  `maior_doador` nunca precisou dele. Documentado em `mapeamento.py` perto de
  `CAMPOS_SENSIVEIS_CONTAS`.
- **Concorrência do `ClienteTSE`**: testado com `concorrencia=4` nos testes pequenos, sem
  nenhum 403/429 do Akamai. Não cheguei a testar em 8 nem 16 (a instrução pede começar em 8
  e não passar de 16) — para o escopo novo (só ~14-30 candidatos + ~14 prestações de conta)
  provavelmente nem é necessário ir além de 4-8.

## Comandos úteis para retomar

```bash
cd "etl"
# Rodar um job:
PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -m raiox tse_candidaturas --cargos 1 --limite 5 --concorrencia 4

# Lint:
PYTHONUTF8=1 python -m uv run ruff check raiox tests

# Testes:
PYTHONUTF8=1 python -m uv run pytest -q

# Conferir banco:
PYTHONUTF8=1 python -m uv run python -c "
import psycopg
c = psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres', row_factory=psycopg.rows.dict_row)
for r in c.execute('select cargo_codigo, cargo_nome, titular, count(*) from candidatura group by 1,2,3 order by 1,3'):
    print(r)
"
```
