import { describe, expect, it } from 'vitest';
import { afinidade, calcularCandidato, calcularTodos, classificar, COBERTURA_MINIMA, type Respostas } from './bussola';
import type { PosicaoBussola } from './contrato';

const pos = (valor: PosicaoBussola['valor']): PosicaoBussola => ({
  valor,
  fonte: 'proposta',
  justificativa: 'teste',
  evidencia: null,
});

describe('afinidade', () => {
  it('é 1 para posições idênticas e 0 para opostas', () => {
    expect(afinidade(2, 2)).toBe(1);
    expect(afinidade(-2, 2)).toBe(0);
    expect(afinidade(0, 2)).toBe(0.5);
    expect(afinidade(1, 0)).toBe(0.75);
  });

  it('é simétrica', () => {
    for (const a of [-2, -1, 0, 1, 2]) for (const b of [-2, -1, 0, 1, 2]) expect(afinidade(a, b)).toBe(afinidade(b, a));
  });

  it('classifica faixas', () => {
    expect(classificar(1)).toBe('convergencia');
    expect(classificar(0.75)).toBe('convergencia');
    expect(classificar(0.5)).toBe('parcial');
    expect(classificar(0.25)).toBe('divergencia');
  });
});

describe('calcularCandidato', () => {
  it('sem respostas: insuficiente, sem percentual', () => {
    const r = calcularCandidato(1, {}, { p1: pos(2) });
    expect(r.suficiente).toBe(false);
    expect(r.percentual).toBeNull();
    expect(r.cobertura).toBe(0);
  });

  it('todas as posições nulas: insuficiente', () => {
    const resp: Respostas = { p1: { valor: 2, peso: 1 }, p2: { valor: -1, peso: 2 } };
    const r = calcularCandidato(1, resp, { p1: pos(null), p2: pos(null) });
    expect(r.suficiente).toBe(false);
    expect(r.percentual).toBeNull();
    expect(r.perguntasComparadas).toBe(0);
    expect(r.detalhes.every((d) => d.afinidade === null)).toBe(true);
  });

  it('concordância total dá 100%', () => {
    const resp: Respostas = { p1: { valor: 2, peso: 1 }, p2: { valor: -2, peso: 3 } };
    const r = calcularCandidato(1, resp, { p1: pos(2), p2: pos(-2) });
    expect(r.percentual).toBe(100);
  });

  it('discordância total dá 0%', () => {
    const resp: Respostas = { p1: { valor: 2, peso: 1 }, p2: { valor: -2, peso: 3 } };
    const r = calcularCandidato(1, resp, { p1: pos(-2), p2: pos(2) });
    expect(r.percentual).toBe(0);
  });

  it('aplica pesos corretamente', () => {
    // p1: afinidade 1 com peso 3; p2: afinidade 0 com peso 1 → 3/4 = 75%
    const resp: Respostas = { p1: { valor: 2, peso: 3 }, p2: { valor: 2, peso: 1 } };
    const r = calcularCandidato(1, resp, { p1: pos(2), p2: pos(-2) });
    expect(r.percentual).toBe(75);
  });

  it('posição nula não penaliza, mas reduz a cobertura', () => {
    const resp: Respostas = {
      p1: { valor: 2, peso: 1 },
      p2: { valor: 2, peso: 1 },
      p3: { valor: 2, peso: 1 },
      p4: { valor: 2, peso: 1 },
      p5: { valor: 2, peso: 1 },
    };
    const posicoes = { p1: pos(2), p2: pos(2), p3: pos(2), p4: pos(null) }; // p5 ausente
    const r = calcularCandidato(1, resp, posicoes);
    expect(r.cobertura).toBeCloseTo(0.6);
    expect(r.suficiente).toBe(true);
    expect(r.percentual).toBe(100);
  });

  it('abaixo da cobertura mínima não mostra percentual', () => {
    const resp: Respostas = { p1: { valor: 2, peso: 1 }, p2: { valor: 2, peso: 1 }, p3: { valor: 2, peso: 1 } };
    const r = calcularCandidato(1, resp, { p1: pos(2) });
    expect(r.cobertura).toBeLessThan(COBERTURA_MINIMA);
    expect(r.suficiente).toBe(false);
    expect(r.percentual).toBeNull();
    expect(r.scoreBruto).toBe(1); // o cálculo existe, só não é exibido
  });

  it('é determinístico e independe da ordem de inserção das respostas', () => {
    const a: Respostas = { p2: { valor: 1, peso: 2 }, p1: { valor: -1, peso: 1 } };
    const b: Respostas = { p1: { valor: -1, peso: 1 }, p2: { valor: 1, peso: 2 } };
    const posicoes = { p1: pos(0), p2: pos(2) };
    expect(calcularCandidato(1, a, posicoes)).toEqual(calcularCandidato(1, b, posicoes));
  });
});

describe('calcularTodos', () => {
  const resp: Respostas = { p1: { valor: 2, peso: 1 }, p2: { valor: 2, peso: 1 } };

  it('ordena suficientes por afinidade e depois insuficientes em ordem alfabética', () => {
    const cands = [
      { id: 1, nomeUrna: 'Zeca', posicoes: { p1: pos(null), p2: pos(null) } },
      { id: 2, nomeUrna: 'Ana', posicoes: { p1: pos(0), p2: pos(0) } },
      { id: 3, nomeUrna: 'Bruno', posicoes: { p1: pos(2), p2: pos(2) } },
      { id: 4, nomeUrna: 'Álvaro', posicoes: {} },
    ];
    const r = calcularTodos(cands, resp);
    expect(r.map((x) => x.candidato.id)).toEqual([3, 2, 4, 1]);
  });

  it('empates são resolvidos alfabeticamente (critério neutro)', () => {
    const cands = [
      { id: 1, nomeUrna: 'Carla', posicoes: { p1: pos(2), p2: pos(2) } },
      { id: 2, nomeUrna: 'Beatriz', posicoes: { p1: pos(2), p2: pos(2) } },
    ];
    expect(calcularTodos(cands, resp).map((x) => x.candidato.nomeUrna)).toEqual(['Beatriz', 'Carla']);
  });
});
