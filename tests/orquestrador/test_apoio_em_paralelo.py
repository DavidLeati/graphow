"""O apoio dos testes do laço com duas sessões ao mesmo tempo.

As fatias em paralelo vão rodar dois executores em threads. A telemetria da
bancada numa conexão `:memory:` presa à thread que a abriu dava
`ProgrammingError` na primeira escrita de outra thread.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from graphow.storage.telemetria_de_sessoes import SessaoRegistrada

from tests.orquestrador.apoio_laco import montar_bancada


def test_a_telemetria_da_bancada_aceita_a_escrita_de_outra_thread(tmp_path: Path) -> None:
    """A conexão de teste da telemetria é aberta para outras threads."""
    bancada = montar_bancada(tmp_path, {})
    with ThreadPoolExecutor(max_workers=1) as pool:
        id_linha = pool.submit(bancada.telemetria.registrar, SessaoRegistrada(id_goal="goal-soma", papel="executor")).result()
    assert [registro.id_linha for registro in bancada.telemetria.listar("goal-soma")] == [id_linha]
