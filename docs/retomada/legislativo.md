# Retomada — ETL Legislativo (Câmara/Senado/CGU/vínculo/votações-chave)

> Pausa geral pedida pelo dono do projeto em 28/09/2026, durante a fase de pesquisa
> (antes de escrever qualquer job). Nenhum processo em segundo plano foi iniciado por
> este agente e nenhuma transação de banco ficou aberta — é seguro retomar a qualquer
> momento. Este documento existe para que a retomada não repita a pesquisa já feita.

## 0. Mudança de escopo (decisão do dono, 28/09, prevalece sobre o prompt original)

A plataforma cobre **apenas os candidatos a Presidente 2026 (titulares + vices)** — não
mais todos os ~513 deputados/81 senadores. Ajustes decorrentes:

- `camara`/`senado`: não baixar a lista completa de deputados/senadores em exercício.
  Buscar, por nome, **apenas** os presidenciáveis/vices que tiveram mandato de deputado
  federal ou senador, em **qualquer legislatura** (a API da Câmara cobre legislaturas
  históricas desde 1826; a numeração de legislatura do Senado é a mesma do Congresso).
- Votações nominais: coletar todas as votações do período de mandato de cada
  presidenciável/vice **mais** as votações-chave curadas — não os ~513 deputados.
- `voto`: só gravar o voto dos presidenciáveis/vices identificados (não da Casa inteira).
  A `votacao` continua guardando o placar agregado (`votos_sim`, `votos_nao`) para
  contexto, isso vem de graça do arquivo em lote.
- CEAP/CEAPS, presença, emendas CGU: só para essas pessoas.
- `vinculo_parlamentar`: só precisa cobrir essas ~26 pessoas (não é mais um job de
  varredura geral).
- Isso reduz drasticamente o risco de estourar os 500 MB do Supabase Free — a
  preocupação de tamanho do prompt original (pensada para todos os deputados) deixa de
  ser o gargalo principal.

## 1. Estado exato no banco local agora (28/09/2026, ~23:11 local)

Rodar para confirmar antes de continuar:
```
cd etl && PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -c "
import psycopg
conn = psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres')
cur = conn.cursor()
for t in ['pessoa','candidatura','parlamentar','proposicao','votacao','voto','presenca','despesa_cota','emenda']:
    cur.execute(f'select count(*) from {t}'); print(t, cur.fetchone()[0])
"
```
Última leitura feita por este agente:

| tabela | linhas |
|---|---|
| pessoa | 10 |
| candidatura | 10 |
| parlamentar | 0 |
| proposicao | 0 |
| votacao | 0 |
| voto | 0 |
| presenca | 0 |
| despesa_cota | 0 |
| emenda | 0 |
| evidencia | 10 |

O job `tse_candidaturas` (de outro agente, em paralelo) já populou **5 dos 13 tickets
presidenciais** (10 pessoas = titular+vice de cada). Ele ainda estava rodando quando a
pausa chegou — **rode de novo antes de continuar** para pegar os ~8 tickets restantes:
```
cd etl && PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -m raiox tse-candidaturas
```
Tickets já confirmados no banco (nome_urna / nome_civil / cargo / partido):
- HERTZ DIAS (PSTU) + VANESSA PORTUGAL
- EDMILSON COSTA (PCB) + CLEUSA SANTOS
- FLAVIO BOLSONARO (PL) + ALFREDO GASPAR
- CLARIANA BARAO (DC) + FABIANA TORQUATO
- ESCRITOR AUGUSTO CURY (AVANTE) + JÚLIO DELGADO

Lista completa esperada (13 tickets, fonte: Wikipédia PT "Eleição presidencial no
Brasil em 2026" + Nexo Jornal, cruzada — **não veio do TSE diretamente**: o domínio
`dadosabertos.tse.jus.br` também está atrás do Akamai e devolveu 403 para chamada
HTTP direta; só o Playwright do módulo `raiox.common.tse` consegue, e isso é a área do
job `tse_candidaturas`, não a nossa). Confirmar cada nome contra `pessoa`/`candidatura`
assim que o job do TSE terminar — **não usar esta lista secundária como fonte de
verdade, só como pista para direcionar a busca nas APIs de Câmara/Senado**:

1. Lula (PT/FE Brasil) + Geraldo Alckmin (PSB)
2. Flávio Bolsonaro (PL) + Alfredo Gaspar (PL) — ✅ confirmado no banco
3. Ronaldo Caiado (PSD) + Gilberto Kassab (PSD)
4. Romeu Zema (NOVO) + Eduardo Girão (NOVO)
5. Augusto Cury (Avante) + Júlio Delgado (Avante) — ✅ confirmado no banco
6. Renan Santos (MISSÃO) + Coronel Medina (MISSÃO)
7. Rui Costa Pimenta (PCO) + Antônio Carlos (PCO)
8. Edmilson Costa (PCB) + Cleusa Santos (PCB) — ✅ confirmado no banco
9. Hertz Dias (PSTU) + Vanessa Portugal (PSTU) — ✅ confirmado no banco
10. Leonardo Avalanche (PRTB) + Silvia (PRTB)
11. Samara Martins (UP) + Raquel Brício (UP)
12. Wilson Grassi (Democrata) + Suêd Haidar (Democrata)
13. Clariana Barão (DC) + Fabiana Torquato (DC) — ✅ confirmado no banco

(Pablo Marçal teria registrado candidatura e sido cassado em 11/09/2026 — por isso
"14" candidaturas registradas inicialmente vs. 13 remanescentes; checar se isso bate
com o que o job do TSE efetivamente carregou.)

**Quem provavelmente tem passagem por Câmara/Senado** (a confirmar via API, não
assumir — ver seção 3 para o método já testado):
- Lula: Deputado Federal por SP, legislatura 48 (1987–1991, Constituinte).
- Flávio Bolsonaro: Senador por RJ, legislaturas 56–57 (2019–atual).
- Alfredo Gaspar: Deputado Federal por AL, legislatura(s) recentes — checar 56/57.
- Ronaldo Caiado: Senador por GO até assumir o governo em 2019 — checar legislatura 55.
- Gilberto Kassab: teve passagem por deputado federal (SP) antes da prefeitura de SP —
  checar legislaturas ~50–52.
- Eduardo Girão: Senador por CE, legislaturas 56–57.
- Júlio Delgado: Deputado Federal por MG, várias legislaturas — checar 54–57.
- Geraldo Alckmin: só Deputado **Estadual**/governador — fora do escopo (só federal).
- Demais (Zema, Cury, Renan Santos, Medina, Pimenta, Costa, Dias, Avalanche, Martins,
  Grassi, Barão e vices menores): provavelmente sem mandato federal, mas **verificar
  todos, não assumir** — o teste é barato (ver seção 3).

## 2. O que está PRONTO

- **Migração `supabase/migrations/20260928020000_legislativo_vinculo.sql`**: criada e
  **já aplicada no banco local** (via psycopg, commitada). Adiciona a `parlamentar`:
  `cpf_hmac text`, `nome_civil text`, `data_nascimento date`, e um índice parcial em
  `cpf_hmac`. Motivo: permitir que `vinculo_parlamentar` rode sem precisar rebater nas
  APIs de novo a cada execução. Confirmar que sobreviveu:
  ```
  select column_name from information_schema.columns where table_name='parlamentar';
  -- deve incluir: casa, id_externo, pessoa_id, nome, vinculo_confianca,
  -- vinculo_revisado, cpf_hmac, nome_civil, data_nascimento
  ```
- Nenhum job novo foi criado ainda (`raiox/jobs/camara.py`, `senado.py`,
  `cgu_emendas.py`, `vinculo_parlamentar.py` **não existem**). Nenhum arquivo em
  `raiox/legislativo/` foi criado (**a pasta não existe ainda**). Nenhum teste em
  `etl/tests/test_legislativo_*.py`. Nenhum `etl/dados/votacoes_chave.json`.
- Lint (`ruff check raiox tests`) e `pytest` rodados uma última vez antes da pausa:
  - `pytest`: **"no tests ran"** (não há nenhum teste no repo ainda — nem os meus nem
    de outros agentes).
  - `ruff`: 5 erros, **todos em arquivos de outros agentes** (`tse_contas.py` ×2,
    `tse/mapeamento.py` ×1, `exportar.py`/outro ×2 — linhas longas E501), **nenhum na
    minha área** porque ainda não escrevi código. Não mexi nesses arquivos (fora da
    minha área).

## 3. Pesquisa já feita (para não repetir)

### 3.1 Câmara dos Deputados — confirmado por chamada real
- `GET /api/v2/deputados?idLegislatura={leg}&nome={q}&itens=700` — lista por
  legislatura; o filtro `nome` **sem** `idLegislatura` só busca na legislatura atual
  (57) — **sempre passar `idLegislatura` explícito** para achar gente de mandatos
  antigos.
- `GET /api/v2/legislaturas?itens=100` — devolve todas as legislaturas com datas; para
  Câmara moderna relevante: 55 (2015-02-01–2019-01-31), 56 (2019-02-01–2023-01-31),
  57 (2023-02-01–2027-01-31). Vai muito além disso historicamente (até legislatura 1,
  1826) — para achar mandatos antigos de presidenciáveis (ex. Lula em 48, 1987–1991)
  já testei buscar por `idLegislatura` de 45 a 57 sem problema.
- `GET /api/v2/deputados/{id}` — detalhe: retorna `cpf`, `dataNascimento`, `nomeCivil`,
  `ufNascimento`, `municipioNascimento`, `sexo`, `escolaridade` dentro de `dados`. Já
  testado com id 220593 (Abilio Brunini): funciona, `cpf` vem como string de 11 dígitos
  sem formatação — **aplicar `identidade.cpf_hmac()` e nunca persistir o campo cru**.
  Lembrar de **remover o campo `cpf` do payload antes de `evidencia.registrar`**
  (exigência do item 6 do prompt).
- **Bug/armadilha de rede descoberta**: downloads grandes (~>23 MB) via `httpx` neste
  ambiente **sempre cortam no meio** (`httpx.RemoteProtocolError: peer closed
  connection`), mesmo com o retry padrão de `raiox.common.http.get_bytes` (que já
  cobre `TransportError`, mas o corte acontece de forma consistente no mesmo ponto,
  então o retry começa do zero e corta de novo). **Confirmado que funciona**: pedir em
  pedaços com `Range: bytes=<offset>-` (o servidor responde `206 Partial Content` e
  entrega o resto sem cortar) — testado em
  `votacoesVotos-2023.csv` (42.794.635 bytes): 1º pedaço cortou em ~23.2 MB, pedido
  seguinte com `Range: bytes=23199744-` trouxe os 19.594.891 bytes restantes sem erro.
  **Ação para retomada**: implementar um downloader em pedaços (`Range`) em
  `raiox/legislativo/arquivos.py` (ainda não criado) — **não** mexer em
  `raiox/common/http.py` (fora da nossa área; isso não é bug da função em si, é
  peculiaridade da rede deste ambiente/proxy). Esboço já pensado (não escrito):
  ```python
  def baixar_grande(cliente: httpx.Client, url: str) -> bytes:
      buf = bytearray()
      while True:
          headers = {"range": f"bytes={len(buf)}-"} if buf else {}
          try:
              with cliente.stream("GET", url, headers=headers, timeout=180) as r:
                  r.raise_for_status()
                  total = _tamanho_total(r, len(buf))  # Content-Length (200) ou Content-Range (206)
                  for chunk in r.iter_bytes(65536):
                      buf.extend(chunk)
          except httpx.TransportError:
              pass  # cai pro laço, que re-tenta com Range a partir do que já tem
          if total is not None and len(buf) >= total:
              return bytes(buf)
          # limitar tentativas para não loopar infinito em erro persistente
  ```
- **Bulk files confirmados (existem e respondem 200/206)**:
  - `https://dadosabertos.camara.leg.br/arquivos/votacoesVotos/csv/votacoesVotos-{ano}.csv`
    — colunas: `idVotacao;uriVotacao;dataHoraVoto;voto;deputado_id;deputado_uri;
    deputado_nome;deputado_siglaPartido;deputado_uriPartido;deputado_siglaUf;
    deputado_idLegislatura;deputado_urlFoto`. **Como só nos interessam ~26 pessoas
    agora**, dá pra baixar o CSV do ano (ou baixar em pedaços) e filtrar em memória por
    `deputado_id` **sem nem precisar da versão "grande" do downloader na maioria dos
    anos** — mas alguns anos passam de 23 MB, então implementar o downloader em
    pedaços mesmo assim (barato, e evita flakiness).
  - `https://dadosabertos.camara.leg.br/arquivos/votacoes/csv/votacoes-{ano}.csv` —
    colunas: `id;uri;data;dataHoraRegistro;idOrgao;uriOrgao;siglaOrgao;idEvento;
    uriEvento;aprovacao;votosSim;votosNao;votosOutros;descricao;
    ultimaAberturaVotacao_dataHoraRegistro;ultimaAberturaVotacao_descricao;
    ultimaApresentacaoProposicao_dataHoraRegistro;ultimaApresentacaoProposicao_descricao;
    ultimaApresentacaoProposicao_idProposicao;ultimaApresentacaoProposicao_uriProposicao`.
    Usar para descobrir quais votações são de Plenário (`siglaOrgao == 'PLEN'`) e
    excluir as procedurais. **Teste real em 2023**: 10.851 votações no ano todo, 1.090
    em PLEN; aplicando o filtro de descrição abaixo sobram 388 "substantivas".
  - Filtro de votação procedural testado e funcionando (heurística por prefixo de
    `descricao`, documentar no código e no relatório final como critério neutro):
    excluir `descricao` que comece com `"Aprovado o Requerimento"`,
    `"Rejeitado o Requerimento"`, `"Requerimento aprovado"`,
    `"Requerimento rejeitado"`, `"Aprovada a Redação Final"`,
    `"Aprovada, por unanimidade, o Requerimento"`,
    `"Aprovado, por unanimidade, o Requerimento"`,
    `"Rejeitado, por votação simbólica"`, `"Alteração do Regime"`,
    `"Mantido o texto"`, `"Suprimido o texto"`. Isso é o filtro de tamanho pensado
    para "todos os deputados" (não mais necessário no mesmo grau agora que o escopo
    caiu pra ~26 pessoas, mas continua sendo o critério certo para decidir "votação
    nominal de proposição, não procedimental" pedido no item 1 do prompt — **manter**,
    é o que documenta a metodologia de forma neutra).
  - `GET /api/v2/votacoes/{id}/votos` retorna **vazio** para votações antigas (API REST
    só cobre período recente) — **não usar**, só os arquivos em lote têm histórico.
  - CEAP (cota) — bulk: `https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip`
    (confirmado 200, ~7,5 MB em 2023; é um zip de um único CSV). Colunas relevantes:
    `txNomeParlamentar;cpf;...;nuDeputadoId;...;numMes;numAno;txtDescricao;
    vlrLiquido;...`. Filtrar por `nuDeputadoId` (vazio = despesa de bancada/liderança,
    não de um deputado individual — **descartar essas**, não têm `id_externo` pra
    ligar em `parlamentar`). Agregar por `(ano, mes, txtDescricao)` somando
    `vlrLiquido` — isso mantém `despesa_cota` pequena mesmo somando anos.
    `txtDescricao` é a categoria (ex. "MANUTENÇÃO DE ESCRITÓRIO DE APOIO À ATIVIDADE
    PARLAMENTAR").

### 3.2 Senado Federal — confirmado por chamada real
- OpenAPI completo em `https://legis.senado.leg.br/dadosabertos/v3/api-docs` (funciona,
  200, é como descobri os paths abaixo — útil pra retomada consultar de novo se faltar
  algo).
- `GET /dadosabertos/senador/lista/legislatura/{leg}?format=json` — lista de senadores
  da legislatura (testado com 56, funciona). Estrutura:
  `ListaParlamentarLegislatura.Parlamentares.Parlamentar[].IdentificacaoParlamentar`
  (`CodigoParlamentar`, `NomeParlamentar`, `NomeCompletoParlamentar`,
  `SiglaPartidoParlamentar`) + `.Mandatos.Mandato[]` (`UfParlamentar`,
  `PrimeiraLegislaturaDoMandato`/`SegundaLegislaturaDoMandato` com `DataInicio`/
  `DataFim`).
- `GET /dadosabertos/senador/{codigo}?format=json` — detalhe: 
  `DetalheParlamentar.Parlamentar.IdentificacaoParlamentar.NomeCompletoParlamentar`
  (nome civil) e `.DadosBasicosParlamentar.DataNascimento` (usar para o vínculo por
  nome+nascimento, já que o Senado não expõe CPF — confiança 90 se bateu nascimento,
  60 se só o nome, como pedido no prompt original).
- Votação nominal em lote por ano:
  `GET /dadosabertos/plenario/votacao/nominal/{ano}?format=json` (testado com 2023,
  200 OK, funciona; é o endpoint antigo mas está ativo até 2026-02-01 segundo o
  próprio payload — **atenção**: `Metadados.Descontinuacao` avisa que será
  desativado; o substituto é `GET /dadosabertos/votacao` — **checar na retomada se já
  não foi desligado**, e se sim usar o substituto, que ainda não testei o formato).
  Estrutura: `ListaVotacoes.Votacoes.Votacao[]` com `CodigoSessao`, `DataSessao`,
  `DescricaoVotacao`, `Resultado`, `TotalVotosSim/Nao/Abstencao`, `SiglaMateria`,
  `NumeroMateria`, `AnoMateria`, `DescricaoIdentificacaoMateria` (ex. "PDL 2/2023") —
  **isso já dá sigla/número/ano da proposição de graça, sem precisar de chamada
  extra** (diferente da Câmara). `Secreta`: `"S"`/`"N"` — **só ingerir voto individual
  quando `"N"`** (voto secreto não expõe Sim/Não/Abstenção reais, só `"Votou"`/códigos
  de ausência — testado em 2023: 91 de 141 votações no ano eram secretas! Confirma a
  necessidade do filtro). Em votação não-secreta, `Votos.VotoParlamentar[].Voto` tem
  valores como `Sim`, `Não`, `Abstenção`, mas também `AP` (Atividade Parlamentar —
  ausência justificada), `LS` (Licença Saúde), `MIS` (Missão), `P-NRV` (Presidente não
  registra voto), `NCom` (não compareceu) — **mapear os códigos de ausência para
  `Ausente`** no normalizador de voto (ainda não escrito), manter `Sim`/`Não`/
  `Abstenção` como estão, e usar `Obstrução`/`Art. 17` se aparecerem (não vistos na
  amostra de 2023, mas são valores válidos do enum do banco — conferir em outra
  amostra antes de fechar o mapeamento).
- CEAPS (cota do Senado) — bulk, **fora da API `legis.senado.leg.br`**, é outro
  domínio: `https://www.senado.leg.br/transparencia/LAI/verba/despesa_ceaps_{ano}.csv`
  (confirmado 2015/2023/2026, todos 200 com `Range`). **Cuidado**: o servidor faz
  negociação de conteúdo e devolve `406` se o header `accept` for
  `application/json` (o padrão do `raiox.common.http.cliente()`) — **precisa
  sobrescrever o header** `accept: text/csv,*/*` na chamada (passar `headers=` no
  `.get()`, não mudar o cliente padrão). CSV em Latin-1 (`iso-8859-1`), `;`-separado,
  colunas: `ANO;MES;SENADOR;TIPO_DESPESA;CNPJ_CPF;FORNECEDOR;DOCUMENTO;DATA;
  DETALHAMENTO;VALOR_REEMBOLSADO;COD_DOCUMENTO`. **Vínculo é por nome** (`SENADOR` vem
  em maiúsculas, ex. "ACIR GURGACZ") — casar contra `parlamentar.nome`/`nome_civil`
  normalizado (`identidade.sem_acento` + upper/lower), não por código.

### 3.3 CGU / Portal da Transparência (emendas) — ainda não testado
Não cheguei a testar `https://api.portaldatransparencia.gov.br/api-de-dados/emendas`
nesta sessão (fiquei preso na pesquisa de Câmara/Senado antes da mudança de escopo).
Falta: confirmar parâmetros de filtro por ano/autor, formato da resposta, e o rate
limit documentado (o prompt original menciona respeitar rate limit mas não dá o
número — checar no header de resposta ou na documentação oficial ao retomar). Lembrar
que **sem `config().portal_transparencia_key` o job deve só logar que pulou e sair com
sucesso** (não falhar).

### 3.4 Identificação dos presidenciáveis com mandato federal
Testei uma abordagem (buscar por nome com `idLegislatura` explícito, uma legislatura
por vez) — funciona mas é lenta se feita nome-a-nome × legislatura (26 × ~11 chamadas).
**Melhor abordagem, já validada como mais eficiente**: baixar a lista completa de
deputados de cada legislatura relevante (**sem** filtro de nome) uma vez —
`GET /api/v2/deputados?idLegislatura={leg}&itens=700` para `leg` de 45 a 57 (13
chamadas) — e casar os nomes localmente (normalizados) contra a lista de
presidenciáveis/vices. **Já rodei isso uma vez com sucesso**: 3.409 deputados únicos
juntando legislaturas 45–57. **Não cheguei a fazer o casamento de nomes** (a pausa
chegou nesse ponto). Para o Senado, mesma lógica com
`/dadosabertos/senador/lista/legislatura/{leg}` por legislatura (o Senado não tem
filtro de nome de qualquer forma).

## 4. Próximos passos (na ordem, para retomar sem erro)

1. Reconferir estado do banco (comando da seção 1) e rodar `tse-candidaturas` de novo
   se `pessoa`/`candidatura` ainda não tiverem as 13 chapas completas — **usar os
   nomes reais de `pessoa.nome_civil`/`nome_urna` do banco a partir daqui, não a lista
   secundária da seção 1** (ela só serve de pista).
2. Criar `etl/raiox/legislativo/__init__.py` e `etl/raiox/legislativo/arquivos.py` com
   o downloader em pedaços (`baixar_grande`, esboço na seção 3.1) e um helper de CSV
   (leitura streaming com `csv.DictReader` sobre `io.StringIO`/`io.TextIOWrapper`,
   decodificando `utf-8-sig` para Câmara e `iso-8859-1` para o CEAPS do Senado).
3. Criar `etl/raiox/legislativo/identificacao.py`: função que recebe a lista de
   presidenciáveis/vices (de `pessoa`/`candidatura`, já carregados) e devolve, para
   cada um, os `id_externo` de Câmara e/ou Senado encontrados (usando a estratégia da
   seção 3.4: baixar listas por legislatura 45–57 uma vez, casar nome normalizado).
   Guardar também o período de mandato (datas de início/fim por legislatura) pra
   escopar quais anos de votação/CEAP buscar por pessoa.
4. Criar `etl/raiox/jobs/camara.py`: usa `identificacao.py` pra achar os deputados
   federais da lista; para cada um, chama `/deputados/{id}` (CPF → hmac, nome civil,
   nascimento; registra evidência **sem o CPF cru no payload**); grava `parlamentar`
   (casa='camara', com `cpf_hmac`/`nome_civil`/`data_nascimento` da migração nova).
   Depois, para cada ano do período de mandato (ou 2015–2026 se não achar o intervalo
   exato), baixa `votacoes-{ano}.csv` (filtra PLEN + não-procedural, seção 3.1),
   monta `proposicao` a partir do texto de `descricao`/`ultimaApresentacaoProposicao_*`
   (ou, se precisar de sigla/número/ano confiáveis, buscar
   `/api/v2/proposicoes/{id}` pontualmente — poucos, agora que é por pessoa), grava
   `votacao` com placar agregado do CSV; baixa `votacoesVotos-{ano}.csv` e filtra só
   as linhas cujo `deputado_id` está na nossa lista, grava `voto`. Presença: contar,
   por ano, quantas das votações retidas (nossas, do ano) o deputado tem linha de voto
   com valor diferente de "Ausente" vs. total de votações retidas naquele ano — **doc-
   umentar isso explicitamente como proxy** (não é frequência de sessão real, é
   proxy por comparecimento em votação nominal de proposição; o prompt já autoriza
   essa abordagem se não houver fonte melhor). CEAP: baixar `Ano-{ano}.csv.zip`,
   filtrar por `nuDeputadoId`, agregar por mês/categoria, gravar `despesa_cota`.
5. Criar `etl/raiox/jobs/senado.py`: mesma lógica pro lado Senado — detalhe do
   senador pra nome civil/nascimento; `plenario/votacao/nominal/{ano}` filtrando
   `Secreta=='N'` e por `CodigoParlamentar` nosso; normalizar voto (mapa de códigos de
   ausência da seção 3.2); CEAPS por nome.
6. Criar `etl/dados/votacoes_chave.json` com ~30–40 votações curadas — **ainda não
   escolhidas nem confirmadas nenhuma** (não cheguei nessa parte). Usar exemplos do
   prompt (Reforma da Previdência PEC 6/2019, Reforma Tributária PEC 45/2019, Teto de
   Gastos PEC 241/2016, Arcabouço Fiscal PLP 93/2023, Reforma Trabalhista PL 6787/2016,
   Marco Temporal, Marco do Saneamento, Autonomia do BC PLP 19/2019, Privatização da
   Eletrobras, Licenciamento Ambiental PL 2159/2021, Piso da Enfermagem, Novo Ensino
   Médio, PEC da Transição, Desoneração da Folha, etc.) e **confirmar o id real de cada
   votação principal via `votacoes-{ano}.csv`/`votacoes/nominal/{ano}` antes de
   incluir** — não inventar IDs; se não achar, documentar como "fora da lista" e
   justificar. Cobertura temática deve seguir os 9 temas de `supabase/seed.sql`
   (economia, previdencia, agro-ambiente, educacao, saude, seguranca, governanca,
   social, infraestrutura), distribuição equilibrada.
7. Criar `etl/raiox/jobs/votacoes_chave.py`: aplica a lista curada — `update votacao
   set chave=true, tema_id=... where id=...` (fazendo upsert de `votacao`/`proposicao`
   primeiro se a votação-chave envolver alguém fora dos ~26, já que a lista de
   votações-chave é para Bússola/Comparador e pode citar votações de deputados/
   senadores que não são presidenciáveis — **decisão a confirmar com o dono**: a
   votação-chave em si e seu placar agregado entram sempre; os votos individuais só
   dos ~26, como o resto).
8. Criar `etl/raiox/jobs/cgu_emendas.py`: testar a API do Portal da Transparência
   (pendência da seção 3.3) antes de escrever o job; usar `config().portal_transparencia_key`;
   sair com sucesso e log claro se a chave não estiver configurada.
9. Criar `etl/raiox/jobs/vinculo_parlamentar.py`: casa `parlamentar.pessoa_id` usando
   `parlamentar.cpf_hmac`/`nome_civil`/`data_nascimento` (já persistidos pelos jobs
   acima) contra `pessoa` — estratégia do prompt original (CPF=100,
   nome+nascimento=90, nome só=60+revisão). Como o escopo agora é só ~26 pessoas, deve
   rodar em menos de 1 segundo. Gerar o relatório de quantos presidenciáveis/vices
   ficaram vinculados.
10. Testes (`etl/tests/test_legislativo_*.py`, fixtures pequenas reais em
    `etl/tests/fixtures/legislativo/`): parse de voto (normalização Câmara/Senado),
    filtro de votação procedural (lista de prefixos da seção 3.1), regra de vínculo
    (CPF vs. nome+nascimento vs. nome só), agregação de CEAP/CEAPS.
11. Rodar tudo de verdade contra o banco local, medir `pg_total_relation_size` das
    tabelas novas, rodar `ruff check raiox tests` e `pytest` de novo, e escrever o
    relatório final pedido pelo prompt original (jobs e como rodar, números reais,
    tamanho das tabelas, método de presença, lista final de votações-chave com casa/id/
    tema, vínculos obtidos, pendências).

## 5. Decisões pendentes (perguntar ao dono se não ficar óbvio ao retomar)

- Lista de 13 tickets da seção 1 tem gente sem passagem federal conhecida (Zema,
  Cury, Renan Santos, Medina, Pimenta, Costa, Dias, Avalanche, Martins, Grassi, Barão
  e a maioria dos vices "menores") — confirmar por API mesmo assim (barato, seção 3.4),
  não assumir que não têm.
- Geraldo Alckmin: só teve mandato de Deputado **Estadual** (SP), não federal — por
  ora, **fora do escopo desta área** (só Câmara/Senado federais). Confirmar que isso
  está correto e que não é esperado tentar achá-lo na API da Câmara.
- Votação-chave que envolve pessoas fora dos ~26: decisão do passo 7 acima precisa de
  confirmação — grava só o agregado, ou expande a coleta de voto individual para os
  autores/relatores relevantes daquela votação também? (Impacta tamanho do banco e a
  utilidade da Bússola/Comparador, que precisa de posição documentada dos
  candidatos.)
- Endpoint antigo do Senado `plenario/votacao/nominal/{ano}` está marcado como
  descontinuado (`DataDesativacaoCompleta: 2026-02-01`, já passou!). Testei em
  27/09/2026 e ainda respondeu 200, mas **isso pode já ter mudado** — testar nos dois
  formatos (`nominal/{ano}` e o novo `/dadosabertos/votacao`) antes de depender de um
  só.

## 6. Comandos úteis para retomar

```bash
cd "/c/Users/User/Downloads/Projeto Eleicoes 2026/etl"
# reconferir banco
PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -c "import psycopg; ..."
# lint + testes (rodado pela última vez em 28/09/2026 ~23:12, ver seção 2)
PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run ruff check raiox tests
PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run pytest -q
# rodar um job (nenhum da nossa área existe ainda)
PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -m raiox camara
```
