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
número corrigido e guarda o do relatório ao lado (`relatorio.custo_usd`).

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

# O auditor sobre uma execução (sessão Opus, só lê e roda verificações)
graphow bancada auditar --execucao ~/bancada/enxuta-estoque-loja-20261011-153000

# A tabela das execuções contra a linha de base
graphow bancada placar --saida ~/bancada
```

`rodar` cria `<saida>/<arquitetura>-<projeto>-<carimbo>/` com o repositório
recriado da semente, a spec ao lado dele (o prompt a cita como
`../spec-<projeto>.md`), o banco `graphow.db`, a pasta `sessoes/` com o
stream-json de cada sessão e o `execucao.json` com as sessões, a linha de
comando de cada uma, as métricas e o estado git da entrega. `auditar` grava em
`auditoria/` o prompt, o stream e o relatório, e em `auditoria.json` o PLACAR
em números, os bloqueantes listados e o custo do auditor.

As arquiteturas ficam no registro de `graphow.bancada.arquiteturas`. Hoje só
existe `enxuta`; a fase 1 registra `orquestrar`.

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
