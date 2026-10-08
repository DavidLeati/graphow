"""`graphow escopo-medir`: a regressão do escopo governado sobre o corpus, sem abrir o banco do usuário."""

from pathlib import Path

from graphow.api.cli_execucao import CODIGO_SUCESSO, ExecutorLinhaDeComando
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.storage.localizador_banco import AmbienteEmMemoria, LocalizadorBancoEventos


def test_escopo_medir_imprime_as_tabelas_sem_criar_banco_nominal(tmp_path: Path) -> None:
    """O comando roda sobre o corpus do repositório, imprime A a E e não deixa banco no diretório de dados."""
    console = EscritorConsoleEmMemoria()
    ambiente = AmbienteEmMemoria({"LOCALAPPDATA": str(tmp_path)}, tmp_path)
    executor = ExecutorLinhaDeComando(console, LocalizadorBancoEventos(ambiente))

    codigo = executor.executar(construir_parser().parse_args(["escopo-medir"]))

    texto = "\n".join(console.linhas)
    assert codigo == CODIGO_SUCESSO
    for titulo in ("## A. Eventos de desvio", "## B. ", "## C. ", "## D. ", "## E. "):
        assert titulo in texto
    assert "goal-3e94e8" in texto and "K dispara na emergente | 4" in texto
    assert not list(tmp_path.rglob("*.db"))


def test_escopo_medir_aceita_o_corpus_por_caminho_edge_case() -> None:
    """Caso de borda: `--corpus` chega ao analisador como texto e o padrão fica vazio."""
    parser = construir_parser()

    assert parser.parse_args(["escopo-medir"]).corpus is None
    assert parser.parse_args(["escopo-medir", "--corpus", "outro.jsonl.gz"]).corpus == "outro.jsonl.gz"
