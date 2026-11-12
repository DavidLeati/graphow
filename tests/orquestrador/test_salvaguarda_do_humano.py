"""T3a7, item 3: a salvaguarda fica fora do repositório do humano e a recuperação sobrevive ao `git gc --prune=now`; T3a9,
itens 2 e 3: o avanço aponta para ela, e ela sai quando o Goal fecha; T3a11, item 2: a que uma Note de perda cita fica;
T3a14: a que uma Note de avanço cita com o que mostrar também fica."""

import base64
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from graphow.orquestrador.conferencia_do_humano import conferir_as_fotos, conferir_o_humano
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.foto_do_humano import foto_antes_da_sessao, fotografar_o_humano
from graphow.orquestrador.suite import shell_dos_agentes

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import executor_pronto, montar_bancada
from tests.orquestrador.test_foto_do_humano import _notas_do_humano
from tests.orquestrador.test_retomada import TUDO, roteiro_farto
from tests.orquestrador.test_trava_do_git import ExecutorComHumano

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
TRABALHO: str = "TRABALHO DO HUMANO, NAO COMMITADO\n"
PREPARADO: str = "no indice, pelo git add\n"
RASCUNHO: bytes = b"rascunho solto\r\ncom CRLF\r\n"
COMANDO_IMPRESSO: re.Pattern[str] = re.compile(r"`(git -C [^`]+)`")
# A sessão que apaga o trabalho do humano e poda os objetos soltos dele: `reset --hard`, o não rastreado e o `gc`, com o
# git sem a trava do ambiente (o hook dela recusaria o `pack-refs` do `gc`).
SESSAO_QUE_PODA: str = (
    "import os, subprocess\nh = {h!r}\n"
    "sem_trava = {{nome: valor for nome, valor in os.environ.items() if not nome.startswith('GIT_CONFIG')}}\n"
    "subprocess.run(['git', '-C', h, 'reset', '-q', '--hard'], check=True, env=sem_trava)\n"
    "os.remove(os.path.join(h, 'rascunho.txt'))\n"
    "subprocess.run(['git', '-C', h, 'gc', '-q', '--prune=now'], check=True, env=sem_trava)\n"
)


def _no_git_bash(comando: str) -> None:
    """O comando colado no Git Bash."""
    shell = shell_dos_agentes()
    if shell is None:
        pytest.skip("sem bash na maquina")
    subprocess.run([str(shell), "-c", comando], check=True, capture_output=True)


def _no_powershell(comando: str) -> None:
    """O comando colado no PowerShell, tal como está (o `-EncodedCommand` não passa pelas aspas da linha de comando)."""
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("sem PowerShell na maquina")
    codificado = base64.b64encode(comando.encode("utf-16-le")).decode("ascii")
    subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand", codificado], check=True, capture_output=True)


@pytest.mark.parametrize("colar", [_no_git_bash, _no_powershell], ids=["git_bash", "powershell"])
def test_comando_impresso_recupera_os_tres_depois_do_gc_edge_case(tmp_path: Path, colar: object) -> None:
    """T3a7.2 (F9): com uma mudança no índice, outra só na árvore e um não rastreado, a sessão faz `reset --hard`, apaga o
    não rastreado e roda `gc --prune=now`, que poda o blob do `git add`. O laço para, a pasta da salvaguarda fica, e os
    comandos que a parada imprime, colados no shell, devolvem os três."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    h = bancada.repositorio
    (h / "README.md").write_text(TRABALHO, encoding="utf-8", newline="\n")
    (h / "preparado.txt").write_text(PREPARADO, encoding="utf-8", newline="\n")
    git(h, "add", "preparado.txt")
    (h / "rascunho.txt").write_bytes(RASCUNHO)
    blob_do_add = git(h, "rev-parse", ":preparado.txt").strip()
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", SESSAO_QUE_PODA.format(h=str(h))]])
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, h, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA and "repositorio_do_humano_mexido" in parada.mensagem, parada.mensagem
    assert bancada.chamadas("executor")[0]["comandos"][0]["codigo"] == 0, "a sessao rodou o reset, o rm e o gc"
    assert subprocess.run(["git", "-C", str(h), "cat-file", "-e", blob_do_add], capture_output=True, check=False).returncode != 0
    (nota,) = _notas_do_humano(bancada)
    pasta = Path(str(nota.obter_propriedade("guardada_em")))
    assert pasta.is_dir() and pasta.parent.parent == bancada.raiz / "estado" and pasta.name == "salvaguarda-do-humano", pasta
    assert not pasta.is_relative_to(h) and (pasta.parent / "area").is_dir(), "ao lado do clone, fora dele e do humano"
    comandos = COMANDO_IMPRESSO.findall(parada.mensagem)
    assert [comando.split(" ")[3] for comando in comandos] == ["fetch", "stash", "restore"], comandos
    for comando in comandos:
        colar(comando)  # type: ignore[operator]
    assert (h / "README.md").read_text(encoding="utf-8") == TRABALHO
    assert (h / "preparado.txt").read_text(encoding="utf-8") == PREPARADO
    assert (h / "rascunho.txt").read_bytes() == RASCUNHO


def _listagem(pasta: Path) -> dict[str, tuple[int, int]]:
    """Cada arquivo e pasta debaixo da pasta, com o tamanho e o mtime em nanossegundos."""
    return {item.relative_to(pasta).as_posix(): (os.stat(item).st_size if item.is_file() else 0, os.stat(item).st_mtime_ns)
            for item in pasta.rglob("*")}


def test_foto_de_um_repositorio_sujo_nao_cria_nem_muda_arquivo_no_git_do_humano_nominal(tmp_path: Path) -> None:
    """T3a7.4: a foto de antes (com a salvaguarda dos rastreados, dos não rastreados e do não rastreado igual a um objeto do
    humano) e a de depois não criam nem mudam arquivo nenhum no `.git` do humano: nem objeto, nem índice, nem data."""
    repositorio = criar_repositorio(tmp_path / "humano", {"README.md": "# brinquedo\n", "NOTAS.txt": "notas\n", "docs/a.txt": "a\n"})
    git(repositorio, "gc", "-q")
    (repositorio / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    (repositorio / "preparado.txt").write_text(PREPARADO, encoding="utf-8", newline="\n")
    git(repositorio, "add", "preparado.txt")
    (repositorio / "rascunho.txt").write_bytes(RASCUNHO)
    shutil.copyfile(repositorio / "README.md", repositorio / "copia.txt")
    antes = _listagem(repositorio / ".git")

    foto = foto_antes_da_sessao(repositorio, salvaguarda=tmp_path / "salvaguarda")
    conferir_o_humano(foto, "executor", "")

    assert foto is not None and foto.salvaguarda.stash and foto.salvaguarda.soltos
    assert _listagem(repositorio / ".git") == antes
    assert list((tmp_path / "salvaguarda" / "objects" / "pack").glob("*.pack")), "o pack do que o stash alcanca e o HEAD nao"


def _retoca(repositorio: Path, *caminhos: str) -> str:
    """O F3 da sonda: `checkout -- .` e um retoque em cada arquivo dado (a linha a mais), em Python, por fora do hook."""
    retoques = "".join(f"open(os.path.join(h, {caminho!r}), 'ab').write(b'+')\n" for caminho in caminhos)
    return (f"import os, subprocess\nh = {str(repositorio)!r}\n"
            f"subprocess.run(['git', '-C', h, 'checkout', '--', '.'], check=True)\n{retoques}")


def test_checkout_e_retoque_e_avanco_com_o_comando_que_mostra_o_de_antes_edge_case(tmp_path: Path) -> None:
    """T3a9.3 (F3): `checkout -- .` seguido de um retoque é avanço (T3a6); o que a conferência devolve traz o `git show`
    da pasta da salvaguarda, com o hash dela, que mostra o conteúdo de antes do rastreado e do não rastreado, os bytes
    como estavam, sem mudar nada no repositório do humano."""
    repositorio = criar_repositorio(tmp_path / "humano", {"README.md": "# brinquedo\n"})
    (repositorio / "README.md").write_text(TRABALHO, encoding="utf-8", newline="\n")
    (repositorio / "rascunho.txt").write_bytes(RASCUNHO)
    foto = foto_antes_da_sessao(repositorio, salvaguarda=tmp_path / "salvaguarda")
    assert foto is not None
    subprocess.run([sys.executable, "-c", _retoca(repositorio, "README.md", "rascunho.txt")], check=True)

    mexido = conferir_as_fotos(foto, fotografar_o_humano(repositorio, foto.listados))

    assert mexido.perdas == () and mexido.avancos == ("README.md mudou para um conteudo novo", "rascunho.txt mudou para um conteudo novo")
    pasta = (tmp_path / "salvaguarda").as_posix()
    assert mexido.ver_o_de_antes == (f'git -C "{pasta}" show "{foto.salvaguarda.stash}:README.md"',
                                     f'git -C "{pasta}" show "{foto.salvaguarda.soltos}:rascunho.txt"')
    estado = _listagem(repositorio / ".git")
    saidas = [subprocess.run(comando, shell=True, capture_output=True, check=True).stdout for comando in mexido.ver_o_de_antes]
    assert saidas == [TRABALHO.encode("utf-8"), RASCUNHO]
    assert _listagem(repositorio / ".git") == estado, "o git show roda na pasta da salvaguarda, nao no humano"


def test_note_do_avanco_do_checkout_com_retoque_traz_o_hash_da_salvaguarda_edge_case(tmp_path: Path) -> None:
    """T3a9.3 (F3), no laço: a sessão do executor faz `checkout -- .` no humano e retoca NOTAS.txt; o laço segue, e a Note
    do avanço traz o hash da salvaguarda e o `git show` com ele."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    h = bancada.repositorio
    (h / "NOTAS.txt").write_text("notas\n", encoding="utf-8", newline="\n")
    git(h, "add", "NOTAS.txt")
    git(h, "commit", "-q", "-m", "Notas do humano")
    (h / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", _retoca(h, "NOTAS.txt")]])
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, h, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert (h / "NOTAS.txt").read_text(encoding="utf-8") == "notas\n+", "o trabalho saiu, e o retoque o esconde da conferencia"
    assert _notas_do_humano(bancada) == []
    (avanco,) = _notas_do_humano(bancada, "repositorio_do_humano_avancou")
    salvaguarda, pasta = str(avanco.obter_propriedade("salvaguarda")), Path(str(avanco.obter_propriedade("guardada_em")))
    assert avanco.obter_propriedade("avancos") == ["NOTAS.txt mudou para um conteudo novo"]
    assert salvaguarda and avanco.obter_propriedade("ver_o_de_antes") == [f'git -C "{pasta.as_posix()}" show "{salvaguarda}:NOTAS.txt"']
    assert avanco.obter_propriedade("durante") == "a sessao do executor"


@pytest.mark.parametrize("fecha", [True, False], ids=["goal_que_fecha", "laco_em_falha"])
def test_goal_que_fecha_apaga_a_salvaguarda_e_o_que_para_em_falha_a_deixa_edge_case(tmp_path: Path, fecha: bool) -> None:
    """T3a9.4: com um não rastreado no humano, toda janela grava a salvaguarda. O Goal que fecha não deixa a pasta (nem o
    clone); o laço que para em FALHA (a sessão do executor apaga o não rastreado) a deixa, e a parada a cita."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    rascunho, pasta = bancada.repositorio / "rascunho.txt", bancada.raiz / "estado" / "goal-soma" / "salvaguarda-do-humano"
    rascunho.write_bytes(RASCUNHO)
    vista: list[bool] = []
    apagar = [] if fecha else [[sys.executable, "-c", f"import os; os.remove(r'{rascunho}')"]]
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=apagar)
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador(executor=ExecutorComHumano(bancada.executor, lambda: vista.append(pasta.is_dir()), na=3)
                                  ).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert vista == [True], "a salvaguarda existia durante a sessao do executor"
    if fecha:
        assert parada.fechou and not pasta.exists() and not (pasta.parent / "area").exists(), parada.mensagem
        assert rascunho.read_bytes() == RASCUNHO, "o nao rastreado do humano fica"
        return
    assert parada.motivo == MotivoDaParada.FALHA and f"em {pasta}:" in parada.mensagem, parada.mensagem
    assert (pasta / "HEAD").is_file() and not rascunho.exists()


def test_goal_que_fecha_depois_da_falha_com_perda_deixa_a_salvaguarda_citada_edge_case(tmp_path: Path) -> None:
    """T3a11.2 (S6): a sessão do executor apaga o não rastreado, e o laço para em FALHA citando a salvaguarda. Rodado de novo,
    como a parada sugere, o Goal fecha sem o clone; a pasta que a Note da perda cita fica, a mensagem diz onde, e o
    `recuperar` da Note devolve o arquivo depois do fechamento."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    rascunho, pasta = bancada.repositorio / "rascunho.txt", bancada.raiz / "estado" / "goal-soma" / "salvaguarda-do-humano"
    rascunho.write_bytes(RASCUNHO)
    apagar = [[sys.executable, "-c", f"import os; os.remove(r'{rascunho}')"]]
    roteiro["executor"].insert(0, executor_pronto(dict(TUDO), comandos=apagar))
    bancada.trocar_roteiro(roteiro)
    primeira = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    assert primeira.motivo == MotivoDaParada.FALHA and f"em {pasta}:" in primeira.mensagem, primeira.mensagem
    (nota,) = _notas_do_humano(bancada)

    segunda = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert segunda.fechou and (pasta / "HEAD").is_file() and not (pasta.parent / "area").exists(), segunda.mensagem
    assert f"A salvaguarda {pasta} fica no disco" in segunda.mensagem and "Apague a pasta quando quiser" in segunda.mensagem
    assert nota.obter_propriedade("guardada_em") == str(pasta) and not rascunho.exists()
    for comando in nota.obter_propriedade("recuperar"):
        subprocess.run(comando, shell=True, check=True, capture_output=True)
    assert rascunho.read_bytes() == RASCUNHO


def test_goal_que_fecha_com_avanco_que_cita_a_salvaguarda_deixa_a_pasta_edge_case(tmp_path: Path) -> None:
    """T3a14.1 (A5): a sessão do executor faz `checkout -- .` no humano e retoca NOTAS.txt. É avanço, o laço segue e o Goal
    fecha no mesmo `iniciar`; a pasta que a Note do avanço cita fica, a mensagem diz onde, e o `ver_o_de_antes` da Note
    devolve o trabalho do humano depois do fechamento."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    h, pasta = bancada.repositorio, bancada.raiz / "estado" / "goal-soma" / "salvaguarda-do-humano"
    (h / "NOTAS.txt").write_text("notas\n", encoding="utf-8", newline="\n")
    git(h, "add", "NOTAS.txt")
    git(h, "commit", "-q", "-m", "Notas do humano")
    (h / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", _retoca(h, "NOTAS.txt")]])
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, h, AUTONOMO)

    assert parada.fechou and (pasta / "HEAD").is_file() and not (pasta.parent / "area").exists(), parada.mensagem
    assert f"A salvaguarda {pasta} fica no disco: a Note do avanco" in parada.mensagem, parada.mensagem
    assert "Apague a pasta quando quiser" in parada.mensagem
    (avanco,) = _notas_do_humano(bancada, "repositorio_do_humano_avancou")
    (comando,) = avanco.obter_propriedade("ver_o_de_antes")
    assert avanco.obter_propriedade("guardada_em") == str(pasta) and _notas_do_humano(bancada) == []
    assert subprocess.run(comando, shell=True, capture_output=True, check=True).stdout == TRABALHO.encode("utf-8")


def test_goal_que_fecha_com_avanco_sem_o_que_mostrar_apaga_a_salvaguarda_edge_case(tmp_path: Path) -> None:
    """T3a14.2: com um não rastreado no humano (a pasta existe), a sessão do executor só cria um arquivo novo ali. É avanço
    sem conteúdo de antes para mostrar: a Note não cita nada que more na pasta, e o Goal que fecha a apaga, como na T3a9.4."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    h, pasta = bancada.repositorio, bancada.raiz / "estado" / "goal-soma" / "salvaguarda-do-humano"
    (h / "rascunho.txt").write_bytes(RASCUNHO)
    criar = [[sys.executable, "-c", f"open(r'{h / 'novo.txt'}', 'w').write('novo')"]]
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=criar)
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, h, AUTONOMO)

    assert parada.fechou and not pasta.exists() and "salvaguarda" not in parada.mensagem, parada.mensagem
    (avanco,) = _notas_do_humano(bancada, "repositorio_do_humano_avancou")
    assert avanco.obter_propriedade("ver_o_de_antes") == [] and avanco.obter_propriedade("guardada_em") == str(pasta)
    assert (h / "rascunho.txt").read_bytes() == RASCUNHO and (h / "novo.txt").read_text(encoding="utf-8") == "novo"
