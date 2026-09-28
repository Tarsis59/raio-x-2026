-- =============================================================================
-- Raio-X 2026 — esquema inicial
-- Princípios aplicados no banco:
--   * Nenhum dado sensível publicado sem evidência e sem dupla revisão (4 olhos).
--   * CPF nunca armazenado em claro (somente HMAC, usado para resolver identidade).
--   * Auditoria append-only em todas as tabelas editoriais.
-- =============================================================================

create extension if not exists unaccent;
create extension if not exists pg_trgm;

-- -----------------------------------------------------------------------------
-- Tipos
-- -----------------------------------------------------------------------------
create type status_revisao as enum ('rascunho', 'em_revisao', 'aprovado', 'rejeitado', 'despublicado');

create type status_regua as enum (
  'reu_acao_penal',              -- denúncia/queixa recebida
  'condenado_1a_instancia',
  'condenado_orgao_colegiado',
  'condenado_transito_julgado',
  'absolvido',
  'anulado',
  'punibilidade_extinta',
  'acao_civel_em_curso',         -- improbidade / ACP sem sentença
  'acao_civel_procedente',
  'acao_civel_improcedente'
);

create type papel_editor as enum ('editor', 'revisor', 'admin');

-- -----------------------------------------------------------------------------
-- Função utilitária: normalização para busca
-- -----------------------------------------------------------------------------
create or replace function normaliza(t text) returns text
language sql immutable parallel safe as $$
  select lower(unaccent('public.unaccent'::regdictionary, coalesce(t, '')))
$$;

create or replace function set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end $$;

-- -----------------------------------------------------------------------------
-- Evidências (repositório imutável)
-- -----------------------------------------------------------------------------
create table evidencia (
  id              uuid primary key default gen_random_uuid(),
  tipo_fonte      text not null,                 -- tse, camara, senado, cgu, datajud, bcb, ibge, caged, factcheck, imprensa, diario_oficial
  url_original    text not null,
  url_arquivo     text,                          -- cópia permanente (archive.org item)
  url_wayback     text,                          -- snapshot Wayback Machine
  sha256          text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  mime            text,
  bytes           bigint,
  capturado_em    timestamptz not null default now(),
  metodo          text not null default 'etl',   -- etl | manual
  link_ok         boolean not null default true,
  link_verificado_em timestamptz,
  unique (url_original, sha256)
);
create index evidencia_sha_idx on evidencia (sha256);

-- -----------------------------------------------------------------------------
-- Pessoas, eleições e candidaturas
-- -----------------------------------------------------------------------------
create table pessoa (
  id                  uuid primary key default gen_random_uuid(),
  slug                text not null unique,
  nome_urna           text not null,
  nome_civil          text not null,
  data_nascimento     date,
  uf_nascimento       text,
  municipio_nascimento text,
  genero              text,
  cor_raca            text,
  grau_instrucao      text,
  ocupacao            text,
  cpf_hmac            text unique,              -- HMAC-SHA256(cpf, segredo). Nunca o CPF em claro.
  foto_url            text,
  foto_evidencia_id   uuid references evidencia(id),
  busca               text generated always as (normaliza(nome_urna) || ' ' || normaliza(nome_civil)) stored,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);
create index pessoa_busca_trgm on pessoa using gin (busca gin_trgm_ops);
create trigger pessoa_updated before update on pessoa for each row execute function set_updated_at();

create table eleicao (
  id          bigint primary key,           -- idEleicao do TSE
  ano         smallint not null,
  nome        text not null,
  data        date,
  abrangencia text                          -- F (federal/estadual) | M (municipal)
);

create table candidatura (
  id                      bigint primary key,           -- idCandidato (sq_candidato) do TSE
  pessoa_id               uuid not null references pessoa(id) on delete cascade,
  eleicao_id              bigint not null references eleicao(id),
  ano                     smallint not null,
  cargo_codigo            smallint not null,
  cargo_nome              text not null,
  uf                      text not null,                -- BR para presidente
  municipio               text,                         -- eleições municipais históricas
  numero                  integer,
  partido_numero          smallint,
  partido_sigla           text,
  partido_nome            text,
  coligacao_nome          text,
  coligacao_composicao    text,
  titular                 boolean not null default true,
  candidatura_titular_id  bigint references candidatura(id),  -- para vices/suplentes
  situacao_registro       text,
  situacao_totalizacao    text,
  reeleicao               boolean,
  limite_gasto_1t         numeric(16,2),
  limite_gasto_2t         numeric(16,2),
  total_bens              numeric(16,2),
  processo_registro       text,
  processo_drap           text,
  processo_contas         text,
  sites                   text[] not null default '{}',
  atualizado_tse_em       timestamptz,
  coletado_em             timestamptz not null default now(),
  evidencia_id            uuid references evidencia(id),
  updated_at              timestamptz not null default now()
);
create index candidatura_pessoa_idx on candidatura (pessoa_id);
create index candidatura_eleicao_cargo_uf_idx on candidatura (eleicao_id, cargo_codigo, uf);
create trigger candidatura_updated before update on candidatura for each row execute function set_updated_at();

create table bem (
  candidatura_id  bigint not null references candidatura(id) on delete cascade,
  ordem           integer not null,
  tipo            text,
  descricao       text,
  valor           numeric(16,2) not null,
  atualizado_tse  date,
  primary key (candidatura_id, ordem)
);

create table arquivo_tse (
  id              bigint primary key,           -- idArquivo do TSE
  candidatura_id  bigint not null references candidatura(id) on delete cascade,
  cod_tipo        smallint not null,
  nome            text,
  anonimizado     boolean,
  status          text not null default 'pendente' check (status in ('pendente', 'baixado', 'indisponivel', 'erro')),
  tentativas      smallint not null default 0,
  evidencia_id    uuid references evidencia(id),
  paginas         integer,
  texto_sha256    text,                         -- hash do texto extraído (cache de IA)
  updated_at      timestamptz not null default now()
);
create index arquivo_tse_cand_idx on arquivo_tse (candidatura_id, cod_tipo);
create trigger arquivo_tse_updated before update on arquivo_tse for each row execute function set_updated_at();

-- Texto por página (usado pela IA e pelo validador de citação literal)
create table arquivo_pagina (
  arquivo_id  bigint not null references arquivo_tse(id) on delete cascade,
  pagina      integer not null,
  texto       text not null,
  primary key (arquivo_id, pagina)
);

create table contas_campanha (
  candidatura_id          bigint primary key references candidatura(id) on delete cascade,
  cnpj_campanha           text,
  total_recebido          numeric(16,2),
  receita_pf              numeric(16,2),
  receita_pj              numeric(16,2),
  receita_partidos        numeric(16,2),
  receita_propria         numeric(16,2),
  receita_fundo_especial  numeric(16,2),   -- FEFC
  receita_fundo_partidario numeric(16,2),
  receita_internet        numeric(16,2),
  receita_outros_candidatos numeric(16,2),
  receita_estimada        numeric(16,2),
  total_despesas          numeric(16,2),
  atualizado_tse_em       date,
  bruto                   jsonb not null,
  coletado_em             timestamptz not null default now()
);

create table maior_doador (
  candidatura_id  bigint not null references candidatura(id) on delete cascade,
  posicao         smallint not null,
  nome            text not null,
  tipo            text not null,                 -- PF | PJ | partido | fundo
  valor           numeric(16,2) not null,
  primary key (candidatura_id, posicao)
);

-- Mandatos/cargos ocupados (derivados de candidaturas eleitas + casas legislativas)
create table mandato (
  id            uuid primary key default gen_random_uuid(),
  pessoa_id     uuid not null references pessoa(id) on delete cascade,
  cargo         text not null,
  esfera        text not null check (esfera in ('federal', 'estadual', 'municipal')),
  uf            text,
  municipio     text,
  inicio        date not null,
  fim           date,
  origem        text not null,                   -- tse_eleito | camara | senado | manual
  candidatura_id bigint references candidatura(id),
  evidencia_id  uuid references evidencia(id),
  unique (pessoa_id, cargo, inicio)
);

-- -----------------------------------------------------------------------------
-- Temas (eixos do comparador e do quiz)
-- -----------------------------------------------------------------------------
create table tema (
  id          text primary key,                  -- slug
  eixo        text not null,
  nome        text not null,
  descricao   text,
  ordem       smallint not null
);

-- -----------------------------------------------------------------------------
-- Atividade legislativa
-- -----------------------------------------------------------------------------
create table parlamentar (
  casa        text not null check (casa in ('camara', 'senado')),
  id_externo  text not null,
  pessoa_id   uuid references pessoa(id) on delete set null,
  nome        text not null,
  vinculo_confianca smallint not null default 0,  -- 100 = CPF; <100 exige revisão
  vinculo_revisado boolean not null default false,
  primary key (casa, id_externo)
);
create index parlamentar_pessoa_idx on parlamentar (pessoa_id);

create table proposicao (
  id          text primary key,                  -- camara:12345 | senado:67890
  casa        text not null,
  sigla_tipo  text not null,
  numero      integer not null,
  ano         smallint not null,
  ementa      text,
  url         text,
  tema_id     text references tema(id)
);

create table votacao (
  id              text primary key,              -- camara:2345678-12 | senado:...
  casa            text not null,
  proposicao_id   text references proposicao(id),
  data            timestamptz not null,
  descricao       text,
  resultado       text,
  votos_sim       integer,
  votos_nao       integer,
  url             text,
  chave           boolean not null default false, -- votação-chave curada (lista pública)
  tema_id         text references tema(id)
);
create index votacao_data_idx on votacao (casa, data desc);

create table voto (
  votacao_id  text not null references votacao(id) on delete cascade,
  casa        text not null,
  id_externo  text not null,
  voto        text not null,                     -- Sim | Não | Abstenção | Obstrução | Art. 17 | Ausente
  primary key (votacao_id, casa, id_externo),
  foreign key (casa, id_externo) references parlamentar(casa, id_externo)
);
create index voto_parlamentar_idx on voto (casa, id_externo);

create table presenca (
  casa          text not null,
  id_externo    text not null,
  ano           smallint not null,
  sessoes       integer not null,
  presencas     integer not null,
  ausencias_justificadas integer not null default 0,
  primary key (casa, id_externo, ano),
  foreign key (casa, id_externo) references parlamentar(casa, id_externo)
);

create table despesa_cota (
  casa        text not null,
  id_externo  text not null,
  ano         smallint not null,
  mes         smallint not null,
  categoria   text not null,
  valor       numeric(14,2) not null,
  primary key (casa, id_externo, ano, mes, categoria),
  foreign key (casa, id_externo) references parlamentar(casa, id_externo)
);

create table emenda (
  codigo        text primary key,
  pessoa_id     uuid references pessoa(id) on delete set null,
  autor_nome    text not null,
  ano           smallint not null,
  tipo          text,                            -- individual, bancada, comissão, relator, pix (transferência especial)
  funcao        text,
  localidade    text,
  valor_empenhado numeric(16,2),
  valor_pago      numeric(16,2),
  url           text
);
create index emenda_pessoa_idx on emenda (pessoa_id, ano);

-- -----------------------------------------------------------------------------
-- Judiciário (curadoria + dupla revisão)
-- -----------------------------------------------------------------------------
create table editor (
  user_id   uuid primary key references auth.users(id) on delete cascade,
  nome      text not null,
  papel     papel_editor not null default 'editor',
  ativo     boolean not null default true,
  created_at timestamptz not null default now()
);

-- Colunas comuns de revisão para tabelas editoriais
-- (criado_por null = gerado por ETL/IA)
create table processo (
  id                    uuid primary key default gen_random_uuid(),
  numero_cnj            text not null unique check (numero_cnj ~ '^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$'),
  tribunal              text not null,
  grau                  text,
  classe                text,
  assuntos              text[] not null default '{}',
  orgao_julgador        text,
  data_ajuizamento      date,
  status                status_regua,
  status_descricao      text,                     -- texto neutro exibido
  ultima_movimentacao_em date,
  ultima_movimentacao   text,
  datajud_bruto         jsonb,
  datajud_atualizado_em timestamptz,
  evidencia_id          uuid references evidencia(id),
  status_revisao        status_revisao not null default 'rascunho',
  criado_por            uuid references auth.users(id),
  revisor_1             uuid references auth.users(id),
  revisor_2             uuid references auth.users(id),
  publicado_em          timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
create trigger processo_updated before update on processo for each row execute function set_updated_at();

create table processo_parte (
  processo_id   uuid not null references processo(id) on delete cascade,
  pessoa_id     uuid not null references pessoa(id) on delete cascade,
  polo          text not null default 'passivo',
  origem        text not null,                   -- certidao_tse | decisao | diario_oficial | manual
  arquivo_id    bigint references arquivo_tse(id),
  evidencia_id  uuid references evidencia(id),
  primary key (processo_id, pessoa_id)
);

-- Leitura de certidões criminais do registro de candidatura (IA + revisão)
create table certidao_analise (
  arquivo_id          bigint primary key references arquivo_tse(id) on delete cascade,
  resultado           text not null check (resultado in ('negativa', 'positiva', 'inconclusiva', 'ilegivel')),
  processos_citados   text[] not null default '{}',
  trechos             jsonb not null default '[]',   -- [{texto, pagina}]
  modelo              text not null,
  prompt_versao       text not null,
  validado_literal    boolean not null default false,
  created_at          timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- Checagens (agências signatárias IFCN)
-- -----------------------------------------------------------------------------
create table agencia_checagem (
  id              text primary key,              -- slug
  nome            text not null,
  dominio         text not null unique,
  ifcn_signataria boolean not null,
  ifcn_verificado_em date not null,
  ativa           boolean not null default true
);

create table checagem (
  id                uuid primary key default gen_random_uuid(),
  agencia_id        text not null references agencia_checagem(id),
  url               text not null unique,
  titulo            text,
  alegacao          text not null,
  autor_alegacao    text,
  avaliacao_original text not null,              -- rótulo exatamente como a agência publicou
  data_publicacao   date,
  pessoa_id         uuid references pessoa(id) on delete cascade,
  relacao           text check (relacao in ('autor_da_alegacao', 'alvo_da_alegacao')),
  tema_id           text references tema(id),
  evidencia_id      uuid references evidencia(id),
  status_revisao    status_revisao not null default 'rascunho',
  criado_por        uuid references auth.users(id),
  revisor_1         uuid references auth.users(id),
  revisor_2         uuid references auth.users(id),
  publicado_em      timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create index checagem_pessoa_idx on checagem (pessoa_id);
create trigger checagem_updated before update on checagem for each row execute function set_updated_at();

-- -----------------------------------------------------------------------------
-- Propostas (planos de governo → IA com citação → revisão)
-- -----------------------------------------------------------------------------
create table proposta (
  id              uuid primary key default gen_random_uuid(),
  candidatura_id  bigint not null references candidatura(id) on delete cascade,
  tema_id         text not null references tema(id),
  resumo          text,                           -- null quando sem_mencao
  trechos         jsonb not null default '[]',    -- [{texto, pagina}] — todos validados literalmente
  sem_mencao      boolean not null default false,
  arquivo_id      bigint references arquivo_tse(id),
  modelo          text,
  prompt_versao   text,
  gerado_por_ia   boolean not null default true,
  status_revisao  status_revisao not null default 'rascunho',
  criado_por      uuid references auth.users(id),
  revisor_1       uuid references auth.users(id),
  revisor_2       uuid references auth.users(id),
  publicado_em    timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (candidatura_id, tema_id)
);
create trigger proposta_updated before update on proposta for each row execute function set_updated_at();

-- -----------------------------------------------------------------------------
-- Bússola (quiz)
-- -----------------------------------------------------------------------------
create table quiz_pergunta (
  id              text primary key,
  tema_id         text not null references tema(id),
  ordem           smallint not null,
  texto           text not null,
  contexto        text not null,
  argumento_favor text not null,
  argumento_contra text not null,
  ativa           boolean not null default true
);

-- Votações que expressam a pergunta: direcao = +1 se votar "Sim" significa concordar
create table quiz_pergunta_votacao (
  pergunta_id text not null references quiz_pergunta(id) on delete cascade,
  votacao_id  text not null references votacao(id) on delete cascade,
  direcao     smallint not null check (direcao in (-1, 1)),
  primary key (pergunta_id, votacao_id)
);

create table quiz_posicao (
  pergunta_id     text not null references quiz_pergunta(id) on delete cascade,
  pessoa_id       uuid not null references pessoa(id) on delete cascade,
  valor           smallint check (valor between -2 and 2),   -- null = sem posição documentada
  fonte_tipo      text not null check (fonte_tipo in ('voto', 'proposta', 'declaracao')),
  justificativa   text not null,
  votacao_id      text references votacao(id),
  proposta_id     uuid references proposta(id),
  evidencia_id    uuid references evidencia(id),
  status_revisao  status_revisao not null default 'rascunho',
  criado_por      uuid references auth.users(id),
  revisor_1       uuid references auth.users(id),
  revisor_2       uuid references auth.users(id),
  publicado_em    timestamptz,
  updated_at      timestamptz not null default now(),
  primary key (pergunta_id, pessoa_id)
);
create trigger quiz_posicao_updated before update on quiz_posicao for each row execute function set_updated_at();

-- -----------------------------------------------------------------------------
-- Indicadores macroeconômicos
-- -----------------------------------------------------------------------------
create table indicador (
  id            text primary key,               -- ipca_12m, selic_meta, dbgg_pib, desocupacao, caged_saldo, pib_var
  nome          text not null,
  unidade       text not null,
  fonte         text not null,
  codigo_fonte  text not null,
  periodicidade text not null,
  descricao     text not null,
  por_uf        boolean not null default false,
  url_fonte     text not null
);

create table indicador_valor (
  indicador_id  text not null references indicador(id) on delete cascade,
  uf            text not null default 'BR',
  data          date not null,
  valor         numeric(18,6) not null,
  primary key (indicador_id, uf, data)
);

create table periodo_governo (
  id          uuid primary key default gen_random_uuid(),
  cargo       text not null check (cargo in ('presidente', 'governador')),
  uf          text not null default 'BR',
  nome        text not null,
  pessoa_id   uuid references pessoa(id) on delete set null,
  inicio      date not null,
  fim         date,
  fonte_url   text not null,
  unique (cargo, uf, inicio)
);

-- -----------------------------------------------------------------------------
-- Correções, changelog, operação
-- -----------------------------------------------------------------------------
create table correcao (
  id              uuid primary key default gen_random_uuid(),
  protocolo       text not null unique default upper(substr(md5(gen_random_uuid()::text), 1, 10)),
  pessoa_id       uuid references pessoa(id) on delete set null,
  pagina_url      text not null,
  tipo_solicitante text not null check (tipo_solicitante in ('eleitor', 'candidato', 'assessoria', 'imprensa', 'outro')),
  descricao       text not null check (length(descricao) between 20 and 5000),
  links           text[] not null default '{}',
  contato_email   text,                          -- opcional; apagado após 12 meses
  status          text not null default 'nova' check (status in ('nova', 'em_analise', 'procedente', 'improcedente')),
  sla_limite      timestamptz not null default now() + interval '24 hours',
  resolucao       text,
  resolvido_por   uuid references auth.users(id),
  resolvido_em    timestamptz,
  created_at      timestamptz not null default now()
);

create table changelog_publico (
  id          bigint generated always as identity primary key,
  pessoa_id   uuid references pessoa(id) on delete cascade,
  tipo        text not null,                    -- atualizacao_automatica | correcao | inclusao | remocao
  descricao   text not null,
  correcao_id uuid references correcao(id),
  created_at  timestamptz not null default now()
);
create index changelog_pessoa_idx on changelog_publico (pessoa_id, created_at desc);

create table etl_execucao (
  id          bigint generated always as identity primary key,
  job         text not null,
  inicio      timestamptz not null default now(),
  fim         timestamptz,
  status      text not null default 'executando' check (status in ('executando', 'sucesso', 'falha', 'bloqueado_qualidade')),
  registros   integer,
  mensagem    text,
  detalhes    jsonb
);
create index etl_execucao_job_idx on etl_execucao (job, inicio desc);

create table audit_log (
  id          bigint generated always as identity primary key,
  ator        uuid,
  ator_tipo   text not null,                     -- usuario | etl | sistema
  tabela      text not null,
  registro_id text not null,
  acao        text not null,
  antes       jsonb,
  depois      jsonb,
  ts          timestamptz not null default now()
);
create index audit_log_registro_idx on audit_log (tabela, registro_id, ts desc);

-- Audit log é append-only
create or replace function bloqueia_alteracao() returns trigger
language plpgsql as $$
begin
  raise exception 'audit_log é somente-inclusão';
end $$;
create trigger audit_log_imutavel before update or delete on audit_log
  for each row execute function bloqueia_alteracao();

create or replace function registra_auditoria() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  v_id text;
begin
  v_id := coalesce(
    (to_jsonb(coalesce(new, old)) ->> 'id'),
    (to_jsonb(coalesce(new, old)) ->> 'pergunta_id') || ':' || (to_jsonb(coalesce(new, old)) ->> 'pessoa_id')
  );
  insert into audit_log (ator, ator_tipo, tabela, registro_id, acao, antes, depois)
  values (
    auth.uid(),
    case when auth.uid() is null then 'etl' else 'usuario' end,
    tg_table_name, v_id, tg_op,
    case when tg_op in ('UPDATE', 'DELETE') then to_jsonb(old) end,
    case when tg_op in ('INSERT', 'UPDATE') then to_jsonb(new) end
  );
  return coalesce(new, old);
end $$;

-- -----------------------------------------------------------------------------
-- Regra dos 4 olhos (vale para processo, checagem, proposta, quiz_posicao)
-- -----------------------------------------------------------------------------
create or replace function valida_quatro_olhos() returns trigger
language plpgsql as $$
begin
  if new.status_revisao = 'aprovado' then
    if new.revisor_1 is null or new.revisor_2 is null then
      raise exception 'Publicação exige dois revisores';
    end if;
    if new.revisor_1 = new.revisor_2 then
      raise exception 'Os dois revisores precisam ser pessoas diferentes';
    end if;
    if new.criado_por is not null and new.criado_por in (new.revisor_1, new.revisor_2) then
      raise exception 'Quem criou o item não pode aprová-lo';
    end if;
    if new.publicado_em is null then
      new.publicado_em := now();
    end if;
  elsif new.status_revisao in ('rascunho', 'em_revisao', 'rejeitado', 'despublicado') then
    new.publicado_em := null;
  end if;
  return new;
end $$;

create trigger processo_quatro_olhos before insert or update on processo for each row execute function valida_quatro_olhos();
create trigger checagem_quatro_olhos before insert or update on checagem for each row execute function valida_quatro_olhos();
create trigger proposta_quatro_olhos before insert or update on proposta for each row execute function valida_quatro_olhos();
create trigger quiz_posicao_quatro_olhos before insert or update on quiz_posicao for each row execute function valida_quatro_olhos();

create trigger processo_audit after insert or update or delete on processo for each row execute function registra_auditoria();
create trigger processo_parte_audit after insert or update or delete on processo_parte for each row execute function registra_auditoria();
create trigger checagem_audit after insert or update or delete on checagem for each row execute function registra_auditoria();
create trigger proposta_audit after insert or update or delete on proposta for each row execute function registra_auditoria();
create trigger quiz_posicao_audit after insert or update or delete on quiz_posicao for each row execute function registra_auditoria();
create trigger quiz_pergunta_audit after insert or update or delete on quiz_pergunta for each row execute function registra_auditoria();
create trigger correcao_audit after insert or update or delete on correcao for each row execute function registra_auditoria();
create trigger agencia_audit after insert or update or delete on agencia_checagem for each row execute function registra_auditoria();
create trigger editor_audit after insert or update or delete on editor for each row execute function registra_auditoria();

-- A evidência nunca é alterada depois de gravada (exceto o estado do link)
create or replace function evidencia_imutavel() returns trigger
language plpgsql as $$
begin
  if new.url_original is distinct from old.url_original
     or new.sha256 is distinct from old.sha256
     or new.capturado_em is distinct from old.capturado_em then
    raise exception 'Evidência é imutável';
  end if;
  return new;
end $$;
create trigger evidencia_imutavel before update on evidencia for each row execute function evidencia_imutavel();
create trigger evidencia_sem_delete before delete on evidencia for each row execute function bloqueia_alteracao();

-- -----------------------------------------------------------------------------
-- Segurança: RLS
-- Público (anon) não lê nada direto do banco: o site é gerado no build.
-- Editores autenticados leem tudo e editam só tabelas editoriais.
-- ETL usa a service role (ignora RLS).
-- -----------------------------------------------------------------------------
create or replace function papel_atual() returns papel_editor
language sql stable security definer set search_path = public as $$
  select papel from editor where user_id = auth.uid() and ativo
$$;

do $$
declare t text;
begin
  foreach t in array array[
    'evidencia','pessoa','eleicao','candidatura','bem','arquivo_tse','arquivo_pagina','contas_campanha',
    'maior_doador','mandato','tema','parlamentar','proposicao','votacao','voto','presenca','despesa_cota',
    'emenda','editor','processo','processo_parte','certidao_analise','agencia_checagem','checagem',
    'proposta','quiz_pergunta','quiz_pergunta_votacao','quiz_posicao','indicador','indicador_valor',
    'periodo_governo','correcao','changelog_publico','etl_execucao','audit_log'
  ] loop
    execute format('alter table %I enable row level security', t);
    execute format('create policy %I on %I for select to authenticated using (papel_atual() is not null)', t || '_leitura_editor', t);
  end loop;

  foreach t in array array[
    'processo','processo_parte','checagem','proposta','quiz_pergunta','quiz_pergunta_votacao','quiz_posicao',
    'agencia_checagem','votacao','mandato','changelog_publico'
  ] loop
    execute format('create policy %I on %I for insert to authenticated with check (papel_atual() is not null)', t || '_insert_editor', t);
    execute format('create policy %I on %I for update to authenticated using (papel_atual() is not null) with check (papel_atual() is not null)', t || '_update_editor', t);
  end loop;
end $$;

create policy correcao_update_editor on correcao for update to authenticated
  using (papel_atual() is not null) with check (papel_atual() is not null);
create policy editor_admin on editor for all to authenticated
  using (papel_atual() = 'admin') with check (papel_atual() = 'admin');
create policy parlamentar_vinculo_editor on parlamentar for update to authenticated
  using (papel_atual() is not null) with check (papel_atual() is not null);

-- Revisores: somente papel revisor/admin pode assinar como revisor
create or replace function valida_papel_revisor() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is not null
     and (new.revisor_1 is distinct from old.revisor_1 or new.revisor_2 is distinct from old.revisor_2) then
    if papel_atual() not in ('revisor', 'admin') then
      raise exception 'Somente revisores podem aprovar';
    end if;
    if (new.revisor_1 is distinct from old.revisor_1 and new.revisor_1 <> auth.uid())
       or (new.revisor_2 is distinct from old.revisor_2 and new.revisor_2 <> auth.uid()) then
      raise exception 'Revisor só pode assinar em seu próprio nome';
    end if;
  end if;
  return new;
end $$;
create trigger processo_papel before update on processo for each row execute function valida_papel_revisor();
create trigger checagem_papel before update on checagem for each row execute function valida_papel_revisor();
create trigger proposta_papel before update on proposta for each row execute function valida_papel_revisor();
create trigger quiz_posicao_papel before update on quiz_posicao for each row execute function valida_papel_revisor();
