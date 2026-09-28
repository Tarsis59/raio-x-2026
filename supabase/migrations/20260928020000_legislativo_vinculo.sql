-- =============================================================================
-- Legislativo — colunas de apoio ao vínculo parlamentar ↔ pessoa
--
-- Por quê: os jobs `camara` e `senado` coletam, na fonte, os dados que permitem
-- identificar a pessoa por trás do mandato (CPF na Câmara; nome civil completo +
-- data de nascimento no Senado, que não expõe CPF). Sem guardar isso em
-- `parlamentar`, o job `vinculo_parlamentar` (separado, re-executável) precisaria
-- rebaixar de novo essas informações nas APIs de origem a cada execução — caro e
-- redundante. Guardamos o HMAC do CPF (nunca o CPF em claro) e o nome/nascimento
-- civis, e o vínculo em si (pessoa_id, confiança, revisão) continua em
-- `parlamentar`, como já definido no esquema inicial.
-- =============================================================================

alter table parlamentar
  add column cpf_hmac text,             -- só Câmara; HMAC-SHA256, mesmo segredo/algoritmo de pessoa.cpf_hmac
  add column nome_civil text,           -- nome completo civil (Câmara: nomeCivil; Senado: NomeCompletoParlamentar)
  add column data_nascimento date;      -- usado para o vínculo por nome+nascimento (Senado, principalmente)

create index parlamentar_cpf_hmac_idx on parlamentar (cpf_hmac) where cpf_hmac is not null;
