"""O que chega à conferência e à fatia de correção: os desacordos, o diff inteiro em resumo e as chamadas de cada achado.

Na revisão da T2c+T2d e da T2e: o desacordo do executor da correção não
chegava a ninguém (a caçada já tinha rodado e a conferência não o recebia), o
diff das correções ia cortado em ordem alfabética, sem aviso (`docs/` e o
README antes de `src/`), e o corte das chamadas que reproduzem valia para a
fatia inteira, com o achado herdado de outro marco sem as dele.
"""

from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.briefing import ContextoDaFatia, briefing_do_executor
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.diff_das_correcoes import diff_das_correcoes, prioridade_no_diff
from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.historico_da_correcao import MAXIMO_DE_CHAMADAS, chamadas_que_reproduzem
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado, VerificacaoRegistrada
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import autor_de_aceite, montar_bancada, roteiro_completo

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
ARGUMENTO: str = "o teste de C1 importa soma de uma pasta que a correcao nao usa"


def _teste_errado() -> dict[str, Any]:
    """A saída do executor do modo autônomo que diz que o teste de aceite de C1 está errado."""
    saida = {"status": "teste_errado", "resumo": "parei no teste de C1", "arquivos": [], "testes": [], "duvida": ARGUMENTO,
             "teste_errado": "C1"}
    return {"saida": saida, "custo": 0.1}


def _mantido() -> dict[str, Any]:
    """O autor de aceite que, refazendo C1, mantém o teste como estava e diz por quê."""
    resposta = autor_de_aceite()
    resposta["saida"]["criterios"] = resposta["saida"]["criterios"][:1]
    resposta["saida"]["resumo"] = "o teste esta certo: importa da raiz, como a suite"
    return resposta


def test_desacordo_do_executor_da_correcao_chega_a_conferencia_nominal(tmp_path: Path) -> None:
    """T2i.1: a correção diz que o teste de C1 está errado, o autor o mantém, e a conferência recebe o desacordo para julgar."""
    roteiro = roteiro_completo()
    roteiro["executor"].insert(2, _teste_errado())
    roteiro["aceite"].append(_mantido())
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    papeis = [c["papel"] for c in bancada.chamadas() if c["papel"] != "segunda_opiniao"]
    assert papeis == ["planejador", "aceite", "executor", "executor", "verificador", "executor", "aceite", "executor",
                      "conferencia"]
    assert "Desacordos sobre testes de aceite" not in bancada.chamadas("verificador")[0]["stdin"]
    conferencia = bancada.chamadas("conferencia")[0]["stdin"]
    assert "## Desacordos sobre testes de aceite (julgue o criterio)" in conferencia
    assert ("- C1: o executor de M1.K1.1 disse que o teste esta errado; o autor o manteve: o teste esta certo: importa da "
            "raiz, como a suite") in conferencia


# Na final, o achado que casa com tudo (a reprodução marcada é o prefixo de toda sonda) vem antes de três com uma sonda cada.
SONDAS_DA_FINAL: list[dict[str, Any]] = [{"comando": f"python sonda.py --caso {n:02d}", "codigo": 1, "saida": f"falhou {n:02d}"}
                                         for n in range(1, 13)]
CHAMADA_DO_M1: dict[str, Any] = {"comando": "python antigo.py --lista", "codigo": 1, "saida": "quebrou no M1"}


def _achado(id_achado: str, verificacao: str, **propriedades: Any) -> AchadoRegistrado:
    """Um bloqueante aberto da verificação dada."""
    return AchadoRegistrado(id_achado, verificacao, "bloqueante", "aberto", {"titulo": id_achado, **propriedades})


def _final_com_cinco_achados() -> tuple[EstadoDoGoal, FatiaRegistrada]:
    """A correção da final com cinco achados: o que casa com tudo, três da final com uma sonda cada e o herdado do M1."""
    geral = _achado("a-geral", "ver-2", reproducao=["python sonda.py"], prova="as sondas falham")
    especificos = [_achado(f"a-{n}", "ver-2", prova=f"rodei `python sonda.py --caso {n}` e falhou") for n in (10, 11, 12)]
    herdado = _achado("a-m1", "ver-1", prova="rodei `python antigo.py --lista` e quebrou")
    do_m1 = VerificacaoRegistrada("ver-1", "c1", "parcial", 1, {"comandos": [CHAMADA_DO_M1]}, achados=(herdado,), marco="M1")
    final = VerificacaoRegistrada("ver-2", "c2", "parcial", 1, {"comandos": SONDAS_DA_FINAL}, achados=(geral, *especificos),
                                  marco="M2")
    ids = ["a-geral", "a-10", "a-11", "a-12", "a-m1"]
    fatia = FatiaRegistrada("task-k1", "M2.K1.1", "Corrige: a-geral (e mais 4)", "pendente", 3,
                            {m.CAMPO_CORRIGE: "ver-2", m.CAMPO_ACHADOS: ids})
    return EstadoDoGoal("goal-x", "Goal x", "ativo", {}, fatias=(fatia,), verificacoes=(do_m1, final)), fatia


def test_cada_achado_da_correcao_tem_a_sua_chamada_e_o_herdado_traz_a_dele_edge_case() -> None:
    """T2i.3: com cinco achados e um que casa com tudo, cada um tem ao menos uma chamada, até 8; o herdado do M1 traz a da verificação dele."""
    estado, fatia = _final_com_cinco_achados()

    linhas = chamadas_que_reproduzem(estado, fatia)

    assert len(linhas) == MAXIMO_DE_CHAMADAS
    for id_achado, comando in (("a-geral", "python sonda.py --caso 01"), ("a-10", "python sonda.py --caso 10"),
                               ("a-11", "python sonda.py --caso 11"), ("a-12", "python sonda.py --caso 12"),
                               ("a-m1", "python antigo.py --lista")):
        assert any(linha.startswith(f"- {id_achado}: `{comando}` saiu com 1") for linha in linhas), (id_achado, linhas)
    assert "- a-m1: `python antigo.py --lista` saiu com 1: quebrou no M1" in linhas
    assert len(set(linhas)) == len(linhas)


def test_briefing_da_correcao_agrupada_fala_no_plural_e_diz_que_ela_se_divide_nominal() -> None:
    """A fatia de correção com cinco achados diz que corrige cinco e que, na segunda falha, se divide em uma por achado."""
    estado, fatia = _final_com_cinco_achados()

    briefing = briefing_do_executor(estado, fatia, ContextoDaFatia(tentativa=1))

    assert "(na segunda falha, a fatia se divide em uma por achado)" in briefing
    assert "Esta fatia corrige 5 achados bloqueantes que a verificacao ver-2 do Goal cobrou." in briefing
    assert "## Achados que esta fatia corrige" in briefing
    assert "## Chamadas que reproduzem os achados, da verificacao de cada um (rode-as antes e depois da correcao)" in briefing


def _diff_grande(tmp_path: Path) -> tuple[Path, str]:
    """Um repositório cuja correção muda 26 arquivos: 20 em `docs/`, o README, três em `src/`, um teste e o documento do Goal."""
    linhas = "".join(f"linha {n} do texto gerado\n" for n in range(60))
    repositorio = criar_repositorio(tmp_path / "repo", {"README.md": "# x\n", "src/pacote/__init__.py": ""})
    antes = git(repositorio, "rev-parse", "HEAD").strip()
    arquivos = {**{f"docs/catalogo_{n:02d}.md": linhas for n in range(20)}, "README.md": "# x\n" + linhas,
                "src/pacote/__init__.py": "VERSAO = 2\n", "src/pacote/agenda.py": "def agendar():\n    return 'ok'\n",
                "src/pacote/lembrete.py": "def lembrar():\n    return 'ja'\n", "tests/test_agenda.py": "def test_agendar():\n    pass\n",
                "docs/goals/agenda.md": "# Goal\n" + linhas}
    for nome, conteudo in arquivos.items():
        (repositorio / nome).parent.mkdir(parents=True, exist_ok=True)
        (repositorio / nome).write_text(conteudo, encoding="utf-8", newline="\n")
    git(repositorio, "add", "-A")
    git(repositorio, "commit", "-q", "-m", "Correcoes")
    return repositorio, antes


def test_diff_grande_traz_o_resumo_inteiro_o_corpo_de_src_e_o_aviso_do_corte_edge_case(tmp_path: Path) -> None:
    """T2i.2: de 25 arquivos (sem o documento do Goal), o resumo traz todos, o corpo começa por `src/` e o aviso diz o que ficou de fora."""
    repositorio, antes = _diff_grande(tmp_path)

    diff = diff_das_correcoes(GitDoGoal(repositorio), antes, "agenda")

    resumo, corpo = diff.split("Corpo, com `src/`")
    assert "25 files changed" in resumo and "docs/goals/agenda.md" not in diff
    assert all(f"docs/catalogo_{n:02d}.md" in resumo for n in range(20)) and "README.md" in resumo
    ordem = ["src/pacote/__init__.py", "src/pacote/agenda.py", "src/pacote/lembrete.py", "tests/test_agenda.py", "README.md",
             "docs/catalogo_00.md"]
    assert [corpo.index(f"+++ b/{nome}") for nome in ordem] == sorted(corpo.index(f"+++ b/{nome}") for nome in ordem)
    assert "+def lembrar():" in corpo and "+def test_agendar():" in corpo
    aviso = corpo.split("Aviso: o corpo vai ate 8000 caracteres. ")[1]
    assert aviso.startswith("O diff de docs/catalogo_03.md foi cortado no meio; ficaram de fora: docs/catalogo_04.md, ")
    assert "docs/catalogo_19.md" in aviso and "src/" not in aviso and "tests/" not in aviso
    assert f"`git diff {antes[:12]}..HEAD -- <arquivo>`" in aviso


def test_diff_que_cabe_vai_inteiro_sem_aviso_nominal(tmp_path: Path) -> None:
    """O diff pequeno vai com o resumo e o corpo inteiro, sem aviso de corte."""
    repositorio = criar_repositorio(tmp_path / "repo", {"README.md": "# x\n", "soma.py": "def somar(a, b):\n    return 0\n"})
    antes = git(repositorio, "rev-parse", "HEAD").strip()
    (repositorio / "soma.py").write_text("def somar(a, b):\n    return a + b\n", encoding="utf-8", newline="\n")
    git(repositorio, "commit", "-q", "-am", "Correcao")

    diff = diff_das_correcoes(GitDoGoal(repositorio), antes, "soma")

    assert "soma.py | 2 +-" in diff and "+    return a + b" in diff and "Aviso" not in diff
    assert diff_das_correcoes(GitDoGoal(repositorio), "", "soma") == ""


@pytest.mark.parametrize(("caminho", "prioridade"), [("src/soma.py", 0), ("aceite/aceite_c1.py", 1), ("tests/test_x.py", 1),
                                                     ("x_test.go", 1), ("soma.py", 2), ("docs/a.md", 3), ("README.md", 3)])
def test_testes_de_aceite_entram_no_grupo_dos_testes_no_diff_edge_case(caminho: str, prioridade: int) -> None:
    """T2l: `aceite/aceite_c1.py` não casa com o padrão de nome de teste, e ia ao grupo do resto."""
    assert prioridade_no_diff(caminho) == prioridade
