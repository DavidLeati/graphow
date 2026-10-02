"""Identidade imutável de uma sessão MCP e política de autorização por ferramenta.

O papel do autor é propriedade da conexão, fixado quando o servidor MCP é aberto
pelo humano que o configura. Nenhum argumento de chamada de ferramenta pode
alterá-lo.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
import secrets
from typing import Any

from graphow.core.exceptions import ErroPermissaoPapel
from graphow.core.governanca import (
    ID_GOVERNANCA_GLOBAL,
    VALOR_ARBITRO,
    Gesto,
    PoliticaGovernanca,
    politica_padrao,
)
from graphow.core.types import PapelAutor
from graphow.kernel.politica_governanca import resolver_politica_do_no
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral
from graphow.kernel.write_kernel import WriteKernel

PAPEIS_VALIDOS_EM_SESSAO: frozenset[PapelAutor] = frozenset(
    {
        PapelAutor.HUMANO,
        PapelAutor.PLANEJADOR,
        PapelAutor.EXECUTOR,
        PapelAutor.REVISOR,
        PapelAutor.ARBITRO,
    }
)

SEPARADOR_DO_SUFIXO_DE_CONEXAO: str = "#"
BYTES_DO_SUFIXO_DE_CONEXAO: int = 3


def autor_da_conexao(autor: str, *, por_conexao: bool) -> str:
    """O autor declarado, com um sufixo único quando cada conexão precisa de posse própria.

    Um subagente com servidor MCP próprio sobe um processo por invocação, sempre
    com os argumentos da definição. Sem o sufixo, dois executores em paralelo
    assinavam o log com o mesmo nome e dividiam a posse de qualquer tarefa: o
    `assumir_tarefa` do segundo passava como se fosse do primeiro. O nome
    declarado continua à frente, para o log dizer de que definição veio.
    """
    if not por_conexao:
        return autor
    sufixo = secrets.token_hex(BYTES_DO_SUFIXO_DE_CONEXAO)
    return f"{autor.strip()}{SEPARADOR_DO_SUFIXO_DE_CONEXAO}{sufixo}"

# Ferramentas que são sempre do humano, em qualquer política: configurar_governanca
# escreve a política que decide o que cada papel pode fazer, e
# configurar_autonomia_projeto (legado) escreve o `nivel_autonomia` que ela lê.
# Um agente que as executasse desligaria todos os portões.
FERRAMENTAS_EXCLUSIVAS_DO_HUMANO: frozenset[str] = frozenset(
    {
        "configurar_governanca",
        "configurar_autonomia_projeto",
    }
)

# Ferramentas que eram só do humano e agora dependem da política efetiva do
# alvo: o humano as usa sempre, o árbitro quando o gesto está com ele, e
# planejador, executor e revisor nunca.
GESTO_POR_FERRAMENTA: Mapping[str, Gesto] = MappingProxyType(
    {
        "responder_questao": Gesto.RESPONDER_QUESTAO,
        "promover_aprendizado": Gesto.PROMOVER_APRENDIZADO,
        "encerrar_sessao": Gesto.ENCERRAR_SESSAO,
        "excluir_projeto": Gesto.EXCLUIR,
        "excluir_em_lote": Gesto.EXCLUIR,
    }
)

# Resolve a política efetiva do alvo (um nó ou aresta) no ramo dado. A pureza do
# veredito vem de a política ser lida do grafo: o mesmo log dá o mesmo veredito.
ResolvedorDePolitica = Callable[[str, str], PoliticaGovernanca]

RAMO_PADRAO_DA_POLITICA: str = "main"
CAMPO_ID_DO_ALVO_POR_FERRAMENTA: Mapping[str, str] = MappingProxyType(
    {
        "responder_questao": "id_questao",
        "promover_aprendizado": "id_aprendizado",
        "encerrar_sessao": "id_sessao",
        "excluir_projeto": "id_projeto",
    }
)
CAMPOS_DE_IDS_DA_EXCLUSAO_EM_LOTE: tuple[str, ...] = ("ids_nos", "ids_arestas")


def resolvedor_de_governanca_maxima(id_alvo: str, ramo_id: str) -> PoliticaGovernanca:
    """Resolvedor sem grafo: vale a política padrão, governança máxima."""
    return politica_padrao()


def resolvedor_do_kernel(kernel: WriteKernel) -> ResolvedorDePolitica:
    """Resolvedor que lê o grafo do kernel: o nó dá o projeto, a aresta dá o projeto da origem."""
    rastreador = RastreadorProjetoAncestral()

    def resolver(id_alvo: str, ramo_id: str) -> PoliticaGovernanca:
        estado = kernel.obter_estado(ramo_id)
        aresta = estado.arestas.get(id_alvo)
        id_no = aresta.origem_id if aresta is not None and id_alvo not in estado.nos else id_alvo
        return resolver_politica_do_no(id_no, estado, rastreador)

    return resolver


def _ids_do_alvo(nome_ferramenta: str, argumentos: Mapping[str, Any]) -> tuple[str, ...]:
    """Os ids que a ferramenta toca, para achar a política de cada um; sem id, a global."""
    if nome_ferramenta == "excluir_em_lote":
        brutos = [argumentos.get(campo) or [] for campo in CAMPOS_DE_IDS_DA_EXCLUSAO_EM_LOTE]
        ids = tuple(str(item) for lista in brutos if isinstance(lista, (list, tuple)) for item in lista)
    else:
        ids = (str(argumentos.get(CAMPO_ID_DO_ALVO_POR_FERRAMENTA[nome_ferramenta]) or ""),)
    return tuple(dict.fromkeys(ids)) or (ID_GOVERNANCA_GLOBAL,)


@dataclass(frozen=True)
class ResultadoAutorizacao:
    """Veredito imutável sobre a permissão de uso de uma ferramenta MCP."""

    autorizado: bool
    motivo: str

    @classmethod
    def permitido(cls) -> "ResultadoAutorizacao":
        """Constrói o veredito positivo padrão."""
        return cls(autorizado=True, motivo="")

    @classmethod
    def negado(cls, motivo: str) -> "ResultadoAutorizacao":
        """Constrói o veredito negativo com a justificativa exibida ao agente."""
        return cls(autorizado=False, motivo=motivo)


@dataclass(frozen=True)
class IdentidadeSessaoMCP:
    """Autor e papel fixados para toda a duração de uma sessão MCP."""

    autor: str
    papel: PapelAutor

    @classmethod
    def criar(cls, autor: str, papel_declarado: str) -> "IdentidadeSessaoMCP":
        """Valida e congela a identidade da sessão a partir da configuração do servidor."""
        autor_normalizado = autor.strip()
        if not autor_normalizado:
            raise ErroPermissaoPapel(
                "Uma sessao MCP exige um autor identificavel",
                {"autor_recebido": repr(autor)},
            )
        return cls(autor=autor_normalizado, papel=cls._converter_papel(papel_declarado))

    @staticmethod
    def _converter_papel(papel_declarado: str) -> PapelAutor:
        """Converte o texto do papel, recusando valores fora do contrato de sessão."""
        try:
            papel = PapelAutor(papel_declarado.strip().lower())
        except ValueError as erro:
            raise ErroPermissaoPapel(
                f"Papel de sessao invalido: '{papel_declarado}'",
                {"papeis_aceitos": ", ".join(sorted(p.value for p in PAPEIS_VALIDOS_EM_SESSAO))},
            ) from erro
        if papel not in PAPEIS_VALIDOS_EM_SESSAO:
            raise ErroPermissaoPapel(
                f"O papel '{papel.value}' nao pode ser atribuido a uma sessao MCP",
                {"papeis_aceitos": ", ".join(sorted(p.value for p in PAPEIS_VALIDOS_EM_SESSAO))},
            )
        return papel

    @property
    def eh_humano(self) -> bool:
        """Indica se a sessão foi aberta sob a identidade humana."""
        return self.papel == PapelAutor.HUMANO


class PoliticaIdentidadeMCP:
    """Decide se a identidade da sessão pode usar a ferramenta, pela política de governança do alvo.

    O veredito não tem efeito colateral: depende só da identidade, dos
    argumentos e da política que o resolvedor lê do grafo.
    """

    def __init__(self, resolvedor: ResolvedorDePolitica = resolvedor_de_governanca_maxima) -> None:
        self._resolvedor: ResolvedorDePolitica = resolvedor

    def autorizar(
        self,
        nome_ferramenta: str,
        identidade: IdentidadeSessaoMCP,
        argumentos: Mapping[str, Any] = MappingProxyType({}),
    ) -> ResultadoAutorizacao:
        """Consulta de autorização da ferramenta para a identidade corrente."""
        if identidade.eh_humano:
            return ResultadoAutorizacao.permitido()
        if nome_ferramenta in FERRAMENTAS_EXCLUSIVAS_DO_HUMANO:
            return ResultadoAutorizacao.negado(
                f"A ferramenta '{nome_ferramenta}' exige uma sessao humana. "
                f"Esta sessao foi aberta como '{identidade.papel.value}'. "
                "Use 'abrir_questao' para escalar a decisao ao humano."
            )
        if nome_ferramenta not in GESTO_POR_FERRAMENTA:
            return ResultadoAutorizacao.permitido()
        return self._autorizar_sob_politica(nome_ferramenta, identidade, argumentos)

    def _autorizar_sob_politica(
        self,
        nome_ferramenta: str,
        identidade: IdentidadeSessaoMCP,
        argumentos: Mapping[str, Any],
    ) -> ResultadoAutorizacao:
        """O árbitro passa se a política do alvo lhe entrega o gesto; os demais papéis de agente, nunca."""
        gesto = GESTO_POR_FERRAMENTA[nome_ferramenta]
        if nome_ferramenta == "promover_aprendizado" and argumentos.get("global"):
            return ResultadoAutorizacao.negado(
                f"A promocao global e sempre do humano, em qualquer politica. "
                f"Esta sessao foi aberta como '{identidade.papel.value}'. "
                "Use 'abrir_questao' para escalar a decisao ao humano."
            )
        ramo = str(argumentos.get("ramo_id", RAMO_PADRAO_DA_POLITICA))
        politicas = [self._resolvedor(id_alvo, ramo) for id_alvo in _ids_do_alvo(nome_ferramenta, argumentos)]
        if identidade.papel == PapelAutor.ARBITRO and all(p.permite(gesto, identidade.papel) for p in politicas):
            return ResultadoAutorizacao.permitido()
        return ResultadoAutorizacao.negado(_motivo_da_recusa(nome_ferramenta, identidade, politicas))


def _motivo_da_recusa(
    nome_ferramenta: str,
    identidade: IdentidadeSessaoMCP,
    politicas: list[PoliticaGovernanca],
) -> str:
    """Diz o gesto, de quem ele é na política do alvo e o caminho: abrir_questao ou o árbitro."""
    gesto = GESTO_POR_FERRAMENTA[nome_ferramenta]
    todos_com_o_arbitro = all(p.valor(gesto) == VALOR_ARBITRO for p in politicas)
    caminho = (
        "Peca ao arbitro da politica de governanca: este papel nao exerce o gesto."
        if todos_com_o_arbitro and identidade.papel != PapelAutor.ARBITRO
        else "Use 'abrir_questao' para escalar a decisao ao humano."
    )
    reserva = "esta com o arbitro" if todos_com_o_arbitro else "esta reservado ao humano"
    return (
        f"A ferramenta '{nome_ferramenta}' exerce o gesto '{gesto.value}', que na politica de governanca "
        f"do alvo {reserva}. Esta sessao foi aberta como '{identidade.papel.value}'. {caminho}"
    )
