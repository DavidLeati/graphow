"""Hierarquia de exceções de domínio cirúrgicas do Graphow."""


class GraphowError(Exception):
    """Exceção raiz para todas as falhas de domínio do Graphow."""

    def __init__(self, mensagem: str, contexto: dict[str, str] | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem: str = mensagem
        self.contexto: dict[str, str] = contexto or {}

    def formatar_para_llm(self) -> str:
        """Formata o erro de forma estruturada para autocorreção por agentes."""
        if not self.contexto:
            return f"ERRO: {self.mensagem}"
        detalhes: str = ", ".join(f"{chave}={valor}" for chave, valor in sorted(self.contexto.items()))
        return f"ERRO: {self.mensagem} | Contexto: [{detalhes}]"


class ErroValidacaoOntologia(GraphowError):
    """Lançado quando uma estrutura viola as regras da ontologia formal."""


class ErroPermissaoPapel(GraphowError):
    """Lançado quando um autor tenta executar uma ação não permitida para seu papel."""


class ErroInvarianteGrafo(GraphowError):
    """Lançado quando uma mutação quebra uma regra de integridade relacional do grafo."""


class ErroCicloDetectado(ErroInvarianteGrafo):
    """Lançado quando uma aresta de dependência cria um ciclo proibido."""


class ErroPatchInvalido(GraphowError):
    """Lançado quando a estrutura do JSON Patch é sintaticamente inválida."""


class ErroSegurancaPatch(GraphowError):
    """Lançado quando um patch tenta acessar campos protegidos (ex: prototype pollution)."""


class ErroLockConcorrencia(GraphowError):
    """Lançado quando múltiplos escritores tentam adquirir lock sobre a mesma Task."""


class ErroNaoDeterminismo(GraphowError):
    """Lançado quando uma projeção diverge em relação ao replay do log."""


class ErroEntidadeNaoEncontrada(GraphowError):
    """Lançado quando um nó, aresta ou evento solicitado não existe."""


class ErroOrcamentoExcedido(GraphowError):
    """Lançado quando a materialização de contexto excede o orçamento estrito de tokens."""


class ErroConflitoDeSequencia(GraphowError):
    """Lançado quando dois escritores tentam ocupar a mesma posição do log."""


class ErroConcorrenciaPersistente(GraphowError):
    """Lançado quando as tentativas de resolver conflitos de escrita se esgotam."""
