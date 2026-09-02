# Matriz Ontológica e Regras Estruturais do Graphow

Este documento serve como referência rápida para agentes IA estruturarem nós e arestas sem violar o `SchemaGate` e o `InvariantGate`.

---

## 1. Classificação dos Nós (12 Tipos Formais)

### Camada de Navegação (Containers Estruturais)
Nós estáticos de organização espacial e temporal do projeto:
- **`Projeto`**: Raiz macro da iniciativa de engenharia ou produto.
- **`Setor`**: Domínio técnico, funcional ou subsistema (ex: `core`, `kernel`, `mcp`, `web`).
- **`Sessao`**: Unidade de trabalho delimitada no tempo e contexto; nó emissor de itens de trabalho.

### Camada de Trabalho (Grafo de Intenção e Execução)
Nós dinâmicos que representam intenções, tarefas, deliberações e entregáveis:
- **`Goal`**: Intenção ou objetivo de alto nível.
- **`Task`**: Unidade de trabalho atômica atribuível a um executor.
- **`Decision`**: Decisão de arquitetura ou técnica formalizada e aprovada.
- **`Question`**: Dúvida, incerteza ou ambiguidade que bloqueia tarefas até resolução humana.
- **`Constraint`**: Restrição mandatória inegociável (técnica, de segurança ou de escopo).
- **`Artifact`**: Entregável concreto (código fonte, arquivo de configuração, especificação).
- **`Evidence`**: Dado empírico, benchmark, telemetria ou prova matemática.
- **`Run`**: Registro de execução e telemetria de invocação de modelo de IA.
- **`Note`**: Anotação livre, aviso reativo ou contexto efêmero.

---

## 2. Matriz de Arestas Permitidas (11 Tipos Inegociáveis)

Qualquer tentativa de criar aresta fora dos pares mapeados abaixo será sumariamente **REJEITADA** pelo `SchemaGate`:

| Tipo de Aresta | Origem Permitida | Destino Permitido | Semântica Canônica |
| :--- | :--- | :--- | :--- |
| **`contem`** | `Projeto` | `Setor` | Hierarquia estrutural primária. |
| **`contem`** | `Setor` | `Sessao` | Delimitação de sessões sob um setor. |
| **`produz`** | `Sessao` | Qualquer Nó de Trabalho | Rastreabilidade de proveniência temporal. |
| **`ocorreu_em`**| `Run` | `Sessao` | Associação de execução agêntica ao contexto da sessão. |
| **`decompoe`** | `Goal` | `Task` | Quebra de objetivo em plano acionável. |
| **`decompoe`** | `Task` | `Task` | Subtarefas subordinadas a uma macro-tarefa. |
| **`depende_de`**| `Task` | `Task` | Pré-requisito de execução causal (DAG acíclico). |
| **`bloqueia`** | `Question` | `Task` | Bloqueio de conclusão enquanto dúvida estiver aberta. |
| **`justifica`** | `Evidence` | `Decision` | Fundamentação empírica de decisões arquiteturais. |
| **`contradiz`** | `Evidence` | `Decision` / `Evidence` | Registro de contraprova ou evidência conflitante. |
| **`substitui`** | `Decision` | `Decision` | Evolução ou depreciação de decisão prévia. |
| **`substitui`** | `Task` | `Task` | Substituição de escopo de tarefa anterior. |
| **`escopa`** | `Constraint` | `Goal` / `Task` | Aplicação de restrição obrigatória a objetivo ou tarefa. |
| **`deriva_de`** | `Artifact` | `Task` | Proveniência causal de arquivos/código a partir da tarefa. |
| **`deriva_de`** | `Artifact` | `Artifact` | Versionamento ou derivação de artefato anterior. |

---

## 3. Máquinas de Estados & Ciclos de Vida

### Ciclo de Vida de `Task` (`StatusTask`)
1. **`pendente`**: Tarefa criada no plano, aguardando início de execução.
2. **`em_andamento`**: Executor assumiu a tarefa e iniciou o trabalho.
3. **`pronto_para_revisao`**: Código/artefatos produzidos e vinculados via `deriva_de`; pronta para o revisor.
4. **`concluido`**: Validada e aceita. *(Proibido transicionar se houver `Question` com aresta `bloqueia` aberta)*.
5. **`bloqueado`**: Impedimento externo ou pendência bloqueante ativa.

### Ciclo de Vida de `Question` (`StatusQuestion`)
1. **`aberta`**: Dúvida ativa bloqueando tarefa(s).
2. **`respondida`**: Humano ou autoridade forneceu esclarecimento no nó.
3. **`descartada`**: Dúvida perdeu o objeto ou foi superada.

### Ciclo de Vida de `Run` (`StatusExecucao`)
- `solicitada` -> `iniciada` -> `concluida` (ou `falha`).

---

## 4. Sanitização e Proteção Contra Prototype Pollution

O `SchemaGate` inspeciona recursivamente todos os nós, propriedades e arestas recebidos no payload. O patch é **rejeitado com erro 400** se contiver chaves maliciosas:
- `__proto__`
- `constructor`
- `__class__`
- `prototype`

Mantenha nomes de propriedades limpos, em snake_case ou kebab-case convencional.
