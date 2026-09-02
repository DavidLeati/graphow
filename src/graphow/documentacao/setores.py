"""Definição das alas temáticas da biblioteca e montagem do catálogo."""

from dataclasses import dataclass

from graphow.core.exceptions import GraphowError
from graphow.documentacao.extrator import ExtratorCatalogo
from graphow.documentacao.leitura_fonte import LeitorCodigoFonte
from graphow.documentacao.modelo import CatalogoRepositorio, SetorDocumentado


@dataclass(frozen=True)
class DefinicaoSetor:
    """Metadados curados de uma ala: o que ela é e por que existe.

    A missão é a única parte do catálogo escrita à mão. Tudo o mais é derivado
    do código, para que a documentação não possa divergir dele em silêncio.
    """

    numero: int
    pacote: str
    titulo: str
    missao: str


DEFINICOES_DE_SETOR: tuple[DefinicaoSetor, ...] = (
    DefinicaoSetor(
        1,
        "core",
        "Núcleo Ontológico",
        "Vocabulário da ontologia, modelos imutáveis do grafo, eventos do log, os modos de falha da taxonomia MAST e a hierarquia de exceções de domínio. Não depende de nenhum outro setor.",
    ),
    DefinicaoSetor(
        2,
        "kernel",
        "Kernel de Escrita (PatchBoard)",
        "Os quatro portões de governança, a conversão de JSON Patch em eventos e o commit transacional. Único caminho de mutação do estado compartilhado.",
    ),
    DefinicaoSetor(
        3,
        "storage",
        "Persistência Append-Only",
        "Repositórios de eventos, locks e linhagem de ramos. Resolve onde o banco vive, migra bancos antigos e repara sequências duplicadas.",
    ),
    DefinicaoSetor(
        4,
        "projection",
        "Projeção Determinística",
        "Dobra os eventos do log no estado em memória e mantém a projeção reconciliada com o que foi persistido por outros escritores.",
    ),
    DefinicaoSetor(
        5,
        "reactive",
        "Motor Reativo",
        "Comportamentos desacoplados que observam commits e propõem patches derivados, com limite de cascata e guarda de reentrância.",
    ),
    DefinicaoSetor(
        6,
        "context",
        "Divulgação Progressiva",
        "Recorta o subgrafo relevante ao alvo por papel e o renderiza sob orçamento estrito de tokens, descartando seções por prioridade.",
    ),
    DefinicaoSetor(
        7,
        "lineage",
        "Linhagem e Ramificação",
        "Rastreio causal reverso até o Goal raiz, replay pontual com instantâneos e forks registrados como ponteiro para o ponto de corte.",
    ),
    DefinicaoSetor(
        8,
        "harness",
        "Integração com Harness",
        "Ponto de entrada para hooks de ambiente registrarem sessões e execuções, sob identidade fixada na configuração.",
    ),
    DefinicaoSetor(
        9,
        "observability",
        "Observabilidade e Taxonomia MAST",
        "Traduz o modo de falha que o portão declarou em categoria MAST e recebe os spans GenAI do kernel, em memória ou em arquivo NDJSON.",
    ),
    DefinicaoSetor(
        10,
        "mcp",
        "Superfície MCP",
        "Ferramentas expostas a agentes via Model Context Protocol, com o papel fixado na abertura da sessão e recusado nos argumentos.",
    ),
    DefinicaoSetor(
        11,
        "api",
        "Linha de Comando e Transporte",
        "Interface de terminal, resolução de dependências por subcomando e formatação de eventos para transporte SSE.",
    ),
    DefinicaoSetor(
        12,
        "web",
        "Canvas e API REST",
        "Servidor HTTP, controladores REST por área e o canal de tempo real que leva cada commit ao canvas.",
    ),
    DefinicaoSetor(
        13,
        "avaliacao",
        "Harness de Avaliação",
        "Corpus de tarefas gravadas e medição de tokens por tarefa bem-sucedida, com e sem o recorte do grafo. Existe para que a métrica principal do plano tenha número em vez de afirmação.",
    ),
    DefinicaoSetor(
        14,
        "documentacao",
        "Geração deste Catálogo",
        "Extrai o catálogo do próprio código e renderiza o índice e os dossiês. Existe para que a documentação não seja mantida à mão.",
    ),
)


class MontadorCatalogo:
    """Monta o catálogo completo a partir do código-fonte lido."""

    def __init__(
        self,
        leitor: LeitorCodigoFonte,
        extrator: ExtratorCatalogo | None = None,
    ) -> None:
        self._leitor: LeitorCodigoFonte = leitor
        self._extrator: ExtratorCatalogo = extrator or ExtratorCatalogo()

    def montar(self) -> CatalogoRepositorio:
        """Consulta pura: percorre as definições e devolve o catálogo montado."""
        pacotes_existentes = frozenset(self._leitor.listar_pacotes())
        self._recusar_definicoes_orfas(pacotes_existentes)
        return CatalogoRepositorio(
            setores=tuple(self._montar_setor(definicao) for definicao in DEFINICOES_DE_SETOR)
        )

    def _recusar_definicoes_orfas(self, pacotes_existentes: frozenset[str]) -> None:
        """Uma ala sem pacote correspondente indica catálogo desalinhado do código."""
        declarados = {definicao.pacote for definicao in DEFINICOES_DE_SETOR}
        ausentes = sorted(declarados - pacotes_existentes)
        se_sobram = sorted(pacotes_existentes - declarados)
        if ausentes or se_sobram:
            raise GraphowError(
                "As alas declaradas nao correspondem aos pacotes do codigo",
                {"sem_pacote": ", ".join(ausentes), "sem_ala": ", ".join(se_sobram)},
            )

    def _montar_setor(self, definicao: DefinicaoSetor) -> SetorDocumentado:
        """Extrai o catálogo de todos os módulos de um pacote."""
        modulos = tuple(
            self._extrator.extrair_modulo(arquivo)
            for arquivo in self._leitor.ler_modulos(definicao.pacote)
        )
        return SetorDocumentado(
            numero=definicao.numero,
            identificador=definicao.pacote,
            titulo=definicao.titulo,
            missao=definicao.missao,
            modulos=modulos,
        )
