# Pedido do humano
O time de operacoes quer a API de tarefas pronta neste repositorio.

Pedido do Marcos, coordenador de operacoes:
"Precisamos de uma API simples para as tarefas do time: criar, ver, editar e apagar tarefa (titulo, descricao, status a fazer/fazendo/feito, responsavel e prazo). Listar com filtro por status e por responsavel, com paginacao porque sao milhares. Se mandarem dado errado, a API tem que dizer o que esta errado. So quem tem o token do time pode usar. Hoje ja perdemos dados quando duas pessoas salvavam ao mesmo tempo na planilha, isso nao pode acontecer. E tem que ter teste automatizado."

Duvidas, todas numa mensagem so.

# Perguntas e proposta do analista (alinhamento já feito)
Antes das perguntas, o que vi no repositório e no grafo.

**Triagem:** entra no grafo como **melhoria, num Goal só**. O repositório é pequeno (`src/server.js` só tem `/health`, `src/storage.js` lê e grava um JSON inteiro). A mudança passa por rotas, validação, autenticação, persistência e testes, mas tudo dentro do mesmo serviço. O projeto no grafo ainda está vazio e não tem `gravacao_do_gerente`, então vale o padrão: só gravo depois que você aprovar o rascunho.

**O que confirmei olhando o código:**
- O armazenamento atual (`storage.js`) relê e reescreve o arquivo inteiro a cada gravação. Dois salvamentos ao mesmo tempo fazem um apagar o outro, a mesma perda que o Marcos descreveu na planilha. Do jeito que está, esse armazenamento não atende o pedido.
- No Windows, o servidor provavelmente nem sobe com `npm start`: a comparação `file://${process.argv[1]}` e o `URL(...).pathname` não batem com caminhos `C:\`. É hipótese, ainda não rodei. Entra na tarefa como correção.
- Hoje não existe nenhum teste. `npm test` roda `node --test` sem arquivos.

**Perguntas (só as que mudam a definição):**

1. **Edição simultânea.** Quando duas pessoas editam a mesma tarefa, minha proposta é que a segunda gravação seja **recusada com um aviso de conflito** (cada tarefa tem uma versão, e quem salva em cima de uma versão antiga recebe um erro e precisa recarregar). Assim nada se perde em silêncio. O custo é que quem chega depois tem que refazer a alteração. A alternativa "o último a salvar vence" é exatamente o que acontece hoje. Posso seguir com a recusa?
2. **Onde guardar os dados.** O README diz "sem dependências externas" e o projeto aceita Node 20. Para milhares de tarefas e gravações concorrentes, eu usaria SQLite, que já vem no Node 22 (`node:sqlite`), sem instalar pacote. Isso exige subir o mínimo para Node 22. As opções são: (a) Node 22 com SQLite, (b) continuar no Node 20 e adicionar uma dependência, ou (c) ficar no arquivo JSON com trava, que é mais frágil. Também preciso saber se já existe um `dados/tarefas.json` com tarefas reais que precisam ser migradas.
3. **Token do time.** Proponho um token único, compartilhado, configurado numa variável de ambiente. A consequência é que a API não vai saber *quem* fez cada alteração. Isso basta, ou o Marcos precisa de um token por pessoa ou de histórico de quem alterou o quê?
4. **Apagar.** Exclusão definitiva, ou exclusão lógica (a tarefa some das listas mas dá para recuperar)? Como o time já perdeu dados antes, pergunto em vez de supor.
5. **Campos:**
   - O responsável é texto livre (nome ou e-mail) ou precisa vir de uma lista fixa de pessoas?
   - O prazo é obrigatório? É só a data ou data e hora? Pode ser uma data no passado?
   - Toda tarefa nova começa como "a fazer"?
   - Há limite de tamanho para título e descrição?
6. **Listagem:**
   - Em que ordem as tarefas aparecem (prazo, data de criação)?
   - Qual o tamanho padrão e o máximo de cada página (proponho 20 e 100)?
   - Os filtros de status e de responsável podem ser usados juntos?
7. **Escopo da entrega.** "Pronta neste repositório" significa código, testes automatizados e um README explicando como usar, **sem** colocar no ar em nenhum servidor? Quem executa são os agentes da orquestração, e a revisão final fica com você. Confere?

# Respostas do humano (decisões finais; valem sobre as propostas acima)
1. Sim, recusa com aviso de conflito pela versao.
2. (a) Node 22 com node:sqlite. Nao existe dado real para migrar, o dados/ esta vazio.
3. Token unico em variavel de ambiente basta.
4. Exclusao definitiva.
5. Responsavel e texto livre. Prazo e opcional, so a data (AAAA-MM-DD), pode ser no passado. Toda tarefa nova comeca "a fazer". Titulo ate 200 caracteres, descricao ate 5000.
6. Ordem por prazo (sem prazo por ultimo), depois por data de criacao. Pagina padrao 20, maximo 100. Os filtros podem ser usados juntos.
7. Confere: codigo, testes e README, sem colocar no ar.

Pode montar o rascunho e, se nao sobrar nada em aberto, ja considere aprovado: grave e siga com a orquestracao.
