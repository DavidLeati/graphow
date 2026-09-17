"""Definições formais de schemas para ferramentas MCP expostas a agentes LLM."""

from typing import Any

DEFINICOES_FERRAMENTAS_MCP: list[dict[str, Any]] = [
    {
        "name": "ler_vista",
        "description": "Materializa uma vista de contexto do subgrafo com orçamento estrito de tokens. Num contêiner (Projeto, Setor, Sessao) a vista traz o panorama agregado dos filhos — quantas tarefas fecharam, quantas seguem abertas — em vez de listar a subárvore. Comece pelo Projeto e desça só onde houver trabalho aberto.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_alvo": {"type": "string", "description": "ID do nó alvo a ser inspecionado."},
                "orcamento_tokens": {"type": "integer", "default": 1500, "description": "Limite máximo de tokens da vista."},
                "escopo": {"type": "string", "enum": ["tudo", "ativo"], "default": "tudo", "description": "'ativo' poda a navegação para o que está perto de trabalho não concluído. O padrão é 'tudo': Decision e Evidence são a memória que evita re-decidir, e escondê-las por default custa mais do que economiza."},
                "raio_do_escopo": {"type": "integer", "default": 1, "description": "Saltos a partir do trabalho aberto quando escopo='ativo'. Acima de 1 o recorte cresce rápido."},
            },
            "required": ["id_alvo"],
        },
    },
    {
        "name": "expandir_no",
        "description": "Obtém detalhes completos e arestas incidentes de um nó específico sob demanda.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_no": {"type": "string", "description": "ID do nó a ser expandido."},
            },
            "required": ["id_no"],
        },
    },
    {
        "name": "propor_patch",
        "description": "Propõe mutações no estado compartilhado via JSON Patch RFC 6902 com validação atômica. Todo nó criado, exceto Projeto, precisa no mesmo lote de uma aresta de contenção chegando nele (produz vinda da Sessao, ou decompoe); sem ela o lote é recusado com no_fora_da_hierarquia.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operacoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {"type": "string", "enum": ["add", "remove", "replace", "move", "copy", "test"]},
                            "path": {"type": "string"},
                            "value": {},
                        },
                        "required": ["op", "path"],
                    },
                    "description": "Lista de operações JSON Patch.",
                },
                "justificativa": {"type": "string", "description": "Motivo da alteração proposta."},
                "ramo_id": {"type": "string", "default": "main", "description": "Ramo do grafo."},
            },
            "required": ["operacoes", "justificativa"],
        },
    },
    {
        "name": "abrir_questao",
        "description": "Abre um nó Question que bloqueia uma Task até que o humano responda. Nenhum papel de agente encerra uma dúvida: use 'aguardar_resposta' para saber quando ela foi respondida.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "titulo": {
                    "type": "string",
                    "description": "Título curto da dúvida, uma linha: é o que o card mostra no canvas. Omitido, é derivado do começo da pergunta.",
                },
                "pergunta": {"type": "string", "description": "Corpo da dúvida: o contexto e a ambiguidade, por extenso."},
                "id_no_bloqueado": {"type": "string", "description": "ID da Task a ser bloqueada."},
                "id_sessao": {"type": "string", "description": "ID da sessão onde a questão é criada."},
            },
            "required": ["pergunta", "id_no_bloqueado", "id_sessao"],
        },
    },
    {
        "name": "proximas_tarefas",
        "description": "Lista as tarefas executáveis de uma sessão (dependências concluídas, sem dúvida aberta, sem posse de outro agente) e, em 'impedidas', o que ficou de fora com o motivo de cada exclusão.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_sessao": {"type": "string", "description": "ID da Sessão cuja fila de trabalho será consultada."},
            },
            "required": ["id_sessao"],
        },
    },
    {
        "name": "assumir_tarefa",
        "description": "Adquire a posse exclusiva de uma Task e a move para 'em_andamento'. Exigido antes de qualquer mudança de status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_task": {"type": "string", "description": "ID da Task a assumir."},
            },
            "required": ["id_task"],
        },
    },
    {
        "name": "liberar_tarefa",
        "description": "Devolve a posse de uma Task assumida por esta sessão, sem alterar o status registrado.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_task": {"type": "string", "description": "ID da Task a liberar."},
            },
            "required": ["id_task"],
        },
    },
    {
        "name": "minhas_questoes",
        "description": "Lista as dúvidas abertas por esta sessão, com a resposta humana quando já houver.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["aberta", "respondida", "descartada"], "description": "Filtro opcional por status da dúvida."},
            },
        },
    },
    {
        "name": "aguardar_resposta",
        "description": "Bloqueia até que o humano encerre a dúvida indicada, ou até o prazo expirar. Substitui o polling manual.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_questao": {"type": "string", "description": "ID da Question a aguardar."},
                "timeout_segundos": {"type": "number", "default": 30, "description": "Prazo máximo de espera, limitado a 300 segundos."},
            },
            "required": ["id_questao"],
        },
    },
    {
        "name": "buscar",
        "description": "Busca textual ranqueada sobre rótulos e propriedades. Devolve os melhores resultados em linha esquelética (id, tipo, rótulo, posição no log), junto de 'total' e 'truncado' para você saber se vale refinar o termo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "termo": {"type": "string", "description": "Termo a pesquisar."},
                "tipos_no": {"type": "array", "items": {"type": "string"}, "description": "Filtro de tipos de nó."},
                "limite": {"type": "integer", "default": 5, "description": "Quantos resultados devolver, no máximo 50. Casamento no rótulo vence casamento em propriedade, palavra inteira vence prefixo, e o que está aberto vence o que foi encerrado."},
                "escopo": {"type": "string", "enum": ["tudo", "ativo"], "default": "tudo", "description": "'ativo' restringe a busca ao que está perto de trabalho não concluído."},
                "raio_do_escopo": {"type": "integer", "default": 1, "description": "Saltos a partir do trabalho aberto quando escopo='ativo'."},
            },
            "required": ["termo"],
        },
    },
    {
        "name": "criar_projeto",
        "description": "Cria um nó de Projeto raiz configurando o nível de autonomia dos agentes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rotulo": {"type": "string", "description": "Nome ou título do projeto."},
                "descricao": {"type": "string", "default": "", "description": "Descrição do projeto."},
                "nivel_autonomia": {"type": "string", "enum": ["estrito", "ilimitado"], "default": "estrito", "description": "Amplia os tipos de nó que agentes podem criar dentro do projeto. Nunca concede Constraint, encerramento de dúvida nem a camada de arestas do humano."},
            },
            "required": ["rotulo"],
        },
    },
    {
        "name": "criar_setor",
        "description": "Cria um nó de Setor vinculado a um Projeto existente.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rotulo": {"type": "string", "description": "Nome do setor (ex: Engenharia, Produto)."},
                "id_projeto": {"type": "string", "description": "ID do Projeto pai."},
            },
            "required": ["rotulo", "id_projeto"],
        },
    },
    {
        "name": "criar_sessao",
        "description": "Cria um nó de Sessão vinculado a um Setor existente.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rotulo": {"type": "string", "description": "Nome da sessão (ex: Sprint 1, Refactor)."},
                "id_setor": {"type": "string", "description": "ID do Setor pai."},
            },
            "required": ["rotulo", "id_setor"],
        },
    },
    {
        "name": "criar_tarefa",
        "description": "Cria uma nova Task executável vinculada a uma Sessão com suporte a decomposição e dependência.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Título da tarefa."},
                "id_sessao": {"type": "string", "description": "ID da Sessão onde a tarefa é criada."},
                "descricao": {"type": "string", "default": "", "description": "Descrição detalhada da tarefa."},
                "criterio_pronto": {"type": "string", "default": "", "description": "Critério de aceitação/pronto."},
                "id_tarefa_pai": {"type": "string", "description": "ID de Task pai caso seja uma sub-tarefa (decompoe)."},
                "depende_de": {"type": "string", "description": "ID de Task pré-requisito (depende_de)."},
            },
            "required": ["titulo", "id_sessao"],
        },
    },
    {
        "name": "responder_questao",
        "description": "Responde e resolve um nó Question, destravando tarefas que estavam bloqueadas por ele.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_questao": {"type": "string", "description": "ID da Question a ser respondida."},
                "resposta": {"type": "string", "description": "Conteúdo da resposta ou decisão esclarecedora."},
            },
            "required": ["id_questao", "resposta"],
        },
    },
    {
        "name": "concluir_tarefa",
        "description": "Marca uma Task como concluída no grafo após verificação de ausência de dúvidas bloqueantes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_task": {"type": "string", "description": "ID da Task a ser concluída."},
                "justificativa": {"type": "string", "default": "Conclusão da tarefa", "description": "Justificativa da conclusão."},
            },
            "required": ["id_task"],
        },
    },
    {
        "name": "configurar_autonomia_projeto",
        "description": "Altera o nível de permissividade e autonomia concedido a agentes em um projeto.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_projeto": {"type": "string", "description": "ID do Projeto."},
                "nivel_autonomia": {"type": "string", "enum": ["estrito", "ilimitado"], "description": "Novo nível de autonomia."},
            },
            "required": ["id_projeto", "nivel_autonomia"],
        },
    },
    {
        "name": "excluir_em_lote",
        "description": "Remove múltiplos nós e arestas do grafo em uma única operação atômica.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ids_nos": {"type": "array", "items": {"type": "string"}, "default": [], "description": "Lista de IDs de nós a remover."},
                "ids_arestas": {"type": "array", "items": {"type": "string"}, "default": [], "description": "Lista de IDs de arestas a remover."},
                "justificativa": {"type": "string", "default": "Exclusão em lote", "description": "Motivo da exclusão."},
            },
        },
    },
    {
        "name": "encerrar_sessao",
        "description": "Encerra uma Sessao: grava status 'concluida' e o resumo opcional. A partir dai a vista da sessao abre pelo fechamento deterministico (decisoes vigentes, duvidas abertas, restricoes, ultimo artefato) e o motor reativo abre a Task de condensacao. Somente sessao humana; o harness encerra pelo hook de fim.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_sessao": {"type": "string", "description": "ID da Sessao a encerrar."},
                "resumo": {"type": "string", "default": "", "description": "Resumo declarado por quem encerra, guardado na propriedade 'resumo'."},
            },
            "required": ["id_sessao"],
        },
    },
    {
        "name": "registrar_aprendizado",
        "description": "Registra um Aprendizado: o que sobrevive ao projeto, com a afirmacao numa linha, como aplicar e os ids de origem. Nasce pendurado na sessao e aponta por deriva_de para cada origem; sem origem o InvariantGate recusa com aprendizado_sem_origem. So o humano promove (promover_aprendizado); ate la o aprendizado vale so onde nasceu.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "afirmacao": {"type": "string", "description": "A licao em uma linha: e o rotulo do no."},
                "como_aplicar": {"type": "string", "default": "", "description": "O que fazer com isto na proxima vez."},
                "id_sessao": {"type": "string", "description": "ID da Sessao que destilou o aprendizado."},
                "origens": {"type": "array", "items": {"type": "string"}, "description": "IDs das Evidence, Decision, Note, Artifact ou Task de onde o aprendizado saiu. Ao menos um."},
            },
            "required": ["afirmacao", "id_sessao", "origens"],
        },
    },
    {
        "name": "promover_aprendizado",
        "description": "Da alcance a um Aprendizado: aresta vale_para um Projeto ou Setor, ou a marca 'alcance: global' para valer em todo projeto. A partir dai ele entra na secao Aprendizados Aplicaveis da vista de qualquer tarefa sob esse alcance. Somente sessao humana.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_aprendizado": {"type": "string", "description": "ID do Aprendizado a promover."},
                "id_alvo": {"type": "string", "description": "ID do Projeto ou Setor onde o aprendizado passa a valer."},
                "global": {"type": "boolean", "default": False, "description": "Vale para todo projeto, sem conteiner ficticio na hierarquia."},
            },
            "required": ["id_aprendizado"],
        },
    },
    {
        "name": "excluir_projeto",
        "description": "Remove um projeto e opcionalmente todos os seus setores, sessões e nós em cascata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_projeto": {"type": "string", "description": "ID do Projeto a ser removido."},
                "cascata": {"type": "boolean", "default": True, "description": "Se verdadeiro, remove também todos os setores, sessões e tarefas descendentes."},
            },
            "required": ["id_projeto"],
        },
    },
]
