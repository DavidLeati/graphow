"""O aceite intocado: o executor não neutraliza os testes de aceite por conftest, configuração, arquivo ignorado ou flag do índice.

Os casos vêm da sonda da revisão adversarial da fase 2 (sonda_conftest.py):
um `aceite/conftest.py` que pula tudo deixava a soma errada fechar o Goal.
"""

import copy
import json
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
from graphow.orquestrador.configuracao_do_aceite import configuracao_do_aceite
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
MARCA_XFAIL: str = PULA_TUDO.replace("skip(", "xfail(")
FATIA_CERTA: dict[str, str] = {"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR}


def _roteiro(primeira: dict[str, Any], plano: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Plano, aceite em pytest, a primeira tentativa de F1 dada, a certa, F2 e uma verificação limpa."""
    roteiro = roteiro_completo()
    roteiro["planejador"] = [{"saida": plano or copy.deepcopy(PLANO), "custo": 0.4}]
    roteiro["aceite"] = [aceite_em_pytest()]
    roteiro["executor"] = [primeira, executor_pronto(FATIA_CERTA), roteiro["executor"][1]]
    roteiro["verificador"] = [verificacao("atende")]
    return roteiro


def test_fatia_que_cria_em_aceite_e_recusada_edge_case(tmp_path: Path) -> None:
    """Caso de borda (bloqueante 1a): o `aceite/conftest.py` que pularia tudo não entra; a tentativa seguinte, certa, fecha."""
    bancada = montar_bancada(tmp_path, _roteiro(executor_pronto({"soma.py": SOMA_ERRADA, "verificar.py": "print('ok')\n",
                                                                "aceite/conftest.py": PULA_TUDO})))

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert "criou em aceite/ os arquivos aceite/conftest.py" in bancada.chamadas("executor")[1]["stdin"]
    assert not (bancada.repositorio / "aceite" / "conftest.py").exists()


@pytest.mark.parametrize(
    ("arquivos", "trocado", "c1"),
    [
        ({"conftest.py": PULA_TUDO}, "conftest.py", "nao_atende"),
        ({"conftest.py": MARCA_XFAIL}, "conftest.py", "nao_atende"),
        ({"pyproject.toml": '[tool.pytest.ini_options]\naddopts = "-p no:python"\n'}, "pyproject.toml", "nao_atende"),
        ({"pytest.ini": "[pytest]\naddopts = -k nada\n"}, "pytest.ini", "nao_atende"),
        ({"pytest.py": "print('1 passed in 0.01s')\n"}, "pytest.py", "diferenca"),
        ({".gitignore": "conftest.py\n", "conftest.py": PULA_TUDO}, "", "nao_atende"),
    ],
    ids=["conftest-na-raiz", "xfail-no-conftest", "addopts-do-pyproject", "pytest-ini", "sombra-do-pytest", "conftest-ignorado"],
)
def test_configuracao_que_neutralizaria_o_aceite_nao_da_verde_edge_case(tmp_path: Path, arquivos: dict[str, str], trocado: str, c1: str) -> None:
    """Caso de borda (rodada 4, item 2): a configuração entra, vai à revisão como sinal, e o aceite com ela não conta o que ela pula.

    O teste pulado, o xfail, o desselecionado e o arquivo solto reprovam C1 já
    na rodada com a configuração entregue. A sombra do pytest, que imprime um resumo
    verde, passa nela e falha com a configuração do commit do aceite: a
    diferença vai ao verificador julgar, e não reprova C1 sozinha.
    """
    roteiro = _roteiro(executor_pronto({"soma.py": SOMA_ERRADA, "verificar.py": "print('ok')\n", **arquivos}))
    roteiro["executor"] = [roteiro["executor"][0], roteiro["executor"][2], executor_pronto(FATIA_CERTA)]
    roteiro["verificador"] = [verificacao("atende"), verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.fatias[0].falhas == 0
    primeira = estado.verificacoes[0].propriedades
    assert {p["id"]: p["veredito"] for p in primeira["pareceres"]}["C1"] == ("atende" if c1 == "diferenca" else "nao_atende")
    assert trocado in primeira["configuracao_do_aceite"] if trocado else "conftest.py" in primeira["tirado_antes_do_aceite"]
    if c1 == "diferenca":
        assert [(d["teste"], d["com_a_entregue"], d["com_a_do_aceite"]) for d in primeira["diferencas_de_configuracao"]][0] == (
            "test_c1_soma", True, False)
        briefing = bancada.chamadas("verificador")[0]["stdin"]
        assert "A configuracao de teste mudou desde o commit do aceite (pytest.py)" in briefing
        assert "test_c1_soma de C1: passa com a configuracao entregue; falha" in briefing
    revisao = bancada.chamadas("revisor")[0]["stdin"]
    assert "muda a configuracao de teste" in revisao and "o plano nao declarou" in revisao


# O aceite que importa `soma` pelo caminho que o pytest monta (sem pôr a raiz na frente), como na sonda_isol.
ACEITE_PELO_CAMINHO_DO_PYTEST: str = (
    '"""C1: somar(2, 3) devolve 5."""\n\n\ndef test_c1_soma():\n    from soma import somar\n    assert somar(2, 3) == 5\n'
)
LAYOUT_SRC: dict[str, str] = {
    "soma.py": SOMA_ERRADA, "src/soma.py": SOMA_CERTA, "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["src"]\n',
    "verificar.py": "import sys\nsys.path.insert(0, 'src')\nfrom soma import somar\nassert somar(2, 3) == 5\nprint('ok')\n",
}


def test_layout_src_que_o_repositorio_entregue_aprova_fecha_e_a_diferenca_vai_ao_verificador_nominal(tmp_path: Path) -> None:
    """Rodada 4, item 2 (sonda_isol): o aceite com a configuração entregue aprova o layout `src/`; a do commit do aceite, não.

    O critério vale pela configuração entregue, e o Goal fecha; a diferença fica
    gravada na verificação e vai ao verificador, que a julgou legítima.
    """
    roteiro = _roteiro(executor_pronto(LAYOUT_SRC))
    roteiro["aceite"] = [aceite_em_pytest(ACEITE_PELO_CAMINHO_DO_PYTEST)]
    roteiro["executor"] = [roteiro["executor"][0], roteiro["executor"][2]]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    final = ler_estado(bancada.kernel.obter_view(), "goal-soma").verificacoes[-1].propriedades
    assert {(e["teste"], e["passou"]) for e in final["aceite_do_orquestrador"]} >= {("test_c1_soma", True)}
    assert [(e["teste"], e["passou"]) for e in final["aceite_com_a_configuracao_do_aceite"]][0] == ("test_c1_soma", False)
    assert final["configuracao_do_aceite"] == ["pyproject.toml"]
    diferencas = {(d["teste"], d["com_a_entregue"], d["com_a_do_aceite"]) for d in final["diferencas_de_configuracao"]}
    assert ("test_c1_soma", True, False) in diferencas
    assert "Julgue se a mudanca e legitima" in bancada.chamadas("verificador")[0]["stdin"]


def test_diferenca_que_o_verificador_julga_ilegitima_vira_bloqueante_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o verificador que julga a mudança de configuração ilegítima registra o achado em C1, e o código o faz bloqueante."""
    roteiro = _roteiro(executor_pronto(LAYOUT_SRC))
    roteiro["aceite"] = [aceite_em_pytest(ACEITE_PELO_CAMINHO_DO_PYTEST)]
    roteiro["executor"] = [roteiro["executor"][0], roteiro["executor"][2], executor_pronto({"notas.txt": "x\n"})]
    ilegitima = {"titulo": "pythonpath troca o modulo que o aceite importa", "descricao": "o aceite de C1 importa src/soma.py",
                 "prova": "`python -m pytest aceite` passa so com o pythonpath novo", "local": "pyproject.toml:2", "criterios": ["C1"],
                 "decisoes": [], "severidade": "alta"}
    roteiro["verificador"] = [verificacao("atende", [ilegitima]), verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    primeira = ler_estado(bancada.kernel.obter_view(), "goal-soma").verificacoes[0]
    assert [(a.texto("titulo"), a.gravidade) for a in primeira.achados] == [("pythonpath troca o modulo que o aceite importa", "bloqueante")]


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


def test_aceite_roda_com_a_parte_de_teste_do_commit_dele_e_a_area_volta_a_ponta_edge_case(tmp_path: Path) -> None:
    """Caso de borda (ajuste 3): só a parte de teste volta ao commit do aceite; o resto dos mistos fica, e depois tudo volta à ponta."""
    repositorio = criar_repositorio(tmp_path / "r", {
        "pyproject.toml": '[project]\nname = "a"\n\n[tool.pytest.ini_options]\naddopts = "-q"\n',
        "package.json": '{"name": "a", "scripts": {"test": "node --test", "start": "node a.js"}}\n',
        "pytest.ini": "[pytest]\n",
    })
    aceite = git(repositorio, "rev-parse", "HEAD").strip()
    (repositorio / "pyproject.toml").write_text('[project]\nname = "a"\ndependencies = ["x"]\n\n[tool.pytest.ini_options]\naddopts = "-k nada"\n',
                                               encoding="utf-8")
    (repositorio / "package.json").write_text('{"name": "a", "type": "module", "scripts": {"test": "exit 0", "start": "node b.js"}}\n',
                                             encoding="utf-8")
    (repositorio / "conftest.py").write_text(PULA_TUDO, encoding="utf-8")
    (repositorio / "pytest.ini").unlink()
    git(repositorio, "add", "-A")
    git(repositorio, "commit", "-qm", "fatia")
    ponta = {nome: (repositorio / nome).read_text(encoding="utf-8") for nome in ("pyproject.toml", "package.json", "conftest.py")}

    with configuracao_do_aceite(repositorio, aceite) as trocados:
        durante = {nome: (repositorio / nome).read_text(encoding="utf-8") if (repositorio / nome).exists() else None
                   for nome in ("pyproject.toml", "package.json", "conftest.py", "pytest.ini")}

    assert trocados == ("conftest.py", "package.json", "pyproject.toml", "pytest.ini")
    assert 'dependencies = ["x"]' in durante["pyproject.toml"] and 'addopts = "-q"' in durante["pyproject.toml"]
    pacote = json.loads(durante["package.json"])
    assert pacote["type"] == "module" and pacote["scripts"] == {"start": "node b.js", "test": "node --test"}
    assert durante["conftest.py"] is None and durante["pytest.ini"] == "[pytest]\n"
    assert {nome: (repositorio / nome).read_text(encoding="utf-8") for nome in ponta} == ponta
    assert not (repositorio / "pytest.ini").exists() and git(repositorio, "status", "--porcelain").strip() == ""


def test_aceite_que_o_gitignore_ignora_entra_no_commit_e_na_copia_intocada_edge_case(tmp_path: Path) -> None:
    """Caso de borda (ajuste 6): com `aceite/` no .gitignore do projeto, o commit do aceite leva o teste à força, e ele roda."""
    bancada = montar_bancada(tmp_path, _roteiro(executor_pronto(FATIA_CERTA)))
    (bancada.repositorio / ".gitignore").write_text("aceite/\n", encoding="utf-8")
    git(bancada.repositorio, "add", ".gitignore")
    git(bancada.repositorio, "commit", "-qm", "Ignora aceite/")

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.aceite is not None
    assert "aceite/aceite_c1.py" in git(bancada.repositorio, "show", "--name-only", "--format=", estado.aceite["commit"])
    assert [e["passou"] for e in estado.verificacoes[-1].propriedades["aceite_do_orquestrador"]][0] is True
