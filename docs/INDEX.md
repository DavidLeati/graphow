# Índice da Biblioteca do Graphow

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

Este índice é o mapa: pilares, roteamento por intenção, regras de engenharia
e o inventário das alas. O catálogo detalhado de cada ala vive em
[`docs/setores/`](setores/), um dossiê por pacote.

**14 alas · 123 módulos · 13130 linhas · 251 classes**

---

## Pilares

1. **O Log é a Verdade** — Event store append-only. O grafo é uma dobra determinística dos eventos, com `UNIQUE(ramo_id, seq)` garantindo ordem total e commit em transação única.
2. **Caminho Único de Escrita** — Humanos e agentes submetem o mesmo JSON Patch (RFC 6902) aos quatro portões. O papel do autor vem da conexão, nunca do payload.
3. **Divulgação Progressiva** — As políticas caminham no grafo a partir do alvo e a renderização descarta seções por prioridade, preservando restrições e a afordância de expansão.
4. **Linhagem e Fork Barato** — Rastreio reverso do Artifact até o Goal. Ramificação é o ponteiro `(ramo_base, seq_corte)`, sem cópia de prefixo.

---

## Por onde começar

| Se você quer… | Vá para |
| :--- | :--- |
| Entender o vocabulário do domínio | Setor 01 — `graphow.core` |
| Mudar regra de permissão ou invariante | Setor 02 — `graphow.kernel` |
| Mexer em persistência, migração ou reparo | Setor 03 — `graphow.storage` |
| Investigar divergência entre grafo e log | Setores 03 e 04 |
| Ajustar o que o agente recebe de contexto | Setor 06 — `graphow.context` |
| Alterar ferramentas expostas ao agente | Setor 10 — `graphow.mcp` |
| Trabalhar no canvas ou no tempo real | Setor 12 — `graphow.web` |
| Regenerar esta documentação | Setor 13 — `graphow docs-gerar` |

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
| 01 | [Núcleo Ontológico](setores/01_core.md) | `graphow.core` | 7 | 570 | 31 |
| 02 | [Kernel de Escrita (PatchBoard)](setores/02_kernel.md) | `graphow.kernel` | 13 | 1939 | 23 |
| 03 | [Persistência Append-Only](setores/03_storage.md) | `graphow.storage` | 11 | 1326 | 31 |
| 04 | [Projeção Determinística](setores/04_projection.md) | `graphow.projection` | 6 | 632 | 9 |
| 05 | [Motor Reativo](setores/05_reactive.md) | `graphow.reactive` | 8 | 471 | 10 |
| 06 | [Divulgação Progressiva](setores/06_context.md) | `graphow.context` | 11 | 1124 | 24 |
| 07 | [Linhagem e Ramificação](setores/07_lineage.md) | `graphow.lineage` | 4 | 292 | 7 |
| 08 | [Integração com Harness](setores/08_harness.md) | `graphow.harness` | 7 | 425 | 9 |
| 09 | [Observabilidade e Taxonomia MAST](setores/09_observability.md) | `graphow.observability` | 4 | 262 | 8 |
| 10 | [Superfície MCP](setores/10_mcp.md) | `graphow.mcp` | 15 | 1699 | 25 |
| 11 | [Linha de Comando e Transporte](setores/11_api.md) | `graphow.api` | 7 | 829 | 10 |
| 12 | [Canvas e API REST](setores/12_web.md) | `graphow.web` | 17 | 1754 | 31 |
| 13 | [Harness de Avaliação](setores/13_avaliacao.md) | `graphow.avaliacao` | 4 | 517 | 6 |
| 14 | [Geração deste Catálogo](setores/14_documentacao.md) | `graphow.documentacao` | 9 | 1290 | 27 |

### Missão de cada ala

**01. Núcleo Ontológico** — Vocabulário da ontologia, modelos imutáveis do grafo, eventos do log, os modos de falha da taxonomia MAST e a hierarquia de exceções de domínio. Não depende de nenhum outro setor.

**02. Kernel de Escrita (PatchBoard)** — Os quatro portões de governança, a conversão de JSON Patch em eventos e o commit transacional. Único caminho de mutação do estado compartilhado.

**03. Persistência Append-Only** — Repositórios de eventos, locks e linhagem de ramos. Resolve onde o banco vive, migra bancos antigos e repara sequências duplicadas.

**04. Projeção Determinística** — Dobra os eventos do log no estado em memória e mantém a projeção reconciliada com o que foi persistido por outros escritores.

**05. Motor Reativo** — Comportamentos desacoplados que observam commits e propõem patches derivados, com limite de cascata e guarda de reentrância.

**06. Divulgação Progressiva** — Recorta o subgrafo relevante ao alvo por papel e o renderiza sob orçamento estrito de tokens, descartando seções por prioridade.

**07. Linhagem e Ramificação** — Rastreio causal reverso até o Goal raiz, replay pontual com instantâneos e forks registrados como ponteiro para o ponto de corte.

**08. Integração com Harness** — Ponto de entrada para hooks de ambiente registrarem sessões e execuções, sob identidade fixada na configuração.

**09. Observabilidade e Taxonomia MAST** — Traduz o modo de falha que o portão declarou em categoria MAST e recebe os spans GenAI do kernel, em memória ou em arquivo NDJSON.

**10. Superfície MCP** — Ferramentas expostas a agentes via Model Context Protocol, com o papel fixado na abertura da sessão e recusado nos argumentos.

**11. Linha de Comando e Transporte** — Interface de terminal, resolução de dependências por subcomando e formatação de eventos para transporte SSE.

**12. Canvas e API REST** — Servidor HTTP, controladores REST por área e o canal de tempo real que leva cada commit ao canvas.

**13. Harness de Avaliação** — Corpus de tarefas gravadas e medição de tokens por tarefa bem-sucedida, com e sem o recorte do grafo. Existe para que a métrica principal do plano tenha número em vez de afirmação.

**14. Geração deste Catálogo** — Extrai o catálogo do próprio código e renderiza o índice e os dossiês. Existe para que a documentação não seja mantida à mão.

