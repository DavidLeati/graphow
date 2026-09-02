---
name: graphow-mcp
description: Guia operacional para modelos de linguagem interagirem com o grafo agêntico bilateral do Graphow via Model Context Protocol (MCP). Use esta skill quando precisar escolher o que fazer numa sessão (proximas_tarefas), tomar posse de uma tarefa antes de mexer nela (assumir_tarefa, liberar_tarefa), consultar contexto sob orçamento estrito de tokens (ler_vista, expandir_no), propor mutações transacionais governadas via JSON Patch RFC 6902 (propor_patch), escalar dúvidas ao humano e aguardar a resposta (abrir_questao, aguardar_resposta, minhas_questoes), ou pesquisar nós e objetivos (buscar), respeitando a ontologia formal, os 4 portões de governança (SchemaGate, RoleGate, InvariantGate, WriteKernel) e os contratos por papel (planejador, executor, revisor).
---

# Graphow MCP — Governança e Operação do Grafo Agêntico Bilateral

Esta skill define o protocolo estrito de interação de agentes autônomos de IA com a plataforma **Graphow** através do **Model Context Protocol (MCP)**. O Graphow é um substrato de alinhamento bilateral onde o grafo é uma projeção determinística derivada de um log de eventos *append-only* bitemporal.

---

## 🛡️ Invariantes Inegociáveis (Non-Negotiables)

1. **O Log é a Verdade Absoluta:**
   - **NUNCA** tente acessar, ler ou mutar a base de dados SQLite (`graphow.db`) diretamente via SQL bruto ou ferramentas genéricas de arquivo.
   - **TODA** mutação de estado **DEVE** passar exclusivamente pelo Kernel de 4 Portões através das ferramentas MCP formais: `propor_patch` ou `abrir_questao`.
2. **Context Engineering sob Orçamento Estrito:**
   - **NUNCA** solicite o despejo integral do grafo.
   - Sempre utilize `ler_vista` especificando o `orcamento_tokens` adequado à fase da tarefa (ex: `1500` para contextualização inicial, `500` para acompanhamento, `200` para checagem rápida).
   - Pratique **divulgação progressiva** (*Progressive Disclosure*): se precisar de detalhes profundos de nós vizinhos retornados em `vizinhos_expansiveis`, use `expandir_no` pontualmente.
3. **Respeito aos Contratos de Papel (`RoleGate`):**
   - **NÃO** envie o campo `papel` em chamada alguma: ele é **recusado**. O papel é propriedade da sessão MCP, fixado pelo humano ao abrir o servidor (`graphow mcp --papel <papel>`) e imutável durante toda a conexão.
   - Descubra o papel desta sessão no campo `serverInfo.papelDaSessao` da resposta de `initialize`.
   - **`planejador`**: Autorizado a criar `Task`, `Decision`, `Question`, `Note`. **PROIBIDO** de marcar tarefas como concluídas.
   - **`executor`**: Autorizado a criar `Artifact`, `Evidence`, `Question`, `Note`, e atualizar progresso de tarefas. **PROIBIDO** de criar novas tarefas ou alterar `Constraint`.
   - **`revisor`**: Autorizado a criar `Evidence`, `Question`, `Note` e validar artefatos. **PROIBIDO** de produzir artefatos executivos.
4. **Respeito às Invariantes Estruturais (`InvariantGate`):**
   - **Aciclicidade Estrita:** Arestas do tipo `depende_de` formam um Grafo Acíclico Dirigido (DAG). Mutações que induzam ciclos são rejeitadas atomicamente.
   - **Bloqueio por Questões Abertas:** Uma `Task` **NÃO PODE** transicionar para `concluido` enquanto houver um nó `Question` aberto conectado a ela por aresta `bloqueia`.
5. **A Escalação Só o Humano Encerra:**
   - `responder_questao`, `configurar_autonomia_projeto`, `excluir_projeto` e `excluir_em_lote` exigem uma sessão aberta como `humano`. Uma sessão de agente recebe recusa explícita.
   - A recusa **não é apenas pelo nome da ferramenta**. O `RoleGate` também barra, para qualquer papel de agente e por qualquer caminho, inclusive `propor_patch`:
     - mudar o status de uma `Question` para `respondida` ou `descartada`;
     - remover uma `Question`;
     - remover a aresta `bloqueia`.
   - Você abre a dúvida; quem a responde é a pessoa. Depois de abrir, use `aguardar_resposta` em vez de ficar sondando com `expandir_no`.
6. **Posse Antes de Mexer no Status:**
   - Nenhum agente move o status de uma `Task` sem deter a posse dela. Chame `assumir_tarefa` primeiro; o kernel recusa a escrita de quem não é dono, com o nome de quem é.
   - Ao interromper o trabalho sem concluir, devolva a posse com `liberar_tarefa` para não travar a fila dos outros.
7. **A Camada de Arestas Também Tem Dono:**
   - `contem`, `escopa` e a **remoção** de `bloqueia` são exclusivas do humano.
   - `decompoe` e `depende_de`: planejador e humano.
   - `deriva_de`, `justifica` e `contradiz`: executor, revisor e humano.
8. **Escalar em vez de Alucinar:**
   - Ao encontrar ambiguidade em especificações, dependências faltantes ou contratos conflitantes, **NÃO ADIVINHE**. Use `abrir_questao` para suspender o trabalho da tarefa e acionar o humano no loop (*Common Ground*).

---

## 🔌 Superfície de Ferramentas MCP Disponíveis

O servidor MCP do Graphow expõe 19 ferramentas padronizadas divididas em três camadas:

### 1. Ferramentas de Leitura & Inspeção
| Ferramenta | Argumentos Principais | Finalidade Operacional |
| :--- | :--- | :--- |
| **`ler_vista`** | `id_alvo`, `orcamento_tokens` (default: 1500), `ramo_id` | Materializa subgrafo focal formatado em Markdown sob orçamento rígido de tokens. |
| **`expandir_no`** | `id_no`, `ramo_id` | Obtém ficha cadastral exaustiva de propriedades e arestas incidentes de um nó específico. |
| **`buscar`** | `termo`, `tipos_no` (opcional), `ramo_id` | Pesquisa textual *case-insensitive* sobre rótulos e propriedades de nós. |
| **`proximas_tarefas`** | `id_sessao`, `ramo_id` | Fila de trabalho: tarefas com dependências concluídas, sem dúvida aberta e sem posse de outro agente, já ordenadas por urgência. Devolve também `impedidas`, com o motivo de cada exclusão (`duvida_aberta`, `dependencia_pendente`, `posse_de_outro`, `concluida`) — é o que dizer quando a fila volta vazia. |

### 2. Ferramentas de Posse e de Retorno da Escalação
| Ferramenta | Argumentos Principais | Finalidade Operacional |
| :--- | :--- | :--- |
| **`assumir_tarefa`** | `id_task` | Adquire a posse exclusiva da Task e a move para `em_andamento`. Exigido antes de qualquer mudança de status. |
| **`liberar_tarefa`** | `id_task` | Devolve a posse sem alterar o status registrado. |
| **`minhas_questoes`** | `status` (opcional) | Lista as dúvidas abertas por esta sessão, com a resposta humana quando já houver. |
| **`aguardar_resposta`** | `id_questao`, `timeout_segundos` (default 30, teto 300) | Bloqueia até o humano encerrar a dúvida, ou até o prazo expirar, devolvendo como retomar. |

### 3. Ferramentas de Ação de Alto Nível & Governança
| Ferramenta | Argumentos Principais | Finalidade Operacional |
| :--- | :--- | :--- |
| **`criar_projeto`** | `rotulo`, `nivel_autonomia` (estrito/ilimitado), `descricao` | Cria o nó Projeto raiz definindo a autonomia dos agentes. |
| **`criar_setor`** | `rotulo`, `id_projeto` | Cria o Setor e a aresta `contem` ligando ao Projeto. |
| **`criar_sessao`** | `rotulo`, `id_setor` | Cria a Sessão e a aresta `contem` ligando ao Setor. |
| **`criar_tarefa`** | `titulo`, `id_sessao`, `descricao`, `criterio_pronto`, `id_tarefa_pai`, `depende_de` | Cria uma Task com aresta `produz` e hierarquias opcionais. |
| **`abrir_questao`** | `pergunta`, `id_no_bloqueado`, `id_sessao` | Abre Question e aresta `bloqueia` sobre a tarefa (trava conclusão). |
| **`responder_questao`** | `id_questao`, `resposta` | Registra a resposta, move Question para `respondida` e **destrava a Task**. |
| **`concluir_tarefa`** | `id_task`, `justificativa` | Transiciona a Task para `concluido` (se destravada). |
| **`configurar_autonomia_projeto`**| `id_projeto`, `nivel_autonomia` (`estrito` / `ilimitado`) *(somente sessão humana)* | Modifica a permissividade dos agentes no projeto. |
| **`excluir_em_lote`** | `ids_nos`, `ids_arestas`, `justificativa` | Remove atomicamente uma coleção arbitrária de nós e arestas. |
| **`excluir_projeto`** | `id_projeto`, `cascata` (default: true) | Remove o projeto e em cascata todos os setores, sessões e tarefas associadas. |
| **`propor_patch`** | `operacoes` (RFC 6902), `justificativa`, `ramo_id` | Submete lote atômico livre avaliado pelos 4 portões. |

---

## 🧭 Roteiro Padrão de Execução (Default Route)

Siga rigorosamente este fluxo de cinco etapas ao executar qualquer atribuição agêntica:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. FASE DE RECONHECIMENTO & SESSÃO (Gate 0)                 │
│    - Retomar pendências da sessão anterior: `minhas_questoes`│
│    - Descobrir a Sessão ativa via `buscar(tipos_no=["Sessao"])│
│    - Pedir a fila: `proximas_tarefas(id_sessao)`            │
│    - Tomar posse do topo da fila: `assumir_tarefa(id_task)` │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. FASE DE ORIENTAÇÃO FOCAL                                 │
│    - Inspecionar a Task assumida via `ler_vista(id_alvo=...)│
│    - Se necessário, inspecionar nós vizinhos com `expandir_no`│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. FASE DE VERIFICAÇÃO DE BLOQUEIO                          │
│    - Há dúvidas, impedimentos de API ou requisitos vagos?   │
│    - SIM ──> `abrir_questao` e depois `aguardar_resposta`.  │
│              Se expirar, `liberar_tarefa` e encerrar limpo. │
│    - NÃO ──> Prosseguir para execução.                      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. FASE DE EXECUÇÃO & PRODUÇÃO DE ENTREGÁVEIS               │
│    - Executar o trabalho técnico fora do grafo (código/docs)│
│    - Preparar lote JSON Patch RFC 6902                      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. FASE DE COMUNICADO & COMMIT (PatchBoard)                 │
│    - Submeter `propor_patch` atômico via MCP                │
│    - Validar se `sucesso == true` no recibo                 │
│    - Se rejeitado, ler `modo_de_falha` e corrigir a proposta│
│    - `concluir_tarefa` e então `liberar_tarefa`             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧩 Protocolo JSON Patch (RFC 6902)

Toda mutação enviada para `propor_patch` deve seguir a semântica RFC 6902:

### Paths Canônicos no Graphow:
- `/nos/<id>`: Alvo de adição, substituição ou remoção de nós.
- `/nos/<id>/propriedades/<chave>`: Atualização granular de propriedades de um nó.
- `/arestas/<id>`: Alvo de adição ou remoção de arestas direcionadas.

### Exemplo: Adicionar Task e Aresta Estrutural (`planejador`)
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

> **Atenção:** o exemplo acima cria a Task e a aresta `produz`. Um `planejador`
> pode fazê-lo. Um `executor` receberia recusa do `RoleGate` na criação da Task,
> e ninguém além do humano consegue acrescentar uma aresta `escopa` ligando uma
> `Constraint` a essa tarefa.

### Exemplo: Registrar Artifact e Atualizar Tarefa (`executor`)
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

> Este lote só passa se a sessão já tiver a posse de `task-auth-jwt`. Chame
> `assumir_tarefa` antes; sem posse, o `InvariantGate` recusa a última operação e
> devolve o nome de quem detém a tarefa.

---

## 📑 Guias de Referência Rápidos

Consulte os arquivos de aprofundamento na pasta `references/` conforme sua necessidade específica:
- [Matriz Ontológica & Regras de Arestas](./references/ontology_matrix.md): Catálogo das 11 arestas, pares válidos de tipos e sanitização de dados.
- [Cookbook de JSON Patch](./references/patch_cookbook.md): Padrões de patches prontos para cópia rápida divididos por papel e finalidade.
- [Guia de Conexão MCP](./references/mcp_setup_guide.md): Como configurar e testar o servidor stdio em múltiplos harnesses (Antigravity, Cursor, Claude Desktop, Arena).
