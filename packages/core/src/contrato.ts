/**
 * Contrato de dados entre o ETL (Python, job `exportar`) e o site (Next.js, export estático).
 *
 * Arquivos gerados em `apps/web/public/dados/` (servidos pela CDN):
 *   meta.json                         → Meta
 *   busca.json                        → IndiceBusca (carregado sob demanda)
 *   lista/{cargo}-{uf}.json           → CandidatoResumo[]
 *   c/{bucket}.json                   → Record<string, PerfilCandidato>   (bucket = id % NUM_BUCKETS)
 *   comparar/{cargo}-{uf}.json        → ComparadorArquivo
 *   bussola/{cargo}-{uf}.json         → BussolaArquivo
 *   economia.json                     → EconomiaArquivo
 *
 * Qualquer mudança aqui exige a mudança correspondente em etl/raiox/jobs/exportar.py
 * (o teste etl/tests/test_contrato.py valida os JSONs gerados contra este formato).
 */

export const NUM_BUCKETS = 5000;
export const bucketDe = (id: number | string): number => Number(BigInt(id) % BigInt(NUM_BUCKETS));

export type CodigoCargo = 1 | 3 | 5 | 6 | 7 | 8;

export const CARGOS: Record<CodigoCargo, { slug: string; nome: string; plural: string; majoritario: boolean }> = {
  1: { slug: 'presidente', nome: 'Presidente', plural: 'Presidência', majoritario: true },
  3: { slug: 'governador', nome: 'Governador(a)', plural: 'Governos estaduais', majoritario: true },
  5: { slug: 'senador', nome: 'Senador(a)', plural: 'Senado', majoritario: true },
  6: { slug: 'deputado-federal', nome: 'Deputado(a) federal', plural: 'Câmara dos Deputados', majoritario: false },
  7: { slug: 'deputado-estadual', nome: 'Deputado(a) estadual', plural: 'Assembleias legislativas', majoritario: false },
  8: { slug: 'deputado-distrital', nome: 'Deputado(a) distrital', plural: 'Câmara Legislativa do DF', majoritario: false },
};

export const UFS = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA',
  'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
] as const;
export type UF = (typeof UFS)[number] | 'BR';

/** Data ISO (AAAA-MM-DD) ou data-hora ISO 8601. */
export type DataISO = string;

// ---------------------------------------------------------------------------
// Fontes / evidências
// ---------------------------------------------------------------------------
export interface Evidencia {
  id: string;
  rotulo: string;
  urlOriginal: string;
  urlArquivo: string | null; // cópia permanente (archive.org)
  sha256: string;
  capturadoEm: DataISO;
}

// ---------------------------------------------------------------------------
// Meta e busca
// ---------------------------------------------------------------------------
export interface Meta {
  geradoEm: DataISO;
  eleicao: { id: number; ano: number; data: DataISO; segundoTurno: DataISO };
  totais: { candidaturas: number; porCargo: Record<string, number> };
  fontes: { id: string; nome: string; atualizadoEm: DataISO | null; url: string }[];
}

/** [id, slug | null, nomeUrna, nomeCivil, partidoSigla, cargoCodigo, uf, numero] */
export type ItemBusca = [number, string | null, string, string, string, CodigoCargo, UF, number];
export type IndiceBusca = ItemBusca[];

export interface CandidatoResumo {
  id: number;
  /** Presente apenas para cargos majoritários (páginas pré-renderizadas em /candidato/[slug]). */
  slug: string | null;
  nomeUrna: string;
  numero: number;
  partido: { sigla: string; nome: string };
  cargo: CodigoCargo;
  uf: UF;
  foto: string | null;
  situacaoRegistro: string;
  situacaoTotalizacao: string;
  reeleicao: boolean;
}

// ---------------------------------------------------------------------------
// Perfil completo
// ---------------------------------------------------------------------------
export interface Bem {
  tipo: string;
  descricao: string;
  valor: number;
}

export interface PatrimonioHistorico {
  ano: number;
  cargo: string;
  uf: string;
  total: number;
  /** Corrigido pelo IPCA até o mês de referência de `Patrimonio.referenciaCorrecao`. */
  totalCorrigido: number | null;
}

export interface Patrimonio {
  total: number;
  bens: Bem[];
  historico: PatrimonioHistorico[];
  referenciaCorrecao: DataISO | null;
}

export interface EleicaoDisputada {
  ano: number;
  cargo: string;
  local: string;
  partido: string;
  resultado: string;
  candidaturaId: number;
}

export interface Mandato {
  cargo: string;
  esfera: 'federal' | 'estadual' | 'municipal';
  local: string | null;
  inicio: DataISO;
  fim: DataISO | null;
  origem: 'tse_eleito' | 'camara' | 'senado' | 'manual';
}

export interface Campanha {
  limiteGasto1T: number | null;
  limiteGasto2T: number | null;
  totalRecebido: number | null;
  totalDespesas: number | null;
  receitas: { origem: string; valor: number }[];
  maioresDoadores: { nome: string; tipo: string; valor: number }[];
  atualizadoEm: DataISO | null;
}

export type VotoRegistrado = 'Sim' | 'Não' | 'Abstenção' | 'Obstrução' | 'Art. 17' | 'Ausente' | string;

export interface VotacaoChave {
  votacaoId: string;
  data: DataISO;
  proposicao: string; // "PEC 45/2019"
  descricao: string;
  temaId: string | null;
  voto: VotoRegistrado;
  resultado: string;
  url: string;
}

export interface Legislativo {
  casa: 'camara' | 'senado';
  idExterno: string;
  urlPerfilOficial: string;
  presenca: { ano: number; sessoes: number; presencas: number; ausenciasJustificadas: number }[];
  votacoesChave: VotacaoChave[];
  cota: { ano: number; total: number; porCategoria: { categoria: string; valor: number }[] }[];
  emendas: { ano: number; empenhado: number; pago: number; quantidade: number }[];
}

export type StatusRegua =
  | 'reu_acao_penal'
  | 'condenado_1a_instancia'
  | 'condenado_orgao_colegiado'
  | 'condenado_transito_julgado'
  | 'absolvido'
  | 'anulado'
  | 'punibilidade_extinta'
  | 'acao_civel_em_curso'
  | 'acao_civel_procedente'
  | 'acao_civel_improcedente';

export interface ProcessoPublico {
  numeroCnj: string;
  tribunal: string;
  classe: string | null;
  assuntos: string[];
  status: StatusRegua;
  statusDescricao: string;
  ativo: boolean;
  ultimaMovimentacao: { data: DataISO; descricao: string } | null;
  consultaUrl: string;
  evidencias: Evidencia[];
  publicadoEm: DataISO;
}

export interface CertidaoPublica {
  tipo: string; // "Certidão criminal da Justiça Federal de 1º grau"
  resultado: 'negativa' | 'positiva' | 'inconclusiva' | 'ilegivel' | 'nao_analisada';
  documento: Evidencia | null;
}

export interface Justica {
  certidoes: CertidaoPublica[];
  processos: ProcessoPublico[];
}

export interface ChecagemPublica {
  agencia: string;
  url: string;
  titulo: string | null;
  alegacao: string;
  avaliacaoOriginal: string;
  dataPublicacao: DataISO | null;
  relacao: 'autor_da_alegacao' | 'alvo_da_alegacao' | null;
  temaId: string | null;
}

export interface Trecho {
  texto: string;
  pagina: number;
}

export interface PropostaPublica {
  temaId: string;
  resumo: string | null;
  trechos: Trecho[];
  semMencao: boolean;
  geradoPorIa: boolean;
  documento: Evidencia | null;
}

export interface PerfilCandidato {
  id: number;
  slug: string | null;
  nomeUrna: string;
  nomeCivil: string;
  numero: number;
  partido: { sigla: string; nome: string; numero: number };
  coligacao: { nome: string | null; composicao: string | null };
  cargo: CodigoCargo;
  uf: UF;
  situacaoRegistro: string;
  situacaoTotalizacao: string;
  reeleicao: boolean;
  foto: string | null;
  dadosPessoais: {
    nascimento: DataISO | null;
    genero: string | null;
    corRaca: string | null;
    grauInstrucao: string | null;
    ocupacao: string | null;
    naturalidade: string | null;
  };
  vices: { nomeUrna: string; cargo: string; partido: string; foto: string | null }[];
  sites: string[];
  patrimonio: Patrimonio;
  trajetoria: { eleicoes: EleicaoDisputada[]; mandatos: Mandato[] };
  campanha: Campanha | null;
  legislativo: Legislativo[];
  justica: Justica;
  checagens: ChecagemPublica[];
  propostas: PropostaPublica[] | null; // null = cargo sem plano de governo (proporcionais/senado)
  fontes: Evidencia[];
  changelog: { data: DataISO; tipo: string; descricao: string }[];
  urlTse: string;
  atualizadoEm: DataISO;
}

// ---------------------------------------------------------------------------
// Comparador
// ---------------------------------------------------------------------------
export interface Tema {
  id: string;
  eixo: string;
  nome: string;
  descricao: string;
}

export interface ComparadorArquivo {
  cargo: CodigoCargo;
  uf: UF;
  temas: Tema[];
  candidatos: (CandidatoResumo & { propostas: PropostaPublica[] })[];
}

// ---------------------------------------------------------------------------
// Bússola
// ---------------------------------------------------------------------------
export interface PerguntaBussola {
  id: string;
  temaId: string;
  texto: string;
  contexto: string;
  argumentoFavor: string;
  argumentoContra: string;
}

/** Posição documentada de um candidato numa pergunta. valor null = sem posição pública documentada. */
export interface PosicaoBussola {
  valor: -2 | -1 | 0 | 1 | 2 | null;
  fonte: 'voto' | 'proposta' | 'declaracao';
  justificativa: string;
  evidencia: Evidencia | null;
}

export interface BussolaArquivo {
  cargo: CodigoCargo;
  uf: UF;
  perguntas: PerguntaBussola[];
  candidatos: (CandidatoResumo & { posicoes: Record<string, PosicaoBussola> })[];
}

// ---------------------------------------------------------------------------
// Economia
// ---------------------------------------------------------------------------
export interface IndicadorEconomico {
  id: string;
  nome: string;
  unidade: string;
  fonte: string;
  descricao: string;
  periodicidade: string;
  urlFonte: string;
  porUf: boolean;
  /** Série nacional: [data, valor][] */
  serie: [DataISO, number][];
  /** Séries por UF (quando porUf). */
  seriesUf?: Partial<Record<UF, [DataISO, number][]>>;
}

export interface PeriodoGoverno {
  cargo: 'presidente' | 'governador';
  uf: UF;
  nome: string;
  inicio: DataISO;
  fim: DataISO | null;
  fonteUrl: string;
}

export interface EconomiaArquivo {
  atualizadoEm: DataISO;
  indicadores: IndicadorEconomico[];
  periodos: PeriodoGoverno[];
}
