"""O relatório de `graphow orquestracao-medir`: um bloco por Goal e a comparação por configuração.

A pergunta é se a divisão de modelos compensa: quantas tarefas fecharam sem
retrabalho, quantas vezes a revisão rejeitou, quantas entregas o teto de
correções aceitou e quanto custou cada tarefa concluída, lado a lado para cada
arranjo de modelos. As tarefas da trilha leve aparecem à parte na linha de
modelos, porque rodam em Sonnet sob qualquer arranjo.

O custo por tarefa concluída ganha minutos de condutor, pontos da cota semanal
e tokens sem a leitura de cache quando os Run os trazem. Cada trecho novo só
aparece com o dado: um banco só com Run antigos dá o relatório de sempre.
"""

from collections import defaultdict
from collections.abc import Sequence

from graphow.avaliacao.orquestracao import SEM_MOTIVO, MedicaoDeGoal
from graphow.avaliacao.relatorio_rodadas import linhas_das_rodadas, nota_das_rodadas

SEM_GOALS: str = "Nenhum Goal com tarefas decompostas: nada a medir."


def formatar_relatorio(medicoes: Sequence[MedicaoDeGoal], *, por_rodada: bool = False) -> tuple[str, ...]:
    """As linhas do relatório: cada Goal medido e, no fim, a soma por configuração.

    Com `por_rodada`, cada Goal ganha uma linha por rodada do condutor, e o
    relatório termina com a explicação das colunas.
    """
    if not medicoes:
        return (SEM_GOALS,)
    linhas = [linha for medicao in medicoes for linha in _bloco_do_goal(medicao, por_rodada)]
    linhas.extend(("", "Por configuracao:"))
    linhas.extend(_linha_da_configuracao(nome, grupo) for nome, grupo in _agrupar(medicoes))
    linhas.extend(nota_das_rodadas(medicoes) if por_rodada else ())
    return tuple(linhas)


def _bloco_do_goal(medicao: MedicaoDeGoal, por_rodada: bool) -> tuple[str, ...]:
    """As linhas do Goal e, se pedidas, as das rodadas dele."""
    return _linhas_do_goal(medicao) + (linhas_das_rodadas(medicao) if por_rodada else ())


def _linhas_do_goal(medicao: MedicaoDeGoal) -> tuple[str, ...]:
    """Três linhas: a contagem de tarefas e revisões, os modelos marcados e o custo."""
    agentes = ", ".join(f"{agente} {_numero(total)}" for agente, total in medicao.tokens_por_agente.items())
    return (
        f"[{medicao.id_goal}] {medicao.rotulo} | configuracao: {medicao.configuracao}",
        f"  tarefas {medicao.tarefas} | concluidas {medicao.concluidas} | sem retrabalho "
        f"{medicao.concluidas_sem_retrabalho} | com retrabalho {medicao.com_retrabalho} ({medicao.correcoes} correcoes)"
        f" | revisao: {medicao.rejeicoes} rejeitadas, {medicao.aprovacoes} aprovadas{_aceites(medicao.aceites_pelo_teto)}",
        f"  modelo por tarefa: {_modelos(medicao)}",
        f"  tokens {_numero(medicao.tokens)}{_sem_cache(medicao)} ({agentes or 'nenhum Run atribuido'}){_sem_tokens(medicao)}",
    )


def _sem_cache(medicao: MedicaoDeGoal) -> str:
    """O total sem a leitura de cache, ao lado do total; some quando não houve leitura de cache."""
    if not medicao.tokens_cache_leitura:
        return ""
    return f" (sem cache de leitura {_numero(medicao.tokens_sem_cache_leitura)})"


def _sem_tokens(medicao: MedicaoDeGoal) -> str:
    """Os Run sem tokens, agrupados pelo motivo que o harness gravou.

    Quando nenhum tem motivo, como os Run gravados antes de o harness dizê-lo,
    o trecho fica como sempre foi.
    """
    if not medicao.runs_sem_tokens:
        return ""
    total = f" | {medicao.runs_sem_tokens} Run sem tokens"
    if set(medicao.runs_sem_tokens_por_motivo) <= {SEM_MOTIVO}:
        return total
    motivos = sorted(medicao.runs_sem_tokens_por_motivo.items(), key=lambda par: (-par[1], par[0]))
    return f"{total}: " + ", ".join(f"{quantos} {motivo}" for motivo, quantos in motivos)


def _modelos(medicao: MedicaoDeGoal) -> str:
    """Os modelos da trilha completa e, quando houve, as tarefas da leve à parte.

    Sem tarefa leve, a linha fica como sempre foi.
    """
    modelos = ", ".join(f"{modelo} {total}" for modelo, total in sorted(medicao.modelos_por_tarefa.items()))
    if not medicao.tarefas_leves:
        return modelos or "nenhuma tarefa"
    return f"{modelos or 'nenhuma na trilha completa'} | trilha leve {medicao.tarefas_leves}"


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
        f" | {sum(medicao.rejeicoes for medicao in grupo)} rejeicoes{_aceites(sum(medicao.aceites_pelo_teto for medicao in grupo))}"
        f" | {_numero(tokens)} tokens | {por_tarefa} por tarefa concluida{_por_tarefa_concluida(grupo, concluidas)}"
    )


def _por_tarefa_concluida(grupo: Sequence[MedicaoDeGoal], concluidas: int) -> str:
    """Minutos de condutor, pontos da cota semanal e tokens sem cache, cada um por tarefa concluída.

    Cada trecho só aparece quando o grupo tem o dado, e nenhum sem conclusão.
    """
    if not concluidas:
        return ""
    trechos = []
    if any(rodada.duracao_s is not None for medicao in grupo for rodada in medicao.rodadas):
        trechos.append(f"{round(sum(medicao.segundos_de_rodada for medicao in grupo) / 60 / concluidas)} min")
    pontos = [medicao.pontos_de_cota_semanal for medicao in grupo if medicao.pontos_de_cota_semanal is not None]
    if pontos:
        trechos.append(f"{_decimal(sum(pontos) / concluidas)} pontos de cota semanal")
    if any(medicao.tokens_cache_leitura for medicao in grupo):
        sem_cache = sum(medicao.tokens_sem_cache_leitura for medicao in grupo)
        trechos.append(f"{_numero(sem_cache // concluidas)} tokens sem cache de leitura")
    return f" ({', '.join(trechos)})" if trechos else ""


def _aceites(total: int) -> str:
    """O trecho dos aceites pelo teto; some quando não houve nenhum, que é o caso comum."""
    return f", {total} aceites pelo teto" if total else ""


def _decimal(valor: float) -> str:
    """Número com uma casa e vírgula decimal, para os pontos de cota."""
    return f"{valor:.1f}".replace(".", ",")


def _numero(valor: int) -> str:
    """Inteiro com separador de milhar, para contagens de tokens na casa dos milhões."""
    return f"{valor:,}".replace(",", ".")
