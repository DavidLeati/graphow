"""T3a9: a janela da foto do humano vai da foto de antes da sessão ao fim do código do agente que o orquestrador roda."""

from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.humano_mexido import RepositorioDoHumanoMexido
from graphow.orquestrador.janela_do_humano import ConfiguracaoDaJanela, JanelaDoHumano

from tests.orquestrador.apoio_git import criar_repositorio
from tests.orquestrador.apoio_laco import ACEITE_C1, VERIFICAR, Bancada, executor_pronto, montar_bancada
from tests.orquestrador.test_foto_do_humano import TRABALHO, _notas_do_humano, _rodar
from tests.orquestrador.test_retomada import TUDO, roteiro_farto

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
FORA_DA_SESSAO: str = "o codigo que o agente escreveu, rodado pelo orquestrador fora da sessao, e nao "


def _checkout_no(humano: Path) -> str:
    """A linha de Python que roda `git -C <humano> checkout -- .`, por fora do hook da trava."""
    return f"import subprocess; subprocess.run(['git', '-C', r'{humano}', 'checkout', '--', '.'], check=True)\n"


def _aceite_que_limpa(humano: Path, *, so_depois_da_implementacao: bool) -> str:
    """O teste de aceite de C1 que o agente escreve e que, ao rodar, desfaz o trabalho do humano: sempre, ou só depois de a
    soma passar (então o vermelho do autor não o roda até ali)."""
    limpa = _checkout_no(humano)
    if so_depois_da_implementacao:
        return ACEITE_C1.replace("    assert somar(2, 3) == 5\n", f"    assert somar(2, 3) == 5\n    {limpa}")
    return limpa + ACEITE_C1


def _bancada_com_trabalho(tmp_path: Path) -> tuple[Bancada, dict[str, list[dict[str, Any]]]]:
    """A bancada do roteiro farto com o README.md do humano mudado e não commitado."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    (bancada.repositorio / "README.md").write_text(TRABALHO, encoding="utf-8", newline="\n")
    return bancada, roteiro


def _confere_a_perda_e_recupera(bancada: Bancada, mensagem: str) -> None:
    """O README.md voltou ao HEAD, a Note diz o mesmo, e os comandos dela devolvem o trabalho."""
    assert (bancada.repositorio / "README.md").read_text(encoding="utf-8") == "# brinquedo\n", "o codigo do agente apagou"
    (nota,) = _notas_do_humano(bancada)
    assert nota.obter_propriedade("perdas") == ["README.md voltou ao conteudo do HEAD ou do indice de antes da sessao"]
    assert str(nota.obter_propriedade("durante")) in mensagem
    for comando in nota.obter_propriedade("recuperar"):
        _rodar(comando)
    assert (bancada.repositorio / "README.md").read_text(encoding="utf-8") == TRABALHO


@pytest.mark.parametrize("so_depois", [True, False], ids=["na_verificacao", "no_vermelho_do_autor"])
def test_teste_de_aceite_que_desfaz_o_humano_para_o_laco_pelo_teste_edge_case(tmp_path: Path, so_depois: bool) -> None:
    """T3a9.1: o teste de aceite que o agente escreve roda `git -C <humano> checkout -- .`. [na_verificacao]: só depois da
    implementação, no aceite que o orquestrador roda antes do verificador, que nenhuma foto via (a do verificador nascia
    depois dele); [no_vermelho_do_autor]: sempre, já no vermelho que o orquestrador confere dentro da sessão do autor. O laço
    para em FALHA, e a parada diz que foi o teste rodado pelo orquestrador, e não a sessão."""
    bancada, roteiro = _bancada_com_trabalho(tmp_path)
    roteiro["aceite"][0]["arquivos"]["aceite/aceite_c1.py"] = _aceite_que_limpa(bancada.repositorio, so_depois_da_implementacao=so_depois)
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA and "repositorio_do_humano_mexido" in parada.mensagem, parada.mensagem
    teste, sessao = (("o aceite que o orquestrador rodou na verificacao do marco M1", "a sessao do verificador") if so_depois else
                     ("os testes de aceite que o orquestrador rodou para conferir o vermelho deles", "a sessao do aceite"))
    assert f"perdeu trabalho durante {teste}: README.md" in parada.mensagem, parada.mensagem
    assert f"{FORA_DA_SESSAO}{sessao}, mexeu fora do clone" in parada.mensagem, parada.mensagem
    assert len(bancada.chamadas("executor")) == (2 if so_depois else 0)
    _confere_a_perda_e_recupera(bancada, parada.mensagem)


def test_suite_rodada_pelo_orquestrador_que_desfaz_o_humano_para_o_laco_edge_case(tmp_path: Path) -> None:
    """T3a9.2: a suíte do plano (o verificar.py que o executor escreve) roda `git -C <humano> checkout -- .` quando o
    orquestrador a roda com a entrega, depois da sessão; o laço para em FALHA, pela suíte, e não pela sessão."""
    bancada, roteiro = _bancada_com_trabalho(tmp_path)
    roteiro["executor"][0] = executor_pronto({**TUDO, "verificar.py": _checkout_no(bancada.repositorio) + VERIFICAR})
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA and "repositorio_do_humano_mexido" in parada.mensagem, parada.mensagem
    assert "perdeu trabalho durante a suite que o orquestrador rodou com a entrega da fatia " in parada.mensagem, parada.mensagem
    assert f"{FORA_DA_SESSAO}a sessao do executor, mexeu fora do clone" in parada.mensagem, parada.mensagem
    assert len(bancada.chamadas("executor")) == 1 and bancada.chamadas("verificador") == []
    _confere_a_perda_e_recupera(bancada, parada.mensagem)


def test_suite_que_nao_mexe_nao_acrescenta_conferencia_alem_da_janela_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T3a9.2, contraprova: o Goal que fecha com um não rastreado no humano e a suíte que não mexe nele roda uma conferência
    (o `status` da foto de antes e o da de depois) por janela, e não uma por comando: a suíte da fatia e o aceite e a suíte
    da verificação são trechos da janela da sessão, sem `status` próprio; e as janelas não passam das sessões."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    (bancada.repositorio / "rascunho.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    original_run, original_fechar = subprocess.run, JanelaDoHumano.fechar
    status: list[list[str]] = []
    janelas: list[list[str]] = []

    def contar(comando: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(comando, list) and "--no-optional-locks" in comando and str(bancada.repositorio) in comando:
            status.extend([comando] if comando[comando.index("--no-optional-locks") + 1] == "status" else [])
        return original_run(comando, *args, **kwargs)

    def fechar(janela: JanelaDoHumano) -> None:
        janelas.extend([[trecho.quem for trecho in janela.trechos]] if janela.aberta else [])
        original_fechar(janela)

    monkeypatch.setattr(subprocess, "run", contar)
    monkeypatch.setattr(JanelaDoHumano, "fechar", fechar)
    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert len(status) == 2 * len(janelas), (len(status), janelas)
    com_suite = [janela for janela in janelas if any(quem.startswith("a suite que o orquestrador") for quem in janela)]
    assert len(com_suite) == 3 and all(janela[0] in ("a sessao do executor", "o aceite que o orquestrador rodou na verificacao "
                                                     "do marco M1") for janela in com_suite), janelas
    assert len(janelas) <= len(bancada.chamadas()), (janelas, len(bancada.chamadas()))
    assert _notas_do_humano(bancada) == [] and _notas_do_humano(bancada, "repositorio_do_humano_avancou") == []


def test_trecho_sem_janela_abre_e_fecha_a_dele_e_dentro_da_aberta_so_marca_nominal(tmp_path: Path) -> None:
    """A janela por dentro: o trecho sem janela aberta tem a foto e a conferência dele; dentro da aberta, só a marca, sem
    processo; e a conferência põe a perda no trecho em que o arquivo mudou."""
    repositorio = criar_repositorio(tmp_path / "humano", {"README.md": "# brinquedo\n"})
    (repositorio / "README.md").write_text(TRABALHO, encoding="utf-8", newline="\n")
    registradas: list[tuple[str, str, Any]] = []
    janela = JanelaDoHumano(ConfiguracaoDaJanela(repositorio, tmp_path / "salvaguarda",
                                                 lambda papel, fatia, mexido: registradas.append((papel, fatia, mexido))))
    with janela.trecho("a suite sozinha"):
        assert janela.aberta
    assert not janela.aberta and registradas == []

    janela.abrir()
    janela.marcar("a sessao do executor", papel="executor", fatia="F1")
    janela.marcar("a suite que o orquestrador rodou")
    subprocess.run([sys.executable, "-c", _checkout_no(repositorio)], check=True)
    janela.marcar("a sessao do revisor", papel="revisor")
    with pytest.raises(RepositorioDoHumanoMexido, match="perdeu trabalho durante a suite que o orquestrador rodou: README.md") as erro:
        janela.fechar()

    assert f"{FORA_DA_SESSAO}a sessao do executor e a sessao do revisor, mexeu" in str(erro.value)
    ((papel, fatia, mexido),) = registradas
    assert (papel, fatia, mexido.durante.texto) == ("executor", "F1", "a suite que o orquestrador rodou")
