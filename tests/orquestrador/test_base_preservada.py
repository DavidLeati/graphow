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
from tests.orquestrador.apoio_laco import executor_pronto, montar_bancada, verificacao
from tests.orquestrador.test_base_que_andou import SOMA_COM_CABECALHO
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
    é recusada, e a que mantém os dois passa: no arquivo em conflito, a mescla favorece o resultado só no trecho dele."""
    roteiro = _roteiro_com_a_fatia(executor_pronto({"soma.py": SOMA_SEM_O_CABECALHO}), executor_pronto({"soma.py": SOMA_COM_OS_DOIS}))
    bancada = montar_bancada(tmp_path, roteiro)
    executor = _humano_depois_do_verificador(bancada, {"soma.py": SOMA_DA_BASE_EM_DOIS_TRECHOS})

    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    conflito = _fatia_de_conflito(bancada)
    assert conflito.propriedades["conflito_com_a_base"]["motivo"] == "conflito"
    executores = bancada.chamadas("executor")
    assert len(executores) == 4 and RECUSA in executores[3]["stdin"], "a primeira tentativa da fatia foi recusada"
    assert parada.fechou and conflito.falhas == 1, parada.mensagem
    assert git(bancada.repositorio, "show", "main:soma.py") == SOMA_COM_OS_DOIS
