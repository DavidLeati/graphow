"""`graphow bancada auditar`: o prompt do auditor sobre a execução, o relatório guardado e o PLACAR extraído."""

import argparse
import json
from pathlib import Path

import pytest

from graphow.api.cli_bancada import executar_bancada
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.bancada.auditoria import auditar, bloqueantes_listados, extrair_placar, pedido_do_auditor
from graphow.bancada.projetos import Bancada, ErroDaBancada, preencher_modelo
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao

from tests.sessoes.apoio import ambiente_de_teste, chamadas_registradas, comando_do_falso

STREAM_DO_AUDITOR: Path = Path(__file__).parent / "dados" / "stream_auditor.jsonl"
LINHA_DO_LABORATORIO: str = "PLACAR: criterios atende 14 / parcial 0 / nao_atende 0; sondas ok 6 / defeito 2; bloqueantes 0"


def _argumentos(*partes: str) -> argparse.Namespace:
    """`graphow bancada ...` analisado, com transcrições numa pasta que não existe."""
    return construir_parser().parse_args(["bancada", *partes, "--transcricoes", "nao-existe"])


def _execucao_do_estoque(tmp_path: Path, **extras: str) -> Path:
    """Uma execução da enxuta no estoque, rodada com o falso, que deixa o trabalho como pedido."""
    sessoes = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "registro-rodar", **extras))
    argumentos = _argumentos("rodar", "--arquitetura", "enxuta", "--projeto", "estoque-loja", "--saida", str(tmp_path / "saida"))
    assert executar_bancada(argumentos, EscritorConsoleEmMemoria(), sessoes=sessoes) == 0
    return next((tmp_path / "saida").iterdir())


def test_auditar_preenche_o_prompt_roda_na_pasta_propria_e_grava_o_placar_nominal(tmp_path: Path) -> None:
    """Prompt do laboratório com os caminhos da execução, sessão Opus em `auditoria/`, banco próprio e o PLACAR lido.

    A pasta de trabalho do auditor não é a da execução, onde está o relato do implementador em `sessoes/`."""
    execucao = _execucao_do_estoque(tmp_path, GRAPHOW_TESTE_COMMIT="chamado-142")
    registro = tmp_path / "registro-auditar"
    sessoes = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(registro, GRAPHOW_TESTE_STREAM=str(STREAM_DO_AUDITOR)))
    console = EscritorConsoleEmMemoria()

    codigo = executar_bancada(_argumentos("auditar", "--execucao", str(execucao)), console, sessoes=sessoes)

    assert codigo == 0, console.linhas
    bancada = Bancada()
    esperado = preencher_modelo(bancada.modelo_do_auditor(), {
        "REPO": str(execucao / "estoque-loja"),
        "SPEC": str(execucao / "spec-estoque-loja.md"),
        "RAMO": "chamado-142",
        "SONDAS": bancada.projeto("estoque-loja").texto_das_sondas(),
    })
    chamada = chamadas_registradas(registro)[0]
    assert chamada["stdin"] == esperado
    assert chamada["argv"][:5] == ["-p", "--model", "opus", "--permission-mode", "bypassPermissions"]
    assert Path(str(chamada["cwd"])) == execucao / "auditoria"
    assert not list(Path(str(chamada["cwd"])).glob("**/enxuta.jsonl"))
    assert chamada["env"]["GRAPHOW_DB"] == str(execucao / "auditoria" / "graphow.db")
    auditoria = json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
    assert auditoria["erro"] == ""
    assert auditoria["placar"]["criterios"] == {"atende": 14, "parcial": 0, "nao_atende": 0}
    assert (auditoria["placar"]["sondas_ok"], auditoria["placar"]["sondas_defeito"], auditoria["placar"]["bloqueantes"]) == (6, 2, 0)
    assert auditoria["metricas"]["custo_usd"] == 1.73
    assert (execucao / "auditoria" / "relatorio.md").read_text(encoding="utf-8").count("PLACAR:") == 1
    assert (execucao / "auditoria" / "prompt.md").read_text(encoding="utf-8") == esperado
    assert any(LINHA_DO_LABORATORIO in linha for linha in console.linhas)


def test_trabalho_nao_commitado_vai_ao_auditor_com_a_ressalva_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem o ramo, o auditor é mandado ao working tree, como na agenda do graphow."""
    execucao = _execucao_do_estoque(tmp_path)

    pedido = pedido_do_auditor(execucao, Bancada())

    assert "O trabalho está na branch `main (o trabalho está NÃO commitado no working tree;" in pedido.prompt


def test_relatorio_sem_placar_grava_erro_e_sai_com_1_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o stream da enxuta não tem PLACAR; nada é inventado."""
    execucao = _execucao_do_estoque(tmp_path)
    sessoes = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r"))

    codigo = executar_bancada(_argumentos("auditar", "--execucao", str(execucao)), EscritorConsoleEmMemoria(), sessoes=sessoes)

    auditoria = json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert auditoria["placar"] is None
    assert "PLACAR" in auditoria["erro"]


def _auditar_com(execucao: Path, sessoes: ExecutorDeSessao, *opcoes: str) -> tuple[int, EscritorConsoleEmMemoria]:
    """`graphow bancada auditar --execucao <execucao>` com as opções dadas."""
    console = EscritorConsoleEmMemoria()
    codigo = executar_bancada(_argumentos("auditar", "--execucao", str(execucao), *opcoes), console, sessoes=sessoes)
    return codigo, console


def test_auditoria_existente_recusa_e_nada_e_sobrescrito_edge_case(tmp_path: Path) -> None:
    """Caso de borda: auditar de novo sem --refazer recusa antes de tocar em qualquer arquivo da anterior."""
    execucao = _execucao_do_estoque(tmp_path, GRAPHOW_TESTE_COMMIT="chamado-142")
    auditor = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r", GRAPHOW_TESTE_STREAM=str(STREAM_DO_AUDITOR)))
    assert _auditar_com(execucao, auditor)[0] == 0
    antes = {caminho: caminho.read_bytes() for caminho in [execucao / "auditoria.json", *(execucao / "auditoria").iterdir()]}

    with pytest.raises(ErroDaBancada) as recusa:
        _auditar_com(execucao, auditor)

    assert recusa.value.contexto["existente"] == "auditoria.json, auditoria"
    assert {caminho: caminho.read_bytes() for caminho in antes} == antes
    assert len(chamadas_registradas(tmp_path / "r")) == 1


def test_auditor_que_morreu_no_meio_tambem_conta_como_auditoria_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sobrou só a pasta auditoria/ de um auditor interrompido, sem auditoria.json; recusa igual."""
    execucao = _execucao_do_estoque(tmp_path)
    (execucao / "auditoria").mkdir()
    (execucao / "auditoria" / "auditor.jsonl").write_text('{"type":"system","subtype":"init"}\n', encoding="utf-8")

    with pytest.raises(ErroDaBancada):
        _auditar_com(execucao, ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r")))


def test_refazer_guarda_a_anterior_com_sufixo_e_audita_de_novo_nominal(tmp_path: Path) -> None:
    """--refazer guarda auditoria/ e auditoria.json como auditoria-anterior-1 (depois -2) e grava a nova."""
    execucao = _execucao_do_estoque(tmp_path, GRAPHOW_TESTE_COMMIT="chamado-142")
    auditor = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r", GRAPHOW_TESTE_STREAM=str(STREAM_DO_AUDITOR)))
    assert _auditar_com(execucao, auditor)[0] == 0
    primeira = (execucao / "auditoria.json").read_bytes()

    codigo, console = _auditar_com(execucao, auditor, "--refazer")
    assert _auditar_com(execucao, auditor, "--refazer")[0] == 0

    assert codigo == 0
    assert (execucao / "auditoria-anterior-1.json").read_bytes() == primeira
    assert (execucao / "auditoria-anterior-1" / "relatorio.md").is_file()
    assert (execucao / "auditoria-anterior-2" / "auditor.jsonl").is_file()
    atual = json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
    assert (atual["auditoria_anterior"], atual["erro"]) == ("auditoria-anterior-2", "")
    assert any("auditoria anterior guardada como auditoria-anterior-1" in linha for linha in console.linhas)


def test_auditor_que_estoura_o_tempo_grava_auditoria_json_com_o_erro_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o auditor morre no tempo limite, sem `result`; auditoria.json diz por quê, sem placar nem custo."""
    execucao = _execucao_do_estoque(tmp_path)
    auditor = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r", GRAPHOW_TESTE_DORMIR="60"))

    codigo, _ = _auditar_com(execucao, auditor, "--tempo-limite", "0.05")

    auditoria = json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert auditoria["erro"] == "a sessao do auditor terminou com erro: tempo esgotado, sem evento result no stream"
    assert (auditoria["placar"], auditoria["relatorio"], auditoria["metricas"]["custo_usd"]) == (None, None, None)
    assert auditoria["sessao"]["tempo_esgotado"] is True


def test_auditor_que_nao_abre_grava_auditoria_json_com_o_erro_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o executável do auditor não existe; a recusa vira o erro da auditoria, e não um registro ausente."""
    execucao = _execucao_do_estoque(tmp_path)
    auditor = ExecutorDeSessao((str(tmp_path / "nao-existe.exe"),), ambiente_de_teste(tmp_path / "r"))

    codigo, _ = _auditar_com(execucao, auditor)

    auditoria = json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert auditoria["erro"].startswith("a sessao do auditor nao abriu:")
    assert (auditoria["placar"], auditoria["sessao"]) == (None, None)


class _AuditorQueDerrubaABancada:
    """Lê o auditoria.json enquanto a sessão roda e derruba o processo, como o fim abrupto da sessão de quem chamou."""

    def __init__(self, execucao: Path) -> None:
        self.execucao = execucao
        self.durante: dict[str, object] = {}

    def rodar(self, pedido: PedidoDeSessao) -> ResultadoDeSessao:
        """Guarda o registro do meio da sessão e interrompe."""
        self.durante = json.loads((self.execucao / "auditoria.json").read_text(encoding="utf-8"))
        raise KeyboardInterrupt


def test_auditoria_json_existe_desde_antes_da_sessao_e_diz_que_ela_nao_terminou_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o processo da bancada morre durante o auditor; o registro que fica diz que a sessão não terminou."""
    execucao = _execucao_do_estoque(tmp_path)
    auditor = _AuditorQueDerrubaABancada(execucao)

    with pytest.raises(KeyboardInterrupt):
        auditar(execucao, pedido_do_auditor(execucao, Bancada()), auditor, transcricoes=None)  # type: ignore[arg-type]

    restante = json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
    assert auditor.durante == restante
    assert restante["erro"] == "a sessao do auditor nao terminou (interrompida, ou ainda rodando)"
    assert restante["placar"] is None


def test_pasta_sem_execucao_json_recusa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: auditar o que não foi montado pela bancada recusa com o caminho."""
    with pytest.raises(ErroDaBancada) as recusa:
        pedido_do_auditor(tmp_path, Bancada())

    assert recusa.value.contexto["arquivo"].endswith("execucao.json")


def test_placar_no_formato_do_prompt_nominal() -> None:
    """A linha exata que o prompt pede."""
    placar = extrair_placar(f"relatorio\n\n{LINHA_DO_LABORATORIO}\n- nenhum")

    assert placar is not None
    assert (placar.atende, placar.parcial, placar.nao_atende) == (14, 0, 0)
    assert (placar.sondas_ok, placar.sondas_defeito, placar.bloqueantes) == (6, 2, 0)
    assert placar.linha == LINHA_DO_LABORATORIO


@pytest.mark.parametrize(
    "linha",
    [
        "**PLACAR:** critérios atende 9 / parcial 3 / não_atende 0; sondas ok 0 / defeito 8; bloqueantes 3",
        "`PLACAR: criterios atende 9 / parcial 3 / nao atende 0; sondas ok 0 / defeitos 8; bloqueantes: 3`",
        "PLACAR: criterios atende: 9 / parcial: 3 / nao_atende: 0; sondas ok: 0 / defeito: 8; bloqueantes: 3",
    ],
)
def test_placar_com_o_que_o_modelo_costuma_mudar_edge_case(linha: str) -> None:
    """Caso de borda: negrito, crase, acento, espaço no lugar do sublinhado e dois-pontos."""
    placar = extrair_placar(linha)

    assert placar is not None
    assert (placar.atende, placar.parcial, placar.nao_atende, placar.sondas_ok, placar.sondas_defeito, placar.bloqueantes) == (
        9, 3, 0, 0, 8, 3,
    )


def test_vale_o_ultimo_placar_com_numeros_edge_case() -> None:
    """Caso de borda: o auditor repete o formato com letras e depois dá o placar; o modelo do prompt não conta."""
    texto = "\n".join([
        'Formato: "PLACAR: criterios atende X / parcial Y / nao_atende Z; sondas ok A / defeito B; bloqueantes C"',
        "PLACAR: criterios atende 1 / parcial 1 / nao_atende 1; sondas ok 1 / defeito 7; bloqueantes 1",
        "PLACAR: criterios atende 2 / parcial 0 / nao_atende 0; sondas ok 8 / defeito 0; bloqueantes 0",
        "PLACAR: incompleto",
    ])

    placar = extrair_placar(texto)

    assert placar is not None and (placar.atende, placar.sondas_ok) == (2, 8)
    assert extrair_placar("sem placar nenhum") is None


def test_bloqueantes_listados_depois_do_placar_nominal() -> None:
    """A lista que o prompt pede depois do PLACAR; o que vem antes dele não conta."""
    texto = "- antes\nPLACAR: criterios atende 1 / parcial 0 / nao_atende 1; sondas ok 7 / defeito 1; bloqueantes 2\n\n" \
            "1. 500 em GET /tarefas?pagina=99999999999999999999 (storage.js:107)\n- POST aceita status\nfim"

    assert bloqueantes_listados(texto) == ("500 em GET /tarefas?pagina=99999999999999999999 (storage.js:107)", "POST aceita status")
    assert bloqueantes_listados("- sem placar") == ()
