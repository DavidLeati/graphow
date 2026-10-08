"""O placar de escopo em texto e em dicionário: as cinco linhas da seção 4.7 e o recorte para a web e o MCP.

Não depende do contexto nem da política: recebe o placar já montado e só o
descreve. O tipo do placar entra por anotação, para o módulo do placar poder
importar daqui sem ciclo.
"""

from typing import TYPE_CHECKING, Any

from graphow.projection.classificacao_escopo import ClasseDeEscopo
from graphow.projection.escopo_plano import VersaoDoPlano

if TYPE_CHECKING:
    from graphow.projection.placar_escopo import GatilhoDeDesvio, PlacarDeEscopo, RaizDoPlacar, RespostaDeDesvio

ROTULO_DAS_CLASSES: dict[str, str] = {
    ClasseDeEscopo.B1.value: "B1",
    ClasseDeEscopo.B3.value: "B3",
    ClasseDeEscopo.CORRECAO.value: "correção",
    ClasseDeEscopo.INTEGRACAO.value: "integração",
    ClasseDeEscopo.REVERSAO.value: "reversão",
    ClasseDeEscopo.ACOMPANHAMENTO.value: "acompanhamento",
    ClasseDeEscopo.SEM_LIGACAO.value: "sem ligação",
}
SEPARADOR: str = " · "
CLASSES_DE_SEMPRE: frozenset[str] = frozenset(
    {
        ClasseDeEscopo.B1.value,
        ClasseDeEscopo.B3.value,
        ClasseDeEscopo.CORRECAO.value,
        ClasseDeEscopo.INTEGRACAO.value,
        ClasseDeEscopo.REVERSAO.value,
    }
)


def linhas_do_placar(placar: "PlacarDeEscopo") -> tuple[str, ...]:
    """As cinco linhas: escopo, plano, contagem desde a referência, raiz que mais gerou e cadeia mais longa."""
    return (
        _linha_do_escopo(placar),
        _linha_do_plano(placar),
        _linha_da_contagem(placar),
        _linha_da_raiz(placar),
        f"Cadeia mais longa: {placar.cadeia_mais_longa}",
    )


def linhas_de_desvio(placar: "PlacarDeEscopo") -> tuple[str, ...]:
    """Os gatilhos disparados, as decisões sem veredito e as respostas de desvio, uma por linha."""
    linhas = [_linha_do_gatilho(gatilho) for gatilho in placar.gatilhos if gatilho.disparou]
    if placar.sem_veredito:
        linhas.append("Decisões sem veredito de escopo: " + ", ".join(placar.sem_veredito))
    linhas.extend(_linha_da_resposta(resposta) for resposta in placar.respostas_de_desvio)
    return tuple(linhas)


def placar_em_dicionario(placar: "PlacarDeEscopo") -> dict[str, Any]:
    """O placar como estruturas simples, com as respostas do árbitro marcadas."""
    topo = placar.raiz_que_mais_gerou
    return {
        "id_goal": placar.id_goal,
        "referencia": _versao_em_dicionario(placar.referencia) if placar.referencia else None,
        "versoes_do_arbitro": [_versao_em_dicionario(versao) for versao in placar.versoes_do_arbitro],
        "plano": {
            "total": placar.plano.total,
            "concluidas": placar.plano.concluidas,
            "sem_comecar": len(placar.plano.sem_comecar),
            "ids_sem_comecar": list(placar.plano.sem_comecar),
            "sem_comecar_por_fase": dict(placar.plano.sem_comecar_por_fase),
        },
        "contagem_por_classe": dict(placar.contagem_por_classe),
        "raizes": [_raiz_em_dicionario(raiz) for raiz in placar.raizes],
        "raiz_que_mais_gerou": topo.raiz if topo is not None else None,
        "cadeia_mais_longa": placar.cadeia_mais_longa,
        "respostas_de_desvio": [_resposta_em_dicionario(r) for r in placar.respostas_de_desvio],
        "emergentes_para_m": placar.emergentes_para_m,
        "gatilhos": [_gatilho_em_dicionario(gatilho) for gatilho in placar.gatilhos],
        "gatilhos_disparados": [_gatilho_em_dicionario(g) for g in placar.gatilhos if g.disparou],
        "sem_veredito": list(placar.sem_veredito),
        "limiares": {"por_raiz": placar.limiares.por_raiz, "por_goal": placar.limiares.por_goal},
    }


def _linha_do_escopo(placar: "PlacarDeEscopo") -> str:
    """A referência (versão, papel, seq) e as versões do árbitro que vieram depois."""
    if placar.referencia is None:
        partes = ["Escopo: sem plano aprovado por humano (toda Task conta como emergente)"]
    else:
        ref = placar.referencia
        partes = [f"Escopo: plano_v{ref.versao} ({ref.papel}, seq {ref.seq})"]
    if placar.versoes_do_arbitro:
        versoes = [versao.versao for versao in placar.versoes_do_arbitro]
        faixa = f"v{min(versoes)}" if min(versoes) == max(versoes) else f"v{min(versoes)}-v{max(versoes)}"
        partes.append(f"{faixa} pelo árbitro")
    return SEPARADOR.join(partes)


def _linha_do_plano(placar: "PlacarDeEscopo") -> str:
    """Total, concluídas e as que ainda não começaram, com as fases quando o plano as declara."""
    plano = placar.plano
    if placar.referencia is None:
        return "Plano: nenhum aprovado por humano"
    sem_comecar = len(plano.sem_comecar)
    texto = f"{sem_comecar} sem começar"
    if plano.sem_comecar_por_fase:
        texto += f" (fase {', '.join(plano.sem_comecar_por_fase)})"
    return SEPARADOR.join([f"Plano: {_plural(plano.total, 'Task', 'Tasks')}", f"{plano.concluidas} concluídas", texto])


def _linha_da_contagem(placar: "PlacarDeEscopo") -> str:
    """A contagem por classe desde a referência, as cinco de sempre e as outras quando existem."""
    contagem = placar.contagem_por_classe
    itens = [f"{ROTULO_DAS_CLASSES.get(classe, classe)} {total}" for classe, total in contagem.items() if _aparece(classe, total)]
    return "Desde a referência: " + SEPARADOR.join(itens)


def _aparece(classe: str, total: int) -> bool:
    """As cinco classes do placar sempre aparecem, as demais só com Task."""
    return total > 0 or classe in CLASSES_DE_SEMPRE


def _linha_da_raiz(placar: "PlacarDeEscopo") -> str:
    """A raiz que mais gerou, com as Tasks, os alvos e a falta de veredito."""
    topo = placar.raiz_que_mais_gerou
    if topo is None:
        return "Raiz que mais gerou: nenhuma"
    por_classe = topo.custo.tasks_por_classe
    partes = [f"Raiz que mais gerou: {topo.raiz}", _plural(por_classe.get(ClasseDeEscopo.B3.value, 0), "Task B3", "Tasks B3")]
    sem_ligacao = por_classe.get(ClasseDeEscopo.SEM_LIGACAO.value, 0)
    if sem_ligacao:
        partes.append(f"{sem_ligacao} sem ligação")
    partes.append(_plural(len(topo.custo.alvos), "alvo", "alvos"))
    if topo.veredito_pendente:
        partes.append("veredito de escopo pendente")
    return SEPARADOR.join(partes)


def _linha_do_gatilho(gatilho: "GatilhoDeDesvio") -> str:
    """Um gatilho disparado em uma linha, com a contagem contra o limiar."""
    if gatilho.tipo == "raiz":
        return f"Gatilho K: {gatilho.raiz} passou de {gatilho.limiar} ({gatilho.contagem} emergentes desde a referência ou a resposta)"
    if gatilho.tipo == "goal":
        return f"Gatilho M: {gatilho.contagem} emergentes desde o último zero (limiar {gatilho.limiar})"
    return f"Inanição: o plano segue sem começar e {gatilho.contagem} emergentes já saíram de pendente (limiar {gatilho.limiar})"


def _linha_da_resposta(resposta: "RespostaDeDesvio") -> str:
    """Uma resposta de desvio, marcando a do árbitro, que não zera o contador."""
    quem = f"{resposta.respondido_por} ({resposta.papel})"
    marca = " [árbitro: não zera]" if resposta.do_arbitro else ""
    alvo = resposta.raiz or "o Goal"
    return f"Resposta de desvio, seq {resposta.seq}, {quem}{marca}: {alvo} · {resposta.resposta}"


def _plural(total: int, singular: str, plural: str) -> str:
    """O número com o substantivo no singular ou no plural."""
    return f"{total} {singular if total == 1 else plural}"


def _versao_em_dicionario(versao: VersaoDoPlano) -> dict[str, Any]:
    """Uma versão do plano."""
    return {"versao": versao.versao, "seq": versao.seq, "aprovado_por": versao.aprovado_por, "papel": versao.papel}


def _raiz_em_dicionario(raiz: "RaizDoPlacar") -> dict[str, Any]:
    """Uma raiz com custo, contador de K e pendência de veredito."""
    custo = raiz.custo
    return {
        "raiz": raiz.raiz,
        "tasks": [task.id for task in custo.tasks],
        "tasks_por_classe": dict(custo.tasks_por_classe),
        "emergentes": raiz.emergentes,
        "contador_k": raiz.contador_k,
        "passou_de_k": raiz.passou_de_k,
        "veredito_pendente": raiz.veredito_pendente,
        "alvos": list(custo.alvos),
        "runs": custo.runs,
        "tokens": custo.tokens,
        "reversoes": custo.reversoes,
        "profundidade": custo.profundidade,
    }


def _resposta_em_dicionario(resposta: "RespostaDeDesvio") -> dict[str, Any]:
    """Uma resposta de desvio, com a marca de que foi o árbitro."""
    return {
        "seq": resposta.seq,
        "respondido_por": resposta.respondido_por,
        "papel": resposta.papel,
        "raiz": resposta.raiz,
        "resposta": resposta.resposta,
        "do_arbitro": resposta.do_arbitro,
    }


def _gatilho_em_dicionario(gatilho: "GatilhoDeDesvio") -> dict[str, Any]:
    """Um gatilho avaliado."""
    return {
        "tipo": gatilho.tipo,
        "raiz": gatilho.raiz,
        "contagem": gatilho.contagem,
        "limiar": gatilho.limiar,
        "disparou": gatilho.disparou,
    }

