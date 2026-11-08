"""O apoio dos testes do laço com duas sessões ao mesmo tempo.

As fatias em paralelo vão rodar dois executores em threads. A telemetria da
bancada numa conexão `:memory:` presa à thread que a abriu dava
`ProgrammingError` na primeira escrita de outra thread. O claude falso lia e
regravava o estado do roteiro sem trava, numerava o registro sem `O_EXCL` e
servia a lista do papel na ordem de chegada, que com duas sessões não é a
ordem de ninguém.
"""

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from graphow.storage.telemetria_de_sessoes import SessaoRegistrada

from tests.orquestrador.apoio_laco import CLAUDE_ROTEIRIZADO, montar_bancada

DORMIR_S: float = 1.2
PRAZO_CURTO_S: float = 2.0
# O que a partida do Python e o fim do processo levam, com a máquina carregada.
FOLGA_S: float = 30.0
PRAZO_DO_PROCESSO_S: float = 120.0


def test_a_telemetria_da_bancada_aceita_a_escrita_de_outra_thread(tmp_path: Path) -> None:
    """A conexão de teste da telemetria é aberta para outras threads."""
    bancada = montar_bancada(tmp_path, {})
    with ThreadPoolExecutor(max_workers=1) as pool:
        id_linha = pool.submit(bancada.telemetria.registrar, SessaoRegistrada(id_goal="goal-soma", papel="executor")).result()
    assert [registro.id_linha for registro in bancada.telemetria.listar("goal-soma")] == [id_linha]


def _ambiente(tmp_path: Path, roteiro: Mapping[str, Any]) -> dict[str, str]:
    caminho = tmp_path / "roteiro.json"
    caminho.write_text(json.dumps(roteiro), encoding="utf-8")
    return {**os.environ, "GRAPHOW_TESTE_ROTEIRO": str(caminho), "GRAPHOW_TESTE_REGISTRO": str(tmp_path / "registro")}


def _rodar(ambiente: Mapping[str, str], pasta: Path, codigo: str) -> tuple[dict[str, Any], float]:
    """Uma invocação do falso como executor da fatia dada: o evento `result` do stream e quanto ela levou."""
    pasta.mkdir(parents=True, exist_ok=True)
    briefing = f"# Fatia {codigo} do Goal goal-1: titulo\nSessao 1 desta fatia.\n"
    inicio = time.monotonic()
    feito = subprocess.run(
        [sys.executable, str(CLAUDE_ROTEIRIZADO), "--append-system-prompt-file", "executor.md"],
        input=briefing.encode("utf-8"), capture_output=True, env=dict(ambiente), cwd=pasta,
        timeout=PRAZO_DO_PROCESSO_S, check=False,
    )
    duracao = time.monotonic() - inicio
    eventos = [json.loads(linha) for linha in feito.stdout.decode("utf-8").splitlines() if linha.strip()]
    return next(evento for evento in eventos if evento["type"] == "result"), duracao


def _em_paralelo(ambiente: Mapping[str, str], tmp_path: Path, codigos: list[str]) -> list[tuple[dict[str, Any], float]]:
    with ThreadPoolExecutor(max_workers=len(codigos)) as pool:
        return list(pool.map(lambda codigo: _rodar(ambiente, tmp_path / codigo, codigo), codigos))


def _resposta(nome: str, **campos: Any) -> dict[str, Any]:
    return {"saida": {"status": "pronto", "resumo": nome}, "arquivos": {f"{nome}.txt": nome}, **campos}


def _registros(tmp_path: Path) -> list[dict[str, Any]]:
    return [json.loads(arquivo.read_text(encoding="utf-8")) for arquivo in sorted((tmp_path / "registro").glob("*.json"))]


def test_dois_falsos_ao_mesmo_tempo_pegam_a_resposta_da_fatia_e_se_encontram(tmp_path: Path) -> None:
    """T3i1.2: cada sessão responde a da sua fatia, as duas se encontram, e o registro tem as duas."""
    roteiro = {"executor": {codigo: [_resposta(codigo, encontro="lote", dormir=DORMIR_S)] for codigo in ("F1", "F2")}}
    feitos = _em_paralelo(_ambiente(tmp_path, roteiro), tmp_path, ["F2", "F1"])
    assert [resultado["structured_output"]["resumo"] for resultado, _ in feitos] == ["F2", "F1"]
    assert [resultado["is_error"] for resultado, _ in feitos] == [False, False]
    assert all(duracao >= DORMIR_S for _, duracao in feitos)
    assert [(tmp_path / codigo / f"{codigo}.txt").read_text(encoding="utf-8") for codigo in ("F1", "F2")] == ["F1", "F2"]
    registros = _registros(tmp_path)
    assert sorted(Path(registro["cwd"]).name for registro in registros) == ["F1", "F2"]
    assert [registro["encontro"]["encontrou"] for registro in registros] == [True, True]


def test_dois_falsos_ao_mesmo_tempo_com_a_lista_de_hoje_pegam_respostas_diferentes(tmp_path: Path) -> None:
    """Sem roteiro por fatia, a lista do papel vale na ordem de hoje, e as duas sessões não pegam a mesma."""
    roteiro = {"executor": [_resposta("primeira", encontro="lote"), _resposta("segunda", encontro="lote")]}
    feitos = _em_paralelo(_ambiente(tmp_path, roteiro), tmp_path, ["F1", "F2"])
    assert sorted(resultado["structured_output"]["resumo"] for resultado, _ in feitos) == ["primeira", "segunda"]
    assert len(_registros(tmp_path)) == 2


def test_sem_a_outra_sessao_o_encontro_responde_erro_dentro_do_prazo_edge_case(tmp_path: Path) -> None:
    """Contraprova: sozinha, a sessão espera o prazo do encontro e responde erro, sem fazer o trabalho."""
    roteiro = {"executor": {"F1": [_resposta("F1", encontro={"nome": "lote", "prazo": PRAZO_CURTO_S})]}}
    resultado, duracao = _rodar(_ambiente(tmp_path, roteiro), tmp_path / "F1", "F1")
    assert resultado["is_error"] and resultado["result"].startswith("encontro lote: 1 de 2 sessoes")
    assert "structured_output" not in resultado
    assert PRAZO_CURTO_S <= duracao < PRAZO_CURTO_S + FOLGA_S
    assert not (tmp_path / "F1" / "F1.txt").exists()
    assert _registros(tmp_path)[0]["encontro"]["encontrou"] is False
