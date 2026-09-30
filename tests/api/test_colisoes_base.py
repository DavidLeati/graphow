"""O cruzamento puro entre o que o ramo base ganhou e o que o Goal toca, sem git nem grafo."""

from graphow.api.colisoes_base import (
    Colisao,
    casa_glob,
    cruzar_colisoes,
    nos_caminhos_de_colisao,
    normalizar_caminho,
    separar_remoto,
)

MIGRATIONS: tuple[str, ...] = ("**/migrations/*.py",)


def test_glob_de_migrations_casa_em_qualquer_profundidade_nominal() -> None:
    """`**/` casa com zero ou mais diretórios; `*` fica dentro do diretório."""
    assert casa_glob("migrations/0001_inicial.py", "**/migrations/*.py")
    assert casa_glob("hub/dados/migrations/0158_x.py", "**/migrations/*.py")
    assert not casa_glob("hub/migrations/antigas/0001.py", "**/migrations/*.py")
    assert not casa_glob("hub/migrations/0158_x.sql", "**/migrations/*.py")


def test_glob_trata_o_resto_como_literal_edge_case() -> None:
    """Caso de borda: ponto e parêntese do glob não viram curinga de expressão regular."""
    assert casa_glob("app/v1.0/x.py", "app/v1.0/*.py")
    assert not casa_glob("app/v1x0/x.py", "app/v1.0/*.py")
    assert casa_glob("a/b.txt", "a/?.txt")
    assert not casa_glob("a/bc.txt", "a/?.txt")


def test_numero_diferente_no_mesmo_diretorio_colide_nominal() -> None:
    """O caso das migrations: nenhum arquivo em comum, e ainda assim colide."""
    colisoes = cruzar_colisoes(
        ["hub/migrations/0158_da_base.py"],
        ["hub/migrations/0158_do_goal.py", "hub/models.py"],
        MIGRATIONS,
    )

    assert colisoes == (Colisao("hub/migrations/0158_da_base.py", "hub/migrations/0158_do_goal.py"),)
    assert colisoes[0].formatar() == "hub/migrations/0158_da_base.py x hub/migrations/0158_do_goal.py"


def test_mesmo_arquivo_dentro_do_glob_colide_nominal() -> None:
    """O mesmo arquivo é o caso particular do mesmo diretório."""
    assert cruzar_colisoes(["app/migrations/0002.py"], ["app/migrations/0002.py"], MIGRATIONS) == (
        Colisao("app/migrations/0002.py", "app/migrations/0002.py"),
    )


def test_outro_diretorio_nao_colide_edge_case() -> None:
    """Caso de borda: migrations de apps diferentes não disputam a numeração."""
    assert cruzar_colisoes(["pagamentos/migrations/0002.py"], ["contas/migrations/0002.py"], MIGRATIONS) == ()


def test_fora_do_glob_nao_colide_nem_no_mesmo_arquivo_edge_case() -> None:
    """Caso de borda: o arquivo em comum fora dos globs é conflito de merge comum, e o git já o acusa."""
    assert cruzar_colisoes(["docs/leia.md", "app/models.py"], ["docs/leia.md", "app/models.py"], MIGRATIONS) == ()


def test_caminho_do_goal_fora_do_glob_no_mesmo_diretorio_nao_colide_edge_case() -> None:
    """Caso de borda: o caminho do Goal também precisa casar com o glob, não só estar ali."""
    assert cruzar_colisoes(["app/migrations/0002.py"], ["app/migrations/LEIA.md"], MIGRATIONS) == ()


def test_barra_do_windows_e_ponto_barra_se_normalizam_edge_case() -> None:
    """Caso de borda: o `arquivos_alvo` escrito à mão casa com o caminho que o git devolve."""
    assert normalizar_caminho(" .\\app\\migrations\\0002.py ") == "app/migrations/0002.py"
    assert cruzar_colisoes(["app/migrations/0003.py"], [".\\app\\migrations\\0002.py"], MIGRATIONS) == (
        Colisao("app/migrations/0003.py", "app/migrations/0002.py"),
    )


def test_so_os_ganhos_nos_caminhos_de_colisao_edge_case() -> None:
    """Caso de borda: glob em branco não casa com nada, e a lista sai sem repetição."""
    arquivos = ["b/migrations/2.py", "a/migrations/1.py", "docs/x.md", "a/migrations/1.py"]

    assert nos_caminhos_de_colisao(arquivos, ["**/migrations/*.py", " "]) == ("a/migrations/1.py", "b/migrations/2.py")


def test_ramo_de_remoto_se_separa_nominal() -> None:
    """`origin/stage` é o ramo `stage` do remoto `origin`."""
    assert separar_remoto("origin/stage", ["origin", "upstream"]) == ("origin", "stage")


def test_ramo_local_com_barra_fica_local_edge_case() -> None:
    """Caso de borda: `feature/x` não é remoto só por ter barra, e `stage` sem remoto fica como está."""
    assert separar_remoto("feature/x", ["origin"]) == ("", "feature/x")
    assert separar_remoto("stage", ["origin"]) == ("", "stage")
    assert separar_remoto("origin/", ["origin"]) == ("", "origin/")
