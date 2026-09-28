// Edge Function: recebe pedidos de correção do site público.
//
// Segurança:
//  * Cloudflare Turnstile obrigatório em produção (TURNSTILE_SECRET_KEY).
//  * CORS restrito ao domínio do site (SITE_URL, lista separada por vírgula).
//  * Validação estrita de todos os campos; grava com a service role (a tabela não aceita escrita anônima).
//  * Não registra IP nem user-agent (minimização de dados — LGPD).

import { createClient } from 'npm:@supabase/supabase-js@2';

const TIPOS = ['eleitor', 'candidato', 'assessoria', 'imprensa', 'outro'] as const;
const EMAIL = /^[^\s@]{1,64}@[^\s@]{1,255}\.[^\s@]{2,}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const origens = (Deno.env.get('SITE_URL') ?? 'http://localhost:3000')
  .split(',')
  .map((s) => s.trim().replace(/\/$/, ''))
  .filter(Boolean);

function cors(origem: string | null): Record<string, string> {
  const permitida = origem && origens.includes(origem) ? origem : origens[0]!;
  return {
    'access-control-allow-origin': permitida,
    'access-control-allow-methods': 'POST, OPTIONS',
    'access-control-allow-headers': 'content-type',
    'access-control-max-age': '86400',
    vary: 'origin',
  };
}

function resposta(corpo: unknown, status: number, origem: string | null): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', ...cors(origem) },
  });
}

interface Pedido {
  pessoaId?: string;
  candidaturaId?: number;
  paginaUrl: string;
  tipoSolicitante: (typeof TIPOS)[number];
  descricao: string;
  links: string[];
  contatoEmail?: string;
  turnstileToken: string;
}

function validar(b: unknown): { ok: true; pedido: Pedido } | { ok: false; erro: string } {
  if (!b || typeof b !== 'object') return { ok: false, erro: 'Corpo inválido.' };
  const p = b as Record<string, unknown>;

  const descricao = typeof p.descricao === 'string' ? p.descricao.trim() : '';
  if (descricao.length < 20 || descricao.length > 5000) {
    return { ok: false, erro: 'A descrição deve ter entre 20 e 5.000 caracteres.' };
  }
  if (!TIPOS.includes(p.tipoSolicitante as Pedido['tipoSolicitante'])) {
    return { ok: false, erro: 'Tipo de solicitante inválido.' };
  }
  let paginaUrl: string;
  try {
    const u = new URL(String(p.paginaUrl));
    if (!origens.some((o) => u.origin === new URL(o).origin)) throw new Error();
    paginaUrl = u.toString();
  } catch {
    return { ok: false, erro: 'Página de origem inválida.' };
  }
  const links = Array.isArray(p.links) ? p.links : [];
  if (links.length > 10) return { ok: false, erro: 'Envie no máximo 10 links.' };
  const linksValidos: string[] = [];
  for (const l of links) {
    try {
      const u = new URL(String(l));
      if (u.protocol !== 'https:' && u.protocol !== 'http:') throw new Error();
      linksValidos.push(u.toString().slice(0, 2000));
    } catch {
      return { ok: false, erro: `Link inválido: ${String(l).slice(0, 80)}` };
    }
  }
  const email = typeof p.contatoEmail === 'string' && p.contatoEmail.trim() ? p.contatoEmail.trim() : undefined;
  if (email && !EMAIL.test(email)) return { ok: false, erro: 'E-mail inválido.' };
  const pessoaId = typeof p.pessoaId === 'string' && UUID.test(p.pessoaId) ? p.pessoaId : undefined;
  const candidaturaId = Number.isSafeInteger(p.candidaturaId) ? (p.candidaturaId as number) : undefined;
  const turnstileToken = typeof p.turnstileToken === 'string' ? p.turnstileToken : '';

  return {
    ok: true,
    pedido: {
      pessoaId,
      candidaturaId,
      paginaUrl,
      tipoSolicitante: p.tipoSolicitante as Pedido['tipoSolicitante'],
      descricao,
      links: linksValidos,
      contatoEmail: email,
      turnstileToken,
    },
  };
}

async function turnstileValido(token: string): Promise<boolean> {
  const segredo = Deno.env.get('TURNSTILE_SECRET_KEY');
  if (!segredo) {
    // Sem segredo configurado só é aceito em ambiente local.
    return (Deno.env.get('SUPABASE_URL') ?? '').includes('127.0.0.1') || Deno.env.get('RAIOX_DEV') === '1';
  }
  if (!token) return false;
  const form = new FormData();
  form.append('secret', segredo);
  form.append('response', token);
  const r = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body: form });
  if (!r.ok) return false;
  const j = (await r.json()) as { success?: boolean };
  return j.success === true;
}

Deno.serve(async (req) => {
  const origem = req.headers.get('origin');
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(origem) });
  if (req.method !== 'POST') return resposta({ erro: 'Método não permitido.' }, 405, origem);
  if (Number(req.headers.get('content-length') ?? '0') > 20_000) {
    return resposta({ erro: 'Pedido grande demais.' }, 413, origem);
  }

  let corpo: unknown;
  try {
    corpo = await req.json();
  } catch {
    return resposta({ erro: 'JSON inválido.' }, 400, origem);
  }
  const v = validar(corpo);
  if (!v.ok) return resposta({ erro: v.erro }, 422, origem);
  if (!(await turnstileValido(v.pedido.turnstileToken))) {
    return resposta({ erro: 'Não foi possível confirmar que você não é um robô. Tente novamente.' }, 403, origem);
  }

  const supabase = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, {
    auth: { persistSession: false },
  });

  let pessoaId = v.pedido.pessoaId ?? null;
  if (!pessoaId && v.pedido.candidaturaId) {
    const { data } = await supabase.from('candidatura').select('pessoa_id').eq('id', v.pedido.candidaturaId).maybeSingle();
    pessoaId = data?.pessoa_id ?? null;
  }

  const { data, error } = await supabase
    .from('correcao')
    .insert({
      pessoa_id: pessoaId,
      pagina_url: v.pedido.paginaUrl,
      tipo_solicitante: v.pedido.tipoSolicitante,
      descricao: v.pedido.descricao,
      links: v.pedido.links,
      contato_email: v.pedido.contatoEmail ?? null,
    })
    .select('protocolo')
    .single();

  if (error || !data) {
    console.error('Falha ao gravar correção', error?.message);
    return resposta({ erro: 'Não foi possível registrar agora. Tente novamente em instantes.' }, 500, origem);
  }
  return resposta({ protocolo: data.protocolo }, 201, origem);
});
