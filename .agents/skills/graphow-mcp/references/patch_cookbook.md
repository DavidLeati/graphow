# Cookbook de JSON Patch (RFC 6902) para o Graphow

> **O campo `papel` nao existe mais nos patches.** O papel e fixado na abertura da
> sessao MCP (`graphow mcp --papel <papel>`) e qualquer chamada que traga `papel`
> nos argumentos e recusada. Os exemplos abaixo ja refletem isso.

Exemplos práticos e canônicos de operações JSON Patch para submissão via ferramenta MCP `propor_patch`.

---

## 1. Operações do Papel: `planejador`

### Receita 1.1: Decompor Goal em Tarefas com Dependência Causal
Cria duas tarefas sob a sessão `sess-sprint-01` e define que a Tarefa 2 depende da Tarefa 1:

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

---

## 2. Operações do Papel: `executor`

### Receita 2.1: Assumir Início de Trabalho em uma Tarefa
Altera o status da tarefa para `em_andamento`:

```json
{
  "justificativa": "Iniciando implementação do parser CSV",
  "operacoes": [
    {
      "op": "replace",
      "path": "/nos/task-parser-csv/propriedades/status",
      "value": "em_andamento"
    }
  ]
}
```

### Receita 2.2: Registrar Artefato de Código Produzido e Pedir Revisão
Cria o nó `Artifact`, conecta à tarefa via `deriva_de` e avança status para `pronto_para_revisao`:

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

---

## 3. Operações do Papel: `revisor`

### Receita 3.1: Anexar Evidência de Auditoria e Aprovar Conclusão
Cria nó `Evidence` atestando cobertura de testes de 100% e libera a tarefa para `concluido`:

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
        "rotulo": "Relatório de Testes Pytest: 14 testes aprovados",
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
    },
    {
      "op": "replace",
      "path": "/nos/task-parser-csv/propriedades/status",
      "value": "concluido"
    }
  ]
}
```

---

## 4. Dica de Bloqueio por Dúvidas: Use `abrir_questao`

Embora seja tecnicamente possível criar um nó `Question` via `propor_patch`, **SEMPRE PREFIRA** utilizar a ferramenta dedicada `abrir_questao`:

```json
{
  "pergunta": "O parser deve ignorar linhas em branco silenciosamente ou lançar ParseWarning?",
  "id_no_bloqueado": "task-parser-csv",
  "id_sessao": "sess-sprint-01"
}
```
A ferramenta `abrir_questao` cria o nó `Question`, o vincula à sessão via `produz` e aplica a aresta `bloqueia` sobre a tarefa de forma atômica e segura.
