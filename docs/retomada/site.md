# Retomada — apps/web (Raio-X 2026, site público)

> Pausa geral pedida pelo dono do projeto em 27/09/2026. Nenhum servidor de dev/estático
> ou navegador foi deixado aberto por este agente (nenhum chegou a ser iniciado nesta sessão).
> Nenhum commit foi feito.

## Escopo vigente (mudou durante esta sessão — leia antes de continuar)

Decisão do dono, prevalece sobre o prompt original: o site cobre **apenas a eleição
presidencial 2026 — 14 candidaturas (com vices)**. Isso elimina do escopo:
seletor de cargo/UF, `/candidatos/[cargo]/[uf]` (virou `/candidatos`, lista única),
listas/paginação/virtualização de deputados, e a rota client-side `/candidato?id=`
(todos os 14 perfis são pré-renderizados em `/candidato/[slug]`). Comparador, Bússola
e Economia usam sempre a chave `presidente-br`.

## PRONTO

1. **Instalação/monorepo**: `pnpm install` na raiz rodou com sucesso (workspace `@raiox/core`
   linkado). `apps/web/package.json` atualizado:
   - dependency `"@raiox/core": "workspace:*"`.
   - scripts novos: `typecheck` (`tsc --noEmit`), `test` (`vitest run`),
     `dados:fixture` (copia fixtures → `public/dados`), `e2e` / `e2e:install`.
   - devDependencies novas: `@axe-core/playwright`, `@playwright/test`, `jsdom`, `serve`, `vitest`.
2. **`apps/web/next.config.ts`**: `output: 'export'`, `trailingSlash: true`,
   `images.unoptimized: true`, `transpilePackages: ['@raiox/core']`. Validado com
   `pnpm build` real (ver resultados abaixo) — gera `out/` com `dados/` copiado de `public/`.
3. **`apps/web/.gitignore`**: adicionado `/public/dados/` (nunca versionar dados gerados)
   e artefatos do Playwright (`/e2e/**/*.png`, `/playwright-report/`, `/test-results/`, `/blob-report/`).
4. **Gerador de fixtures — `apps/web/fixtures/gerar.ts`** (TypeScript, roda com
   `node --experimental-strip-types`, importa tipos direto de `@raiox/core/contrato`,
   determinístico via PRNG mulberry32 propositalmente semeado). Testado e funcionando.
   Produz `apps/web/fixtures/dados/`:
   - `meta.json` — `fixture: true`, eleição `{id: 20322002026, ano: 2026, data: "2026-10-04",
     segundoTurno: "2026-10-25"}`, `totais.porCargo.presidente = 14`, 5 fontes.
   - `lista/presidente-br.json` — 14 `CandidatoResumo`, **já em ordem alfabética** (não reordenar
     de novo na UI; "ordem aleatória" é um recurso de exibição client-side separado, com semente
     visível, ainda não implementado).
   - `c/{bucket}.json` — 14 perfis completos (`PerfilCandidato`), bucketados por
     `bucketDe(id)` (buckets atuais: 1, 4, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35, 38).
   - `comparar/presidente-br.json` — `ComparadorArquivo` com os 6 temas fixos
     (economia, previdencia, agro-ambiente, educacao-saude, seguranca, governanca) e os 14 candidatos + propostas.
   - `bussola/presidente-br.json` — 10 perguntas (`p1`..`p10`) balanceadas pelos 6 temas,
     14 candidatos com `posicoes` (uma candidata — sufixo "B" — tem ~90% de posições nulas,
     de propósito, para exercitar o caso "dados insuficientes" / cobertura < 60%).
   - `economia.json` — 8 indicadores nacionais (`ipca12m`, `selic`, `dbgg`, `desocupacao`,
     `caged`, `pib`, `dolar`, `resultado-primario`), séries mensais/trimestrais 2019–2026,
     e `periodos` com 3 mandatos presidenciais fictícios (2015–18, 2019–22, 2023–26).
   - `correcoes.json` — `CorrecoesArquivo` (3 itens de exemplo no changelog público).

   **Papéis fixos dos 14 candidatos** (nome de urna "Candidata/Candidato Exemplo A"…"N",
   ordem de criação — a ordem pública é sempre alfabética calculada na escrita):
   | Letra | Papel |
   |---|---|
   | A | Perfil rico + mandato legislativo anterior + processo `reu_acao_penal` |
   | B | **Perfil totalmente vazio** (isonomia — tudo "sem registro") |
   | C | `condenado_1a_instancia` |
   | D | `condenado_orgao_colegiado` + legislativo |
   | E | `condenado_transito_julgado` |
   | F | `absolvido` + legislativo |
   | G | `anulado` |
   | H | `punibilidade_extinta` |
   | I | `acao_civel_em_curso` + legislativo |
   | J | `acao_civel_procedente` |
   | K | `acao_civel_improcedente` + legislativo |
   | L | `reu_acao_penal` + certidão positiva/inconclusiva + 4 checagens |
   | M | Reeleição (`reeleicao: true`) + legislativo + doações ricas |
   | N | Registro limpo em Justiça (contraste isonômico com B — só a aba Justiça fica "sem registro", as demais têm dados normais) |

   Isso cobre **todos os 10 valores de `StatusRegua`**, o caso de perfil 100% vazio, a
   variedade de `CertidaoPublica.resultado` (negativa/positiva/inconclusiva/não analisada),
   mandato/votos legislativos prévios, e `posicoes` da bússola com `null`.
5. **`apps/web/scripts/copiar-fixtures.ts`** — copia `fixtures/dados` → `public/dados` e força
   `meta.fixture = true`. Testado e funcionando (`node --experimental-strip-types scripts/copiar-fixtures.ts`).
   `apps/web/fixtures/package.json` e `apps/web/scripts/package.json` (ambos `{"type":"module"}`)
   foram criados só para permitir ESM nesses dois scripts sem mudar o `package.json` principal do app.
6. **Paleta e tipografia — DECIDIDAS, contraste verificado, ainda NÃO aplicadas no CSS**:
   - Tinta (texto/fundo escuro): `#0F1115`. Papel (fundo claro): `#FAFAF8`.
   - Rampa neutra planejada (10 degraus interpolados entre tinta e papel): `g-950 #0F1115`,
     `g-900 #16191F`, `g-800 #21252C`, `g-700 #2E333C`, `g-600 #454C57`, `g-500 #5C6472`,
     `g-400 #7C838F`, `g-300 #A6ACB5`, `g-150 #E4E6E8`, `g-100 #EEEFF0`, `g-50 #FAFAF8`.
   - Acento único não-partidário (grafite-azulado, baixa saturação):
     **claro `#3B4F61`** (contraste 8.11:1 sobre `#FAFAF8` — AA/AAA texto) e
     **escuro `#9FB4C4`** (contraste 8.82:1 sobre `#0F1115`). Verificado com script Node
     (fórmula WCAG relative luminance), não é achismo.
   - Tipografia: Inter (ou Geist, já disponível) para UI; **Source Serif 4** para títulos
     editoriais; ambas via `next/font/google` (self-host automático no build); números com
     `font-variant-numeric: tabular-nums` em tabelas/gráficos.
7. **Skills carregadas**: `dataviz` e `frontend-design` (via `Skill` tool) — orientam a
   implementação de gráficos e a direção visual ainda por vir.
8. **Última rodada de qualidade** (rodada agora, antes da pausa):
   - `pnpm --filter @raiox/core test` → **19/19 passando**.
   - `pnpm --filter @raiox/core typecheck` → **FALHA pré-existente**, não introduzida por
     este agente: `src/bussola.test.ts(110,29)` — um objeto de teste sem assinatura de índice
     não é atribuível a `Record<string, PosicaoBussola>`. Este arquivo não foi tocado nesta
     sessão; sinalizar para quem mantém `packages/core`.
   - `pnpm --filter web lint` → **limpo, sem avisos**.
   - `pnpm --filter web typecheck` → **limpo** (rodar depois de `next build`, porque
     `.next/types` — de onde vem o tipo global `LayoutProps` usado em `app/layout.tsx` — só
     é gerado no build/dev).
   - `pnpm --filter web build` → **sucesso**. Neste momento o app ainda é só o scaffold
     padrão do `create-next-app` + nosso `next.config.ts`; nenhuma rota/página própria foi
     escrita ainda. `out/` gerado corretamente com `out/dados/**` (cópia de `public/dados`,
     14 candidatos — nada perto do limite de 20 000 arquivos do Cloudflare Pages).

## EM ANDAMENTO / AINDA NÃO EXISTE

Nada do design system, layout, rotas, componentes, formulário de correção, headers de
segurança, SEO, testes de UI ou E2E foi escrito ainda. `apps/web/src/app/` continua com o
`layout.tsx`, `page.tsx` e `globals.css` padrão do `create-next-app` (fonte Geist, sem
tema, `lang="en"`, sem navegação). **Nada disso deve ser reaproveitado** — é só o ponto de
partida a ser substituído no próximo passo.

## PRÓXIMOS PASSOS (nesta ordem)

1. **Confirmar com o coordenador**: (a) quem corrige o typecheck de
   `packages/core/src/bussola.test.ts` (não fiz essa correção durante a pausa); (b) se o
   fallback de 1 OG image estática global é aceitável em vez de OG dinâmica por candidato;
   (c) valores reais (ou placeholders documentados) para `NEXT_PUBLIC_SITE_URL`,
   `NEXT_PUBLIC_CORRECAO_URL`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`.
2. Construir o design system: `apps/web/src/app/globals.css` (bloco `@theme` do Tailwind v4
   com a paleta/tipografia da seção 6 acima) + fontes via `next/font/google` em
   `layout.tsx` (`lang="pt-BR"`), modo claro/escuro (`prefers-color-scheme` + toggle manual
   persistido em `localStorage` com `try/catch`, script inline anti-flash no `<head>`).
3. `layout.tsx` raiz: skip link, `<Header>` (logo + nav desktop), `<BottomNav>` fixo no
   mobile (Início · Comparar · Bússola · Economia · Buscar, alvo ≥44px, safe-area-inset),
   `<Footer>` (texto institucional fixo + links + "última atualização" vindo de
   `meta.geradoEm`), landmark `<main>`.
4. `lib/dados.ts`: leitura server-side (`fs/promises`) de `public/dados/*.json` no build,
   tipada com `@raiox/core/contrato`. Como o escopo é uma corrida só, a maior parte das
   páginas pode ler os dados como Server Component e passar como props para os componentes
   client (`/comparar`, `/bussola`, `/economia` são interativos e precisam de `'use client'`,
   mas não precisam re-buscar via `fetch` no navegador — os dados cabem tranquilamente no
   HTML/props, é só 1 arquivo por endpoint agora).
5. **Guarda de produção contra fixture**: no módulo raiz do layout (ou um `lib/guarda-fixture.ts`
   importado por ele), ler `public/dados/meta.json` em tempo de build e lançar erro claro se
   `meta.fixture === true && process.env.NODE_ENV === 'production' && !process.env.RAIOX_PERMITIR_FIXTURE`.
6. Rotas (nesta ordem sugerida, cada uma reaproveitando os mesmos componentes de perfil):
   `/` (grade dos 14 em ordem alfabética + botão "ordem aleatória" com semente visível +
   busca local simples, sem precisar de `busca.json` + contagem regressiva neutra) →
   `/candidatos` (lista completa dedicada, mesmo componente de grade) →
   `/candidato/[slug]` (generateStaticParams a partir de `lista/presidente-br.json`, 14
   páginas; abas SEMPRE na mesma ordem: Resumo · Trajetória · Patrimônio · Propostas ·
   Votações · Justiça · Checagens · Campanha · Fontes; seção vazia sempre mostra "Sem
   registro público encontrado", nunca some) → `/comparar` (até 4 desktop / 2 swipe mobile,
   estado na URL `?c=id1,id2&tema=economia`) → `/bussola` (sem seletor de cargo/UF, usa
   `bussola/presidente-br.json`, 100% client-side, `calcularTodos` de `@raiox/core/bussola`,
   texto fixo "Isto não é pesquisa eleitoral nem recomendação de voto.") → `/economia`
   (só séries nacionais, só os 3 períodos presidenciais, gráficos SVG leves — ver decisão de
   paleta abaixo — CSV no cliente) → páginas institucionais (`/metodologia`,
   `/politica-editorial`, `/regua-judicial`, `/correcoes`, `/sobre`, `/privacidade`,
   `/termos`, `/dados-abertos`, texto completo baseado no `PLANO_FINAL.md`, marcar trechos
   jurídicos com `{/* REVISAO_JURIDICA */}`) → `not-found.tsx` → `sitemap.ts` / `robots.ts`
   (`export const dynamic = 'force-static'`) / `opengraph-image.tsx` raiz.
7. Formulário "Reportar erro" (`components/correcao/FormularioErro.tsx`, modal/drawer,
   client): campos do contrato do PLANO (tipo de solicitante, descrição 20–5000, links,
   e-mail opcional, Turnstile condicional), `POST` JSON para `NEXT_PUBLIC_CORRECAO_URL`,
   estados carregando/erro/sucesso com `protocolo`.
8. `public/_headers` (CSP estrita — permitir `divulgacandcontas.tse.jus.br`, `archive.org`,
   `challenges.cloudflare.com`, Cloudflare Web Analytics, host de `NEXT_PUBLIC_CORRECAO_URL`
   — + HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`,
   `frame-ancestors 'none'`) e `public/_redirects` se necessário.
9. Testes: `vitest.config.ts` (ambiente jsdom) + testes de lógica não-trivial (estado de URL
   do comparador, persistência/"apagar minhas respostas" da bússola em `localStorage`, busca
   normalizada com `normalizarBusca` de `@raiox/core/formatos`).
10. Playwright: `playwright.config.ts` servindo `out/` (pacote `serve`), viewports iPhone SE /
    iPhone 15 Pro / Pixel 7 / iPad / desktop 1440; specs em `apps/web/e2e/`: home→busca→perfil,
    comparador com swipe, bússola completa até resultado, economia com troca de série,
    formulário de correção (mock de fetch), **isonomia** (as 9 abas, mesma ordem, nos 14
    perfis), `@axe-core/playwright` sem violações sérias/críticas em todas as rotas, sem
    scroll horizontal em 390px.
11. QA visual: `pnpm build && npx serve out`, usar as ferramentas de browser do Playwright
    MCP para screenshots em 390px/1440px × claro/escuro em cada rota; iterar até "premium".
12. Relatório final ao coordenador: rotas, paleta/fontes finais, dependências, resultados de
    lint/typecheck/build/test/E2E/axe, contagem de arquivos de `out/` vs. limite de 20 000,
    tamanho de JS por rota, screenshots conferidas, pendências.

## Comandos exatos para retomar

```bash
cd "apps/web"   # (relativo à raiz do repo)

# só se node_modules sumir:
cd .. && pnpm install && cd apps/web

# regenerar a fonte das fixtures (só se fixtures/gerar.ts ou o contrato mudarem):
node --experimental-strip-types fixtures/gerar.ts

# copiar fixtures -> public/dados (meta.fixture=true) — sempre antes de rodar/buildar:
pnpm dados:fixture

pnpm lint
pnpm typecheck        # rodar depois de ao menos um `pnpm build` ou `pnpm dev`
pnpm build            # depois do passo 5 acima, vai exigir RAIOX_PERMITIR_FIXTURE=1 em produção:
                       #   RAIOX_PERMITIR_FIXTURE=1 pnpm build
pnpm test             # vitest (specs ainda não existem)
pnpm e2e:install       # uma vez, instala os browsers do Playwright
pnpm e2e               # depois que e2e/*.spec.ts e playwright.config.ts existirem
```

## Pendências e decisões em aberto

- **Typecheck de `packages/core`**: falha pré-existente em `bussola.test.ts:110`, não
  causada por esta sessão. Não corrigida (fora do escopo `apps/web/`, e a pausa pediu para
  não avançar mais nada).
- **OG images**: plano é 1 imagem OG estática global (fallback explicitamente permitido pelo
  enunciado) em vez de OG dinâmica por candidato — confirmar se está OK.
- **Paleta de gráficos**: a skill `dataviz` (carregada) pede 8 matizes categóricas fixas
  validadas por script; o enunciado do projeto exige **zero cor associável a partido** —
  decisão planejada é usar identidade categórica monocromática (degraus de cinza-ardósia +
  padrão de traço/textura distinto por candidato + rótulo direto sempre visível + legenda),
  que é exatamente o canal de "codificação secundária" que a própria skill permite quando o
  piso de croma não é atingido. Isso é um desvio deliberado e documentado do uso padrão da
  skill, não um esquecimento — repetir essa justificativa no relatório final.
- **Variáveis de ambiente**: `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_CORRECAO_URL`,
  `NEXT_PUBLIC_TURNSTILE_SITE_KEY` ainda não definidas em lugar nenhum — o formulário de
  correção precisa esconder o widget Turnstile com elegância quando a chave não existir
  (comportamento de dev), e todas as páginas que citam a URL canônica devem ter um fallback
  sensato enquanto `NEXT_PUBLIC_SITE_URL` não for definida.
- Nenhuma alteração foi proposta ao contrato (`packages/core/src/contrato.ts`) além das que
  o próprio coordenador já aplicou (`fixture?`, `CorrecoesArquivo`, `chaveArquivo`).
