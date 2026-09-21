"""O relatório de `graphow orquestracao-medir`: um bloco por Goal e a comparação por configuração.

A pergunta é se a divisão de modelos compensa: quantas tarefas fecharam sem
retrabalho, quantas vezes a revisão rejeitou e quanto custou cada tarefa
concluída, lado a lado para cada arranjo de modelos.
"""

from collections import defaultdict
from collections.abc import Sequence

from graphow.avaliacao.orquestracao import MedicaoDeGoal

SEM_GOALS: str = "Nenhum Goal com tarefas decompostas: nada a medir."


def formatar_relatorio(medicoes: Sequence[MedicaoDeGoal]) -> tuple[str, ...]:
    """As linhas do relatório: cada Goal medido e, no fim, a soma por configuração."""
    if not medicoes:
        return (SEM_GOALS,)
    linhas = [linha for medicao in medicoes for linha in _linhas_do_goal(medicao)]
    linhas.extend(("", "Por configuracao:"))
    linhas.extend(_linha_da_configuracao(nome, grupo) for nome, grupo in _agrupar(medicoes))
    return tuple(linhas)


def _linhas_do_goal(medicao: MedicaoDeGoal) -> tuple[str, ...]:
    """Três linhas: a contagem de tarefas e revisões, os modelos marcados e o custo."""
    modelos = ", ".join(f"{modelo} {total}" for modelo, total in sorted(medicao.modelos_por_tarefa.items()))
    agentes = ", ".join(f"{agente} {_numero(total)}" for agente, total in medicao.tokens_por_agente.items())
    sem_tokens = f" | {medicao.runs_sem_tokens} Run sem tokens" if medicao.runs_sem_tokens else ""
    return (
        f"[{medicao.id_goal}] {medicao.rotulo} | configuracao: {medicao.configuracao}",
        f"  tarefas {medicao.tarefas} | concluidas {medicao.concluidas} | sem retrabalho "
        f"{medicao.concluidas_sem_retrabalho} | com retrabalho {medicao.com_retrabalho} ({medicao.correcoes} correcoes)"
        f" | revisao: {medicao.rejeicoes} rejeitadas, {medicao.aprovacoes} aprovadas",
        f"  modelo por tarefa: {modelos or 'nenhuma tarefa'}",
        f"  tokens {_numero(medicao.tokens)} ({agentes or 'nenhum Run atribuido'}){sem_tokens}",
    )


def _agrupar(medicoes: Sequence[MedicaoDeGoal]) -> tuple[tuple[str, tuple[MedicaoDeGoal, ...]], ...]:
    """As medições por configuração, em ordem alfabética do rótulo."""
    grupos: dict[str, list[MedicaoDeGoal]] = defaultdict(list)
    for medicao in medicoes:
        grupos[medicao.configuracao].append(medicao)
    return tuple((nome, tuple(grupo)) for nome, grupo in sorted(grupos.items()))


def _linha_da_configuracao(nome: str, grupo: Sequence[MedicaoDeGoal]) -> str:
    """A soma de um arranjo de modelos, com a taxa sem retrabalho e o custo por tarefa concluída."""
    tarefas = sum(medicao.tarefas for medicao in grupo)
    concluidas = sum(medicao.concluidas for medicao in grupo)
    limpas = sum(medicao.concluidas_sem_retrabalho for medicao in grupo)
    tokens = sum(medicao.tokens for medicao in grupo)
    taxa = f"{round(100 * limpas / concluidas)}%" if concluidas else "sem conclusao"
    por_tarefa = _numero(tokens // concluidas) if concluidas else "sem conclusao"
    return (
        f"  {nome}: {len(grupo)} Goals | {tarefas} tarefas | {concluidas} concluidas, {limpas} sem retrabalho ({taxa})"
        f" | {sum(medicao.rejeicoes for medicao in grupo)} rejeicoes | {_numero(tokens)} tokens | {por_tarefa} por tarefa concluida"
    )


def _numero(valor: int) -> str:
    """Inteiro com separador de milhar, para contagens de tokens na casa dos milhões."""
    return f"{valor:,}".replace(",", ".")
