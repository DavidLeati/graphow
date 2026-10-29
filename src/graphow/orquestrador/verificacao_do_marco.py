"""A verificação de um marco: uma sessão nova do verificador, a suíte que o orquestrador roda e o registro no livro-razão.

Ao fim de cada marco, com as fatias dele concluídas, o orquestrador roda no
commit atual os testes de aceite dos critérios que os marcos até este
completaram (os dos marcos anteriores, como regressão; na final, também o
comando de todos e, num comando só, a suíte com todos os testes de aceite),
com `aceite/` de volta ao commit do aceite e sem arquivo solto nele
(orquestrador/aceite_intocado.py), com a configuração entregue e, se ela
mudou, também com a do commit do aceite (orquestrador/aceite_no_commit.py).
Depois, uma sessão nova do verificador confere a entrega: julga os critérios
que o marco completou (no último marco, a verificação final, todos os
critérios e todas as decisões, sobre o Goal inteiro), roda a suíte e o
programa, sonda as bordas e dá um parecer sobre cada diferença entre as duas
configurações que o código não decidiu sozinho (orquestrador/aceite_no_commit.py).
Os comandos que ele rodou o orquestrador tira do stream da sessão,
com o código de saída e um trecho da saída, e grava na verificação. Por fim o
orquestrador roda a suíte do plano (sem os testes de aceite): a suíte vermelha
é bloqueante, e o teste de aceite vermelho com a configuração entregue reprova
o critério dele e vira Achado bloqueante, diga o verificador o que disser. O
aceite roda antes da sessão, que não o alcança; o que ela deixar em `aceite/`
sai antes da suíte. Antes do aceite, o que estiver fora de commit sai da área:
o processo que caiu no meio da rodada com a configuração do commit do aceite
deixou a área com ela, e a retomada rodaria a rodada "entregue" com a errada.

A sessão é de um dos três tipos (orquestrador/tipo_da_verificacao.py): a do
marco intermediário e a caçada da primeira final, com o briefing inteiro, e a
conferência de depois de cada correção, com o briefing curto dela; o tipo vai
na Evidence.

Num marco intermediário o parecer sobre um critério que só um marco seguinte
completa não conta, e o achado não pode tocar esse critério: ele ainda não foi
construído. A verificação, os Achados e as pendências vão ao livro-razão num
lote só (orquestrador/gravacao_da_verificacao.py), e o documento do Goal é
sincronizado com as pendências num commit só dele, pelo caminho. O que a
suíte escreve sai da área logo depois dela (orquestrador/suite_sem_rastro.py):
na sonda L2 da revisão da T2k+T2l, o conftest.py que ela gerava ia à base no
commit das pendências, que levava a área inteira.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from graphow.core import aceite as a
from graphow.orquestrador.aceite_intocado import preparar_o_aceite
from graphow.orquestrador.aceite_no_commit import AceiteNoCommit, rodar_o_aceite
from graphow.orquestrador.briefing import PedidoDaConferencia, briefing_da_conferencia, briefing_do_verificador
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.diff_das_correcoes import diff_das_correcoes
from graphow.orquestrador.documento_do_goal import caminho_do_documento, com_pendencias, gravar_se_mudou
from graphow.orquestrador.git_do_goal import descartar_mudancas, mensagem_do_orquestrador
from graphow.orquestrador.gravacao_da_verificacao import RegistroDaVerificacao, gravar_verificacao
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, MarcoRegistrado
from graphow.orquestrador.saida_do_aceite import TESTE_DA_SUITE_COM_O_ACEITE, ExecucaoDeAceite
from graphow.orquestrador.comandos_do_stream import chamadas_bash
from graphow.orquestrador.saida_do_verificador import TITULO_DA_SUITE_VERMELHA, ComandoRodado, Verificacao, conferir_verificacao
from graphow.orquestrador.segunda_opiniao import com_a_segunda_opiniao
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel
from graphow.orquestrador.suite import LIMITE_DO_TRECHO, ResultadoDaSuite, arquivos_ocultos, rodar_suite
from graphow.orquestrador.suite_sem_rastro import sem_o_que_a_suite_escreve
from graphow.orquestrador.tipo_da_verificacao import TipoDaVerificacao, escolher_o_tipo


def verificar_marco(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada | None:
    """Uma sessão nova do verificador no commit atual e a suíte do plano, gravadas como Evidence do Goal."""
    sem_orcamento = contexto.sem_orcamento()
    if sem_orcamento is not None:
        return sem_orcamento
    head, plano, commit_do_aceite = contexto.git.head(), estado.plano or {}, str((estado.aceite or {}).get("commit", ""))
    descartar_mudancas(contexto.area, contexto.patch(f"antes-da-verificacao-{len(estado.verificacoes) + 1}"))
    tirado = preparar_o_aceite(contexto.area, commit_do_aceite)
    aceite = rodar_o_aceite(contexto, estado, criterios_ate_o_marco(estado, marco), final=marco.final)
    descartar_mudancas(contexto.area, contexto.patch(f"aceite-{len(estado.verificacoes) + 1}"))
    tipo = escolher_o_tipo(estado, marco, contexto.git)
    dados = _sessao_do_verificador(contexto, estado, marco, head=head, aceite=aceite, tipo=tipo)
    if isinstance(dados, Parada):
        return dados
    tirado = (*tirado, *preparar_o_aceite(contexto.area, commit_do_aceite))
    rastro = contexto.patch(f"suite-{len(estado.verificacoes) + 1}")
    with sem_o_que_a_suite_escreve(contexto.area, rastro), arquivos_ocultos(
            contexto.area, estado.arquivos_protegidos(), contexto.pasta / "aceite-oculto"):
        suite = rodar_suite(contexto.area, str(plano.get("comando_suite", "")), contexto.banco_descartavel,
                            tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s)
    registro = _registro(contexto, estado, marco, dados=dados, suite=suite, aceite=aceite, head=head, tirado=tirado, tipo=tipo)
    gravar_verificacao(contexto.livro, registro)
    sincronizar_documento(contexto, registro.pendencias, numero=registro.numero)
    return None


def _registro(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado, *,
    dados: tuple[Mapping[str, Any], tuple[ComandoRodado, ...]], suite: ResultadoDaSuite, aceite: AceiteNoCommit, head: str,
    tirado: Sequence[str], tipo: TipoDaVerificacao,
) -> RegistroDaVerificacao:
    """A verificação julgada, com a suíte e o aceite do orquestrador, a segunda opinião e, na conferência, a regra dela.

    O que o orquestrador viu (a suíte, o aceite) entra antes do destino que a
    conferência dá a cada achado: a regressão só se confirma quando o critério
    atendia ou viraria `atende`, e o teste de aceite vermelho o impede. Por
    último, o que ela reprova e a regra dá por `atende` sai `atende`
    (orquestrador/regra_da_conferencia.py).
    """
    saida, chamadas = dados
    lida = replace(_so_o_que_o_marco_julga(Verificacao.de_json(saida), estado, marco), comandos=chamadas)
    if not suite.passou:
        lida = lida.com_achado_do_orquestrador(TITULO_DA_SUITE_VERMELHA, suite.descrever()[-LIMITE_DO_TRECHO:])
    julgada = tipo.ajustar(aceite.julgar(_com_o_aceite(lida, aceite.execucoes)))
    verificacao = tipo.sustentar(com_a_segunda_opiniao(contexto, julgada, textos=_textos_julgaveis(estado, marco)))
    registro = RegistroDaVerificacao(
        numero=len(estado.verificacoes) + 1, commit=head, verificacao=verificacao,
        commit_do_codigo=contexto.commit_do_codigo(), suite=suite, nos=nos_do_plano(estado.plano or {}),
        ciclo=estado.ciclos_do_marco(marco), final=marco.final, marco=marco.id,
        aceite=[execucao.em_json() for execucao in aceite.execucoes], resolver=estado.corrigidos(marco, verificacao.confirmados),
        tirado_antes_do_aceite=tuple(dict.fromkeys(tirado)), configuracao_do_aceite=aceite.trocados,
        aceite_com_a_configuracao_do_aceite=[execucao.em_json() for execucao in aceite.com_a_do_aceite],
        diferencas_de_configuracao=aceite.diferencas_em_json(verificacao.diferencas), tipo=tipo.tipo,
    )
    return replace(registro, pendencias=_pendencias_depois(estado, registro, marco, id_goal=contexto.id_goal))


def _com_o_aceite(verificacao: Verificacao, execucoes: Sequence[ExecucaoDeAceite]) -> Verificacao:
    """O teste de aceite vermelho reprova o critério dele, diga o verificador o que disser, e vira Achado bloqueante.

    O comando de todos, ou a suíte junto com o aceite, que falha só vira
    Achado próprio quando nenhum teste sozinho falhou, e só o primeiro deles:
    senão é a mesma falha, contada duas ou três vezes.
    """
    algum_criterio = any(not e.passou for e in execucoes if e.criterio)
    juntos = [] if algum_criterio else [e for e in execucoes if not e.criterio and not e.passou][:1]
    for execucao in (*(e for e in execucoes if e.criterio and not e.passou), *juntos):
        verificacao = _com_a_falha(verificacao, execucao)
    return verificacao


def _com_a_falha(verificacao: Verificacao, execucao: ExecucaoDeAceite) -> Verificacao:
    """A execução que não passou como Achado do orquestrador; a do teste de um critério reprova o critério."""
    situacao = execucao.motivo
    descricao = f"`{execucao.comando}` nao passou no commit verificado: {situacao}. Fim da saida:\n{execucao.saida[-LIMITE_DO_TRECHO:]}"
    if not execucao.criterio:
        juntos = execucao.teste == TESTE_DA_SUITE_COM_O_ACEITE
        titulo = "A suite e os testes de aceite juntos falharam" if juntos else "O comando de aceite falhou"
        return verificacao.com_achado_do_orquestrador(f"{titulo} no commit verificado", descricao)
    prova = f"o teste de aceite {execucao.teste} nao passou ({situacao}) quando o orquestrador o rodou"
    verificacao = verificacao.com_parecer(execucao.criterio, a.VEREDITO_NAO_ATENDE, prova)
    titulo = f"O teste de aceite {execucao.teste} de {execucao.criterio} falhou"
    return verificacao.com_achado_do_orquestrador(titulo, descricao, (execucao.criterio,))


def criterios_ate_o_marco(estado: EstadoDoGoal, marco: MarcoRegistrado) -> tuple[str, ...]:
    """Os critérios que os marcos até este, inclusive, completaram: os que já podem ser julgados ou feridos."""
    marcos = estado.marcos()
    ids = [item.id for item in marcos]
    ate = marcos[: ids.index(marco.id) + 1] if marco.id in ids else (marco,)
    return tuple(dict.fromkeys(criterio for item in ate for criterio in item.criterios))


def _textos_julgaveis(estado: EstadoDoGoal, marco: MarcoRegistrado) -> dict[str, str]:
    """O texto de cada critério que os marcos até este completaram e de cada decisão do plano, pelo código."""
    plano = estado.plano or {}
    validos = set(criterios_ate_o_marco(estado, marco))
    criterios = {str(c["id"]): str(c.get("texto", "")) for c in plano.get("criterios", []) if str(c["id"]) in validos}
    return {**criterios, **{str(d["id"]): str(d.get("texto", "")) for d in plano.get("decisoes", [])}}


def decisoes_do_plano(estado: EstadoDoGoal) -> tuple[str, ...]:
    """Os ids das decisões do plano."""
    return tuple(str(d["id"]) for d in (estado.plano or {}).get("decisoes", []))


def _so_o_que_o_marco_julga(verificacao: Verificacao, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Verificacao:
    """A verificação sem os pareceres de critérios que só um marco seguinte completa."""
    validos = set(criterios_ate_o_marco(estado, marco))
    return replace(verificacao, criterios=tuple(parecer for parecer in verificacao.criterios if parecer.id in validos))


def nos_do_plano(plano: Mapping[str, Any]) -> dict[str, str]:
    """O nó do livro-razão de cada critério e decisão do plano, pelo código."""
    itens = [*plano.get("criterios", []), *plano.get("decisoes", [])]
    return {str(item["id"]): str(item.get("no", "")) for item in itens if isinstance(item, Mapping)}


def _sessao_do_verificador(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado, *, head: str, aceite: AceiteNoCommit,
    tipo: TipoDaVerificacao,
) -> tuple[Mapping[str, Any], tuple[ComandoRodado, ...]] | Parada:
    """A saída conferida do verificador do tipo dado e as chamadas Bash que o stream dele mostra; ou a parada.

    A sessão roda num contexto novo e não deixa mudança na área. Os comandos
    da verificação saem do stream, com o código e o trecho da saída: o
    verificador não os declara, e nada volta a ele por isso.
    """
    decisoes = decisoes_do_plano(estado)
    exigidas = decisoes if marco.final else ()
    conhecidos = criterios_ate_o_marco(estado, marco)
    numero = len(estado.verificacoes) + 1
    resposta = contexto.sessoes.rodar(
        PedidoDePapel(
            papel=tipo.papel, id_goal=contexto.id_goal, pasta=contexto.area, tentativa=numero,
            briefing=_briefing(contexto, estado, marco, head=head, aceite=aceite, tipo=tipo),
            conferir=lambda dados: conferir_verificacao(
                Verificacao.de_json(dados), marco.criterios, exigidas, conhecidos=(*conhecidos, *decisoes),
                diferencas=aceite.chaves_a_julgar(), conferidos=tipo.ids_dos_conferidos, excedentes=tipo.ids_dos_excedentes,
            ),
            orcamento_restante_usd=contexto.restante(), exige_bash=True,
        )
    )
    descartar_mudancas(contexto.area, contexto.patch(f"verificador-{numero}"))
    if resposta.dados is None:
        return Parada(contexto.id_goal, MotivoDaParada.FALHA, "A verificacao nao conferiu: " + "; ".join(resposta.problemas))
    chamadas = chamadas_bash(resultado.arquivo_stream for resultado in resposta.resultados)
    return resposta.dados, tuple(ComandoRodado(c.comando, c.codigo, c.saida) for c in chamadas)


def _briefing(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado, *, head: str, aceite: AceiteNoCommit,
    tipo: TipoDaVerificacao,
) -> str:
    """O briefing inteiro da caçada e do marco, ou o curto da conferência, com o diff das correções."""
    if not tipo.conferencia:
        return briefing_do_verificador(estado, head, contexto.git.commits_desde(contexto.configuracao.base), marco=marco,
                                       diferencas=aceite.para_o_verificador())
    diff = diff_das_correcoes(contexto.git, tipo.antes, contexto.configuracao.slug)
    pedido = PedidoDaConferencia(tipo.conferidos, tipo.antes, diff, aceite.para_o_verificador(), tipo.excedentes)
    return briefing_da_conferencia(estado, head, marco=marco, pedido=pedido)


def _pendencias_depois(
    estado: EstadoDoGoal, registro: RegistroDaVerificacao, marco: MarcoRegistrado, *, id_goal: str
) -> list[dict[str, Any]]:
    """As pendências de antes, mais os acompanhamentos desta verificação (e os bloqueantes, se o marco não tem mais ciclo), sem repetir.

    O acompanhamento que uma verificação anterior achou continua pendência,
    ache-o a seguinte ou não; o mesmo título no mesmo local não entra duas vezes.
    """
    sem_ciclo = estado.ciclos_do_marco(marco) >= estado.limite_de_ciclos(marco)
    novas = [
        {**achado.em_json(), "achado": id_achado, "origem": f"verificacao {registro.numero}"}
        for id_achado, achado in registro.achados(id_goal)
        if sem_ciclo or achado.gravidade == a.GRAVIDADE_ACOMPANHAMENTO
    ]
    vistas: set[tuple[str, str]] = set()
    pendencias: list[dict[str, Any]] = []
    for item in [*estado.pendencias, *novas]:
        chave = (str(item.get("titulo", "")).strip().lower(), str(item.get("local", "")).strip())
        if chave not in vistas:
            vistas.add(chave)
            pendencias.append(dict(item))
    return pendencias


def sincronizar_documento(contexto: ContextoDoGoal, pendencias: Sequence[Mapping[str, Any]], *, numero: int) -> None:
    """Reescreve a seção de pendências do documento como o livro-razão a tem e commita só ele, pelo caminho, se ele mudou."""
    documento = caminho_do_documento(contexto.configuracao.slug)
    caminho = contexto.area / documento
    if not caminho.is_file():
        return
    if not gravar_se_mudou(caminho, com_pendencias(caminho.read_text(encoding="utf-8"), pendencias)) or not contexto.git.mudancas(documento):
        return
    assunto = f"Registra as pendencias da verificacao {numero} do Goal {contexto.configuracao.slug}"
    contexto.commitar(mensagem_do_orquestrador(assunto, "", id_goal=contexto.id_goal), caminhos=(documento,))
