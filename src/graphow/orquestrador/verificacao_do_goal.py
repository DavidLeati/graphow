"""Os passos do fim: a verificação adversarial do Goal, as fatias de correção e o fechamento.

Com as fatias concluídas, uma sessão nova do verificador confere a entrega no
commit atual e lista os comandos que rodou, com o código e um trecho da saída;
depois o próprio orquestrador roda a suíte do plano nesse commit, e a suíte
vermelha é bloqueante, diga o verificador o que disser. A verificação vira
Evidence ligada ao Goal, com os comandos e a suíte; cada bloqueante vira
fatia de correção, até dois ciclos; os acompanhamentos vão para a seção de
pendências do documento do Goal, num commit só desse documento. O Goal só
fecha quando a última verificação não tem bloqueante e vale para o commit
atual: o mesmo commit, ou um depois dele que só mudou o documento do Goal. No
modo autônomo o orquestrador integra por fast-forward na base e fecha; no
supervisionado, para com "pronto para integrar", e a chamada seguinte vê a
branch integrada e fecha.

A verificação e as pendências que ela deixa vão ao livro-razão num lote só; o
documento é sincronizado com elas a cada passo depois da verificação, e por isso
a queda entre o lote e o commit do documento não perde acompanhamento.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.briefing import briefing_do_verificador
from graphow.orquestrador.contexto_do_laco import MAXIMO_DE_CICLOS_DE_CORRECAO, ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.documento_do_goal import caminho_do_documento, com_pendencias
from graphow.orquestrador.esquemas import PAPEL_VERIFICADOR
from graphow.orquestrador.git_do_goal import (
    FalhaDoGitDoGoal,
    GitDoGoal,
    commitar,
    descartar_mudancas,
    integrar_por_fast_forward,
    mensagem_do_orquestrador,
    remover_area,
    restaurar_head,
)
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, VerificacaoRegistrada
from graphow.orquestrador.saidas import Achado, Verificacao, conferir_verificacao
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel
from graphow.orquestrador.suite import LIMITE_DO_TRECHO, rodar_suite


def verificar_ou_fechar(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None:
    """Com as fatias concluídas: verifica o commit atual, abre correções ou fecha."""
    ultima = estado.ultima_verificacao
    if ultima is None or not _vale_para_o_commit_atual(contexto, ultima) or _ja_corrigida(estado, ultima):
        return _verificar(contexto, estado)
    _sincronizar_documento(contexto, estado.pendencias, numero=len(estado.verificacoes))
    if ultima.limpa:
        return _fechar(contexto)
    return _corrigir(contexto, estado, ultima)


def _vale_para_o_commit_atual(contexto: ContextoDoGoal, verificacao: VerificacaoRegistrada) -> bool:
    """O commit verificado é o atual, ou o que veio depois dele só mexeu no documento do Goal."""
    head = contexto.git.head()
    if verificacao.commit == head:
        return True
    if not contexto.git.e_ancestral(verificacao.commit, head):
        return False
    documento = caminho_do_documento(contexto.configuracao.slug)
    return set(contexto.git.arquivos_entre(verificacao.commit, head)) <= {documento}


def _ja_corrigida(estado: EstadoDoGoal, verificacao: VerificacaoRegistrada) -> bool:
    """A verificação rejeitada já teve as correções dela, todas concluídas: verificar de novo."""
    correcoes = [fatia for fatia in estado.fatias if fatia.texto(m.CAMPO_CORRIGE) == verificacao.id]
    return not verificacao.limpa and bool(correcoes) and all(f.status == m.STATUS_CONCLUIDO for f in correcoes)


def _verificar(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None:
    """Uma sessão nova do verificador no commit atual e a suíte do plano, gravadas como Evidence do Goal."""
    sem_orcamento = contexto.sem_orcamento()
    if sem_orcamento is not None:
        return sem_orcamento
    head = contexto.git.head()
    dados = _sessao_do_verificador(contexto, estado, head)
    if isinstance(dados, Parada):
        return dados
    plano = estado.plano or {}
    suite = rodar_suite(contexto.area, str(plano.get("comando_suite", "")), contexto.banco_descartavel,
                        tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s)
    verificacao = Verificacao.de_json(dados)
    verificacao = verificacao if suite.passou else verificacao.com_a_suite_vermelha(suite.descrever()[-LIMITE_DO_TRECHO:])
    numero = len(estado.verificacoes) + 1
    pendencias = _pendencias_depois(estado, verificacao, numero=numero)
    contexto.livro.gravar_verificacao(
        numero, verificacao, commit=head, ciclo=estado.ciclos_de_correcao, pendencias=pendencias, suite=suite
    )
    _sincronizar_documento(contexto, pendencias, numero=numero)
    return None


def _sessao_do_verificador(contexto: ContextoDoGoal, estado: EstadoDoGoal, head: str) -> Mapping[str, Any] | Parada:
    """A saída conferida do verificador, que roda numa sessão nova e não deixa mudança na área; ou a parada."""
    plano = estado.plano or {}
    criterios = [str(c["id"]) for c in plano.get("criterios", [])]
    decisoes = [str(d["id"]) for d in plano.get("decisoes", [])]
    resposta = contexto.sessoes.rodar(
        PedidoDePapel(
            papel=PAPEL_VERIFICADOR, id_goal=contexto.id_goal, pasta=contexto.area, tentativa=len(estado.verificacoes) + 1,
            briefing=briefing_do_verificador(estado, head, contexto.git.commits_desde(contexto.configuracao.base)),
            conferir=lambda dados: conferir_verificacao(Verificacao.de_json(dados), criterios, decisoes),
            orcamento_restante_usd=contexto.restante(),
        )
    )
    restaurar_head(contexto.area, contexto.configuracao.ramo, head)
    descartar_mudancas(contexto.area, contexto.patch(f"verificador-{len(estado.verificacoes) + 1}"))
    if resposta.dados is None:
        return Parada(contexto.id_goal, MotivoDaParada.FALHA, "A verificacao nao conferiu: " + "; ".join(resposta.problemas))
    return resposta.dados


def _pendencias_depois(estado: EstadoDoGoal, verificacao: Verificacao, *, numero: int) -> list[dict[str, Any]]:
    """As pendências das fatias e os acompanhamentos (e os bloqueantes, se não há mais ciclo) desta verificação."""
    sem_ciclo = estado.ciclos_de_correcao >= MAXIMO_DE_CICLOS_DE_CORRECAO
    achados = [*verificacao.acompanhamentos(), *(verificacao.bloqueantes() if sem_ciclo else ())]
    origem = f"verificacao {numero}"
    novas = [{**achado.em_json(), "origem": origem} for achado in achados]
    return [item for item in estado.pendencias if item.get("gravidade") == "pendencia"] + novas


def _sincronizar_documento(contexto: ContextoDoGoal, pendencias: Sequence[Mapping[str, Any]], *, numero: int) -> None:
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
    commitar(contexto.area, mensagem_do_orquestrador(assunto, "", id_goal=contexto.id_goal))


def _corrigir(contexto: ContextoDoGoal, estado: EstadoDoGoal, ultima: VerificacaoRegistrada) -> Parada | None:
    """Os bloqueantes viram fatias de correção, enquanto houver ciclo; sem ciclo, o laço para."""
    bloqueantes = [Achado(str(a.get("gravidade", "bloqueante")), str(a.get("titulo", "")), str(a.get("descricao", "")),
                          str(a.get("local", "")), tuple(a.get("criterios") or ())) for a in ultima.lista("bloqueantes")]
    if estado.ciclos_de_correcao >= MAXIMO_DE_CICLOS_DE_CORRECAO:
        titulos = "; ".join(achado.titulo for achado in bloqueantes)
        return Parada(
            contexto.id_goal,
            MotivoDaParada.BLOQUEANTES_RESTANTES,
            f"Depois de {MAXIMO_DE_CICLOS_DE_CORRECAO} ciclos de correcao a verificacao {ultima.id} ainda tem "
            f"{len(bloqueantes)} bloqueante(s): {titulos}. Eles estao nas pendencias do Goal; o Goal fica aberto.",
        )
    ordem = max((fatia.ordem for fatia in estado.fatias), default=0)
    contexto.livro.criar_correcoes(ultima.id, bloqueantes, ciclo=estado.ciclos_de_correcao + 1, ordem=ordem)
    return None


def _fechar(contexto: ContextoDoGoal) -> Parada:
    """Integra no modo autônomo, ou espera o humano integrar no supervisionado; fecha quando integrado."""
    configuracao = contexto.configuracao
    repositorio = Path(configuracao.repositorio)
    head = contexto.git.head()
    if configuracao.modo == m.MODO_AUTONOMO:
        try:
            integrado = integrar_por_fast_forward(repositorio, configuracao.ramo, configuracao.base)
        except FalhaDoGitDoGoal as erro:
            return Parada(contexto.id_goal, MotivoDaParada.FALHA, f"A integracao nao foi possivel: {erro.formatar_para_llm()}")
        return _fechar_integrado(contexto, integrado)
    if GitDoGoal(repositorio).e_ancestral(head, configuracao.base):
        return _fechar_integrado(contexto, GitDoGoal(repositorio).rodar("rev-parse", configuracao.base).strip())
    return Parada(
        contexto.id_goal,
        MotivoDaParada.PRONTO_PARA_INTEGRAR,
        f"Pronto para integrar: a verificacao limpa vale para {head[:12]}. Integre com "
        f"`git -C \"{repositorio}\" merge --ff-only {configuracao.ramo}` (na base {configuracao.base}) e rode de novo para fechar.",
    )


def _fechar_integrado(contexto: ContextoDoGoal, integrado: str) -> Parada:
    """Fecha o Goal e tira a área de trabalho, que já cumpriu o papel."""
    contexto.livro.fechar(integrado)
    removida = remover_area(Path(contexto.configuracao.repositorio), contexto.area)
    sobra = "" if removida else f" A area {contexto.area} ficou no disco (o git nao a removeu)."
    return Parada(contexto.id_goal, MotivoDaParada.FECHADO, f"Goal fechado: {contexto.configuracao.base} em {integrado[:12]}.{sobra}")
