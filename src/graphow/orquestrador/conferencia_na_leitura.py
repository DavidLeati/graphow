"""A conferência da Evidence na hora da leitura: o briefing, a vista, o canvas e o `--status` perguntam aqui.

A conferência em si mora em orquestrador/conferencia_da_evidencia.py. Aqui
fica o que cada leitor precisa em volta dela:

- a Evidence que não é sobre código e não tem âncora (a fonte, o log de teste,
  o veredito do revisor do MCP) não leva marca: não afirma nada do código;
- a sobre código sem âncora, a antiga gravada antes da regra, sai `sem_ancora`,
  sem precisar de git;
- a ancorada é conferida no git da leitura; sem repositório à mão, sai
  `nao_conferida`, e o leitor não adivinha.

A vista e o canvas não têm área nem repositório: a Evidence do orquestrador
confere no repositório do humano, na branch do Goal dela, que a configuração
gravada no Goal diz (a branch existe enquanto o Goal vive e depois do fecho,
quando a área já foi removida). A de outro papel não tem repositório gravado e
sai `nao_conferida`.

A revisão de risco confere no clone do Goal (a `area` da configuração),
enquanto ele existe: a árvore da revisão rejeitada só fica lá, porque a
tentativa não vira commit e o repositório do humano só recebe o que a branch
alcança. Sem o clone, ela confere no repositório do humano, onde a árvore da
aprovada está (é a do commit da fatia); a que não está lá sai `nao_conferida`,
com o motivo, e não `sem_ancora`: o objeto não sumiu, só não está à mão.

Cada leitura tem o seu cache (`GitDaLeitura`): cada consulta ao git, o
`diff --name-only` por par de commits inclusive, roda uma vez por leitura. O
canvas guarda as consultas também entre pedidos (`MemoriaDasPontas`): a tela
recarrega a cada evento do grafo, e cada pedido conferia de novo todas as
Evidence do orquestrador (na revisão da T3d2, 4 Evidence custavam 13 processos
git). A leitura resolve a ponta da branch num hash, com um `rev-parse` por
pedido, e as consultas guardadas valem enquanto a ponta for a mesma: a chave é
o commit da Evidence (está nos argumentos) e a ponta.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any

from graphow.core.models import NoGrafo
from graphow.core.orquestracao import ler_texto
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.ancora_da_evidencia import ancora_da_evidencia, sobre_codigo
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.conferencia_da_evidencia import (
    CAMPO_ARVORE,
    DESATUALIZADA,
    SEM_ANCORA,
    VIGENTE,
    ConferenciaDaEvidencia,
    conferir_evidencia,
    sem_ancora,
)
from graphow.orquestrador.git_do_goal import GitDoGoal, SaidaDoGit
from graphow.projection.graph_view import GrafoView

NAO_CONFERIDA: str = "nao_conferida"
PAPEL_DO_ORQUESTRADOR: str = PapelAutor.ORQUESTRADOR.value
MAXIMO_DE_ARQUIVOS_NO_ROTULO: int = 8
ROTULOS: dict[str, str] = {VIGENTE: "vigente", SEM_ANCORA: "sem ancora", NAO_CONFERIDA: "nao conferida"}


@dataclass(frozen=True)
class GitDaLeitura(GitDoGoal):
    """O git de uma leitura: cada consulta roda uma vez e fica guardada até a leitura acabar."""

    memoria: dict[tuple[str, ...], SaidaDoGit] = field(default_factory=dict, compare=False, repr=False)

    def tentar(self, *argumentos: str) -> SaidaDoGit:
        """A consulta, do cache quando a leitura já a fez."""
        if argumentos not in self.memoria:
            self.memoria[argumentos] = super().tentar(*argumentos)
        return self.memoria[argumentos]


class LeituraDaConferencia:
    """Uma leitura: o git em que a Evidence ancorada confere (ou nenhum) e a ponta."""

    def __init__(self, git: GitDoGoal | None, ponta: str = "HEAD", *, memoria: dict[tuple[str, ...], SaidaDoGit] | None = None) -> None:
        self._git: GitDaLeitura | None = None if git is None else GitDaLeitura(git.pasta, {} if memoria is None else memoria)
        self._ponta: str = ponta

    @property
    def com_git(self) -> bool:
        """A leitura tem um repositório à mão para conferir a ancorada."""
        return self._git is not None

    def conferir(self, papel: str, propriedades: Mapping[str, Any]) -> ConferenciaDaEvidencia | None:
        """A conferência da Evidence gravada pelo papel; None quando ela não é sobre código nem tem âncora."""
        if ancora_da_evidencia(propriedades) is None:
            return sem_ancora(propriedades) if sobre_codigo(papel, propriedades) else None
        if self._git is None:
            return ConferenciaDaEvidencia(NAO_CONFERIDA, motivo="sem repositorio git a mao nesta leitura")
        return conferir_evidencia(propriedades, self._git, self._ponta)


class MemoriaDasPontas:
    """O que o canvas guarda entre pedidos: por repositório e branch, a ponta conferida e as consultas ao git feitas nela."""

    def __init__(self) -> None:
        self._por_ramo: dict[tuple[str, str], tuple[str, dict[tuple[str, ...], SaidaDoGit]]] = {}
        self._trava: threading.Lock = threading.Lock()

    def da_ponta(self, pasta: str, ramo: str, ponta: str) -> dict[tuple[str, ...], SaidaDoGit]:
        """As consultas guardadas na ponta dada; vazias, e as da ponta anterior esquecidas, quando ela andou."""
        with self._trava:
            guardada = self._por_ramo.get((pasta, ramo))
            if guardada is None or guardada[0] != ponta:
                guardada = (ponta, {})
                self._por_ramo[(pasta, ramo)] = guardada
            return guardada[1]


def leitura_do_repositorio(repositorio: object, ramo: object, *, memoria: MemoriaDasPontas | None = None) -> LeituraDaConferencia:
    """A leitura no repositório, na ponta da branch (o hash); sem git quando a pasta não é repositório ou a branch não existe."""
    pasta, nome = Path(str(repositorio or "")), str(ramo or "")
    if not str(repositorio or "") or not nome or not pasta.is_dir():
        return LeituraDaConferencia(None)
    git = GitDoGoal(pasta)
    feito = git.tentar("rev-parse", "--verify", "--quiet", f"refs/heads/{nome}^{{commit}}")
    if feito.codigo != 0 or not feito.saida.strip():
        return LeituraDaConferencia(None)
    ponta = feito.saida.strip()
    guardadas = None if memoria is None else memoria.da_ponta(str(pasta), nome, ponta)
    return LeituraDaConferencia(git, ponta, memoria=guardadas)


def rotulo_da_conferencia(conferencia: ConferenciaDaEvidencia) -> str:
    """O rótulo curto: `vigente`, `desatualizada (mudaram: ...)`, `sem ancora` ou `nao conferida`."""
    if conferencia.estado != DESATUALIZADA:
        return ROTULOS.get(conferencia.estado, conferencia.estado)
    arquivos = list(conferencia.arquivos[:MAXIMO_DE_ARQUIVOS_NO_ROTULO])
    resto = len(conferencia.arquivos) - len(arquivos)
    return "desatualizada (mudaram: " + ", ".join(arquivos) + (f" e mais {resto}" if resto > 0 else "") + ")"


def marca_da_conferencia(conferencia: ConferenciaDaEvidencia) -> str:
    """O rótulo com o motivo, quando há: a vista, o `--rastro` e o inspetor dizem por quê, e não só o estado.

    A sem âncora e a não conferida sempre têm motivo. A vigente e a
    desatualizada têm quando o commit está fora da branch (`vigente: commit
    fora da branch: ...`): o rótulo é o do conteúdo, que pode seguir igual, e o
    aviso é o da história.
    """
    rotulo = rotulo_da_conferencia(conferencia)
    return f"{rotulo}: {conferencia.motivo}" if conferencia.motivo else rotulo


def conferencia_em_json(conferencia: ConferenciaDaEvidencia | None) -> dict[str, Any] | None:
    """A conferência como o canvas a manda ao inspetor, com o rótulo curto e a marca com o motivo; None sem conferência."""
    if conferencia is None:
        return None
    return {"estado": conferencia.estado, "arquivos": list(conferencia.arquivos), "motivo": conferencia.motivo,
            "rotulo": rotulo_da_conferencia(conferencia), "marca": marca_da_conferencia(conferencia)}


def aviso_de_historico(conferencia: ConferenciaDaEvidencia) -> str:
    """O aviso do briefing para a Evidence que não vale na ponta: o estado em maiúsculas e os arquivos, ou o motivo."""
    if conferencia.estado == DESATUALIZADA:
        return f"DESATUALIZADA: {', '.join(conferencia.arquivos)} mudaram desde o commit dela"
    estado = rotulo_da_conferencia(conferencia).upper()
    return f"{estado} ({conferencia.motivo})" if conferencia.motivo else estado


class LeituraPorGoal:
    """A leitura da vista e do canvas: a Evidence do orquestrador confere na branch do Goal dela; as outras, sem git.

    Com a memória (a do canvas), as consultas ao git ficam guardadas entre leituras enquanto a ponta não anda.
    """

    def __init__(self, view: GrafoView, memoria: MemoriaDasPontas | None = None) -> None:
        self._view: GrafoView = view
        self._memoria: MemoriaDasPontas | None = memoria
        self._sem_git: LeituraDaConferencia = LeituraDaConferencia(None)
        self._por_pasta: dict[tuple[str, str], LeituraDaConferencia] = {}

    def conferir(self, no: NoGrafo) -> ConferenciaDaEvidencia | None:
        """A conferência do nó Evidence; None para os outros tipos e para a Evidence livre."""
        if no.tipo != TipoNo.EVIDENCE:
            return None
        papel, propriedades = no.proveniencia.papel, no.propriedades
        configuracao = self._configuracao(no) if papel == PAPEL_DO_ORQUESTRADOR else None
        if configuracao is None:
            return self._sem_git.conferir(papel, propriedades)
        if ler_texto(propriedades, CAMPO_ARVORE):
            return self._conferir_a_revisao(configuracao, no)
        return self._leitura(configuracao, "repositorio").conferir(papel, propriedades)

    def _conferir_a_revisao(self, configuracao: Mapping[str, Any], no: NoGrafo) -> ConferenciaDaEvidencia | None:
        """A revisão de risco no clone do Goal; sem ele, no repositório do humano, onde a árvore da rejeitada não está."""
        papel, propriedades = no.proveniencia.papel, no.propriedades
        no_clone = self._leitura(configuracao, "area")
        if no_clone.com_git:
            return no_clone.conferir(papel, propriedades)
        conferencia = self._leitura(configuracao, "repositorio").conferir(papel, propriedades)
        if conferencia is None or conferencia.estado != SEM_ANCORA or ancora_da_evidencia(propriedades) is None:
            return conferencia
        arvore = ler_texto(propriedades, CAMPO_ARVORE)[:12]
        motivo = f"a arvore revisada {arvore} so ficou no clone do Goal, que nao existe mais: {configuracao.get('area')}"
        return ConferenciaDaEvidencia(NAO_CONFERIDA, motivo=motivo)

    def _leitura(self, configuracao: Mapping[str, Any], campo: str) -> LeituraDaConferencia:
        """A leitura na pasta do campo (o repositório do humano ou o clone), na branch do Goal, guardada por pasta."""
        chave = (str(configuracao.get(campo) or ""), str(configuracao.get("ramo") or ""))
        if chave not in self._por_pasta:
            self._por_pasta[chave] = leitura_do_repositorio(*chave, memoria=self._memoria)
        return self._por_pasta[chave]

    def _configuracao(self, no: NoGrafo) -> Mapping[str, Any] | None:
        """A configuração gravada no Goal de onde a Evidence deriva."""
        goal = self._goal_configurado(no)
        return None if goal is None else goal.obter_propriedade(m.CAMPO_ORQUESTRACAO)

    def _goal_configurado(self, no: NoGrafo) -> NoGrafo | None:
        """O Goal de onde a Evidence deriva, direto (a verificação, o rebase) ou pela fatia (a revisão de risco)."""
        derivados = [self._view.obter_no(a.destino_id) for a in self._view.obter_arestas_saida(no.id, TipoAresta.DERIVA_DE)]
        pais = [self._view.obter_no(a.origem_id) for d in derivados if d is not None and d.tipo == TipoNo.TASK
                for a in self._view.obter_arestas_entrada(d.id, TipoAresta.DECOMPOE)]
        return next((g for g in (*derivados, *pais) if g is not None and _configurado(g)), None)


def _configurado(no: NoGrafo) -> bool:
    """O Goal que o orquestrador conduz, com a configuração gravada."""
    return no.tipo == TipoNo.GOAL and isinstance(no.obter_propriedade(m.CAMPO_ORQUESTRACAO), Mapping)
