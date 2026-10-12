"""Os passos do fim: a verificação adversarial do Goal, as fatias de correção e o fechamento.

Com as fatias concluídas, uma sessão nova do verificador confere a entrega no
commit atual e lista os comandos que rodou, com o código e um trecho da saída;
cada comando declarado tem de aparecer nas chamadas Bash do stream da sessão;
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
from dataclasses import replace
from pathlib import Path
from typing import Any

from graphow.core import aceite as a
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.briefing import briefing_do_verificador
from graphow.orquestrador.contexto_do_laco import MAXIMO_DE_CICLOS_DE_CORRECAO, ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.documento_do_goal import caminho_do_documento, com_pendencias
from graphow.orquestrador.esquemas import PAPEL_VERIFICADOR
from graphow.orquestrador.git_do_goal import (
    FalhaDoGitDoGoal,
    GitDoGoal,
    descartar_mudancas,
    integrar_por_fast_forward,
    mensagem_do_orquestrador,
    remover_area,
)
from graphow.orquestrador.gravacao_da_verificacao import RegistroDaVerificacao, gravar_verificacao
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, VerificacaoRegistrada
from graphow.orquestrador.saida_do_verificador import TITULO_DA_SUITE_VERMELHA, Verificacao, conferir_verificacao
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
    """A verificação foi feita no commit do código atual: o que veio depois dela só mexeu no documento do Goal.

    É a mesma conta que o kernel faz contra a ponta da branch gravada no Goal
    (kernel/fechamento_do_goal.py); a verificação de antes da fase 2, sem o
    commit do código, não vale mais e é refeita.
    """
    return bool(verificacao.commit_do_codigo) and verificacao.commit_do_codigo == contexto.commit_do_codigo()


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
    if not suite.passou:
        verificacao = verificacao.com_achado_do_orquestrador(TITULO_DA_SUITE_VERMELHA, suite.descrever()[-LIMITE_DO_TRECHO:])
    registro = RegistroDaVerificacao(
        numero=len(estado.verificacoes) + 1, verificacao=verificacao, commit=head, commit_do_codigo=contexto.commit_do_codigo(),
        suite=suite, nos=_nos_do_plano(plano), ciclo=estado.ciclos_de_correcao, resolver=_corrigidos(estado),
    )
    registro = replace(registro, pendencias=_pendencias_depois(estado, registro, contexto.id_goal))
    gravar_verificacao(contexto.livro, registro)
    _sincronizar_documento(contexto, registro.pendencias, numero=registro.numero)
    return None


def _corrigidos(estado: EstadoDoGoal) -> tuple[str, ...]:
    """Os Achados que uma correção já entregou e que a verificação limpa resolve."""
    return tuple(achado.id for v in estado.verificacoes for achado in v.achados if achado.estado == a.ESTADO_CORRIGIDO)


def _nos_do_plano(plano: Mapping[str, Any]) -> dict[str, str]:
    """O nó do livro-razão de cada critério e decisão do plano, pelo código."""
    itens = [*plano.get("criterios", []), *plano.get("decisoes", [])]
    return {str(item["id"]): str(item.get("no", "")) for item in itens if isinstance(item, Mapping)}


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
            comandos_declarados=lambda dados: [str(comando.get("comando", "")) for comando in dados.get("comandos", [])],
            orcamento_restante_usd=contexto.restante(),
        )
    )
    descartar_mudancas(contexto.area, contexto.patch(f"verificador-{len(estado.verificacoes) + 1}"))
    if resposta.dados is None:
        return Parada(contexto.id_goal, MotivoDaParada.FALHA, "A verificacao nao conferiu: " + "; ".join(resposta.problemas))
    return resposta.dados


def _pendencias_depois(estado: EstadoDoGoal, registro: RegistroDaVerificacao, id_goal: str) -> list[dict[str, Any]]:
    """As pendências de antes, mais os acompanhamentos desta verificação (e os bloqueantes, se não há mais ciclo), sem repetir.

    O acompanhamento que uma verificação anterior achou continua pendência,
    ache-o a seguinte ou não; o mesmo título no mesmo local não entra duas vezes.
    """
    sem_ciclo = estado.ciclos_de_correcao >= MAXIMO_DE_CICLOS_DE_CORRECAO
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
    contexto.commitar(mensagem_do_orquestrador(assunto, "", id_goal=contexto.id_goal))


def _corrigir(contexto: ContextoDoGoal, estado: EstadoDoGoal, ultima: VerificacaoRegistrada) -> Parada | None:
    """Os bloqueantes viram fatias de correção, enquanto houver ciclo; sem ciclo, o laço para."""
    bloqueantes = ultima.bloqueantes()
    if estado.ciclos_de_correcao >= MAXIMO_DE_CICLOS_DE_CORRECAO:
        titulos = "; ".join(achado.texto("titulo") for achado in bloqueantes)
        return Parada(
            contexto.id_goal,
            MotivoDaParada.BLOQUEANTES_RESTANTES,
            f"Depois de {MAXIMO_DE_CICLOS_DE_CORRECAO} ciclos de correcao a verificacao {ultima.id} ainda tem "
            f"{len(bloqueantes)} bloqueante(s): {titulos}. Eles seguem como Achados abertos e nas pendencias do Goal; "
            "o Goal fica aberto, e o kernel nao o fecha enquanto houver bloqueante aberto.",
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
    removida = remover_area(contexto.area)
    sobra = "" if removida else f" A area {contexto.area} ficou no disco (o git nao a removeu)."
    return Parada(contexto.id_goal, MotivoDaParada.FECHADO, f"Goal fechado: {contexto.configuracao.base} em {integrado[:12]}.{sobra}")
