# Cookbook de JSON Patch (RFC 6902)

Patches prontos para `propor_patch`, por papel. Nenhum deles declara o papel do autor: ele é fixado na abertura da sessão MCP (`graphow mcp --papel <papel>`) e qualquer chamada que o traga nos argumentos é recusada.

## planejador: decompor em tarefas com dependência

Duas tarefas sob a sessão `sess-sprint-01`, com a carga dependendo do parser. O `depende_de` só passa se não fechar ciclo, e só o planejador e o humano podem criá-lo.

```json
{
  "justificativa": "Decomposição do pipeline de ingestão de dados em etapas sequenciais",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/task-parser-csv",
      "value": {
        "id": "task-parser-csv",
        "tipo": "Task",
        "rotulo": "Implementar parser robusto de arquivos CSV",
        "propriedades": {
          "status": "pendente",
          "estimativa_horas": 4
        }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-parser",
      "value": {
        "id": "prod-parser",
        "origem_id": "sess-sprint-01",
        "destino_id": "task-parser-csv",
        "tipo": "produz"
      }
    },
    {
      "op": "add",
      "path": "/nos/task-loader-db",
      "value": {
        "id": "task-loader-db",
        "tipo": "Task",
        "rotulo": "Implementar carga em lote no banco SQLite",
        "propriedades": {
          "status": "pendente",
          "estimativa_horas": 3
        }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-loader",
      "value": {
        "id": "prod-loader",
        "origem_id": "sess-sprint-01",
        "destino_id": "task-loader-db",
        "tipo": "produz"
      }
    },
    {
      "op": "add",
      "path": "/arestas/dep-loader-parser",
      "value": {
        "id": "dep-loader-parser",
        "origem_id": "task-loader-db",
        "destino_id": "task-parser-csv",
        "tipo": "depende_de"
      }
    }
  ]
}
```

## executor: começar o trabalho

Não escreva `em_andamento` por patch. `assumir_tarefa(id_task)` toma a posse e move o status na mesma operação, e sem essa posse o InvariantGate recusa qualquer mudança de status sua com `posse_de_tarefa_ausente`.

## executor: registrar o artefato e pedir revisão

Cria o `Artifact`, liga à tarefa por `deriva_de` e avança o status. Depende da posse tomada no passo anterior.

```json
{
  "justificativa": "Conclusão do parser CSV com tratamento de erros de encoding e testes de unidade",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/art-csv-parser",
      "value": {
        "id": "art-csv-parser",
        "tipo": "Artifact",
        "rotulo": "src/graphow/parsers/csv.py",
        "propriedades": {
          "caminho": "src/graphow/parsers/csv.py",
          "linhas": 120,
          "testes_associados": "tests/test_csv_parser.py"
        }
      }
    },
    {
      "op": "add",
      "path": "/arestas/deriv-parser-art",
      "value": {
        "id": "deriv-parser-art",
        "origem_id": "art-csv-parser",
        "destino_id": "task-parser-csv",
        "tipo": "deriva_de"
      }
    },
    {
      "op": "replace",
      "path": "/nos/task-parser-csv/propriedades/status",
      "value": "pronto_para_revisao"
    }
  ]
}
```

## revisor: anexar a evidência da auditoria

O revisor registra o que verificou e para por aí. Acrescentar `"value": "concluido"` ao status da tarefa neste mesmo lote derrubaria tudo com `violacao_permissao_papel`: fechar `Task` é de executor e humano, e o patch é atômico.

```json
{
  "justificativa": "Auditoria de código e suite de testes executada com 100% de sucesso",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/evi-test-pass",
      "value": {
        "id": "evi-test-pass",
        "tipo": "Evidence",
        "rotulo": "Relatório de testes pytest: 14 aprovados",
        "propriedades": {
          "cobertura": "98.5%",
          "tempo_execucao_ms": 340
        }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-evi",
      "value": {
        "id": "prod-evi",
        "origem_id": "sess-sprint-01",
        "destino_id": "evi-test-pass",
        "tipo": "produz"
      }
    }
  ]
}
```

Quem fecha a tarefa depois é o executor que a detém, por `concluir_tarefa`.

## Dúvida: use `abrir_questao`, não patch

Criar o nó `Question` por `propor_patch` é tecnicamente possível e quase sempre errado. A ferramenta dedicada cria a `Question`, liga à sessão por `produz` e aplica o `bloqueia` sobre a tarefa num lote atômico:

```json
{
  "pergunta": "O parser deve ignorar linhas em branco silenciosamente ou lançar ParseWarning?",
  "id_no_bloqueado": "task-parser-csv",
  "id_sessao": "sess-sprint-01"
}
```

Você abre a dúvida e espera em `aguardar_resposta`. Mover a `Question` para `respondida` ou `descartada`, removê-la ou tirar o `bloqueia` são operações de sessão humana, por qualquer caminho.
