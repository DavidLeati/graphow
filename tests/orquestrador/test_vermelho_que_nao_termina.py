"""A conferência do vermelho com teste de aceite que não termina: o limite de um teste, o teto e o comando de todos (T3k).

No portão da fase 3, dois testes que deixavam um servidor aberto seguraram o
Goal por 90 minutos: 30 de cada um e 30 do comando que roda todos.
"""

from pathlib import Path
import sys

import pytest

from graphow.orquestrador import autor_de_aceite as passo_do_aceite
from graphow.orquestrador import saida_do_aceite as sa
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.suite import ResultadoDaSuite, rodar_suite

from tests.orquestrador.apoio_laco import montar_bancada, roteiro_completo, verificacao

COMANDO_DE_TODOS: str = "python aceite/todos.py"
LIMITE_DA_SUITE_S: float = 1200.0
# O teste preso dorme dois minutos; o limite que o corta é de três segundos.
LIMITE_DO_TESTE_PRESO_S: float = 3.0
TESTE_PRESO: str = "import time\n\n\ndef test_c1_preso():\n    time.sleep(120)\n\n\ntest_c1_preso()\n"


def _saida(*nomes: str) -> sa.SaidaDoAceite:
    """Um critério com os testes dados, cada um com o comando que o roda sozinho."""
    testes = tuple(sa.TesteDeAceite(f"aceite/{nome}.py", nome, f"python aceite/{nome}.py") for nome in nomes)
    return sa.SaidaDoAceite("testes de C1", COMANDO_DE_TODOS, (sa.AceiteDoCriterio("C1", testes),))


def _vermelho(comando: str, nome: str) -> ResultadoDaSuite:
    """O teste que falha numa asserção dele e sai."""
    return ResultadoDaSuite(comando, 1, f'  File "aceite/{nome}.py", line 9, in {nome}\n    assert somar(2, 3) == 5\nAssertionError\n')


class Rodador:
    """Um `Rodar` falso: os testes dados não terminam, os outros falham na asserção; guarda os comandos que recebeu.

    O comando de todos não termina quando algum teste não termina, ou quando o teste pede (`todos_sem_fim`).
    """

    def __init__(self, sem_fim: tuple[str, ...], *, todos_sem_fim: bool = False) -> None:
        self.sem_fim: tuple[str, ...] = sem_fim
        self.todos_sem_fim: bool = todos_sem_fim or bool(sem_fim)
        self.comandos: list[str] = []

    def __call__(self, comando: str) -> ResultadoDaSuite:
        self.comandos.append(comando)
        nome = Path(comando.split()[-1]).stem
        if nome in self.sem_fim or (nome == Path(COMANDO_DE_TODOS).stem and self.todos_sem_fim):
            return ResultadoDaSuite(comando, None, "", tempo_esgotado=True)
        return _vermelho(comando, nome)


def test_teste_que_nao_termina_volta_ao_autor_sem_esperar_o_comando_de_todos_nominal() -> None:
    """T3k.1: dois testes sem fim e um vermelho de verdade dão dois problemas, três execuções e nenhum comando de todos."""
    rodar = Rodador(sem_fim=("test_c1_servidor", "test_c1_reabre"))

    problemas, execucoes = sa.conferir_vermelho(_saida("test_c1_servidor", "test_c1_soma", "test_c1_reabre"), rodar)

    assert not any(comando.endswith("aceite/todos.py") for comando in rodar.comandos)
    assert [e.teste for e in execucoes] == ["test_c1_servidor", "test_c1_soma", "test_c1_reabre"]
    assert [e.codigo for e in execucoes] == [None, 1, None]
    assert len(problemas) == 2
    assert "o teste test_c1_servidor de C1 nao terminou" in problemas[0]
    assert "feche-os tambem quando a assercao falha" in problemas[0] and "se e so lento" in problemas[0]
    assert "--tempo-limite-suite" in problemas[0]
    assert "o teste test_c1_reabre de C1 nao terminou" in problemas[1]
    assert not any("vermelho pelo motivo errado" in problema for problema in problemas)


def test_processo_de_verdade_que_nao_termina_e_cortado_no_limite_e_volta_ao_autor_edge_case(tmp_path: Path) -> None:
    """T3k.1, com um processo de verdade: o teste que dorme é cortado no limite, volta ao autor e o comando de todos não roda."""
    (tmp_path / "aceite").mkdir()
    (tmp_path / "aceite" / "aceite_c1.py").write_text(TESTE_PRESO, encoding="utf-8", newline="\n")
    marca = tmp_path / "rodou-o-comando-de-todos"
    de_todos = f'"{sys.executable}" -c "open(r\'{marca}\', \'w\').close()"'
    teste = sa.TesteDeAceite("aceite/aceite_c1.py", "test_c1_preso", f'"{sys.executable}" aceite/aceite_c1.py')
    saida = sa.SaidaDoAceite("um teste preso", de_todos, (sa.AceiteDoCriterio("C1", (teste,)),))

    def rodar(comando: str) -> ResultadoDaSuite:
        return rodar_suite(tmp_path, comando, tmp_path / "descartavel.db", tempo_limite_s=LIMITE_DO_TESTE_PRESO_S, do_aceite=True)

    problemas, execucoes = sa.conferir_vermelho(saida, rodar)

    assert [(e.teste, e.codigo) for e in execucoes] == [("test_c1_preso", None)]
    assert len(problemas) == 1 and "o teste test_c1_preso de C1 nao terminou" in problemas[0]
    assert not marca.exists()


def test_depois_de_seis_que_nao_terminam_os_outros_ficam_para_a_rodada_seguinte_edge_case() -> None:
    """T3k.2: com oito testes sem fim, seis rodam, os dois que sobraram são nomeados e o comando de todos não roda."""
    nomes = tuple(f"test_c1_caso{n}" for n in range(1, 9))
    rodar = Rodador(sem_fim=nomes)

    problemas, execucoes = sa.conferir_vermelho(_saida(*nomes), rodar)

    assert len(rodar.comandos) == sa.PARTE_DA_SUITE_PARA_UM_TESTE == 6
    assert [e.teste for e in execucoes] == list(nomes[:6])
    assert sum("nao terminou" in problema for problema in problemas) == 6
    sobra = next(problema for problema in problemas if "nao foram rodados" in problema)
    assert "test_c1_caso7" in sobra and "test_c1_caso8" in sobra and "test_c1_caso6" not in sobra


def test_teto_no_meio_de_um_criterio_ja_atendido_nao_cobra_o_teste_que_nao_rodou_edge_case() -> None:
    """Achado 1 da revisão: o teste verde que ficou sem rodar por causa do teto não vira "nenhum teste dele passa"."""
    presos = tuple(f"test_c1_preso{n}" for n in range(1, 7))
    nomes = ("test_c1_vermelho", *presos, "test_c1_verde")
    testes = tuple(sa.TesteDeAceite(f"aceite/{nome}.py", nome, f"python aceite/{nome}.py") for nome in nomes)
    saida = sa.SaidaDoAceite("C1 em parte", COMANDO_DE_TODOS, (sa.AceiteDoCriterio("C1", testes, ja_atendido="somar ja existe"),))

    problemas, execucoes = sa.conferir_vermelho(saida, Rodador(sem_fim=presos))

    assert [e.teste for e in execucoes] == ["test_c1_vermelho", *presos]
    assert "test_c1_verde" in next(problema for problema in problemas if "nao foram rodados" in problema)
    assert not any("nenhum teste dele passa" in problema for problema in problemas)


def test_comando_de_todos_que_nao_termina_volta_ao_autor_edge_case() -> None:
    """Achado 2 da revisão: com cada teste vermelho e só o comando de todos preso, a conferência devolve o problema dele."""
    rodar = Rodador(sem_fim=(), todos_sem_fim=True)

    problemas, execucoes = sa.conferir_vermelho(_saida("test_c1_soma"), rodar)

    assert [e.codigo for e in execucoes] == [1, None]
    assert len(problemas) == 1 and f"o comando_aceite `{COMANDO_DE_TODOS}` nao terminou no limite da suite" in problemas[0]
    assert "--tempo-limite-suite" in problemas[0]


def test_com_todos_terminando_o_comando_de_todos_roda_como_antes_edge_case() -> None:
    """T3k.5 (contraprova): sem teste sem fim, o comando de todos roda por último e a conferência sai limpa."""
    rodar = Rodador(sem_fim=())

    problemas, execucoes = sa.conferir_vermelho(_saida("test_c1_soma", "test_c1_borda"), rodar)

    assert problemas == ()
    assert rodar.comandos[-1].endswith("aceite/todos.py") and len(rodar.comandos) == 3
    assert [e.teste for e in execucoes] == ["test_c1_soma", "test_c1_borda", sa.TESTE_DO_COMANDO_DE_ACEITE]


def test_cada_teste_roda_por_rodar_um_e_o_comando_de_todos_por_rodar_edge_case() -> None:
    """Caso de borda: com os dois rodadores, os testes sozinhos vão a um e o comando de todos ao outro."""
    de_um, de_todos = Rodador(sem_fim=()), Rodador(sem_fim=())

    sa.conferir_vermelho(_saida("test_c1_soma", "test_c1_borda"), de_todos, rodar_um=de_um)

    assert [Path(comando.split()[-1]).stem for comando in de_um.comandos] == ["test_c1_soma", "test_c1_borda"]
    assert [Path(comando.split()[-1]).stem for comando in de_todos.comandos] == ["todos"]


@pytest.mark.parametrize(
    ("limite_da_suite_s", "esperado_s"),
    [(1800.0, 300.0), (3600.0, 600.0), (120.0, 60.0), (30.0, 30.0)],
    ids=["padrao", "suite-de-uma-hora", "piso-de-um-minuto", "nunca-mais-que-a-suite"],
)
def test_limite_de_um_teste_e_um_sexto_do_da_suite_com_piso_e_teto_nominal(limite_da_suite_s: float, esperado_s: float) -> None:
    """T3k.4: um sexto do limite da suíte, nunca menos de um minuto nem mais que o da suíte."""
    assert sa.limite_de_um_teste(limite_da_suite_s) == esperado_s


def test_no_laco_o_teste_sozinho_recebe_o_limite_de_um_teste_e_o_comando_de_todos_o_da_suite_nominal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T3k.3: a conferência do autor passa a `rodar_suite` o limite de um teste para o teste sozinho e o da suíte para todos."""
    limites: list[float] = []

    def rodar_e_anotar(area: Path, comando: str, banco: Path, *, tempo_limite_s: float, do_aceite: bool = False) -> ResultadoDaSuite:
        limites.append(tempo_limite_s)
        return rodar_suite(area, comando, banco, tempo_limite_s=tempo_limite_s, do_aceite=do_aceite)

    monkeypatch.setattr(passo_do_aceite, "rodar_suite", rodar_e_anotar)
    roteiro = roteiro_completo()
    roteiro["executor"] = roteiro["executor"][:2]
    roteiro["verificador"] = [verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)
    opcoes = OpcoesDoLaco(modo="autonomo", tempo_limite_da_suite_s=LIMITE_DA_SUITE_S)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, opcoes).fechou

    assert limites == [sa.limite_de_um_teste(LIMITE_DA_SUITE_S), LIMITE_DA_SUITE_S] == [200.0, 1200.0]
