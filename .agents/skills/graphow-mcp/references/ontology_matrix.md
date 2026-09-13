# Matriz ontológica do Graphow

Referência de estrutura: que nó existe, que aresta liga o quê, quem pode criá-la e por onde os status andam. Um par de tipos fora da tabela é recusado pelo SchemaGate com `par_de_aresta_invalido`; o papel errado é recusado pelo RoleGate com `violacao_permissao_papel`, junto da lista de quem poderia. As duas checagens são independentes: o patch precisa passar nas duas.

## Os 12 tipos de nó

Camada de navegação, os contêineres:

- `Projeto`: raiz da iniciativa, e onde mora o nível de autonomia.
- `Setor`: domínio técnico ou subsistema (`core`, `kernel`, `mcp`, `web`).
- `Sessao`: unidade de trabalho no tempo; é dela que saem os itens de trabalho, pela aresta `produz`.

Camada de trabalho:

- `Goal`: intenção de alto nível.
- `Task`: unidade atribuível a um executor.
- `Decision`: decisão técnica ou de arquitetura registrada.
- `Question`: dúvida que bloqueia tarefa até a resposta humana.
- `Constraint`: restrição obrigatória de técnica, segurança ou escopo.
- `Artifact`: entregável concreto, de código a especificação.
- `Evidence`: dado empírico, benchmark, telemetria ou prova.
- `Run`: registro de execução e telemetria de invocação de modelo.
- `Note`: anotação livre ou aviso reativo.

## As 11 arestas: pares válidos e donos

| Aresta | Origem para destino | Cria | Remove |
| :--- | :--- | :--- | :--- |
| `contem` | `Projeto`→`Setor`, `Setor`→`Sessao` | humano, sistema | humano |
| `produz` | `Sessao`→ qualquer nó da camada de trabalho | humano, sistema, os três papéis de agente | humano |
| `ocorreu_em` | `Run`→`Sessao` | humano, sistema | humano, sistema |
| `decompoe` | `Goal`→`Task`, `Task`→`Task` | humano, planejador | humano, planejador |
| `depende_de` | `Task`→`Task` | humano, planejador | humano, planejador |
| `substitui` | `Decision`→`Decision`, `Task`→`Task` | humano, planejador | humano, planejador |
| `bloqueia` | `Question`→`Task` | humano e qualquer agente | só humano |
| `justifica` | `Evidence`→`Decision` | humano, executor, revisor | humano, executor, revisor |
| `contradiz` | `Evidence`→`Decision`, `Evidence`→`Evidence` | humano, executor, revisor | humano, executor, revisor |
| `deriva_de` | `Artifact`→`Task`, `Artifact`→`Artifact`, `Note`→`Task`, `Note`→`Decision` | humano, executor, revisor | humano, executor, revisor |
| `escopa` | `Constraint`→`Goal`, `Constraint`→`Task` | só humano | só humano |

Num Projeto marcado com `nivel_autonomia: ilimitado`, a criação se amplia para todas as arestas menos `escopa`, e para todos os tipos de nó menos `Constraint`. A remoção nunca se amplia: retirar um `bloqueia` exige sessão humana em qualquer projeto.

## Quem cria cada tipo de nó

Num projeto de autonomia estrita:

- `planejador`: `Task`, `Decision`, `Question`, `Note`.
- `executor`: `Artifact`, `Evidence`, `Decision`, `Question`, `Note`.
- `revisor`: `Evidence`, `Question`, `Note`.
- `sistema`, a identidade do harness: `Run` e `Sessao`, nada do grafo de trabalho.
- `humano`: todos os 12.

`Constraint` é o único tipo que nenhum agente cria ou altera, em projeto nenhum. Remover uma `Constraint` ou uma `Question` também exige sessão humana: apagar a dúvida seria a forma mais direta de encerrá-la sem resposta.

## Status e ciclos de vida

`Task`: `pendente`, `em_andamento`, `pronto_para_revisao`, `concluido`, e `bloqueado` fora da linha principal. Três regras do kernel andam com esses valores:

1. Quem move o status precisa deter a posse da tarefa (`assumir_tarefa`), exceto o humano.
2. Só executor e humano gravam `concluido`. Planejador e revisor são recusados, inclusive por `propor_patch`.
3. Nenhum papel conclui uma `Task` que tenha `Question` aberta apontando para ela por `bloqueia`.

`Question`: `aberta`, `respondida`, `descartada`. Os dois status de encerramento são reservados ao humano; devolver uma pergunta para `aberta` segue livre, porque reabrir não anula garantia nenhuma.

`Run`: `solicitada`, `iniciada`, `concluida` ou `falha`.

## Sanitização de payload

O SchemaGate percorre path, chaves e valores em toda profundidade antes de olhar a ontologia. Qualquer uma destas chaves derruba o patch com o modo `prototype_pollution`:

`__proto__`, `constructor`, `prototype`, `__class__`, `__globals__`, `__dict__`

Nomes de propriedade em snake_case não esbarram nisso.
