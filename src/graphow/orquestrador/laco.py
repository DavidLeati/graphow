"""O laço do `graphow orquestrar`: de uma spec ou de um Goal até o Goal fechado, ou até um portão.

Cada passo relê o estado do livro-razão e do git e decide: planejar, parar no
portão do plano (modo supervisionado), executar a próxima fatia pronta, parar
na pendência ou na dúvida que espera o humano, verificar, abrir correções ou
fechar. Por isso rodar de novo retoma de onde parou, inclusive depois de o
processo morrer no meio de uma sessão.
"""

from pathlib import Path

from graphow.core.exceptions import GraphowError
from graphow.core.types import PapelAutor
from graphow.mcp.ferramentas_escopo import FerramentasEscopo
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.submissao import ContextoFerramentaMCP
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import (
    ORCAMENTO_PADRAO_USD,
    ContextoDoGoal,
    DependenciasDoLaco,
    GoalInexistente,
    MotivoDaParada,
    OpcoesDoLaco,
    Parada,
)
from graphow.orquestrador.execucao_da_fatia import executar_fatia
from graphow.orquestrador.git_do_goal import AreaDoGoal, GitDoGoal, instalar_trava, preparar_area, raiz_do_repositorio
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado, setor_do_goal
from graphow.orquestrador.livro_razao import GoalNovo, LivroRazaoDoGoal, propriedade
from graphow.orquestrador.planejamento import planejar
from graphow.orquestrador.sessoes_de_papel import ConfiguracaoDasSessoes, SessoesDePapel
from graphow.orquestrador.spec_do_goal import montar_spec_do_goal
from graphow.orquestrador.verificacao_do_goal import verificar_ou_fechar
from graphow.projection.graph_view import GrafoView

LIMITE_DE_PASSOS: int = 200
PREFIXO_GENERICO_DA_SPEC: str = "spec-"


class PedidoInvalido(GraphowError):
    """O que a chamada pediu não dá para conduzir."""


class Orquestrador:
    """Conduz Goals com as dependências dadas; cada chamada roda até o Goal fechar ou o laço parar."""

    def __init__(self, dependencias: DependenciasDoLaco) -> None:
        self._dependencias: DependenciasDoLaco = dependencias

    def iniciar_da_spec(self, spec: Path, repositorio: Path, opcoes: OpcoesDoLaco) -> Parada:
        """Cria o Goal da spec (ou retoma o que a mesma spec já criou) e roda."""
        texto = spec.read_text(encoding="utf-8")
        raiz = raiz_do_repositorio(repositorio)
        slug = _slug_da_spec(spec, raiz)
        id_goal = self._goal_da_spec(slug, texto, raiz)
        if ler_estado(self._view(), id_goal) is None:
            configuracao = self._configuracao(id_goal, slug, raiz, opcoes=opcoes)
            novo = GoalNovo(id_goal=id_goal, rotulo=slug, spec=texto, configuracao=configuracao, nome_do_repositorio=raiz.name)
            LivroRazaoDoGoal(self._dependencias.kernel, id_goal).criar_goal(novo)
        return self.rodar(id_goal, opcoes, raiz)

    def rodar(self, id_goal: str, opcoes: OpcoesDoLaco, repositorio: Path | None = None) -> Parada:
        """Roda ou retoma o Goal até ele fechar ou o laço parar."""
        estado = ler_estado(self._view(), id_goal)
        if estado is None:
            raise GoalInexistente("Goal nao encontrado no livro-razao", {"id_goal": id_goal})
        if estado.fechado:
            return Parada(id_goal, MotivoDaParada.FECHADO, f"O Goal {id_goal} ja esta fechado.")
        contexto = self._contexto(estado, opcoes, repositorio)
        preparar_area(AreaDoGoal(Path(contexto.configuracao.repositorio), contexto.area,
                                 contexto.configuracao.ramo, contexto.configuracao.base))
        for _ in range(LIMITE_DE_PASSOS):
            parada = _passo(contexto)
            if parada is not None:
                return parada
        return Parada(id_goal, MotivoDaParada.FALHA, f"O laco passou de {LIMITE_DE_PASSOS} passos sem parar.")

    def aprovar_plano(self, id_goal: str, autor: str) -> str:
        """O portão do plano pelo humano: o mesmo gesto `aprovar_plano` que o MCP do humano expõe."""
        estado = ler_estado(self._view(), id_goal)
        if estado is None or estado.plano is None:
            raise PedidoInvalido("o Goal ainda nao tem plano para aprovar", {"id_goal": id_goal})
        identidade = IdentidadeSessaoMCP.criar(autor, PapelAutor.HUMANO.value)
        resposta = FerramentasEscopo(ContextoFerramentaMCP(self._dependencias.kernel, identidade)).aprovar_plano({"id_goal": id_goal})
        if not resposta.get("sucesso"):
            raise PedidoInvalido("a aprovacao do plano foi recusada", {"id_goal": id_goal, "motivo": str(resposta.get("mensagem"))})
        return f"Plano do Goal {id_goal} aprovado por {autor} (versao {resposta.get('versao')})."

    def _view(self) -> GrafoView:
        """O grafo agora."""
        return self._dependencias.kernel.obter_view()

    def _goal_da_spec(self, slug: str, texto: str, raiz: Path) -> str:
        """O Goal aberto que a mesma spec criou no mesmo repositório, ou um id livre para um novo."""
        for sufixo in ("", *(f"-{n}" for n in range(2, 100))):
            id_goal = m.id_do_goal(slug + sufixo)
            estado = ler_estado(self._view(), id_goal)
            if estado is None:
                return id_goal
            configuracao = estado.configuracao
            mesma = configuracao is not None and Path(configuracao.repositorio) == raiz and estado.propriedades.get(m.CAMPO_SPEC) == texto
            if mesma and not estado.fechado:
                return id_goal
        raise PedidoInvalido("ids de Goal esgotados para a spec", {"slug": slug})

    def _configuracao(self, id_goal: str, slug: str, raiz: Path, *, opcoes: OpcoesDoLaco) -> m.ConfiguracaoDoGoal:
        """A configuração do Goal novo, com os padrões do que a chamada não disse."""
        base = opcoes.base or GitDoGoal(raiz).ramo_atual()
        if not base:
            raise PedidoInvalido("o repositorio esta com o HEAD destacado: diga a base com --base", {"repositorio": str(raiz)})
        area = opcoes.area or self._dependencias.pasta_de_estado / id_goal / "area"
        return m.ConfiguracaoDoGoal(
            modo=opcoes.modo or m.MODO_SUPERVISIONADO, repositorio=str(raiz), area=str(area),
            ramo=opcoes.ramo or f"graphow/{slug}", base=base, slug=slug,
            orcamento_usd=opcoes.orcamento_usd if opcoes.orcamento_usd is not None else ORCAMENTO_PADRAO_USD,
        )

    def _contexto(self, estado: EstadoDoGoal, opcoes: OpcoesDoLaco, repositorio: Path | None) -> ContextoDoGoal:
        """O contexto do Goal, adotando o Goal do gerente na primeira chamada e aplicando o que a chamada mudou."""
        livro = LivroRazaoDoGoal(self._dependencias.kernel, estado.id_goal)
        configuracao = estado.configuracao or self._adotar(livro, estado, opcoes, repositorio=repositorio)
        configuracao = self._atualizar(livro, configuracao, opcoes)
        pasta = self._dependencias.pasta_de_estado / estado.id_goal
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

    def _adotar(self, livro: LivroRazaoDoGoal, estado: EstadoDoGoal, opcoes: OpcoesDoLaco, *, repositorio: Path | None) -> m.ConfiguracaoDoGoal:
        """O Goal do gerente passa a ser conduzido: a spec montada dos nós e a configuração da chamada."""
        if repositorio is None:
            raise PedidoInvalido("o Goal ainda nao foi orquestrado: diga o repositorio com --repo", {"id_goal": estado.id_goal})
        raiz = raiz_do_repositorio(repositorio)
        slug = m.slug_de(estado.id_goal.removeprefix("goal-"))
        configuracao = self._configuracao(estado.id_goal, slug, raiz, opcoes=opcoes)
        id_setor = setor_do_goal(livro.view(), estado.id_goal)
        if not id_setor:
            raise PedidoInvalido("o Goal nao esta pendurado numa Sessao de um Setor", {"id_goal": estado.id_goal})
        livro.adotar_goal(id_setor, montar_spec_do_goal(livro.view(), estado.id_goal).texto, configuracao)
        return configuracao

    def _atualizar(self, livro: LivroRazaoDoGoal, configuracao: m.ConfiguracaoDoGoal, opcoes: OpcoesDoLaco) -> m.ConfiguracaoDoGoal:
        """O modo e o orçamento que a chamada pede de novo valem daqui em diante, e ficam gravados."""
        modo = opcoes.modo or configuracao.modo
        orcamento = opcoes.orcamento_usd if opcoes.orcamento_usd is not None else configuracao.orcamento_usd
        if (modo, orcamento) == (configuracao.modo, configuracao.orcamento_usd):
            return configuracao
        nova = m.ConfiguracaoDoGoal(**{**configuracao.em_json(), "modo": modo, "orcamento_usd": orcamento})
        livro.gravar([propriedade(livro.id_goal, m.CAMPO_ORQUESTRACAO, nova.em_json())], f"Configuracao do Goal {livro.id_goal}")
        return nova


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
            f"e aprove com `graphow orquestrar --goal {contexto.id_goal} --aprovar-plano` (ou pelo gesto aprovar_plano).",
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


def _slug_da_spec(spec: Path, raiz: Path) -> str:
    """O slug do Goal: o nome da spec sem o prefixo `spec-`; a spec de nome genérico leva o nome do repositório."""
    nome = spec.stem.removeprefix(PREFIXO_GENERICO_DA_SPEC)
    return m.slug_de(raiz.name if nome.lower() in ("spec", "") else nome)
