# Manual editorial — Raio-X 2026

Documento obrigatório para toda pessoa com acesso ao painel editorial.
Este manual é **público** (transparência) e prevalece sobre qualquer instrução informal.

## 1. O que publicamos e o que não publicamos

| Publicamos | Não publicamos |
|---|---|
| Dados oficiais do TSE, da Câmara, do Senado, da CGU, do BCB, do IBGE e do MTE | Opinião, adjetivo ou juízo de valor sobre candidatos |
| Processos com número CNJ e status formal (régua da seção 3) | Inquéritos, investigações, delações não homologadas, "notícias de bastidores" |
| Checagens de agências signatárias da IFCN, com o rótulo original | Checagens de agências não signatárias, ou rótulos "traduzidos" por nós |
| Resumos de planos de governo com trecho literal e página | Resumo sem trecho literal verificável |
| Posições para a Bússola com evidência (voto, trecho do plano, declaração gravada) | Posição inferida, "provável" ou baseada em reputação |

**Regra de ouro:** se não existe documento público que prove o fato, ele não existe para a plataforma.

## 2. Fluxo de publicação (4 olhos)

1. O item entra como **rascunho**, criado pelo ETL, pela IA ou por um editor.
2. Um editor completa e confere as evidências e move o item para **em revisão**.
3. **Revisor 1** confere o item contra a fonte original (abrir o documento, e não só o resumo) e assina.
4. **Revisor 2**, necessariamente outra pessoa, confere de forma independente e assina. O item é publicado no próximo deploy.
5. Quem criou o item **não pode** ser revisor dele. O banco de dados impede isso tecnicamente.

Para cada item, o revisor verifica:
- [ ] A evidência abre e corresponde exatamente ao que está escrito.
- [ ] O texto é descritivo e neutro (sem adjetivos, sem "polêmico", "grave", "escândalo" etc.).
- [ ] Datas, números e nomes conferem com a fonte.
- [ ] O mesmo tipo de informação foi tratado da mesma forma para todos os candidatos (isonomia).
- [ ] Processos: o número CNJ e o status seguem a régua; a presunção de inocência aparece quando cabe.

## 3. Régua judicial

| Situação no processo | Status no sistema | Texto exibido |
|---|---|---|
| Denúncia ou queixa **recebida** | `reu_acao_penal` | Réu em ação penal — sem condenação |
| Sentença condenatória de 1º grau | `condenado_1a_instancia` | Condenado em 1ª instância — cabe recurso |
| Condenação por órgão colegiado | `condenado_orgao_colegiado` | Condenado por órgão colegiado — cabe recurso |
| Trânsito em julgado | `condenado_transito_julgado` | Condenação definitiva |
| Absolvição | `absolvido` | Absolvido |
| Anulação | `anulado` | Processo anulado |
| Prescrição/extinção | `punibilidade_extinta` | Punibilidade extinta |
| Improbidade/ACP em curso | `acao_civel_em_curso` | Ação cível em andamento |
| Improbidade/ACP julgada procedente | `acao_civel_procedente` | Ação cível julgada procedente |
| Improbidade/ACP julgada improcedente | `acao_civel_improcedente` | Ação cível julgada improcedente |

- O DataJud **sugere** o status; o revisor **confirma** lendo a movimentação ou a decisão.
- Processo em segredo de justiça: não publicar.
- Todo processo não transitado em julgado exibe: *"Presunção de inocência — decisão ainda pode ser revista (CF, art. 5º, LVII)."*

## 4. Conteúdo gerado por IA

- A IA só **resume e localiza trechos**. Nunca avalia, compara ou prevê.
- Todo resumo tem trecho literal validado automaticamente e é revisado por 2 pessoas.
- O selo "Resumo gerado por IA e revisado pela equipe editorial" é obrigatório e automático.
- Na dúvida entre o resumo e o original, vale o original: edite o resumo ou rejeite o item.

## 5. Correções (SLA)

| Prazo | Ação |
|---|---|
| Até 2 h | Triagem: classificar como "em análise" |
| Até 24 h (48 h fora do período eleitoral) | Decisão: procedente ou improcedente, com resolução escrita |
| Procedente | Corrigir, publicar e registrar no changelog público do perfil |
| Risco grave (dado errado com potencial de dano) | **Despublicar imediatamente** (1 clique no painel) e só depois apurar |

Pedidos do próprio candidato ou da assessoria dele têm o mesmo rito. A resposta documentada do candidato pode ser exibida junto ao item contestado.

## 6. Vedações do período eleitoral

- Não impulsionar (patrocinar) conteúdo que mencione candidatos (Lei 9.504/97, art. 57-C).
- Não divulgar resultados agregados da Bússola (vedação a enquetes, art. 33, §5º).
- Não publicar conteúdo sintético (deepfake, voz ou imagem gerada) de nenhuma pessoa.
- Na véspera e no dia da eleição, só correções de erro. Nenhuma inclusão nova de conteúdo sensível sem aprovação do responsável jurídico.

## 7. Conflito de interesses

A pessoa revisora deve se declarar impedida (e não revisar) quando tiver vínculo com candidato, partido ou campanha: filiação ativa, trabalho remunerado ou parentesco.
