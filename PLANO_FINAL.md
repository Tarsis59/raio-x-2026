# Plano Final — Plataforma Cívica Eleições 2026

> **REVISÃO 1.1 (27/09/2026) — decisões do dono do projeto, que prevalecem sobre o resto do documento:**
> 1. **Escopo total, sem cortes:** todos os candidatos, de todos os cargos, com todas as funcionalidades.
> 2. **Custo zero em infraestrutura.** Só a API do Claude é paga. A arquitetura oficial passa a ser a da seção **4-B**.
> 3. O parecer jurídico já está coberto pelo advogado eleitoral do projeto.
> 4. O nome do produto será definido depois (por enquanto, "Raio-X 2026").

## 4-B. Arquitetura custo zero (oficial)

| Necessidade | Serviço gratuito | Limite relevante | Como contornamos |
|---|---|---|---|
| Site público | **Cloudflare Pages** (export estático do Next.js 16) | Banda e requisições ilimitadas para estático; 20.000 arquivos por deploy; 500 deploys/mês | Páginas pré-renderizadas para Presidente, Governador e Senador. Deputados em rota única `/candidato/?id=` lendo *shards* JSON (≈3.000 arquivos, 10 candidatos cada) |
| Proteção | Cloudflare (DNS, WAF básico, anti-DDoS, **Turnstile**) | — | Turnstile no formulário de correção |
| Banco | **Supabase Free** (Postgres) | 500 MB, pausa após 7 dias sem uso, 5 GB de saída por mês | O site não lê o banco em tempo real: lê só no build. Os crons diários mantêm o projeto ativo |
| Formulários e painel | Supabase Auth + RLS + Edge Functions | 50 mil usuários ativos por mês; 500 mil chamadas de função por mês | Uso mínimo: só correções e o painel editorial |
| Evidências imutáveis | **Internet Archive** (Wayback SavePageNow + itens no archive.org via API S3) | Gratuito e permanente | Hash SHA-256 guardado no banco; o arquivo fica no archive.org |
| Orquestração | **GitHub Actions** (repositório público = minutos ilimitados) | — | Crons de ETL, build e deploy |
| Fontes do TSE | O Akamai bloqueia clientes que não são navegador (confirmado em 27/09) | — | Coleta via **Playwright (Chromium real)**. Se o TSE também bloquear os IPs do GitHub (EUA), roda um *runner* do GitHub na máquina do projeto, no Brasil, também de graça |
| Checagens | Google Fact Check Tools API | Gratuita, com chave | — |
| Erros e uso | Sentry (plano Developer) + Cloudflare Web Analytics (sem cookies) | Gratuitos | — |
| IA | **Claude API (paga)** | — | Extração com citação literal validada; cache por hash do documento (nunca reprocessa o mesmo PDF) |

**Fato verificado em 27/09/2026:** a API do DivulgaCandContas responde normalmente em navegador. A eleição de 2026 tem id `20322002026` e há 14 candidaturas à Presidência listadas.

> Versão 1.0 · 27/09/2026 · Documento-mestre de produto, dados, arquitetura, jurídico e execução.
> Nome provisório do produto: **"Raio-X 2026"** (trocar livremente).

---

## 0. Leitura obrigatória: o calendário mudou o plano

Hoje é **27/09/2026**. O 1º turno é **04/10/2026** (7 dias) e o 2º turno é **25/10/2026** (28 dias).
O roadmap original de 12 semanas **não cabe** antes da eleição. Em vez de cortar qualidade, este plano corta **escopo** e aproveita um fato a nosso favor: depois do 1º turno o universo encolhe para 2 candidatos à Presidência e poucos governadores em 2º turno.

| Trilha | Janela | Entrega | Escopo |
|---|---|---|---|
| **T0 — Fundação** | 27/09 → 04/10 | Repositório, banco, ETL do TSE/BCB/IBGE, design system, perfis com dados **100% objetivos** (sem jurídico, sem IA) em ambiente de preview | Presidente + Governadores (todos) |
| **T1 — Lançamento 2º turno** | 05/10 → 12/10 | **Go-live público** com Raio-X completo, Comparador, Dashboard Macro, Bússola | Apenas candidatos no 2º turno (Pres. + UFs com 2º turno) |
| **T2 — Consolidação** | 13/10 → 25/10 | Tempo real de correções, testes de carga, monitoramento 24/7 até a eleição | Idem |
| **T3 — Plataforma permanente** | Nov/2026 → 2028 | "Monitor de Mandatos" dos eleitos (promessa × entrega), Senado/Câmara, base para Municipais 2028 | Eleitos 2026 |

**Decisão:** não lançar perfis jurídicos/controversos antes do 1º turno. Um erro nessa semana é o cenário de maior risco jurídico e reputacional do projeto. Dados objetivos (bens, carreira, votações, indicadores) podem ir ao ar em T0 se estiverem prontos e auditados.

---

## 1. Princípios não-negociáveis (a "Constituição" do produto)

1. **Nenhuma opinião própria.** A plataforma organiza dados públicos; nunca adjetiva, ranqueia "melhor/pior" ou recomenda voto.
2. **Toda afirmação tem evidência.** Nenhum dado vai ao ar sem `evidencia_id` → URL oficial + cópia arquivada + hash SHA-256 + data/hora de captura.
3. **Isonomia visual e algorítmica.** Mesmo layout, mesmos campos, mesmo tamanho de foto, mesma ordem de seções para todos. Campos vazios aparecem como "Sem registro público encontrado" — nunca somem (sumir favorece).
4. **Ordenação neutra.** Listas de candidatos em **ordem alfabética do nome de urna** (padrão) ou **aleatória com semente por sessão** (opção). **Não** ordenar por pesquisa eleitoral (cria efeito manada e é o ponto mais atacável perante o TSE).
5. **IA só resume, nunca julga** — e todo texto gerado por IA é rotulado e revisado por humano antes de publicar.
6. **Humano no circuito para tudo que é sensível.** Dados objetivos publicam automaticamente após testes de qualidade; processos judiciais, fact-checks e posições do quiz exigem **revisão em dupla (4 olhos)**.
7. **Privacidade por design.** Sem login para o público, sem cookies de rastreamento, respostas do quiz **nunca saem do navegador**.
8. **Correção rápida e pública.** Todo perfil tem "Reportar erro"; correções têm SLA e ficam registradas num changelog público.

---

## 2. Blindagem jurídica (revisada e ampliada)

### 2.1 Pontos que o plano original não cobria — e são críticos

| Risco | Base legal | Mitigação no produto |
|---|---|---|
| **Enquete eleitoral proibida** | Lei 9.504/97 art. 33 §5º; Res. TSE 23.600/2019 | O quiz **nunca** publica agregados ("X% dos usuários se alinham a Fulano"). Resultado é individual, calculado no navegador, não armazenado. Sem ranking público, sem contador. |
| **Dado sensível (opinião política)** | LGPD art. 5º II e art. 11 | Quiz 100% client-side. Nenhuma resposta vai ao servidor. Analytics não registra eventos com respostas. |
| **Conteúdo gerado por IA** | Res. TSE 23.610/2019 alterada pela 23.732/2024 (rotulagem de IA, vedação a deepfake) | Selo "Resumo gerado por IA e revisado por equipe editorial" + link para trecho original. Nenhuma imagem/áudio/vídeo sintético. |
| **Impulsionamento pago** | Lei 9.504 art. 57-C (só candidatos/partidos podem impulsionar conteúdo eleitoral) | **Proibido** patrocinar posts sobre candidatos específicos. Divulgação paga só institucional ("conheça a plataforma"), sem nomes/fotos — validar com advogado. |
| **Direito de resposta / difamação** | Lei 9.504 art. 58; CP arts. 138-140 | Canal de correção com SLA de 24h (48h fora do período crítico); resposta do candidato publicada junto ao item contestado, quando documentada. |
| **Responsabilidade por conteúdo** | Marco Civil arts. 15 e 19 | Guarda de logs de acesso ao painel administrativo por 6 meses; logs de edição imutáveis permanentes. |
| **Propaganda disfarçada** | Res. TSE 23.610 | Nenhuma call-to-action de voto; nenhuma cor partidária; mesma estrutura para todos. |

### 2.2 Régua de admissibilidade judicial (mantida e detalhada)

Só entram processos com **número CNJ** (NNNNNNN-DD.AAAA.J.TR.OOOO) e um destes status formais:

| Status | Rótulo exibido | Cor (neutra) |
|---|---|---|
| Denúncia/queixa **recebida** | "Réu em ação penal — sem condenação" | cinza |
| Condenação 1ª instância | "Condenado em 1ª instância — cabe recurso" | cinza-escuro |
| Condenação 2ª instância / órgão colegiado | "Condenado por órgão colegiado — cabe recurso" | grafite |
| Trânsito em julgado | "Condenação definitiva" | grafite |
| Absolvição / anulação / prescrição / extinção | "Absolvido" / "Processo anulado" / "Punibilidade extinta (prescrição)" | cinza-claro |
| Ação de improbidade / ACP | Mesma régua, rótulo "Ação cível" | — |

**Não entram:** inquéritos, notícias de investigação, delações não homologadas, processos arquivados sem decisão de mérito, processos em segredo de justiça.

**Regra da presunção de inocência:** todo item não transitado em julgado exibe a frase fixa *"Presunção de inocência — decisão ainda pode ser revista (CF art. 5º, LVII)."*

**Realidade técnica importante:** a API pública do **DataJud (CNJ)** não expõe nomes das partes. Portanto a vinculação processo ↔ candidato é **curadoria editorial**: o número do processo vem de fonte documental (certidões anexadas ao registro de candidatura no TSE, decisões publicadas, diários oficiais) e o DataJud é usado **automaticamente** apenas para acompanhar movimentações daquele número.

### 2.3 Fact-checking

- Fonte primária automatizada: **Google Fact Check Tools API** (marcação ClaimReview), filtrada por uma *allowlist* de publicadores.
- A allowlist é uma **tabela no banco** (`agencia_checagem`) com o status de signatário IFCN verificado na data (ex.: Lupa, Aos Fatos, Estadão Verifica, UOL Confere, AFP Checamos) — revalidada mensalmente contra a lista oficial da IFCN. Nunca fixar a lista no código.
- Matching checagem ↔ candidato: automático por nome + revisão humana obrigatória.

### 2.4 Governança jurídica

- [ ] Parecer de advogado eleitoral **antes do go-live** (checklist em `docs/juridico/checklist-go-live.md`).
- [ ] Pessoa jurídica responsável (CNPJ) + expediente/"Quem somos" + metodologia pública.
- [ ] Termos de Uso, Política de Privacidade, Política Editorial, Política de Correções (todas públicas).
- [ ] Encarregado de dados (DPO) nomeado e e-mail de contato.
- [ ] Declaração pública de financiamento e de independência (quem paga o projeto).

---

## 3. Fontes de dados (mapeamento técnico real)

| Domínio | Fonte | Acesso | Frequência | Publicação |
|---|---|---|---|---|
| Candidaturas, bens, fotos, certidões, planos de governo | **Portal de Dados Abertos do TSE** (CSV em lote: `consulta_cand`, `bem_candidato`, `consulta_cand_complementar`) + **DivulgaCandContas** (JSON para fotos/PDFs) | Download em lote; JSON sem chave | Diária (6h) no período eleitoral | Automática |
| Histórico eleitoral (2002–2024) | Dados Abertos TSE (anos anteriores) | Lote, uma vez | Única + reconciliação | Automática após *identity match* revisado |
| Receitas/despesas de campanha | Dados Abertos TSE — prestação de contas | Lote | Diária | Automática |
| Votações e presença (Câmara) | **API Dados Abertos Câmara** v2 | REST sem chave | Diária | Automática |
| Votações (Senado) | **API Dados Abertos Senado** | REST/XML sem chave | Diária | Automática |
| Cota parlamentar (CEAP) | API Câmara / Senado (CEAPS) | REST | Semanal | Automática |
| Emendas, convênios, contratos | **Portal da Transparência (CGU)** | REST **com chave** (header `chave-api-dados`), rate limit | Semanal | Automática |
| Processos | **DataJud (CNJ)** — API pública Elasticsearch com chave pública | REST | Diária (só números já curados) | **Revisão humana** |
| Inflação, juros, dívida | **BCB SGS**: IPCA 433, Meta Selic 432, DBGG %PIB 13762 | REST sem chave | Diária | Automática |
| Desemprego, PIB | **IBGE SIDRA** (PNAD Contínua t. 6381; PIB t. 5932) | REST sem chave | Mensal/trimestral | Automática |
| Emprego formal | **Novo CAGED (MTE/PDET)** | Arquivos mensais | Mensal | Automática |
| Checagens | Google Fact Check Tools API | REST com chave | A cada 6h | **Revisão humana** |
| Posições para o quiz | Planos de governo (TSE), votações nominais, entrevistas/debates com vídeo oficial | Pipeline IA + humano | Contínua | **Revisão humana (4 olhos)** |

> Os códigos de séries/tabelas acima devem ser confirmados no primeiro dia de ETL (teste automatizado que falha se o metadado da série mudar).

**Identidade entre eleições:** o TSE não publica CPF aberto. A pessoa é resolvida por `SQ_CANDIDATO` + nome civil + data de nascimento + UF/município de nascimento, com *score* de confiança; matches abaixo de 100% vão para a fila de revisão.

---

## 4. Arquitetura (simplificada para robustez e custo)

O desenho original tem peças demais para o prazo (Airflow + FastAPI + Node + Redis + MinIO). Mesma capacidade com menos pontos de falha:

```
┌──────────────────────── Fontes públicas ────────────────────────┐
│ TSE · Câmara · Senado · CGU · DataJud · BCB · IBGE · CAGED · CR  │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
  ETL Python 3.12 (uv) · httpx · polars · pydantic · Playwright só p/ PDFs/prints
  Orquestração: GitHub Actions (cron) → jobs idempotentes com checkpoint
                               ▼
  Camada RAW (Supabase Storage)  → arquivo original + SHA-256 + captured_at
  Wayback SavePageNow            → cópia pública independente
                               ▼
  PostgreSQL 16 (Supabase, região São Paulo)
   schemas: raw · staging · core · editorial · audit
   testes de qualidade de dados (pydantic + SQL asserts) — falhou, não publica
                               ▼
  Pipeline IA (Claude API, citações de PDF) → rascunho em editorial.*
  Validação automática: citação literal precisa existir no texto do PDF
                               ▼
  Painel Editorial (/admin, Supabase Auth + MFA, RLS, revisão 4 olhos)
                               ▼
  Next.js 15 (App Router, RSC) — páginas estáticas + ISR
  Revalidação sob demanda disparada pelo ETL/painel (revalidateTag)
                               ▼
  Vercel (edge/CDN, região gru1) + Cloudflare (DNS, WAF, rate limit, anti-DDoS)
```

**Por que assim**
- **Sem API separada nem Redis no MVP:** 99% do tráfego é leitura de páginas que mudam poucas vezes por dia → HTML estático em CDN aguenta picos de milhões de acessos a custo quase zero. Route Handlers do Next cobrem as poucas rotas dinâmicas.
- **GitHub Actions em vez de Airflow:** zero infraestrutura, logs versionados, retry nativo. Migra para Dagster/Prefect em T3 se o volume exigir.
- **Supabase** entrega Postgres + Storage (substitui MinIO/S3) + Auth do painel + RLS em um só serviço.
- **Tudo versionado:** tabelas `core` têm histórico (`valid_from/valid_to`) — o site pode mostrar "como este perfil estava em 01/10".

### 4.1 Stack definitiva

| Camada | Escolha |
|---|---|
| Monorepo | pnpm + Turborepo |
| Web | Next.js 15, React 19, TypeScript estrito, Tailwind CSS v4, shadcn/ui (Radix) |
| Gráficos | Recharts (via shadcn/charts) + visx para gráficos custom (linha do tempo, patrimônio) |
| Animação | Motion (framer), sempre respeitando `prefers-reduced-motion` |
| ORM | Drizzle ORM + migrações SQL versionadas |
| ETL | Python 3.12, uv, httpx, polars, pydantic v2, pdfplumber, Playwright |
| IA | Claude API (`claude-sonnet-5` para extração com citações; `claude-haiku-4-5` para classificação barata) |
| Busca | Postgres full-text (`unaccent` + `pg_trgm`) — suficiente para nomes/temas |
| Observabilidade | Sentry (erros), Better Stack/UptimeRobot (uptime), Umami self-host ou Plausible (analytics sem cookies) |
| Testes | Vitest, Playwright (E2E em viewports mobile/desktop), pytest, Lighthouse CI, k6 |
| CI/CD | GitHub Actions: lint → typecheck → testes → build → preview Vercel → produção com aprovação |

### 4.2 Estrutura do repositório

```
raio-x-2026/
├─ apps/web/                 # Next.js (site público + /admin)
│  ├─ app/(public)/          # home, candidato/[slug], comparar, economia, bussola, metodologia
│  ├─ app/admin/             # fila de revisão, editor de evidências, correções
│  └─ components/            # design system
├─ packages/db/              # schema Drizzle, migrações, seeds
├─ packages/core/            # tipos compartilhados, algoritmo do quiz (testado)
├─ etl/                      # jobs Python (um módulo por fonte)
│  ├─ sources/tse, camara, senado, cgu, datajud, bcb, ibge, caged, factcheck
│  ├─ evidence/              # arquivamento + hash + Wayback
│  ├─ ai/                    # extração com citação + validador literal
│  └─ quality/               # testes de dados
├─ docs/                     # manual editorial, metodologia, jurídico, runbooks
└─ .github/workflows/        # CI + crons do ETL
```

---

## 5. Modelo de dados (núcleo)

```
pessoa(id, nome_civil, nome_urna_atual, nascimento, slug, foto_evidencia_id)
candidatura(id, pessoa_id, ano, cargo, uf, partido, numero, situacao, sq_candidato_tse, coligacao)
mandato(id, pessoa_id, cargo, esfera, uf, inicio, fim, origem_evidencia_id)
bem_declarado(id, candidatura_id, tipo, descricao, valor_nominal, valor_corrigido_ipca, evidencia_id)
receita_campanha / despesa_campanha(...)
proposicao(id, casa, sigla, numero, ano, ementa, tema_id)
votacao(id, proposicao_id, casa, data, descricao, resultado, evidencia_id)
voto_parlamentar(votacao_id, pessoa_id, voto)            -- Sim/Não/Abst/Obstrução/Ausente
processo(id, numero_cnj, tribunal, classe, assunto, status_regua, ultima_movimentacao, publicado)
processo_parte(processo_id, pessoa_id, polo, evidencia_vinculo_id)
fact_check(id, agencia_id, url, claim, rating_original, data, pessoa_id, tema_id, publicado)
tema(id, eixo, nome)                                      -- Economia, Previdência, Agro/Ambiente, Educação/Saúde...
proposta(id, candidatura_id, tema_id, resumo_ia, trecho_literal, pagina, evidencia_id, status_revisao)
quiz_pergunta(id, tema_id, texto, contexto_neutro, ordem, ativa)
quiz_posicao(pergunta_id, pessoa_id, valor [-2..2] | null, justificativa, evidencia_id, revisor_1, revisor_2)
indicador(id, codigo_fonte, nome, unidade, fonte); indicador_valor(indicador_id, data, valor, uf?)
periodo_governo(id, pessoa_id?, cargo, uf, inicio, fim)
evidencia(id, tipo_fonte, url_original, url_wayback, storage_path, sha256, mime, captured_at, capturado_por)
correcao(id, entidade, entidade_id, solicitante_tipo, descricao, anexos, status, sla_limite, resolucao)
audit_log(id, ator, acao, entidade, antes jsonb, depois jsonb, ts)   -- append-only (trigger bloqueia UPDATE/DELETE)
```

Regras de banco:
- `CHECK` que impede `publicado = true` sem `evidencia_id` e sem dois revisores distintos (onde aplicável).
- RLS: público só lê views `public_*` com `publicado = true`.
- Valores monetários de bens exibidos **nominal e corrigido pelo IPCA** (com a série e a data-base explícitas).

---

## 6. Repositório imutável de evidências

Para cada URL citada:
1. Download do original (HTML/PDF) → SHA-256 → Supabase Storage em caminho endereçado por hash (`evidencias/ab/cd/<sha256>.pdf`), bucket sem permissão de sobrescrita.
2. Screenshot de página inteira (Playwright) para páginas HTML.
3. Envio ao **Wayback Machine (SavePageNow)** com fila e retry (respeitar limite de taxa).
4. Registro em `evidencia` com `captured_at` em UTC.
5. Job semanal de **verificação de links**: se o original sumir, o site passa a exibir a cópia arquivada automaticamente com aviso "Fonte original indisponível desde DD/MM".

Na interface, cada dado tem um ícone "fonte" que abre: link original · cópia arquivada · hash · data de captura.

---

## 7. Pipeline de IA com guardrails

Uso restrito: **extrair e resumir** planos de governo e mapear trechos aos temas do comparador/quiz.

1. PDF do plano (do TSE) → Claude API com o documento anexado e **citações habilitadas** (a API devolve página/trecho de onde veio cada frase).
2. Prompt de sistema: proibido adjetivar, avaliar viabilidade, comparar candidatos ou inferir intenções; saída em JSON estrito (`tema`, `resumo ≤ 280 caracteres`, `trechos_literais[]`, `paginas[]`, `sem_mencao: bool`).
3. **Validador determinístico** (não-IA): cada `trecho_literal` precisa existir no texto extraído do PDF (normalizado). Falhou → descartado.
4. **Linter de neutralidade**: lista de termos proibidos no resumo (ex.: "ousado", "irresponsável", "melhor", "populista") → falhou, volta.
5. Revisão humana no painel lado a lado (PDF ↔ resumo) → publica com selo de IA.
6. Tema sem menção no plano: exibe "O plano protocolado não menciona este tema" (isonomia).
7. Configuração determinística (temperatura mínima suportada), prompt e versão do modelo gravados em cada registro para auditoria.

---

## 8. Funcionalidades (especificação de produto)

### 8.1 Home
- Busca instantânea (nome de urna, partido, UF, cargo).
- Seletor de cargo/UF. Grade de candidatos em ordem alfabética, cartões idênticos.
- Faixa fixa "Como funciona / Metodologia" e "Última atualização dos dados: DD/MM HH:MM".

### 8.2 Raio-X do Candidato (`/candidato/[slug]`)
Abas (mesma ordem para todos): **Resumo · Trajetória · Patrimônio · Propostas · Votações · Justiça · Checagens · Campanha · Fontes**
- **Trajetória:** linha do tempo vertical interativa (cargos, mandatos, eleições disputadas, projetos de autoria sancionados/vetados).
- **Patrimônio:** gráfico de evolução por eleição (nominal × corrigido IPCA), tabela de bens por categoria; sem juízo — só números e variação %.
- **Votações:** matérias-chave curadas (lista pública e fixa por tema, definida antes de ver os votos) + presença + CEAP.
- **Justiça:** "Processos ativos" e "Concluídos" conforme régua da seção 2.2; número CNJ clicável; última movimentação com data.
- **Checagens:** cartões das agências com o rótulo original da agência (não reinterpretar).
- **Campanha:** receitas por origem, maiores doadores PJ/PF conforme TSE, despesas por categoria.
- **Fontes:** todas as evidências do perfil + changelog público do perfil.
- Botões: "Comparar", "Compartilhar" (imagem OG neutra gerada dinamicamente), "Reportar erro".

### 8.3 Comparador Temático (`/comparar`)
- Até 4 candidatos (desktop) / 2 com swipe horizontal (celular).
- Eixos: Economia & Tributação · Previdência & Trabalho · Agro & Meio Ambiente · Educação & Saúde · Segurança Pública · Governança & Combate à Corrupção.
- Cada célula: resumo + trecho literal + página + votos históricos relacionados.
- URL compartilhável (`/comparar?c=a,b&tema=economia`).

### 8.4 Dashboard Macroeconômico (`/economia`)
- Séries: IPCA 12m, Selic meta, DBGG % PIB, desemprego PNAD, saldo CAGED, PIB.
- Faixas de governo sombreadas por período, **todas na mesma cor neutra** com rótulo de texto.
- Aviso fixo de metodologia: *"Indicadores refletem múltiplos fatores (cenário externo, Congresso, choques). A sobreposição de mandatos não indica causalidade."*
- Comparação por mandato com **janelas iguais** (ex.: variação acumulada nos primeiros 48 meses).
- Estados: apenas indicadores com recorte por UF disponível (desemprego PNAD por UF, CAGED por UF); IPCA só onde há região metropolitana medida — sinalizar ausência.
- Download CSV de todas as séries (transparência total).

### 8.5 Bússola de Afinidade (`/bussola`)
- 20 perguntas, balanceadas por eixo (cada eixo com o mesmo nº), redação revisada por 2 pessoas de orientações diferentes, com contexto neutro de 1 linha e "o que dizem os dois lados".
- Resposta em 5 níveis (Discordo totalmente → Concordo totalmente) + "Pular" + peso de importância (1–3).
- **Algoritmo (em `packages/core`, 100% testado):**
  - Para cada pergunta *i* com resposta do usuário `uᵢ` e posição documentada do candidato `cᵢ` (ambos em −2..+2):
    `afinidadeᵢ = 1 − |uᵢ − cᵢ| / 4`
  - `score = Σ wᵢ·afinidadeᵢ / Σ wᵢ` apenas sobre perguntas com posição documentada.
  - `cobertura = nº perguntas com posição / nº perguntas respondidas`. Se cobertura < 60%, exibe "Dados insuficientes" em vez do percentual.
  - Posição **sem evidência** = `null` (não conta, não penaliza) e aparece como "Sem posição pública documentada".
- Resultado: lista de afinidade com detalhamento por pergunta (convergência/divergência + link da evidência da posição).
- Execução client-side; nada é enviado; opção "baixar meu resultado (imagem)" gerada localmente.
- Texto fixo: *"Isto não é pesquisa eleitoral nem recomendação de voto."*

### 8.6 Páginas institucionais
Metodologia · Política editorial · Régua judicial · Correções (log público) · Quem somos/financiamento · Privacidade · Termos · Dados abertos (download do dataset).

### 8.7 Painel editorial (`/admin`)
- Login Supabase Auth + MFA obrigatório; papéis: `editor`, `revisor`, `admin`.
- **Fila de revisão** (itens novos do ETL/IA), **diff visual** do que mudou desde a última publicação.
- Regra 4 olhos: quem criou não aprova.
- Fila de correções com SLA e cronômetro.
- Botão "despublicar de emergência" (1 clique, registrado no audit log, revalida o CDN em segundos).

---

## 9. Design premium, neutro e 100% responsivo

**Direção visual:** editorial/jornalística de alto padrão (referências de qualidade: The Pudding, FT Visual, Our World in Data) — sóbria, legível, dados em primeiro plano.

- **Paleta:** base monocromática (grafite `#111418`, cinzas neutros, off-white `#FAFAF7`) + **um único acento não partidário** usado só em interação (links/foco). Nenhuma cor de candidato: candidatos são identificados por **foto + nome**, nunca por cor. Em gráficos multi-candidato, paleta categórica neutra atribuída por ordem alfabética (não pelo partido).
- **Tipografia:** Inter (UI) + uma serifada editorial para títulos (ex.: Source Serif 4); números tabulares em tabelas/gráficos.
- **Modo claro/escuro** automático + manual.
- **Mobile-first real:**
  - Navegação inferior fixa no celular (Início · Comparar · Bússola · Economia).
  - Abas do perfil viram *chips* roláveis com *sticky header*.
  - Tabelas viram cartões empilhados < 640px.
  - Gráficos com tooltip por toque, alvos ≥ 44px, pinça desabilitada em gráficos (evita conflito com scroll).
  - Comparador com swipe e indicador de posição.
- **Acessibilidade WCAG 2.2 AA:** contraste verificado, navegação por teclado, leitores de tela (gráficos com tabela alternativa), `prefers-reduced-motion`, linguagem simples.
- **Performance (orçamento travado no CI):** LCP < 2,0s em 4G, CLS < 0,05, INP < 200ms, JS inicial < 150 KB; imagens AVIF/WebP via `next/image`; fontes self-hosted com `font-display: swap`.
- **SEO/compartilhamento:** `schema.org/Person` e `Dataset`, sitemap, OG images dinâmicas neutras por candidato, URLs em português.

---

## 10. Automação (o que roda sozinho)

| Job (GitHub Actions cron, horário de Brasília) | Frequência | Publica sozinho? |
|---|---|---|
| `tse-candidaturas` (cadastro, situação, bens, fotos, planos) | 06:00 diário | Sim (dados objetivos) |
| `tse-contas` (receitas/despesas) | 07:00 diário | Sim |
| `camara-senado` (votações, presença, CEAP) | 05:00 diário | Sim |
| `bcb-ibge-caged` (indicadores) | 08:00 diário | Sim |
| `cgu-transparencia` (emendas, convênios) | Domingo 03:00 | Sim |
| `datajud-movimentacoes` (só processos curados) | 04:00 diário | **Não** → fila de revisão |
| `factcheck-claimreview` | a cada 6h | **Não** → fila de revisão |
| `ai-planos` (novo/alterado plano de governo) | ao detectar hash novo | **Não** → fila de revisão |
| `evidencias-linkcheck` + Wayback | Diário | Sim (troca para cópia arquivada) |
| `backup-db` (dump criptografado fora do Supabase) | 02:00 diário | — |

Garantias de automação:
- Jobs **idempotentes** (reexecutar não duplica), com *upsert* por chave natural.
- **Portão de qualidade:** cada job roda testes (contagem mínima de registros, schema, variações absurdas — ex.: patrimônio que mudou 1000× → segura e alerta). Falhou → nada publica, alerta no Slack/Telegram/e-mail.
- Detecção de mudança por hash do arquivo-fonte (só processa o que mudou).
- Após publicar, o job chama o endpoint de revalidação do Next (`revalidateTag`) → site atualizado em segundos.
- Painel `/admin/status` com saúde de cada job, última execução, próximos horários.

---

## 11. Segurança e resiliência para o pico eleitoral

- Cloudflare na frente: WAF gerenciado, rate limit em rotas dinâmicas, proteção DDoS, "Under Attack Mode" pronto para ativar.
- Site público 100% estático/ISR → se o banco cair, o site continua no ar (servindo a última versão).
- Painel admin fora do cache, com MFA e allowlist opcional de IP.
- Segredos só em GitHub/Vercel secrets; rotação antes do go-live.
- Headers: CSP estrita, HSTS, `X-Frame-Options`, `Referrer-Policy`.
- Dependabot + `pnpm audit`/`pip-audit` no CI.
- **Teste de carga (k6):** meta de 5.000 req/s sustentado no CDN e 50 req/s nas rotas dinâmicas sem erro.
- **Runbooks** em `docs/runbooks/`: site fora do ar, dado errado publicado, ataque, pedido judicial de remoção, fonte oficial mudou de formato.
- Plantão definido para 04/10 e 25/10 (e noites anteriores).

---

## 12. Qualidade e testes (critério de "sem erros")

| Camada | Teste | Portão |
|---|---|---|
| Algoritmo do quiz | Vitest com casos-limite (tudo nulo, pesos, empate, cobertura) | 100% de cobertura de linhas |
| ETL | pytest com fixtures reais gravadas de cada fonte | Obrigatório no CI |
| Dados | Testes de qualidade a cada execução | Bloqueia publicação |
| UI | Playwright E2E em iPhone SE, iPhone 15, Pixel 7, iPad, 1440px desktop | Obrigatório no CI |
| Visual | Screenshots de regressão dos componentes principais | Revisão no PR |
| Acessibilidade | axe-core no Playwright | Zero violações sérias |
| Performance | Lighthouse CI | ≥ 95 Performance/A11y/SEO/Best Practices |
| Carga | k6 | Metas da seção 11 |
| Isonomia | Teste automatizado: todo perfil renderiza exatamente as mesmas seções | Obrigatório |
| Neutralidade | Linter de termos proibidos em todo texto publicado | Obrigatório |

---

## 13. Cronograma executável detalhado

### T0 — Fundação (27/09 → 04/10)
- **D1:** monorepo, CI, Supabase (São Paulo), Vercel, Cloudflare, domínio; schema v1 + RLS + audit log.
- **D2:** ETL TSE (candidaturas, bens, fotos, planos) + camada de evidências.
- **D3:** ETL BCB/IBGE/CAGED; ETL Câmara/Senado; testes de qualidade.
- **D4:** design system (tokens, tipografia, componentes base, dark mode), layout mobile/desktop.
- **D5:** páginas Home + Perfil (abas objetivas: Resumo, Trajetória, Patrimônio, Votações, Campanha, Fontes).
- **D6:** Dashboard Economia; painel admin v1 (fila + 4 olhos).
- **D7:** manual editorial, régua judicial, metodologia; revisão jurídica agendada. *Opcional:* soft-launch só com dados objetivos se todos os portões de qualidade passarem.

### T1 — Lançamento 2º turno (05/10 → 12/10)
- **05/10:** congelar lista dos candidatos no 2º turno; curadoria jurídica e checagens desses nomes (dupla revisão).
- **06–07/10:** pipeline IA dos planos + Comparador.
- **08–09/10:** Bússola (perguntas revisadas, posições documentadas com evidência, algoritmo testado).
- **10/10:** Lighthouse, acessibilidade, E2E, k6, pentest básico.
- **11/10:** parecer jurídico final + correções.
- **12/10:** **go-live**.

### T2 — Operação (13/10 → 25/10)
- Monitoramento 24/7, SLA de correções, atualizações diárias automáticas, congelamento de features a partir de 20/10 (só correções).

### T3 — Plataforma permanente (nov/2026 em diante)
- "Monitor de Mandatos": promessas do plano × ações do governo eleito.
- Senadores e deputados federais eleitos (dados objetivos automáticos).
- API pública de dados abertos + download do dataset completo.
- Preparação para **Municipais 2028**.

---

## 14. Custos estimados (mensal, período eleitoral)

| Item | Estimativa |
|---|---|
| Vercel Pro | US$ 20 + excedentes de banda |
| Supabase Pro | US$ 25 (+ storage) |
| Cloudflare | Free/Pro US$ 20 |
| Claude API (planos de governo, uma passada + reprocessos) | US$ 20–100 |
| Sentry / Uptime / Analytics | US$ 0–50 |
| **Total infraestrutura** | **≈ US$ 100–250/mês** |
| Advogado eleitoral (parecer) | À parte — item mais importante do orçamento |

---

## 15. Riscos principais e resposta

| Risco | Prob. | Impacto | Resposta |
|---|---|---|---|
| Publicar processo/checagem errado | Média | Crítico | 4 olhos, régua fixa, despublicação em 1 clique, SLA 24h |
| Acusação de parcialidade | Alta | Alto | Metodologia pública, ordem alfabética, isonomia testada, changelog público |
| Fonte oficial muda formato/cai | Média | Médio | Testes de schema, fallback para último dado bom, alerta |
| Pico de tráfego/ataque | Média | Alto | Estático + CDN + WAF |
| Prazo | Alta | Alto | Escopo reduzido ao 2º turno; features não-críticas vão para T3 |
| Alucinação de IA | Média | Alto | Validador de citação literal + revisão humana; IA nunca publica sozinha |

---

## 16. Definição de pronto (go-live)

- [ ] Todos os candidatos do escopo com perfil completo e isonômico.
- [ ] 100% dos itens publicados com evidência arquivada + hash.
- [ ] 100% dos itens sensíveis com 2 revisores.
- [ ] Todos os testes do CI verdes; Lighthouse ≥ 95; zero violações axe sérias.
- [ ] k6 aprovado; runbooks escritos; plantão escalado.
- [ ] Parecer jurídico favorável e páginas institucionais publicadas.
- [ ] Canal de correções testado ponta a ponta.

---

## 17. Decisões que dependem de você (posso seguir com os padrões abaixo)

1. **Escopo de lançamento:** padrão = 2º turno (Presidente + governadores). Alternativa: tentar soft-launch objetivo antes de 04/10.
2. **Nome/domínio** do produto.
3. **Contas:** Supabase, Vercel, Cloudflare, GitHub, chave Claude API, chave Portal da Transparência, chave Google Fact Check.
4. **Equipe editorial:** quem serão os revisores (mínimo 2 pessoas) — a IA e a automação não substituem essa etapa.
5. **Advogado eleitoral** para o parecer antes do go-live.
