"""O orquestrador em código: `graphow orquestrar`, o laço de planejar, executar, verificar e fechar um Goal.

Na arquitetura anterior a coordenação era feita por LLMs: uma raiz que
despachava rodadas, um condutor novo a cada rodada, um árbitro e um executor
só para fechar. Custavam dois terços dos tokens fazendo o que um laço de
código faz. Aqui o laço é código, retomável a partir do livro-razão e do git,
e os LLMs entram só onde há julgamento: o planejador (uma vez por Goal), o
executor (uma sessão nova por fatia) e o verificador adversarial. Cada um roda
numa sessão `claude -p` nova, com o briefing montado por código, sem MCP do
graphow, e devolve JSON validado por schema. Nenhum agente escreve no grafo:
o orquestrador grava, com o papel `orquestrador`, e commita.
"""
