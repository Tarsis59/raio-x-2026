# Runbooks — resposta a incidentes

Contatos, acessos e plantão ficam no documento interno (fora do repositório público).

## 1. Dado errado publicado
1. Painel editorial → item → **Despublicar** (ou `status_revisao = 'despublicado'`).
2. GitHub → Actions → **Deploy** → *Run workflow* (motivo: "correção urgente"). O site atualiza em cerca de 5 min.
3. Registrar no changelog público do perfil e responder ao pedido de correção com o protocolo.
4. Post-mortem em até 48 h: por que passou pelos 4 olhos?

## 2. Site fora do ar
- O site é estático no Cloudflare Pages. Verifique https://www.cloudflarestatus.com.
- Rollback: Cloudflare → Pages → raio-x-2026 → Deployments → versão anterior → **Rollback**.
- O banco fora do ar **não** derruba o site; só atrasa a próxima atualização.

## 3. Ataque / pico anômalo
- Cloudflare → Security → **Under Attack Mode** (ou regra de rate limit no formulário de correção).
- A Edge Function de correção já exige Turnstile. Se houver spam mesmo assim, aumente a dificuldade do widget.

## 4. Fonte oficial mudou de formato ou bloqueou
- O job falha no portão de qualidade e o site continua com o último dado bom.
- TSE bloqueando o GitHub Actions: registre um runner self-hosted numa máquina no Brasil
  (Settings → Actions → Runners → New self-hosted runner) e defina a variável de repositório `TSE_RUNNER=self-hosted`.
- Ajuste o parser, rode os testes (`uv run pytest`) e reexecute o workflow **ETL** (grupo correspondente).

## 5. Ordem judicial de remoção
1. Cumprir no prazo determinado: despublicar o item (runbook 1).
2. Encaminhar ao jurídico. Preservar o registro no audit log (ele é imutável).
3. Publicar no changelog: "Conteúdo removido por ordem judicial (processo nº …)", salvo se houver sigilo.

## 6. Vazamento de segredo
1. Revogar imediatamente a chave no provedor (Anthropic, Supabase, Cloudflare, archive.org, Google, CGU).
2. Gerar uma nova e atualizar em GitHub → Settings → Secrets.
3. **Nunca** troque o `CPF_HMAC_SECRET`: todas as identidades seriam recalculadas. Se ele vazar, planeje uma migração controlada com o time técnico.

## 7. Supabase pausado (projeto gratuito pausa após 7 dias sem uso)
- Os crons diários mantêm o projeto ativo. Se pausar, reative no painel do Supabase (Restore) e reexecute o ETL.
