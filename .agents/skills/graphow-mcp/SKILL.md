---
name: graphow-mcp
description: Protocolo de operação do grafo agêntico bilateral do Graphow via Model Context Protocol (MCP). Use esta skill para escolher o que fazer numa sessão (proximas_tarefas), tomar posse de uma tarefa antes de mexer nela (assumir_tarefa, liberar_tarefa), ler contexto sob orçamento de tokens (ler_vista, expandir_no), propor mutações em JSON Patch RFC 6902 (propor_patch), escalar dúvida ao humano e esperar a resposta (abrir_questao, aguardar_resposta, minhas_questoes) ou pesquisar nós (buscar). Cobre a ontologia formal, os 4 portões de governança (SchemaGate, RoleGate, InvariantGate, WriteKernel) e os contratos dos papéis planejador, executor e revisor.
---

# Graphow MCP: operação do grafo agêntico

O grafo do Graphow é projeção determinística de um log append-only bitemporal. Você não edita o grafo. Você propõe mutações, e o Kernel de 4 Portões aceita ou recusa o lote inteiro.

## Regras que o kernel aplica

Cada item abaixo é recusa em tempo de execução, não recomendação de estilo.

**1. Só se escreve pelo PatchBoard.** Não abra o SQLite (`graphow.db`) por SQL nem por ferramenta de arquivo. Toda mutação passa pelas ferramentas MCP de ação ou por `propor_patch`; não existe caminho alternativo.

**2. Contexto sob orçamento.** Nunca peça o grafo inteiro. Chame `ler_vista` com `orcamento_tokens` proporcional à fase: 1500 para entrar numa tarefa, 500 para acompanhar, 200 para conferir. Quando a resposta trouxer `vizinhos_expansiveis`, use `expandir_no` no nó que interessa em vez de subir o orçamento.

**3. O papel pertence à sessão, não à chamada.** O campo do papel é recusado em qualquer ferramenta: quem o fixa é a pessoa ao abrir o servidor (`graphow mcp --papel <papel>`), e ele não muda enquanto a conexão viver. Leia o seu em `serverInfo.papelDaSessao`, na resposta de `initialize`.

- `planejador`: cria `Task`, `Decision`, `Question`, `Note`. Não conclui tarefa.
- `executor`: cria `Artifact`, `Evidence`, `Decision`, `Question`, `Note` e move o status da tarefa que detém. É o único papel de agente que grava `concluido`.
- `revisor`: cria `Evidence`, `Question`, `Note` e registra o que auditou. Não produz artefato executivo nem conclui tarefa.

**4. As arestas também têm dono.** `contem`, `escopa` e a remoção de `bloqueia` são exclusivas do humano. `decompoe`, `depende_de` e `substitui`: planejador e humano. `deriva_de`, `justifica` e `contradiz`: executor, revisor e humano. `produz` e a criação de `bloqueia` ficam abertas a qualquer papel. A matriz completa, com a coluna de remoção e o que muda sob autonomia ilimitada, está em [ontology_matrix.md](./references/ontology_matrix.md).

**5. Invariantes estruturais.** Todo nó novo, exceto `Projeto`, nasce pendurado na hierarquia: o mesmo lote que o cria traz a aresta de contenção que chega nele — `produz` vinda da `Sessao` para nós de trabalho, `decompoe` vinda de um `Goal` ou `Task` para subtarefas. `deriva_de` não conta. Sem isso o lote inteiro é recusado com `no_fora_da_hierarquia`, inclusive para o humano. As arestas `depende_de` formam um DAG, e o patch que fecha ciclo é rejeitado por inteiro. Uma `Task` não transiciona para `concluido` enquanto existir `Question` aberta ligada a ela por aresta `bloqueia`.

**6. Quem encerra a dúvida é a pessoa.** `responder_questao`, `configurar_autonomia_projeto`, `excluir_projeto`, `excluir_em_lote` e `encerrar_sessao` exigem sessão humana e recusam sessão de agente. O RoleGate barra o mesmo efeito por qualquer caminho, `propor_patch` incluído: mover uma `Question` para `respondida` ou `descartada`, remover uma `Question`, remover uma aresta `bloqueia`. Depois de `abrir_questao`, espere em `aguardar_resposta` em vez de sondar com `expandir_no`.

**7. Posse antes de status.** Chame `assumir_tarefa` antes de mexer no status de uma `Task`; o kernel recusa a escrita de quem não é dono e devolve o nome de quem é. Se parar no meio, `liberar_tarefa`, para não travar a fila dos outros.

**8. Ambiguidade vira questão, não chute.** Especificação vaga, dependência faltando, contrato em conflito: `abrir_questao` suspende a tarefa e chama o humano.

## As 20 ferramentas do servidor

### Leitura

| Ferramenta | Argumentos | O que faz |
| :--- | :--- | :--- |
| `ler_vista` | `id_alvo`, `orcamento_tokens` (1500), `escopo` (`tudo`\|`ativo`), `raio_do_escopo`, `ramo_id` | Devolve o subgrafo focal em Markdown dentro do orçamento. Em contêiner (Projeto, Setor, Sessao) devolve o panorama dos filhos, quantas tarefas fecharam, quantas seguem abertas, quantas dúvidas esperam, em vez da subárvore. |
| `expandir_no` | `id_no`, `ramo_id` | Propriedades e arestas incidentes de um nó, sem corte. |
| `buscar` | `termo`, `tipos_no`, `limite` (5, teto 50), `escopo`, `ramo_id` | Busca ranqueada: rótulo vence propriedade, palavra inteira vence prefixo, aberto vence encerrado. Se voltar `truncado`, refine o termo em vez de subir o `limite`. |
| `proximas_tarefas` | `id_sessao`, `ramo_id` | Fila ordenada por urgência com o que está livre para pegar. Traz também `impedidas`, com o motivo de cada exclusão (`duvida_aberta`, `dependencia_pendente`, `posse_de_outro`, `concluida`), que é o que dizer quando a fila volta vazia. |

### Posse e escalação

| Ferramenta | Argumentos | O que faz |
| :--- | :--- | :--- |
| `assumir_tarefa` | `id_task` | Toma a posse exclusiva e move a tarefa para `em_andamento`. |
| `liberar_tarefa` | `id_task` | Devolve a posse sem tocar no status. |
| `minhas_questoes` | `status` | Lista as dúvidas abertas por esta sessão, com a resposta humana quando já houver. |
| `aguardar_resposta` | `id_questao`, `timeout_segundos` (30, teto 300) | Bloqueia até a pessoa encerrar a dúvida ou o prazo expirar, e diz como retomar. |

### Ação e governança

| Ferramenta | Argumentos | O que faz |
| :--- | :--- | :--- |
| `criar_projeto` | `rotulo`, `nivel_autonomia`, `descricao` | Cria o Projeto raiz e define a autonomia dos agentes nele. |
| `criar_setor` | `rotulo`, `id_projeto` | Cria o Setor e a aresta `contem`. |
| `criar_sessao` | `rotulo`, `id_setor` | Cria a Sessao e a aresta `contem`. |
| `criar_tarefa` | `titulo`, `id_sessao`, `descricao`, `criterio_pronto`, `id_tarefa_pai`, `depende_de` | Cria a Task com aresta `produz` e as hierarquias opcionais. |
| `abrir_questao` | `pergunta`, `id_no_bloqueado`, `id_sessao`, `titulo` | Abre a Question e a aresta `bloqueia`, travando a conclusão da tarefa. `titulo` é a chamada de uma linha que o card exibe; `pergunta` é o corpo por extenso. Omitido o `titulo`, ele é derivado do começo da pergunta. |
| `responder_questao` | `id_questao`, `resposta` *(só humano)* | Registra a resposta, move a Question para `respondida` e destrava a Task. |
| `concluir_tarefa` | `id_task`, `justificativa` | Move a Task para `concluido`, se destravada. |
| `configurar_autonomia_projeto` | `id_projeto`, `nivel_autonomia` (`estrito`\|`ilimitado`) *(só humano)* | Muda a permissividade dos agentes no projeto. |
| `encerrar_sessao` | `id_sessao`, `resumo` *(só humano)* | Encerra a Sessao: status `concluida` e resumo opcional. A vista da sessão passa a abrir pelo fechamento, e `ler_vista` numa sessão encerrada é o jeito barato de retomá-la. |
| `excluir_em_lote` | `ids_nos`, `ids_arestas`, `justificativa` *(só humano)* | Remove atomicamente uma coleção de nós e arestas. |
| `excluir_projeto` | `id_projeto`, `cascata` (true) *(só humano)* | Remove o projeto e, em cascata, setores, sessões e tarefas. |
| `propor_patch` | `operacoes` (RFC 6902), `justificativa`, `ramo_id` | Submete um lote atômico livre aos 4 portões. |

## Roteiro padrão

1. **Retomar e escolher.** Comece por `minhas_questoes`, para não reabrir dúvida já respondida. Desça do Projeto pelo panorama de `ler_vista` e abra só o filho marcado com trabalho aberto; varrer todos os contêineres custa uma ordem de grandeza a mais e chega na mesma resposta. Peça a fila com `proximas_tarefas(id_sessao)` e pegue o topo com `assumir_tarefa(id_task)`.
2. **Orientar-se na tarefa.** `ler_vista` na Task assumida e, se faltar detalhe de vizinho, `expandir_no` no nó específico.
3. **Checar bloqueio.** Havendo requisito vago ou impedimento, `abrir_questao` e depois `aguardar_resposta`. Se o prazo expirar, `liberar_tarefa` e encerre limpo.
4. **Executar.** O trabalho técnico acontece fora do grafo, em código e documentos. Ao terminar, monte o lote JSON Patch.
5. **Registrar.** Submeta `propor_patch` e confira `sucesso` no recibo; se vier recusa, leia `modo_de_falha` e corrija a proposta. Depois `concluir_tarefa` e `liberar_tarefa`.

## JSON Patch (RFC 6902)

Paths canônicos:

- `/nos/<id>`: adição, substituição ou remoção de nó.
- `/nos/<id>/propriedades/<chave>`: atualização granular de propriedade.
- `/arestas/<id>`: adição ou remoção de aresta direcionada.

### Criar tarefa e aresta estrutural (planejador)

```json
{
  "justificativa": "Decomposição da funcionalidade de autenticação JWT",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/task-auth-jwt",
      "value": {
        "id": "task-auth-jwt",
        "tipo": "Task",
        "rotulo": "Implementar middleware de validação JWT",
        "propriedades": {
          "status": "pendente",
          "complexidade": "media"
        }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-task-auth",
      "value": {
        "id": "prod-task-auth",
        "origem_id": "sess-01",
        "destino_id": "task-auth-jwt",
        "tipo": "produz"
      }
    }
  ]
}
```

Um executor receberia recusa do RoleGate já na criação da Task, e nenhum papel de agente consegue acrescentar uma aresta `escopa` ligando uma `Constraint` a essa tarefa.

### Registrar artefato e atualizar a tarefa (executor)

```json
{
  "justificativa": "Entrega do módulo de autenticação e solicitação de revisão",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/art-jwt-py",
      "value": {
        "id": "art-jwt-py",
        "tipo": "Artifact",
        "rotulo": "src/security/jwt_auth.py",
        "propriedades": {
          "caminho_arquivo": "src/security/jwt_auth.py",
          "versao": "1.0.0"
        }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-art-jwt",
      "value": {
        "id": "prod-art-jwt",
        "origem_id": "sess-01",
        "destino_id": "art-jwt-py",
        "tipo": "produz"
      }
    },
    {
      "op": "add",
      "path": "/arestas/deriv-art-jwt",
      "value": {
        "id": "deriv-art-jwt",
        "origem_id": "art-jwt-py",
        "destino_id": "task-auth-jwt",
        "tipo": "deriva_de"
      }
    },
    {
      "op": "replace",
      "path": "/nos/task-auth-jwt/propriedades/status",
      "value": "pronto_para_revisao"
    }
  ]
}
```

Este lote só passa com a posse de `task-auth-jwt`. Sem `assumir_tarefa` antes, o InvariantGate recusa a última operação e devolve o nome de quem detém a tarefa. Sem o `produz`, o `Artifact` nasceria fora da hierarquia e o lote cairia com `no_fora_da_hierarquia`: o `deriva_de` liga o artefato à tarefa, mas não o põe dentro de sessão nenhuma.

## Referências

- [Matriz ontológica e regras de aresta](./references/ontology_matrix.md): as 11 arestas, os pares de tipo válidos e a sanitização de dados.
- [Cookbook de JSON Patch](./references/patch_cookbook.md): patches prontos por papel e finalidade.
- [Guia de conexão MCP](./references/mcp_setup_guide.md): como configurar e testar o servidor stdio em Antigravity, Cursor, Claude Desktop e Arena.
