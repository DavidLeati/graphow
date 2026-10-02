# Matriz ontológica do Graphow

Referência de estrutura: que nó existe, que aresta liga o quê, quem pode criá-la e por onde os status andam. Um par de tipos fora da tabela é recusado pelo SchemaGate com `par_de_aresta_invalido`; o papel errado é recusado pelo RoleGate com `violacao_permissao_papel`, junto da lista de quem poderia. As duas checagens são independentes: o patch precisa passar nas duas.

## Os 14 tipos de nó

Camada de navegação, os contêineres:

- `Projeto`: raiz da iniciativa, e onde moram a política de governança do projeto (propriedade `governanca`, que herda a global) e o nível de autonomia legado.
- `Governanca`: o singleton `governanca-global`, com o `preset` e a `personalizada` da política global. Raiz como o `Projeto`: nenhuma aresta o toca, e só o humano o cria, edita ou remove, em qualquer política.
- `Setor`: domínio técnico ou subsistema (`core`, `kernel`, `mcp`, `web`).
- `Sessao`: unidade de trabalho no tempo; é dela que saem os itens de trabalho, pela aresta `produz`. Tem status `ativa` ou `concluida`; encerrada, a vista dela abre pelo fechamento.

Camada de trabalho:

- `Goal`: intenção de alto nível.
- `Task`: unidade atribuível a um executor.
- `Decision`: decisão técnica ou de arquitetura registrada.
- `Question`: dúvida que bloqueia tarefa até a resposta do humano ou, conforme a política, do árbitro.
- `Constraint`: restrição obrigatória de técnica, segurança ou escopo.
- `Artifact`: entregável concreto, de código a especificação.
- `Evidence`: dado empírico, benchmark, telemetria, prova ou trecho de código lido. Pode apontar por `deriva_de` o `Artifact` ou a `Task` que avalia. Quando cita `linhas` ou `trecho`, e sempre que é do planejador, carrega o ponteiro inteiro: `arquivo`, `linhas` e `trecho`.
- `Run`: registro de execução e telemetria de invocação de modelo.
- `Note`: anotação livre ou aviso reativo; com `acao: condensacao_de_sessao`, a condensação em prosa de uma sessão encerrada.
- `Aprendizado`: memória de longo prazo, o que sobrevive ao projeto. O rótulo é a afirmação; `como_aplicar` diz o que fazer com ela. Nasce com `deriva_de` obrigatório e só alcança outros projetos quando o humano o promove.

## As 13 arestas: pares válidos e donos

| Aresta | Origem para destino | Cria | Remove |
| :--- | :--- | :--- | :--- |
| `contem` | `Projeto`→`Setor`, `Setor`→`Sessao` | humano, sistema | humano |
| `produz` | `Sessao`→ qualquer nó da camada de trabalho | humano, sistema, os quatro papéis de agente | humano |
| `ocorreu_em` | `Run`→`Sessao` | humano, sistema | humano, sistema |
| `decompoe` | `Goal`→`Task`, `Task`→`Task` | humano, planejador | humano, planejador |
| `depende_de` | `Task`→`Task` | humano, planejador | humano, planejador |
| `substitui` | `Decision`→`Decision`, `Task`→`Task`, `Aprendizado`→`Aprendizado` | humano, planejador; `Aprendizado`→`Aprendizado`: também executor e revisor (consolidação) | humano, planejador |
| `bloqueia` | `Question`→`Task` | humano e qualquer agente | humano; árbitro, se a política lhe entrega `responder_questao` (e não a da Question que ele abriu) |
| `justifica` | `Evidence`→`Decision` | humano, planejador, executor, revisor, árbitro | humano, planejador, executor, revisor, árbitro |
| `contradiz` | `Evidence`→`Decision`, `Evidence`→`Evidence`, `Evidence`→`Aprendizado` | humano, executor, revisor | humano, executor, revisor |
| `deriva_de` | `Artifact`→`Task`, `Artifact`→`Artifact`, `Evidence`→`Artifact`, `Evidence`→`Task`, `Note`→`Task`, `Note`→`Decision`, `Note`→`Evidence`, `Note`→`Artifact`, `Aprendizado`→`Evidence`, `Aprendizado`→`Decision`, `Aprendizado`→`Note`, `Aprendizado`→`Artifact`, `Aprendizado`→`Task` | humano, executor, revisor | humano, executor, revisor |
| `escopa` | `Constraint`→`Goal`, `Constraint`→`Task` | humano; árbitro, se a política lhe entrega `constraint` | humano; árbitro, idem |
| `vale_para` | `Aprendizado`→`Projeto`, `Aprendizado`→`Setor` | humano; árbitro, se a política lhe entrega `promover_aprendizado` (e não o Aprendizado que ele registrou) | humano; árbitro, idem |
| `orienta` | `Decision`→`Task`, `Decision`→`Goal` | humano, planejador | humano, planejador |

Num projeto cuja política tem `estrutura: ilimitado` (o que o `nivel_autonomia: ilimitado` legado vira, e o que a `arbitragem_maxima` fixa), a criação se amplia para todas as arestas menos `escopa` e `vale_para`, e para todos os tipos de nó menos `Constraint`, `Governanca` e `Projeto`. A remoção nunca se amplia: retirar um `bloqueia` exige o humano, ou o árbitro com `responder_questao`, em qualquer projeto. As colunas acima dizem o dono da tabela; o gesto da política só acrescenta quem pode, nunca tira.

## Quem cria cada tipo de nó

Num projeto de autonomia estrita:

- `planejador`: `Task`, `Decision`, `Question`, `Note`, `Evidence`. A `Evidence` do planejador é o que ele leu no código e nasce com `arquivo`, `linhas` e `trecho` (`evidencia_sem_localizacao` na falta de um deles).
- `executor`: `Artifact`, `Evidence`, `Decision`, `Question`, `Note`, `Aprendizado`.
- `revisor`: `Evidence`, `Question`, `Note`, `Aprendizado`. Registra `Aprendizado` quem detém `deriva_de`, a aresta de origem que ele exige.
- `sistema`, a identidade do harness: `Run`, `Sessao` e, quando o hook roda sem `--setor`, o ambiente padrão da memória (o `Projeto` com o nome do repositório e o `Setor` `Memoria`). Nada do grafo de trabalho.
- `arbitro`: `Evidence`, `Decision` e `Note`. O resto vem da política do projeto do alvo: `Constraint` com o gesto `constraint`, e os demais tipos sob `estrutura: ilimitado`. Não cria `Governanca` nem `Projeto`.
- `humano`: todos os 14.

`Governanca` é o único tipo que nenhum agente cria, altera ou remove, em projeto e política nenhuma: ele guarda a política que decide os gestos, e quem a escrevesse se daria todos eles. `Constraint` só se abre ao árbitro, com o gesto `constraint`. Remover uma `Constraint`, uma `Question` ou um `Aprendizado` exige o humano, ou o árbitro com o gesto `excluir`: apagar a dúvida seria a forma mais direta de encerrá-la sem resposta, e por isso o árbitro não remove a `Question` que ele abriu. Memória se substitui ou se contradiz, não se apaga.

Um `Aprendizado` nasce só com `deriva_de` no mesmo lote (`aprendizado_sem_origem` na falta dele), e a propriedade `alcance` é reservada ao humano: um agente que a escrevesse promoveria o próprio aprendizado. O árbitro promove ao Setor ou ao Projeto pela aresta `vale_para`, nunca ao global.

## Status e ciclos de vida

`Task`: `pendente`, `em_andamento`, `pronto_para_revisao`, `concluido`, e `bloqueado` fora da linha principal. Três regras do kernel andam com esses valores:

1. Quem move o status precisa deter a posse da tarefa (`assumir_tarefa`), exceto o humano.
2. Só executor e humano gravam `concluido`. Planejador e revisor são recusados, inclusive por `propor_patch`, e fechar Task não é gesto do árbitro. Além do papel, vale a regra do kernel, em todo preset: o agente só conclui com veredito vigente `aprovado` (uma `Evidence` com `veredito` de revisor, humano ou árbitro) ou com aceite legítimo pelo teto de correções. Sem isso, `fechamento_sem_veredito_aprovado`.
3. Nenhum papel conclui uma `Task` que tenha `Question` aberta apontando para ela por `bloqueia`.

`Question`: `aberta`, `respondida`, `descartada`. Os dois status de encerramento são do humano, ou do árbitro quando a política lhe entrega `responder_questao`, que escreve só esses dois e não encerra a que abriu; devolver uma pergunta para `aberta` segue livre, porque reabrir não anula garantia nenhuma.

`Run`: `solicitada`, `iniciada`, `concluida` ou `falha`.

`Sessao`: `ativa` ou `concluida`. Encerrar é do humano (`encerrar_sessao`, interface), do árbitro quando a política lhe entrega `encerrar_sessao`, ou do harness (hook de fim, sempre); ao encerrar, o grafo abre a Task de condensação.

`Goal`: escrever `concluido` é o gesto `fechar_goal`, do humano ou do árbitro conforme a política.

`Aprendizado` não tem status gravado: vigente ou substituído é derivado da aresta `substitui`, e contradito da aresta `contradiz`, como já se faz com `Decision`. `valido_ate`, quando presente, tira o aprendizado vencido da vista.

## Sanitização de payload

O SchemaGate percorre path, chaves e valores em toda profundidade antes de olhar a ontologia. Qualquer uma destas chaves derruba o patch com o modo `prototype_pollution`:

`__proto__`, `constructor`, `prototype`, `__class__`, `__globals__`, `__dict__`

Nomes de propriedade em snake_case não esbarram nisso.
