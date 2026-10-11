Implemente neste repositorio a demanda descrita em {SPEC}. O alinhamento com o humano ja terminou: as respostas dele no fim do arquivo sao as decisoes finais e valem sobre as propostas do analista. Ignore qualquer mencao a grafo, Goal ou orquestracao no texto do analista e nao use ferramentas nem skills do graphow (nada de mcp__graphow, nada de graphow-*). Nao faca perguntas: decida pelo que esta na spec e registre a decisao.

Siga este processo, nesta ordem:

1. Escreva docs/especificacao.md com os criterios de aceite numerados (C1, C2...), as decisoes (D1, D2...) com o motivo e o que ficou fora do escopo. Commit.
2. Antes de implementar, escreva testes de aceitacao executaveis derivados dos criterios: cada teste cita o criterio que prova (ex.: "C3"). Eles devem falhar agora. Commit.
3. Implemente em passos pequenos. A cada passo com os testes passando, commit na branch {RAMO} (crie-a a partir da main no inicio). Mensagens de commit citam os criterios.
4. Com tudo verde, despache UM subagente (Agent, subagent_type general-purpose) como revisor adversarial, em primeiro plano, com um prompt autocontido: o caminho do repositorio, o caminho de docs/especificacao.md e da spec, e as instrucoes: "Voce nao viu a implementacao. Rode os testes e o programa de verdade (dados em pasta temporaria; se subir servidor, porta aleatoria e mate so o PID). Para cada criterio e decisao, diga atende/parcial/nao_atende com prova. Procure ativamente casos de borda que o criterio implica e os testes nao cobrem. Avalie a qualidade dos testes (testam o que dizem?). Nao edite nada. Devolva a lista de achados com gravidade (bloqueante: fere criterio ou decisao; acompanhamento: o resto) e arquivo:linha."
5. Corrija todo achado bloqueante, com teste que o reproduz antes da correcao. Os de acompanhamento que forem baratos, corrija tambem; os demais registre em docs/pendencias.md. Commit.
6. Se corrigiu algum bloqueante, rode a revisao do passo 4 mais uma vez (no maximo duas revisoes no total).
7. Termine com um relatorio curto: o que foi entregue, criterios atendidos, o que o revisor achou e o que foi feito, pendencias, e os commits.
