"""Os leitores conferem a Evidence na leitura: o `--status`, a vista e o canvas marcam a desatualizada e a sem âncora.

O banco é montado direto no log, como um banco antigo: o replay não passa
pelos portões, e assim a verificação sem commit (de antes da regra) convive
com as ancoradas. O Goal aponta para um repositório de brinquedo, na branch
main, em que `a.py` mudou depois do commit das verificações.
"""

from pathlib import Path
from typing import Any

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.kernel.composicao import abrir_kernel_sqlite
from graphow.kernel.conversao_eventos import ConversorPatchParaEventos
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.conferencia_na_leitura import LeituraDaConferencia, LeituraPorGoal
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.status import formatar_status
from graphow.storage.sqlite_store import SQLiteEventStore
from graphow.web.rest_canvas_controller import CanvasWebController

from tests.orquestrador.apoio_git import criar_repositorio, git

GOAL: str = "goal-leitores"
LIDA_NO_ARQUIVO: dict[str, Any] = {"arquivo": "a.py", "linhas": "1", "trecho": "A = 1"}


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, Any]) -> list[ItemPatch]:
    """O nó e a aresta `deriva_de` dele para o Goal (o próprio Goal, sem aresta)."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades}
    operacoes = [ItemPatch(OperacaoPatch.ADD, f"/nos/{id_no}", valor)]
    if id_no != GOAL:
        aresta = {"id": f"deriva-{id_no}", "origem_id": id_no, "destino_id": GOAL, "tipo": TipoAresta.DERIVA_DE.value}
        operacoes.append(ItemPatch(OperacaoPatch.ADD, f"/arestas/deriva-{id_no}", aresta))
    return operacoes


def _verificacao(numero: int, **ancora: Any) -> list[ItemPatch]:
    """A verificação do orquestrador, com a âncora dada (ou nenhuma, a antiga)."""
    propriedades = {"acao": m.ACAO_DA_VERIFICACAO, m.CAMPO_VEREDITO: m.VEREDITO_LIMPO, m.CAMPO_CICLO: 1, "marco": "M1", **ancora}
    return _no(f"ver-{GOAL}-{numero}", TipoNo.EVIDENCE, propriedades)


def _banco(tmp_path: Path, repositorio: Path) -> Path:
    """O log com o Goal configurado, três verificações (desatualizada, vigente, antiga) e três Evidence de agente."""
    visto = git(repositorio, "rev-parse", "HEAD").strip()
    (repositorio / "a.py").write_text("A = 2\n", encoding="utf-8", newline="\n")
    git(repositorio, "commit", "-q", "-am", "muda a.py")
    configuracao = {"modo": "autonomo", "repositorio": str(repositorio), "area": str(tmp_path / "area-removida"), "ramo": "main",
                    "base": "main", "slug": "leitores", "orcamento_usd": 1.0}
    do_orquestrador = [*_no(GOAL, TipoNo.GOAL, {m.CAMPO_ORQUESTRACAO: configuracao}),
                       *_verificacao(1, commit=visto, arquivos=["a.py"]), *_verificacao(2, commit=visto, arquivos=["b.py"]),
                       *_verificacao(3, commit="abc1234")]
    do_agente = [*_no("evi-antiga", TipoNo.EVIDENCE, dict(LIDA_NO_ARQUIVO)),
                 *_no("evi-ancorada", TipoNo.EVIDENCE, {**LIDA_NO_ARQUIVO, "commit": visto}),
                 *_no("evi-fonte", TipoNo.EVIDENCE, {"fonte": "https://exemplo.invalid", "resumo": "lido"})]
    eventos: list[Any] = []
    for papel, operacoes in ((PapelAutor.ORQUESTRADOR, do_orquestrador), (PapelAutor.EXECUTOR, do_agente)):
        proposta = PropostaPatch.criar(DadosPropostaPatch(autor=f"autor-{papel.value}", papel=papel, operacoes=tuple(operacoes),
                                                          justificativa="banco de teste"))
        eventos += ConversorPatchParaEventos().converter(proposta, len(eventos))
    banco = tmp_path / "leitores.db"
    with SQLiteEventStore(banco) as store:
        store.append_eventos(eventos)
    return banco


def _repositorio(tmp_path: Path) -> Path:
    """O repositório de brinquedo, com a.py e b.py na main."""
    return criar_repositorio(tmp_path / "repo", {"a.py": "A = 1\n", "b.py": "B = 1\n"})


def test_status_marca_a_verificacao_desatualizada_com_os_arquivos_e_a_antiga_sem_ancora_nominal(tmp_path: Path) -> None:
    """T3d2.2: o `--status` confere cada verificação na ponta da branch do Goal, no repositório do humano."""
    store, kernel = abrir_kernel_sqlite(_banco(tmp_path, _repositorio(tmp_path)))
    try:
        estado = ler_estado(kernel.obter_view(), GOAL)
    finally:
        store.fechar()

    assert estado is not None
    linhas = {linha.split(" ")[2]: linha for linha in formatar_status(estado, []) if linha.startswith(f"  ver-{GOAL}")}
    assert linhas[f"ver-{GOAL}-1"].endswith("[desatualizada (mudaram: a.py)]"), linhas
    assert linhas[f"ver-{GOAL}-2"].endswith("[vigente]")
    assert linhas[f"ver-{GOAL}-3"].endswith("[sem ancora]")


def test_status_sem_o_repositorio_diz_nao_conferida_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o repositório do Goal sumiu; a ancorada sai não conferida, e a antiga segue sem âncora."""
    repositorio = _repositorio(tmp_path)
    banco = _banco(tmp_path, repositorio)
    git(repositorio, "branch", "-m", "main", "outra")
    store, kernel = abrir_kernel_sqlite(banco)
    try:
        estado = ler_estado(kernel.obter_view(), GOAL)
    finally:
        store.fechar()

    assert estado is not None
    linhas = [linha for linha in formatar_status(estado, []) if linha.startswith(f"  ver-{GOAL}")]
    assert [linha.rsplit("[", 1)[1] for linha in linhas] == ["nao conferida]", "nao conferida]", "sem ancora]"]


def test_vista_marca_a_desatualizada_com_os_arquivos_a_antiga_sem_ancora_e_a_do_agente_nao_conferida_nominal(tmp_path: Path) -> None:
    """T3d2.2: na vista, a Evidence do orquestrador confere na branch do Goal; a do agente, sem repositório, não é conferida."""
    store, kernel = abrir_kernel_sqlite(_banco(tmp_path, _repositorio(tmp_path)))
    try:
        view = kernel.obter_view()
        materializador = MaterializadorContexto()
        vistas = [materializador.materializar(RequisicaoVista(GOAL, papel, orcamento_tokens=20000), view).conteudo_formatado
                  for papel in (PapelAutor.EXECUTOR, PapelAutor.ARBITRO)]
    finally:
        store.fechar()

    for vista in vistas:
        linhas: dict[str, str] = {}
        for linha in (linha for linha in vista.splitlines() if linha.startswith("- [")):
            linhas.setdefault(linha.split("]")[0].removeprefix("- ["), linha)  # a secao de Evidence vem antes dos vizinhos
        assert linhas[f"ver-{GOAL}-1"].startswith(f"- [ver-{GOAL}-1] [desatualizada (mudaram: a.py)] "), vista
        assert linhas[f"ver-{GOAL}-2"].startswith(f"- [ver-{GOAL}-2] [vigente]")
        assert linhas[f"ver-{GOAL}-3"].startswith(f"- [ver-{GOAL}-3] [sem ancora]")
        assert linhas["evi-antiga"].startswith("- [evi-antiga] [sem ancora]")
        assert linhas["evi-ancorada"].startswith("- [evi-ancorada] [nao conferida]")
        assert linhas["evi-fonte"].startswith("- [evi-fonte] [nao confiavel"), "a Evidence que nao fala de codigo nao leva marca"


def test_canvas_manda_a_conferencia_da_evidence_ao_inspetor_nominal(tmp_path: Path) -> None:
    """O canvas leva a conferência de cada Evidence sobre código; a livre e os outros nós vêm sem ela."""
    store, kernel = abrir_kernel_sqlite(_banco(tmp_path, _repositorio(tmp_path)))
    try:
        nos = {no.id: no for no in CanvasWebController(kernel).obter_canvas().nos}
    finally:
        store.fechar()

    desatualizada = nos[f"ver-{GOAL}-1"].conferencia
    assert desatualizada is not None and desatualizada["estado"] == "desatualizada" and desatualizada["arquivos"] == ["a.py"]
    assert (nos[f"ver-{GOAL}-3"].conferencia or {}).get("estado") == "sem_ancora"
    assert (nos["evi-ancorada"].conferencia or {}).get("rotulo") == "nao conferida"
    assert nos["evi-fonte"].conferencia is None and nos[GOAL].conferencia is None


def test_um_diff_por_par_de_commits_em_cada_leitura_edge_case(tmp_path: Path) -> None:
    """Caso de borda: duas Evidence do mesmo commit pedem um só `diff --name-only` na leitura."""
    store, kernel = abrir_kernel_sqlite(_banco(tmp_path, _repositorio(tmp_path)))
    try:
        view = kernel.obter_view()
        leitura = LeituraPorGoal(view)
        estados = [leitura.conferir(view.obter_no(f"ver-{GOAL}-{n}")) for n in (1, 2)]  # type: ignore[arg-type]
    finally:
        store.fechar()

    assert [c.estado for c in estados if c] == ["desatualizada", "vigente"]
    git_da_leitura = leitura._por_goal[GOAL]._git  # noqa: SLF001 - o cache e o que o caso confere
    assert git_da_leitura is not None
    assert sum(1 for chave in git_da_leitura.memoria if chave[0] == "diff") == 1
    assert LeituraDaConferencia(None).conferir(PapelAutor.ORQUESTRADOR.value, {"commit": "f" * 40}).estado == "nao_conferida"  # type: ignore[union-attr]
