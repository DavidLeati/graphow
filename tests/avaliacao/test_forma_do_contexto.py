"""A forma do contexto por Goal: peso por turno, saídas grandes, pausas, leituras fora do alvo e os Run mais caros."""

from graphow.avaliacao.forma_do_contexto import (
    agregar_forma,
    casa_com_alvo,
    contar_fora_do_alvo,
    formatar_forma,
)
from graphow.avaliacao.orquestracao import MedidorDeOrquestracao
from graphow.avaliacao.relatorio_orquestracao import formatar_relatorio
from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from tests.avaliacao.test_orquestracao import _derivado, _montar, _run, _tarefa


def test_caminho_lido_casa_com_o_alvo_por_sufixo_nominal() -> None:
    """Absoluto contra relativo, barra do Windows, maiúsculas e pasta-alvo casam; o vizinho não."""
    assert casa_com_alvo(r"C:\Users\David\Repo\SRC\Mp\a.py", "src/mp/a.py")
    assert casa_com_alvo("src/mp/a.py", "C:/repo/src/mp/a.py")
    assert casa_com_alvo("C:/repo/src/mp/referencias/b.py", "./src/mp/referencias/")
    assert not casa_com_alvo("C:/repo/src/mp/aa.py", "src/mp/a.py")
    assert not casa_com_alvo("C:/repo/src/mp", "src/mp/a.py")


def test_sem_alvo_a_contagem_fica_de_fora_edge_case() -> None:
    """Caso de borda: sem alvo contra o qual medir, nada de zero inventado."""
    assert contar_fora_do_alvo(["a.py"], []) is None
    assert contar_fora_do_alvo(["a.py", "b.py"], ["a.py"]) == 1


def test_agregado_pondera_a_media_pelos_turnos_nominal() -> None:
    """O Run de 90 turnos pesa nove vezes o de 10; picos no máximo, contagens somadas."""
    longo = {"mensagens_de_modelo": 90, "contexto_medio_turno": 200, "contexto_maximo_turno": 500, "maior_saida_ferramenta": 30000,
             "saidas_acima_2000": 4, "pausas_acima_5min": 1, "maior_pausa_s": 480}
    curto = {"mensagens_de_modelo": 10, "contexto_medio_turno": 100, "contexto_maximo_turno": 150, "maior_pausa_s": 10}

    forma = agregar_forma([(longo, 3), (curto, None)])

    assert forma is not None
    assert (forma.contexto_medio, forma.contexto_maximo, forma.turnos_maximo) == (190, 500, 90)
    assert (forma.maior_saida, forma.saidas_grandes, forma.pausas_longas, forma.leituras_fora_do_alvo) == (30000, 4, 1, 3)
    assert formatar_forma(forma) == (
        "contexto: medio/turno 190, maximo 500 | turnos max 90 | maior saida 30.000 car, 4 saidas >2k"
        " | 1 pausas >5min (maior 8 min) | 3 leituras fora do alvo"
    )


def test_run_sem_forma_nao_da_agregado_edge_case() -> None:
    """Caso de borda: Run gravado antes da forma do contexto não produz linha nenhuma."""
    assert agregar_forma([({"tokens_entrada": 10, "mensagens_de_modelo": 3}, None)]) is None


def _montar_com_forma() -> WriteKernel:
    """O cenário de sempre, com um executor que leu dentro e fora do alvo da tarefa."""
    kernel = _montar()
    operacoes = (
        *_tarefa("t4", "goal-a", arquivos_alvo=["src/mp/a.py"]),
        *_derivado("evi-leitura", TipoNo.EVIDENCE, ("t4",), arquivo="src/mp/b.py"),
    )
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="forma")
    assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso
    _run(
        kernel, "run-exec-4", agente="graphow-executor", tarefas=["t4"], tokens_entrada=9000, tokens_saida=1000,
        mensagens_de_modelo=240, duracao_s=3000, contexto_medio_turno=350000, contexto_maximo_turno=400000,
        maior_saida_ferramenta=33000, saidas_acima_2000=14, pausas_acima_5min=3, maior_pausa_s=420,
        caminhos_lidos=["C:/repo/src/mp/a.py", "C:/repo/src/mp/b.py", "C:/repo/README.md"],
        caminhos_lidos_shell=["src/outro.py", "src/mp/a.py"],
        saidas_grandes_por_ferramenta={"Bash": 8, "Read": 4, "expandir_no": 1, "ler_vista": 1},
    )
    return kernel


def test_relatorio_mostra_a_forma_e_os_runs_mais_caros_nominal() -> None:
    """O Goal ganha a linha do contexto, com as leituras do Read e do shell contra o alvo e a Evidence, e a dos Run mais caros."""
    medicao = next(m for m in MedidorDeOrquestracao(_montar_com_forma().obter_view()).medir() if m.id_goal == "goal-a")

    linhas = formatar_relatorio((medicao,))

    assert medicao.forma is not None and medicao.forma.leituras_fora_do_alvo == 2
    assert "  contexto: medio/turno 350.000, maximo 400.000 | turnos max 240 | maior saida 33.000 car, 14 saidas >2k" \
           " | >2k: Bash 8, Read 4, expandir_no 1 | 3 pausas >5min (maior 7 min) | 2 leituras fora do alvo" in linhas
    caros = next(linha for linha in linhas if linha.startswith("  mais caros: "))
    assert caros.startswith("  mais caros: graphow-executor 10.000 tokens, 50 min, 240 turnos, contexto medio 350.000; ")
    assert caros.count(";") == 2


def test_relatorio_sem_forma_fica_como_era_edge_case() -> None:
    """Caso de borda: com só Run antigos, nenhuma linha nova aparece."""
    linhas = formatar_relatorio(MedidorDeOrquestracao(_montar().obter_view()).medir())

    assert not any(linha.strip().startswith(("contexto:", "mais caros:")) for linha in linhas)
