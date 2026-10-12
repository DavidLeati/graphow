"""O aceite intocado: o executor não neutraliza os testes de aceite por conftest, configuração, arquivo ignorado ou flag do índice.

Os casos vêm da sonda da revisão adversarial da fase 2 (sonda_conftest.py):
um `aceite/conftest.py` que pula tudo deixava a soma errada fechar o Goal.
"""

import copy
from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador.aceite_intocado import (
    configuracoes_mudadas,
    e_configuracao_de_teste,
    flags_do_indice,
    preparar_o_aceite,
    soltos_que_mudam_os_testes,
)
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.trava_do_git import regras_que_negam_git

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import (
    ACEITE_PYTEST,
    PLANO,
    SOMA_CERTA,
    SOMA_ERRADA,
    VERIFICAR,
    aceite_em_pytest,
    executor_pronto,
    montar_bancada,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
PULA_TUDO: str = (
    "import pytest\n\n\ndef pytest_collection_modifyitems(items):\n    for item in items:\n"
    "        item.add_marker(pytest.mark.skip(reason='x'))\n"
)
FATIA_CERTA: dict[str, str] = {"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR}


def _roteiro(primeira: dict[str, Any], plano: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Plano, aceite em pytest, a primeira tentativa de F1 dada, a certa, F2 e uma verificação limpa."""
    roteiro = roteiro_completo()
    roteiro["planejador"] = [{"saida": plano or copy.deepcopy(PLANO), "custo": 0.4}]
    roteiro["aceite"] = [aceite_em_pytest()]
    roteiro["executor"] = [primeira, executor_pronto(FATIA_CERTA), roteiro["executor"][1]]
    roteiro["verificador"] = [verificacao("atende")]
    return roteiro


@pytest.mark.parametrize(
    ("arquivos", "trecho"),
    [
        ({"aceite/conftest.py": PULA_TUDO}, "criou em aceite/ os arquivos aceite/conftest.py"),
        ({"conftest.py": PULA_TUDO}, "mexeu na configuracao de teste conftest.py, que o plano nao declarou"),
        ({"pyproject.toml": '[tool.pytest.ini_options]\naddopts = "-p no:python"\n'}, "configuracao de teste pyproject.toml"),
        ({"pytest.ini": "[pytest]\naddopts = -k nada\n"}, "configuracao de teste pytest.ini"),
        ({"sitecustomize.py": "import os\n"}, "configuracao de teste sitecustomize.py"),
        ({"pytest.py": "print('1 passed in 0.01s')\n"}, "configuracao de teste pytest.py"),
        ({"package.json": '{"scripts": {"test": "exit 0"}}\n'}, "configuracao de teste package.json"),
        ({".gitignore": "conftest.py\n", "conftest.py": PULA_TUDO}, "fora do git (ignorada): conftest.py"),
    ],
    ids=["conftest-em-aceite", "conftest-na-raiz", "addopts-do-pyproject", "pytest-ini", "sitecustomize", "sombra-do-pytest",
         "script-de-teste-do-package", "conftest-ignorado"],
)
def test_fatia_que_neutraliza_o_aceite_e_recusada_edge_case(tmp_path: Path, arquivos: dict[str, str], trecho: str) -> None:
    """Caso de borda (bloqueante 1a/1b): a configuração que pularia o aceite não entra; a tentativa seguinte, certa, fecha."""
    bancada = montar_bancada(tmp_path, _roteiro(executor_pronto({"soma.py": SOMA_ERRADA, "verificar.py": "print('ok')\n",
                                                                **arquivos})))

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert trecho in bancada.chamadas("executor")[1]["stdin"]
    assert not any((bancada.repositorio / caminho).exists() for caminho in arquivos if caminho != ".gitignore")
    assert (bancada.repositorio / "soma.py").read_text(encoding="utf-8") == SOMA_CERTA


def test_mudanca_fora_da_parte_de_teste_do_pyproject_passa_direto_nominal(tmp_path: Path) -> None:
    """O pyproject que só ganha o nome do projeto não é configuração de teste: a fatia entra na primeira, sem revisão."""
    bancada = montar_bancada(tmp_path, _roteiro(executor_pronto({**FATIA_CERTA, "pyproject.toml": '[project]\nname = "b"\n'})))

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.fatias[0].falhas == 0
    assert bancada.chamadas("revisor") == []


def test_configuracao_declarada_pelo_plano_vai_a_revisao_de_risco_nominal(tmp_path: Path) -> None:
    """A fatia que o plano diz que mexe no conftest.py pode mexer, e passa pela revisão de risco antes do commit."""
    plano = copy.deepcopy(PLANO)
    plano["fatias"][0]["arquivos"] = ["soma.py", "verificar.py", "conftest.py"]
    fixture = "import pytest\n\n\n@pytest.fixture\ndef dois():\n    return 2\n"
    bancada = montar_bancada(tmp_path, _roteiro(executor_pronto({**FATIA_CERTA, "conftest.py": fixture}), plano))

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    revisoes = bancada.chamadas("revisor")
    assert len(revisoes) == 1 and "muda a configuracao de teste (conftest.py)" in revisoes[0]["stdin"]
    assert (bancada.repositorio / "conftest.py").read_text(encoding="utf-8") == fixture


def test_flag_do_indice_que_esconde_a_mudanca_e_limpa_e_reprova_a_fatia_edge_case(tmp_path: Path) -> None:
    """Caso de borda (bloqueante 1d): o skip-worktree esconderia a soma errada do status; a flag sai e a tentativa falha."""
    escondida = executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR},
                                comandos=[["git", "update-index", "--skip-worktree", "verificar.py"]])
    bancada = montar_bancada(tmp_path, _roteiro(escondida))

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert "escondeu do git os arquivos verificar.py com skip-worktree" in bancada.chamadas("executor")[1]["stdin"]


def test_verificacao_roda_o_aceite_da_copia_intocada_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o conftest ignorado que a sessão do verificador deixou em aceite/ sai antes de o orquestrador rodar o aceite."""
    roteiro = _roteiro(executor_pronto({"soma.py": SOMA_ERRADA, "verificar.py": "print('ok')\n"}))
    roteiro["executor"] = [roteiro["executor"][0], roteiro["executor"][2], executor_pronto({"soma.py": SOMA_CERTA})]
    plantado = {**verificacao("atende"), "arquivos": {"aceite/.gitignore": "*\n", "aceite/conftest.py": PULA_TUDO}}
    roteiro["verificador"] = [plantado, verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    primeira = estado.verificacoes[0].propriedades
    assert set(primeira["tirado_antes_do_aceite"]) >= {"aceite/conftest.py"}
    assert {p["id"]: p["veredito"] for p in primeira["pareceres"]}["C1"] == "nao_atende"


@pytest.mark.parametrize(
    ("caminho", "e"),
    [("conftest.py", True), ("src/pacote/conftest.py", True), ("aceite/conftest.py", True), ("pytest.ini", True),
     ("jest.config.js", True), ("vitest.config.ts", True), (".mocharc.yml", True), ("x.pth", True), ("pytest/__init__.py", True),
     ("src/pytest.py", False), ("soma.py", False), ("pyproject.toml", False), ("tests/test_soma.py", False)],
)
def test_configuracao_de_teste_pelo_nome_edge_case(caminho: str, e: bool) -> None:
    """Caso de borda: o nome diz se o arquivo muda como os testes rodam; a sombra do runner só vale na raiz."""
    assert e_configuracao_de_teste(caminho) is e


def test_so_a_parte_de_teste_dos_arquivos_mistos_conta_edge_case(tmp_path: Path) -> None:
    """Caso de borda: no pyproject, setup.cfg e package.json, só a seção de teste conta; o resto muda livre."""
    repositorio = criar_repositorio(tmp_path / "r", {
        "pyproject.toml": '[project]\nname = "a"\n\n[tool.pytest.ini_options]\naddopts = "-q"\n',
        "setup.cfg": "[metadata]\nname = a\n\n[tool:pytest]\naddopts = -q\n",
        "package.json": '{"name": "a", "scripts": {"test": "node --test", "start": "node a.js"}}\n',
    })
    antes = git(repositorio, "rev-parse", "HEAD").strip()
    (repositorio / "pyproject.toml").write_text('[project]\nname = "b"\n\n[tool.pytest.ini_options]\naddopts = "-q"\n', encoding="utf-8")
    (repositorio / "setup.cfg").write_text("[metadata]\nname = a\n\n[tool:pytest]\naddopts = -k nada\n", encoding="utf-8")
    (repositorio / "package.json").write_text('{"name": "b", "scripts": {"test": "node --test", "start": "node b.js"}}\n',
                                              encoding="utf-8")

    mudados = configuracoes_mudadas(repositorio, ["pyproject.toml", "setup.cfg", "package.json"], antes=antes)

    assert mudados == ("setup.cfg",)


def test_flags_e_soltos_vistos_e_tirados_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o assume-unchanged aparece, o conftest ignorado aparece, e preparar o aceite tira os dois."""
    repositorio = criar_repositorio(tmp_path / "r", {"soma.py": SOMA_ERRADA, ".gitignore": "conftest.py\nignorada/\n",
                                                     "aceite/aceite_c1.py": ACEITE_PYTEST})
    commit = git(repositorio, "rev-parse", "HEAD").strip()
    git(repositorio, "update-index", "--assume-unchanged", "soma.py")
    (repositorio / "conftest.py").write_text(PULA_TUDO, encoding="utf-8")
    (repositorio / "ignorada").mkdir()
    (repositorio / "ignorada" / "conftest.py").write_text(PULA_TUDO, encoding="utf-8")
    (repositorio / "aceite" / "aceite_c1.py").write_text("def test_c1_soma():\n    pass\n", encoding="utf-8")

    assert flags_do_indice(repositorio) == ("soma.py",)
    assert set(soltos_que_mudam_os_testes(repositorio)) == {"conftest.py", "ignorada/conftest.py"}
    tirado = preparar_o_aceite(repositorio, commit)

    assert set(tirado) == {"conftest.py", "ignorada/conftest.py", "soma.py"}
    assert flags_do_indice(repositorio) == () and not (repositorio / "conftest.py").exists()
    assert (repositorio / "aceite" / "aceite_c1.py").read_text(encoding="utf-8") == ACEITE_PYTEST


def test_update_index_esta_nas_regras_negadas_nominal() -> None:
    """O executor não roda git update-index: a regra o nega, como nega o commit."""
    assert "Bash(git update-index:*)" in regras_que_negam_git(("Bash",))
