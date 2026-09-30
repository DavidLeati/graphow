"""`graphow base-colisoes` sobre um repositório git de verdade, criado no teste, sem rede.

O ramo `main` é o do Goal; `stage` é o ramo base, que ganhou uma migration
depois que `main` saiu dele. O remoto, quando há, é outro repositório local.
"""

from pathlib import Path
import shutil
import subprocess
from typing import Any

import pytest

from graphow.api.cli_execucao import ExecutorLinhaDeComando
from graphow.api.cli_parser import construir_parser
from graphow.api.conferencia_base import CODIGO_COM_COLISAO, CODIGO_CONFERENCIA_IMPOSSIVEL, CODIGO_SEM_COLISAO
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.localizador_banco import AmbienteEmMemoria, LocalizadorBancoEventos
from graphow.storage.sqlite_store import SQLiteEventStore

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git fora do PATH do teste")

MIGRATIONS: list[str] = ["**/migrations/*.py"]
MIGRATION_DA_BASE: str = "app/migrations/0002_da_base.py"
MIGRATION_DO_GOAL: str = "app/migrations/0002_do_goal.py"


def _git(repositorio: Path, *argumentos: str) -> str:
    """Roda o git no repositório do teste, com identidade própria e sem assinatura."""
    configuracao = ["-c", "user.name=teste", "-c", "user.email=teste@exemplo.invalid", "-c", "commit.gpgsign=false"]
    resultado = subprocess.run(
        ["git", "-C", str(repositorio), *configuracao, *argumentos], capture_output=True, text=True, check=True
    )
    return resultado.stdout


def _commitar(repositorio: Path, arquivos: dict[str, str]) -> None:
    """Escreve os arquivos e faz um commit com eles."""
    for caminho, conteudo in arquivos.items():
        destino = repositorio / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8")
    _git(repositorio, "add", "--all")
    _git(repositorio, "commit", "--quiet", "-m", "passo")


def _repositorio(raiz: Path) -> Path:
    """`main` e `stage` saem do mesmo commit; `stage` ganha uma migration e um texto fora do glob."""
    repositorio = raiz / "repo"
    repositorio.mkdir()
    _git(repositorio, "init", "--quiet", "-b", "main")
    _commitar(repositorio, {"app/migrations/0001_inicial.py": "# 1\n", "app/models.py": "# modelos\n"})
    _git(repositorio, "branch", "stage")
    _git(repositorio, "checkout", "--quiet", "stage")
    _commitar(repositorio, {MIGRATION_DA_BASE: "# 2 da base\n", "docs/leia.md": "base\n"})
    _git(repositorio, "checkout", "--quiet", "main")
    return repositorio


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, Any]) -> ItemPatch:
    """Operação que cria um nó com as propriedades dadas."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação que cria a aresta entre dois nós."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _gravar_goal(dados: Path, propriedades: dict[str, dict[str, Any]], alvos: list[str]) -> None:
    """Projeto > Setor > Sessao que produz o Goal, e uma Task do Goal com os arquivos-alvo dados."""
    operacoes = [
        _no("proj", TipoNo.PROJETO, propriedades.get("proj", {})),
        _no("setor", TipoNo.SETOR, propriedades.get("setor", {})),
        _no("sess", TipoNo.SESSAO, {}),
        _no("goal", TipoNo.GOAL, propriedades.get("goal", {})),
        _no("task", TipoNo.TASK, {"status": "pendente", "arquivos_alvo": alvos}),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        _aresta("setor", "sess", TipoAresta.CONTEM),
        _aresta("sess", "goal", TipoAresta.PRODUZ),
        _aresta("sess", "task", TipoAresta.PRODUZ),
        _aresta("goal", "task", TipoAresta.DECOMPOE),
    ]
    caminho = dados / "graphow" / "graphow.db"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with SQLiteEventStore(str(caminho)) as store:
        recibo = WriteKernel(store).submeter_patch(PropostaPatch.criar(DadosPropostaPatch("david", PapelAutor.HUMANO, operacoes)))
    assert recibo.sucesso, recibo.mensagem


def _executar(argumentos: list[str], dados: Path) -> tuple[int, list[str]]:
    """Roda o subcomando com o banco no diretório de dados do teste."""
    console = EscritorConsoleEmMemoria()
    ambiente = AmbienteEmMemoria({"LOCALAPPDATA": str(dados)}, dados)
    codigo = ExecutorLinhaDeComando(console, LocalizadorBancoEventos(ambiente)).executar(construir_parser().parse_args(argumentos))
    return codigo, list(console.linhas)


def _colisoes(linhas: list[str]) -> list[str]:
    """As linhas de colisão da saída."""
    return [linha for linha in linhas if " x " in linha]


def _conferir(tmp_path: Path, propriedades: dict[str, dict[str, Any]], alvos: list[str]) -> tuple[int, list[str]]:
    """Grava o Goal e confere contra o repositório padrão do teste, sem fetch."""
    repositorio = _repositorio(tmp_path)
    _gravar_goal(tmp_path, propriedades, alvos)
    return _executar(["base-colisoes", "--goal", "goal", "--repo", str(repositorio), "--sem-fetch"], tmp_path)


def test_sem_colisao_sai_com_zero_e_sem_linha_de_colisao_nominal(tmp_path: Path) -> None:
    """O Goal que não toca migrations não colide com a que o ramo base ganhou."""
    codigo, linhas = _conferir(tmp_path, {"goal": {"ramo_base": "stage", "caminhos_de_colisao": MIGRATIONS}}, ["app/views.py"])

    assert codigo == CODIGO_SEM_COLISAO
    assert _colisoes(linhas) == []
    assert "Sem colisao com stage." in linhas


def test_migration_nova_no_mesmo_diretorio_colide_nominal(tmp_path: Path) -> None:
    """Números diferentes no mesmo diretório: é a colisão que o merge não acusa."""
    codigo, linhas = _conferir(
        tmp_path, {"goal": {"ramo_base": "stage", "caminhos_de_colisao": MIGRATIONS}}, [MIGRATION_DO_GOAL]
    )

    assert codigo == CODIGO_COM_COLISAO
    assert _colisoes(linhas) == [f"{MIGRATION_DA_BASE} x {MIGRATION_DO_GOAL}"]


def test_arquivo_fora_do_glob_nao_colide_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o ramo base alterou docs/leia.md, que o Goal também toca, mas fora dos globs."""
    codigo, linhas = _conferir(
        tmp_path, {"goal": {"ramo_base": "stage", "caminhos_de_colisao": MIGRATIONS}}, ["docs/leia.md"]
    )

    assert codigo == CODIGO_SEM_COLISAO
    assert _colisoes(linhas) == []


def test_goal_sem_ramo_base_diz_que_nao_ha_o_que_conferir_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem ramo_base na herança, a saída é uma mensagem e o código é zero."""
    codigo, linhas = _conferir(tmp_path, {"proj": {"caminhos_de_colisao": MIGRATIONS}}, [MIGRATION_DO_GOAL])

    assert codigo == CODIGO_SEM_COLISAO
    assert any("sem ramo_base" in linha and "nada a conferir" in linha for linha in linhas)
    assert _colisoes(linhas) == []


def test_heranca_do_setor_e_do_projeto_nominal(tmp_path: Path) -> None:
    """O ramo base vem do Projeto e os globs do Setor, e o cabeçalho diz de onde veio cada um."""
    codigo, linhas = _conferir(
        tmp_path,
        {"proj": {"ramo_base": "stage", "caminhos_de_colisao": ["**/*.sql"]}, "setor": {"caminhos_de_colisao": MIGRATIONS}},
        [MIGRATION_DO_GOAL],
    )

    assert codigo == CODIGO_COM_COLISAO
    assert any(linha.startswith("Ramo base: stage (de proj)") and "(de setor)" in linha for linha in linhas)
    assert _colisoes(linhas) == [f"{MIGRATION_DA_BASE} x {MIGRATION_DO_GOAL}"]


def test_goal_vence_a_heranca_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o ramo base gravado no Goal vence o do Projeto; aqui ele é o próprio main, sem nada novo."""
    codigo, linhas = _conferir(
        tmp_path,
        {"proj": {"ramo_base": "stage", "caminhos_de_colisao": MIGRATIONS}, "goal": {"ramo_base": "main"}},
        [MIGRATION_DO_GOAL],
    )

    assert codigo == CODIGO_SEM_COLISAO
    assert "Sem colisao com main." in linhas


def test_ramo_base_inexistente_sai_com_dois_edge_case(tmp_path: Path) -> None:
    """Caso de borda: não conferir não é colisão; o código 2 separa os dois casos."""
    codigo, linhas = _conferir(
        tmp_path, {"goal": {"ramo_base": "nao-existe", "caminhos_de_colisao": MIGRATIONS}}, [MIGRATION_DO_GOAL]
    )

    assert codigo == CODIGO_CONFERENCIA_IMPOSSIVEL
    assert any(linha.startswith("ERRO: ramo base inexistente") for linha in linhas)


def test_goal_inexistente_sai_com_dois_edge_case(tmp_path: Path) -> None:
    """Caso de borda: id errado é recusa clara, não traceback."""
    _gravar_goal(tmp_path, {}, [])

    codigo, linhas = _executar(["base-colisoes", "--goal", "goal-errado", "--sem-fetch"], tmp_path)

    assert codigo == CODIGO_CONFERENCIA_IMPOSSIVEL
    assert "Goal inexistente: goal-errado" in linhas


def test_ramo_remoto_e_atualizado_pelo_fetch_nominal(tmp_path: Path) -> None:
    """`origin/stage` faz fetch do remoto antes; com --sem-fetch, fica a cópia local, mais velha.

    O remoto é outro repositório no disco: o fetch roda sem rede.
    """
    upstream = _repositorio(tmp_path)
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", str(upstream), str(clone))
    _git(upstream, "checkout", "--quiet", "stage")
    _commitar(upstream, {"app/migrations/0003_depois_do_clone.py": "# 3\n"})
    _gravar_goal(tmp_path, {"goal": {"ramo_base": "origin/stage", "caminhos_de_colisao": MIGRATIONS}}, ["app/migrations/0003_do_goal.py"])
    argumentos = ["base-colisoes", "--goal", "goal", "--repo", str(clone)]

    codigo_local, linhas_local = _executar([*argumentos, "--sem-fetch"], tmp_path)
    codigo, linhas = _executar(argumentos, tmp_path)

    assert codigo_local == CODIGO_COM_COLISAO
    assert _colisoes(linhas_local) == [f"{MIGRATION_DA_BASE} x app/migrations/0003_do_goal.py"]
    assert codigo == CODIGO_COM_COLISAO
    assert "app/migrations/0003_depois_do_clone.py x app/migrations/0003_do_goal.py" in _colisoes(linhas)


def test_ramo_com_cara_de_opcao_nao_chega_ao_git_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o nome vem do grafo, e um trecho que começa por `-` seria lido como opção."""
    codigo, linhas = _conferir(
        tmp_path, {"goal": {"ramo_base": "origin/--upload-pack=x", "caminhos_de_colisao": MIGRATIONS}}, [MIGRATION_DO_GOAL]
    )

    assert codigo == CODIGO_CONFERENCIA_IMPOSSIVEL
    assert any(linha.startswith("ERRO: ramo_base invalido") for linha in linhas)


def test_fetch_que_falha_avisa_e_confere_com_a_copia_local_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem o remoto (sem rede, por exemplo), a conferência segue com o que há e diz isso."""
    upstream = _repositorio(tmp_path)
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", str(upstream), str(clone))
    _git(clone, "remote", "set-url", "origin", str(tmp_path / "remoto-que-sumiu"))
    _gravar_goal(tmp_path, {"goal": {"ramo_base": "origin/stage", "caminhos_de_colisao": MIGRATIONS}}, [MIGRATION_DO_GOAL])

    codigo, linhas = _executar(["base-colisoes", "--goal", "goal", "--repo", str(clone)], tmp_path)

    assert codigo == CODIGO_COM_COLISAO
    assert any(linha.startswith("Aviso: fetch de origin stage falhou") for linha in linhas)
    assert _colisoes(linhas) == [f"{MIGRATION_DA_BASE} x {MIGRATION_DO_GOAL}"]
