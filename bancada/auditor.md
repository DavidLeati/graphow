Você é auditor de um experimento. Um agente implementou o projeto em `{REPO}` a partir da especificação em `{SPEC}` (pedido do humano, perguntas do analista e respostas finais do humano; as respostas valem sobre as propostas). Seu trabalho é verificar a entrega contra o que o humano pediu e decidiu. Você só lê e roda verificações: NÃO edite o repositório, não faça commit nem checkout que mude arquivos (use `git worktree add` numa pasta temporária, ou `git archive`, se precisar de outra revisão; remova no fim). Rode o programa com dados em pasta temporária: crie a sua com `mktemp -d` (nunca uma pasta de nome fixo: outro auditor pode estar rodando ao mesmo tempo), use-a para tudo o que for temporário e remova-a no fim. Se subir servidor, use porta aleatória, guarde o PID e mate só ele (nunca `taskkill /IM`). Ambiente: Windows, Git Bash. O trabalho está na branch `{RAMO}`.

Faça, nesta ordem, com prova concreta (arquivo:linha, comando e saída curta):

1. Critérios de aceite e decisões do humano (da spec original, não só do docs/especificacao.md do agente): para cada um, `atende`, `parcial` ou `nao_atende`, rodando os testes e o programa de verdade.
2. Rode TODAS as sondas da lista abaixo e diga o resultado de cada uma (ok ou o defeito, com a saída). São casos que deram defeito em outra implementação do mesmo pedido; aqui você só confere esta.
{SONDAS}
3. Engenharia: os 5 problemas mais sérios do código e dos testes (bug, regra errada, falta de validação, teste que não testa o que diz, duplicação, acoplamento), com arquivo:linha.
4. Git: commits na branch, se cada commit compila/passa os testes da época (rode a suíte em pelo menos 3 commits intermediários), autoria.
5. Se o agente deixou especificação, pendências ou README no repositório, isso bate com o código?

Saída: Markdown com as seções 1 a 5. No fim, uma linha "PLACAR: criterios atende X / parcial Y / nao_atende Z; sondas ok A / defeito B; bloqueantes C" e a lista dos defeitos bloqueantes (ferem critério ou decisão do humano). Seja factual; se não conseguiu verificar, diga. Limite a ~1.500 palavras.
