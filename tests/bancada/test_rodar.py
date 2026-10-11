"""`graphow bancada rodar`: a execução montada da semente, a sessão certa chamada e `execucao.json` gravado."""

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from graphow.api.cli_bancada import executar_bancada
from graphow.api.cli_execucao import ExecutorLinhaDeComando
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.bancada.arquiteturas import PedidoDeExecucao, RegistroDeArquiteturas, registro_padrao
from graphow.bancada.projetos import Bancada, ErroDaBancada
from graphow.bancada.semente import GitDaBancada
from graphow.core.exceptions import GraphowError
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao
from graphow.storage.localizador_banco import AmbienteEmMemoria, LocalizadorBancoEventos

from tests.bancada.test_projetos import SHA_DO_PROMPT_DA_ENXUTA
from tests.sessoes.apoio import ambiente_de_teste, chamadas_registradas, comando_do_falso, criar_executavel_falso

ARGUMENTOS_DA_SESSAO_ENXUTA: list[str] = [
    "-p", "--model", "opus", "--permission-mode", "bypassPermissions", "--output-format", "stream-json", "--verbose",
]
# O stream gravado tem duas respostas da sessão principal; o falso grava a transcrição delas e a de um subagente.
TOKENS_DAS_TRANSCRICOES_DO_FALSO: int = (2 + 7 + 52248 + 7638) + (2 + 42 + 66890 + 522) + (1000 + 10)


def _rodar_pela_cli(argumentos: list[str], dados: Path) -> tuple[int, EscritorConsoleEmMemoria]:
    """`graphow ...` pelo executor da linha de comando, com o diretório de dados no temporário."""
    console = EscritorConsoleEmMemoria()
    ambiente = AmbienteEmMemoria({"LOCALAPPDATA": str(dados)}, dados)
    codigo = ExecutorLinhaDeComando(console, LocalizadorBancoEventos(ambiente)).executar(construir_parser().parse_args(argumentos))
    return codigo, console


def _unica_execucao(saida: Path) -> Path:
    """A pasta da única execução criada na saída."""
    pastas = [pasta for pasta in saida.iterdir() if pasta.is_dir()]
    assert len(pastas) == 1, pastas
    return pastas[0]


def test_rodar_enxuta_no_estoque_monta_a_execucao_e_chama_a_sessao_certa_nominal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pela CLI, com o executável falso em GRAPHOW_CLAUDE: repositório da semente, spec ao lado, prompt do
    laboratório pela entrada, pasta do repositório, banco próprio e as métricas em execucao.json."""
    registro, projetos = tmp_path / "registro", tmp_path / "projetos"
    for nome, valor in ambiente_de_teste(registro, GRAPHOW_TESTE_COMMIT="chamado-142").items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("GRAPHOW_CLAUDE", str(criar_executavel_falso(tmp_path / "bin")))
    monkeypatch.setenv("GRAPHOW_TESTE_TRANSCRICOES", str(projetos))

    codigo, console = _rodar_pela_cli(
        ["bancada", "rodar", "--arquitetura", "enxuta", "--projeto", "estoque-loja",
         "--saida", str(tmp_path / "saida"), "--transcricoes", str(projetos)],
        tmp_path / "dados",
    )

    assert codigo == 0, console.linhas
    execucao = _unica_execucao(tmp_path / "saida")
    assert execucao.name.startswith("enxuta-estoque-loja-")
    projeto = Bancada().projeto("estoque-loja")
    assert (execucao / "spec-estoque-loja.md").read_bytes() == projeto.spec.read_bytes()
    git = GitDaBancada(execucao / "estoque-loja")
    assert git.rodar("rev-parse", "chamado-142~1").strip() == projeto.semente.commit
    chamada = chamadas_registradas(registro)[0]
    assert chamada["argv"] == ARGUMENTOS_DA_SESSAO_ENXUTA
    assert Path(str(chamada["cwd"])) == execucao / "estoque-loja"
    assert hashlib.sha256(str(chamada["stdin"]).encode("utf-8")).hexdigest() == SHA_DO_PROMPT_DA_ENXUTA["estoque-loja"]
    ambiente = chamada["env"]
    assert isinstance(ambiente, dict)
    assert ambiente["GRAPHOW_DB"] == str(execucao / "graphow.db")
    assert not [nome for nome in ambiente if nome.upper().startswith("CLAUDE")]
    gravado = json.loads((execucao / "execucao.json").read_text(encoding="utf-8"))
    assert (gravado["arquitetura"], gravado["projeto"], gravado["erro"]) == ("enxuta", "estoque-loja", "")
    metricas = gravado["metricas"]
    assert (metricas["custo_usd"], metricas["commits"], metricas["fonte_dos_tokens"]) == (5.03, 1, "transcricoes")
    assert metricas["tokens"] == TOKENS_DAS_TRANSCRICOES_DO_FALSO
    assert metricas["minutos"] is not None and metricas["minutos"] < 5
    assert gravado["sessoes"][0]["comando"][1:] == ARGUMENTOS_DA_SESSAO_ENXUTA
    assert (execucao / "sessoes" / "enxuta.jsonl").is_file()
    assert any("--permission-mode bypassPermissions" in linha for linha in console.linhas)


def _argumentos(saida: Path, projeto: str, arquitetura: str = "enxuta") -> argparse.Namespace:
    """Os argumentos de `bancada rodar`, sem passar pelo analisador."""
    return construir_parser().parse_args(
        ["bancada", "rodar", "--arquitetura", arquitetura, "--projeto", projeto, "--saida", str(saida),
         "--transcricoes", str(saida.parent / "sem-transcricoes")]
    )


def test_todos_roda_os_tres_projetos_cada_um_na_sua_pasta_nominal(tmp_path: Path) -> None:
    """Três execuções, três sessões, cada uma no repositório do seu projeto; sem transcrição, tokens do modelUsage."""
    registro = tmp_path / "registro"
    sessoes = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(registro))

    codigo = executar_bancada(_argumentos(tmp_path / "saida", "todos"), EscritorConsoleEmMemoria(), sessoes=sessoes)

    assert codigo == 0
    pastas = sorted(pasta.name.rsplit("-", 2)[0] for pasta in (tmp_path / "saida").iterdir())
    assert pastas == ["enxuta-agenda-salas", "enxuta-api-tarefas", "enxuta-estoque-loja"]
    diretorios = {Path(str(chamada["cwd"])).name for chamada in chamadas_registradas(registro)}
    assert diretorios == {"agenda-salas", "api-tarefas", "estoque-loja"}
    for pasta in (tmp_path / "saida").iterdir():
        metricas = json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))["metricas"]
        assert (metricas["fonte_dos_tokens"], metricas["tokens"], metricas["commits"]) == ("model_usage", 6_200_140, 0)


def test_sessao_com_erro_fica_gravada_e_a_saida_e_1_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o processo saiu com 3; a execução é gravada assim mesmo, com a sessão marcada."""
    sessoes = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r", GRAPHOW_TESTE_SAIDA="3"))

    codigo = executar_bancada(_argumentos(tmp_path / "saida", "agenda-salas"), EscritorConsoleEmMemoria(), sessoes=sessoes)

    gravado = json.loads((_unica_execucao(tmp_path / "saida") / "execucao.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert gravado["sessoes"][0]["is_error"] is True
    assert gravado["sessoes"][0]["codigo_saida"] == 3


def test_arquitetura_desconhecida_recusa_antes_de_criar_pasta_edge_case(tmp_path: Path) -> None:
    """Caso de borda: `orquestrar` ainda não existe nesta fase; nada é montado."""
    sessoes = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r"))

    with pytest.raises(ErroDaBancada) as recusa:
        executar_bancada(_argumentos(tmp_path / "saida", "agenda-salas", "orquestrar"), EscritorConsoleEmMemoria(), sessoes=sessoes)

    assert recusa.value.contexto["registradas"] == "enxuta"
    assert not (tmp_path / "saida").exists()


class _ArquiteturaQueFalha:
    """Uma arquitetura registrada de fora que recusa no meio, como uma fase futura poderia."""

    nome: str = "quebrada"

    def executar(self, pedido: PedidoDeExecucao, sessoes: ExecutorDeSessao) -> tuple[ResultadoDeSessao, ...]:
        """Confere que recebeu a execução montada e recusa."""
        assert (pedido.repositorio / ".git").is_dir() and pedido.spec.is_file()
        raise GraphowError("plano recusado", {"motivo": "teste"})


def test_arquitetura_registrada_de_fora_roda_e_a_falha_fica_gravada_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o ponto de extensão aceita outra arquitetura; a falha dela vai para o `erro` da execução."""
    registro = registro_padrao()
    registro.registrar("quebrada", _ArquiteturaQueFalha)
    sessoes = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r"))

    codigo = executar_bancada(
        _argumentos(tmp_path / "saida", "api-tarefas", "quebrada"), EscritorConsoleEmMemoria(), registro=registro, sessoes=sessoes
    )

    gravado = json.loads((_unica_execucao(tmp_path / "saida") / "execucao.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert "plano recusado" in gravado["erro"]
    assert gravado["sessoes"] == [] and gravado["metricas"]["custo_usd"] == 0.0


def test_registro_recusa_o_mesmo_nome_duas_vezes_edge_case() -> None:
    """Caso de borda: registrar `enxuta` de novo é engano, não substituição."""
    registro = RegistroDeArquiteturas()
    registro.registrar("enxuta", _ArquiteturaQueFalha)

    with pytest.raises(ErroDaBancada):
        registro.registrar("enxuta", _ArquiteturaQueFalha)
    assert registro.nomes == ("enxuta",)
