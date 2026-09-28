-- Dados-base (idempotente)

insert into tema (id, eixo, nome, descricao, ordem) values
  ('economia',     'Economia & Tributação',        'Economia e tributação',        'Reforma tributária, regras fiscais, gastos públicos, arrecadação, câmbio.', 1),
  ('previdencia',  'Previdência & Trabalho',       'Previdência e trabalho',       'INSS, FGTS, salário mínimo, legislação trabalhista, emprego.', 2),
  ('agro-ambiente','Agropecuária & Meio Ambiente', 'Agropecuária e meio ambiente', 'Plano Safra, crédito rural, terras, licenciamento, clima, desmatamento.', 3),
  ('educacao',     'Educação & Saúde',             'Educação',                     'Financiamento, universidades, educação básica, pisos salariais, gestão.', 4),
  ('saude',        'Educação & Saúde',             'Saúde',                        'SUS, financiamento, piso da enfermagem, parcerias, atenção básica.', 5),
  ('seguranca',    'Segurança Pública',            'Segurança pública',            'Polícias, sistema prisional, armas, crime organizado.', 6),
  ('governanca',   'Governança & Integridade',     'Governança e integridade',     'Combate à corrupção, transparência, emendas, estatais, reforma do Estado.', 7),
  ('social',       'Assistência & Direitos',       'Assistência social e direitos','Programas de transferência de renda, habitação, direitos civis.', 8),
  ('infraestrutura','Infraestrutura & Energia',    'Infraestrutura e energia',     'Transportes, saneamento, energia, privatizações e concessões.', 9)
on conflict (id) do update set eixo = excluded.eixo, nome = excluded.nome, descricao = excluded.descricao, ordem = excluded.ordem;

-- Agências: signatárias do código de princípios da IFCN atuando no Brasil.
-- O status é revalidado mensalmente pelo job etl/sources/factcheck/ifcn.py contra a lista oficial.
insert into agencia_checagem (id, nome, dominio, ifcn_signataria, ifcn_verificado_em) values
  ('lupa',            'Agência Lupa',        'lupa.uol.com.br',          true, '2026-09-27'),
  ('aos-fatos',       'Aos Fatos',           'aosfatos.org',             true, '2026-09-27'),
  ('estadao-verifica','Estadão Verifica',    'estadao.com.br',           true, '2026-09-27'),
  ('uol-confere',     'UOL Confere',         'noticias.uol.com.br',      true, '2026-09-27'),
  ('afp-checamos',    'AFP Checamos',        'checamos.afp.com',         true, '2026-09-27'),
  ('fato-ou-fake',    'Fato ou Fake (g1)',   'g1.globo.com',             true, '2026-09-27'),
  ('comprova',        'Projeto Comprova',    'projetocomprova.com.br',   true, '2026-09-27')
on conflict (id) do nothing;

insert into indicador (id, nome, unidade, fonte, codigo_fonte, periodicidade, descricao, por_uf, url_fonte) values
  ('ipca_mensal',  'IPCA — variação mensal',            '% a.m.',      'IBGE via BCB SGS',  'SGS 433',   'mensal',     'Índice oficial de inflação ao consumidor, variação no mês.', false, 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json'),
  ('ipca_12m',     'IPCA — acumulado em 12 meses',      '%',           'IBGE via BCB SGS',  'SGS 13522', 'mensal',     'Inflação acumulada nos últimos 12 meses.', false, 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados?formato=json'),
  ('selic_meta',   'Selic — meta definida pelo Copom',  '% a.a.',      'BCB SGS',           'SGS 432',   'diária',     'Taxa básica de juros da economia definida pelo Comitê de Política Monetária.', false, 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json'),
  ('dbgg_pib',     'Dívida Bruta do Governo Geral',     '% do PIB',    'BCB SGS',           'SGS 13762', 'mensal',     'Dívida bruta do governo geral (metodologia a partir de 2008) em proporção do PIB.', false, 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.13762/dados?formato=json'),
  ('desocupacao',  'Taxa de desocupação',               '%',           'IBGE PNAD Contínua','SIDRA 4099','trimestral', 'Percentual de pessoas desocupadas na força de trabalho (14 anos ou mais).', true,  'https://sidra.ibge.gov.br/tabela/4099'),
  ('caged_saldo',  'Saldo de empregos formais (CAGED)', 'vagas',       'MTE Novo CAGED',    'Novo CAGED','mensal',     'Admissões menos desligamentos com carteira assinada.', true,  'https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/novo-caged'),
  ('pib_var',      'PIB — variação anual',              '%',           'IBGE Contas Nacionais','SIDRA 5932','trimestral','Taxa de variação do PIB acumulada em quatro trimestres.', false, 'https://sidra.ibge.gov.br/tabela/5932'),
  ('cambio_usd',   'Dólar comercial (venda)',           'R$',          'BCB SGS',           'SGS 1',     'diária',     'Taxa de câmbio livre — dólar americano (venda).', false, 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json'),
  ('resultado_primario','Resultado primário do setor público consolidado','% do PIB','BCB SGS','SGS 5793','mensal','Resultado primário acumulado em 12 meses (sinal positivo = superávit).', false, 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.5793/dados?formato=json')
on conflict (id) do update set nome = excluded.nome, descricao = excluded.descricao, codigo_fonte = excluded.codigo_fonte, url_fonte = excluded.url_fonte;

insert into eleicao (id, ano, nome, data, abrangencia) values
  (20322002026, 2026, 'Eleição Geral Federal 2026', '2026-10-04', 'F')
on conflict (id) do nothing;
