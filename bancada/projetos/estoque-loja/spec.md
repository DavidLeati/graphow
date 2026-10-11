# Pedido do humano
Chegou o chamado 142 da Ferragem Silva, esta em docs/chamado-142.md.

Pode mandar as duvidas todas numa mensagem so.

# Perguntas e proposta do analista (alinhamento já feito)
Reproduzi os três defeitos e li o `estoque.py` inteiro. Não gravei nada no grafo ainda: o projeto não tem `gravacao_do_gerente` configurada, então vale o padrão, que é gravar só depois que você aprovar.

## Triagem

Tudo entra como desenvolvimento, e é uma **melhoria** (um Goal só). Mexe em um arquivo e em poucos pontos dele: a função `pedido`, a leitura e gravação do CSV, a formatação do `total` e do `listar`, um comando novo e os testes. Duas coisas são operação de dados, não código, e dependem de você: acertar a fita com -3 e recadastrar o parafuso.

## O que confirmei

1. **Estoque negativo (é bug).** A conferência em `estoque.py:73-79` olha cada linha do pedido sozinha contra o saldo. 6 ≤ 10 passa, 7 ≤ 10 passa, e o sistema baixa 13. Reproduzi: entrada de 10, pedido `007:6 007:7`, resultado -3. Bate com o `movimentos.log` (entrada 10 em 30/09, saídas 6 e 7 em 01/10).
2. **Vírgula no nome (é bug).** O CSV é separado por vírgula na mão (`split(",")`, linha 27) e gravado sem aspas. Com "3,5mm" a linha ganha uma coluna a mais, e o `listar` quebra com `ValueError: '5mm'`. Reproduzi. O parafuso não está mais no `estoque.csv`, porque a Marcia tirou a linha.
3. **Casas decimais (é bug, mas não reproduzi o número).** O total é somado em `float` e impresso cru. Com o arquivo de hoje sai `R$ 1141.2`, não o `1484.3999…` do chamado; esse número deve ser de quando o parafuso ainda estava no arquivo. O defeito existe do mesmo jeito. Repare também que o -3 da fita **tira** R$ 14,10 do total. O `listar` tem o mesmo problema de formatação: mostra "R$ 39.9".
4. **Lista abaixo do mínimo (novo).** Com os dados de hoje entrariam a fita 007 (-3 de 20) e a broca 015 (2 de 6).
5. **"Saber que não quebrou."** Não existe nenhum teste. Proponho uma suíre de testes automáticos que rode com um comando só e cubra os quatro casos acima.

## Dúvidas (todas de uma vez)

**Pedido**
1. Quando o total de um código no pedido passa do saldo, o pedido inteiro é recusado e nada é baixado? É o que o sistema já faz para uma linha só, e eu manteria.

**Dados (precisam do seu aval, não vou mexer sem ele)**
2. Fita 007: qual saldo gravar? Saíram 13 e havia 10. Pode ser que só 10 tenham sido entregues, ou que houvesse mais na prateleira sem registro. Alguém precisa contar. Ou a correção fica com a loja, como uma "entrada de ajuste"?
3. Parafuso sextavado 3,5mm: você tem código, preço e mínimo para recadastrar? Ou a Bruna recadastra depois da correção? Hoje ainda seria preciso trocar a vírgula por ponto no nome.

**Nome com vírgula**
4. Proponho **aceitar** a vírgula no nome, gravando o CSV com aspas no padrão do formato. O arquivo atual continua sendo lido igual. A outra opção é **bloquear** a vírgula com um aviso no cadastro. Concorda em aceitar?
5. Se uma linha do arquivo vier estragada no futuro, o sistema deve **parar com uma mensagem clara** dizendo qual é a linha, ou **pular a linha com aviso** e seguir? Pular evita o sistema travado, mas esconde um produto. Eu iria de parar com mensagem clara.

**Valores**
6. Que formato o contador quer: `R$ 1.141,20` (padrão brasileiro) ou `R$ 1141.20`? Vale também para o preço no `listar`?

**Lista de compras**
7. "Abaixo do mínimo" é estritamente menor, ou inclui quem está exatamente no mínimo?
8. A lista deve mostrar quanto comprar (mínimo − saldo)? Basta sair na tela, ou precisa virar arquivo para imprimir? Agendar para toda segunda fica fora do escopo, a menos que você queira.

**Testes e entrega**
9. Posso usar só o que vem com o Python (`unittest`), sem instalar nada, já que não sobrou ninguém na loja para manter dependências? Além dos testes, quer um README curto de uso e de "como conferir que não quebrou"?
10. A entrega vai como commit numa branch nova (sugiro `chamado-142`) ou direto na `main`? Não há remoto configurado, então não teria PR.
11. A resposta para a Marcia: eu redijo no fim e o Rafael envia, certo? Um aviso: a política do projeto deixa ação externa com o executor. Por isso **não** vou criar Task de envio, só o rascunho.

Com as respostas, monto a definição completa (Goal, critérios de aceite, Constraints e Decisions) para você aprovar antes de gravar e seguir para a orquestração.

# Respostas do humano (decisões finais; valem sobre as propostas acima)
1. Sim, o pedido inteiro e recusado e nada e baixado.
2. A Marcia contou a prateleira: tem 0 fitas. Preciso de um jeito de acertar o saldo pelo sistema que fique registrado no movimentos.log com o motivo, algo como um comando de ajuste de inventario. Ela mesma roda o ajuste depois da entrega.
3. A Bruna recadastra o parafuso depois da correcao, nao precisa fazer nada com ele.
4. Aceitar a virgula, com aspas no padrao do CSV.
5. Parar com mensagem clara dizendo a linha.
6. R$ 1.141,20, padrao brasileiro, no total e no listar.
7. Estritamente menor que o minimo.
8. Mostrar quanto comprar (minimo - saldo). So na tela. Agendamento fica fora.
9. So unittest, sem instalar nada. README curto de uso e de como conferir, sim.
10. Branch chamado-142.
11. Isso, voce redige e o Rafael envia.

Monte a definicao e, se nao sobrar nada em aberto, considere aprovada: grave e siga com a orquestracao.
