"""O briefing de cada sessão, montado por código a partir do livro-razão e do git.

O agente não lê o grafo: tudo o que ele precisa chega aqui, com o texto
inteiro dos critérios e das decisões. O executor recebe a fatia, os critérios
que ela cobre, todas as decisões, o comando da suíte, o que as fatias
anteriores entregaram (assuntos e hashes dos commits, diff resumido da
anterior), a resposta do humano à dúvida dele e, numa nova tentativa, o erro
da anterior. O verificador recebe só a spec, o plano e o commit: nada das
sessões que implementaram.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada
from graphow.orquestrador.suite import descrever_shell, shell_dos_agentes

LIMITE_DO_ERRO: int = 6000


def _criterios(plano: Mapping[str, Any], ids: Sequence[str] | None = None) -> list[str]:
    """Os critérios do plano por extenso, todos ou só os pedidos."""
    return [
        f"- {c['id']} ({c['verificacao']}): {c['texto']}"
        for c in plano.get("criterios", []) if ids is None or c["id"] in ids
    ]


def _decisoes(plano: Mapping[str, Any]) -> list[str]:
    """As decisões do plano por extenso, com o motivo."""
    return [f"- {d['id']}: {d['texto']} Motivo: {d['motivo']}" for d in plano.get("decisoes", [])]


def _bloco(titulo: str, linhas: Sequence[str]) -> str:
    """Uma seção do briefing; vazia quando não há linha."""
    conteudo = [linha for linha in linhas if str(linha).strip()]
    return f"## {titulo}\n" + "\n".join(conteudo) if conteudo else ""


def _juntar(partes: Sequence[str]) -> str:
    """As partes não vazias, separadas por linha em branco."""
    return "\n\n".join(parte for parte in partes if parte.strip()) + "\n"


def briefing_do_planejador(estado: EstadoDoGoal, spec: str, tem_fixados: bool) -> str:
    """O pedido ao planejador: a spec inteira e onde está o repositório."""
    configuracao = estado.configuracao
    ramo = configuracao.ramo if configuracao else ""
    aviso = (
        "Os criterios (C) e as decisoes (D) com id na spec ja foram fixados pelo humano: devolva-os com o mesmo id e o mesmo texto."
        if tem_fixados else ""
    )
    return _juntar([
        f"# Plano do Goal {estado.id_goal}",
        f"O repositorio esta na pasta atual, na branch {ramo}, criada da base.",
        f"O orquestrador roda o `comando_suite` na raiz da area em {descrever_shell(shell_dos_agentes())}, "
        "o mesmo shell da sua ferramenta Bash: escreva o comando para ele.",
        aviso,
        "## Spec do Goal\n" + spec.strip(),
        "Devolva o plano no JSON do schema.",
    ])


@dataclass(frozen=True)
class ContextoDaFatia:
    """O que o git e o livro-razão dizem em volta da fatia que vai rodar."""

    tentativa: int
    entregues: tuple[str, ...] = ()
    diff_da_anterior: str = ""


def briefing_do_executor(estado: EstadoDoGoal, fatia: FatiaRegistrada, contexto: ContextoDaFatia) -> str:
    """O pedido ao executor da fatia, com tudo o que a governa por extenso."""
    plano = estado.plano or {}
    return _juntar([
        f"# Fatia {fatia.codigo} do Goal {estado.id_goal}: {fatia.titulo}",
        f"Sessao {contexto.tentativa} desta fatia; {fatia.falhas} falha(s) ate agora (na segunda, a fatia vira pendencia). "
        "Pasta: a area de trabalho do Goal, na branch dele.",
        _bloco("Objetivo da fatia", [fatia.texto(m.CAMPO_OBJETIVO), _arquivos(fatia), _correcao(estado, fatia)]),
        _bloco("Criterios que esta fatia cobre", _criterios(plano, fatia.lista(m.CAMPO_CRITERIOS))),
        _bloco("Todos os criterios do Goal (contexto)", _criterios(plano)),
        _bloco("Decisoes que o trabalho segue", _decisoes(plano)),
        _bloco("Suite", [f"`{plano.get('comando_suite', '')}`: o orquestrador roda de novo depois de voce, e ela precisa passar."]),
        _bloco("O que as fatias anteriores entregaram", [*contexto.entregues, _diff(contexto.diff_da_anterior)]),
        _bloco("Respostas do humano as suas duvidas", _respostas(fatia)),
        _bloco("A tentativa anterior falhou", _falha_anterior(fatia)),
        "## Spec completa do Goal\n" + str(estado.propriedades.get(m.CAMPO_SPEC, "")).strip(),
    ])


def _arquivos(fatia: FatiaRegistrada) -> str:
    """Os arquivos que o plano previu para a fatia."""
    arquivos = fatia.lista(m.CAMPO_ARQUIVOS_ALVO)
    return f"Arquivos: {', '.join(arquivos)}" if arquivos else ""


def _correcao(estado: EstadoDoGoal, fatia: FatiaRegistrada) -> str:
    """Na fatia de correção, de onde ela veio."""
    origem = fatia.texto(m.CAMPO_CORRIGE)
    return f"Esta fatia corrige um achado bloqueante da verificacao {origem} do Goal." if origem else ""


def _diff(diff: str) -> str:
    """O diff resumido da fatia anterior."""
    return f"Diff da fatia anterior:\n```\n{diff}\n```" if diff else ""


def _respostas(fatia: FatiaRegistrada) -> list[str]:
    """Cada dúvida que o humano respondeu, com a resposta, e onde está o que a tentativa pausada tinha feito."""
    respostas = [f"- Pergunta: {d.pergunta}\n  Resposta: {d.resposta or '(sem texto)'}" for d in fatia.duvidas if not d.aberta]
    patch = fatia.texto(m.CAMPO_PATCH)
    if respostas and patch and not fatia.texto(m.CAMPO_ULTIMO_ERRO):
        respostas.append(f"O que a tentativa pausada tinha mudado foi descartado da area e guardado em {patch} (pode ler).")
    return respostas


def _falha_anterior(fatia: FatiaRegistrada) -> list[str]:
    """O erro da tentativa anterior e onde está o que ela tinha mudado."""
    erro = fatia.texto(m.CAMPO_ULTIMO_ERRO)
    if not erro:
        return []
    patch = fatia.texto(m.CAMPO_PATCH)
    linhas = [erro[-LIMITE_DO_ERRO:]]
    if patch:
        linhas.append(f"O que ela tinha mudado foi descartado da area e guardado em {patch} (pode ler).")
    return linhas


def briefing_do_verificador(estado: EstadoDoGoal, commit: str, entregues: Sequence[str]) -> str:
    """O pedido ao verificador: spec, critérios, decisões, suíte e o commit, sem nada de quem implementou."""
    plano = estado.plano or {}
    return _juntar([
        f"# Verificacao do Goal {estado.id_goal}: {estado.rotulo}",
        f"Commit verificado: {commit}. A pasta atual esta nesse commit.",
        _bloco("Suite", [f"`{plano.get('comando_suite', '')}`"]),
        _bloco("Criterios de aceite", _criterios(plano)),
        _bloco("Decisoes", _decisoes(plano)),
        _bloco("Commits do Goal desde a base", list(entregues)),
        "## Spec completa do Goal\n" + str(estado.propriedades.get(m.CAMPO_SPEC, "")).strip(),
        "Devolva a verificacao no JSON do schema, com um parecer para cada criterio e cada decisao e, em `comandos`, "
        "cada comando que rodou, com o codigo de saida e um trecho do que ele imprimiu. Depois de voce, o orquestrador "
        "roda a suite nesse commit: suite vermelha reprova a entrega.",
    ])


def pedido_de_correcao_da_saida(problemas: Sequence[str]) -> str:
    """O que vai à mesma sessão quando a saída dela não conferiu."""
    lista = "\n".join(f"- {problema}" for problema in problemas)
    return f"A sua saida nao conferiu com o que o orquestrador precisa:\n{lista}\n\nDevolva de novo o JSON inteiro, corrigido."
