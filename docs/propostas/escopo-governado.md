# Proposta: Escopo Governado

Status: proposta, aberta a revisão. Versão da ontologia alvo: `1.5.0`.

O Graphow governa quem faz cada gesto (o `RoleGate` e a política de governança) e
o que pode fechar (a regra do veredito, com o teto em `max_correcoes`). Falta uma
terceira dimensão: quanto trabalho uma decisão gera. Esta proposta faz do escopo
uma dimensão governada como as outras duas, com o mínimo de recusa no kernel e o
máximo de visibilidade para quem decide.

---

## 1. O Problema

Numa orquestração longa, cada rodada abre um condutor novo, que lê a próxima
Task e decide o que fazer. Cada decisão é razoável no local, e nenhuma rodada vê
o acumulado. O resultado é a expansão de escopo: o trabalho cresce para os
lados, o plano combinado fica parado e parte do que foi feito acaba revertido.

A causa não é falta de autorização. É que **uma decisão gera trabalho sem que o
custo dela fique visível enquanto ele cresce**, e isso vale para decisão do
humano, do árbitro ou do planejador. Hoje, no grafo:

- criar Task não custa nada ao planejador, nem pelo `criar_tarefa` nem pelo `propor_patch`;
- nada distingue a Task combinada da Task que surgiu no caminho;
- o fora de escopo do Goal, quando existe, é prosa numa propriedade, e a vista de Task mostra do Goal só o rótulo;
- uma descoberta tem duas saídas, virar Task (executar) ou Question (travar), e nenhuma barata;
- a fila não prefere o que foi combinado ao que surgiu depois.

## 2. Evidência

Medida no log de eventos de dois bancos reais, só leitura. "Plano" são as Tasks
que existiam quando a decomposição foi combinada; "emergente" é o resto.

| Goal | Tasks (plano → total) | Observação |
|---|---|---|
| Goal de código com plano e fora de escopo escritos pelo humano | 14 → 121 | 355 h; duas das cinco fases do plano nunca começaram |
| Goal conduzido de perto pelo humano | 12 → 14 | — |
| Goal de código com plano humano de 18 Tasks | 18 → 18 | — |
| Goal de pesquisa decomposto pelo condutor em ondas | 5 → 35 | cada onda nova, sem aprovação |
| Goal em modo contínuo, por ordem do humano | 3 → 100 | — |

No primeiro Goal, as 107 Tasks emergentes se dividem em:

| Qtd | O que são |
|---|---|
| 40 | subdivisão legítima das fases do plano |
| 27 | expansão lateral para serviços de outros módulos, depois quase toda revertida |
| 14 | Tasks só de prova ao vivo e de registro da prova |
| 12 | correções e acompanhamentos |
| 9 | prosa: comentários, README, descrições |
| 5 | rebase e renumeração |

Só cerca de 8% vieram de reprovação do revisor. A expansão lateral **passou pelo
humano**: o condutor abriu uma Question perguntando a regra de domínio, o humano
respondeu, e uma decisão anterior do próprio humano levou a regra a quatro
leitores fora do Goal. A pergunta não mostrava o custo de escopo da resposta. A
reversão veio uma semana depois.

Um portão que pedisse autorização para expandir teria sido aprovado. O que
faltou foi mostrar o custo enquanto ele crescia.

## 3. Princípios

1. **O kernel garante a estrutura, não a verdade.** Ele confere que toda Task
   nova diz de onde veio e que a ligação aponta para o tipo certo. Se a ligação é
   verdadeira, isso é julgamento, e julgamento é da revisão.
2. **Medir, não prever.** O custo de uma decisão sai do grafo à medida que as
   Tasks nascem. Ninguém estima nada em prosa.
3. **Devolver a palavra, não recusar.** O padrão é a cadência voltar ao humano
   com um placar. A recusa por contagem existe só como opção da política.
4. **A referência é humana.** Desvio se mede contra o que o humano aprovou. O
   árbitro destrava a execução, mas não redefine a referência.
5. **Neutro de domínio.** Nada aqui supõe código. Arquivos, fontes e gestos no
   mundo passam pelas mesmas ligações.

## 4. Desenho

### 4.1 D1: Fronteira como dado

Os critérios de aceite e o fora de escopo do Goal deixam de ser prosa e viram
`Constraint` ligada ao Goal por `escopa`:

| Constraint | Propriedade | Conteúdo |
|---|---|---|
| Um nó por critério | `tipo: criterio_aceite` | O critério, endereçável pelo id do nó |
| Um nó por Goal | `tipo: fronteira` | O que está fora do escopo, item a item |

As restrições já sobem a hierarquia até toda vista e são a última seção cortada
pelo orçamento (`context/renderizacao.py`). A skill `graphow-gerente` passa a
gravar critérios e fronteira assim, e o Goal deixa de levar as propriedades em
prosa, para não haver duas fontes que divergem.

Uma descoberta que não atende a nenhum critério ganha uma terceira saída: uma
`Note` com `acao: proposta_fora_do_goal`, pendurada no Projeto, que aparece numa
caixa de propostas na web e na vista do humano e não entra na fila do condutor.

### 4.2 D2: Ligação obrigatória

Toda Task criada depois do plano aprovado (4.3) declara de onde veio, por uma
destas ligações:

| Classe | Ligação | Alvo que o kernel confere |
|---|---|---|
| Subdivisão (B1) | `decompoe` vindo de uma Task do plano vigente | Task do plano, ou descendente de uma |
| Correção | propriedade `corrige` (já existe) | `Evidence` de veredito `rejeitado` |
| Acompanhamento | aresta nova `acompanha` | `Evidence` de veredito `rejeitado` com `Decision` de `aceite_apos_reprovacao` |
| Integração | aresta nova `integra` | Task do mesmo Goal com `Artifact` |
| Reversão | aresta nova `desfaz` | `Decision` já substituída (`substitui`) ou revogada |
| Emergente (B3) | aresta nova `motivada_por`, mais a propriedade `atende_criterio` | `Decision`, `Evidence`, `Task` ou `Question`; `atende_criterio` aponta uma `Constraint` `criterio_aceite` do Goal |

A `Decision` criada pelo planejador depois do plano aprovado também leva
`motivada_por`. Assim a origem de uma decisão fica estrutural, e a cadeia "a
Decision A gerou a Task, que gerou a Evidence, que gerou a Decision B" tem raiz
calculável.

A conferência mora no `InvariantGate`, que lê o estado depois do lote, como a
regra de que nenhum nó nasce solto. Por isso ela cobre o `criar_tarefa` e o
`propor_patch`. Recusa: `ligacao_de_escopo_ausente`, com a lista de ligações
aceitas.

Vale para todo autor, o humano inclusive: invariante estrutural não distingue
autor. Uma Task criada pelo humano conta no placar, mas não para o limiar M
(4.5), porque criá-la já é um gesto consciente de escopo.

O kernel garante só que a ligação existe e aponta para o tipo certo. Uma
expansão pendurada como subdivisão de uma Task do plano passa no portão: quem a
pega é a revisão por decisão (4.5).

O padrão do `criar_tarefa` deixa de ser o Goal como pai. Ele exige uma das
ligações acima.

### 4.3 D3: Plano aprovado, com versões

Um gesto novo na política, `aprovar_plano` (`humano` ou `arbitro`), grava no Goal
uma versão do plano:

```json
"planos": [
  {"versao": 1, "seq": 27310, "aprovado_por": "david", "papel": "humano"},
  {"versao": 2, "seq": 31002, "aprovado_por": "arbitro#4f61da", "papel": "arbitro"}
]
```

O plano de uma versão são as Tasks sob o Goal no `seq` dela. Replanejar, e a
onda de decomposição de um condutor é um replanejamento, exige uma versão nova.

- **Execução**: o executor não assume Task de Goal sem plano aprovado vigente
  (`plano_nao_aprovado`). Qualquer versão destrava, inclusive a do árbitro,
  quando a política lhe entrega o gesto.
- **Referência do desvio**: a última versão aprovada por humano. As Tasks de
  versões do árbitro contam como emergentes em relação a ela.
- **Sem aprovação humana nenhuma**: toda Task conta como emergente desde a primeira.

### 4.4 D4: Fila com o plano primeiro

`proximas_tarefas` serve, nesta ordem:

1. Tasks do plano vigente e suas subdivisões;
2. emergentes aprovadas pelo humano e emergentes das quais uma Task do plano depende (`depende_de`);
3. o resto.

Ela só reordena e não bloqueia nada. Ataca a inanição em que o plano combinado
fica parado enquanto o emergente anda.

### 4.5 D5: Custo por decisão e cadência por desvio

Uma projeção nova calcula, para cada raiz de cadeia de `motivada_por`:

- quantas Tasks ela gerou, por classe (B1, B3, correção, acompanhamento, integração, reversão);
- os alvos tocados (`arquivos_alvo`, ou a fonte, no trabalho não-dev);
- o custo dos `Run`s dessas Tasks;
- as reversões (`desfaz`), somadas à decisão original;
- a profundidade da cadeia.

Dois gatilhos de desvio, lidos da política:

| Leitura | Default inicial | Dispara quando |
|---|---|---|
| `limiar_desvio_por_raiz` (K) | 3 | uma raiz passa de K Tasks B3 desde a referência |
| `limiar_desvio_por_goal` (M) | 5, a calibrar | o Goal passa de M Tasks B3 desde a última vez que o contador zerou, ou Tasks do plano seguem sem começar enquanto as B3 crescem |

K diz **qual decisão** revisar. M não se engana com decisões fragmentadas: a
mesma expansão espalhada por várias decisões pequenas nunca passa de K, mas
passa de M.

As classes de integração, acompanhamento e reversão não disparam gatilho, mas
aparecem no placar por raiz, para que um volume anormal fique visível.

**Quem responde.** Um gesto novo, `responder_desvio`, com default `humano` em
todos os presets, `arbitragem_maxima` inclusive. Só a `personalizada` o entrega
ao árbitro, e o placar marca quando foi o árbitro que dispensou um alerta.

**O que zera o contador.** Só o `responder_desvio` e o `aprovar_plano` feitos
por humano, os dois gestos que mostram o placar. Responder uma Question, criar
uma Constraint ou qualquer outro gesto humano não zera.

**O que o kernel projeta.** "Decisões sem veredito de escopo": as raízes que
passaram de K e ainda não foram julgadas. A pendência mora no kernel, para
qualquer cliente MCP vê-la, e não só a skill de orquestração.

**A revisão.** Uma revisão com Opus julga a decisão junto das Tasks que ela
gerou, contra as `Constraint`s de critério e de fronteira do Goal. Ela registra
o veredito como `Evidence` e não bloqueia. Julgar "esta decisão e as nove Tasks
dela cabem no Goal?" é mais fácil que julgar nove Tasks soltas.

**A cadência.** Um valor novo de `cadencia`, `desvio`: a orquestração devolve a
palavra quando um gatilho dispara, com o placar.

### 4.6 D6: Recusa por contagem, só como opção

A leitura `teto_expansao` existe na política, desligada por padrão. Ligada, o
`InvariantGate` recusa a Task B3 acima do teto (`orcamento_de_escopo_esgotado`)
até um `responder_desvio`. Ela não é o mecanismo principal porque contar Tasks
pune a subdivisão legítima e empurra o condutor a fazer Tasks grandes.

### 4.7 Placar

Na vista do Goal, na vista do condutor e na web:

```
Escopo: plano_v4 (humano, seq 27310) · v5-v7 pelo árbitro
Plano: 14 Tasks · 9 concluídas · 3 sem começar (fase F3, F4)
Desde a referência: B1 40 · B3 12 · correção 12 · integração 5 · reversão 8
Raiz que mais gerou: dec-hub-contrato-segue-o-codigo · 9 Tasks B3 · 4 alvos fora da fronteira · veredito de escopo pendente
Cadeia mais longa: 4
```

A propriedade `fase` na Task do plano é opcional e serve só para agrupar na
apresentação.

## 5. Mudanças na Ontologia

| Item | Mudança |
|---|---|
| Arestas novas | `motivada_por` (Task, Decision → Decision, Evidence, Task, Question); `acompanha` (Task → Evidence); `integra` (Task → Task); `desfaz` (Task → Decision) |
| Quem cria as arestas novas | `humano`, `planejador`; remover: `humano` |
| Propriedades novas | `Goal.planos`; `Task.atende_criterio`; `Task.fase`; `Constraint.tipo` com `criterio_aceite` e `fronteira`; `Note.acao: proposta_fora_do_goal` |
| Gestos novos | `aprovar_plano`, `responder_desvio` (`humano` ou `arbitro`) |
| Leituras próprias novas | `limiar_desvio_por_raiz`, `limiar_desvio_por_goal`, `teto_expansao` |
| Falhas novas | `ligacao_de_escopo_ausente`, `plano_nao_aprovado`, `orcamento_de_escopo_esgotado` |
| Cadência | valor novo `desvio` |
| Prompts | condutor: descoberta fora dos critérios vira proposta; Question que destrava trabalho diz se a resposta pode cruzar a fronteira (sim, não ou talvez); prova ao vivo e registro dela entram no critério da Task que entrega, sem Task própria |

## 6. Migração

1. **Por versão.** Os portões de D2 e de D3 valem só para eventos com
   `versao_ontologia` maior ou igual a `1.5.0`. O replay de eventos antigos não
   passa por eles.
2. **Sem aprovação implícita.** Os Goals em andamento entram sem plano aprovado
   e travam o executor até um `aprovar_plano` humano sobre o estado atual, que
   vira a `plano_v1`. A vista e a web dizem por que o Goal travou e qual gesto o
   destrava. Aprovar na migração seria o mesmo furo de deixar o árbitro definir
   a referência.
3. **Ordem de deploy**:
   1. schema e projeções que leem as arestas, os gestos e as propriedades novas, tolerando que estejam ausentes;
   2. o código que os escreve;
   3. a ativação dos portões.

   Cada passo é testado com replay de um banco antigo, num banco descartável,
   nunca no real: tipo novo gravado no banco real quebra o replay das sessões
   que ainda rodam o código antigo.

## 7. Validação

O desenho foi testado contra o histórico antes de ser escrito. Como a aresta
`motivada_por` ainda não existe, o teste usou o `orienta` (Decision → Task) para
aproximá-la. Correções, acompanhamentos, rebases e PRs foram separados pelo
nome, e os disparos de um mesmo lote contam como um evento. Gatilho: K = 3 por
raiz.

| Goal | Eventos de desvio |
|---|---|
| Plano humano, 14 → 121 (o caso) | 2. O primeiro no lote que criou as Tasks da expansão lateral, antes de qualquer execução e uma semana antes da reversão. O segundo, marginal, em polimento fora das fases do plano |
| Conduzido de perto pelo humano, 12 → 14 | 0 |
| Plano humano de 18 Tasks | 0 |
| Decomposto pelo condutor, 5 → 35 | 6, um por onda de decomposição |
| Modo contínuo, 3 → 100 | 23, um a cada 1 a 2 h |

O que o teste mostrou além dos números:

- A primeira Task da expansão lateral se chamava "Correção", mas não tinha
  `corrige`, e a classificação pelo nome a deixou passar como logística. Por
  isso, em D2, cada classe aponta para um alvo cujo tipo o kernel confere.
- Num Goal de 55 Tasks de construção, o trabalho se espalhou por 20 decisões
  sem ninguém tentar fugir de limiar, e a raiz pelas arestas atuais não as
  juntou. Por isso existem o `motivada_por` na Decision e o gatilho M por Goal.
- A regra "a subdivisão só toca os alvos do pai" não separa nada quando o plano
  é feito de épicos: 53 de 65 subdivisões legítimas a violam. Ela ficou de fora.

Este teste vira um teste de regressão em `avaliacao/`, sobre logs reais
anonimizados. **Limite**: todas as amostras são de um usuário só. Por isso K e M
são defaults da política, com origem visível no placar, a recalibrar com o uso
de outros, e nunca constantes do kernel.

## 8. Fora Desta Proposta

| Ideia | Por que ficou de fora |
|---|---|
| Teto de Tasks como mecanismo principal | Pune a subdivisão legítima e empurra para Tasks grandes. Ficou como opção (D6) |
| Fronteira por seletores de arquivo | Tem forma de código e não passa no princípio 5. A Constraint de fronteira e a revisão cobrem o caso |
| Estimativa de custo dentro da Question | Quem pergunta não sabe o custo da resposta, e a estimativa seria um chute. Ficou só o sim, não ou talvez |
| Detector de deriva no motor reativo | O placar por raiz já mostra o retrabalho pelas reversões |
| Decaimento de Aprendizado | Outro problema, outra proposta |

## 9. Ordem de Implementação Sugerida

1. D1 e a terceira saída da descoberta, sem portão nenhum: só dado, vista e prompt.
2. D4 (fila), que só reordena.
3. A projeção de D5 e o placar, sobre as ligações que existirem, ainda sem cadência.
4. D2 e D3 no kernel, com a migração (seção 6).
5. Os gatilhos, `responder_desvio` e `cadencia: desvio`.
6. O teste de regressão em `avaliacao/`.

Cada passo é útil sozinho, e os três primeiros não mudam nenhum portão.
