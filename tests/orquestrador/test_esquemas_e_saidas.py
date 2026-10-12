"""Os schemas dos papéis, a validação em código e a conferência de sentido de cada saída."""

import copy
import json
from pathlib import Path
import tomllib
from typing import Any

import pytest

from graphow.orquestrador.esquemas import (
    ESQUEMA_DA_EXECUCAO,
    ESQUEMA_DA_VERIFICACAO,
    ESQUEMA_DO_PLANO,
    LIMITE_DO_PROMPT_BYTES,
    PAPEIS,
    caminho_do_prompt,
)
from graphow.orquestrador.comandos_do_stream import chamadas_bash
from graphow.orquestrador.saida_do_verificador import Verificacao, conferir_verificacao
from graphow.orquestrador.saidas import (
    IdsFixados,
    Plano,
    SaidaDoExecutor,
    conferir_plano,
)
from graphow.orquestrador.validacao_json import validar_contra_esquema

RAIZ: Path = Path(__file__).resolve().parents[2]

PLANO: dict[str, Any] = {
    "titulo": "Soma de dois numeros",
    "comando_suite": "python -m pytest -q",
    "criterios": [
        {"id": "C1", "texto": "somar(2, 3) devolve 5", "verificacao": "teste"},
        {"id": "C2", "texto": "o README explica o uso", "verificacao": "checagem"},
    ],
    "decisoes": [{"id": "D1", "texto": "so a biblioteca padrao", "motivo": "o pacote nao tem dependencia"}],
    "fatias": [
        {"id": "F1", "titulo": "Funcao", "objetivo": "somar com teste", "criterios": ["C1"], "arquivos": ["soma.py"],
         "depende_de": [], "modelo": "opus"},
        {"id": "F2", "titulo": "Uso", "objetivo": "README", "criterios": ["C2"], "arquivos": ["README.md"],
         "depende_de": ["F1"], "modelo": "sonnet"},
    ],
    "marcos": [{"id": "M1", "titulo": "Soma e uso", "fatias": ["F1", "F2"]}],
}
VERIFICACAO: dict[str, Any] = {
    "resumo": "suite verde, programa rodado",
    "criterios": [{"id": "C1", "veredito": "atende", "prova": "pytest 2 passed"},
                  {"id": "C2", "veredito": "parcial", "prova": "README sem exemplo"}],
    "decisoes": [{"id": "D1", "veredito": "atende", "prova": "sem import externo"}],
    "achados": [{"titulo": "nome", "descricao": "renomear", "prova": "soma.py:1 lido, nome generico", "local": "soma.py:1",
                 "criterios": [], "decisoes": [], "severidade": "baixa"}],
}


def _plano(**trocas: Any) -> dict[str, Any]:
    """O plano de exemplo com campos trocados."""
    return {**copy.deepcopy(PLANO), **trocas}


def test_saidas_bem_formadas_conferem_com_os_schemas_nominal() -> None:
    """O plano, a execução e a verificação de exemplo passam pela validação em código."""
    execucao = {"status": "pronto", "resumo": "feito", "arquivos": ["soma.py"], "testes": ["pytest: 2 passed"], "duvida": ""}

    assert validar_contra_esquema(PLANO, ESQUEMA_DO_PLANO) == ()
    assert validar_contra_esquema(execucao, ESQUEMA_DA_EXECUCAO) == ()
    assert validar_contra_esquema(VERIFICACAO, ESQUEMA_DA_VERIFICACAO) == ()
    assert conferir_plano(Plano.de_json(PLANO), IdsFixados()) == ()


@pytest.mark.parametrize(
    ("valor", "trecho"),
    [
        (_plano(titulo=""), "$.titulo: texto vazio"),
        ({k: v for k, v in PLANO.items() if k != "fatias"}, "falta 'fatias'"),
        (_plano(extra=1), "campo nao previsto 'extra'"),
        (_plano(fatias=[]), "precisa de ao menos 1"),
        (_plano(criterios=[{"id": "C1", "texto": "x", "verificacao": "olhar"}]), "fora de"),
        (_plano(titulo=True), "veio booleano"),
    ],
)
def test_validacao_aponta_o_caminho_do_problema_edge_case(valor: dict[str, Any], trecho: str) -> None:
    """Caso de borda: cada desvio do schema volta com o caminho, para a sessão corrigir."""
    problemas = validar_contra_esquema(valor, ESQUEMA_DO_PLANO)

    assert any(trecho in problema for problema in problemas), problemas


def test_plano_sem_sentido_e_recusado_com_o_motivo_edge_case() -> None:
    """Caso de borda: critério sem fatia, dependência desconhecida, critério inexistente e fixado que sumiu."""
    fatias = copy.deepcopy(PLANO["fatias"])
    fatias[1]["criterios"] = ["C9"]
    fatias[1]["depende_de"] = ["F7"]

    problemas = conferir_plano(Plano.de_json(_plano(fatias=fatias)), IdsFixados(criterios=("C3",)))

    assert "o criterio C2 nao e coberto por nenhuma fatia" in problemas
    assert "a fatia F2 cita o criterio C9, que nao existe" in problemas
    assert "a fatia F2 depende de F7, que nao e fatia do plano" in problemas
    assert "o criterio fixado C3 sumiu do plano" in problemas


def test_dependencia_em_ciclo_e_recusada_edge_case() -> None:
    """Caso de borda: F1 depende de F2 e F2 de F1 não tem ordem possível."""
    fatias = copy.deepcopy(PLANO["fatias"])
    fatias[0]["depende_de"] = ["F2"]

    problemas = conferir_plano(Plano.de_json(_plano(fatias=fatias)), IdsFixados())

    assert problemas == ("as fatias F1, F2 dependem umas das outras em ciclo",)


def test_duvida_sem_pergunta_e_recusada_edge_case() -> None:
    """Caso de borda: o status de dúvida precisa da pergunta, ou o humano não teria o que responder."""
    saida = SaidaDoExecutor.de_json({"status": "duvida", "resumo": "parei", "arquivos": [], "testes": [], "duvida": " "})

    assert saida.conferir() == ("status duvida sem a pergunta em 'duvida'",)


def test_criterio_parcial_sem_achado_vira_bloqueante_nominal() -> None:
    """O parecer que não atende é bloqueante mesmo que o verificador não o tenha listado como achado."""
    verificacao = Verificacao.de_json(VERIFICACAO)

    bloqueantes = verificacao.bloqueantes()

    assert [(achado.titulo, achado.criterios) for achado in bloqueantes] == [("C2 parcial", ("C2",))]
    assert [achado.titulo for achado in verificacao.acompanhamentos()] == ["nome"]


def test_verificacao_sem_parecer_de_um_criterio_e_recusada_edge_case() -> None:
    """Caso de borda: o verificador que pulou um critério ou citou um id que não existe devolve de novo."""
    dados = copy.deepcopy(VERIFICACAO)
    dados["criterios"] = dados["criterios"][:1]
    dados["achados"][0]["criterios"] = ["C7"]

    problemas = conferir_verificacao(Verificacao.de_json(dados), ("C1", "C2"), ("D1",))

    assert "falta o parecer do criterio C2" in problemas
    assert "o achado 'nome' toca C7, que nao e criterio nem decisao desta verificacao" in problemas


@pytest.mark.parametrize(
    ("trocas", "trecho"),
    [
        ({"criterios": [{"id": "C1", "veredito": "atende", "prova": "."}]}, "$.criterios[0].prova"),
        ({"comandos": [{"comando": "pytest", "codigo": 0, "saida": "ok"}]}, "$: campo nao previsto 'comandos'"),
    ],
)
def test_verificacao_com_prova_vazia_ou_que_declara_comandos_nao_confere_edge_case(trocas: dict[str, Any], trecho: str) -> None:
    """Caso de borda: a prova "." volta, e o verificador não declara mais `comandos`: eles vêm do stream (F)."""
    problemas = validar_contra_esquema({**copy.deepcopy(VERIFICACAO), **trocas}, ESQUEMA_DA_VERIFICACAO)

    assert any(problema.startswith(trecho) for problema in problemas), problemas


def test_prova_curta_diz_que_e_curta_e_nao_vazia_edge_case() -> None:
    """Caso de borda: a prova "." não é vazia; o problema diz o tamanho que falta."""
    dados = {**copy.deepcopy(VERIFICACAO), "criterios": [{"id": "C1", "veredito": "atende", "prova": "."}]}

    problemas = validar_contra_esquema(dados, ESQUEMA_DA_VERIFICACAO)

    assert "$.criterios[0].prova: texto curto demais (1 caractere(s); o minimo e 10)" in problemas


def test_chamadas_bash_saem_do_stream_com_o_codigo_e_o_trecho_da_saida_nominal(tmp_path: Path) -> None:
    """F: o comando, o código (do `Exit code N` do erro; zero sem erro) e o fim da saída de cada chamada Bash do stream."""
    stream = tmp_path / "verificador.jsonl"
    chamadas = [{"type": "tool_use", "id": f"t{n}", "name": "Bash", "input": {"command": c}}
                for n, c in enumerate(("python -m unittest", "python cli.py media"))]
    resultados = [{"type": "tool_result", "tool_use_id": "t0", "content": "Ran 3 tests\r\nOK", "is_error": False},
                  {"type": "tool_result", "tool_use_id": "t1", "content": "Exit code 2\nlista vazia", "is_error": True}]
    linhas = [{"type": "assistant", "message": {"content": chamadas}}, {"type": "user", "message": {"content": resultados}}]
    stream.write_text("\n".join(json.dumps(linha) for linha in linhas) + "\n", encoding="utf-8")

    lidas = chamadas_bash([stream])

    assert [(c.comando, c.codigo, c.saida) for c in lidas] == [("python -m unittest", 0, "Ran 3 tests\nOK"),
                                                               ("python cli.py media", 2, "lista vazia")]


@pytest.mark.parametrize("papel", PAPEIS)
def test_prompt_de_cada_papel_mora_no_pacote_e_cabe_em_5_kb_nominal(papel: str) -> None:
    """F1.4: o prompt de papel vai da pasta do pacote à sessão, e cada um fica abaixo de 5 KB."""
    caminho = caminho_do_prompt(papel)

    assert caminho.is_file()
    assert caminho.stat().st_size < LIMITE_DO_PROMPT_BYTES


def test_prompts_entram_no_pacote_instalado_edge_case() -> None:
    """Caso de borda: sem package-data, a instalação não editável perderia os prompts."""
    configuracao = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))

    assert "prompts/*.md" in configuracao["tool"]["setuptools"]["package-data"]["graphow.orquestrador"]
