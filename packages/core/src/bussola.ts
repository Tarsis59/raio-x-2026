/**
 * Bússola de afinidade — algoritmo público e determinístico.
 *
 * Roda 100% no navegador do eleitor: as respostas nunca são enviadas a servidor algum
 * (LGPD art. 11: opinião política é dado sensível) e nunca são agregadas
 * (Lei 9.504/97 art. 33 §5º: vedação a enquetes no período eleitoral).
 *
 * Para cada pergunta i respondida pelo eleitor (u_i ∈ [-2, 2], peso w_i ∈ {1, 2, 3})
 * e com posição documentada do candidato (c_i ∈ [-2, 2]):
 *
 *     afinidade_i = 1 − |u_i − c_i| / 4                (1 = idêntico, 0 = oposto)
 *     score       = Σ w_i · afinidade_i / Σ w_i
 *     cobertura   = nº perguntas com posição documentada / nº perguntas respondidas
 *
 * Posição sem evidência (null) não conta nem penaliza. Abaixo de COBERTURA_MINIMA
 * o resultado é "dados insuficientes" — não exibimos percentual.
 */

import type { PosicaoBussola } from './contrato';

export const COBERTURA_MINIMA = 0.6;

export type ValorResposta = -2 | -1 | 0 | 1 | 2;
export type Peso = 1 | 2 | 3;

export interface Resposta {
  valor: ValorResposta;
  peso: Peso;
}

/** Respostas por id da pergunta. Pergunta ausente = pulada. */
export type Respostas = Record<string, Resposta>;

export type Comparacao = 'convergencia' | 'parcial' | 'divergencia';

export interface DetalhePergunta {
  perguntaId: string;
  resposta: Resposta;
  posicao: PosicaoBussola | null;
  afinidade: number | null; // null = sem posição documentada
  comparacao: Comparacao | null;
}

export interface ResultadoCandidato {
  candidatoId: number;
  /** 0–100, arredondado. null quando a cobertura é insuficiente. */
  percentual: number | null;
  scoreBruto: number | null;
  cobertura: number;
  perguntasComparadas: number;
  perguntasRespondidas: number;
  suficiente: boolean;
  detalhes: DetalhePergunta[];
}

export function afinidade(usuario: number, candidato: number): number {
  return 1 - Math.abs(usuario - candidato) / 4;
}

export function classificar(a: number): Comparacao {
  if (a >= 0.75) return 'convergencia';
  if (a >= 0.5) return 'parcial';
  return 'divergencia';
}

export function calcularCandidato(
  candidatoId: number,
  respostas: Respostas,
  posicoes: Record<string, PosicaoBussola | undefined>,
): ResultadoCandidato {
  const detalhes: DetalhePergunta[] = [];
  let somaPesos = 0;
  let somaPonderada = 0;
  let comparadas = 0;

  const ids = Object.keys(respostas).sort();
  for (const perguntaId of ids) {
    const resposta = respostas[perguntaId]!;
    const posicao = posicoes[perguntaId] ?? null;
    if (!posicao || posicao.valor === null) {
      detalhes.push({ perguntaId, resposta, posicao, afinidade: null, comparacao: null });
      continue;
    }
    const a = afinidade(resposta.valor, posicao.valor);
    somaPesos += resposta.peso;
    somaPonderada += resposta.peso * a;
    comparadas += 1;
    detalhes.push({ perguntaId, resposta, posicao, afinidade: a, comparacao: classificar(a) });
  }

  const respondidas = ids.length;
  const cobertura = respondidas === 0 ? 0 : comparadas / respondidas;
  const suficiente = respondidas > 0 && comparadas > 0 && cobertura >= COBERTURA_MINIMA;
  const scoreBruto = somaPesos > 0 ? somaPonderada / somaPesos : null;

  return {
    candidatoId,
    percentual: suficiente && scoreBruto !== null ? Math.round(scoreBruto * 100) : null,
    scoreBruto,
    cobertura,
    perguntasComparadas: comparadas,
    perguntasRespondidas: respondidas,
    suficiente,
    detalhes,
  };
}

/**
 * Calcula todos os candidatos. Ordenação: suficientes primeiro por percentual decrescente;
 * empates e insuficientes em ordem alfabética do nome de urna (critério neutro e público).
 */
export function calcularTodos<C extends { id: number; nomeUrna: string; posicoes: Record<string, PosicaoBussola> }>(
  candidatos: C[],
  respostas: Respostas,
): (ResultadoCandidato & { candidato: C })[] {
  const col = new Intl.Collator('pt-BR', { sensitivity: 'base' });
  return candidatos
    .map((c) => ({ ...calcularCandidato(c.id, respostas, c.posicoes), candidato: c }))
    .sort((a, b) => {
      if (a.suficiente !== b.suficiente) return a.suficiente ? -1 : 1;
      if (a.suficiente && b.suficiente && a.scoreBruto !== b.scoreBruto) {
        return (b.scoreBruto ?? 0) - (a.scoreBruto ?? 0);
      }
      return col.compare(a.candidato.nomeUrna, b.candidato.nomeUrna);
    });
}
