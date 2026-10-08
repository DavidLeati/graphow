"""A anonimização recorta por Goal, descarta o texto e mantém a forma do log."""

import json
from typing import Any

from graphow.avaliacao.anonimizacao_log import anonimizar_eventos


def _linha(seq: int, tipo: str, payload: dict[str, Any], autor: str = "pessoa", papel: str = "humano") -> dict[str, Any]:
    """Linha no formato da tabela `eventos`."""
    return {
        "id": f"e{seq}", "seq": seq, "timestamp_utc": f"2026-01-01T00:00:{seq:02d}+00:00",
        "autor": autor, "papel": papel, "origem": "humano", "tipo_evento": tipo,
        "payload_json": json.dumps(payload), "versao_ontologia": "1.4.0",
    }


def _no(seq: int, id_no: str, tipo: str, **propriedades: Any) -> dict[str, Any]:
    """Evento de criação de nó com rótulo de texto livre."""
    return _linha(seq, "no_criado", {"id": id_no, "tipo": tipo, "rotulo": "Texto Sigiloso", "propriedades": propriedades})


def _aresta(seq: int, origem: str, destino: str, tipo: str) -> dict[str, Any]:
    """Evento de criação de aresta."""
    return _linha(seq, "aresta_criada", {"id": f"{origem}>{destino}", "origem_id": origem, "destino_id": destino, "tipo": tipo})


def _cenario() -> list[dict[str, Any]]:
    """Goal com 3 Tasks, uma Evidence ligada, um Goal pequeno de fora e uma Evidence solta."""
    linhas = [_no(1, "g-grande", "Goal"), _no(2, "g-pequeno", "Goal"), _no(3, "e-solta", "Evidence")]
    for i in range(3):
        linhas += [_no(10 + i, f"t{i}", "Task", status="pendente", descricao="Texto Sigiloso", arquivos_alvo=["a", "b"])]
        linhas += [_aresta(20 + i, "g-grande", f"t{i}", "decompoe")]
    linhas += [_no(30, "t-fora", "Task"), _aresta(31, "g-pequeno", "t-fora", "decompoe")]
    linhas += [_no(32, "ev", "Evidence", veredito="rejeitado", resultado="Texto Sigiloso"), _aresta(33, "ev", "t0", "deriva_de")]
    return linhas


def test_recorte_guarda_so_o_goal_com_tres_tasks_e_a_vizinhanca() -> None:
    """Goal pequeno, sua Task e a Evidence solta ficam de fora."""
    saida = anonimizar_eventos(_cenario())
    criados = [e for e in saida if e["tipo_evento"] == "no_criado"]

    assert sorted(e["payload"]["tipo"] for e in criados) == ["Evidence", "Goal", "Task", "Task", "Task"]
    assert not any("Sigiloso" in json.dumps(e) for e in saida)
    assert not any(k in e["payload"] for e in saida for k in ("rotulo", "descricao"))


def test_arestas_so_entram_com_as_duas_pontas() -> None:
    """Toda aresta do corpus liga dois nós criados no corpus."""
    saida = anonimizar_eventos(_cenario())
    nos = {e["payload"]["id"] for e in saida if e["tipo_evento"] == "no_criado"}
    arestas = [e["payload"] for e in saida if e["tipo_evento"] == "aresta_criada"]

    assert len(arestas) == 4
    assert all(a["origem_id"] in nos and a["destino_id"] in nos for a in arestas)


def test_propriedades_viram_forma_sem_conteudo() -> None:
    """Categóricas ficam, listas viram contagem, texto vira presença."""
    saida = anonimizar_eventos(_cenario())
    task = next(e for e in saida if e["payload"].get("tipo") == "Task")

    assert task["payload"]["propriedades"] == {"status": "pendente", "n_arquivos_alvo": 2, "tem_descricao": True}
    evidencia = next(e for e in saida if e["payload"].get("tipo") == "Evidence")
    assert evidencia["payload"]["propriedades"] == {"veredito": "rejeitado"}


def test_atualizacao_so_de_posicao_e_descartada_edge_case() -> None:
    """Caso de borda: mover o nó no canvas não deixa rastro, mas a mudança de status sim."""
    linhas = _cenario() + [
        _linha(40, "no_atualizado", {"id": "t0", "propriedades": {"pos_x": 1, "pos_y": 2}}),
        _linha(41, "no_atualizado", {"id": "t0", "propriedades": {"pos_x": 3, "status": "em_andamento", "assumida_por": "agente-x"}}),
    ]
    saida = [e for e in anonimizar_eventos(linhas) if e["tipo_evento"] == "no_atualizado"]

    assert [e["seq"] for e in saida] == [41]
    assert saida[0]["payload"]["propriedades"] == {"status": "em_andamento", "assumida_por": "agente-1"}


def test_autores_viram_rotulos_e_preservam_o_papel() -> None:
    """Humano e agente ganham rótulos numerados; o papel segue no evento."""
    linhas = _cenario() + [_linha(50, "no_atualizado", {"id": "t1", "propriedades": {"status": "concluido"}}, "exec-9", "executor")]
    saida = anonimizar_eventos(linhas)

    assert {(e["autor"], e["papel"]) for e in saida} == {("humano-1", "humano"), ("agente-1", "executor")}
