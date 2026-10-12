# Índice da Biblioteca do Graphow

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

Este índice é o mapa: pilares, roteamento por intenção, regras de engenharia
e o inventário das alas. O catálogo detalhado de cada ala vive em
[`docs/setores/`](setores/), um dossiê por pacote.

**18 alas · 303 módulos · 42978 linhas · 534 classes**

---

## Pilares

1. **O Log é a Verdade** — Event store append-only. O grafo é uma dobra determinística dos eventos, com `UNIQUE(ramo_id, seq)` garantindo ordem total e commit em transação única.
2. **Caminho Único de Escrita** — Humanos e agentes submetem o mesmo JSON Patch (RFC 6902) aos quatro portões. O papel do autor vem da conexão, nunca do payload, e a política de governança do projeto decide quem exerce cada gesto: o humano ou o árbitro.
3. **Divulgação Progressiva** — As políticas caminham no grafo a partir do alvo e a renderização descarta seções por prioridade, preservando restrições e a afordância de expansão.
4. **Linhagem e Fork Barato** — Rastreio reverso do Artifact até o Goal. Ramificação é o ponteiro `(ramo_base, seq_corte)`, sem cópia de prefixo.

---

## Por onde começar

| Se você quer… | Vá para |
| :--- | :--- |
| Entender o vocabulário do domínio | Setor 01 — `graphow.core` |
| Mudar regra de permissão ou invariante | Setor 02 — `graphow.kernel` |
| Mudar quem exerce um gesto (humano ou árbitro), presets e herança | Setores 01 e 02 — `graphow.core.governanca` e `graphow.kernel` |
| Mexer em persistência, migração ou reparo | Setor 03 — `graphow.storage` |
| Investigar divergência entre grafo e log | Setores 03 e 04 |
| Ajustar o que o agente recebe de contexto | Setor 06 — `graphow.context` |
| Alterar ferramentas expostas ao agente | Setor 10 — `graphow.mcp` |
| Trabalhar no canvas ou no tempo real | Setor 12 — `graphow.web` |
| Regenerar esta documentação | Setor 14 — `graphow docs-gerar` |
| Gerar o acervo de notas dos aprendizados | Setor 15 — `graphow notas-gerar` |
| Rodar uma sessão `claude -p` e ler o que ela custou | Setor 16 — `graphow.sessoes` |
| Medir uma arquitetura nas demandas do laboratório | Setor 17 — `graphow bancada` |
| Rodar um Goal do plano ao fechamento | Setor 18 — `graphow orquestrar` |

---

## Regras de engenharia

Verificadas por AST em `tests/qualidade/`. Uma violação quebra a suíte.

| Regra | Limite |
| :--- | :--- |
| Linhas por arquivo | no máximo 400 |
| Linhas por função | no máximo 30 |
| Níveis de aninhamento | no máximo 2, com cláusulas de guarda |
| Parâmetros posicionais | no máximo 3, agrupados em DTOs acima disso |
| Tipagem | 100% das assinaturas anotadas |
| Exceções | captura sempre específica, nunca `Exception` nu |
| Imutabilidade | `@dataclass(frozen=True)` como padrão |

---

## As alas da biblioteca

| # | Ala | Pacote | Módulos | Linhas | Classes |
| ---: | :--- | :--- | ---: | ---: | ---: |
| 01 | [Núcleo Ontológico](setores/01_core.md) | `graphow.core` | 13 | 1459 | 38 |
| 02 | [Kernel de Escrita (PatchBoard)](setores/02_kernel.md) | `graphow.kernel` | 33 | 5605 | 35 |
| 03 | [Persistência Append-Only](setores/03_storage.md) | `graphow.storage` | 13 | 1746 | 38 |
| 04 | [Projeção Determinística](setores/04_projection.md) | `graphow.projection` | 23 | 3742 | 40 |
| 05 | [Motor Reativo](setores/05_reactive.md) | `graphow.reactive` | 10 | 896 | 13 |
| 06 | [Divulgação Progressiva](setores/06_context.md) | `graphow.context` | 21 | 2759 | 31 |
| 07 | [Linhagem e Ramificação](setores/07_lineage.md) | `graphow.lineage` | 4 | 282 | 7 |
| 08 | [Integração com Harness](setores/08_harness.md) | `graphow.harness` | 15 | 1806 | 20 |
| 09 | [Observabilidade e Taxonomia MAST](setores/09_observability.md) | `graphow.observability` | 4 | 262 | 8 |
| 10 | [Superfície MCP](setores/10_mcp.md) | `graphow.mcp` | 18 | 2781 | 28 |
| 11 | [Linha de Comando e Transporte](setores/11_api.md) | `graphow.api` | 13 | 2081 | 20 |
| 12 | [Canvas e API REST](setores/12_web.md) | `graphow.web` | 31 | 3739 | 60 |
| 13 | [Harness de Avaliação](setores/13_avaliacao.md) | `graphow.avaliacao` | 28 | 4583 | 56 |
| 14 | [Geração deste Catálogo](setores/14_documentacao.md) | `graphow.documentacao` | 13 | 1749 | 38 |
| 15 | [Acervo de Notas como Projeção](setores/15_notas.md) | `graphow.notas` | 5 | 403 | 9 |
| 16 | [Sessões claude -p](setores/16_sessoes.md) | `graphow.sessoes` | 5 | 558 | 8 |
| 17 | [Bancada de Medição](setores/17_bancada.md) | `graphow.bancada` | 13 | 1751 | 25 |
| 18 | [Orquestrador em Código](setores/18_orquestrador.md) | `graphow.orquestrador` | 41 | 6776 | 60 |

### Missão de cada ala

**01. Núcleo Ontológico** — Vocabulário da ontologia (versão 1.7.0: o aceite no centro, com os tipos Criterio e Achado e a aresta fere, sobre o papel orquestrador da 1.6.0, que grava o livro-razão do Goal no lugar dos agentes, o escopo governado da 1.5.0, o tipo Governanca, o papel arbitro e a Evidence localizada por fonte genérica), modelos imutáveis do grafo, eventos do log, os modos de falha da taxonomia MAST, a hierarquia de exceções de domínio e a política de governança pura (gestos, presets, herança global para projeto e composição pela mais restritiva). Não depende de nenhum outro setor.

**02. Kernel de Escrita (PatchBoard)** — Os quatro portões de governança, a conversão de JSON Patch em eventos e o commit transacional. Único caminho de mutação do estado compartilhado. O RoleGate decide cada gesto pela política de governança do Projeto do alvo (humano ou árbitro, a mais restritiva quando o nó tem mais de um Projeto), mantém sempre humanos a promoção global e a configuração da governança, e o InvariantGate só deixa um agente concluir uma Task com veredito de revisão aprovado, em qualquer preset, e só deixa o Goal do aceite no centro (conduzido pelo orquestrador ou com Criterio) fechar com a verificação final limpa no commit atual, todo critério atendido e nenhum achado bloqueante aberto, para qualquer papel. O papel orquestrador, que nenhum servidor MCP alcança, tem contrato próprio: grava o Goal que conduz sem posse nem veredito por Task e nunca toca as reservas do humano.

**03. Persistência Append-Only** — Repositórios de eventos, locks, linhagem de ramos e a telemetria das sessões do orquestrador, numa tabela fora do log. Resolve onde o banco vive, migra bancos antigos e repara sequências duplicadas.

**04. Projeção Determinística** — Dobra os eventos do log no estado em memória e mantém a projeção reconciliada com o que foi persistido por outros escritores.

**05. Motor Reativo** — Comportamentos desacoplados que observam commits e propõem patches derivados, com limite de cascata e guarda de reentrância. A Task de condensar a sessão e a de consolidar aprendizados dizem no roteiro quem promove, conforme a política do Projeto, e a consolidação não reabre enquanto há consolidado esperando promoção.

**06. Divulgação Progressiva** — Recorta o subgrafo relevante ao alvo por papel e o renderiza sob orçamento estrito de tokens, descartando seções por prioridade. Diz ao agente a governança vigente (seção Governanca e protocolo) a partir da política do Projeto do alvo, e a vista do árbitro traz o que ele precisa para decidir.

**07. Linhagem e Ramificação** — Rastreio causal reverso até o Goal raiz, replay pontual com instantâneos e forks registrados como ponteiro para o ponto de corte.

**08. Integração com Harness** — Ponto de entrada para hooks de ambiente registrarem sessões e execuções, sob identidade fixada na configuração.

**09. Observabilidade e Taxonomia MAST** — Traduz o modo de falha que o portão declarou em categoria MAST e recebe os spans GenAI do kernel, em memória ou em arquivo NDJSON.

**10. Superfície MCP** — Ferramentas expostas via Model Context Protocol à sessão do humano (graphow mcp --papel humano, o único papel que abre servidor), com o papel fixado na abertura e recusado nos argumentos. Os agentes do graphow orquestrar rodam sem MCP do graphow. As identidades de agente (planejador, executor, revisor, árbitro) seguem só em processo até a fase 4; configurar_governanca e configurar_autonomia_projeto são sempre do humano.

**11. Linha de Comando e Transporte** — Interface de terminal, resolução de dependências por subcomando e formatação de eventos para transporte SSE.

**12. Canvas e API REST** — Servidor HTTP, controladores REST por área e o canal de tempo real que leva cada commit ao canvas. Inclui a aba Configurações (governança global e por projeto, auditoria do árbitro) e as rotas que a servem, com o catálogo de gestos e presets lido da própria política.

**13. Harness de Avaliação** — Corpus de tarefas gravadas e medição do tamanho da vista contra o despejo da sessão, com e sem o recorte do grafo. Existe para que essa métrica tenha número em vez de afirmação, e declara o que ela não mede: sucesso de tarefa exige um agente real.

**14. Geração deste Catálogo** — Extrai o catálogo do próprio código e renderiza o índice e os dossiês. Existe para que a documentação não seja mantida à mão.

**15. Acervo de Notas como Projeção** — Renderiza um diretório de notas em Markdown a partir dos aprendizados promovidos, uma nota por aprendizado, com a origem derivada das arestas. O grafo é a fonte; o acervo é leitura, regenerável do zero, e a conferência acusa qualquer deriva.

**16. Sessões claude -p** — Roda uma sessão `claude -p` pelo caminho único: acha o executável (GRAPHOW_CLAUDE, depois o PATH), monta o comando com saída stream-json, tira do ambiente as variáveis da sessão mãe, aplica o GRAPHOW_DB pedido, espera até o tempo limite, grava o stream num arquivo e devolve o resultado tipado (sessão, texto final, erro, custo, tokens, duração e turnos). Não depende do grafo: é a peça sobre a qual a bancada e o orquestrador rodam agentes.

**17. Bancada de Medição** — O portão de cada fase da reestruturação: as três demandas do laboratório rodadas do zero por arquitetura e auditadas do mesmo jeito. Lê os dados versionados em `bancada/` (semente, spec, sondas, prompts e linha de base) e recria o repositório de cada execução com o mesmo hash do laboratório. Não toca o banco do usuário: cada execução tem o seu.

**18. Orquestrador em Código** — O `graphow orquestrar`: o laço que planeja, executa, verifica e fecha um Goal sem LLM coordenando. O planejador, o executor de cada fatia e o verificador adversarial rodam em sessões `claude -p` novas, com briefing montado por código, sem MCP do graphow e com o git de escrita travado, e devolvem JSON validado por schema. O orquestrador grava o livro-razão com o papel `orquestrador`, commita cada fatia numa branch do Goal, guarda a telemetria de cada sessão fora do grafo e retoma de onde parou a partir do livro-razão e do git.

