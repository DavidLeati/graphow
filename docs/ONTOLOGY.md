# Especificação Formal da Ontologia — Graphow

Especificação semântica do grafo agêntico bilateral para alinhamento entre humanos e agentes de inteligência artificial.

---

## 1. Princípios da Ontologia

1. **Separação em Duas Camadas**:
   - **Camada de Navegação**: Espinha dorsal visual e de agrupamento hierárquico (`Projeto` → `Setor` → `Sessao`). Apenas humanos criam e estruturam a navegação.
   - **Camada de Trabalho**: Nós semânticos de intenção, execução e evidência pendurados exclusivamente em instâncias de `Sessao`. Tanto humanos quanto agentes interagem com a camada de trabalho.
   - **Nenhum nó nasce solto**: exceto `Projeto`, todo nó criado recebe no mesmo lote uma aresta de contenção (`contem`, `produz` ou `decompoe`). O `InvariantGate` recusa o lote com `no_fora_da_hierarquia` para qualquer papel, humano incluído.
   - **Memória diz de onde veio**: o `Aprendizado` é o único nó de trabalho que atravessa a hierarquia, e por isso é o único que nasce apontando obrigatoriamente para a origem. Sem uma aresta `deriva_de` no mesmo lote, o `InvariantGate` recusa com `aprendizado_sem_origem`. O alcance dele (`vale_para` um `Projeto` ou `Setor`, ou a propriedade `alcance: global`) é escrito só pelo humano.
   - **A Sessão tem ciclo de vida** (`ativa`, `concluida`). Encerrada, a vista dela abre pelo fechamento determinístico (decisões vigentes, dúvidas abertas, restrições, último artefato), que é projeção do log e nunca é gravado, e o motor reativo abre nela a `Task` de condensação.

2. **Temporalidade Bitemporal**:
   - `criado_em` (ISO 8601 UTC): Momento em que o fato/evento ocorreu ou foi gerado.
   - `registrado_em` (ISO 8601 UTC): Momento em que o sistema logou o evento.
   - `valido_de` / `valido_ate` (Opcional): Período de vigência do fato no mundo real (suporte a substituição não-destrutiva).

3. **Imutabilidade e Evolução**:
   - Nenhum nó ou aresta é destruído fisicamente; modificações geram novos eventos de patch.
   - Informações obsoletas são conectadas via arestas `substitui` ou `contradiz`.
   - **Versão do vocabulário** (`VERSAO_ONTOLOGIA`, atualmente `1.1.0`): cada evento do log declara sob qual versão desta especificação foi escrito. `core/ontologia.py` deriva uma assinatura dos termos em vigor, e um teste exige que a versão declarada acompanhe qualquer mudança de tipo, papel, origem ou status. Eventos anteriores à introdução do campo são lidos como versão `0`.

---

## 2. Tipos de Nós

### 2.1 Camada de Navegação

| Tipo de Nó | Descrição | Autor Permitido |
|---|---|---|
| `Projeto` | Agrupador raiz de alto nível de iniciativas e repositórios. | `humano`; `harness`, só o Projeto do repositório no ambiente padrão da memória |
| `Setor` | Domínio de negócio ou especialidade dentro de um projeto. | `humano`; `harness`, só o Setor `Memoria` do ambiente padrão |
| `Sessao` | Contexto de interação onde execuções e diálogos ocorrem. Tem ciclo de vida: `ativa` e `concluida`. | `humano`, `harness` |

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
| `Note` | Anotação textual livre sem contrato semântico estrito. Com `acao: condensacao_de_sessao`, é a condensação em prosa de uma sessão encerrada. | `humano`, `planejador`, `executor`, `revisor` |
| `Aprendizado` | Memória de longo prazo: o que sobrevive ao projeto. O rótulo é a afirmação em uma linha; `como_aplicar` diz o que fazer com ela; `alcance: global` só pelo humano; `valido_ate` é lido pela vista. Registra quem detém `deriva_de`. | `humano`, `executor`, `revisor` |

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
| `contradiz` | `Evidence` → `Decision` / `Evidence` / `Aprendizado` | Aponta divergência ou refutação empírica; num `Aprendizado`, sinaliza que ele precisa de revisão. |
| `substitui` | `Decision` → `Decision`, `Task` → `Task`, `Aprendizado` → `Aprendizado` | Substituição evolutiva de definição anterior. O substituído segue visível, marcado. |
| `escopa` | `Constraint` → `Goal` / `Task` | Aplicação de restrição obrigatória. |
| `deriva_de` | `Artifact` → `Task` / `Artifact`; `Note` → `Task` / `Decision` / `Evidence` / `Artifact`; `Aprendizado` → `Evidence` / `Decision` / `Note` / `Artifact` / `Task` | Proveniência de artefatos, de notas reativas, da condensação de uma sessão e da origem de um aprendizado. |
| `vale_para` | `Aprendizado` → `Projeto` / `Setor` | Alcance de um aprendizado promovido: entra na vista de toda tarefa sob esse contêiner. |

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
| `vale_para` | `humano` | `humano` |

Nem a autonomia ilimitada de um projeto abre `escopa` ou `vale_para` a um agente:
a primeira amarra a restrição ao trabalho, a segunda promove memória de agente a
memória de todos.

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
| `planejador` | `Task`, `Decision`, `Question`, `Note` | `titulo`, `descricao`, `criterio_pronto` de `Task` | Fechar `Task`, editar `Constraint`, encerrar `Question`, registrar ou promover `Aprendizado` |
| `executor` | `Artifact`, `Evidence`, `Decision`, `Question`, `Note`, `Aprendizado` | `status` da `Task` cuja posse detém | Criar `Task`, editar `Constraint`, encerrar `Question`, mexer em `Task` de outro, promover `Aprendizado` |
| `revisor` | `Evidence`, `Question`, `Note`, `Aprendizado` | Status de revisão da `Task` cuja posse detém | Fechar `Task` diretamente, encerrar `Question`, promover `Aprendizado` |
| `sistema` | `Run`, `Sessao`, e `Projeto` e `Setor` do ambiente padrão da memória | Métricas de execução e a própria `Sessao` | Criar ou alterar nós semânticos de trabalho |

### 4.1 O Que Nenhum Agente Faz, Por Nenhum Caminho

Estas operações exigem sessão humana no **portão**, não no nome da
ferramenta — um `propor_patch` cru recebe a mesma recusa:

1. Mudar o status de uma `Question` para `respondida` ou `descartada`.
2. Remover uma `Question`.
3. Remover uma aresta `bloqueia`.
4. Escrever `alcance` num `Aprendizado`, ou criar e remover `vale_para`: promover é do humano.
5. Remover um `Aprendizado`: memória é substituída ou contradita, nunca apagada por agente.
