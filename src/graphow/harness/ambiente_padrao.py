"""O ambiente padrão da memória: o Projeto do repositório e o Setor `Memoria` dentro dele.

O hook de início exigia `--setor` com o id de um Setor criado à mão no grafo, e
sem ele a sessão não era aberta: nada de fechamento, de condensação nem de
aprendizado. A memória precisa de um lugar para nascer sem cerimônia, e o lugar
é o próprio repositório: um Projeto com o nome da pasta e um Setor de memória
dentro dele, criados na primeira sessão e reaproveitados nas seguintes.

Esse Projeto é das sessões do hook, e não de trabalho. O hook reaproveitava o
Projeto que o humano tivesse criado com o nome do repositório, e com isso as
sessões e os Runs de telemetria iam parar no meio do trabalho estruturado.
Agora ele só reconhece o ambiente que ele mesmo criou, pela proveniência (ver
`projection.ambito`), e um id derivado já ocupado por outro nó ganha sufixo.
"""

from dataclasses import dataclass
from itertools import count
from pathlib import Path
import re
import unicodedata

from graphow.core.models import NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.harness.identidade_harness import IdentidadeHarness
from graphow.harness.repositorio import nome_do_projeto
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.ambito import eh_ambiente_do_hook
from graphow.projection.graph_view import GrafoView

ROTULO_DO_SETOR_DE_MEMORIA: str = "Memoria"
DESCRICAO_DO_SETOR_DE_MEMORIA: str = (
    "Ambiente padrao da memoria: as sessoes do harness, seus fechamentos, "
    "condensacoes e aprendizados deste repositorio."
)
PREFIXO_DE_PROJETO: str = "proj"
PREFIXO_DE_SETOR: str = "setor"
SUFIXO_DO_SETOR_DE_MEMORIA: str = "memoria"
SLUG_RESERVA: str = "projeto"
RAMO_PADRAO: str = "main"
_NAO_ALFANUMERICO: re.Pattern[str] = re.compile(r"[^a-z0-9]+")


def gerar_slug(texto: str) -> str:
    """Identificador estável a partir de um nome: minúsculas e hífens, sem acento nem espaço."""
    sem_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    slug = _NAO_ALFANUMERICO.sub("-", sem_acentos.lower()).strip("-")
    return slug or SLUG_RESERVA


@dataclass(frozen=True)
class AmbientePadrao:
    """Os identificadores e rótulos do ambiente padrão de um repositório."""

    nome_do_projeto: str

    @classmethod
    def do_diretorio(cls, diretorio: str) -> "AmbientePadrao":
        """Deriva do diretório de trabalho; vazio significa o diretório corrente do processo."""
        caminho = Path(diretorio) if diretorio.strip() else Path.cwd()
        return cls(nome_do_projeto=nome_do_projeto(caminho))

    @property
    def slug(self) -> str:
        """A forma do nome que entra nos identificadores."""
        return gerar_slug(self.nome_do_projeto)

    @property
    def id_projeto(self) -> str:
        """Id derivado do Projeto do ambiente, usado ao criá-lo quando nenhum outro nó o ocupa."""
        return f"{PREFIXO_DE_PROJETO}-{self.slug}"

    @property
    def id_setor(self) -> str:
        """Id derivado do Setor de memória do repositório, com a mesma regra de ocupação."""
        return f"{PREFIXO_DE_SETOR}-{self.slug}-{SUFIXO_DO_SETOR_DE_MEMORIA}"

    @property
    def rotulo_do_projeto(self) -> str:
        """O Projeto se chama como a pasta do repositório."""
        return self.nome_do_projeto

    @property
    def rotulo_do_setor(self) -> str:
        """O Setor de memória tem o mesmo rótulo em todo repositório."""
        return ROTULO_DO_SETOR_DE_MEMORIA


@dataclass(frozen=True)
class IdsDoAmbiente:
    """Os ids com que o ambiente nasce: os derivados do nome ou, ocupados, os primeiros livres depois deles."""

    id_projeto: str
    id_setor: str

    @classmethod
    def reservar(cls, ambiente: AmbientePadrao, projeto: NoGrafo | None, view: GrafoView) -> "IdsDoAmbiente":
        """Mantém o Projeto já achado e procura id livre para o que ainda vai nascer."""
        id_projeto = projeto.id if projeto is not None else primeiro_id_livre(ambiente.id_projeto, view)
        return cls(id_projeto=id_projeto, id_setor=primeiro_id_livre(ambiente.id_setor, view))


def primeiro_id_livre(base: str, view: GrafoView) -> str:
    """O id derivado, se nenhum nó o usa; senão o primeiro `<id>-2`, `<id>-3`... livre.

    Criar com um id que já existe falharia o lote inteiro, e a sessão nasceria
    sem Setor, só com telemetria.
    """
    if not view.contem_no(base):
        return base
    return next(candidato for candidato in (f"{base}-{n}" for n in count(2)) if not view.contem_no(candidato))


def localizar_projeto(ambiente: AmbientePadrao, view: GrafoView) -> NoGrafo | None:
    """O ambiente do repositório entre os que o hook criou: pelo id derivado ou pelo nome da pasta.

    Um Projeto de trabalho com o nome do repositório, ou até com o id derivado,
    não é o ambiente. Pendurar nele as sessões do hook o encheria de sessões e
    Runs de telemetria, que é justamente o que a separação evita.
    """
    pelo_id = view.obter_no(ambiente.id_projeto)
    if pelo_id is not None and eh_ambiente_do_hook(pelo_id):
        return pelo_id
    nome = ambiente.nome_do_projeto.strip().casefold()
    candidatos = [
        no
        for no in view.listar_nos_por_tipo(TipoNo.PROJETO)
        if eh_ambiente_do_hook(no) and no.rotulo.strip().casefold() == nome
    ]
    return min(candidatos, key=lambda no: (no.ordem.seq_criacao, no.id), default=None)


def localizar_setor_de_memoria(projeto: NoGrafo, ambiente: AmbientePadrao, view: GrafoView) -> NoGrafo | None:
    """O Setor de memória do Projeto: pelo id derivado ou pelo rótulo `Memoria`."""
    rotulo = ambiente.rotulo_do_setor.casefold()
    for filho in view.obter_filhos_por_contencao(projeto.id):
        if filho.tipo != TipoNo.SETOR:
            continue
        if filho.id == ambiente.id_setor or filho.rotulo.strip().casefold() == rotulo:
            return filho
    return None


class GarantidorDeAmbientePadrao:
    """Garante que o Projeto e o Setor de memória existem, criando só o que falta."""

    def __init__(self, kernel: WriteKernel, identidade: IdentidadeHarness | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._identidade: IdentidadeHarness = identidade or IdentidadeHarness()

    def garantir(self, ambiente: AmbientePadrao, ramo_id: str = RAMO_PADRAO) -> str:
        """Devolve o id do Setor de memória; vazio quando o grafo recusou criá-lo."""
        view = self._kernel.obter_view(ramo_id)
        projeto = localizar_projeto(ambiente, view)
        setor = localizar_setor_de_memoria(projeto, ambiente, view) if projeto is not None else None
        if setor is not None:
            return setor.id
        ids = IdsDoAmbiente.reservar(ambiente, projeto, view)
        dados = DadosPropostaPatch(
            autor=self._identidade.autor,
            papel=self._identidade.papel,
            operacoes=montar_operacoes_do_ambiente(ambiente, ids, criar_projeto=projeto is None),
            justificativa=f"Ambiente padrao da memoria do repositorio '{ambiente.nome_do_projeto}'",
            ramo_id=ramo_id,
        )
        recibo = self._kernel.submeter_patch(PropostaPatch.criar(dados))
        return ids.id_setor if recibo.sucesso else ""


def montar_operacoes_do_ambiente(
    ambiente: AmbientePadrao, ids: IdsDoAmbiente, *, criar_projeto: bool
) -> tuple[ItemPatch, ...]:
    """O Projeto, se ainda não existe, e o Setor de memória pendurado nele no mesmo lote."""
    operacoes: list[ItemPatch] = []
    if criar_projeto:
        operacoes.append(_operacao_de_no(ids.id_projeto, TipoNo.PROJETO, ambiente.rotulo_do_projeto))
    operacoes.append(
        _operacao_de_no(
            ids.id_setor,
            TipoNo.SETOR,
            ambiente.rotulo_do_setor,
            propriedades={"descricao": DESCRICAO_DO_SETOR_DE_MEMORIA},
        )
    )
    operacoes.append(_operacao_de_contencao(ids.id_projeto, ids.id_setor))
    return tuple(operacoes)


def _operacao_de_no(id_no: str, tipo: TipoNo, rotulo: str, *, propriedades: dict[str, str] | None = None) -> ItemPatch:
    """Operação de criação de um contêiner do ambiente padrão."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_no}",
        value={"id": id_no, "tipo": tipo.value, "rotulo": rotulo, "propriedades": dict(propriedades or {})},
    )


def _operacao_de_contencao(id_projeto: str, id_setor: str) -> ItemPatch:
    """A aresta `contem` que pendura o Setor de memória no Projeto, no mesmo lote."""
    id_aresta = f"contem-{id_projeto}-{id_setor}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": id_projeto, "destino_id": id_setor, "tipo": TipoAresta.CONTEM.value},
    )
