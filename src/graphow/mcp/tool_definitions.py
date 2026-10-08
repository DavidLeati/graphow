"""Definições formais de schemas para ferramentas MCP expostas a agentes LLM."""

from typing import Any

DEFINICOES_FERRAMENTAS_MCP: list[dict[str, Any]] = [
    {
        "name": "ler_vista",
        "description": "Materializa uma vista de contexto do subgrafo com orçamento estrito de tokens. Num contêiner (Projeto, Setor, Sessao) a vista traz o panorama agregado dos filhos — quantas tarefas fecharam, quantas seguem abertas — em vez de listar a subárvore. Comece pelo Projeto e desça só onde houver trabalho aberto. Numa Sessao é o primeiro passo do trabalho: a vista traz a seção 'Aprendizados Aplicaveis', com o que outras sessões já aprenderam, e, se a sessão está encerrada, o fechamento dela.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_alvo": {"type": "string", "description": "ID do nó alvo a ser inspecionado."},
                "orcamento_tokens": {"type": "integer", "default": 1500, "description": "Limite máximo de tokens da vista."},
                "escopo": {"type": "string", "enum": ["tudo", "ativo"], "default": "tudo", "description": "'ativo' poda a navegação para o que está perto de trabalho não concluído. O padrão é 'tudo': Decision e Evidence são a memória que evita re-decidir, e escondê-las por default custa mais do que economiza."},
                "raio_do_escopo": {"type": "integer", "default": 1, "description": "Saltos a partir do trabalho aberto quando escopo='ativo'. Acima de 1 o recorte cresce rápido."},
                "perspectiva": {"type": "string", "enum": ["planejador", "executor", "revisor"], "description": "Lê o alvo como esse papel o lê; omitida, vale o papel da sessão. É o teste do executor frio: antes de despachar uma Task, leia-a com perspectiva='executor' e pergunte se quem nunca viu a conversa a executaria só com aquilo."},
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
        "description": "Propõe mutações no estado compartilhado via JSON Patch RFC 6902 com validação atômica. Todo nó criado, exceto Projeto, precisa no mesmo lote de uma aresta de contenção chegando nele (produz vinda da Sessao, ou decompoe); sem ela o lote é recusado com no_fora_da_hierarquia. Formas aceitas: add e remove em /nos/<id> e /arestas/<id>, add e replace em /nos/<id>/rotulo, add, replace e remove em /nos/<id>/propriedades/<chave>; o resto volta com caminho_invalido. add só cria: o id do caminho é o do campo id do valor e não pode existir ainda (elemento_ja_existente); para editar um nó, use replace no rótulo ou numa propriedade. É por aqui que o trabalho vira memória: registre Evidence (fato observado: leitura, fonte consultada, saída de verificação) e Decision (escolha com motivo) produzidas pela sessão assim que acontecem, não só no fim; é delas que o fechamento, a condensação e o Aprendizado saem.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operacoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {"type": "string", "enum": ["add", "remove", "replace"]},
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
        "description": "Abre um nó Question que bloqueia uma Task até que o humano, ou o árbitro quando a política de governança do projeto lhe entrega o gesto responder_questao, a responda. Planejador, executor e revisor nunca encerram uma dúvida, nem a que abriram: use 'aguardar_resposta' para saber quando ela foi respondida.",
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
        "description": "Lista as tarefas executáveis de uma sessão ou de um Goal (dependências concluídas, sem dúvida aberta, sem posse de outro agente) e, em 'impedidas', o que ficou de fora com o motivo de cada exclusão. Cada tarefa traz modelo, trilha, entrega, arquivos_alvo e criterio_pronto: só rodam em paralelo tarefas com arquivos_alvo disjuntos, e a de entrega acao_externa é do humano, salvo quando a política entrega o gesto acao_externa ao executor. Na correção, corrige traz a Evidence do veredito que a motivou, e profundidade_correcao conta as correções na cadeia até a original: 0 na original, 1 na primeira correção, 2 na correção de uma correção. Em Goal com plano aprovado, o que está em voo vem antes e as pendentes seguem a faixa de escopo (campo faixa, com a classe em escopo): 1 o plano vigente e as subdivisões, 2 o que o humano criou e o que o plano pede por depende_de, 3 o resto; só reordena, não bloqueia.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_sessao": {"type": "string", "description": "ID da Sessão, ou do Goal, cuja fila de trabalho será consultada. Num Goal, a fila percorre a decomposição dele, de qualquer sessão."},
            },
            "required": ["id_sessao"],
        },
    },
    {
        "name": "assumir_tarefa",
        "description": "Adquire a posse exclusiva de uma Task e a move para 'em_andamento'. Exigido antes de qualquer mudança de status. Posse de outro autor recusa, salvo para o executor numa Task cujo veredito de revisão vigente é 'aprovado': ele retoma a posse órfã para fechá-la, e o recibo diz de quem em 'posse_retomada_de'.",
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
        "description": "Devolve a posse de uma Task assumida por esta sessão, sem alterar o status registrado. Libere antes de terminar: a posse de um subagente que acabou sem liberar trava a tarefa até quem pode devolver a posse de outro autor por esta mesma ferramenta: o humano, ou o árbitro quando a política do projeto lhe entrega o gesto liberar_posse_alheia.",
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
        "description": "Lista as dúvidas abertas por esta sessão, com a resposta (do humano ou do árbitro) quando já houver.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["aberta", "respondida", "descartada"], "description": "Filtro opcional por status da dúvida."},
            },
        },
    },
    {
        "name": "aguardar_resposta",
        "description": "Bloqueia até que a dúvida indicada seja encerrada (pelo humano ou pelo árbitro), ou até o prazo expirar. Substitui o polling manual.",
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
                "nivel_autonomia": {"type": "string", "enum": ["estrito", "ilimitado"], "default": "estrito", "description": "Amplia os tipos de nó que agentes podem criar dentro do projeto. É o campo legado da política de governança (o gesto estrutura); nunca concede, por si, Constraint, encerramento de dúvida nem a camada de arestas do humano."},
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
                "rotulo": {"type": "string", "description": "Nome do setor (ex: Engenharia, Pesquisa, Comercial)."},
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
                "rotulo": {"type": "string", "description": "Nome da sessão (ex: Sprint 1, Levantamento de fornecedores)."},
                "id_setor": {"type": "string", "description": "ID do Setor pai."},
            },
            "required": ["rotulo", "id_setor"],
        },
    },
    {
        "name": "criar_tarefa",
        "description": "Cria uma nova Task executável vinculada a uma Sessão com suporte a decomposição e dependência. Para a orquestração, grava também o modelo que a executa (com o motivo), a trilha, a entrega, os arquivos que ela toca e as decisões que a orientam.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Título da tarefa."},
                "id_sessao": {"type": "string", "description": "ID da Sessão onde a tarefa é criada."},
                "descricao": {"type": "string", "default": "", "description": "Descrição detalhada da tarefa."},
                "criterio_pronto": {"type": "string", "default": "", "description": "Critério de aceitação/pronto: é contra ele que o revisor julga."},
                "id_tarefa_pai": {"type": "string", "description": "ID de Task pai caso seja uma sub-tarefa (decompoe). Na tarefa de correção, a tarefa que a revisão rejeitou."},
                "depende_de": {"type": "string", "description": "ID de Task pré-requisito (depende_de)."},
                "modelo": {"type": "string", "description": "Modelo que deve executar a tarefa, como 'sonnet' ou 'opus'. Exige motivo_modelo: a escolha fica auditável no log."},
                "motivo_modelo": {"type": "string", "description": "Por que este modelo: julgamento de domínio, mudança que atravessa várias partes do trabalho, tarefa que já falhou uma revisão."},
                "trilha": {"type": "string", "enum": ["leve", "completa"], "description": "Trilha da tarefa. 'leve' só para tarefa trivial de texto (redação, revisão de texto, comentário ou documentação), sem mudança com efeito em código, dado ou configuração: pula o teste do executor frio e vai ao revisor Sonnet. Recusada com modelo opus. Ausente vale 'completa'."},
                "entrega": {"type": "string", "enum": ["artefato", "acao_externa"], "description": "O que a tarefa entrega. 'artefato' (padrão): arquivo, documento ou dado. 'acao_externa': um gesto no mundo que não deixa arquivo, como enviar um e-mail ou marcar uma reunião; o gesto acao_externa da política decide se é do humano (padrão) ou do executor, e a prova vai numa Evidence com fonte e resultado."},
                "arquivos_alvo": {"type": "array", "items": {"type": "string"}, "description": "Arquivos que a tarefa vai tocar, relativos à raiz do trabalho (código, documentos, planilhas). Só rodam em paralelo tarefas com arquivos_alvo disjuntos; a de ação externa não leva."},
                "decisoes": {"type": "array", "items": {"type": "string"}, "description": "IDs das Decision que valem para esta tarefa. Cada uma ganha a aresta orienta, que é por onde o executor as encontra."},
                "corrige": {"type": "string", "description": "Na tarefa de correção, o id da Evidence de revisão rejeitada que a motivou. Com id_tarefa_pai, a tarefa rejeitada passa a depender da correção e sai da fila até ela fechar."},
            },
            "required": ["titulo", "id_sessao"],
        },
    },
    {
        "name": "responder_questao",
        "description": "Responde e resolve um nó Question, destravando tarefas que estavam bloqueadas por ele. É o gesto responder_questao da política de governança: do humano, ou do árbitro quando a política do projeto da Question o entrega; planejador, executor e revisor são recusados. O árbitro não responde a Question que ele mesmo abriu. Grava respondida_por e respondida_por_papel.",
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
        "description": "Legado: altera o nivel_autonomia de um projeto (estrito ou ilimitado), que a política de governança lê como o gesto estrutura. Segue funcionando, mas o caminho novo é configurar_governanca. Sempre do humano.",
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
        "name": "configurar_governanca",
        "description": "Grava a política de governança, que decide quem exerce cada gesto antes só do humano (responder_questao, promover_aprendizado, constraint, estrutura, excluir, fechar_goal, encerrar_sessao, liberar_posse_alheia, integracao, aprovar_plano, responder_desvio, max_correcoes, limiar_desvio_por_raiz, limiar_desvio_por_goal, teto_expansao, acao_externa): o humano, ou o árbitro; na acao_externa, o humano ou o executor. Os gestos aprovar_plano e responder_desvio são do escopo governado: o responder_desvio é do humano em qualquer preset fixo. As leituras max_correcoes, limiar_desvio_por_raiz, limiar_desvio_por_goal e teto_expansao são números. É o caminho novo, que substitui configurar_autonomia_projeto. Sempre do humano: nenhum papel de agente, árbitro inclusive, a configura. Presets: governanca_maxima e arbitragem_maxima são fixos; só a personalizada é editável, e ela fica sempre guardada à parte, sem ser apagada ao trocar de preset. escopo 'global' grava o nó governanca-global (criado se não existir); o id de um Projeto grava a política dele, em que a personalizada é parcial e o gesto ausente herda a global. Devolve a política efetiva resultante e a origem de cada gesto.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "escopo": {"type": "string", "description": "'global' ou o ID de um Projeto."},
                "preset": {"type": "string", "enum": ["governanca_maxima", "arbitragem_maxima", "personalizada", "herdar"], "description": "No escopo global: governanca_maxima, arbitragem_maxima ou personalizada. Num Projeto também 'herdar', que vale a política global."},
                "personalizada": {"type": "object", "description": "Opcional: gesto -> valor ('humano' ou 'arbitro'; estrutura: 'estrito' ou 'ilimitado'; max_correcoes: inteiro de 0 a 5; limiar_desvio_por_raiz: inteiro de 1 a 50; limiar_desvio_por_goal: inteiro de 1 a 200; teto_expansao: inteiro de 0 a 500, 0 desliga; acao_externa: 'humano' ou 'executor'). É mesclada na personalizada já salva. Num Projeto, o valor 'herdar' apaga a sobrescrita do gesto."},
            },
            "required": ["escopo", "preset"],
        },
    },
    {
        "name": "excluir_em_lote",
        "description": "Remove múltiplos nós e arestas do grafo em uma única operação atômica. É o gesto excluir da política de governança: do humano, ou do árbitro quando a política de todos os alvos o entrega; os demais papéis são recusados.",
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
        "description": "Encerra uma Sessao: grava status 'concluida' e o resumo opcional. A partir dai a vista da sessao abre pelo fechamento deterministico (decisoes vigentes, duvidas abertas, restricoes, ultimo artefato) e o motor reativo abre a Task de condensacao. E o gesto encerrar_sessao da politica de governanca: do humano, ou do arbitro quando a politica do projeto da sessao o entrega; planejador, executor e revisor sao recusados. O harness encerra pelo hook de fim.",
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
        "description": "Chame antes de terminar, para cada lição que vale além desta sessão. Registra um Aprendizado: o que sobrevive ao projeto, com a afirmacao numa linha, como aplicar e os ids de origem. Nasce pendurado na sessao e aponta por deriva_de para cada origem; sem origem o InvariantGate recusa com aprendizado_sem_origem. Promover (promover_aprendizado) e do humano, ou do arbitro quando a politica do projeto o entrega, e a promocao global e sempre do humano; ate la o aprendizado vale so onde nasceu. Para consolidar (Task de acao consolidar_aprendizados), passe em substitui os ids dos Aprendizados absorvidos: a aresta substitui nasce no mesmo lote, e o absorvido sai da vista quando o consolidado for promovido.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "afirmacao": {"type": "string", "description": "A licao em uma linha: e o rotulo do no."},
                "como_aplicar": {"type": "string", "default": "", "description": "O que fazer com isto na proxima vez."},
                "id_sessao": {"type": "string", "description": "ID da Sessao que destilou o aprendizado."},
                "origens": {"type": "array", "items": {"type": "string"}, "description": "IDs das Evidence, Decision, Note, Artifact ou Task de onde o aprendizado saiu. Ao menos um."},
                "substitui": {"type": "array", "items": {"type": "string"}, "default": [], "description": "IDs dos Aprendizados que este consolida e substitui. O absorvido fica no grafo e sai da vista quando este for promovido."},
            },
            "required": ["afirmacao", "id_sessao", "origens"],
        },
    },
    {
        "name": "promover_aprendizado",
        "description": "Da alcance a um Aprendizado: aresta vale_para um Projeto ou Setor, ou a marca 'alcance: global' para valer em todo projeto. A partir dai ele entra na secao Aprendizados Aplicaveis da vista de qualquer tarefa sob esse alcance. E o gesto promover_aprendizado da politica de governanca: do humano, ou do arbitro quando a politica do projeto o entrega (o arbitro nao promove o aprendizado que ele mesmo registrou); com global=true e sempre o humano; planejador, executor e revisor sao recusados. Grava promovido_por e promovido_por_papel. Sem id_alvo nem global, promove ao Setor da sessao que o produziu, que e o alcance padrao: reserve o Projeto para o que vale em toda tarefa dele, e global para o que vale em qualquer projeto.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_aprendizado": {"type": "string", "description": "ID do Aprendizado a promover."},
                "id_alvo": {"type": "string", "description": "ID do Projeto ou Setor onde o aprendizado passa a valer. Omitido, e sem global, vale o Setor da sessao de origem."},
                "global": {"type": "boolean", "default": False, "description": "Vale para todo projeto, sem conteiner ficticio na hierarquia."},
            },
            "required": ["id_aprendizado"],
        },
    },
    {
        "name": "excluir_projeto",
        "description": "Remove um projeto e opcionalmente todos os seus setores, sessões e nós em cascata. É o gesto excluir da política de governança: do humano, ou do árbitro quando a política do projeto o entrega; os demais papéis são recusados.",
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
