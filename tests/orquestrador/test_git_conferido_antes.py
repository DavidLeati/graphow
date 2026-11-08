"""T3a10, item 2: os arquivos que mudam o git são relidos logo depois de cada sessão e na retomada, antes do primeiro git."""

import os
from pathlib import Path
import sys
from typing import Any

import pytest

from graphow.orquestrador import laco, sessoes_de_papel
from graphow.orquestrador.contexto_do_laco import Parada
from graphow.orquestrador.janela_do_humano import NA_QUEDA, JanelaDoHumano
from graphow.orquestrador.janela_gravada import JANELA_GRAVADA
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import Bancada, Queda, executor_pronto, montar_bancada
from tests.orquestrador.test_arquivos_do_git import AUTONOMO, _parou_no_arquivo
from tests.orquestrador.test_git_sem_codigo_plantado import PLANTA_NA_GLOBAL, _casa_falsa
from tests.orquestrador.test_retomada import TUDO, roteiro_farto

# A sessão que acrescenta à global (argv 1) um filtro `clean` que roda o script dado (argv 2), e põe no clone o
# `.gitattributes` que o liga: o `-c` do orquestrador não desliga filtro, e o `add` da suíte sem rastro o rodaria.
PLANTA_O_FILTRO: str = ("import pathlib, sys\np = pathlib.Path(sys.argv[1])\n"
                        "p.write_bytes(p.read_bytes() + (\"[filter \\\"x\\\"]\\n\\tclean = sh '\" + sys.argv[2] + \"'\\n\").encode())\n"
                        "pathlib.Path('.gitattributes').write_text('* filter=x\\n')\n")


class _CaiDepoisDoExecutor(ExecutorDeSessao):
    """A sessão do executor roda, e o processo do orquestrador cai logo depois dela."""

    def __init__(self, base: ExecutorDeSessao) -> None:
        super().__init__(base._executavel, base._ambiente)

    def rodar(self, pedido: PedidoDeSessao) -> ResultadoDeSessao:
        """A sessão; a do executor derruba o processo."""
        resultado = super().rodar(pedido)
        if pedido.arquivo_stream.name.startswith("executor-"):
            raise Queda()
        return resultado


def _script(tmp_path: Path) -> tuple[Path, Path]:
    """O script plantado (grava o marcador e sai com erro) e o marcador."""
    marca, script = tmp_path / "marca.txt", tmp_path / "plantado.sh"
    script.write_bytes(f"#!/bin/sh\necho rodou >> '{marca.as_posix()}'\ncat\n".encode())
    return script, marca


def _espiar(monkeypatch: pytest.MonkeyPatch, modulo: Any, nome: str, anotar: Any = None) -> list[Any]:
    """A função do módulo passa a anotar cada chamada (o nome, ou o que `anotar()` diz na hora), e segue rodando; devolve
    a lista das anotações."""
    chamadas: list[Any] = []
    original = getattr(modulo, nome)

    def anotada(*argumentos: Any, **nomeados: Any) -> Any:
        chamadas.append(anotar() if anotar is not None else nome)
        return original(*argumentos, **nomeados)

    monkeypatch.setattr(modulo, nome, anotada)
    return chamadas


def test_filtro_plantado_na_global_para_o_laco_logo_depois_da_sessao_edge_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A sessão planta na global um `filter.x.clean`, que o `-c` não desliga, e o liga no clone. A janela relê a global
    logo depois da sessão: o laço para por ela, sem restaurar o clone, e o filtro não roda. Contraprova: o `git add`
    comum no clone o roda."""
    global_ = _casa_falsa(tmp_path, monkeypatch)
    script, marca = _script(tmp_path)
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path / "b", roteiro)
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", PLANTA_O_FILTRO, str(global_), script.as_posix()]])
    bancada.trocar_roteiro(roteiro)
    restauracoes = _espiar(monkeypatch, sessoes_de_papel, "restaurar_o_clone", lambda: len(bancada.chamadas("executor")))

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    _parou_no_arquivo(bancada, parada, Path(os.path.abspath(global_)).as_posix())
    assert "durante a sessao do executor" in parada.mensagem, parada.mensagem
    assert not marca.exists(), "o filtro plantado na global rodou pelo git do orquestrador"
    assert restauracoes and not any(restauracoes), "o clone foi restaurado (git) depois da sessao do executor"
    area = bancada.raiz / "estado" / "goal-soma" / "area"
    git(area, "add", "-A")
    assert marca.exists(), "contraprova: o add comum roda o filtro da global"


def _cair_e_retomar(bancada: Bancada, monkeypatch: pytest.MonkeyPatch) -> tuple[Parada, list[str]]:
    """A primeira chamada cai logo depois da sessão do executor, sem fechar a janela (o processo morreu); a segunda, com
    o `retomar_o_rebase` e o `preparar_area` espiados, retoma."""
    fechar = JanelaDoHumano.fechar
    monkeypatch.setattr(JanelaDoHumano, "fechar", lambda janela: None)
    with pytest.raises(Queda):
        bancada.orquestrador(executor=_CaiDepoisDoExecutor(bancada.executor)).iniciar_da_spec(bancada.spec, bancada.repositorio,
                                                                                               AUTONOMO)
    assert (bancada.raiz / "estado" / "goal-soma" / JANELA_GRAVADA).is_file(), "a janela aberta ficou gravada"
    monkeypatch.setattr(JanelaDoHumano, "fechar", fechar)
    rebases, preparos = _espiar(monkeypatch, laco, "retomar_o_rebase"), _espiar(monkeypatch, laco, "preparar_area")
    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    return parada, rebases + preparos


@pytest.mark.parametrize("mexida", [True, False], ids=["global_mexida", "nada_mexido"])
def test_retomada_com_a_global_mexida_para_antes_do_fetch_edge_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                     mexida: bool) -> None:
    """T3a10.3: a sessão planta `core.fsmonitor` na global e o orquestrador cai com a janela aberta. A retomada relê a
    global contra a janela gravada antes do primeiro git: para por ela, sem `retomar_o_rebase` nem `preparar_area` (o
    `fetch`), e a gravação sai. Contraprova: a queda sem nada mexido retoma até o Goal fechar."""
    global_ = _casa_falsa(tmp_path, monkeypatch)
    script, marca = _script(tmp_path)
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path / "b", roteiro)
    if mexida:
        roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", PLANTA_NA_GLOBAL, str(global_),
                                                                        script.as_posix()]])
    bancada.trocar_roteiro(roteiro)

    parada, gits = _cair_e_retomar(bancada, monkeypatch)

    assert not (bancada.raiz / "estado" / "goal-soma" / JANELA_GRAVADA).exists()
    if not mexida:
        assert parada.fechou and gits, parada.mensagem
        return
    _parou_no_arquivo(bancada, parada, Path(os.path.abspath(global_)).as_posix())
    assert NA_QUEDA in parada.mensagem and not gits and not marca.exists(), (gits, parada.mensagem)
