/**
 * Gerador determinístico de dados FICTÍCIOS para desenvolvimento.
 *
 * Escopo do produto: SOMENTE a eleição presidencial 2026 (14 candidaturas, com vices).
 * Produz `apps/web/fixtures/dados/**` seguindo EXATAMENTE `@raiox/core/contrato`.
 * Nenhum nome, partido ou número aqui corresponde a pessoas ou siglas reais.
 *
 * Rodar: node --experimental-strip-types fixtures/gerar.ts
 * Depois: pnpm dados:fixture (copia para public/dados com meta.fixture=true)
 */
import { mkdir, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  CARGOS,
  NUM_BUCKETS,
  bucketDe,
  chaveArquivo,
  type UF,
  type Evidencia,
  type CandidatoResumo,
  type PerfilCandidato,
  type Bem,
  type PatrimonioHistorico,
  type ProcessoPublico,
  type StatusRegua,
  type ChecagemPublica,
  type PropostaPublica,
  type Legislativo,
  type VotacaoChave,
  type Meta,
  type ComparadorArquivo,
  type BussolaArquivo,
  type PerguntaBussola,
  type PosicaoBussola,
  type EconomiaArquivo,
  type IndicadorEconomico,
  type CorrecoesArquivo,
  type Tema,
} from "@raiox/core/contrato";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const SAIDA = path.join(AQUI, "dados");
const CARGO_PRESIDENTE = 1 as const;
const UF_BR: UF = "BR";

// ---------------------------------------------------------------------------
// Aleatoriedade determinística (mulberry32) — mesma saída sempre.
// ---------------------------------------------------------------------------
function criarRng(semente: number) {
  let a = semente >>> 0;
  return function rng() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const escolher = <T,>(arr: readonly T[], rng: () => number): T => arr[Math.floor(rng() * arr.length)]!;
const inteiro = (min: number, max: number, rng: () => number) => Math.floor(rng() * (max - min + 1)) + min;

function slugificar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

let contadorSha = 1;
function shaFalso(): string {
  const n = (contadorSha++).toString(16).padStart(8, "0");
  return n.repeat(8).slice(0, 64);
}

let contadorEvidencia = 1;
function evidencia(rotulo: string, urlOriginal: string, arquivada = true): Evidencia {
  return {
    id: `ev-${contadorEvidencia++}`,
    rotulo,
    urlOriginal,
    urlArquivo: arquivada ? `https://web.archive.org/web/2026/${urlOriginal}` : null,
    sha256: shaFalso(),
    capturadoEm: "2026-09-20T08:00:00-03:00",
  };
}

// ---------------------------------------------------------------------------
// Partidos fictícios (nenhuma sigla real; sem cor associada)
// ---------------------------------------------------------------------------
const PARTIDOS: { sigla: string; nome: string; numero: number }[] = [
  { sigla: "PEX", nome: "Partido Exemplo", numero: 11 },
  { sigla: "PZT", nome: "Partido Zenital", numero: 12 },
  { sigla: "PQV", nome: "Partido Qualidade de Vida", numero: 13 },
  { sigla: "PBT", nome: "Partido Base Territorial", numero: 14 },
  { sigla: "PJX", nome: "Partido Justiça Cívica Exemplar", numero: 15 },
  { sigla: "PVZ", nome: "Partido Vertente Zeta", numero: 16 },
  { sigla: "PMK", nome: "Partido Modelo Cívico", numero: 17 },
  { sigla: "PRY", nome: "Partido Raiz Popular", numero: 18 },
  { sigla: "PDX", nome: "Partido Diálogo Exemplar", numero: 19 },
  { sigla: "PLC", nome: "Partido Livre Consenso", numero: 20 },
  { sigla: "PFC", nome: "Partido Formato Cívico", numero: 21 },
  { sigla: "PSC2", nome: "Partido Semente Cívica", numero: 22 },
  { sigla: "PGH", nome: "Partido Grande Horizonte", numero: 23 },
  { sigla: "PXQ", nome: "Partido Exemplo Alternativo", numero: 24 },
];

const TEMAS: Tema[] = [
  { id: "economia", eixo: "Economia & Tributação", nome: "Economia & Tributação", descricao: "Impostos, gasto público, câmbio e crescimento." },
  { id: "previdencia", eixo: "Previdência & Trabalho", nome: "Previdência & Trabalho", descricao: "Aposentadoria, legislação trabalhista e emprego." },
  { id: "agro-ambiente", eixo: "Agro & Meio Ambiente", nome: "Agro & Meio Ambiente", descricao: "Produção agropecuária, clima e proteção ambiental." },
  { id: "educacao-saude", eixo: "Educação & Saúde", nome: "Educação & Saúde", descricao: "Ensino público, universidades e sistema de saúde." },
  { id: "seguranca", eixo: "Segurança Pública", nome: "Segurança Pública", descricao: "Polícia, sistema prisional e política criminal." },
  { id: "governanca", eixo: "Governança & Combate à Corrupção", nome: "Governança & Combate à Corrupção", descricao: "Transparência, controle e integridade pública." },
];

const AGENCIAS_CHECAGEM = ["Verifica Já", "Checa Público", "Análise Aberta", "Dados Conferidos"];

function bem(tipo: string, descricao: string, valor: number): Bem {
  return { tipo, descricao, valor };
}

function historico(anos: number[], base: number, rng: () => number): PatrimonioHistorico[] {
  return anos.map((ano, i) => {
    const total = Math.round(base * (0.55 + i * 0.22 + rng() * 0.3));
    return {
      ano,
      cargo: ano === 2026 ? "Presidente" : "Candidato(a) — eleição anterior (exemplo)",
      uf: "BR",
      total,
      totalCorrigido: Math.round(total * (1 + (anos.length - 1 - i) * 0.08)),
    };
  });
}

const STATUS_LABEL: Record<StatusRegua, string> = {
  reu_acao_penal: "Réu em ação penal — sem condenação",
  condenado_1a_instancia: "Condenado em 1ª instância — cabe recurso",
  condenado_orgao_colegiado: "Condenado por órgão colegiado — cabe recurso",
  condenado_transito_julgado: "Condenação definitiva",
  absolvido: "Absolvido",
  anulado: "Processo anulado",
  punibilidade_extinta: "Punibilidade extinta (prescrição)",
  acao_civel_em_curso: "Ação cível em curso",
  acao_civel_procedente: "Ação cível — pedido procedente",
  acao_civel_improcedente: "Ação cível — pedido improcedente",
};

function processo(status: StatusRegua, numero: string, ativo: boolean): ProcessoPublico {
  return {
    numeroCnj: numero,
    tribunal: "Tribunal Regional Fictício da 9ª Região",
    classe: status.startsWith("acao_civel") ? "Ação Civil Pública (exemplo)" : "Ação Penal Pública (exemplo)",
    assuntos: [status.startsWith("acao_civel") ? "Improbidade administrativa (exemplo)" : "Crime contra a Administração Pública (exemplo)"],
    status,
    statusDescricao: STATUS_LABEL[status],
    ativo,
    ultimaMovimentacao: { data: "2026-08-15", descricao: "Juntada de petição (movimentação de exemplo)." },
    consultaUrl: "https://www.cnj.jus.br/pjecor/ConsultaPublica/DetalheProcessoConsultaPublica/documentoSemLoginHTML.seam",
    evidencias: [evidencia("Certidão de andamento processual (exemplo)", "https://www.tjex.jus.br/processo/exemplo")],
    publicadoEm: "2026-09-15T00:00:00-03:00",
  };
}

let seqId = 100000;
function proximoId() {
  seqId += 1;
  return seqId;
}

interface Papel {
  tipo: "rico" | "vazio" | "padrao" | StatusRegua;
  reeleicao?: boolean;
  certidaoPositiva?: boolean;
  temLegislativo?: boolean;
}

function gerarCandidato(nomeUrna: string, nomeCivil: string, numero: number, partido: (typeof PARTIDOS)[number], papel: Papel, rng: () => number): PerfilCandidato {
  const id = proximoId();
  const slug = `${slugificar(nomeUrna)}-br`;
  const vazio = papel.tipo === "vazio";

  const bens: Bem[] = vazio
    ? []
    : [
        bem("Bens imóveis", "Apartamento residencial (exemplo)", inteiro(300000, 1200000, rng)),
        bem("Bens imóveis", "Imóvel rural (exemplo)", inteiro(0, 900000, rng)),
        bem("Veículos automotores", "Automóvel de passeio (exemplo)", inteiro(40000, 150000, rng)),
        bem("Aplicações e fundos", "Fundo de investimento (exemplo)", inteiro(20000, 500000, rng)),
        bem("Participações societárias", "Cotas de empresa (exemplo)", inteiro(0, 600000, rng)),
      ].filter((b) => b.valor > 0);
  const totalBens = bens.reduce((s, b) => s + b.valor, 0);

  const patrimonio = {
    total: totalBens,
    bens,
    historico: vazio ? [] : historico([2014, 2018, 2022, 2026], Math.max(totalBens, 150000), rng),
    referenciaCorrecao: vazio ? null : "2026-08-01",
  };

  const eleicoesAnteriores = vazio
    ? []
    : [
        {
          ano: 2022,
          cargo: escolher(["Senador(a) (exemplo)", "Deputado(a) federal (exemplo)", "Governador(a) (exemplo)"], rng),
          local: escolher(["SP", "MG", "RS", "BA", "PR"], rng),
          partido: partido.sigla,
          resultado: rng() > 0.4 ? "Eleito(a)" : "Não eleito(a)",
          candidaturaId: proximoId(),
        },
        {
          ano: 2018,
          cargo: "Deputado(a) federal (exemplo)",
          local: escolher(["SP", "MG", "RS", "BA", "PR"], rng),
          partido: partido.sigla,
          resultado: rng() > 0.5 ? "Eleito(a)" : "Não eleito(a)",
          candidaturaId: proximoId(),
        },
      ];
  const mandatos = vazio
    ? []
    : eleicoesAnteriores
        .filter((e) => e.resultado === "Eleito(a)")
        .map((e) => ({
          cargo: e.cargo.replace(" (exemplo)", ""),
          esfera: "federal" as const,
          local: e.local,
          inicio: `${e.ano + 1}-01-01`,
          fim: `${e.ano + 4}-12-31`,
          origem: "manual" as const,
        }));

  const campanha = vazio
    ? null
    : {
        limiteGasto1T: inteiro(40000000, 80000000, rng),
        limiteGasto2T: inteiro(30000000, 60000000, rng),
        totalRecebido: inteiro(5000000, 70000000, rng),
        totalDespesas: inteiro(4000000, 65000000, rng),
        receitas: [
          { origem: "Recursos próprios", valor: inteiro(10000, 500000, rng) },
          { origem: "Doações de pessoas físicas", valor: inteiro(100000, 3000000, rng) },
          { origem: "Fundo Partidário", valor: inteiro(200000, 4000000, rng) },
          { origem: "Fundo Especial de Financiamento de Campanha (FEFC)", valor: inteiro(2000000, 45000000, rng) },
        ],
        maioresDoadores: [
          { nome: "Doador(a) Exemplo 1", tipo: "Pessoa física", valor: inteiro(20000, 50000, rng) },
          { nome: "Doador(a) Exemplo 2", tipo: "Pessoa física", valor: inteiro(20000, 50000, rng) },
          { nome: "Comitê Financeiro Estadual (exemplo)", tipo: "Recurso de partido", valor: inteiro(100000, 900000, rng) },
        ],
        atualizadoEm: "2026-09-18T00:00:00-03:00",
      };

  const legislativo: Legislativo[] = !papel.temLegislativo || vazio
    ? []
    : [
        {
          casa: escolher(["camara", "senado"] as const, rng),
          idExterno: String(inteiro(10000, 99999, rng)),
          urlPerfilOficial: "https://www.congressonacional.leg.br/exemplo",
          presenca: [
            { ano: 2020, sessoes: 180, presencas: inteiro(120, 178, rng), ausenciasJustificadas: inteiro(0, 10, rng) },
            { ano: 2021, sessoes: 190, presencas: inteiro(130, 188, rng), ausenciasJustificadas: inteiro(0, 10, rng) },
            { ano: 2022, sessoes: 150, presencas: inteiro(100, 148, rng), ausenciasJustificadas: inteiro(0, 8, rng) },
          ],
          votacoesChave: gerarVotacoes(rng),
          cota: [
            {
              ano: 2021,
              total: inteiro(80000, 250000, rng),
              porCategoria: [
                { categoria: "Passagens aéreas", valor: inteiro(10000, 40000, rng) },
                { categoria: "Combustíveis e lubrificantes", valor: inteiro(5000, 20000, rng) },
                { categoria: "Divulgação da atividade parlamentar", valor: inteiro(5000, 30000, rng) },
              ],
            },
          ],
          emendas: [{ ano: 2021, empenhado: inteiro(500000, 5000000, rng), pago: inteiro(300000, 4500000, rng), quantidade: inteiro(1, 12, rng) }],
        },
      ];

  let processos: ProcessoPublico[] = [];
  const statusEspecial: StatusRegua[] = [
    "reu_acao_penal",
    "condenado_1a_instancia",
    "condenado_orgao_colegiado",
    "condenado_transito_julgado",
    "absolvido",
    "anulado",
    "punibilidade_extinta",
    "acao_civel_em_curso",
    "acao_civel_procedente",
    "acao_civel_improcedente",
  ];
  if ((statusEspecial as string[]).includes(papel.tipo)) {
    processos = [processo(papel.tipo as StatusRegua, `${inteiro(1000000, 9999999, rng)}-${inteiro(10, 99, rng)}.2024.8.09.0001`, true)];
  } else if (papel.tipo === "rico") {
    processos = [
      processo("reu_acao_penal", `${inteiro(1000000, 9999999, rng)}-${inteiro(10, 99, rng)}.2023.8.09.0001`, true),
      processo("acao_civel_em_curso", `${inteiro(1000000, 9999999, rng)}-${inteiro(10, 99, rng)}.2024.4.01.3400`, true),
    ];
  }

  const certidoes = vazio
    ? [{ tipo: "Certidão criminal da Justiça Federal de 1º grau", resultado: "nao_analisada" as const, documento: null }]
    : [
        {
          tipo: "Certidão criminal da Justiça Federal de 1º grau",
          resultado: papel.certidaoPositiva ? ("positiva" as const) : ("negativa" as const),
          documento: evidencia("Certidão criminal — Justiça Federal", "https://www.jfex.jus.br/certidao/exemplo"),
        },
        {
          tipo: "Certidão criminal da Justiça Estadual de 1º grau",
          resultado: papel.certidaoPositiva ? ("inconclusiva" as const) : ("negativa" as const),
          documento: evidencia("Certidão criminal — Justiça Estadual", "https://www.tjex.jus.br/certidao/exemplo"),
        },
        {
          tipo: "Certidão criminal da Justiça Eleitoral",
          resultado: "negativa" as const,
          documento: evidencia("Certidão criminal — Justiça Eleitoral", "https://www.tseex.jus.br/certidao/exemplo"),
        },
      ];

  const checagens: ChecagemPublica[] = vazio
    ? []
    : Array.from({ length: papel.tipo === "rico" || papel.certidaoPositiva ? 4 : inteiro(1, 2, rng) }, (_, i) => ({
        agencia: escolher(AGENCIAS_CHECAGEM, rng),
        url: `https://checagem.exemplo.org/verificacao-${i + 1}`,
        titulo: `É #Verificado: declaração sobre ${escolher(TEMAS, rng).nome.toLowerCase()} (exemplo)`,
        alegacao: "Alegação fictícia usada apenas para testar o layout desta seção.",
        avaliacaoOriginal: escolher(["Verdadeiro", "Falso", "Impreciso", "Sem contexto"], rng),
        dataPublicacao: "2026-09-10",
        relacao: escolher(["autor_da_alegacao", "alvo_da_alegacao"] as const, rng),
        temaId: escolher(TEMAS, rng).id,
      }));

  const propostas: PropostaPublica[] = TEMAS.map((tema, i) => {
    const semMencao = vazio || (i % 3 === 2 && papel.tipo !== "rico" && papel.tipo !== "padrao");
    return {
      temaId: tema.id,
      resumo: semMencao ? null : `Resumo de exemplo do plano de governo sobre ${tema.nome.toLowerCase()}, gerado apenas para teste (≤ 280 caracteres).`,
      trechos: semMencao
        ? []
        : [{ texto: `"Trecho literal fictício do plano de governo sobre ${tema.nome.toLowerCase()}, usado apenas para teste de layout."`, pagina: inteiro(3, 60, rng) }],
      semMencao,
      geradoPorIa: !semMencao,
      documento: semMencao ? null : evidencia(`Plano de governo (PDF) — ${tema.nome}`, "https://divulgacandcontas.tse.jus.br/plano-exemplo.pdf"),
    };
  });

  const fontes: Evidencia[] = [
    evidencia("Registro de candidatura (TSE)", "https://divulgacandcontas.tse.jus.br/candidato/exemplo"),
    ...(vazio ? [] : [evidencia("Declaração de bens (TSE)", "https://divulgacandcontas.tse.jus.br/bens/exemplo"), evidencia("Plano de governo protocolado (TSE)", "https://divulgacandcontas.tse.jus.br/plano-exemplo.pdf")]),
  ];

  const changelog = vazio
    ? []
    : [
        { data: "2026-09-05T10:00:00-03:00", tipo: "criacao", descricao: "Perfil publicado com os dados do registro de candidatura." },
        { data: "2026-09-20T09:00:00-03:00", tipo: "atualizacao", descricao: "Atualização de dados de campanha a partir da prestação de contas parcial (exemplo)." },
      ];

  const dadosPessoais = vazio
    ? { nascimento: null, genero: null, corRaca: null, grauInstrucao: null, ocupacao: null, naturalidade: null }
    : {
        nascimento: `19${inteiro(55, 80, rng)}-0${inteiro(1, 9, rng)}-1${inteiro(0, 8, rng)}`,
        genero: nomeUrna.startsWith("Candidata") ? "Feminino" : "Masculino",
        corRaca: escolher(["Branca", "Parda", "Preta", "Amarela", "Indígena"], rng),
        grauInstrucao: escolher(["Ensino médio completo", "Ensino superior completo", "Ensino superior incompleto", "Pós-graduação"], rng),
        ocupacao: escolher(["Advogado(a)", "Professor(a)", "Empresário(a)", "Médico(a)", "Servidor(a) público(a)", "Engenheiro(a)"], rng),
        naturalidade: `Cidade Exemplo/${escolher(["SP", "MG", "RS", "BA", "PR", "PE"], rng)}`,
      };

  return {
    id,
    slug,
    nomeUrna,
    nomeCivil,
    numero,
    partido: { sigla: partido.sigla, nome: partido.nome, numero: partido.numero },
    coligacao: { nome: "Coligação Exemplo pelo Futuro", composicao: `${partido.sigla} / ${escolher(PARTIDOS, rng).sigla} / ${escolher(PARTIDOS, rng).sigla}` },
    cargo: CARGO_PRESIDENTE,
    uf: UF_BR,
    situacaoRegistro: "Deferido",
    situacaoTotalizacao: "Apto(a)",
    reeleicao: Boolean(papel.reeleicao),
    foto: null,
    dadosPessoais,
    vices: [{ nomeUrna: `Vice Exemplo de ${nomeUrna}`, cargo: "Vice-presidente", partido: escolher(PARTIDOS, rng).sigla, foto: null }],
    sites: vazio ? [] : ["https://exemplo-campanha.org"],
    patrimonio,
    trajetoria: { eleicoes: eleicoesAnteriores, mandatos },
    campanha,
    legislativo,
    justica: { certidoes, processos },
    checagens,
    propostas,
    fontes,
    changelog,
    urlTse: "https://divulgacandcontas.tse.jus.br/candidato/exemplo",
    atualizadoEm: "2026-09-26T06:00:00-03:00",
  };
}

function gerarVotacoes(rng: () => number): VotacaoChave[] {
  const materias = [
    { proposicao: "PEC 45/2019 (exemplo)", descricao: "Reforma tributária — texto-base (votação de exemplo)." },
    { proposicao: "PL 2630/2020 (exemplo)", descricao: "Regulação de plataformas digitais (votação de exemplo)." },
    { proposicao: "PEC 6/2019 (exemplo)", descricao: "Reforma da previdência — texto-base (votação de exemplo)." },
    { proposicao: "PL 6299/2002 (exemplo)", descricao: "Marco regulatório de agrotóxicos (votação de exemplo)." },
  ];
  return materias.map((m, i) => ({
    votacaoId: `vot-${i}-${inteiro(1000, 9999, rng)}`,
    data: `202${1 + i}-0${i + 3}-1${i}`,
    proposicao: m.proposicao,
    descricao: m.descricao,
    temaId: escolher(TEMAS, rng).id,
    voto: escolher(["Sim", "Não", "Abstenção", "Obstrução", "Ausente"] as const, rng),
    resultado: "Aprovado (exemplo)",
    url: "https://www.camara.leg.br/votacao/exemplo",
  }));
}

// ---------------------------------------------------------------------------
// Os 14 candidatos à Presidência (ordem de criação; a ordenação pública é
// sempre alfabética por nome de urna, calculada na hora de gravar).
// ---------------------------------------------------------------------------
const NOMES_A_N = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N"];

function nomeGenerico(indice: number): { urna: string; civil: string } {
  const letra = NOMES_A_N[indice]!;
  const feminino = indice % 2 === 0;
  const urna = `${feminino ? "Candidata Exemplo" : "Candidato Exemplo"} ${letra}`;
  return { urna, civil: `${urna} da Silva Fictício(a)` };
}

const rngPrincipal = criarRng(20261004);
const PAPEIS: Papel[] = [
  { tipo: "rico", temLegislativo: true }, // A
  { tipo: "vazio" }, // B — perfil totalmente vazio (isonomia)
  { tipo: "condenado_1a_instancia" }, // C
  { tipo: "condenado_orgao_colegiado", temLegislativo: true }, // D
  { tipo: "condenado_transito_julgado" }, // E
  { tipo: "absolvido", temLegislativo: true }, // F
  { tipo: "anulado" }, // G
  { tipo: "punibilidade_extinta" }, // H
  { tipo: "acao_civel_em_curso", temLegislativo: true }, // I
  { tipo: "acao_civel_procedente" }, // J
  { tipo: "acao_civel_improcedente", temLegislativo: true }, // K
  { tipo: "reu_acao_penal", certidaoPositiva: true }, // L — certidão positiva/inconclusiva + checagens
  { tipo: "padrao", reeleicao: true, temLegislativo: true }, // M — reeleição
  { tipo: "padrao" }, // N — registro limpo (contraste isonômico com B)
];

const candidatos: PerfilCandidato[] = NOMES_A_N.map((_, i) => {
  const { urna, civil } = nomeGenerico(i);
  const partido = PARTIDOS[i % PARTIDOS.length]!;
  return gerarCandidato(urna, civil, 10 + i, partido, PAPEIS[i]!, rngPrincipal);
});

// ---------------------------------------------------------------------------
// Escrita dos arquivos
// ---------------------------------------------------------------------------
async function escrever(relativo: string, dado: unknown) {
  const destino = path.join(SAIDA, relativo);
  await mkdir(path.dirname(destino), { recursive: true });
  await writeFile(destino, JSON.stringify(dado));
}

function paraResumo(p: PerfilCandidato): CandidatoResumo {
  return {
    id: p.id,
    slug: p.slug,
    nomeUrna: p.nomeUrna,
    numero: p.numero,
    partido: { sigla: p.partido.sigla, nome: p.partido.nome },
    cargo: p.cargo,
    uf: p.uf,
    foto: p.foto,
    situacaoRegistro: p.situacaoRegistro,
    situacaoTotalizacao: p.situacaoTotalizacao,
    reeleicao: p.reeleicao,
  };
}

function serieMensal(inicioAno: number, inicioMes: number, n: number, base: number, variacao: number, rng: () => number, tendencia = 0): [string, number][] {
  const pontos: [string, number][] = [];
  let valor = base;
  let ano = inicioAno;
  let mes = inicioMes;
  for (let i = 0; i < n; i++) {
    valor += (rng() - 0.5) * variacao + tendencia;
    pontos.push([`${ano}-${String(mes).padStart(2, "0")}-01`, Math.round(valor * 100) / 100]);
    mes += 1;
    if (mes > 12) {
      mes = 1;
      ano += 1;
    }
  }
  return pontos;
}

function gerarEconomia(): EconomiaArquivo {
  const rng = criarRng(555);
  const indicadores: IndicadorEconomico[] = [
    { id: "ipca12m", nome: "IPCA acumulado em 12 meses", unidade: "% em 12 meses", fonte: "IBGE", descricao: "Variação do Índice de Preços ao Consumidor Amplo nos últimos 12 meses.", periodicidade: "Mensal", urlFonte: "https://sidra.ibge.gov.br/tabela/1737", porUf: false, serie: serieMensal(2019, 1, 93, 4.5, 1.2, rng) },
    { id: "selic", nome: "Taxa Selic meta", unidade: "% ao ano", fonte: "Banco Central (SGS 432)", descricao: "Meta da taxa básica de juros definida pelo Copom.", periodicidade: "Por reunião do Copom", urlFonte: "https://www3.bcb.gov.br/sgspub", porUf: false, serie: serieMensal(2019, 1, 93, 8, 0.6, rng) },
    { id: "dbgg", nome: "Dívida Bruta do Governo Geral", unidade: "% do PIB", fonte: "Banco Central (SGS 13762)", descricao: "Dívida bruta do governo geral como proporção do PIB.", periodicidade: "Mensal", urlFonte: "https://www3.bcb.gov.br/sgspub", porUf: false, serie: serieMensal(2019, 1, 93, 75, 0.8, rng, 0.05) },
    { id: "desocupacao", nome: "Taxa de desocupação", unidade: "% da força de trabalho", fonte: "IBGE — PNAD Contínua", descricao: "Proporção de pessoas desocupadas na força de trabalho, média móvel trimestral, Brasil.", periodicidade: "Trimestral", urlFonte: "https://sidra.ibge.gov.br/tabela/6381", porUf: false, serie: serieMensal(2019, 1, 31, 11, 1.5, rng) },
    { id: "caged", nome: "Saldo de empregos formais (CAGED)", unidade: "Vagas líquidas no mês", fonte: "Novo CAGED / MTE", descricao: "Diferença entre admissões e desligamentos formais no mês, Brasil.", periodicidade: "Mensal", urlFonte: "https://www.gov.br/trabalho-e-emprego/pt-br/novo-caged", porUf: false, serie: serieMensal(2019, 1, 93, 150000, 80000, rng) },
    { id: "pib", nome: "PIB — variação trimestral", unidade: "% (dessazonalizado)", fonte: "IBGE — Contas Nacionais", descricao: "Variação do PIB frente ao trimestre imediatamente anterior, com ajuste sazonal.", periodicidade: "Trimestral", urlFonte: "https://sidra.ibge.gov.br/tabela/5932", porUf: false, serie: serieMensal(2019, 1, 31, 0.4, 0.8, rng) },
    { id: "dolar", nome: "Taxa de câmbio (R$/US$)", unidade: "R$ por US$, venda", fonte: "Banco Central (PTAX)", descricao: "Cotação média de venda do dólar americano.", periodicidade: "Diária (agregado mensal)", urlFonte: "https://www3.bcb.gov.br/sgspub", porUf: false, serie: serieMensal(2019, 1, 93, 4.2, 0.3, rng, 0.01) },
    { id: "resultado-primario", nome: "Resultado primário do governo central", unidade: "% do PIB (acumulado 12 meses)", fonte: "Tesouro Nacional", descricao: "Diferença entre receitas e despesas primárias do governo central, acumulada em 12 meses.", periodicidade: "Mensal", urlFonte: "https://www.gov.br/tesouronacional", porUf: false, serie: serieMensal(2019, 1, 93, -1, 0.5, rng) },
  ];

  return {
    atualizadoEm: "2026-09-27T08:00:00-03:00",
    indicadores,
    periodos: [
      { cargo: "presidente", uf: "BR", nome: "Mandato presidencial 2015–2018 (exemplo)", inicio: "2015-01-01", fim: "2018-12-31", fonteUrl: "https://www.gov.br/planalto" },
      { cargo: "presidente", uf: "BR", nome: "Mandato presidencial 2019–2022 (exemplo)", inicio: "2019-01-01", fim: "2022-12-31", fonteUrl: "https://www.gov.br/planalto" },
      { cargo: "presidente", uf: "BR", nome: "Mandato presidencial 2023–2026 (exemplo)", inicio: "2023-01-01", fim: "2026-12-31", fonteUrl: "https://www.gov.br/planalto" },
    ],
  };
}

async function principal() {
  await rm(SAIDA, { recursive: true, force: true });

  const porBucket = new Map<number, Record<string, PerfilCandidato>>();
  for (const c of candidatos) {
    const b = bucketDe(c.id);
    if (!porBucket.has(b)) porBucket.set(b, {});
    porBucket.get(b)![String(c.id)] = c;
  }
  for (const [bucket, registro] of porBucket) {
    await escrever(`c/${bucket}.json`, registro);
  }

  const colacaoAlfabetica = new Intl.Collator("pt-BR", { sensitivity: "base" });
  const ordenados = [...candidatos].sort((a, b) => colacaoAlfabetica.compare(a.nomeUrna, b.nomeUrna));
  await escrever(`lista/${chaveArquivo(CARGO_PRESIDENTE, UF_BR)}.json`, ordenados.map(paraResumo));

  // --- Comparador -----------------------------------------------------------
  const comparador: ComparadorArquivo = {
    cargo: CARGO_PRESIDENTE,
    uf: UF_BR,
    temas: TEMAS,
    candidatos: ordenados.map((c) => ({ ...paraResumo(c), propostas: c.propostas! })),
  };
  await escrever(`comparar/${chaveArquivo(CARGO_PRESIDENTE, UF_BR)}.json`, comparador);

  // --- Bússola ---------------------------------------------------------------
  const perguntas: PerguntaBussola[] = [
    { id: "p1", temaId: "economia", texto: "O Estado deveria reduzir impostos sobre a folha de pagamento para estimular a contratação formal?", contexto: "Hoje parte da tributação brasileira incide sobre a folha de salários.", argumentoFavor: "Reduzir encargos baratearia a contratação formal.", argumentoContra: "A União perderia arrecadação usada em políticas públicas." },
    { id: "p2", temaId: "previdencia", texto: "As regras de aposentadoria deveriam ser as mesmas para todas as categorias profissionais?", contexto: "Hoje existem regras diferentes por categoria e por regime (público/privado).", argumentoFavor: "Regras únicas simplificariam o sistema e reduziriam desigualdades entre categorias.", argumentoContra: "Categorias com atividades de risco ou desgaste alegam necessidade de regras específicas." },
    { id: "p3", temaId: "agro-ambiente", texto: "O licenciamento ambiental para grandes obras deveria ser simplificado?", contexto: "O processo de licenciamento envolve várias etapas e órgãos federais e estaduais.", argumentoFavor: "Simplificar reduziria prazos e custos para investimentos.", argumentoContra: "Etapas de licenciamento existem para prevenir danos ambientais irreversíveis." },
    { id: "p4", temaId: "educacao-saude", texto: "O investimento público em universidades federais deveria aumentar mesmo que outras áreas recebam menos recursos?", contexto: "O orçamento público é limitado e a alocação entre áreas é uma escolha explícita.", argumentoFavor: "Universidades federais formam pesquisa e mão de obra qualificada.", argumentoContra: "Outras prioridades, como saúde básica, podem ter retorno social mais imediato." },
    { id: "p5", temaId: "seguranca", texto: "Policiais deveriam responder a processos na Justiça comum (e não militar) em casos de morte de civis em serviço?", contexto: "Hoje esses casos podem tramitar na Justiça Militar estadual, a depender da fase.", argumentoFavor: "A Justiça comum traria mais transparência ao julgamento desses casos.", argumentoContra: "A Justiça Militar tem conhecimento técnico sobre as condições do policiamento." },
    { id: "p6", temaId: "governanca", texto: "O sigilo de agendas de autoridades públicas deveria ser eliminado por completo?", contexto: "Parte dos compromissos oficiais de autoridades é hoje classificada como reservada.", argumentoFavor: "Transparência total facilitaria o controle social sobre decisões públicas.", argumentoContra: "Certas negociações exigem sigilo temporário para viabilizar acordos." },
    { id: "p7", temaId: "economia", texto: "Empresas estatais deveriam poder ser vendidas para o setor privado quando o governo entender conveniente?", contexto: "O Brasil tem um conjunto de empresas de capital majoritariamente público em diferentes setores.", argumentoFavor: "A venda poderia gerar receita e eficiência operacional.", argumentoContra: "Setores estratégicos poderiam perder direcionamento de política pública." },
    { id: "p8", temaId: "previdencia", texto: "A legislação trabalhista deveria permitir mais formas de negociação direta entre empresa e trabalhador, acima da lei geral?", contexto: "Hoje a Consolidação das Leis do Trabalho (CLT) já permite alguma negociação coletiva.", argumentoFavor: "Mais flexibilidade adaptaria regras a realidades específicas de cada setor.", argumentoContra: "Reduzir o piso legal poderia enfraquecer a proteção de trabalhadores menos organizados." },
    { id: "p9", temaId: "seguranca", texto: "A posse legal de armas de fogo por civis deveria ser facilitada?", contexto: "Regras de posse e porte de armas são definidas por lei federal e decretos.", argumentoFavor: "Facilitar ampliaria o que se descreve como direito à autodefesa.", argumentoContra: "Mais armas em circulação podem estar associadas a mais mortes violentas." },
    { id: "p10", temaId: "governanca", texto: "Doações de empresas para campanhas eleitorais deveriam voltar a ser permitidas?", contexto: "Desde 2015 apenas pessoas físicas podem doar para campanhas eleitorais no Brasil.", argumentoFavor: "Ampliaria as fontes de financiamento lícito de campanhas.", argumentoContra: "Pode ampliar a influência de interesses econômicos concentrados sobre eleitos." },
  ];

  const rngBussola = criarRng(4242);
  const candidatosBussola = ordenados.map((c) => {
    const posicoes: Record<string, PosicaoBussola> = {};
    for (const p of perguntas) {
      const semPosicao = rngBussola() < (c.nomeUrna.endsWith("B") ? 0.9 : 0.15);
      posicoes[p.id] = semPosicao
        ? { valor: null, fonte: "declaracao", justificativa: "Sem posição pública documentada para esta pergunta.", evidencia: null }
        : {
            valor: escolher([-2, -1, 0, 1, 2] as const, rngBussola),
            fonte: escolher(["voto", "proposta", "declaracao"] as const, rngBussola),
            justificativa: "Posição estimada a partir de declaração pública de exemplo, apenas para teste.",
            evidencia: evidencia("Fonte da posição (exemplo)", "https://exemplo.org/fonte-posicao"),
          };
    }
    return { ...paraResumo(c), posicoes };
  });
  const bussola: BussolaArquivo = { cargo: CARGO_PRESIDENTE, uf: UF_BR, perguntas, candidatos: candidatosBussola };
  await escrever(`bussola/${chaveArquivo(CARGO_PRESIDENTE, UF_BR)}.json`, bussola);

  // --- Economia ---------------------------------------------------------------
  await escrever("economia.json", gerarEconomia());

  // --- Correções (log público) --------------------------------------------
  const correcoes: CorrecoesArquivo = {
    atualizadoEm: "2026-09-24T18:00:00-03:00",
    itens: [
      {
        data: "2026-09-24T18:00:00-03:00",
        pessoa: { nomeUrna: ordenados[0]!.nomeUrna, slug: ordenados[0]!.slug, id: ordenados[0]!.id },
        tipo: "Correção de dado factual",
        descricao: "Valor de um bem declarado estava com a categoria incorreta; corrigido conforme a declaração original do TSE (exemplo).",
      },
      {
        data: "2026-09-18T11:30:00-03:00",
        pessoa: null,
        tipo: "Correção de metodologia",
        descricao: "Ajustado o texto da régua judicial para deixar mais claro o significado de 'ação cível' (exemplo).",
      },
      {
        data: "2026-09-10T09:15:00-03:00",
        pessoa: { nomeUrna: ordenados[3]!.nomeUrna, slug: ordenados[3]!.slug, id: ordenados[3]!.id },
        tipo: "Atualização de status processual",
        descricao: "Movimentação processual mais recente incorporada após verificação manual (exemplo).",
      },
    ],
  };
  await escrever("correcoes.json", correcoes);

  // --- Meta -------------------------------------------------------------------
  const meta: Meta = {
    fixture: true,
    geradoEm: "2026-09-27T06:00:00-03:00",
    eleicao: { id: 20322002026, ano: 2026, data: "2026-10-04", segundoTurno: "2026-10-25" },
    totais: { candidaturas: candidatos.length, porCargo: { [CARGOS[CARGO_PRESIDENTE].slug]: candidatos.length } },
    fontes: [
      { id: "tse", nome: "Portal de Dados Abertos do TSE", atualizadoEm: "2026-09-27T06:00:00-03:00", url: "https://dadosabertos.tse.jus.br" },
      { id: "bcb", nome: "Banco Central — SGS", atualizadoEm: "2026-09-27T08:00:00-03:00", url: "https://www3.bcb.gov.br/sgspub" },
      { id: "ibge", nome: "IBGE — SIDRA", atualizadoEm: "2026-09-01T08:00:00-03:00", url: "https://sidra.ibge.gov.br" },
      { id: "cnj", nome: "CNJ — DataJud", atualizadoEm: "2026-09-25T04:00:00-03:00", url: "https://www.cnj.jus.br/sistemas/datajud/" },
      { id: "factcheck", nome: "Google Fact Check Tools", atualizadoEm: "2026-09-26T12:00:00-03:00", url: "https://toolbox.google.com/factcheck/apis" },
    ],
  };
  await escrever("meta.json", meta);

  console.log(`Fixtures geradas em ${SAIDA}`);
  console.log(`Candidatos: ${candidatos.length} · Buckets usados: ${porBucket.size} · NUM_BUCKETS=${NUM_BUCKETS}`);
}

await principal();
