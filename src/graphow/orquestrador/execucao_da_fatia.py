"""O passo de uma fatia: a sessão do executor, a conferência do git e da suíte, o commit e o registro.

O executor implementa e devolve `pronto`, `duvida` ou `falhou`. O orquestrador
confere que o git está onde estava (e desfaz o commit que tenha escapado à
trava), roda a suíte ele mesmo e só então commita na branch do Goal, com a
mensagem que cita a fatia e os critérios, e grava o Artifact com o hash. A
dúvida vira Question que pausa só aquela fatia. A falha, ou a suíte vermelha,
ganha uma nova tentativa com o erro no briefing; na segunda, a fatia vira
pendência do Goal e o laço para. O que não vira commit vai para um `.patch`
e sai da área, para não vazar para a fatia seguinte.
"""

from dataclasses import dataclass

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.briefing import ContextoDaFatia, briefing_do_executor
from graphow.orquestrador.contexto_do_laco import MAXIMO_DE_FALHAS, ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.esquemas import PAPEL_EXECUTOR
from graphow.orquestrador.git_do_goal import commitar, descartar_mudancas, restaurar_head
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada
from graphow.orquestrador.saidas import SaidaDoExecutor
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel
from graphow.orquestrador.suite import rodar_suite

STATUS_PRONTO: str = "pronto"
STATUS_DUVIDA: str = "duvida"


@dataclass(frozen=True)
class Tentativa:
    """Uma tentativa em curso: a fatia, o número e o commit de onde ela partiu."""

    fatia: FatiaRegistrada
    numero: int
    head: str


def executar_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, fatia: FatiaRegistrada) -> Parada | None:
    """Roda uma tentativa da fatia; a parada diz por que o laço não segue."""
    if fatia.status == m.STATUS_EM_ANDAMENTO:
        _registrar_interrupcao(contexto, fatia)
        estado = contexto.estado()
        fatia = next(registrada for registrada in estado.fatias if registrada.id == fatia.id)
    if fatia.falhas >= MAXIMO_DE_FALHAS:
        return _virar_pendencia(contexto, fatia, f"falhou {fatia.falhas} vezes; a ultima: {fatia.texto(m.CAMPO_ULTIMO_ERRO)[:500]}")
    numero = fatia.tentativas + 1
    sem_orcamento = contexto.sem_orcamento()
    if sem_orcamento is not None:
        return sem_orcamento
    tentativa = Tentativa(fatia, numero, contexto.git.head())
    contexto.livro.iniciar_tentativa(fatia.id, numero)
    resposta = contexto.sessoes.rodar(
        PedidoDePapel(
            papel=PAPEL_EXECUTOR, id_goal=contexto.id_goal, pasta=contexto.area, fatia=fatia.id, tentativa=numero,
            briefing=briefing_do_executor(estado, fatia, _contexto_da_fatia(contexto, estado, numero)),
            conferir=lambda dados: SaidaDoExecutor.de_json(dados).conferir(),
            modelo=_modelo(contexto, fatia), orcamento_restante_usd=contexto.restante(),
        )
    )
    desfeito = restaurar_head(contexto.area, contexto.configuracao.ramo, tentativa.head)
    if resposta.dados is None:
        return _falhou(contexto, tentativa, "a saida do executor nao conferiu: " + "; ".join(resposta.problemas))
    return _depois_da_sessao(contexto, tentativa, SaidaDoExecutor.de_json(resposta.dados), desfeito=desfeito)


def _depois_da_sessao(contexto: ContextoDoGoal, tentativa: Tentativa, saida: SaidaDoExecutor, *, desfeito: str) -> Parada | None:
    """Dúvida, falha ou entrega conferida pela suíte."""
    fatia = tentativa.fatia
    if saida.status == STATUS_DUVIDA:
        patch = _guardar(contexto, fatia, f"t{tentativa.numero}-duvida")
        contexto.livro.abrir_duvida(fatia.id, tentativa.numero, pergunta=saida.duvida, patch=patch)
        return None
    if saida.status != STATUS_PRONTO:
        return _falhou(contexto, tentativa, f"o executor devolveu {saida.status}: {saida.resumo}")
    plano = contexto.estado().plano or {}
    suite = rodar_suite(
        contexto.area, str(plano.get("comando_suite", "")), contexto.banco_descartavel,
        tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s,
    )
    if not suite.passou:
        return _falhou(contexto, tentativa, suite.descrever())
    commit = commitar(contexto.area, _mensagem(contexto, fatia, saida)) if contexto.git.mudancas() else tentativa.head
    contexto.livro.concluir_fatia(fatia.id, tentativa.numero, commit=commit, saida=saida, observacao=desfeito)
    return None


def _falhou(contexto: ContextoDoGoal, tentativa: Tentativa, erro: str) -> Parada | None:
    """A tentativa falhou: o que ela deixou vai para um .patch; na segunda, a fatia vira pendência."""
    fatia = tentativa.fatia
    patch = _guardar(contexto, fatia, f"t{tentativa.numero}")
    falhas = fatia.falhas + 1
    contexto.livro.registrar_falha(fatia.id, tentativa.numero, erro=erro, patch=patch, falhas=falhas)
    if falhas < MAXIMO_DE_FALHAS:
        return None
    return _virar_pendencia(contexto, fatia, f"falhou {falhas} vezes; a ultima: {erro[:500]}")


def _virar_pendencia(contexto: ContextoDoGoal, fatia: FatiaRegistrada, motivo: str) -> Parada:
    """A fatia sai da fila e o Goal ganha a pendência; o laço para."""
    pendencias = [*contexto.estado().pendencias, {"gravidade": "pendencia", "titulo": fatia.titulo, "descricao": motivo,
                                                   "origem": fatia.id}]
    contexto.livro.marcar_pendencia(fatia.id, motivo, pendencias)
    return Parada(
        contexto.id_goal,
        MotivoDaParada.PENDENCIA,
        f"A fatia {fatia.codigo} ({fatia.id}) virou pendencia: {motivo}. O que ela deixou esta em "
        f"{contexto.pasta / 'patches'}. Corrija o que impede e reabra a Task (status pendente) para tentar de novo.",
    )


def _registrar_interrupcao(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> None:
    """A tentativa que estava em andamento quando o laço parou conta como falha, e a área volta ao commit."""
    patch = _guardar(contexto, fatia, f"t{fatia.tentativas}-interrompida")
    erro = "a tentativa anterior foi interrompida no meio (o orquestrador parou antes de ela terminar)"
    contexto.livro.registrar_falha(fatia.id, fatia.tentativas, erro=erro, patch=patch, falhas=fatia.falhas + 1)


def _guardar(contexto: ContextoDoGoal, fatia: FatiaRegistrada, sufixo: str) -> str:
    """O que está fora de commit vai para o .patch da tentativa; devolve o caminho, ou vazio sem nada."""
    caminho = contexto.patch(f"{fatia.id}-{sufixo}")
    return str(caminho) if descartar_mudancas(contexto.area, caminho) else ""


def _contexto_da_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, numero: int) -> ContextoDaFatia:
    """Os commits do Goal desde a base e o diff resumido do último."""
    git = contexto.git
    entregues = git.commits_desde(contexto.configuracao.base)
    diff = git.resumo_do_diff("HEAD~1", "HEAD") if entregues else ""
    return ContextoDaFatia(tentativa=numero, entregues=tuple(f"- {linha}" for linha in entregues), diff_da_anterior=diff)


def _modelo(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> str:
    """O modelo do executor: o configurado, ou o que o plano sugeriu quando a configuração pede."""
    configurado = contexto.sessoes.modelo_do_papel(PAPEL_EXECUTOR)
    return fatia.texto(m.CAMPO_MODELO) or "opus" if configurado == "sugerido" else configurado


def _mensagem(contexto: ContextoDoGoal, fatia: FatiaRegistrada, saida: SaidaDoExecutor) -> str:
    """A mensagem do commit: a fatia, os critérios, o que o executor fez e de onde veio."""
    criterios = ", ".join(fatia.lista(m.CAMPO_CRITERIOS))
    titulo = fatia.titulo.split(": ", 1)[-1]
    assunto = f"Fatia {fatia.codigo}: {titulo}" + (f" ({criterios})" if criterios else "")
    return f"{assunto}\n\n{saida.resumo}\n\nGoal: {contexto.id_goal} | Task: {fatia.id} | graphow orquestrar"
