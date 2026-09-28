import { describe, expect, it } from 'vitest';
import { formatarMoeda, formatarVariacao, idade, nomeProprio, normalizarBusca } from './formatos';
import { bucketDe } from './contrato';

describe('formatos', () => {
  it('moeda em pt-BR', () => {
    expect(formatarMoeda(1234.5).replace(/\s/g, ' ')).toBe('R$ 1.234,50');
    expect(formatarMoeda(null)).toBe('—');
  });
  it('variação com sinal', () => {
    expect(formatarVariacao(12.345)).toBe('+12,3%');
    expect(formatarVariacao(-3)).toBe('−3,0%');
  });
  it('idade na data da eleição', () => {
    expect(idade('1950-04-08')).toBe(76);
    expect(idade('1990-10-05')).toBe(35);
    expect(idade('1990-10-04')).toBe(36);
  });
  it('normaliza busca', () => {
    expect(normalizarBusca('  JOSÉ  da Conceição ')).toBe('jose da conceicao');
  });
  it('nome próprio', () => {
    expect(nomeProprio('EDMILSON SILVA DA COSTA')).toBe('Edmilson Silva da Costa');
  });
  it('bucket estável para ids grandes', () => {
    expect(bucketDe(280002551975)).toBe(280002551975 % 5000);
    expect(bucketDe('280002551975')).toBe(1975);
  });
});
