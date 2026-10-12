"""O passo do aceite: uma sessão do autor de aceite, os testes conferidos vermelhos, o commit e o registro.

Depois do plano e antes de qualquer implementação, uma sessão nova do autor de
aceite, que não é o executor, recebe a spec, os critérios e o código e escreve
os testes de aceite em `aceite/` (orquestrador/saida_do_aceite.py). O
orquestrador confere a forma e roda cada teste: todos falham agora, salvo o do
critério que o código já atendia, com a justificativa. Conferido, o
orquestrador commita os testes com a seção "Testes de aceite" do documento do
Goal e grava no livro-razão a ligação de cada critério aos seus testes. No
modo supervisionado o portão do plano vem depois deste passo: o humano aprova
junto o plano e os testes, "isto é o que vai provar que está pronto".

O aceite pago não se paga de novo: a saída conferida vai ao Goal
(`aceite_proposto`) antes do commit. A retomada reconhece o commit dos testes
pelo trailer `Graphow-Task: aceite-<goal>`, ou commita os arquivos que a
sessão deixou, e só abre outra sessão quando eles se perderam.
"""

from collections.abc import Mapping
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.briefing import briefing_do_autor_de_aceite
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.documento_do_goal import caminho_do_documento, com_aceite
from graphow.orquestrador.esquemas import ESQUEMA_DO_ACEITE, PAPEL_AUTOR_DE_ACEITE
from graphow.orquestrador.git_do_goal import arquivos_do_commit, commit_da_fatia, descartar_mudancas, mensagem_do_orquestrador
from graphow.orquestrador.gravacao_do_aceite import AceiteParaGravar, gravar_aceite, gravar_aceite_proposto
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.saida_do_aceite import SaidaDoAceite, conferir_forma, conferir_vermelho, dentro_do_aceite, e_cache
from graphow.orquestrador.sessoes_de_papel import Conferencia, PedidoDePapel
from graphow.orquestrador.suite import ResultadoDaSuite, rodar_suite
from graphow.orquestrador.validacao_json import validar_contra_esquema
from graphow.orquestrador.verificacao_do_marco import nos_do_plano


def escrever_aceite(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None:
    """Os testes de aceite já pagos, ou uma sessão do autor; commita e grava, ou diz por que não deu."""
    proposto = _aceite_ja_pago(estado)
    if proposto is None:
        descartar_mudancas(contexto.area, contexto.patch("aceite-interrompido"))
        sem_orcamento = contexto.sem_orcamento()
        if sem_orcamento is not None:
            return sem_orcamento
        proposto, problemas = _sessao_do_autor(contexto, estado)
        if proposto is None:
            return Parada(contexto.id_goal, MotivoDaParada.FALHA, "Os testes de aceite nao conferiram: " + "; ".join(problemas))
        gravar_aceite_proposto(contexto.livro, proposto)
    saida = SaidaDoAceite.de_json(proposto["saida"])
    commit = _commit_do_aceite(contexto, saida)
    if commit is None:
        gravar_aceite_proposto(contexto.livro, None)
        return None
    declarados = [teste.arquivo for _, teste in saida.testes()]
    do_commit = [a for a in arquivos_do_commit(contexto.area, commit) if dentro_do_aceite(a) and not e_cache(a)]
    arquivos = tuple(dict.fromkeys([*declarados, *do_commit]))
    execucoes = [dict(item) for item in proposto.get("execucoes", []) if isinstance(item, Mapping)]
    gravar_aceite(contexto.livro, AceiteParaGravar(saida, commit, arquivos, execucoes, nos_do_plano(estado.plano or {})))
    return None


def _aceite_ja_pago(estado: EstadoDoGoal) -> Mapping[str, Any] | None:
    """A saída do autor que já foi conferida e gravada no Goal, quando há."""
    proposto = estado.propriedades.get(m.CAMPO_ACEITE_PROPOSTO)
    saida = proposto.get("saida") if isinstance(proposto, Mapping) else None
    valida = isinstance(saida, Mapping) and not validar_contra_esquema(dict(saida), ESQUEMA_DO_ACEITE)
    return proposto if valida else None


def _sessao_do_autor(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Uma sessão do autor na área; a saída conferida com as execuções vermelhas, ou os problemas."""
    guarda: dict[str, Any] = {}
    resposta = contexto.sessoes.rodar(
        PedidoDePapel(
            papel=PAPEL_AUTOR_DE_ACEITE, id_goal=contexto.id_goal, pasta=contexto.area,
            briefing=briefing_do_autor_de_aceite(estado), conferir=_conferencia(contexto, estado, guarda),
            orcamento_restante_usd=contexto.restante(),
        )
    )
    if resposta.dados is None:
        descartar_mudancas(contexto.area, contexto.patch("aceite-recusado"))
        return None, resposta.problemas
    return {"saida": dict(resposta.dados), "execucoes": guarda.get("execucoes", [])}, ()


def _conferencia(contexto: ContextoDoGoal, estado: EstadoDoGoal, guarda: dict[str, Any]) -> Conferencia:
    """A conferência da saída do autor: a forma, o lugar dos arquivos e o vermelho, guardando as execuções."""
    criterios = {str(c["id"]): str(c["verificacao"]) for c in (estado.plano or {}).get("criterios", [])}

    def rodar(comando: str) -> ResultadoDaSuite:
        return rodar_suite(contexto.area, comando, contexto.banco_descartavel, tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s)

    def conferir(dados: Mapping[str, Any]) -> tuple[str, ...]:
        saida = SaidaDoAceite.de_json(dados)
        mudados = [caminho for caminho in contexto.git.caminhos_mudados() if not e_cache(caminho)]
        problemas = conferir_forma(saida, criterios, contexto.area, mudados=mudados)
        if problemas:
            return problemas
        problemas, execucoes = conferir_vermelho(saida, rodar)
        guarda["execucoes"] = [execucao.em_json() for execucao in execucoes]
        return problemas

    return conferir


def _commit_do_aceite(contexto: ContextoDoGoal, saida: SaidaDoAceite) -> str | None:
    """O commit dos testes: o que já está na branch (pelo trailer), ou o dos arquivos que a sessão deixou; None sem eles.

    O teste que já estava na base, igual, não muda nada no git, e o commit sai
    mesmo assim, com a seção do documento (ou vazio): é ele que marca o aceite.
    """
    id_do_aceite = m.id_do_aceite(contexto.id_goal)
    feito = commit_da_fatia(contexto.area, id_do_aceite, contexto.configuracao.base)
    if feito is not None:
        return feito.hash
    if not all((contexto.area / teste.arquivo).is_file() for _, teste in saida.testes()):
        return None
    caminho = contexto.area / caminho_do_documento(contexto.configuracao.slug)
    if caminho.is_file():
        caminho.write_text(com_aceite(caminho.read_text(encoding="utf-8"), linhas_do_aceite(saida)), encoding="utf-8", newline="\n")
    provados = ", ".join(criterio.id for criterio in saida.criterios)
    assunto = f"Escreve os testes de aceite do Goal {contexto.configuracao.slug} ({provados})"
    mensagem = mensagem_do_orquestrador(assunto, saida.resumo, id_goal=contexto.id_goal, id_task=id_do_aceite)
    return contexto.commitar(mensagem, vazio_permitido=True)


def linhas_do_aceite(saida: SaidaDoAceite) -> list[str]:
    """A seção dos testes de aceite no documento do Goal: o comando e o que prova cada critério."""
    linhas = [f"Comando de aceite: `{saida.comando_aceite}`. O executor nao altera estes arquivos.", ""]
    for criterio in saida.criterios:
        provas = [f"`{teste.arquivo}::{teste.nome}`" for teste in criterio.testes]
        provas += [f"checagem {n}: {passo}" for n, passo in enumerate(criterio.checagem, start=1)]
        atendido = f" (o codigo ja atendia: {criterio.ja_atendido})" if criterio.ja_atendido else ""
        linhas.append(f"- **{criterio.id}**{atendido}: " + "; ".join(provas))
    return linhas
