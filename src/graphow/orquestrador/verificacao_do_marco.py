"""A verificação de um marco: uma sessão nova do verificador, a suíte que o orquestrador roda e o registro no livro-razão.

Ao fim de cada marco, com as fatias dele concluídas, uma sessão nova do
verificador confere a entrega no commit atual: julga os critérios que o marco
completou (no último marco, a verificação final, todos os critérios e todas as
decisões, sobre o Goal inteiro), roda a suíte e o programa e sonda as bordas.
Lista os comandos que rodou, e cada um tem de aparecer nas chamadas Bash do
stream da sessão. Depois o próprio orquestrador roda nesse commit a suíte do
plano (sem os testes de aceite) e os testes de aceite dos critérios que os
marcos até este completaram (os dos marcos anteriores, como regressão; na
final, também o comando de todos e, num comando só, a suíte com todos os
testes de aceite), com `aceite/` de volta ao
commit do aceite e sem configuração de teste solta na área
(orquestrador/aceite_intocado.py): a suíte vermelha é
bloqueante, e o teste de aceite vermelho reprova o critério dele e vira Achado
bloqueante, diga o verificador o que disser.

Num marco intermediário o parecer sobre um critério que só um marco seguinte
completa não conta, e o achado não pode tocar esse critério: ele ainda não foi
construído. A verificação, os Achados e as pendências vão ao livro-razão num
lote só (orquestrador/gravacao_da_verificacao.py), e o documento do Goal é
sincronizado com as pendências num commit só dele.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from graphow.core import aceite as a
from graphow.orquestrador.aceite_intocado import preparar_o_aceite
from graphow.orquestrador.briefing import briefing_do_verificador
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.documento_do_goal import caminho_do_documento, com_pendencias
from graphow.orquestrador.esquemas import PAPEL_VERIFICADOR
from graphow.orquestrador.git_do_goal import descartar_mudancas, mensagem_do_orquestrador
from graphow.orquestrador.gravacao_da_verificacao import RegistroDaVerificacao, gravar_verificacao
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, MarcoRegistrado
from graphow.orquestrador.saida_do_aceite import (
    TESTE_DA_SUITE_COM_O_ACEITE,
    ExecucaoDeAceite,
    SaidaDoAceite,
    rodar_a_suite_com_o_aceite,
    rodar_o_comando_de_aceite,
    rodar_testes,
)
from graphow.orquestrador.saida_do_verificador import TITULO_DA_SUITE_VERMELHA, Verificacao, conferir_verificacao
from graphow.orquestrador.segunda_opiniao import com_a_segunda_opiniao
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel
from graphow.orquestrador.suite import LIMITE_DO_TRECHO, ResultadoDaSuite, arquivos_ocultos, rodar_suite


def verificar_marco(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada | None:
    """Uma sessão nova do verificador no commit atual e a suíte do plano, gravadas como Evidence do Goal."""
    sem_orcamento = contexto.sem_orcamento()
    if sem_orcamento is not None:
        return sem_orcamento
    head = contexto.git.head()
    dados = _sessao_do_verificador(contexto, estado, marco, head=head)
    if isinstance(dados, Parada):
        return dados
    plano = estado.plano or {}
    tirado = preparar_o_aceite(contexto.area, str((estado.aceite or {}).get("commit", "")))
    with arquivos_ocultos(contexto.area, estado.arquivos_protegidos(), contexto.pasta / "aceite-oculto"):
        suite = rodar_suite(contexto.area, str(plano.get("comando_suite", "")), contexto.banco_descartavel,
                            tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s)
    verificacao = com_a_segunda_opiniao(contexto, _so_o_que_o_marco_julga(Verificacao.de_json(dados), estado, marco),
                                        textos=_textos_julgaveis(estado, marco))
    if not suite.passou:
        verificacao = verificacao.com_achado_do_orquestrador(TITULO_DA_SUITE_VERMELHA, suite.descrever()[-LIMITE_DO_TRECHO:])
    execucoes = _aceite_no_commit(contexto, estado, marco)
    registro = RegistroDaVerificacao(
        numero=len(estado.verificacoes) + 1, verificacao=_com_o_aceite(verificacao, execucoes), commit=head,
        commit_do_codigo=contexto.commit_do_codigo(), suite=suite, nos=nos_do_plano(plano), ciclo=estado.ciclos_do_marco(marco),
        final=marco.final, marco=marco.id, aceite=[execucao.em_json() for execucao in execucoes], resolver=estado.corrigidos(marco),
        tirado_antes_do_aceite=tirado,
    )
    registro = replace(registro, pendencias=_pendencias_depois(estado, registro, marco, id_goal=contexto.id_goal))
    gravar_verificacao(contexto.livro, registro)
    sincronizar_documento(contexto, registro.pendencias, numero=registro.numero)
    return None


def _aceite_no_commit(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> tuple[ExecucaoDeAceite, ...]:
    """Os testes de aceite dos marcos até este, rodados pelo orquestrador; na final, também o comando de todos e a suíte junto."""
    aceite = SaidaDoAceite.do_livro(estado.aceite)

    def rodar(comando: str) -> ResultadoDaSuite:
        return rodar_suite(contexto.area, comando, contexto.banco_descartavel, tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s)

    execucoes = rodar_testes(aceite, rodar, criterios_ate_o_marco(estado, marco))
    if not (marco.final and execucoes):
        return execucoes
    comando_suite = str((estado.plano or {}).get("comando_suite", ""))
    return (*execucoes, rodar_o_comando_de_aceite(aceite, rodar), rodar_a_suite_com_o_aceite(aceite, comando_suite, rodar))


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
    contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado, *, head: str
) -> Mapping[str, Any] | Parada:
    """A saída conferida do verificador, que roda numa sessão nova e não deixa mudança na área; ou a parada."""
    decisoes = decisoes_do_plano(estado)
    exigidas = decisoes if marco.final else ()
    conhecidos = criterios_ate_o_marco(estado, marco)
    numero = len(estado.verificacoes) + 1
    resposta = contexto.sessoes.rodar(
        PedidoDePapel(
            papel=PAPEL_VERIFICADOR, id_goal=contexto.id_goal, pasta=contexto.area, tentativa=numero,
            briefing=briefing_do_verificador(estado, head, contexto.git.commits_desde(contexto.configuracao.base), marco=marco),
            conferir=lambda dados: conferir_verificacao(
                Verificacao.de_json(dados), marco.criterios, exigidas, conhecidos=(*conhecidos, *decisoes)
            ),
            comandos_declarados=lambda dados: [str(comando.get("comando", "")) for comando in dados.get("comandos", [])],
            orcamento_restante_usd=contexto.restante(),
        )
    )
    descartar_mudancas(contexto.area, contexto.patch(f"verificador-{numero}"))
    if resposta.dados is None:
        return Parada(contexto.id_goal, MotivoDaParada.FALHA, "A verificacao nao conferiu: " + "; ".join(resposta.problemas))
    return resposta.dados


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
    """Reescreve a seção de pendências do documento como o livro-razão a tem e commita, se ele mudou."""
    caminho = contexto.area / caminho_do_documento(contexto.configuracao.slug)
    if not caminho.is_file():
        return
    atual = caminho.read_text(encoding="utf-8")
    novo = com_pendencias(atual, pendencias)
    if novo == atual:
        return
    caminho.write_text(novo, encoding="utf-8", newline="\n")
    assunto = f"Registra as pendencias da verificacao {numero} do Goal {contexto.configuracao.slug}"
    contexto.commitar(mensagem_do_orquestrador(assunto, "", id_goal=contexto.id_goal))
