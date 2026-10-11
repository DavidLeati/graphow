"""Sessões `claude -p` que o graphow roda, com o resultado tipado.

O laboratório rodava cada sessão por um script de shell solto, com o caminho do
executável fixo e a limpeza do ambiente copiada de um para outro. Aqui fica o
caminho único: achar o executável, montar o comando, limpar o ambiente, rodar
com tempo limite, gravar o stream e ler dele o que a sessão custou e respondeu.
A bancada roda assim a arquitetura enxuta e o auditor; o orquestrador da fase 1
vai rodar assim o planejador, o executor e o verificador.
"""
