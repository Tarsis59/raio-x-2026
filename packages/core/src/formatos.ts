/** Formatação pt-BR consistente em todo o site. */

const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const moedaCompacta = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  notation: 'compact',
  maximumFractionDigits: 1,
});
const numero = new Intl.NumberFormat('pt-BR');
const dataLonga = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'long', year: 'numeric', timeZone: 'UTC' });
const dataCurta = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' });
const dataHora = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'America/Sao_Paulo',
});

export const formatarMoeda = (v: number | null | undefined): string => (v == null ? '—' : moeda.format(v));
export const formatarMoedaCompacta = (v: number | null | undefined): string =>
  v == null ? '—' : moedaCompacta.format(v);
export const formatarNumero = (v: number | null | undefined): string => (v == null ? '—' : numero.format(v));

export function formatarPercentual(v: number | null | undefined, casas = 1): string {
  if (v == null) return '—';
  return `${v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })}%`;
}

export function formatarVariacao(v: number | null | undefined, casas = 1): string {
  if (v == null) return '—';
  const s = formatarPercentual(Math.abs(v), casas);
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s;
}

const paraData = (iso: string) => new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);

export const formatarData = (iso: string | null | undefined): string => (iso ? dataLonga.format(paraData(iso)) : '—');
export const formatarDataCurta = (iso: string | null | undefined): string =>
  iso ? dataCurta.format(paraData(iso)) : '—';
export const formatarDataHora = (iso: string | null | undefined): string => (iso ? dataHora.format(paraData(iso)) : '—');

/** Idade completa na data de referência (padrão: data da eleição). */
export function idade(nascimento: string | null | undefined, referencia = '2026-10-04'): number | null {
  if (!nascimento) return null;
  const n = paraData(nascimento);
  const r = paraData(referencia);
  let anos = r.getUTCFullYear() - n.getUTCFullYear();
  const m = r.getUTCMonth() - n.getUTCMonth();
  if (m < 0 || (m === 0 && r.getUTCDate() < n.getUTCDate())) anos -= 1;
  return anos;
}

/** Remove acentos e normaliza para busca. */
export function normalizarBusca(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

/** Nome próprio a partir de CAIXA ALTA, respeitando preposições e siglas curtas. */
export function nomeProprio(texto: string): string {
  const minusculas = new Set(['da', 'de', 'do', 'das', 'dos', 'e', 'di', 'du', 'del']);
  return texto
    .toLowerCase()
    .split(/\s+/)
    .map((p, i) => (i > 0 && minusculas.has(p) ? p : p.charAt(0).toUpperCase() + p.slice(1)))
    .join(' ');
}
