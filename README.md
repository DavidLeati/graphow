# Graphow 🌐

> **Substrato Bilateral de Grafo Agêntico para Coordenação Humano-IA**  
> *Common Ground compartilhado, governança em 4 portões (PatchBoard), log append-only determinístico (ActiveGraph) e divulgação progressiva com orçamento de tokens.*

---

## 📌 Visão Geral

O **Graphow** é uma plataforma de estado compartilhado (*common ground*) que atua como substrato bilateral para coordenação estruturada entre desenvolvedores humanos e agentes autônomos de Inteligência Artificial (Planejadores, Executores, Revisores).

A arquitetura do Graphow é fundamentada em quatro pilares inegociáveis:
1. **O Log é a Verdade (*ActiveGraph*):** Event store *append-only* bitemporal (SQLite local-first ou memória); o grafo é uma projeção puramente determinística e reconstruível do zero absoluto via *event replay*.
2. **Caminho Único de Escrita (*PatchBoard*):** Humanos e IAs submetem mutações utilizando o mesmo protocolo JSON Patch ([RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902)), avaliado rigorosamente por um **Kernel de 4 Portões**.
3. **Divulgação Progressiva (*Progressive Disclosure*):** Agentes de IA consom recortes de contexto otimizados sob orçamento estrito de tokens, expandindo nós vizinhos sob demanda.
4. **Linhagem Causal e Reversibilidade:** Rastreabilidade reversa integral do `Artifact` até a intenção raiz (`Goal`), com ramificações históricas (*forks*) registradas como ponteiro `(ramo_base, seq_corte)`, sem cópia de prefixo.

---

## 🏛️ Arquitetura do Sistema

```
  ┌────────────────────────────────────────────────────────┐
  │                 HUMANO (Canvas / REST / CLI)            │
  └──────────────────────────┬─────────────────────────────┘
                             │ Proposta JSON Patch (RFC 6902)
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │                 AGENTE IA (MCP Server)                 │
  └──────────────────────────┬─────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │             KERNEL DE ESCRITA EM 4 PORTÕES             │
  │  1. SchemaGate     -> Validação Ontológica e Tipos     │
  │  2. RoleGate       -> Contratos de Permissão por Papel │
  │  3. InvariantGate  -> Ciclos DAG, Locks e Bloqueios    │
  │  4. WriteKernel    -> Transação Atômica & Commit       │
  └──────────────────────────┬─────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │            EVENT STORE APPEND-ONLY (SQLite)            │
  └──────────────────────────┬─────────────────────────────┘
                             │
                 ┌───────────┴───────────┐
                 ▼                       ▼
   ┌───────────────────────────┐   ┌───────────────────────────┐
   │    PROJEÇÃO EM MEMÓRIA    │   │      MOTOR REATIVO        │
   │  (GrafoReducer & View)    │   │  (Revisões, Alertas, Run) │
   └───────────────────────────┘   └───────────────────────────┘
```

---

## 🧩 Ontologia Formal em Duas Camadas

O Graphow adota uma ontologia formal rígida (detalhada na [Especificação Ontológica](docs/ONTOLOGY.md)) que separa navegação espacial do trabalho executivo:

### 1. Camada de Navegação (Containers Hierárquicos)
- **`Projeto`**: Raiz macro da iniciativa.
- **`Setor`**: Domínio ou subsistema técnico/funcional.
- **`Sessao`**: Janela de contexto temporal e transacional.

### 2. Camada de Trabalho (Grafo de Intenção e Execução)
- **`Goal`**: Intenção ou objetivo de alto nível.
- **`Task`**: Unidade atômica de trabalho técnico.
- **`Decision`**: Decisão arquitetural ou técnica aprovada.
- **`Question`**: Dúvida ou ambiguidade que **bloqueia** uma tarefa.
- **`Constraint`**: Restrição inviolável que escopa objetivos e tarefas.
- **`Artifact`**: Entregável concreto de código, documento ou configuração.
- **`Evidence`**: Dado empírico, benchmark ou prova que justifica decisões.
- **`Run`**: Registro de execução e telemetria de um modelo de IA.
- **`Note`**: Anotação livre, aviso reativo ou contexto efêmero.

### 3. Matriz de Arestas Permitidas (11 Tipos)

Cada tipo de aresta tem **dono declarado**, e criar não é o mesmo poder que
remover: qualquer agente abre uma escalação com `bloqueia`, e só o humano a
retira. A tabela vive em `kernel/matriz_papeis.py`, o `RoleGate` a aplica no
portão, e um teste de estrutura confere que nenhum tipo ficou sem dono.

| Tipo de Aresta | Par Permitido (Origem $\rightarrow$ Destino) | Quem cria / quem remove | Semântica |
| :--- | :--- | :--- | :--- |
| **`contem`** | `Projeto` $\rightarrow$ `Setor`, `Setor` $\rightarrow$ `Sessao` | humano, sistema / humano | Hierarquia estrutural de navegação. |
| **`produz`** | `Sessao` $\rightarrow$ Nós de Trabalho | todos / humano | Criação de itens de trabalho no escopo da sessão. |
| **`ocorreu_em`** | `Run` $\rightarrow$ `Sessao` | humano, sistema / humano, sistema | Associação de execução agêntica à sessão. |
| **`decompoe`** | `Goal` $\rightarrow$ `Task`, `Task` $\rightarrow$ `Task` | humano, planejador | Decomposição hierárquica de tarefas. |
| **`depende_de`** | `Task` $\rightarrow$ `Task` | humano, planejador | Pré-requisito de execução (DAG acíclico estrito). |
| **`bloqueia`** | `Question` $\rightarrow$ `Task` | todos / **humano** | Bloqueia a conclusão da tarefa até resolução humana. |
| **`justifica`** | `Evidence` $\rightarrow$ `Decision` | humano, executor, revisor | Fundamentação empírica de decisões. |
| **`contradiz`** | `Evidence` $\rightarrow$ `Decision` / `Evidence` | humano, executor, revisor | Registro de evidência conflitante. |
| **`substitui`** | `Decision` $\rightarrow$ `Decision`, `Task` $\rightarrow$ `Task` | humano, planejador | Evolução e invalidação histórica. |
| **`escopa`** | `Constraint` $\rightarrow$ `Goal` / `Task` | **humano** | Restrição mandatória sobre a execução. |
| **`deriva_de`** | `Artifact`/`Note` $\rightarrow$ `Task` / `Artifact` / `Decision` | humano, executor, revisor | Proveniência de artefatos e de notas reativas. |

---

## 🛡️ Os 4 Portões de Governança (PatchBoard)

Toda mutação no grafo (seja humana ou de IA) é submetida via JSON Patch RFC 6902 e processada sequencialmente:

1. **Portão 1 — `SchemaGate`:** Sanitização estrita contra *prototype pollution* (`__proto__`, `constructor`, `__class__`), checagem de tipos e validação da tabela ontológica de pares válidos de arestas.
2. **Portão 2 — `RoleGate`:** Matriz de permissões por papel, aplicada sobre a identidade da *conexão*, nunca sobre um campo do payload:
   - **`humano`**: Acesso irrestrito (único autorizado a criar/editar `Constraint`, encerrar uma `Question` e estruturar a camada de navegação).
   - **`planejador`**: Cria `Task`, `Decision`, `Question`, `Note`; decompõe e ordena; proibido de fechar tarefas.
   - **`executor`**: Cria `Artifact`, `Evidence`, `Question`, `Note`; assume tarefas e trabalha nelas; proibido de criar tarefas ou alterar constraints.
   - **`revisor`**: Cria `Evidence`, `Question`, `Note`; valida artefatos.
   - **`sistema`**: Telemetria (`Run`) e a `Sessao` em que o harness roda. Nada do grafo de trabalho.

   Três regras valem para **todo** papel não humano, e valem no kernel, não no
   nome da ferramenta: mudar o status de uma `Question` para `respondida` ou
   `descartada`, remover uma `Question` e remover a aresta `bloqueia` exigem
   sessão humana. Sem elas, um agente encerrava a própria escalação com um
   `propor_patch` e concluía a tarefa em seguida.
3. **Portão 3 — `InvariantGate`:**
   - **Detecção de Ciclos:** DFS iterativa impedindo ciclos em `depende_de`.
   - **Bloqueio por Dúvidas:** Impede que uma `Task` passe para `concluido` enquanto houver `Question` aberta com aresta `bloqueia`.
   - **Posse de Tarefa:** Nenhum agente move o status de uma `Task` sem deter o lock dela. Sem isso, dois executores na mesma tarefa não colidiam e o segundo sobrescrevia o primeiro em silêncio.
   - **Locks Exclusivos:** Impede mutações em tarefas travadas por outro escritor.
4. **Portão 4 — `WriteKernel`:** Geração dos `EventoLog`, persistência do lote inteiro em uma única transação (`BEGIN IMMEDIATE`/`ROLLBACK`, com `UNIQUE(ramo_id, seq)`) e notificação dos observadores — canal SSE e motor reativo.

---

## 🔌 Superfície de Ferramentas MCP (Model Context Protocol)

O `GraphowMCPServer` expõe 19 ferramentas para consumo por agentes de IA. O **papel do agente não é um argumento**: ele é fixado na abertura da sessão (`graphow mcp --papel <papel>`) e qualquer chamada que traga `papel` é recusada.

| Ferramenta | Descrição |
| :--- | :--- |
| **`ler_vista`** | Materializa o subgrafo do nó alvo formatado em Markdown, respeitando orçamentos estritos de tokens (ex: 1500, 500, 200). Num contêiner, traz o **panorama agregado** dos filhos em vez de listar a subárvore. Aceita `escopo="ativo"` para podar a navegação até o trabalho não concluído. |
| **`expandir_no`** | Fornece visão detalhada sob demanda de propriedades e arestas incidentes de um nó específico. |
| **`propor_patch`** | Submete propostas de alteração via operações JSON Patch com validação atômica. |
| **`abrir_questao`** | Cria um nó `Question` e uma aresta `bloqueia` sobre uma `Task`, sinalizando dúvida ao humano. Aceita `titulo` curto — é o que o card mostra no canvas — e guarda o corpo da dúvida na propriedade `pergunta`; sem `titulo`, ele sai do começo da pergunta. |
| **`buscar`** | Busca textual *case-insensitive* ranqueada por relevância, cortada em `limite` (padrão 5, teto 50) e sempre acompanhada de `total` e `truncado`. Filtra por `TipoNo` e por `escopo`. |
| **`proximas_tarefas`** | Fila de trabalho da sessão: tarefas com dependências concluídas, sem dúvida aberta e sem posse de outro agente, em ordem de atendimento. |
| **`assumir_tarefa`** | Adquire a posse exclusiva de uma `Task` e a move para `em_andamento`. Exigido antes de qualquer mudança de status. |
| **`liberar_tarefa`** | Devolve a posse de uma `Task`, sem alterar o status registrado. |
| **`minhas_questoes`** | Lista as dúvidas abertas por esta sessão, com a resposta humana quando já houver. |
| **`aguardar_resposta`** | Long-poll até o humano encerrar a dúvida, ou até o prazo expirar. Substitui o polling manual com `expandir_no`. |
| **`criar_projeto`** | Cria o nó `Projeto` raiz e define o nível de autonomia dos agentes nele. |
| **`criar_setor`** | Cria o `Setor` e a aresta `contem` que o liga ao `Projeto`. |
| **`criar_sessao`** | Cria a `Sessao` e a aresta `contem` que a liga ao `Setor`. |
| **`criar_tarefa`** | Cria uma `Task` com aresta `produz` e hierarquias opcionais. |
| **`concluir_tarefa`** | Transiciona a `Task` para `concluido`, se nenhuma `Question` aberta a bloquear. |
| **`responder_questao`** | Registra a resposta e destrava a `Task`. **Somente sessão humana.** |
| **`configurar_autonomia_projeto`** | Ajusta a autonomia dos agentes no projeto. **Somente sessão humana.** |
| **`excluir_em_lote`** | Remove atomicamente uma coleção de nós e arestas. **Somente sessão humana.** |
| **`excluir_projeto`** | Remove o projeto e, opcionalmente, seus descendentes. **Somente sessão humana.** |

As quatro ferramentas restritas são as que anulariam uma garantia se um agente as
executasse: `responder_questao` encerra a escalação ao humano e as demais desligam
governança ou apagam trabalho em cascata. A recusa por nome de ferramenta é a
primeira camada, não a única: o `RoleGate` impõe as mesmas garantias contra
qualquer caminho, inclusive um `propor_patch` cru.

### O ciclo de um agente autônomo

As ferramentas acima fecham as três decisões que um agente sem supervisão
precisa tomar sozinho:

1. **O que fazer** — `proximas_tarefas(id_sessao)` devolve a fila já filtrada.
2. **Trabalhar sem colidir** — `assumir_tarefa` toma a posse; o kernel recusa
   qualquer mudança de status vinda de quem não a detém.
3. **Quando parar e retomar** — `abrir_questao` escala, `aguardar_resposta`
   espera em long-poll, e `minhas_questoes` recupera o que ficou pendente na
   sessão anterior.

---

## 📚 Documentação Gerada a Partir do Código

O catálogo técnico em [`docs/`](docs/) **não é mantido à mão**: ele é derivado da
árvore sintática do próprio código por `graphow docs-gerar`. Documentação escrita à
mão diverge do código em silêncio — foi assim que este projeto chegou a ter três
contagens diferentes das ferramentas MCP e duas promessas que a implementação
contradizia.

```bash
# Regenerar o índice e os dossiês
graphow docs-gerar

# Só conferir se estão em dia (sai com código 1 se não estiverem)
graphow docs-gerar --conferir
```

A estrutura tem duas camadas:

- **[`docs/INDEX.md`](docs/INDEX.md)** — o mapa: pilares com o mecanismo que os
  sustenta, roteamento por intenção, regras de engenharia e o inventário das alas.
  Compacto de propósito; o detalhe mora nos dossiês.
- **[`docs/setores/`](docs/setores/)** — um dossiê por pacote, com o catálogo de
  módulos, classes, campos, assinaturas tipadas e constantes.

A única parte escrita à mão é o texto de missão de cada ala, em
`DEFINICOES_DE_SETOR` ([`src/graphow/documentacao/setores.py`](src/graphow/documentacao/setores.py)).
Um pacote novo sem ala declarada — ou uma ala sem pacote — faz a geração falhar.

`tests/qualidade/test_documentacao_alinhada.py` compara o que está em `docs/` com o
que o código produziria agora: alterar o código sem regenerar quebra a suíte.

**Documento canônico escrito à mão** (conceitual, não catalográfico):
- **[🧩 Especificação Formal da Ontologia (`docs/ONTOLOGY.md`)](docs/ONTOLOGY.md)**: Vocabulário semântico, bitemporalidade, separação Navegação vs Trabalho e matriz de 11 arestas permitidas.

---

## 🚀 Instalação e Execução

### Pré-requisitos
- Python $\ge$ 3.11

### Instalação em Modo Editável
```bash
git clone https://github.com/seu-usuario/graphow.git
cd graphow
pip install -e .
```

---

## 💻 Guia de Uso

### 1. Interface de Linha de Comando (CLI)

```bash
# Descobrir onde o banco vive (padrão: diretório de dados do usuário, fora de nuvem)
graphow banco-info

# Inicializar o banco de eventos
graphow init

# Trazer um banco antigo, preservando a origem intacta
graphow migrar-banco --origem "C:/caminho/antigo/graphow.db"

# Criar uma tarefa vinculada a uma Sessão
graphow task-create --titulo "Implementar Parser XML" --sessao "sess-01"

# Listar tarefas registradas
graphow task-list

# Imprimir resumo estrutural do Grafo
graphow print

# Abrir o servidor MCP com o papel fixado para a sessão
graphow mcp --papel executor --autor agente-cursor

# Regenerar o catálogo de documentação a partir do código
graphow docs-gerar

# Registrar o ciclo de vida de uma execução (chamado pelos hooks do ambiente)
graphow harness --fase inicio --sessao sess-01 --setor setor-eng --modelo opus-5
graphow harness --fase fim --sessao sess-01 --resumo "3 tarefas concluidas"

# Medir tokens por tarefa bem-sucedida sobre o corpus gravado
graphow avaliar

# Medir a escala do grafo que está no banco: peso do canvas por recorte,
# custo de navegar e custo de buscar
graphow medir-escala
```

### 2. Uso Programático em Python

```python
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.composicao import abrir_kernel_sqlite
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer

# 1. Inicializar Repositório e Kernel pela raiz de composição
store, kernel = abrir_kernel_sqlite("graphow.db")
mcp_server = GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar("agente-planejador", "planejador"))

# 2. Humano cria Sessão e Goal
proposta_inicial = PropostaPatch.criar(DadosPropostaPatch(
    autor="david",
    papel=PapelAutor.HUMANO,
    operacoes=[
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/sess-01", value={"id": "sess-01", "tipo": TipoNo.SESSAO.value, "rotulo": "Sprint 1"}),
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/goal-1", value={"id": "goal-1", "tipo": TipoNo.GOAL.value, "rotulo": "Substrato Bilateral"}),
        ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e-prod", value={"id": "e-prod", "origem_id": "sess-01", "destino_id": "goal-1", "tipo": TipoAresta.PRODUZ.value}),
    ],
    justificativa="Inicialização do projeto",
))
recibo = kernel.submeter_patch(proposta_inicial)
assert recibo.sucesso is True

# 3. Agente Planejador consome vista sob orçamento de tokens
# O papel vem da identidade da sessão, não dos argumentos da chamada
vista = mcp_server.executar_ferramenta("ler_vista", {
    "id_alvo": "goal-1",
    "orcamento_tokens": 1000,
})
print(vista["conteudo"])
```

### 3. Interface Web (`graphow web`)

O canvas fica no centro, com a moldura em volta dele. A faixa de ícones à esquerda guarda as ações globais. A lateral
esquerda tem o **explorador** (a árvore Projeto → Setor → Sessão → trabalho,
com o trabalho aberto de cada subárvore ao lado do nome), a **busca** e os
**marcadores**. No centro, cada **aba** abre o grafo num escopo — tudo, um
projeto, um setor ou uma sessão — com trilha, voltar e avançar no cabeçalho. A
lateral direita mostra o nó selecionado em cima (**propriedades**,
**conexões**, **linhagem** e **vista do agente**) e o **histórico** do log
embaixo, com o calendário de atividade e a viagem no tempo. A barra de status
fica no canto: ramo, versão do log, tamanho da tela, zoom, tempo real e
identidade.

| Onde | O que faz |
| :--- | :--- |
| Explorador | Clique abre o contêiner no canvas; Ctrl+clique abre em aba nova; o botão direito cria setor, sessão ou nó já pendurado no pai |
| Busca (`Ctrl+K`, `Ctrl+Shift+F`) | Procura no ramo inteiro, não só no que está na tela, na mesma ordem de relevância do `buscar` do MCP |
| Paleta (`Ctrl+P`) | Lista todo comando da interface, com o atalho de cada um (`?` mostra todos) |
| Canvas | Clique direito em nó, aresta ou fundo abre o menu daquilo; duplo clique num contêiner o abre; duplo clique no fundo cria um nó naquele ponto |
| Histórico | O dia no calendário filtra os eventos; cada evento volta o grafo até ele, em modo somente leitura |

**Auto-layout.** O arranjo automático não põe o grafo inteiro num Sugiyama só:
ele monta o desenho em blocos. Cada componente de trabalho vira um bloco em
camadas no sentido do fluxo causal — com as folhas de um mesmo vizinho
(as dezessete evidências de uma decisão) recolhidas numa grade, em vez de numa
coluna de quatro metros. Cada bloco vai para o menor contêiner que abriga todos
os seus nós, e por isso nenhuma aresta de trabalho atravessa uma sessão alheia.
O conteúdo de uma sessão se empacota embaixo do cartão dela, os filhos de
árvore descem numa coluna ao lado do pai, e a coluna só se reparte quando
passa da altura de uma página — que é calculada e recalculada até o desenho
inteiro ter a proporção da tela. Duzentos e vinte nós saem em 8000 × 7000 px,
sem um cartão sobre o outro; dois mil e quinhentos nós levam 100 ms.

Quatro leituras sustentam a moldura, todas resolvidas no servidor:

| Rota | Para quê |
| :--- | :--- |
| `GET /api/canvas?setor=<id>` | Escopo por Setor, ao lado de `projeto` e `sessao`. Aberta uma Sessão, só ela e o que produziu vão para a tela |
| `GET /api/busca?termo=&tipos=&limite=` | Busca ranqueada sobre o ramo, com a sessão de cada nó e o trecho onde o termo casou |
| `GET /api/ontologia` | Tipos de nó, pares de aresta aceitos e vocabulário de status, lidos da tabela do `SchemaGate` — a tela não mantém cópia |
| `POST /api/nodes` com `contido_em` | Cria o contêiner e a aresta `contem` até o pai no mesmo lote: se o portão recusar a aresta, o nó também não entra |

---

## 🔬 Observabilidade: Spans do Kernel e Taxonomia MAST

**O que existe, dito com precisão:** o Graphow **não embarca o SDK do
OpenTelemetry** e não fala OTLP. O que ele faz é emitir spans que seguem a
convenção de atributos **GenAI** e escrevê-los em NDJSON, um span por linha,
com os nomes de campo do modelo OTLP (`traceId`, `spanId`, `name`,
`attributes`). A ponte para um coletor é sua, e é curta.

**Quem emite:** o `WriteKernel`, em toda submissão ao PatchBoard e em todo fato
de ciclo de vida do harness — aceito ou recusado. O destino é injetado e, por
padrão, é `TracerNulo`: sem `--spans`, a telemetria não custa nada.

```bash
graphow --spans spans/graphow.ndjson web
```

**Atributos:** `gen_ai.system`, `gen_ai.model` (nos spans de execução),
`agent.role`, `graphow.autor`, `graphow.patch.id`, `graphow.no.id` (o nó focal
do lote), `graphow.ramo.id` e, na recusa, `graphow.portao` e
`graphow.modo_de_falha`.

**Diagnóstico MAST** (*Why Do Multi-Agent LLM Systems Fail?* Cemri et al.,
2025): o portão que recusa **declara** o modo de falha (`core/falhas.py`); o
avaliador só traduz modo em macro-categoria. Antes ele decidia por substring da
mensagem em português — funcionava, e quebraria na primeira reescrita de texto:

  - `DESALINHAMENTO_DE_AGENTE` (`VIOLACAO_PERMISSAO_PAPEL`, `PROTOTYPE_POLLUTION`)
  - `DESIGN_DO_SISTEMA` (`CICLO_DEPENDENCIA`, `ESTOURO_ORCAMENTO_TOKENS`, `TIPO_DESCONHECIDO`, `CONFLITO_CONCORRENCIA_LOCK`, `CAMINHO_INVALIDO`, `ESTRUTURA_INCOMPLETA`, `REFERENCIA_INEXISTENTE`, `PAR_DE_ARESTA_INVALIDO`)
  - `VERIFICACAO_DE_TAREFA` (`FECHAMENTO_COM_BLOQUEIO_PENDENTE`, `POSSE_DE_TAREFA_AUSENTE`)

Um teste de AST confere que toda recusa dos três portões declara o seu modo, e
a escada textual sobrevive apenas como rede para vereditos montados fora deles.

---

## 🪪 Identidade da Escrita nas Duas Superfícies

Quem escreveu o quê é a coisa que o produto promete mostrar, então a identidade
é propriedade da **conexão** nos dois lados da ponte, nunca do payload:

| Superfície | Onde a identidade é fixada | O que acontece se o corpo a declarar |
| :--- | :--- | :--- |
| **MCP (agentes)** | `graphow mcp --papel <papel> --autor <autor>` | A chamada é recusada com o papel real da sessão. |
| **Web (canvas)** | Sessão do servidor, no `graphow web` | `POST`/`PUT` com `autor` ou `papel` é recusado com `400`. |
| **Harness (hooks)** | `IdentidadeHarness`, papel `sistema` | Papéis de agente são recusados na construção. |

A vista materializada carrega essa proveniência em cada linha (`por autor
(papel)`), e conteúdo de `Evidence` ou `Artifact` criado por agente chega ao
modelo marcado como **não confiável** — a defesa mínima contra injeção
persistente.

Junto dela viaja a **ordem**: cada nó carrega a sequência do evento que o criou
(`log #N` nas linhas da vista e no rodapé do card, com a data por extenso em
`expandir_no` e no inspetor). O carimbo de tempo diz a idade; a sequência diz
quem veio antes de quem, e é a única resposta confiável para isso, porque a web
e o MCP escrevem de processos distintos, cada um com o seu relógio. A sequência
fica fora do cabeçalho da vista de propósito: ele é obrigatório em toda leitura,
então tudo que entra ali sai do orçamento de tokens de todo agente.

Cada evento também declara **em qual vocabulário foi escrito**
(`versao_ontologia`, hoje `1.0.0`), gravado no log e devolvido na linha do tempo
e no SSE. Sem isso, um log relido depois de um tipo mudar de nome projeta errado
em silêncio. A versão não pode mentir: `core/ontologia.py` calcula uma
assinatura dos termos em vigor, e um teste a compara com a versão declarada —
acrescentar um tipo de aresta sem subir a versão derruba a suíte. Eventos
gravados antes desta mudança voltam do banco como versão `0`, que é a verdade
sobre eles.

---

## 🔗 Harness: o Grafo Sabe que a Sessão Existe

`graphow harness` é a porta pela qual os hooks de início e fim de sessão do
ambiente escrevem no log. Cada disparo emite um evento de ciclo de vida
(`execucao_solicitada`, `execucao_iniciada`, `execucao_concluida`), projetado no
nó `Run` da sessão.

O identificador da sessão **não vem de variável de ambiente**: o hook entrega um
objeto JSON na entrada padrão, com `session_id` dentro. `--entrada-hook` lê esse
objeto no próprio subcomando, sem depender de `jq` no PATH:

```bash
graphow harness --fase inicio --entrada-hook --setor setor-eng
```

Fora de um hook, a sessão é declarada à mão. `--sessao` e `--entrada-hook` são
mutuamente exclusivos e um deles é obrigatório, e um identificador em branco é
recusado pelo analisador — antes era escrito como caminho vazio no patch:

```bash
graphow harness --fase fim --sessao sess-1 --resumo "sprint encerrada"
```

A fiação pronta está em `.agents/hooks/graphow_harness_hooks.json`, e
`graphow docs-gerar --conferir` passa cada comando desse arquivo pelo analisador
real e recusa qualquer exemplo que dependa de variável de ambiente.

O motor reativo escreve com origem `comportamento`, distinta de `harness` e de
`humano`, e cada nota reativa nasce ligada à sessão e ao nó que a motivou — nota
órfã não aparece na vista de ninguém.

---

## 📊 Métrica Número Um: Tokens por Tarefa Bem-Sucedida

`graphow avaliar` mede essa métrica sobre um
corpus de **dez tarefas gravadas** (`src/graphow/avaliacao/`), comparando o
recorte do grafo com o despejo integral do subgrafo da sessão:

```bash
graphow avaliar
```

O relatório publica tokens por tarefa nos dois braços, a redução média, as
intervenções humanas por tarefa e a calibração do contador em uso. Ele também
declara os próprios limites: a taxa de patch rejeitado por rodada exige um
agente real e continua fora da medição.

### Escala: o grafo real ainda cabe?

`graphow avaliar` corre sobre um cenário gravado, hermético de propósito.
`graphow medir-escala` responde a outra pergunta — *o meu grafo, do tamanho que
está hoje, cabe na tela e no orçamento?* — e por isso corre contra o banco
aberto:

```bash
graphow medir-escala
```

Ela publica três eixos: o peso do payload do canvas sob cada recorte, o custo de
descobrir onde há trabalho aberto (varrer todos os contêineres contra descer
guiado pelo rollup) e o custo de uma busca com e sem limite.

---

## 🔭 Recorte: Rollup, Escopo Ativo e Caminho Crítico

Um grafo de duzentos nós não cabe na tela nem no orçamento. Três recortes
independentes e combináveis resolvem isso, **todos resolvidos no servidor** — um
agrupamento feito só no cliente ainda faria o payload inteiro atravessar a rede.

| Recorte | Canvas | Agente |
| :--- | :--- | :--- |
| **Rollup de subárvore** | `?colapsar=setor\|sessao` mostra só a camada de navegação, cada contêiner com o progresso agregado da sua subárvore | `ler_vista` num contêiner traz a seção *Panorama dos Filhos* |
| **Escopo ativo** | `?escopo=ativo&raio=1` mantém o que está perto de tarefa não concluída ou dúvida aberta | `escopo="ativo"` em `ler_vista` e `buscar` |
| **Caminho crítico** | `?vista=caminho_critico` mantém quem participa de dependência declarada | `proximas_tarefas` já traz `depende_de` e as impedidas com motivo |

O índice de rollup é recalculado **inteiro a cada commit**, dentro de
`ProjecaoSincronizada._registrar` — ponto único, porque o kernel adota a
projeção que ele mesmo dobrou após o commit. Não há manutenção incremental: a
agregação é uma dobra pura do estado, com a mesma garantia de determinismo do
resto da projeção.

A resposta do canvas carrega sempre um bloco `recorte` dizendo quantos nós
ficaram de fora, por qual filtro, e quais nós estão fora de qualquer hierarquia.
Uma tela que mostra 6 de 191 nós sem explicar por quê é indistinguível de uma
tela quebrada.

O escopo ativo tem padrões assimétricos de propósito: ligado no canvas, desligado
no MCP. O humano fecha uma gaveta porque sabe que pode reabri-la; o agente não
sabe que ela existe, e `Decision` e `Evidence` são exatamente a memória que
impede re-decidir.

---

## 📐 Regras de Qualidade e Engenharia de Código

O código do Graphow segue padrões rigorosos de engenharia de software validados de forma automatizada via AST em `tests/qualidade/`:

- **Limite de Linhas por Arquivo:** Máximo de 400 linhas por arquivo.
- **Limite de Linhas por Função:** Máximo de 30 linhas por método/função.
- **Aninhamento:** Máximo de 2 níveis de indentação interna (uso extensivo de *guard clauses*).
- **Parâmetros Posicionais:** Máximo de 3 parâmetros posicionais por assinatura (agrupamento via DTOs/dataclasses imutáveis).
- **Tipagem Estática:** 100% de anotações estáticas explícitas (sem `Any` desnecessário).
- **Imutabilidade como Padrão:** `@dataclass(frozen=True)` em todas as entidades e DTOs.
- **CQRS:** Zero efeitos colaterais em consultas (`GrafoView`).

---

## 🧪 Execução dos Testes

```bash
# Executar a suíte completa de testes
pytest tests/ -v

# Executar a verificação estrita de regras de qualidade de código
pytest tests/qualidade/test_estrutura_codigo.py tests/qualidade/test_aninhamento_e_excecoes.py -v

# Executar as invariantes do substrato sobre sequências arbitrárias de patches
pytest tests/qualidade/test_invariantes_do_substrato.py -v

# Executar a invariante da escalação: nenhum agente encerra a própria dúvida
pytest tests/qualidade/test_invariantes_de_escalacao.py -v

# Conferir catálogo gerado e exemplos de linha de comando dos guias
graphow docs-gerar --conferir

# Executar simulação ponta a ponta
pytest tests/test_end_to_end_simulation.py -v
```

---

## 📄 Licença

Distribuído sob a licença MIT. Consulte `LICENSE` para mais detalhes.
