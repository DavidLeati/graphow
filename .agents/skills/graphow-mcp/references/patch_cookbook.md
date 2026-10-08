# Cookbook de JSON Patch (RFC 6902)

Patches prontos para `propor_patch`, por papel. Nenhum deles declara o papel do autor: ele é fixado na abertura da sessão MCP (`graphow mcp --papel <papel>`) e qualquer chamada que o traga nos argumentos é recusada.

## planejador: decompor em tarefas com dependência

Duas tarefas sob a sessão `sess-sprint-01`, com a carga dependendo do parser. O `depende_de` só passa se não fechar ciclo, e só o planejador e o humano podem criá-lo. O exemplo é código; um relatório decomposto em levantar os números e redigir tem a mesma forma, com a redação dependendo do levantamento.

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

O planejador decide em cima do que leu, e o que leu entra como `Evidence` com o ponteiro inteiro. Quando a fonte é um arquivo (código, ata em Markdown, CSV), o ponteiro é `arquivo`, `linhas` e o `trecho` literal dessas linhas; sem um dos três o InvariantGate recusa com `evidencia_sem_localizacao`, e um trecho com mais linhas do que a faixa também cai. A outra forma, para o que não mora num arquivo com linhas, está na receita seguinte. A `Decision` diz onde vale por `orienta`, e é por essa aresta que ela chega à vista de quem executa a tarefa, mesmo que a tarefa tenha nascido noutra sessão.

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

## planejador: registrar o que leu numa fonte que não é arquivo

Página web, PDF, conversa: o ponteiro é `fonte` (a URL, o documento, ou a conversa com data e participantes), `local` opcional e livre (página, seção, minuto) e o `trecho` literal. Sem `trecho`, o lote cai com `evidencia_sem_localizacao`; `linhas` é de arquivo, e para página ou seção vale `local`.

```json
{
  "justificativa": "Indice de reajuste confirmado na fonte oficial",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/evi-ipca-setembro",
      "value": {
        "id": "evi-ipca-setembro",
        "tipo": "Evidence",
        "rotulo": "O IPCA acumulado em 12 meses ate setembro e 4,42%",
        "propriedades": {
          "fonte": "https://www.ibge.gov.br/indicadores/ipca",
          "local": "tabela de variacao acumulada em 12 meses, linha set/2026",
          "trecho": "set/2026 | 4,42",
          "relevancia": "e o indice que o contrato manda aplicar no reajuste"
        }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-evi-ipca-setembro",
      "value": { "id": "prod-evi-ipca-setembro", "origem_id": "sess-sprint-01", "destino_id": "evi-ipca-setembro", "tipo": "produz" }
    }
  ]
}
```

A `Decision` que essa leitura sustenta se liga como na receita anterior, por `justifica` e `orienta`.

## planejador: Task emergente com a ligação de escopo

Depois que o humano aprovou o plano do Goal, a Task nova diz de que nasceu. A emergente liga `motivada_por` ao que a motivou (aqui, a Evidence do achado) e leva `atende_criterio` com o id da Constraint `criterio_aceite` do Goal que ela atende; ela entra na hierarquia por `decompoe` e na sessão por `produz`. O `criar_tarefa` não recebe essas duas ligações, então a Task emergente vai por `propor_patch`. Sem um critério que ela atenda, não é Task: é proposta (receita seguinte).

```json
{
  "justificativa": "Task emergente: o achado mostra que o CSV perde o saldo negativo, criterio crit-relatorio-1",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/task-saldo-negativo",
      "value": {
        "id": "task-saldo-negativo",
        "tipo": "Task",
        "rotulo": "Exportar o saldo negativo com sinal no CSV",
        "propriedades": {
          "status": "pendente",
          "descricao": "A exportacao descarta o sinal dos saldos negativos (ver a Evidence).",
          "criterio_pronto": "Atende crit-relatorio-1: o CSV de teste com saldo de -150,00 traz -15000 na coluna de saldo; pytest tests/exportacao -q passa",
          "atende_criterio": "crit-relatorio-1"
        }
      }
    },
    {"op": "add", "path": "/arestas/prod-task-saldo-negativo", "value": {"id": "prod-task-saldo-negativo", "origem_id": "sess-01", "destino_id": "task-saldo-negativo", "tipo": "produz"}},
    {"op": "add", "path": "/arestas/dec-task-saldo-negativo", "value": {"id": "dec-task-saldo-negativo", "origem_id": "goal-relatorio", "destino_id": "task-saldo-negativo", "tipo": "decompoe"}},
    {"op": "add", "path": "/arestas/mot-task-saldo-negativo", "value": {"id": "mot-task-saldo-negativo", "origem_id": "task-saldo-negativo", "destino_id": "evi-saldo-sem-sinal", "tipo": "motivada_por"}}
  ]
}
```

As outras ligações seguem o mesmo molde, só mudando a aresta e o alvo: a correção usa a propriedade `corrige` com a Evidence rejeitada, o acompanhamento uma aresta `acompanha` para essa Evidence, a integração `integra` para a Task do mesmo Goal que tem Artifact, e a reversão `desfaz` para a Decision substituída. A Decision que o planejador cria depois do plano aprovado também leva `motivada_por`, para a cadeia "esta Decision gerou a Task, que gerou a Evidence, que gerou a Decision B" ter raiz.

## planejador: proposta fora do Goal

A descoberta que não atende a critério de aceite nenhum, ou que cruza a Constraint `fronteira`, vira uma Note, não uma Task nem uma Question. Ela nasce aberta (`status: aberta`, que também é o que vale na ausência), produzida pela sessão, e o humano a fecha com `aceita` ou `descartada`. O planejador não é dono de `deriva_de` (é de executor, revisor e humano), então o achado vai em `origens`; o executor e o revisor, que são donos, podem acrescentar a aresta `deriva_de` para a Evidence ou a Task.

```json
{
  "justificativa": "Achado fora dos criterios do goal: vira proposta para o humano",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/prop-cache-leitura",
      "value": {
        "id": "prop-cache-leitura",
        "tipo": "Note",
        "rotulo": "Cachear a leitura do relatorio mensal",
        "propriedades": {
          "acao": "proposta_fora_do_goal",
          "status": "aberta",
          "corpo": "A leitura repete a consulta a cada exportacao; um cache reduziria o tempo, mas nenhum criterio pede isso e a fronteira deixa a performance de fora.",
          "origens": ["evi-consulta-repetida"]
        }
      }
    },
    {"op": "add", "path": "/arestas/prod-prop-cache-leitura", "value": {"id": "prod-prop-cache-leitura", "origem_id": "sess-01", "destino_id": "prop-cache-leitura", "tipo": "produz"}}
  ]
}
```

O humano decide pela caixa de propostas do `graphow web` ou por um patch seu: `replace` em `/nos/prop-cache-leitura/propriedades/status` com `aceita` ou `descartada`. Aceitar não cria Task: o trabalho entra por um critério novo no Goal ou por outro Goal.

## humano: critérios de aceite e fronteira do Goal

Cada critério é uma Constraint com `tipo: criterio_aceite`, e o fora do escopo é uma só, com `tipo: fronteira`, todas com `escopa` para o Goal e `produz` da sessão. O lote completo, com o Goal, está na skill `graphow-gerente` (passo 4). A Task emergente cita o id do nó do critério, por isso vale um id legível.

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
          "arquivos": ["src/graphow/parsers/csv.py", "tests/test_csv_parser.py"],
          "resumo": "parser CSV com tratamento de erros de encoding e testes de unidade"
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

`arquivos` lista o que a entrega alterou e `resumo` diz em uma linha o que ela é. Num documento ou numa planilha, `arquivos` aponta o documento ou a planilha, e o resto do lote é igual. Quando a entrega é código, os testes que a provam entram em `arquivos` junto do código.

## executor: registrar a ação externa

Enviar um e-mail, marcar uma reunião, publicar: a Task entrega um gesto no mundo, não um arquivo. O planejador a cria com `entrega: acao_externa` e sem `arquivos_alvo`, e o critério diz o que prova o gesto:

```json
{
  "titulo": "Enviar o relatorio de fechamento de setembro a diretoria",
  "id_sessao": "sess-sprint-01",
  "criterio_pronto": "E-mail enviado a diretoria@ com o relatorio em anexo, registrado com data e hora do envio",
  "entrega": "acao_externa",
  "depende_de": "task-relatorio-fechamento"
}
```

Quem a executa é o gesto `acao_externa` da política: o humano, que é o padrão e o que vale em `governanca_maxima`, ou o executor, que é o que vale em `arbitragem_maxima` e o que a política personalizada pode escolher. Com o gesto no humano, o `assumir_tarefa` do executor é recusado; a pessoa faz o gesto, e a sessão humana registra a prova em nome dela. Com o gesto no executor, ele faz o gesto com as ferramentas que tem e registra a prova. O lote é o mesmo nos dois casos: um `Artifact` sem `arquivos`, com o `resumo` do que foi feito, e a `Evidence` de prova com `fonte` e `resultado`, ligada por `deriva_de` ao `Artifact` e à Task.

```json
{
  "justificativa": "Relatorio de setembro enviado a diretoria",
  "operacoes": [
    {
      "op": "add",
      "path": "/nos/art-envio-fechamento",
      "value": {
        "id": "art-envio-fechamento",
        "tipo": "Artifact",
        "rotulo": "Envio do relatorio de setembro a diretoria",
        "propriedades": { "resumo": "e-mail com o relatorio em anexo enviado a diretoria@" }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-art-envio-fechamento",
      "value": { "id": "prod-art-envio-fechamento", "origem_id": "sess-sprint-01", "destino_id": "art-envio-fechamento", "tipo": "produz" }
    },
    {
      "op": "add",
      "path": "/arestas/deriv-art-envio-task",
      "value": { "id": "deriv-art-envio-task", "origem_id": "art-envio-fechamento", "destino_id": "task-envio-fechamento", "tipo": "deriva_de" }
    },
    {
      "op": "add",
      "path": "/nos/evi-envio-fechamento",
      "value": {
        "id": "evi-envio-fechamento",
        "tipo": "Evidence",
        "rotulo": "E-mail do fechamento enviado",
        "propriedades": { "fonte": "caixa de saida", "resultado": "enviado 06/10 14:02 para diretoria@" }
      }
    },
    {
      "op": "add",
      "path": "/arestas/prod-evi-envio-fechamento",
      "value": { "id": "prod-evi-envio-fechamento", "origem_id": "sess-sprint-01", "destino_id": "evi-envio-fechamento", "tipo": "produz" }
    },
    {
      "op": "add",
      "path": "/arestas/deriv-evi-envio-art",
      "value": { "id": "deriv-evi-envio-art", "origem_id": "evi-envio-fechamento", "destino_id": "art-envio-fechamento", "tipo": "deriva_de" }
    },
    {
      "op": "add",
      "path": "/arestas/deriv-evi-envio-task",
      "value": { "id": "deriv-evi-envio-task", "origem_id": "evi-envio-fechamento", "destino_id": "task-envio-fechamento", "tipo": "deriva_de" }
    },
    {
      "op": "replace",
      "path": "/nos/task-envio-fechamento/propriedades/status",
      "value": "pronto_para_revisao"
    }
  ]
}
```

A `Evidence` de prova leva `fonte` sem `trecho`, e por isso passa livre: é registro de envio, não citação. O lote pede a posse da Task (`assumir_tarefa` antes, `liberar_tarefa` depois). Daí em diante o ciclo é o de sempre: o revisor julga se a fonte e o resultado batem com o critério, e o executor fecha a Task aprovada; a posse para fechar segue livre a ele mesmo com o gesto no humano.

## revisor: anexar a evidência da auditoria

O revisor registra o que verificou e para por aí. A `Evidence` aponta por `deriva_de` o artefato que avaliou e a tarefa, e o `veredito` diz se passou (`aprovado`) ou não (`rejeitado`, com o ponteiro que o prova, de arquivo ou de fonte). A verificação é o que prova o critério: quando a entrega é código, rodar os testes, como no exemplo; num texto, dado ou análise, ler o documento e conferir números e fontes; na ação externa, julgar se a `fonte` e o `resultado` da prova batem com o critério. Acrescentar `"value": "concluido"` ao status da tarefa neste mesmo lote derrubaria tudo com `violacao_permissao_papel`: fechar `Task` é de executor e humano, e o patch é atômico. A propriedade `veredito` também é só de quem julga (revisor, humano, árbitro): é ela que o kernel lê para deixar o executor concluir.

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

Quem fecha a tarefa depois é o executor que a detém, por `concluir_tarefa`, e só se o `aprovado` é o veredito mais recente da Task: com `rejeitado` vigente, o kernel recusa com `fechamento_sem_veredito_aprovado`, a menos que a correção aprovada o supere ou haja aceite legítimo pelo teto de correções.

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

Fora do código a dúvida tem a mesma forma: "A ata de 03/10 fala em reajuste de 5% e a planilha de custos em 4,5%: qual entra no relatório?".

O `titulo` é o rótulo do nó, e é o que o card mostra no canvas: mande uma linha. O corpo vai em `pergunta` e pode ser tão longo quanto a dúvida exigir. Sem `titulo`, ele é derivado do começo da pergunta — e uma pergunta de vinte linhas vira um título truncado.

Você abre a dúvida e espera em `aguardar_resposta`. Mover a `Question` para `respondida` ou `descartada`, removê-la ou tirar o `bloqueia` são operações do humano, ou do árbitro quando a política lhe entrega `responder_questao`, por qualquer caminho. Planejador, executor e revisor são recusados, e o árbitro não encerra a que ele mesmo abriu.

## revisor: condensar a sessão encerrada

A Task de condensar (`acao: condensar_sessao`) foi aberta pelo grafo quando a sessão `sess-sprint-01` encerrou. Depois de `assumir_tarefa` nela e de `ler_vista("sess-sprint-01")`, a condensação é uma `Note` produzida pela sessão, com `deriva_de` para cada nó de onde saiu uma afirmação do corpo. Sem o `produz`, a Note nasce fora da hierarquia; sem os `deriva_de`, é opinião sem origem. O exemplo condensa a cadeia de código acima; a de um relatório ou de uma ação externa se condensa igual, com `deriva_de` para o `Artifact` e a `Evidence` de prova.

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

## revisor: consolidar aprendizados acumulados

A Task de consolidar (`acao: consolidar_aprendizados`) foi aberta pelo grafo quando uma sessão abriu num alcance com mais de doze aprendizados vigentes; a descrição lista os ids. Consolidar não é patch: é `registrar_aprendizado` por tema, que monta o `produz`, os `deriva_de` e os `substitui` no mesmo lote.

```json
{
  "afirmacao": "Toda escrita fora do PatchBoard nasce com aresta de contencao no mesmo lote",
  "como_aplicar": "No canal de execucao e em qualquer comportamento reativo, crie produz ou contem junto do no; o InvariantGate nao ve esses canais",
  "id_sessao": "sess-sprint-02",
  "origens": ["evi-runs-fora-da-hierarquia", "dec-run-pendurado-na-sessao", "evi-nota-orfa"],
  "substitui": ["apr-run-sem-aresta", "apr-nota-reativa-orfa"]
}
```

Os dois absorvidos ficam no grafo, marcados com `SUBSTITUTO PENDENTE` na vista, até o humano, ou o árbitro quando a política lhe entrega `promover_aprendizado`, promover o consolidado; só então saem dela. Depois, o revisor move a Task para `pronto_para_revisao` e libera a posse, como na condensação.
