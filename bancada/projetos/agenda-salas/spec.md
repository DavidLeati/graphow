# Pedido do humano
Tenho uma demanda nova para este repositorio.

Pedido da Carla, secretaria do coworking Ponto Comum:
"Hoje as reservas das 4 salas sao numa planilha e todo mes alguem marca duas reunioes na mesma sala no mesmo horario. Queremos um programinha de linha de comando: cadastrar sala (nome e capacidade), reservar sala com inicio e fim, nao deixar reservar se ja tem alguem, reserva que se repete toda semana (a reuniao de segunda das 9h), cancelar, ver a agenda do dia de uma sala e exportar a semana num CSV para eu mandar no grupo. Os dados podem ficar num arquivo no computador da recepcao."

Estou sem tempo para muita conversa: se tiver duvidas, mande todas numa mensagem so.

# Perguntas e proposta do analista (alinhamento já feito)
Li o repositório: tem só o README e o `.gitignore`, então o programa vai ser feito do zero. Também conferi o grafo: o Projeto `agenda-salas` existe e não tem nada configurado sobre quando gravar, então só gravo depois que você aprovar.

**Triagem:** é uma melhoria e vira um Goal só. É um programa novo e pequeno, sem integração com outro sistema. Ele toca 7 pontos: arquivo de dados, salas, reservas com bloqueio de conflito, recorrência semanal, cancelamento, agenda do dia e exportação em CSV.

## Dúvidas (todas aqui)

Para cada dúvida já deixei uma proposta. Se ela servir, responda só "ok".

1. **Linguagem e máquina:** a recepção usa Windows e tem Python 3.12, ou dá para instalar? **Proposta:** Python usando só o que vem com ele (nenhuma biblioteca extra), com os dados num arquivo JSON.
2. **Quem digita os comandos:** a Carla, num terminal? **Proposta:** sim. Por isso as mensagens e as datas ficam em português, no formato `dd/mm/aaaa HH:MM`.
3. **Até quando a reserva semanal se repete:** **Proposta:** ela tem data de fim obrigatória, para não ocupar a sala para sempre. Se a série nova bater com qualquer reserva já marcada, o programa recusa a série inteira e mostra as datas em conflito.
4. **Cancelar uma reserva semanal:** dá para cancelar só um dia (por exemplo, a segunda de feriado) ou só a série toda? **Proposta:** as duas opções.
5. **O que é conflito:** **Proposta:** horários que se sobrepõem. Reservas encostadas, como 9h–10h e 10h–11h, são permitidas.
6. **Dados de cada reserva:** **Proposta:** sala, início, fim, responsável e descrição. Número de pessoas fica de fora, porque a Carla não pediu para bloquear reserva acima da capacidade. Você quer esse bloqueio?
7. **Limites de horário:** **Proposta:** sem horário de funcionamento nem tamanho mínimo de reserva. O fim tem que ser depois do início, no mesmo dia.
8. **CSV da semana:** **Proposta:** de segunda a domingo, todas as salas juntas, ordenado por dia e hora. Separado por `;` e com acentos que abrem certo no Excel em português. Colunas: data, dia da semana, sala, início, fim, responsável, descrição.
9. **As 4 salas:** **Proposta:** a Carla cadastra as salas pelo próprio programa, sem nada já carregado. Se você souber os nomes, mande.
10. **Mais de um computador:** **Proposta:** só o da recepção usa o arquivo, um uso por vez. Para não corromper o arquivo se algo travar no meio, o programa grava uma cópia nova e só então troca pela antiga.

## Rascunho da definição (com as propostas acima)

```
Demanda: melhoria — programa novo; 7 pontos: arquivo de dados, salas, reserva/conflito, recorrência, cancelamento, agenda do dia, CSV
Goal: CLI agenda-salas — programa de linha de comando para a recepção do Ponto Comum cadastrar salas, reservar sem conflito (avulsa e semanal), cancelar, ver a agenda do dia por sala e exportar a semana em CSV
Critérios de aceite:
  - cadastra sala (nome único, capacidade inteira > 0) e lista as salas
  - reserva com início/fim; recusa, com mensagem clara, reserva que se sobrepõe a outra na mesma sala; reservas encostadas são aceitas
  - reserva semanal até uma data de fim; recusa a série inteira se uma data tiver conflito, listando as datas
  - cancela uma reserva, um dia da série ou a série inteira; o horário cancelado volta a ficar livre
  - agenda do dia de uma sala, em ordem de horário, com as reservas semanais incluídas
  - CSV da semana (seg–dom) com separador ";" que abre certo no Excel em português
  - dados num arquivo local que continuam lá ao fechar o programa; o arquivo não corrompe se o programa cair no meio da gravação
  - testes automatizados cobrindo conflito, recorrência, cancelamento e CSV, todos passando; README com exemplos de uso
Constraints:
  - Python 3.12 só com o que vem nele, rodando no Windows da recepção (dúvida 1)
  - dados só em arquivo local, sem servidor nem rede (pedido da Carla)
Decisions: as propostas 3–10, cada uma com o motivo
Fora do escopo: login/usuários, interface gráfica, enviar o CSV no grupo (quem envia é a Carla), bloqueio por capacidade (se não aprovado na dúvida 6)
Em aberto: nada, depois das suas respostas
```

Responda "aprovado", ou só os números que quiser mudar. Com isso eu gravo o Goal, as restrições e as decisões no grafo e começo a orquestração até o Goal fechar.

# Respostas do humano (decisões finais; valem sobre as propostas acima)
Aprovado, com dois ajustes:

6. Sim, quero o bloqueio por capacidade: a reserva informa o numero de pessoas e o programa recusa se passar da capacidade da sala.
9. As salas sao: Ipe (8 pessoas), Jatoba (4), Aroeira (12) e Auditorio (30). A Carla cadastra pelo programa mesmo.

O resto das propostas pode seguir como voce escreveu. Grave e siga com a orquestracao.
