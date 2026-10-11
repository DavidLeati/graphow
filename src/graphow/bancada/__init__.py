"""A bancada: as três demandas do laboratório rodadas do zero, por arquitetura, e auditadas do mesmo jeito.

Toda fase da reestruturação passa por um portão medido aqui. Os dados vivem em
`bancada/` na raiz do repositório (a semente de cada projeto, a spec com as
respostas do humano, as sondas, os prompts da arquitetura enxuta e do auditor e
a linha de base); este pacote monta a execução, roda a arquitetura, mede custo,
tokens e minutos com as definições do laboratório, roda o auditor e imprime o
placar contra a linha de base.
"""
