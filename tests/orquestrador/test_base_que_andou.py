"""A integração do Goal: o cancelamento que chega no meio do passo, e a base que andou desde que a branch do Goal saiu dela."""

from collections.abc import Callable, Sequence
from pathlib import Path
import subprocess

import pytest

from graphow.core.models import NoGrafo
from graphow.core.types import TipoNo
from graphow.orquestrador import base_que_andou
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal
from graphow.orquestrador.pedidos_do_humano import PEDIDO_CANCELAR, NovoPedido
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    Bancada,
    Queda,
    ate_o_portao_aprovado,
    executor_pronto,
    montar_bancada,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
RAMO: str = "graphow/soma"
SOMA_COM_CABECALHO: str = "# soma de inteiros\ndef somar(a, b):\n    return 0\n"
SOMA_QUE_SUBTRAI: str = "def somar(a, b):\n    return a - b\n"
SOMA_DA_BASE_QUE_CONFLITA: str = "def somar(a, b):\n    # so inteiros\n    return 0\n"
SOMA_RESOLVIDA: str = "def somar(a, b):\n    # so inteiros\n    return a + b\n"
OPCAO_DO_PROMPT: str = "--append-system-prompt-file"


class ExecutorQueAndaABase(ExecutorDeSessao):
    """Roda a sessão e, depois da primeira do papel dado, faz o commit do humano na base do repositório dele."""

    def __init__(self, base: ExecutorDeSessao, papel: str, andar: Callable[[], None]) -> None:
        super().__init__(base._executavel, base._ambiente)
        self._papel: str = papel
        self._andar: Callable[[], None] = andar
        self._andou: bool = False

    def rodar(self, pedido: PedidoDeSessao) -> ResultadoDeSessao:
        """A sessão roda; depois da primeira do papel, a base anda."""
        resultado = super().rodar(pedido)
        argumentos = list(pedido.argumentos_extras)
        prompt = argumentos[argumentos.index(OPCAO_DO_PROMPT) + 1] if OPCAO_DO_PROMPT in argumentos else ""
        if not self._andou and Path(prompt).stem == self._papel:
            self._andou = True
            self._andar()
        return resultado


def _roteiro_limpo() -> dict[str, list[dict[str, object]]]:
    """Plano, aceite, as duas fatias e a verificação final limpa de primeira."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende")]
    roteiro["executor"] = roteiro["executor"][:2]
    return roteiro


def _commit_do_humano(repositorio: Path, arquivo: str, conteudo: str) -> Callable[[], str]:
    """O commit que o humano faz na main dele, com o arquivo dado; a função devolve o hash."""
    def commitar() -> str:
        (repositorio / arquivo).write_text(conteudo, encoding="utf-8", newline="\n")
        git(repositorio, "add", "-A")
        git(repositorio, "commit", "-q", "-m", f"Humano muda {arquivo}")
        return git(repositorio, "rev-parse", "HEAD").strip()
    return commitar


def _andando_depois_do(bancada: Bancada, papel: str, arquivo: str, conteudo: str) -> tuple[ExecutorQueAndaABase, list[str]]:
    """O executor que faz o commit do humano depois da primeira sessão do papel, e a lista que recebe o hash dele."""
    hashes: list[str] = []
    humano = _commit_do_humano(bancada.repositorio, arquivo, conteudo)
    return ExecutorQueAndaABase(bancada.executor, papel, lambda: hashes.append(humano())), hashes


def _rebases(bancada: Bancada) -> list[NoGrafo]:
    """As Evidence de rebase do Goal no livro-razão."""
    evidencias = bancada.kernel.obter_view().listar_nos_por_tipo(TipoNo.EVIDENCE)
    return [no for no in evidencias if no.obter_propriedade("acao") == "rebase_do_goal"]


def _verificacoes(bancada: Bancada) -> list[str]:
    """O papel de cada sessão de verificação, na ordem: a caçada, o marco e a conferência."""
    return [chamada["papel"] for chamada in bancada.chamadas() if chamada["papel"] in ("verificador", "marco", "conferencia")]


def _na_historia(repositorio: Path, commit: str, ponta: str = "main") -> bool:
    """O commit está na história da ponta."""
    feito = subprocess.run(["git", "-C", str(repositorio), "merge-base", "--is-ancestor", commit, ponta], capture_output=True, check=False)
    return feito.returncode == 0


def test_cancelamento_que_chega_no_meio_do_passo_impede_a_integracao_edge_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caso de borda (revisão da T3b, achado 7): o `--cancelar` gravado depois da leitura do passo não deixa o Goal integrar."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())
    orquestrador = bancada.orquestrador()
    original = LivroRazaoDoGoal.resolver

    def resolver_e_cancelar(livro: LivroRazaoDoGoal, achados: Sequence[str], justificativa: str) -> None:
        orquestrador.pedir(livro.id_goal, NovoPedido(PEDIDO_CANCELAR, "desisti durante o fechamento", "david"))
        original(livro, achados, justificativa)

    monkeypatch.setattr(LivroRazaoDoGoal, "resolver", resolver_e_cancelar)
    base_antes = git(bancada.repositorio, "rev-parse", "main").strip()

    parada = orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.CANCELADO, parada.mensagem
    assert "antes da integracao" in parada.mensagem and "desisti durante o fechamento" in parada.mensagem
    assert git(bancada.repositorio, "rev-parse", "main").strip() == base_antes, "a base nao recebe o Goal cancelado"
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.cancelado


def test_base_que_andou_em_arquivo_de_fora_rebaseia_e_integra_sem_nova_verificacao_nominal(tmp_path: Path) -> None:
    """T3g.1: a base anda num arquivo que nenhuma fatia toca; rebase limpo, sem nova verificação, integração por fast-forward."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())
    executor, hashes = _andando_depois_do(bancada, "verificador", "NOTAS.txt", "anotacao do humano\n")

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert _verificacoes(bancada) == ["verificador"], "o rebase sem arquivo de criterio nao refaz a verificacao"
    assert git(bancada.repositorio, "rev-parse", "main").strip() == git(bancada.repositorio, "rev-parse", RAMO).strip()
    assert _na_historia(bancada.repositorio, hashes[0]) and git(bancada.repositorio, "rev-list", "--merges", "main") == ""
    trailers = git(bancada.repositorio, "log", "--format=%(trailers:key=Graphow-Task,valueonly)", f"{hashes[0]}..main").split()
    assert {"task-soma-f1", "task-soma-f2"} <= set(trailers), "os commits rebaseados mantem os trailers"
    (rebase,) = _rebases(bancada)
    assert rebase.obter_propriedade("verificacao_vale") is True and rebase.obter_propriedade("base_depois") == hashes[0]
    assert rebase.obter_propriedade("arquivos") == ["NOTAS.txt"] and rebase.obter_propriedade("cobertos") == []
    assert {item["task"] for item in rebase.obter_propriedade("fatias")} == {"task-soma-f1", "task-soma-f2"}
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and all(_na_historia(bancada.repositorio, f.texto("commit")) for f in estado.fatias)
    assert not _na_historia(bancada.repositorio, estado.verificacoes[-1].commit), "a verificacao foi feita antes do rebase"
    artefato = bancada.kernel.obter_view().obter_no("art-task-soma-f1-t1")
    assert artefato is not None and _na_historia(bancada.repositorio, str(artefato.obter_propriedade("commit")))
    assert not _na_historia(bancada.repositorio, str(artefato.obter_propriedade("commit_antes_do_rebase")))


def test_queda_entre_o_registro_do_rebase_e_as_refs_retoma_pelas_refs_edge_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caso de borda: o processo cai depois de gravar o rebase e antes das refs; rodar de novo leva as refs e integra."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())
    executor, hashes = _andando_depois_do(bancada, "verificador", "NOTAS.txt", "anotacao do humano\n")

    def cair(*_: object) -> None:
        raise Queda()

    monkeypatch.setattr(base_que_andou, "mover_as_refs", cair)
    with pytest.raises(Queda):
        bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    (rebase,) = _rebases(bancada)
    assert git(bancada.repositorio, "rev-parse", RAMO).strip() == rebase.obter_propriedade("commit_antes")
    monkeypatch.undo()

    parada = bancada.orquestrador().rodar("goal-soma", AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert git(bancada.repositorio, "rev-parse", "main").strip() == rebase.obter_propriedade("commit")
    assert _na_historia(bancada.repositorio, hashes[0]) and len(_rebases(bancada)) == 1
    assert _verificacoes(bancada) == ["verificador"]


def test_base_que_andou_em_arquivo_de_criterio_refaz_a_verificacao_final_antes_de_integrar_nominal(tmp_path: Path) -> None:
    """T3g.2: a base anda em soma.py (de C1) sem conflito; rebase limpo, e a verificação final roda de novo antes de integrar."""
    roteiro = _roteiro_limpo()
    roteiro["verificador"].append(verificacao("atende"))
    bancada = montar_bancada(tmp_path, roteiro)
    executor, _ = _andando_depois_do(bancada, "verificador", "soma.py", SOMA_COM_CABECALHO)

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert _verificacoes(bancada) == ["verificador", "conferencia"]
    (rebase,) = _rebases(bancada)
    assert rebase.obter_propriedade("verificacao_vale") is False and rebase.obter_propriedade("cobertos") == ["soma.py"]
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and len(estado.verificacoes) == 2
    assert not _na_historia(bancada.repositorio, estado.verificacoes[0].commit)
    assert estado.verificacoes[1].commit_do_codigo == rebase.obter_propriedade("commit_do_codigo")
    soma = git(bancada.repositorio, "show", "main:soma.py")
    assert soma.startswith("# soma de inteiros") and "return a + b" in soma


def test_conflito_com_a_base_no_supervisionado_para_com_os_arquivos_e_a_branch_intacta_edge_case(tmp_path: Path) -> None:
    """T3g.3: no supervisionado, o rebase com conflito sai, a parada traz soma.py, e a branch do Goal fica onde estava."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())
    orquestrador = ate_o_portao_aprovado(bancada)
    pronto = orquestrador.rodar("goal-soma", OpcoesDoLaco())
    assert pronto.motivo == MotivoDaParada.PRONTO_PARA_INTEGRAR, pronto.mensagem
    ponta = git(bancada.repositorio, "rev-parse", RAMO).strip()
    _commit_do_humano(bancada.repositorio, "soma.py", SOMA_QUE_SUBTRAI)()

    parada = orquestrador.rodar("goal-soma", OpcoesDoLaco())

    assert parada.motivo == MotivoDaParada.CONFLITO_COM_A_BASE, parada.mensagem
    assert "deu conflito em soma.py" in parada.mensagem and ponta[:12] in parada.mensagem
    assert git(bancada.repositorio, "rev-parse", RAMO).strip() == ponta
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.configuracao is not None
    area = Path(estado.configuracao.area)
    assert git(area, "rev-parse", "HEAD").strip() == ponta and git(area, "branch", "--show-current").strip() == RAMO
    assert git(area, "status", "--porcelain") == "" and not (area / ".git" / "rebase-merge").exists()
    assert _rebases(bancada) == [], "o rebase desfeito nao vai ao livro-razao"
    assert orquestrador.rodar("goal-soma", OpcoesDoLaco()).motivo == MotivoDaParada.CONFLITO_COM_A_BASE


def test_rebase_limpo_com_a_suite_vermelha_no_supervisionado_desfaz_e_para_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a base nova quebra a suíte sem conflito; o rebase sai, a branch fica, e a parada traz o fim da suíte."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())
    orquestrador = ate_o_portao_aprovado(bancada)
    assert orquestrador.rodar("goal-soma", OpcoesDoLaco()).motivo == MotivoDaParada.PRONTO_PARA_INTEGRAR
    ponta = git(bancada.repositorio, "rev-parse", RAMO).strip()
    _commit_do_humano(bancada.repositorio, "soma.py", "import modulo_que_nao_existe\ndef somar(a, b):\n    return 0\n")()

    parada = orquestrador.rodar("goal-soma", OpcoesDoLaco())

    assert parada.motivo == MotivoDaParada.CONFLITO_COM_A_BASE, parada.mensagem
    assert "deixou a suite vermelha" in parada.mensagem and "modulo_que_nao_existe" in parada.mensagem
    assert git(bancada.repositorio, "rev-parse", RAMO).strip() == ponta and _rebases(bancada) == []


def test_conflito_com_a_base_no_autonomo_abre_a_fatia_de_conflito_e_o_goal_fecha_depois_dela_nominal(tmp_path: Path) -> None:
    """T3g.4: no autônomo, o conflito vira a fatia M1.R1 sobre a base nova; ela resolve, a verificação roda de novo e o Goal fecha."""
    roteiro = _roteiro_limpo()
    roteiro["executor"].append(executor_pronto({"soma.py": SOMA_RESOLVIDA}))
    roteiro["verificador"].append(verificacao("atende"))
    bancada = montar_bancada(tmp_path, roteiro)
    executor, hashes = _andando_depois_do(bancada, "verificador", "soma.py", SOMA_DA_BASE_QUE_CONFLITA)

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    (conflito,) = [fatia for fatia in estado.fatias if fatia.codigo == "M1.R1"]
    assert conflito.status == "concluido" and conflito.propriedades["conflito_com_a_base"]["arquivos"] == ["soma.py"]
    briefing = bancada.chamadas("executor")[2]["stdin"]
    assert "deu conflito em soma.py" in briefing and "<<<<<<<" in briefing and "# so inteiros" in briefing
    assert git(bancada.repositorio, "show", "main:soma.py") == SOMA_RESOLVIDA
    assert _na_historia(bancada.repositorio, hashes[0]) and git(bancada.repositorio, "rev-list", "--merges", "main") == ""
    trailers = git(bancada.repositorio, "log", "--format=%(trailers:key=Graphow-Task,valueonly)", f"{hashes[0]}..main").split()
    assert trailers == [conflito.id], "a historia da branch e a base nova mais o commit da fatia de conflito"
    assert _verificacoes(bancada) == ["verificador", "conferencia"]
    (rebase,) = _rebases(bancada)
    assert rebase.obter_propriedade("fatia_de_conflito") == conflito.id and rebase.obter_propriedade("verificacao_vale") is False
    plano = [fatia for fatia in estado.fatias if fatia.codigo in ("F1", "F2")]
    assert {fatia.texto("commit") for fatia in plano} == {conflito.texto("commit")}
