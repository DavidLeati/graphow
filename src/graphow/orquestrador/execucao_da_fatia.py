"""O passo de uma fatia: a sessão do executor, a conferência do git e da suíte, o commit e o registro.

O executor implementa e devolve `pronto`, `duvida` ou `falhou`. O orquestrador
confere que o git está onde estava (e desfaz o commit que tenha escapado à
trava), recusa a fatia que mexeu em `aceite/` (o ignorado pelo git inclusive),
que escondeu mudança com as flags do índice, que criou um módulo com o nome
do runner de testes ou que pôs num conftest.py um hook do pytest que decide o
resultado (orquestrador/aceite_intocado.py), roda a
suíte ele mesmo (sem os testes de aceite, que provam o Goal inteiro e ficam
vermelhos até a fatia que os atende), passa a fatia de risco, e a que mudou a
configuração de teste (o que é sinal, e não recusa), pela revisão
(orquestrador/revisao_da_fatia.py) e só então commita na branch do Goal, com
a mensagem que cita a fatia e os critérios, e grava o Artifact com o hash. A
dúvida vira Question que pausa só aquela fatia. A falha, ou a suíte vermelha,
ganha uma nova tentativa com o erro no briefing; na segunda, a fatia vira
pendência do Goal e o laço para. O que não vira commit vai para um `.patch`
e sai da área, para não vazar para a fatia seguinte. A fatia que caiu no
meio da sessão passa por isso na retomada, e antes do pedido do humano que
chega primeiro (`guardar_a_fatia_interrompida`).
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.aceite_intocado import (
    configuracoes_mudadas,
    conftests_que_decidem_o_resultado,
    flags_do_indice,
    limpar_flags,
    soltos_que_mudam_os_testes,
    tirar_sombras_do_runner,
)
from graphow.orquestrador.briefing import ContextoDaFatia, briefing_do_executor
from graphow.orquestrador.contexto_do_laco import MAXIMO_DE_FALHAS, ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.decisoes_do_agente import (
    CAMPO_CRITERIOS_REFEITOS,
    CAMPO_DESACORDO,
    CAMPO_TESTE_ERRADO,
    PREFIXO_DO_PEDIDO_AUTOMATICO,
    documentar_decisoes,
    operacoes_das_decisoes,
)
from graphow.orquestrador.esquemas import ESQUEMA_DA_EXECUCAO_AUTONOMA, PAPEL_EXECUTOR
from graphow.orquestrador.falhas_da_api import LimiteDaApi
from graphow.orquestrador.git_do_goal import (
    arquivos_do_commit,
    commit_da_fatia,
    descartar_mudancas,
    guardar_patch,
    mensagem_do_orquestrador,
)
from graphow.orquestrador.historico_da_correcao import tentativas_anteriores
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada
from graphow.orquestrador.livro_razao import propriedade
from graphow.orquestrador.revisao_da_fatia import PedidoDeRevisao, RejeicaoDaRevisao, de_risco, revisar_fatia
from graphow.orquestrador.saida_do_aceite import dentro_do_aceite, e_cache
from graphow.orquestrador.saidas import SaidaDoExecutor
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel
from graphow.orquestrador.suite import arquivos_ocultos, rodar_suite

STATUS_PRONTO: str = "pronto"
STATUS_DUVIDA: str = "duvida"
STATUS_TESTE_ERRADO: str = "teste_errado"
# A correção de um bloqueante é o trabalho que já falhou uma vez: roda no modelo mais forte.
MODELO_DA_CORRECAO: str = "opus"


@dataclass(frozen=True)
class Tentativa:
    """Uma tentativa em curso: a fatia, o número e o commit de onde ela partiu."""

    fatia: FatiaRegistrada
    numero: int
    head: str


def executar_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, fatia: FatiaRegistrada) -> Parada | None:
    """Roda uma tentativa da fatia; a parada diz por que o laço não segue."""
    if fatia.status == m.STATUS_EM_ANDAMENTO:
        entrega = fatia.propriedades.get(m.CAMPO_ENTREGA_PENDENTE)
        if _concluir_pelo_commit(contexto, fatia):
            return None
        if isinstance(entrega, Mapping) and _reaplicar(contexto, entrega):
            return _retomar_a_revisao(contexto, fatia, entrega)
        estado, fatia = _depois_da_interrupcao(contexto, fatia)
    if fatia.falhas >= MAXIMO_DE_FALHAS:
        return _esgotou(contexto, fatia, f"falhou {fatia.falhas} vezes; a ultima: {fatia.texto(m.CAMPO_ULTIMO_ERRO)[:500]}")
    numero = fatia.tentativas + 1
    sem_orcamento = contexto.sem_orcamento()
    if sem_orcamento is not None:
        return sem_orcamento
    tentativa = Tentativa(fatia, numero, contexto.git.head())
    contexto.livro.iniciar_tentativa(fatia.id, numero)
    resposta = contexto.sessoes.rodar(
        PedidoDePapel(
            papel=PAPEL_EXECUTOR, id_goal=contexto.id_goal, pasta=contexto.area, fatia=fatia.id, tentativa=numero,
            briefing=briefing_do_executor(estado, fatia, _contexto_da_fatia(contexto, estado, numero, fatia=fatia)),
            conferir=lambda dados: SaidaDoExecutor.de_json(dados).conferir(),
            modelo=_modelo(contexto, fatia), orcamento_restante_usd=contexto.restante(),
            esquema=ESQUEMA_DA_EXECUCAO_AUTONOMA if contexto.configuracao.modo == m.MODO_AUTONOMO else None,
        )
    )
    desfeito = resposta.desfeito
    if resposta.dados is None:
        return _falhou(contexto, tentativa, "a saida do executor nao conferiu: " + "; ".join(resposta.problemas))
    return _depois_da_sessao(contexto, tentativa, SaidaDoExecutor.de_json(resposta.dados), desfeito=desfeito)


def _depois_da_sessao(contexto: ContextoDoGoal, tentativa: Tentativa, saida: SaidaDoExecutor, *, desfeito: str) -> Parada | None:
    """Dúvida, falha ou entrega conferida pela suíte."""
    fatia = tentativa.fatia
    if saida.status == STATUS_DUVIDA:
        patch = _guardar(contexto, fatia, f"t{tentativa.numero}-duvida")
        contexto.livro.abrir_duvida(fatia.id, tentativa.numero, pergunta=saida.duvida, patch=patch, criterio_do_teste=saida.teste_errado)
        return None
    if saida.status == STATUS_TESTE_ERRADO and _pausar_para_refazer(contexto, tentativa, saida):
        return None
    if saida.status not in (STATUS_PRONTO, STATUS_TESTE_ERRADO):
        return _falhou(contexto, tentativa, f"o executor devolveu {saida.status}: {saida.resumo}")
    try:
        problema = _conferir_a_entrega(contexto, tentativa)
    except LimiteDaApi:
        _guardar_a_entrega(contexto, tentativa, saida)
        raise
    if isinstance(problema, Parada):
        return problema
    if isinstance(problema, RejeicaoDaRevisao):
        return _falhou(contexto, tentativa, problema.texto, nota=False)
    if problema:
        return _falhou(contexto, tentativa, problema)
    documentar_decisoes(contexto, fatia, saida.decisoes)
    commit = contexto.commitar(_mensagem(contexto, fatia, saida), vazio_permitido=True)
    contexto.livro.concluir_fatia(fatia.id, tentativa.numero, commit=commit, saida=saida, observacao=desfeito,
                                  achados=m.achados_da_correcao(fatia.propriedades),
                                  extra=operacoes_das_decisoes(contexto.livro, fatia.id, tentativa.numero, decisoes=saida.decisoes))
    return None


def _pausar_para_refazer(contexto: ContextoDoGoal, tentativa: Tentativa, saida: SaidaDoExecutor) -> bool:
    """O teste errado do modo autônomo: a fatia volta à fila e o laço pede o refazer, uma vez por critério; senão, segue."""
    fatia = tentativa.fatia
    refeitos = contexto.estado().propriedades.get(CAMPO_CRITERIOS_REFEITOS) or []
    if saida.teste_errado in refeitos:
        contexto.livro.gravar([propriedade(fatia.id, CAMPO_DESACORDO, {"criterio": saida.teste_errado, "argumento": saida.duvida})],
                              f"Desacordo sobre o teste de aceite de {saida.teste_errado} na fatia {fatia.id}")
        return False
    patch = _guardar(contexto, fatia, f"t{tentativa.numero}-teste-errado")
    pedido = {"id": f"{PREFIXO_DO_PEDIDO_AUTOMATICO}{fatia.id}-t{tentativa.numero}", "criterio": saida.teste_errado,
              "argumento": saida.duvida, "tentativa": tentativa.numero}
    contexto.livro.gravar([propriedade(fatia.id, CAMPO_TESTE_ERRADO, pedido), propriedade(fatia.id, m.CAMPO_PATCH, patch),
                           propriedade(fatia.id, m.CAMPO_STATUS, m.STATUS_PENDENTE)],
                          f"O executor da fatia {fatia.id} diz que o teste de aceite de {saida.teste_errado} esta errado")
    return True


def _depois_da_interrupcao(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> tuple[EstadoDoGoal, FatiaRegistrada]:
    """A tentativa interrompida conta como falha; devolve o estado e a fatia relidos."""
    _registrar_interrupcao(contexto, fatia)
    estado = contexto.estado()
    return estado, next(registrada for registrada in estado.fatias if registrada.id == fatia.id)


def _guardar_a_entrega(contexto: ContextoDoGoal, tentativa: Tentativa, saida: SaidaDoExecutor) -> None:
    """A API recusou a revisão de risco: o que o executor entregou vai a um .patch, e a fatia o guarda com a saída dele."""
    patch = contexto.patch(f"{tentativa.fatia.id}-t{tentativa.numero}-entrega")
    guardar_patch(contexto.area, patch)
    contexto.git.rodar("reset", "-q")
    contexto.livro.guardar_entrega(tentativa.fatia.id, {"patch": str(patch), "saida": asdict(saida), "tentativa": tentativa.numero})


def _reaplicar(contexto: ContextoDoGoal, entrega: Mapping[str, Any]) -> bool:
    """A entrega guardada volta à área limpa; falso quando o .patch se perdeu ou não aplica mais."""
    patch = Path(str(entrega.get("patch", "")))
    if not patch.is_file():
        return False
    descartar_mudancas(contexto.area, contexto.patch("antes-da-entrega-guardada"))
    return patch.stat().st_size == 0 or contexto.git.tentar("apply", "--binary", str(patch)).codigo == 0


def _retomar_a_revisao(contexto: ContextoDoGoal, fatia: FatiaRegistrada, entrega: Mapping[str, Any]) -> Parada | None:
    """A tentativa que esperava a revisão quando a API a recusou: sem outro executor, confere e revisa de novo a mesma entrega."""
    numero = int(entrega.get("tentativa") or fatia.tentativas)
    saida = SaidaDoExecutor.de_json(entrega.get("saida") or {"status": STATUS_PRONTO, "resumo": ""})
    tentativa = Tentativa(fatia, numero, contexto.git.head())
    return _depois_da_sessao(contexto, tentativa, saida, desfeito="retomada: a entrega esperava a revisao de risco quando a API a recusou")


def _conferir_a_entrega(contexto: ContextoDoGoal, tentativa: Tentativa) -> str | Parada | RejeicaoDaRevisao:
    """Os testes de aceite intocados, a suíte verde sem eles e, na fatia de risco, a revisão; vazio quando tudo passa."""
    estado = contexto.estado()
    problema, configuracao = _conferir_o_que_mudou(contexto, estado, tentativa)
    if problema:
        return problema
    plano = estado.plano or {}
    with arquivos_ocultos(contexto.area, estado.arquivos_protegidos(), contexto.pasta / "aceite-oculto"):
        suite = rodar_suite(
            contexto.area, str(plano.get("comando_suite", "")), contexto.banco_descartavel,
            tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s,
        )
    if not suite.passou:
        return suite.descrever()
    motivo = de_risco(tentativa.fatia) or _sinal_da_configuracao(tentativa.fatia, configuracao)
    return revisar_fatia(contexto, estado, PedidoDeRevisao(tentativa.fatia, tentativa.numero, motivo)) if motivo else ""


def _conferir_o_que_mudou(contexto: ContextoDoGoal, estado: EstadoDoGoal, tentativa: Tentativa) -> tuple[str, tuple[str, ...]]:
    """O problema do que a fatia mudou (flags, sombra do runner, hook que decide, aceite/) e a configuração de teste mudada, que é só sinal.

    A mudança de configuração de teste não é recusada: o aceite roda com ela
    e com a do commit do aceite, e a diferença vai ao verificador
    (orquestrador/aceite_no_commit.py); a fatia vai à revisão de risco.
    """
    sinalizados = flags_do_indice(contexto.area)
    if sinalizados:
        limpar_flags(contexto.area, sinalizados)
        return (f"a fatia escondeu do git os arquivos {', '.join(sinalizados)} com skip-worktree ou assume-unchanged: o "
                "orquestrador tirou as flags, e a tentativa nao vale (git update-index nao e do executor)"), ()
    mudados = contexto.git.caminhos_mudados()
    sombras = tirar_sombras_do_runner(contexto.area, mudados, antes=tentativa.head)
    if sombras:
        return _sombreou_o_runner(sombras), ()
    decidem = conftests_que_decidem_o_resultado(contexto.area, mudados, antes=tentativa.head)
    if decidem:
        return _decide_o_resultado(decidem), ()
    soltos = soltos_que_mudam_os_testes(contexto.area)
    no_aceite = sorted({c for c in (*mudados, *soltos) if dentro_do_aceite(c) and not e_cache(c)}
                       | (set(mudados) & set(estado.arquivos_protegidos())))
    if no_aceite:
        return _mexeu_no_aceite(no_aceite), ()
    configuracao = (*configuracoes_mudadas(contexto.area, mudados, antes=tentativa.head), *sorted(set(soltos) - set(mudados)))
    return "", configuracao


def _sinal_da_configuracao(fatia: FatiaRegistrada, configuracao: tuple[str, ...]) -> str:
    """O motivo da revisão da fatia que mudou a configuração de teste, dizendo o que o plano não declarou."""
    if not configuracao:
        return ""
    fora = [caminho for caminho in configuracao if caminho not in fatia.lista(m.CAMPO_ARQUIVOS_ALVO)]
    nao_declarada = f"; o plano nao declarou {', '.join(fora)}" if fora else ""
    return f"muda a configuracao de teste ({', '.join(configuracao)}){nao_declarada}"


def _sombreou_o_runner(sombras: tuple[str, ...]) -> str:
    """O erro da fatia que criou arquivo ou pasta com o nome do módulo de um runner de testes."""
    return (
        f"a fatia criou {', '.join(sombras)}, com o nome do modulo de um runner de testes ou de um que ele importa (pytest, "
        "_pytest, pluggy, iniconfig, packaging, unittest): numa pasta do sys.path ele toma o lugar do runner, e um pytest.py "
        "que imprime '1 passed' daria verde. O orquestrador os "
        "apagou, e a tentativa nao vale: de outro nome ao modulo."
    )


def _decide_o_resultado(conftests: Mapping[str, tuple[str, ...]]) -> str:
    """O erro da fatia que criou ou mudou um conftest.py com hook do pytest que decide o resultado do teste."""
    lista = "; ".join(f"{caminho} ({', '.join(hooks)})" for caminho, hooks in conftests.items())
    return (
        f"a fatia criou ou mudou conftest.py com hook do pytest que decide o resultado do teste: {lista}. Um "
        "pytest_pyfunc_call que devolve True da verde a qualquer teste, a soma errada inclusive. O orquestrador recusa esse "
        "conftest sempre (o novo saiu do disco), e a tentativa nao vale: prepare os testes por fixture, sem esses hooks."
    )


def _mexeu_no_aceite(mexidos: list[str]) -> str:
    """O erro da fatia que alterou, apagou ou moveu teste de aceite."""
    return (
        f"a fatia alterou, apagou, moveu ou criou em aceite/ os arquivos {', '.join(mexidos)}: o executor nao toca os testes de aceite, eles provam os "
        "criterios e foram escritos antes, por outra sessao. Se um teste de aceite esta errado, diga o criterio em `teste_errado` "
        "e o porque em `duvida`."
    )


def _falhou(contexto: ContextoDoGoal, tentativa: Tentativa, erro: str, *, nota: bool = True) -> Parada | None:
    """A tentativa falhou: o que ela deixou vai para um .patch; na segunda, a fatia vira pendência."""
    fatia = tentativa.fatia
    patch = _guardar(contexto, fatia, f"t{tentativa.numero}")
    falhas = fatia.falhas + 1
    contexto.livro.registrar_falha(fatia.id, tentativa.numero, erro=erro, patch=patch, falhas=falhas, nota=nota)
    if falhas < MAXIMO_DE_FALHAS:
        return None
    return _esgotou(contexto, fatia, f"falhou {falhas} vezes; a ultima: {erro[:500]}")


def _esgotou(contexto: ContextoDoGoal, fatia: FatiaRegistrada, motivo: str) -> Parada | None:
    """A fatia gastou as tentativas: a correção agrupada se divide numa fatia por achado; a outra vira pendência."""
    estado = contexto.estado()
    achados = [achado for id_achado in m.achados_da_correcao(fatia.propriedades) if (achado := estado.achado(id_achado))]
    if len(achados) > 1:
        contexto.livro.dividir_correcao(fatia, achados)
        return None
    return _virar_pendencia(contexto, fatia, motivo)


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


def guardar_a_fatia_interrompida(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> EstadoDoGoal:
    """Antes do pedido do humano, a fatia que caiu no meio da sessão é tratada como na retomada; devolve o estado relido.

    A tentativa conta como falha, e o que ela deixou vai ao .patch dela e sai
    da área. Sem isso, o autor que refazia um critério trabalhava na área com
    a metade do executor e levava a culpa por ela (sonda 3 da revisão da
    T2i+T2g). A fatia com o commit na branch e a que guardou a entrega para a
    revisão ficam para a retomada: nada delas está solto na área.
    """
    caidas = [fatia for fatia in estado.fatias if fatia.status == m.STATUS_EM_ANDAMENTO
              and not fatia.propriedades.get(m.CAMPO_ENTREGA_PENDENTE)
              and commit_da_fatia(contexto.area, fatia.id, contexto.configuracao.base) is None]
    for fatia in caidas:
        _registrar_interrupcao(contexto, fatia)
    return contexto.estado() if caidas else estado


def _registrar_interrupcao(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> None:
    """A tentativa que estava em andamento quando o laço parou conta como falha, e a área volta ao commit."""
    patch = _guardar(contexto, fatia, f"t{fatia.tentativas}-interrompida")
    erro = "a tentativa anterior foi interrompida no meio (o orquestrador parou antes de ela terminar)"
    contexto.livro.registrar_falha(fatia.id, fatia.tentativas, erro=erro, patch=patch, falhas=fatia.falhas + 1)


def _guardar(contexto: ContextoDoGoal, fatia: FatiaRegistrada, sufixo: str) -> str:
    """O que está fora de commit vai para o .patch da tentativa; devolve o caminho, ou vazio sem nada."""
    caminho = contexto.patch(f"{fatia.id}-{sufixo}")
    return str(caminho) if descartar_mudancas(contexto.area, caminho) else ""


def _contexto_da_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, numero: int, *, fatia: FatiaRegistrada) -> ContextoDaFatia:
    """Os commits do Goal desde a base, o diff resumido do último e, na correção, as tentativas anteriores da mesma área."""
    git = contexto.git
    entregues = git.commits_desde(contexto.configuracao.base)
    diff = git.resumo_do_diff("HEAD~1", "HEAD") if entregues else ""
    return ContextoDaFatia(tentativa=numero, entregues=tuple(f"- {linha}" for linha in entregues), diff_da_anterior=diff,
                           correcoes_anteriores=tentativas_anteriores(git, estado, fatia))


def _modelo(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> str:
    """O modelo do executor: o configurado, ou o que o plano sugeriu quando a configuração pede; a correção, sempre Opus."""
    if fatia.texto(m.CAMPO_CORRIGE):
        return MODELO_DA_CORRECAO
    configurado = contexto.sessoes.modelo_do_papel(PAPEL_EXECUTOR)
    return fatia.texto(m.CAMPO_MODELO) or "opus" if configurado == "sugerido" else configurado


def _mensagem(contexto: ContextoDoGoal, fatia: FatiaRegistrada, saida: SaidaDoExecutor) -> str:
    """A mensagem do commit: a fatia, os critérios, o que o executor fez e os trailers do Goal e da Task."""
    criterios = ", ".join(fatia.lista(m.CAMPO_CRITERIOS))
    titulo = fatia.titulo.split(": ", 1)[-1]
    assunto = f"Fatia {fatia.codigo}: {titulo}" + (f" ({criterios})" if criterios else "")
    return mensagem_do_orquestrador(assunto, saida.resumo, id_goal=contexto.id_goal, id_task=fatia.id)


def _concluir_pelo_commit(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> bool:
    """A tentativa interrompida depois do commit dela: o commit está na branch, e a fatia fecha sem nova sessão."""
    commit = commit_da_fatia(contexto.area, fatia.id, contexto.configuracao.base)
    if commit is None:
        return False
    resumo = commit.mensagem.split("\n\n")[1] if commit.mensagem.count("\n\n") >= 2 else ""
    saida = SaidaDoExecutor(STATUS_PRONTO, resumo, arquivos_do_commit(contexto.area, commit.hash))
    observacao = "retomada: o commit da fatia ja estava na branch quando o orquestrador parou"
    contexto.livro.concluir_fatia(fatia.id, fatia.tentativas, commit=commit.hash, saida=saida, observacao=observacao,
                                  achados=m.achados_da_correcao(fatia.propriedades))
    return True
