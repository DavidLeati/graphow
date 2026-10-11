# Bancada

A bancada é o portão de cada fase da reestruturação do graphow: as três
demandas do laboratório de 10/10/2026, rodadas do zero por uma arquitetura e
auditadas do mesmo jeito, comparadas com a linha de base. Nenhuma fase passa
se aumentar os defeitos bloqueantes que o auditor acha.

## O que ela mede

Por execução (uma arquitetura num projeto):

| Número | De onde sai |
| :--- | :--- |
| Custo (US$) | `total_cost_usd` do último `result` de cada sessão `claude -p`, somado entre as sessões |
| Tokens | entrada + saída + cache, das transcrições da sessão e dos subagentes em `~/.claude/projects`, cada mensagem pela primeira entrada (a definição de `graphow-lab/_runs/base.py`) |
| Minutos | do início da primeira sessão ao fim da última, em tempo de parede |
| Commits | commits no ramo de trabalho depois do commit da semente |
| Critérios | `atende / parcial / nao_atende` da linha PLACAR do auditor |
| Sondas ok | das 8 sondas do projeto, quantas o auditor confirmou sem defeito |
| Bloqueantes | defeitos que ferem critério ou decisão do humano, segundo o auditor |

O custo usa o último `result` de cada sessão porque uma sessão retomada com
`--resume` traz nele o acumulado. O relatório de 10/10 somou os `result` das
raízes retomadas e inflou o custo do graphow 0.4.4; a linha de base grava o
número corrigido e guarda o do relatório ao lado (`relatorio.custo_usd`). As
correções estão na seção abaixo.

## Correções ao relatório de 10/10

O relatório publicado do laboratório somou custos acumulados. Cada raiz do
graphow 0.4.4 foi retomada com `--resume` (o gerente, o Goal principal e, na
agenda, o Goal de acabamento), e o `result` de cada invocação já traz o custo
acumulado da sessão. Somar os `result` contou duas vezes as invocações
anteriores. O custo correto soma só o último `result` de cada `session_id`. Na
enxuta, de sessão única, a soma é o próprio custo e nada muda. Os commits
publicados da enxuta também estavam errados: os ramos de trabalho têm 11, 11
e 10 commits depois da semente.

| Execução | US$ publicado | US$ correto | Commits publicados | Commits corretos |
| :--- | ---: | ---: | ---: | ---: |
| graphow 0.4.4, agenda-salas | 18,58 | 10,65 | 0 | 0 |
| graphow 0.4.4, agenda-salas sem o Goal de acabamento | 7,93 | 7,57 | | |
| graphow 0.4.4, estoque-loja | 7,73 | 7,30 | 7 | 7 |
| graphow 0.4.4, api-tarefas | 9,09 | 8,77 | 0 | 0 |
| enxuta, agenda-salas | 4,78 | 4,78 | 12 | 11 |
| enxuta, estoque-loja | 5,03 | 5,03 | 11 | 11 |
| enxuta, api-tarefas | 6,24 | 6,24 | 11 | 10 |

Na agenda, o relatório contou o commit "Estado inicial" (12 em vez de 11); na
api, a tabela do plano diz 11, e o placar e o repositório, 10. A confirmação de
que o `result` é acumulado está nas transcrições. Na agenda do graphow, o
`modelUsage` do último `result` (15.435.012 tokens) é o que as transcrições
somam, e a soma dos três `result` (26.232.290) não é.

A linha de base grava os números corretos e guarda os publicados em
`relatorio`; o bloco `correcoes_ao_relatorio` dela tem esta tabela.
`graphow bancada medir-laboratorio` mede tudo de novo dos logs, e
`tests/bancada/test_linha_de_base.py` prende os números corretos e a regra
fora da medição, para que um erro na medição e na linha de base juntas não
passe.

## O que tem aqui

```
bancada/
  projetos/<projeto>/
    semente/        a árvore do commit "Estado inicial" do laboratório
    spec.md         pedido, perguntas do analista e respostas finais do humano
    sondas.md       os 8 casos que deram defeito numa das implementações
    projeto.json    ramo de trabalho e a identidade do commit da semente
  arquiteturas/enxuta.md   o prompt do controle, com {SPEC} e {RAMO}
  auditor.md               o prompt do auditor, com {REPO}, {SPEC}, {RAMO} e {SONDAS}
  linha-de-base.json       graphow 0.4.4 e enxuta, por projeto, com a fonte de cada número
```

Os projetos são `agenda-salas` (CLI Python de reservas), `estoque-loja` (CLI
Python de estoque, o chamado 142) e `api-tarefas` (API HTTP em Node 22). A
pasta é `-text` no git: a semente, as specs e os prompts chegam ao agente byte
a byte como no laboratório, e o commit da semente recriado tem o mesmo hash.

## Como rodar

O executável do Claude Code vem de `GRAPHOW_CLAUDE` ou do PATH. Toda sessão
roda sem as variáveis `CLAUDE*`, `AI_AGENT` e `BAGGAGE` da sessão de onde o
comando foi chamado, e com o `GRAPHOW_DB` apontando para um banco da própria
execução: os hooks do graphow rodam em toda sessão e nunca escrevem no banco
do usuário.

```bash
export GRAPHOW_CLAUDE="/caminho/do/claude.exe"

# Uma arquitetura num projeto, ou nos três em paralelo
graphow bancada rodar --arquitetura enxuta --projeto estoque-loja --saida ~/bancada
graphow bancada rodar --arquitetura enxuta --projeto todos --saida ~/bancada
graphow bancada rodar --arquitetura orquestrar --projeto todos --saida ~/bancada

# O auditor sobre uma execução (sessão Opus, só lê e roda verificações)
graphow bancada auditar --execucao ~/bancada/enxuta-estoque-loja-20261011-153000

# Auditar de novo: a anterior fica guardada como auditoria-anterior-1/ e auditoria-anterior-1.json
graphow bancada auditar --execucao ~/bancada/enxuta-estoque-loja-20261011-153000 --refazer

# A tabela das execuções contra a linha de base
graphow bancada placar --saida ~/bancada

# A linha de base medida de novo dos logs do laboratório, número a número
graphow bancada medir-laboratorio --laboratorio ~/Documents/graphow-lab
```

`rodar` cria `<saida>/<arquitetura>-<projeto>-<carimbo>/` com o repositório
recriado da semente, a spec ao lado dele (o prompt a cita como
`../spec-<projeto>.md`), o banco `graphow.db`, a pasta `sessoes/` com o
stream-json de cada sessão e o `execucao.json` com as sessões, a linha de
comando de cada uma, as métricas e o estado git da entrega. `auditar` roda o
auditor em `auditoria/`, uma pasta só dele, longe do relato do implementador
em `sessoes/`, e grava ali o prompt, o stream e o relatório; em
`auditoria.json` ficam o PLACAR em números, os bloqueantes listados e o custo
do auditor. Uma auditoria não sobrescreve outra: a execução que já tem
`auditoria.json` ou `auditoria/` (a de um auditor que morreu no meio também
conta) recusa sem `--refazer`. E o `auditoria.json` existe desde antes da
sessão, dizendo que ela não terminou, para que um auditor morto deixe o erro
registrado, e não um buraco.

As arquiteturas ficam no registro de `graphow.bancada.arquiteturas`. Hoje são
duas:

- `enxuta`: o controle do laboratório, uma sessão Opus com o prompt de
  processo fixo de `arquiteturas/enxuta.md`.
- `orquestrar`: o `graphow orquestrar` da fase 1, no processo da bancada, em
  modo autônomo. Cria o Goal da `spec-<projeto>.md` no `graphow.db` da
  execução, trabalha na branch de entrega do `projeto.json` (criada da branch
  da semente) e integra por fast-forward no fim. Planejador, executores e
  verificador são sessões `claude -p` separadas, todas Opus, com
  `--permission-mode bypassPermissions`, sem MCP do graphow e sem a
  configuração do usuário (`--strict-mcp-config`, `--setting-sources
  project`). O estado do Goal (área de trabalho, streams, patches) fica em
  `orquestrar/` dentro da execução, e a parada do laço com o status do Goal
  em `orquestrar.json`. Custo, tokens e minutos somam todas as sessões que a
  telemetria do orquestrador registrou.

`medir-laboratorio` não roda sessão: lê os logs do laboratório (`_runs/` e
`b/_runs/`), as transcrições e os repositórios das entregas, mede tudo com a
mesma medição das execuções e confere cada número da linha de base, inclusive
a soma dos `result` que o relatório publicado usou. Sai com 1 se algum
divergir. É o que reconfere a linha de base sem confiar nela.

## Quanto custa

Ordem de grandeza, pelos números do laboratório (Opus em tudo):

| | Por projeto | Os três |
| :--- | :--- | :--- |
| `enxuta` | US$ 4,78 a 6,24 e 20 a 27 min | ~US$ 16, ~30 min em paralelo |
| graphow 0.4.4 (referência) | US$ 7,30 a 10,65 e 22 a 29 min | ~US$ 27 |
| auditor | ~US$ 1 e ~10 min (medido: US$ 0,98, 8,4 min no estoque) | ~US$ 3 |

Uma rodada completa da enxuta nos três projetos, com auditoria, fica perto
de US$ 20; a do graphow 0.4.4 ficaria perto de US$ 30. As sessões são
`claude -p` reais e cobram de verdade; os testes usam um executável falso.

## Como ler o placar

```
| Execucao | Projeto | US$ | Tokens | Min | Commits | Criterios | Sondas ok | Bloqueantes |
| enxuta-estoque-loja-... | estoque-loja | 5,11 | 6,3 M | 21,0 min | 11 | 13/1/0 | 7/8 | 1 |
| base enxuta | estoque-loja | 5,03 | 6,2 M | 20,0 min | 11 | 14/0/0 | 6/8 | 0 |
| base graphow-0.4.4 | estoque-loja | 7,30 | 11,4 M | 24,9 min | 7 | 9/3/0 | 0/8 | 3 |

| Execucao | Contra | US$ | Tokens | Min | Commits | Atende (fracao) | Sondas ok | Bloqueantes |
| enxuta-estoque-loja-... | enxuta | +2% | +2% | +5% | +0% | -7% | +17% | +1 (base 0) |
| enxuta-estoque-loja-... | graphow-0.4.4 | -30% | -45% | -16% | +57% | +24% | +7 (base 0) | -67% |
```

A primeira tabela traz os números de cada execução e, abaixo, as referências
da linha de base no mesmo projeto. A segunda traz a variação contra cada
arquitetura de base: percentual, ou a diferença absoluta quando a base é zero.
Dos critérios compara-se a fração atendida (atende sobre julgados), porque
cada auditor conta os itens da spec do seu jeito.
Na agenda do graphow 0.4.4 valem custo, tokens e minutos sem o Goal de
acabamento, que é o comparável (a nota diz isso no fim). Execução sem
auditoria aparece com critérios, sondas e bloqueantes em `-`.

O auditor varia de uma sessão para outra. A mesma entrega de controle do
estoque, auditada duas vezes, deu `14/0/0; sondas 6/2; bloqueantes 0` no
laboratório e `11/0/0; sondas 5/3; bloqueantes 0` na bancada: os bloqueantes
bateram, a contagem de critérios mudou (tudo atendido nas duas) e uma sonda
mudou de lado (o terceiro exemplo do README falha com os dados atuais). Uma
sonda ou um critério parcial de diferença é ruído; o portão olha os
bloqueantes e a direção nos três projetos.
