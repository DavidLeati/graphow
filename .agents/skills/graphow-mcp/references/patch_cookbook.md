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

## planejador: registrar o trecho lido e a decisão que ele sustenta

O planejador decide em cima do código que leu, e o que leu entra como `Evidence` com o ponteiro inteiro: `arquivo`, `linhas` e o `trecho` literal dessas linhas. Sem um dos três o InvariantGate recusa com `evidencia_sem_localizacao`, e um trecho com mais linhas do que a faixa também cai. A `Decision` diz onde vale por `orienta`, e é por essa aresta que ela chega à vista de quem executa a tarefa, mesmo que a tarefa tenha nascido noutra sessão.

```json
{
  "justificativa": "Base de dias do fator de desconto confirmada no codigo",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/evi-fator-base-252",
      "value": {
        "id": "evi-fator-base-252",
        "tipo": "Evidence",
        "rotulo": "O fator de desconto usa base 252 dias uteis",
        "propriedades": {
          "arquivo": "src/precos/fator.py",
          "linhas": "40-42",
          "trecho": "def taxa_para_fator(taxa: float, dias: int) -> float:\n    \"\"\"Desconto.\"\"\"\n    return (1 + taxa) ** (-dias / 252)",
          "relevancia": "e onde a taxa de compra vira fator de desconto"
        }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-evi-fator-base-252",
      "value": { "id": "prod-evi-fator-base-252", "origem_id": "sess-sprint-01", "destino_id": "evi-fator-base-252", "tipo": "produz" }
    },
    {
      "op": "add",
      "path": "/nos/dec-manter-base-252",
      "value": {
        "id": "dec-manter-base-252",
        "tipo": "Decision",
        "rotulo": "O novo calculo reusa taxa_para_fator em vez de repetir a formula",
        "propriedades": { "motivo": "a base 252 ja esta la; duas formulas divergiriam na primeira mudanca de convencao" }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-dec-manter-base-252",
      "value": { "id": "prod-dec-manter-base-252", "origem_id": "sess-sprint-01", "destino_id": "dec-manter-base-252", "tipo": "produz" }
    },
    {
      "op": "add",
      "path": "/arestas/just-base-252",
      "value": { "id": "just-base-252", "origem_id": "evi-fator-base-252", "destino_id": "dec-manter-base-252", "tipo": "justifica" }
    },
    {
      "op": "add",
      "path": "/arestas/orienta-base-252",
      "value": { "id": "orienta-base-252", "origem_id": "dec-manter-base-252", "destino_id": "task-parser-csv", "tipo": "orienta" }
    }
  ]
}
```

## executor: começar o trabalho

Não escreva `em_andamento` por patch. `assumir_tarefa(id_task)` toma a posse e move o status na mesma operação, e sem essa posse o InvariantGate recusa qualquer mudança de status sua com `posse_de_tarefa_ausente`.

## executor: registrar o artefato e pedir revisão

Cria o `Artifact`, pendura na sessão por `produz`, liga à tarefa por `deriva_de` e avança o status. Depende da posse tomada no passo anterior. O `produz` não é opcional: todo nó novo, exceto `Projeto`, precisa de aresta de contenção no mesmo lote, e `deriva_de` não é uma — sem ela o lote cai com `no_fora_da_hierarquia`.

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
      "path": "/arestas/prod-art-parser",
      "value": {
        "id": "prod-art-parser",
        "origem_id": "sess-sprint-01",
        "destino_id": "art-csv-parser",
        "tipo": "produz"
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

O revisor registra o que verificou e para por aí. A `Evidence` aponta por `deriva_de` o artefato que avaliou e a tarefa, e o `veredito` diz se passou (`aprovado`) ou não (`rejeitado`, com o trecho que o prova). Acrescentar `"value": "concluido"` ao status da tarefa neste mesmo lote derrubaria tudo com `violacao_permissao_papel`: fechar `Task` é de executor e humano, e o patch é atômico.

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
          "veredito": "aprovado",
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
      "op": "add",
      "path": "/arestas/deriv-evi-art",
      "value": {
        "id": "deriv-evi-art",
        "origem_id": "evi-test-pass",
        "destino_id": "art-csv-parser",
        "tipo": "deriva_de"
      }
    },
    {
      "op": "add",
      "path": "/arestas/deriv-evi-task",
      "value": {
        "id": "deriv-evi-task",
        "origem_id": "evi-test-pass",
        "destino_id": "task-parser-csv",
        "tipo": "deriva_de"
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
  "titulo": "Linha em branco no CSV: ignorar ou avisar?",
  "pergunta": "O parser deve ignorar linhas em branco silenciosamente ou lançar ParseWarning? O arquivo de amostra tem 14 linhas vazias no meio, e o contrato do importador não diz nada sobre elas.",
  "id_no_bloqueado": "task-parser-csv",
  "id_sessao": "sess-sprint-01"
}
```

O `titulo` é o rótulo do nó, e é o que o card mostra no canvas: mande uma linha. O corpo vai em `pergunta` e pode ser tão longo quanto a dúvida exigir. Sem `titulo`, ele é derivado do começo da pergunta — e uma pergunta de vinte linhas vira um título truncado.

Você abre a dúvida e espera em `aguardar_resposta`. Mover a `Question` para `respondida` ou `descartada`, removê-la ou tirar o `bloqueia` são operações de sessão humana, por qualquer caminho.

## revisor: condensar a sessão encerrada

A Task de condensar (`acao: condensar_sessao`) foi aberta pelo grafo quando a sessão `sess-sprint-01` encerrou. Depois de `assumir_tarefa` nela e de `ler_vista("sess-sprint-01")`, a condensação é uma `Note` produzida pela sessão, com `deriva_de` para cada nó de onde saiu uma afirmação do corpo. Sem o `produz`, a Note nasce fora da hierarquia; sem os `deriva_de`, é opinião sem origem.

```json
{
  "justificativa": "Condensacao da sessao sess-sprint-01: decisoes vigentes, achados e o que ficou aberto",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/nota-condensacao-sprint-01",
      "value": {
        "id": "nota-condensacao-sprint-01",
        "tipo": "Note",
        "rotulo": "Condensacao da sprint 01",
        "propriedades": {
          "acao": "condensacao_de_sessao",
          "id_alvo": "sess-sprint-01",
          "corpo": "Vigora: o parser CSV ignora linhas em branco e avisa por ParseWarning, porque o contrato do importador nao as menciona e a amostra tem 14 delas. Achado que mudou a decisao: o relatorio de 14 testes aprovados com 98,5% de cobertura. Ficou aberto: a carga em lote no SQLite. Nao fazer de novo: decidir o tratamento de linhas em branco sem abrir questao ao humano."
        }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-nota-condensacao-sprint-01",
      "value": {
        "id": "prod-nota-condensacao-sprint-01",
        "origem_id": "sess-sprint-01",
        "destino_id": "nota-condensacao-sprint-01",
        "tipo": "produz"
      }
    },
    {
      "op": "add",
      "path": "/arestas/deriv-condensacao-evi",
      "value": {
        "id": "deriv-condensacao-evi",
        "origem_id": "nota-condensacao-sprint-01",
        "destino_id": "evi-test-pass",
        "tipo": "deriva_de"
      }
    },
    {
      "op": "add",
      "path": "/arestas/deriv-condensacao-art",
      "value": {
        "id": "deriv-condensacao-art",
        "origem_id": "nota-condensacao-sprint-01",
        "destino_id": "art-csv-parser",
        "tipo": "deriva_de"
      }
    },
    {
      "op": "replace",
      "path": "/nos/task-condensar-sprint-01/propriedades/status",
      "value": "pronto_para_revisao"
    }
  ]
}
```

O revisor não grava `concluido`: ele deixa a Task em `pronto_para_revisao` e devolve a posse com `liberar_tarefa`. Um executor que condensasse poderia fechar por `concluir_tarefa`.
