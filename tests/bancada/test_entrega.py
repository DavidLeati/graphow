"""O estado git da entrega e o ramo como o auditor o recebe, nas três formas que o laboratório viu."""

from pathlib import Path
import subprocess

from graphow.bancada.entrega import EstadoDaEntrega, descrever_ramo, ler_estado_da_entrega
from graphow.bancada.formatacao import formatar_dinheiro, formatar_minutos, formatar_tokens, formatar_variacao
from graphow.bancada.projetos import Bancada
from graphow.bancada.semente import criar_repositorio


def _git(repositorio: Path, *argumentos: str) -> None:
    """Um comando git no repositório da entrega, com identidade fixa."""
    identidade = ["-c", "user.name=Teste", "-c", "user.email=teste@teste.invalid"]
    subprocess.run(["git", "-C", str(repositorio), *identidade, *argumentos], check=True, capture_output=True)


def test_commits_no_ramo_com_a_arvore_em_outro_ramo_nominal(tmp_path: Path) -> None:
    """O estoque do graphow: commits no ramo pedido, árvore deixada na main; o auditor lê por worktree."""
    projeto = Bancada().projeto("estoque-loja")
    repositorio = tmp_path / "repo"
    criar_repositorio(projeto, repositorio)
    _git(repositorio, "checkout", "-q", "-b", "chamado-142")
    for numero in (1, 2):
        (repositorio / f"f{numero}.txt").write_text("x\n", encoding="utf-8")
        _git(repositorio, "add", ".")
        _git(repositorio, "commit", "-q", "-m", f"passo {numero}")
    _git(repositorio, "checkout", "-q", "main")

    estado = ler_estado_da_entrega(repositorio, projeto)

    assert (estado.ramo_existe, estado.commits, estado.ramo_atual, estado.arvore_suja) == (True, 2, "main", False)
    assert descrever_ramo(estado) == (
        "chamado-142 (o working tree está na main; leia a branch chamado-142 por worktree temporário)"
    )


def test_nada_commitado_manda_o_auditor_ao_working_tree_nominal(tmp_path: Path) -> None:
    """A agenda e a api do graphow: sem o ramo, o trabalho está na árvore suja da main."""
    projeto = Bancada().projeto("agenda-salas")
    repositorio = tmp_path / "repo"
    criar_repositorio(projeto, repositorio)
    (repositorio / "agenda.py").write_text("print()\n", encoding="utf-8")

    estado = ler_estado_da_entrega(repositorio, projeto)

    assert (estado.ramo_existe, estado.commits, estado.arvore_suja) == (False, 0, True)
    assert descrever_ramo(estado) == "main (o trabalho está NÃO commitado no working tree; use o working tree como está)"


def test_ramo_pedido_com_a_arvore_nele_e_so_o_nome_edge_case() -> None:
    """Caso de borda: a enxuta entrega no ramo e fica nele; o auditor recebe só o nome."""
    estado = EstadoDaEntrega(ramo="entrega", ramo_existe=True, ramo_atual="entrega", commits=11, arvore_suja=False)

    assert descrever_ramo(estado) == "entrega"


def test_numeros_saem_no_formato_do_relatorio_nominal() -> None:
    """Vírgula decimal, ponto de milhar e variação com sinal; base zero vira diferença absoluta."""
    assert formatar_dinheiro(1234.5) == "US$ 1.234,50"
    assert formatar_tokens(15_325_496) == "15,3 M"
    assert formatar_minutos(28.78) == "28,8 min"
    assert formatar_variacao(5.03, 7.30) == "-31%"
    assert formatar_variacao(7.30, 7.30) == "+0%"
    assert formatar_variacao(2, 0) == "+2 (base 0)"
    assert formatar_variacao(None, 1.0) == formatar_dinheiro(None) == "-"
