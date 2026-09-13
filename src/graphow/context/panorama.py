"""Seção de panorama: os filhos de um contêiner resumidos, em vez de listados.

A vista de uma Sessão com 35 vizinhos gastava 1.177 tokens listando um a um
artefatos e evidências de trabalho já encerrado, e a vista de um Projeto listava
cinco setores sem dizer em qual deles havia trabalho aberto — a única coisa que o
agente queria saber ali. O panorama troca a lista pelo agregado: uma linha por
filho, com quantas tarefas fecharam, quantas seguem abertas e quantas dúvidas
esperam o humano. O detalhe continua a um `expandir_no` de distância.

A seção retém como NAVEGACAO, não como apoio: ela é a afordância de descida, e
descartá-la deixa o agente sem saber para onde ir — o mesmo motivo pelo qual a
seção de vizinhos encolhe por dentro antes de sumir.
"""

from collections.abc import Sequence

from graphow.context.secoes import GrupoDeLinhas, PrioridadeRetencao, SecaoContexto
from graphow.core.models import NoGrafo
from graphow.core.types import StatusQuestion, StatusTask, TipoNo
from graphow.projection.rollup import STATUS_TERMINAIS_DE_TAREFA, ResumoDeSubarvore

TITULO_PANORAMA: str = "Panorama dos Filhos (use ler_vista no que tiver trabalho aberto)"
ORDEM_DE_EXIBICAO_DO_PANORAMA: int = 8

# Quantos filhos sem subárvore o panorama nomeia por tipo antes de apenas contar.
# Sem este teto o panorama de uma Sessão volta a ser a lista crua que ele veio
# substituir: os filhos dela são folhas, e resumir folha a folha não resume nada.
# O teto não se aplica a quem tem trabalho aberto — esse é o caminho de descida,
# e escondê-lo devolveria o agente à varredura.
LIMITE_DE_FILHOS_NOMEADOS_POR_TIPO: int = 5


class FilhoResumido:
    """Par de nó e resumo, na ordem em que o panorama deve exibi-los."""

    def __init__(self, no: NoGrafo, resumo: ResumoDeSubarvore | None) -> None:
        self.no: NoGrafo = no
        self.resumo: ResumoDeSubarvore | None = resumo

    @property
    def tem_trabalho_aberto(self) -> bool:
        """Trabalho aberto na subárvore ou, sendo folha, no próprio nó.

        Uma Task pendente sem subtarefas é folha, e sem esta segunda metade ela
        seria cortada pelo teto de filhos nomeados — justamente o nó que o agente
        precisa ver.
        """
        if self.resumo is not None:
            return self.resumo.tem_trabalho_aberto
        return self._proprio_esta_aberto()

    def _proprio_esta_aberto(self) -> bool:
        """Uma Task não concluída ou uma dúvida sem resposta seguem pedindo trabalho."""
        if self.no.tipo == TipoNo.TASK:
            return str(self.no.obter_propriedade("status", StatusTask.PENDENTE.value)) not in STATUS_TERMINAIS_DE_TAREFA
        if self.no.tipo == TipoNo.QUESTION:
            return self.no.obter_propriedade("status", StatusQuestion.ABERTA.value) == StatusQuestion.ABERTA.value
        return False

    def formatar(self) -> str:
        """Uma linha: identidade do filho e o agregado da subárvore dele.

        Um filho sem subárvore ainda carrega o próprio status. Omiti-lo faria o
        panorama dizer menos que a lista de vizinhos que ele substituiu, e o
        status é a informação mais barata e mais decisiva da linha.
        """
        cabeca = f"- [{self.no.id}] ({self.no.tipo.value}): {self.no.rotulo}"
        if self.resumo is None:
            return f"{cabeca}{self._sufixo_de_status()}"
        marca = " <- trabalho aberto" if self.resumo.tem_trabalho_aberto else ""
        return f"{cabeca} | {self.resumo.descrever()}{marca}"

    def _sufixo_de_status(self) -> str:
        """Estado próprio do nó, quando ele tem um."""
        status = self.no.obter_propriedade("status")
        return f" [{status}]" if status is not None else ""


def ordenar_por_urgencia(filhos: Sequence[FilhoResumido]) -> tuple[FilhoResumido, ...]:
    """Quem tem trabalho aberto vem primeiro; o resto segue por identificador."""
    return tuple(sorted(filhos, key=lambda filho: (not filho.tem_trabalho_aberto, filho.no.id)))


def montar_secao_de_panorama(filhos: Sequence[FilhoResumido]) -> SecaoContexto:
    """Monta o panorama agrupado por tipo, pronto para encolher sob orçamento."""
    grupos = _agrupar_por_tipo(ordenar_por_urgencia(filhos))
    return SecaoContexto(
        titulo=TITULO_PANORAMA,
        linhas=tuple(linha for grupo in grupos for linha in grupo.linhas),
        ordem_exibicao=ORDEM_DE_EXIBICAO_DO_PANORAMA,
        prioridade_retencao=PrioridadeRetencao.NAVEGACAO,
        ids_incluidos=tuple(id_no for grupo in grupos for id_no in grupo.ids),
        grupos=grupos,
    )


def _agrupar_por_tipo(filhos: Sequence[FilhoResumido]) -> tuple[GrupoDeLinhas, ...]:
    """Reparte os filhos por tipo da ontologia, preservando a ordem interna."""
    por_tipo: dict[str, list[FilhoResumido]] = {}
    for filho in filhos:
        por_tipo.setdefault(filho.no.tipo.value, []).append(filho)
    return tuple(
        _montar_grupo(tipo, membros) for tipo, membros in sorted(por_tipo.items())
    )


def _montar_grupo(tipo: str, membros: Sequence[FilhoResumido]) -> GrupoDeLinhas:
    """Nomeia os filhos retidos do tipo e conta em uma linha o que ficou de fora."""
    nomeados = _selecionar_nomeados(membros)
    omitidos = len(membros) - len(nomeados)
    linhas = [membro.formatar() for membro in nomeados]
    if omitidos > 0:
        linhas.append(f"- ... e mais {omitidos} do tipo {tipo} (use buscar para listar)")
    return GrupoDeLinhas(
        rotulo=tipo,
        linhas=tuple(linhas),
        ids=tuple(membro.no.id for membro in nomeados),
    )


def _selecionar_nomeados(membros: Sequence[FilhoResumido]) -> tuple[FilhoResumido, ...]:
    """Todos os que têm trabalho aberto, mais os primeiros do resto até o teto."""
    com_trabalho = [membro for membro in membros if membro.tem_trabalho_aberto]
    restantes = [membro for membro in membros if not membro.tem_trabalho_aberto]
    vagas = max(0, LIMITE_DE_FILHOS_NOMEADOS_POR_TIPO - len(com_trabalho))
    return tuple(com_trabalho + restantes[:vagas])
