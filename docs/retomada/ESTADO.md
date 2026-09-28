# Estado do projeto — PAUSADO em 28/09/2026

> Pausado a pedido do dono do projeto. Para retomar, siga o **Roteiro de retomada** abaixo, na ordem.
> Os pontos de parada de cada frente ficam nos arquivos desta pasta (`tse.md`, `legislativo.md`, `economia.md`, `ia-justica-checagens.md`, `site.md`).

## Decisões vigentes (prevalecem sobre qualquer outra coisa)
- **Escopo: SOMENTE a eleição presidencial 2026**: 14 candidaturas a Presidente e seus vices, com todas as funcionalidades.
- **Custo zero de infraestrutura.** Só a API do Claude é paga. Site estático no Cloudflare Pages, Supabase Free, GitHub Actions (repositório público), evidências no archive.org.
- O parecer jurídico fica com o advogado eleitoral do projeto. O nome do produto será definido depois (provisório: "Raio-X 2026").
- Meta: lançar antes do 1º turno (04/10/2026). 2º turno: 25/10/2026.

## Pronto e no GitHub (github.com/Tarsis59/raio-x-2026, branch `main`)
- Monorepo (pnpm + Turborepo), `PLANO_FINAL.md` rev. 1.1.
- `supabase/migrations/20260928000000_esquema_inicial.sql`: esquema completo (evidência imutável, audit log append-only, regra dos 4 olhos, RLS) + `seed.sql`.
- ETL base `etl/raiox/common/*`: config, db.upsert, job.executar (portão de qualidade), evidencia (SHA-256 + archive.org), identidade (HMAC de CPF), http (truststore), tse.ClienteTSE (Chromium *new headless* com UA normal, porque o Akamai bloqueia o resto).
- `etl/raiox/jobs/exportar.py`: gera os JSONs do site (somente itens aprovados, somente cargo 1, bloqueia CPF/título). Testado com dados reais parciais.
- `packages/core`: contrato de dados (`contrato.ts`), algoritmo da Bússola, formatos (19 testes passando).
- `supabase/functions/correcao`: Edge Function de correções (Turnstile, CORS, validação).
- `.github/workflows`: `ci.yml`, `etl.yml` (2x/dia), `deploy.yml` (Cloudflare Pages).
- `docs/`: fontes/TSE.md, editorial/MANUAL.md, runbooks/RUNBOOKS.md.
- `.env.example` com todas as chaves.

## Trabalho das 5 frentes (agentes) — NÃO commitado na `main`
Tudo o que os agentes produziram até a pausa está salvo no commit da branch **`wip/pausa-2026-09-28`**. Pode estar incompleto: revise cada frente pelo arquivo de retomada correspondente antes de juntar na `main`.

## Ambiente local
- Supabase local (Docker) **parado com os dados preservados** (`supabase stop` mantém os volumes). Para religar: abrir o Docker Desktop e rodar
  `supabase start -x realtime,storage-api,imgproxy,mailpit,edge-runtime,logflare,vector,supavisor,studio,postgres-meta`
  O banco fica em `postgresql://postgres:postgres@127.0.0.1:54322/postgres`.
- Python: `cd etl && PYTHONUTF8=1 UV_SYSTEM_CERTS=1 python -m uv run python -m raiox --lista`. O `uv` está instalado via `pip --user`, e o antivírus exige `UV_SYSTEM_CERTS=1`.
- Segredos de produção já gerados: `.env.prod.local` (fora do Git) contém `SUPABASE_DB_PASSWORD` e `CPF_HMAC_SECRET`. **Nunca trocar o CPF_HMAC_SECRET.**

## Pendências do dono do projeto
1. Pausar o projeto "Tarsis59's Project" (ref `ldukelwxsccefbsvugbb`) no Supabase: o plano gratuito permite só 2 projetos ativos. Depois disso, criar o projeto `raio-x-2026` em `sa-east-1`:
   `supabase projects create raio-x-2026 --org-id bllreigqeziykzhjvtnp --region sa-east-1 --db-password <SUPABASE_DB_PASSWORD do .env.prod.local>`
   (o MCP do Supabase nesta máquina está ligado a OUTRA conta; use a CLI).
2. `.env` com ANTHROPIC_API_KEY, IA_S3_ACCESS_KEY/SECRET (archive.org), GOOGLE_FACTCHECK_API_KEY, PORTAL_TRANSPARENCIA_API_KEY.
3. Conta Cloudflare (Pages + Turnstile + token de API).

## Roteiro de retomada (quando o dono autorizar)
1. Ler este arquivo e todos os `docs/retomada/*.md`.
2. Ligar o Docker Desktop e o Supabase local (comando acima). Conferir as contagens do banco.
3. `git checkout wip/pausa-2026-09-28` e rodar lint e testes de cada frente (`etl`: ruff + pytest; `web`: lint, typecheck, build).
4. Retomar cada frente pelos "próximos passos" do seu arquivo (podem rodar em paralelo, como antes).
5. Integrar: rodar `exportar` com dados reais → build do site → revisão visual (390px/1440px, claro/escuro).
6. Construir o painel editorial (`apps/admin`: login com MFA, fila de revisão 4 olhos, correções com SLA, despublicar, botão "Publicar agora").
7. Produção: criar o projeto Supabase, aplicar as migrações (`supabase link` + `supabase db push`), deploy da função `correcao`, secrets no GitHub, projeto no Cloudflare Pages, primeiro deploy.
8. Revisão final: segurança, acessibilidade, carga (k6), checklist de go-live (seção 16 do plano).
9. Pontos já anotados para revisar:
   - **Economia:** o agente relatou que `etl/raiox/economia/__init__.py`, `bcb.py` e `sidra.py` foram alterados por outro processo durante o trabalho. Antes de continuar, conferir o que está em disco e escolher uma única implementação (ver `economia.md`).
   - **Novo CAGED (2020+):** não há fonte estável em formato legível por máquina. Decisão do dono: exibir só até 2019 (com aviso de quebra) ou montar o processamento dos arquivos oficiais.
   - Senado: a maioria das votações é secreta; só ingerir voto individual com `Secreta='N'`. Downloads grandes via httpx precisam de `Range` em pedaços (ver `legislativo.md`).
   - `packages/core`: o typecheck falha em `bussola.test.ts:110` (bug meu, pequeno). Corrigir na retomada.
   - Horário `atualizado_tse_em` gravado como UTC, mas o TSE informa horário de Brasília.
   - Validar o `regiao` do link público do TSE (hoje fixo em `BR`, o que está correto para Presidente).
