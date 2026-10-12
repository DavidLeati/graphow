"""O laço do `graphow orquestrar`: de uma spec ou de um Goal até o Goal fechado, ou até um portão.

Cada passo relê o estado do livro-razão e do git e decide: planejar, parar no
portão do plano (modo supervisionado), executar a próxima fatia pronta, parar
na pendência ou na dúvida que espera o humano, verificar, abrir correções ou
fechar. Por isso rodar de novo retoma de onde parou, inclusive depois de o
processo morrer no meio de uma sessão. Toda falha de domínio (o kernel que
recusa um lote, o git que recusa um comando, a sessão que não abre) vira uma
parada legível, e não uma exceção no meio da chamada.
"""

from pathlib import Path

from graphow.core.exceptions import GraphowError
from graphow.core.types import PapelAutor
from graphow.kernel.patch_models import DadosPropostaPatch, PropostaPatch
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import (
    ContextoDoGoal,
    DependenciasDoLaco,
    GoalInexistente,
    MotivoDaParada,
    OpcoesDoLaco,
    Parada,
)
from graphow.orquestrador.entrada_do_goal import (
    PedidoDeConfiguracao,
    PedidoInvalido,
    adotar_goal,
    atualizar_configuracao,
    configuracao_nova,
    goal_da_spec,
    pedido_de_adocao,
)
from graphow.orquestrador.execucao_da_fatia import executar_fatia
from graphow.orquestrador.git_do_goal import AreaDoGoal, instalar_trava, preparar_area, raiz_do_repositorio
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado
from graphow.orquestrador.livro_razao import GoalNovo, LivroRazaoDoGoal, propriedade
from graphow.orquestrador.planejamento import planejar
from graphow.orquestrador.sessoes_de_papel import ConfiguracaoDasSessoes, SessoesDePapel
from graphow.orquestrador.verificacao_do_goal import verificar_ou_fechar
from graphow.projection.graph_view import GrafoView

LIMITE_DE_PASSOS: int = 200

__all__ = ["Orquestrador", "PedidoInvalido"]


class Orquestrador:
    """Conduz Goals com as dependências dadas; cada chamada roda até o Goal fechar ou o laço parar."""

    def __init__(self, dependencias: DependenciasDoLaco) -> None:
        self._dependencias: DependenciasDoLaco = dependencias

    def iniciar_da_spec(self, spec: Path, repositorio: Path, opcoes: OpcoesDoLaco) -> Parada:
        """Cria o Goal da spec (ou retoma o que a mesma spec já criou) e roda; a falha de domínio vira parada."""
        try:
            id_goal = self._goal_da_spec(spec, repositorio, opcoes)
        except GraphowError as erro:
            return _parada_de_falha("", erro)
        return self.rodar(id_goal, opcoes, raiz_do_repositorio(repositorio))

    def rodar(self, id_goal: str, opcoes: OpcoesDoLaco, repositorio: Path | None = None) -> Parada:
        """Roda ou retoma o Goal até ele fechar ou o laço parar; a falha de domínio vira parada."""
        try:
            return self._rodar(id_goal, opcoes, repositorio)
        except GraphowError as erro:
            return _parada_de_falha(id_goal, erro)

    def aprovar_plano(self, id_goal: str, autor: str) -> str:
        """O portão do plano do orquestrador: o humano grava a aprovação no Goal, com o commit do documento.

        É do orquestrador, e não o gesto `aprovar_plano` do escopo governado:
        o laço não depende das regras que a fase 4 apaga.
        """
        estado = ler_estado(self._view(), id_goal)
        if estado is None or estado.plano is None:
            raise PedidoInvalido("o Goal ainda nao tem plano para aprovar", {"id_goal": id_goal})
        documento = estado.plano.get("documento", {})
        aprovacao = {"papel": PapelAutor.HUMANO.value, "por": autor, "documento": documento.get("commit", "")}
        dados = DadosPropostaPatch(
            autor=autor, papel=PapelAutor.HUMANO, justificativa=f"Aprovacao do plano do Goal {id_goal}",
            operacoes=(propriedade(id_goal, m.CAMPO_APROVACAO_DO_PLANO, aprovacao),),
        )
        recibo = self._dependencias.kernel.submeter_patch(PropostaPatch.criar(dados))
        if not recibo.sucesso:
            raise PedidoInvalido("a aprovacao do plano foi recusada", {"id_goal": id_goal, "motivo": recibo.mensagem})
        return f"Plano do Goal {id_goal} aprovado por {autor} (documento em {str(aprovacao['documento'])[:12]})."

    def _view(self) -> GrafoView:
        """O grafo agora."""
        return self._dependencias.kernel.obter_view()

    def _goal_da_spec(self, spec: Path, repositorio: Path, opcoes: OpcoesDoLaco) -> str:
        """O Goal que a spec retoma ou cria, criado no livro-razão quando é novo."""
        texto = spec.read_text(encoding="utf-8")
        raiz = raiz_do_repositorio(repositorio)
        alvo = goal_da_spec(self._view(), spec, texto, raiz=raiz)
        if alvo.existe:
            return alvo.id_goal
        configuracao = configuracao_nova(
            PedidoDeConfiguracao(alvo.id_goal, alvo.slug, raiz, opcoes, self._dependencias.pasta_de_estado)
        )
        novo = GoalNovo(id_goal=alvo.id_goal, rotulo=alvo.slug, spec=texto, configuracao=configuracao, nome_do_repositorio=raiz.name)
        LivroRazaoDoGoal(self._dependencias.kernel, alvo.id_goal).criar_goal(novo)
        return alvo.id_goal

    def _rodar(self, id_goal: str, opcoes: OpcoesDoLaco, repositorio: Path | None) -> Parada:
        """O laço, passo a passo, até uma parada."""
        estado = ler_estado(self._view(), id_goal)
        if estado is None:
            raise GoalInexistente("Goal nao encontrado no livro-razao", {"id_goal": id_goal})
        if estado.fechado:
            return Parada(id_goal, MotivoDaParada.FECHADO, f"O Goal {id_goal} ja esta fechado.")
        contexto = self._contexto(estado, opcoes, repositorio)
        configuracao = contexto.configuracao
        preparar_area(AreaDoGoal(Path(configuracao.repositorio), contexto.area, configuracao.ramo, configuracao.base))
        for _ in range(LIMITE_DE_PASSOS):
            parada = _passo(contexto)
            if parada is not None:
                return parada
        return Parada(id_goal, MotivoDaParada.FALHA, f"O laco passou de {LIMITE_DE_PASSOS} passos sem parar.")

    def _contexto(self, estado: EstadoDoGoal, opcoes: OpcoesDoLaco, repositorio: Path | None) -> ContextoDoGoal:
        """O contexto do Goal, adotando o Goal do gerente na primeira chamada e aplicando o que a chamada mudou."""
        livro = LivroRazaoDoGoal(self._dependencias.kernel, estado.id_goal)
        pasta_de_estado = self._dependencias.pasta_de_estado
        configuracao = estado.configuracao or adotar_goal(
            livro, estado, pedido_de_adocao(estado, opcoes, repositorio=repositorio, pasta_de_estado=pasta_de_estado)
        )
        configuracao = atualizar_configuracao(livro, configuracao, opcoes)
        pasta = pasta_de_estado / estado.id_goal
        sessoes = SessoesDePapel(
            self._dependencias.executor,
            self._dependencias.telemetria,
            ConfiguracaoDasSessoes(
                pasta_das_sessoes=pasta / "sessoes", ambiente_da_trava=instalar_trava(pasta / "trava-do-git"),
                modelos=self._dependencias.modelos, modo_de_permissao=self._dependencias.modo_de_permissao,
                tempo_limite_s=self._dependencias.tempo_limite_da_sessao_s, banco_dos_hooks=pasta / "descartavel.db",
            ),
        )
        return ContextoDoGoal(livro, configuracao, sessoes, self._dependencias.telemetria, pasta, opcoes)


def _passo(contexto: ContextoDoGoal) -> Parada | None:
    """Um passo do laço, decidido pelo estado de agora; None quando o laço segue."""
    estado = contexto.estado()
    if estado.fechado:
        return Parada(contexto.id_goal, MotivoDaParada.FECHADO, f"O Goal {contexto.id_goal} esta fechado.")
    if estado.plano is None:
        return planejar(contexto, estado)
    if contexto.configuracao.modo == m.MODO_SUPERVISIONADO and not estado.plano_aprovado:
        return Parada(
            contexto.id_goal,
            MotivoDaParada.AGUARDANDO_APROVACAO,
            f"O plano espera aprovacao: leia docs/goals/{contexto.configuracao.slug}.md na branch {contexto.configuracao.ramo} "
            f"e aprove com `graphow orquestrar --goal {contexto.id_goal} --aprovar-plano`.",
        )
    prontas = estado.prontas()
    if prontas:
        return executar_fatia(contexto, estado, prontas[0])
    if estado.bloqueadas():
        return Parada(contexto.id_goal, MotivoDaParada.PENDENCIA, "Ha fatia que virou pendencia: " + ", ".join(f.codigo for f in estado.bloqueadas()))
    if estado.pausadas():
        duvidas = "; ".join(f"{f.duvida_aberta.id}: {f.duvida_aberta.pergunta}" for f in estado.pausadas() if f.duvida_aberta)
        return Parada(contexto.id_goal, MotivoDaParada.AGUARDANDO_RESPOSTA, f"Fatias pausadas esperando resposta do humano: {duvidas}")
    return verificar_ou_fechar(contexto, estado)


def _parada_de_falha(id_goal: str, erro: GraphowError) -> Parada:
    """A falha de domínio como parada, com a mensagem e o contexto que o domínio deu."""
    return Parada(id_goal, MotivoDaParada.FALHA, f"{type(erro).__name__}: {erro.formatar_para_llm()}")
