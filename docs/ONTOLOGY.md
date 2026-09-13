# Especificação Formal da Ontologia — Graphow

Especificação semântica do grafo agêntico bilateral para alinhamento entre humanos e agentes de inteligência artificial.

---

## 1. Princípios da Ontologia

1. **Separação em Duas Camadas**:
   - **Camada de Navegação**: Espinha dorsal visual e de agrupamento hierárquico (`Projeto` → `Setor` → `Sessao`). Apenas humanos criam e estruturam a navegação.
   - **Camada de Trabalho**: Nós semânticos de intenção, execução e evidência pendurados exclusivamente em instâncias de `Sessao`. Tanto humanos quanto agentes interagem com a camada de trabalho.

2. **Temporalidade Bitemporal**:
   - `criado_em` (ISO 8601 UTC): Momento em que o fato/evento ocorreu ou foi gerado.
   - `registrado_em` (ISO 8601 UTC): Momento em que o sistema logou o evento.
   - `valido_de` / `valido_ate` (Opcional): Período de vigência do fato no mundo real (suporte a substituição não-destrutiva).

3. **Imutabilidade e Evolução**:
   - Nenhum nó ou aresta é destruído fisicamente; modificações geram novos eventos de patch.
   - Informações obsoletas são conectadas via arestas `substitui` ou `contradiz`.
   - **Versão do vocabulário** (`VERSAO_ONTOLOGIA`, atualmente `1.0.0`): cada evento do log declara sob qual versão desta especificação foi escrito. `core/ontologia.py` deriva uma assinatura dos termos em vigor, e um teste exige que a versão declarada acompanhe qualquer mudança de tipo, papel, origem ou status. Eventos anteriores à introdução do campo são lidos como versão `0`.

---

## 2. Tipos de Nós

### 2.1 Camada de Navegação

| Tipo de Nó | Descrição | Autor Permitido |
|---|---|---|
| `Projeto` | Agrupador raiz de alto nível de iniciativas e repositórios. | `humano` |
| `Setor` | Domínio de negócio ou especialidade dentro de um projeto. | `humano` |
| `Sessao` | Contexto de interação onde execuções e diálogos ocorrem. | `humano`, `harness` |

### 2.2 Camada de Trabalho

| Tipo de Nó | Descrição | Autor Permitido |
|---|---|---|
| `Goal` | Intenção ou objetivo de alto nível estabelecido pelo humano. | `humano` |
| `Task` | Unidade de trabalho executável com critério de pronto e status. | `humano`, `planejador` |
| `Decision` | Escolha tomada com alternativas consideradas e justificativa. | `humano`, `planejador`, `executor` |
| `Question` | Ponto de dúvida ou ambiguidade que requer resposta humana. | `planejador`, `executor`, `revisor` |
| `Constraint` | Restrição ou regra mandatória de negócio/código. | `humano` |
| `Artifact` | Entregável produzido (código, documento, patch, arquivo). | `executor` |
| `Evidence` | Fato observado no mundo (saída de teste, log, retorno de busca). | `executor`, `revisor` |
| `Run` | Registro de uma execução de agente (modelo, tokens, latência). | `sistema` |
| `Note` | Anotação textual livre sem contrato semântico estrito. | `humano`, `planejador`, `executor`, `revisor` |

---

## 3. Tipos de Arestas

| Tipo de Aresta | Origem Permitida | Destino Permitido | Semântica |
|---|---|---|---|
| `contem` | `Projeto` → `Setor`, `Setor` → `Sessao` | Hierarquia estrita de navegação. |
| `produz` | `Sessao` → Nó de Trabalho | Vincula o item à sessão onde foi gerado. |
| `ocorreu_em` | `Run` → `Sessao` | Associa a execução à sessão ativa. |
| `decompoe` | `Goal` → `Task`, `Task` → `Task` | Decomposição hierárquica de tarefas. |
| `depende_de` | `Task` → `Task` | Pré-requisito de execução (acíclico obrigatório). |
| `bloqueia` | `Question` → `Task` | Trava o avanço da tarefa até resolução. |
| `justifica` | `Evidence` → `Decision` | Base empírica que sustenta uma decisão. |
| `contradiz` | `Evidence` → `Decision` / `Evidence` | Aponta divergência ou refutação empírica. |
| `substitui` | `Decision` → `Decision`, `Task` → `Task` | Substituição evolutiva de definição anterior. |
| `escopa` | `Constraint` → `Goal` / `Task` | Aplicação de restrição obrigatória. |
| `deriva_de` | `Artifact` / `Note` → `Task` / `Artifact` / `Decision` | Proveniência de artefatos gerados e de notas reativas. |

### 3.1 Dono de Cada Aresta

Criar e remover são poderes distintos, e ambos são impostos pelo `RoleGate`
(`kernel/matriz_papeis.py`). Qualquer agente abre uma escalação com `bloqueia`;
só o humano a retira.

| Tipo de Aresta | Pode criar | Pode remover |
|---|---|---|
| `contem` | `humano`, `sistema` | `humano` |
| `produz` | todos os papéis | `humano` |
| `ocorreu_em` | `humano`, `sistema` | `humano`, `sistema` |
| `decompoe` | `humano`, `planejador` | `humano`, `planejador` |
| `depende_de` | `humano`, `planejador` | `humano`, `planejador` |
| `bloqueia` | `humano`, `planejador`, `executor`, `revisor` | `humano` |
| `justifica` | `humano`, `executor`, `revisor` | `humano`, `executor`, `revisor` |
| `contradiz` | `humano`, `executor`, `revisor` | `humano`, `executor`, `revisor` |
| `substitui` | `humano`, `planejador` | `humano`, `planejador` |
| `escopa` | `humano` | `humano` |
| `deriva_de` | `humano`, `executor`, `revisor` | `humano`, `executor`, `revisor` |

---

## 4. Matriz de Contratos por Papel

"A própria `Task` atribuída" deixou de ser uma frase e virou regra do kernel: a
atribuição é o **lock** da tarefa, adquirido por `assumir_tarefa` e verificado
pelo `InvariantGate` a cada mudança de status. Um agente sem posse recebe
recusa com o modo de falha `posse_de_tarefa_ausente` e o nome de quem detém a
tarefa.

| Papel | Nós que pode criar | Campos que pode editar | Ações proibidas |
|---|---|---|---|
| `humano` | Todos | Todos | Nenhuma |
| `planejador` | `Task`, `Decision`, `Question`, `Note` | `titulo`, `descricao`, `criterio_pronto` de `Task` | Fechar `Task`, editar `Constraint`, encerrar `Question` |
| `executor` | `Artifact`, `Evidence`, `Decision`, `Question`, `Note` | `status` da `Task` cuja posse detém | Criar `Task`, editar `Constraint`, encerrar `Question`, mexer em `Task` de outro |
| `revisor` | `Evidence`, `Question`, `Note` | Status de revisão da `Task` cuja posse detém | Fechar `Task` diretamente, encerrar `Question` |
| `sistema` | `Run`, `Sessao` | Métricas de execução e a própria `Sessao` | Criar ou alterar nós semânticos de trabalho |

### 4.1 O Que Nenhum Agente Faz, Por Nenhum Caminho

Estas três operações exigem sessão humana no **portão**, não no nome da
ferramenta — um `propor_patch` cru recebe a mesma recusa:

1. Mudar o status de uma `Question` para `respondida` ou `descartada`.
2. Remover uma `Question`.
3. Remover uma aresta `bloqueia`.
