"""A fatia aberta pelo rebase não tira a mudança da base nova (revisão da T3g3 e da T3g4, V1 e V2).

No texto, a conferência é mecânica: `git merge-tree --merge-base=<base antiga>
<base nova> <resultado>` devolve o próprio resultado quando a mudança da base
continua nele. No comportamento (um arquivo do Goal que anula em tempo de
execução o que a base trouxe, um pacote novo que o import prefere ao arquivo
da base), não há conferência mecânica: a fatia vai à revisão de risco já na
primeira tentativa, com o diff da base no briefing.
"""

from pathlib import Path

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import executor_pronto, montar_bancada, revisao, verificacao
from tests.orquestrador.test_base_que_andou import SOMA_COM_CABECALHO, SOMA_DA_BASE_QUE_CONFLITA, SOMA_RESOLVIDA
from tests.orquestrador.test_fatia_de_conflito import (
    _commit,
    _fatia_de_conflito,
    _humano_depois_do_verificador,
    _roteiro_com_a_fatia,
    _roteiro_do_fator,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
SOMA_QUE_ESCAPA: str = "import fator\nfator.FATOR = 1\n\n\ndef somar(a, b):\n    return a + b\n"
SOMA_PELO_FATOR: str = "# soma de inteiros\ndef somar(a, b):\n    return (a + b) / 2\n"
VERIFICAR_PELO_FATOR: str = "from soma import somar\nassert somar(2, 3) == 2.5, 'C1'\nprint('ok')\n"
SOMA_DA_BASE_EM_DOIS_TRECHOS: str = "# soma de inteiros\ndef somar(a, b):\n    # so inteiros\n    return 0\n"
SOMA_SEM_O_CABECALHO: str = "def somar(a, b):\n    # so inteiros\n    return a + b\n"
SOMA_COM_OS_DOIS: str = "# soma de inteiros\ndef somar(a, b):\n    # so inteiros\n    return a + b\n"
SOMA_SEM_O_CABECALHO_E_COM_A_LINHA_COLADA: str = "def somar(a, b):  # do goal\n    # so inteiros\n    return a + b\n"
RECUSA: str = "tirou do resultado parte do que a base nova"


def test_fatia_do_vermelho_que_tira_a_linha_da_base_e_recusada_e_a_que_corrige_so_o_goal_passa_edge_case(tmp_path: Path) -> None:
    """T3g5.2 (V1 da sonda): a base põe o cabeçalho em soma.py e muda fator.py, e o aceite fica vermelho; o executor que
    tira o cabeçalho é recusado antes da suíte, com o arquivo e o que a base poria de volta; o que muda só o código do Goal
    passa, e a main tem as duas mudanças."""
    corrige = executor_pronto({"soma.py": SOMA_PELO_FATOR, "verificar.py": VERIFICAR_PELO_FATOR})
    roteiro = _roteiro_do_fator(executor_pronto({"soma.py": SOMA_QUE_ESCAPA}), corrige)
    roteiro["verificador"].append(verificacao("atende"))
    bancada = montar_bancada(tmp_path, roteiro)
    _commit(bancada.repositorio, {"fator.py": "FATOR = 1\n"}, "Fator")
    executor = _humano_depois_do_verificador(bancada, {"soma.py": SOMA_COM_CABECALHO, "fator.py": "FATOR = 2\n"})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    conflito = _fatia_de_conflito(bancada)
    assert conflito.propriedades["conflito_com_a_base"]["motivo"] == "aceite_vermelho"
    executores = bancada.chamadas("executor")
    assert len(executores) == 4, "a primeira tentativa da fatia foi recusada, e houve uma segunda"
    segunda = executores[3]["stdin"]
    assert RECUSA in segunda and "em soma.py:" in segunda and "+# soma de inteiros" in segunda, segunda
    assert parada.fechou and conflito.falhas == 1, parada.mensagem
    assert git(bancada.repositorio, "show", "main:soma.py") == SOMA_PELO_FATOR
    assert git(bancada.repositorio, "show", "main:fator.py") == "FATOR = 2\n"


def test_fatia_de_conflito_que_tira_a_base_fora_do_trecho_em_conflito_e_recusada_edge_case(tmp_path: Path) -> None:
    """T3g5.2: a base muda soma.py em dois trechos, e só um conflita com o Goal; a resolução que tira o outro (o cabeçalho)
    é recusada, e a que mantém os dois passa: no arquivo em conflito, só o trecho em conflito do rebase pode diferir da base
    (a linha 1 da base nova falta no resultado, fora dele)."""
    roteiro = _roteiro_com_a_fatia(executor_pronto({"soma.py": SOMA_SEM_O_CABECALHO}), executor_pronto({"soma.py": SOMA_COM_OS_DOIS}))
    bancada = montar_bancada(tmp_path, roteiro)
    executor = _humano_depois_do_verificador(bancada, {"soma.py": SOMA_DA_BASE_EM_DOIS_TRECHOS})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    conflito = _fatia_de_conflito(bancada)
    assert conflito.propriedades["conflito_com_a_base"]["motivo"] == "conflito"
    executores = bancada.chamadas("executor")
    assert len(executores) == 4 and RECUSA in executores[3]["stdin"], "a primeira tentativa da fatia foi recusada"
    assert "soma.py (linha 1 da base nova, linha da base fora do resultado)" in executores[3]["stdin"]
    assert parada.fechou and conflito.falhas == 1, parada.mensagem
    assert git(bancada.repositorio, "show", "main:soma.py") == SOMA_COM_OS_DOIS


def test_fatia_de_conflito_que_tira_o_cabecalho_e_muda_a_linha_colada_a_ele_e_recusada_edge_case(tmp_path: Path) -> None:
    """T3g6.1 (sonda da revisão da T3g5): o executor tira o cabeçalho, fora do trecho em conflito, e muda a linha colada a
    ele, o que abre na mescla um conflito novo; o conflito fica fora do trecho que o rebase abriu, e a fatia é recusada com o
    arquivo e o trecho (as linhas da base nova); a resolução que mantém os dois passa, e a main tem o cabeçalho."""
    primeira = executor_pronto({"soma.py": SOMA_SEM_O_CABECALHO_E_COM_A_LINHA_COLADA})
    roteiro = _roteiro_com_a_fatia(primeira, executor_pronto({"soma.py": SOMA_COM_OS_DOIS}))
    bancada = montar_bancada(tmp_path, roteiro)
    executor = _humano_depois_do_verificador(bancada, {"soma.py": SOMA_DA_BASE_EM_DOIS_TRECHOS})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    conflito = _fatia_de_conflito(bancada)
    executores = bancada.chamadas("executor")
    assert len(executores) == 4, "a primeira tentativa da fatia foi recusada, e houve uma segunda"
    segunda = executores[3]["stdin"]
    assert RECUSA in segunda and "soma.py (linhas 1 a 4 da base nova, conflito fora do trecho do rebase)" in segunda, segunda
    assert "+# soma de inteiros" in segunda.split(RECUSA, 1)[1], segunda
    assert parada.fechou and conflito.falhas == 1, parada.mensagem
    assert git(bancada.repositorio, "show", "main:soma.py") == SOMA_COM_OS_DOIS


def test_fatia_aberta_pelo_rebase_vai_a_revisao_de_risco_na_primeira_tentativa_com_o_diff_da_base_nominal(tmp_path: Path) -> None:
    """T3g5.3: a fatia de conflito que passa de primeira vai à revisão de risco nessa mesma tentativa, e o briefing do
    revisor traz o diff da base nova (o conflito e o arquivo que só ela mudou) e pergunta se o resultado o anula."""
    bancada = montar_bancada(tmp_path, _roteiro_com_a_fatia(executor_pronto({"soma.py": SOMA_RESOLVIDA})))
    executor = _humano_depois_do_verificador(bancada, {"soma.py": SOMA_DA_BASE_QUE_CONFLITA, "NOTAS.txt": "do humano\n"})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    conflito = _fatia_de_conflito(bancada)
    assert conflito.falhas == 0
    (revisor,) = bancada.chamadas("revisor")
    briefing = revisor["stdin"]
    assert "Por que ela e revisada: foi aberta pelo rebase" in briefing
    da_base = briefing.split("## O que a base nova trouxe", 1)[1]
    assert "+    # so inteiros" in da_base and "+do humano" in da_base and "anula o que a base trouxe" in da_base
    revisao = bancada.kernel.obter_view().obter_no(f"rev-{conflito.id}-t1")
    assert revisao is not None and revisao.obter_propriedade("veredito") == "aprovado"


def test_pacote_novo_que_sombreia_o_arquivo_da_base_fica_com_a_revisao_da_primeira_tentativa_edge_case(tmp_path: Path) -> None:
    """T3g5.3 (V2 da sonda): fator/__init__.py, que o import prefere ao fator.py da base, passa no texto, na suíte e no
    aceite; a revisão da 1ª tentativa, com o diff de fator.py no briefing, é quem o recusa, e o Goal não chega à main."""
    roteiro = _roteiro_do_fator(executor_pronto({"fator/__init__.py": "FATOR = 1\n"}), executor_pronto({}))
    roteiro["revisor"] = [revisao("rejeitado")]
    bancada = montar_bancada(tmp_path, roteiro)
    _commit(bancada.repositorio, {"fator.py": "FATOR = 1\n"}, "Fator")
    executor = _humano_depois_do_verificador(bancada, {"fator.py": "FATOR = 2\n"})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    (revisor,) = bancada.chamadas("revisor")
    assert "-FATOR = 1\n+FATOR = 2" in revisor["stdin"].split("## O que a base nova trouxe", 1)[1]
    assert "fator/__init__.py" in revisor["stdin"].split("Arquivos mudados", 1)[1]
    assert parada.motivo == MotivoDaParada.PENDENCIA and "M1.R1" in parada.mensagem, parada.mensagem
    assert git(bancada.repositorio, "ls-tree", "-r", "--name-only", "main", "--", "fator", "fator.py").split() == ["fator.py"]
