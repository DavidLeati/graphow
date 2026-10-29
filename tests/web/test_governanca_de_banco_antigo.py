"""Nota de migração da fase 3: um banco gravado antes do T3h abre na tela de configurações.

O gesto `integracao` saiu da política de governança. O banco antigo guarda o
gesto na `personalizada` global e na do Projeto. Os eventos daqui são os que
o kernel de antes escrevia, copiados de um banco montado com aquele código. Eles
entram crus num SQLite, sem passar pelos portões de hoje, que os recusariam.
"""

from http import HTTPStatus
from pathlib import Path
from typing import Any

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import PapelAutor
from graphow.kernel.composicao import abrir_kernel_sqlite
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.sqlite_store import SQLiteEventStore
from graphow.web.dto import RequisicaoGovernanca
from graphow.web.rest_governanca_controller import GovernancaWebController

GESTO_QUE_SAIU: str = "integracao"

EVENTOS_ANTIGOS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("no_criado", {"id": "proj-antigo", "propriedades": {}, "rotulo": "Projeto antigo", "tipo": "Projeto"}),
    ("no_criado", {"id": "setor-antigo", "propriedades": {}, "rotulo": "Setor antigo", "tipo": "Setor"}),
    ("aresta_criada", {"destino_id": "setor-antigo", "id": "cont-setor-antigo", "origem_id": "proj-antigo", "tipo": "contem"}),
    ("no_criado", {"id": "sess-antiga", "propriedades": {}, "rotulo": "Sessao antiga", "tipo": "Sessao"}),
    ("aresta_criada", {"destino_id": "sess-antiga", "id": "cont-sess-antiga", "origem_id": "setor-antigo", "tipo": "contem"}),
    ("no_criado", {"id": "goal-antigo", "propriedades": {}, "rotulo": "Goal antigo", "tipo": "Goal"}),
    ("aresta_criada", {"destino_id": "goal-antigo", "id": "prod-goal-antigo", "origem_id": "sess-antiga", "tipo": "produz"}),
    (
        "no_criado",
        {
            "id": "governanca-global",
            "propriedades": {"personalizada": {"excluir": "arbitro", GESTO_QUE_SAIU: "arbitro"}, "preset": "personalizada"},
            "rotulo": "Governanca global",
            "tipo": "Governanca",
        },
    ),
    (
        "no_atualizado",
        {
            "id": "proj-antigo",
            "propriedades": {
                "governanca": {"personalizada": {"fechar_goal": "arbitro", GESTO_QUE_SAIU: "humano"}, "preset": "personalizada"}
            },
        },
    ),
    ("no_atualizado", {"id": "proj-antigo", "propriedades": {"ramo_base": "origin/stage"}}),
    ("no_atualizado", {"id": "proj-antigo", "propriedades": {"caminhos_de_colisao": ["**/migrations/*.py"]}}),
    ("no_atualizado", {"id": "proj-antigo", "propriedades": {"gravacao_do_gerente": "durante_alinhamento"}}),
    ("no_atualizado", {"id": "goal-antigo", "propriedades": {"ramo_base": "main"}}),
    ("no_atualizado", {"id": "setor-antigo", "propriedades": {"caminhos_de_colisao": ["db/*.sql"]}}),
)


def _gravar_banco_antigo(caminho: Path) -> None:
    """Escreve os eventos antigos direto no SQLite, como o kernel de antes os deixou."""
    store = SQLiteEventStore(caminho)
    eventos = [
        EventoLog.criar(
            DadosCriacaoEvento(
                seq=seq,
                autor="humano-antigo",
                papel=PapelAutor.HUMANO,
                tipo_evento=TipoEvento(tipo),
                payload=payload,
            )
        )
        for seq, (tipo, payload) in enumerate(EVENTOS_ANTIGOS, start=1)
    ]
    store.append_eventos(eventos)
    store.fechar()


def _abrir(tmp_path: Path) -> tuple[SQLiteEventStore, WriteKernel, GovernancaWebController]:
    """O banco antigo reaberto pelo código de hoje, com o kernel e o controlador da tela."""
    caminho = tmp_path / "antigo.db"
    _gravar_banco_antigo(caminho)
    store, kernel = abrir_kernel_sqlite(caminho)
    return store, kernel, GovernancaWebController(kernel)


def _personalizada_no_log(kernel: WriteKernel) -> tuple[dict[str, Any], dict[str, Any]]:
    """A `personalizada` global e a do Projeto como o replay as deixa, sem filtro nenhum."""
    nos = kernel.obter_estado().nos
    return dict(nos["governanca-global"].propriedades["personalizada"]), dict(
        nos["proj-antigo"].propriedades["governanca"]["personalizada"]
    )


def test_politica_antiga_faz_replay_e_abre_na_tela_nominal(tmp_path: Path) -> None:
    """A política com o gesto que saiu faz replay e abre: o gesto fica no log, a tela não o lê."""
    store, kernel, governanca = _abrir(tmp_path)
    try:
        global_ = governanca.obter_global()
        projeto = governanca.obter_projeto("proj-antigo")
        no_log = _personalizada_no_log(kernel)
    finally:
        store.fechar()

    assert (no_log[0][GESTO_QUE_SAIU], no_log[1][GESTO_QUE_SAIU]) == ("arbitro", "humano")
    assert global_.status == HTTPStatus.OK, global_.corpo
    assert global_.corpo["versao_log"] == len(EVENTOS_ANTIGOS)
    assert global_.corpo["configuracao"] == {"preset": "personalizada", "personalizada": {"excluir": "arbitro"}}
    assert global_.corpo["politica_efetiva"]["excluir"] == "arbitro"
    assert GESTO_QUE_SAIU not in global_.corpo["politica_efetiva"]
    assert GESTO_QUE_SAIU not in [item["gesto"] for item in global_.corpo["catalogo"]["gestos"]]
    assert projeto.status == HTTPStatus.OK, projeto.corpo
    assert projeto.corpo["configuracao"]["personalizada"] == {"fechar_goal": "arbitro"}
    assert projeto.corpo["politica_efetiva"]["fechar_goal"] == "arbitro"
    assert GESTO_QUE_SAIU not in projeto.corpo["origens"]


def test_gravar_por_cima_da_politica_antiga_tira_o_gesto_que_saiu_edge_case(tmp_path: Path) -> None:
    """Caso de borda: mudar um gesto na tela não tropeça no que saiu, e a gravação o tira da personalizada."""
    store, kernel, governanca = _abrir(tmp_path)
    try:
        global_ = governanca.gravar_global(RequisicaoGovernanca(personalizada={"responder_questao": "arbitro"}))
        projeto = governanca.gravar_projeto("proj-antigo", RequisicaoGovernanca(personalizada={"excluir": "arbitro"}))
        no_log = _personalizada_no_log(kernel)
    finally:
        store.fechar()

    assert global_.status == HTTPStatus.OK, global_.corpo
    assert projeto.status == HTTPStatus.OK, projeto.corpo
    assert no_log == ({"excluir": "arbitro", "responder_questao": "arbitro"}, {"fechar_goal": "arbitro", "excluir": "arbitro"})
