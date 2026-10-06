"""Testes do controlador de governança: leitura, escrita, auditoria e liberação de posse."""

from http import HTTPStatus

from graphow.core.governanca import ID_GOVERNANCA_GLOBAL
from graphow.core.types import PapelAutor
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.dto import RequisicaoEdicaoNo, RequisicaoGovernanca, RequisicaoNovoNo
from graphow.web.rest_canvas_controller import CanvasWebController
from graphow.web.rest_governanca_controller import GovernancaWebController


def _montar() -> tuple[WriteKernel, GovernancaWebController]:
    """Um Projeto, um Setor, uma Sessão e uma Task pendurada nela, sobre um kernel em memória."""
    kernel = WriteKernel(InMemoryEventStore())
    canvas = CanvasWebController(kernel)
    requisicoes = (
        RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto 1", id_no="proj-01"),
        RequisicaoNovoNo(tipo="Setor", rotulo="Setor 1", id_no="setor-01", contido_em="proj-01"),
        RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao 1", id_no="sess-01", contido_em="setor-01"),
        RequisicaoNovoNo(tipo="Task", rotulo="Task 1", id_no="task-01", sessao_id="sess-01"),
    )
    for req in requisicoes:
        assert canvas.criar_no(req).sucesso is True
    return kernel, GovernancaWebController(kernel)


def _escrever_como_arbitro(kernel: WriteKernel, id_no: str) -> None:
    """O árbitro registra uma Decision pendurada na sessão: um evento de papel `arbitro` no log."""
    no = {"id": id_no, "tipo": "Decision", "rotulo": "Decisao do arbitro", "propriedades": {}}
    aresta = {"id": f"prod-{id_no}", "origem_id": "sess-01", "destino_id": id_no, "tipo": "produz"}
    dados = DadosPropostaPatch(
        autor="arbitro-1",
        papel=PapelAutor.ARBITRO,
        operacoes=(
            ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=no),
            ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/prod-{id_no}", value=aresta),
        ),
        justificativa="Decisao de teste",
    )
    assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso is True


def test_ler_global_sem_nada_gravado_traz_catalogo_e_governanca_maxima_nominal() -> None:
    """Sem nó global vale a governança máxima, e o catálogo diz gestos, valores e presets."""
    _, governanca = _montar()

    resposta = governanca.obter_global()

    corpo = resposta.corpo
    assert resposta.status == HTTPStatus.OK
    assert corpo["declarada"] is False
    assert corpo["configuracao"] == {"preset": "governanca_maxima", "personalizada": {}}
    assert set(corpo["politica_efetiva"].values()) == {"humano", "estrito", 2}
    gestos = {item["gesto"]: item for item in corpo["catalogo"]["gestos"]}
    assert gestos["estrutura"]["valores"] == ["estrito", "ilimitado"]
    assert gestos["max_correcoes"]["valores"] == [0, 1, 2, 3, 4, 5]
    assert all(item["descricao"] for item in gestos.values())
    presets = {item["preset"]: item for item in corpo["catalogo"]["presets"]}
    assert presets["arbitragem_maxima"]["valores"]["excluir"] == "arbitro"
    assert presets["personalizada"]["fixo"] is False


def test_gravar_global_valido_devolve_a_politica_efetiva_nominal() -> None:
    """A escrita válida cria o nó global e devolve o que passou a valer."""
    kernel, governanca = _montar()

    resposta = governanca.gravar_global(
        RequisicaoGovernanca(preset="personalizada", personalizada={"excluir": "arbitro", "max_correcoes": 4})
    )

    assert resposta.status == HTTPStatus.OK, resposta.corpo
    assert resposta.corpo["politica_efetiva"]["excluir"] == "arbitro"
    assert resposta.corpo["politica_efetiva"]["max_correcoes"] == 4
    assert resposta.corpo["origens"]["excluir"] == "global"
    assert kernel.obter_estado().nos[ID_GOVERNANCA_GLOBAL].propriedades["preset"] == "personalizada"


def test_gravar_global_invalido_recusa_com_os_problemas_edge_case() -> None:
    """Caso de borda: gesto desconhecido e valor fora do domínio voltam como 400, cada um listado."""
    kernel, governanca = _montar()

    resposta = governanca.gravar_global(
        RequisicaoGovernanca(preset="personalizada", personalizada={"excluir": "ninguem", "inventado": "humano"})
    )

    assert resposta.status == HTTPStatus.BAD_REQUEST
    assert resposta.corpo["sucesso"] is False
    assert len(resposta.corpo["problemas"]) == 2
    assert any("excluir" in problema for problema in resposta.corpo["problemas"])
    assert any("inventado" in problema for problema in resposta.corpo["problemas"])
    assert ID_GOVERNANCA_GLOBAL not in kernel.obter_estado().nos


def test_trocar_o_preset_preserva_a_personalizada_e_voltar_a_recupera_nominal() -> None:
    """A personalizada fica guardada ao trocar para um preset fixo, e a política dela volta intacta."""
    _, governanca = _montar()
    governanca.gravar_global(RequisicaoGovernanca(preset="personalizada", personalizada={"excluir": "arbitro"}))

    fixo = governanca.gravar_global(RequisicaoGovernanca(preset="governanca_maxima"))
    volta = governanca.gravar_global(RequisicaoGovernanca(preset="personalizada"))

    assert fixo.corpo["configuracao"]["personalizada"] == {"excluir": "arbitro"}
    assert fixo.corpo["politica_efetiva"]["excluir"] == "humano"
    assert volta.corpo["politica_efetiva"]["excluir"] == "arbitro"


def test_so_a_personalizada_usa_o_preset_salvo_nominal() -> None:
    """O corpo com só a personalizada não troca o preset que já estava guardado."""
    _, governanca = _montar()
    governanca.gravar_global(RequisicaoGovernanca(preset="personalizada", personalizada={"excluir": "arbitro"}))

    resposta = governanca.gravar_global(RequisicaoGovernanca(personalizada={"fechar_goal": "arbitro"}))

    assert resposta.status == HTTPStatus.OK, resposta.corpo
    assert resposta.corpo["configuracao"]["preset"] == "personalizada"
    assert resposta.corpo["configuracao"]["personalizada"] == {"excluir": "arbitro", "fechar_goal": "arbitro"}


def test_gravar_global_sem_campo_nenhum_e_recusado_edge_case() -> None:
    """Caso de borda: um corpo vazio não grava uma configuração que ninguém pediu."""
    _, governanca = _montar()

    resposta = governanca.gravar_global(RequisicaoGovernanca())

    assert resposta.status == HTTPStatus.BAD_REQUEST
    assert resposta.corpo["problemas"]


def test_projeto_herda_e_herdar_por_gesto_apaga_a_sobrescrita_nominal() -> None:
    """A sobrescrita do gesto vale no Projeto, e `herdar` a apaga sem tocar nas outras."""
    _, governanca = _montar()
    governanca.gravar_global(RequisicaoGovernanca(preset="personalizada", personalizada={"excluir": "arbitro"}))

    antes = governanca.obter_projeto("proj-01").corpo
    gravada = governanca.gravar_projeto(
        "proj-01",
        RequisicaoGovernanca(preset="personalizada", personalizada={"excluir": "humano", "fechar_goal": "arbitro"}),
    )
    herdada = governanca.gravar_projeto("proj-01", RequisicaoGovernanca(personalizada={"excluir": "herdar"}))

    assert antes["configuracao"]["preset"] == "herdar"
    assert antes["origens"]["excluir"] == "global"
    assert gravada.corpo["politica_efetiva"]["excluir"] == "humano"
    assert gravada.corpo["origens"]["excluir"] == "projeto"
    assert herdada.corpo["configuracao"]["personalizada"] == {"fechar_goal": "arbitro"}
    assert herdada.corpo["politica_efetiva"]["excluir"] == "arbitro"
    assert herdada.corpo["origens"]["excluir"] == "global"
    assert herdada.corpo["origens"]["fechar_goal"] == "projeto"


def test_projeto_com_preset_fixo_reporta_a_origem_do_preset_nominal() -> None:
    """Um preset fixo no Projeto vale como está, e a origem de cada gesto é o preset."""
    _, governanca = _montar()

    resposta = governanca.gravar_projeto("proj-01", RequisicaoGovernanca(preset="arbitragem_maxima"))

    assert resposta.status == HTTPStatus.OK, resposta.corpo
    assert set(resposta.corpo["origens"].values()) == {"preset:arbitragem_maxima"}
    assert resposta.corpo["politica_efetiva"]["estrutura"] == "ilimitado"


def test_projeto_legado_ilimitado_reporta_a_origem_legada_edge_case() -> None:
    """Caso de borda: o nivel_autonomia ilimitado de antes da política aparece como origem legada."""
    kernel, governanca = _montar()
    canvas = CanvasWebController(kernel)
    assert canvas.editar_no(RequisicaoEdicaoNo(id_no="proj-01", novas_propriedades={"nivel_autonomia": "ilimitado"})).sucesso

    corpo = governanca.obter_projeto("proj-01").corpo

    assert corpo["origens"]["estrutura"] == "legado:nivel_autonomia"
    assert corpo["politica_efetiva"]["estrutura"] == "ilimitado"


def test_operacao_grava_as_propriedades_do_projeto_no_mesmo_lote_nominal() -> None:
    """A política e as propriedades operacionais saem no mesmo lote, sob o preset salvo."""
    kernel, governanca = _montar()
    antes = kernel.obter_estado().versao_log

    resposta = governanca.gravar_projeto(
        "proj-01",
        RequisicaoGovernanca(
            preset="personalizada",
            personalizada={"excluir": "arbitro"},
            operacao={"cadencia": "setor", "teto_rodadas": 8, "ramo_base": "origin/stage", "caminhos_de_colisao": ["db/*"]},
        ),
    )

    assert resposta.status == HTTPStatus.OK, resposta.corpo
    assert resposta.corpo["operacao"] == {
        "cadencia": "setor",
        "teto_rodadas": 8,
        "ramo_base": "origin/stage",
        "caminhos_de_colisao": ["db/*"],
        "gravacao_do_gerente": None,
    }
    leitura = governanca.obter_projeto("proj-01").corpo
    assert leitura["operacao"]["ramo_base"] == "origin/stage"
    assert leitura["politica_efetiva"]["excluir"] == "arbitro"
    assert kernel.obter_estado().versao_log > antes


def test_so_operacao_nao_regrava_a_configuracao_nominal() -> None:
    """O corpo com só `operacao` grava as propriedades e deixa a configuração guardada como estava."""
    kernel, governanca = _montar()
    governanca.gravar_projeto("proj-01", RequisicaoGovernanca(preset="arbitragem_maxima"))
    props_antes = dict(kernel.obter_estado().nos["proj-01"].propriedades)

    resposta = governanca.gravar_projeto("proj-01", RequisicaoGovernanca(operacao={"cadencia": "tarefa"}))

    assert resposta.status == HTTPStatus.OK, resposta.corpo
    propriedades = kernel.obter_estado().nos["proj-01"].propriedades
    assert propriedades["governanca"] == props_antes["governanca"]
    assert propriedades["cadencia"] == "tarefa"
    assert resposta.corpo["configuracao"]["preset"] == "arbitragem_maxima"


def test_operacao_invalida_recusa_o_lote_inteiro_edge_case() -> None:
    """Caso de borda: uma propriedade operacional inválida derruba também a política do mesmo corpo."""
    kernel, governanca = _montar()

    resposta = governanca.gravar_projeto(
        "proj-01",
        RequisicaoGovernanca(
            preset="arbitragem_maxima",
            operacao={"cadencia": "quando_quiser", "teto_rodadas": 0, "inventada": 1},
        ),
    )

    assert resposta.status == HTTPStatus.BAD_REQUEST
    assert len(resposta.corpo["problemas"]) == 3
    assert "governanca" not in kernel.obter_estado().nos["proj-01"].propriedades


def test_operacao_nula_apaga_a_propriedade_nominal() -> None:
    """Valor nulo remove a propriedade operacional; apagar a que não existe não escreve nada."""
    kernel, governanca = _montar()
    governanca.gravar_projeto("proj-01", RequisicaoGovernanca(operacao={"ramo_base": "stage"}))

    apagada = governanca.gravar_projeto("proj-01", RequisicaoGovernanca(operacao={"ramo_base": None, "cadencia": None}))

    assert apagada.status == HTTPStatus.OK, apagada.corpo
    assert "ramo_base" not in kernel.obter_estado().nos["proj-01"].propriedades
    assert apagada.corpo["operacao"]["ramo_base"] is None


def test_gravacao_do_gerente_grava_e_recusa_valor_fora_do_dominio_nominal() -> None:
    """A gravação do gerente aceita os dois modos, e um valor inventado volta com o domínio na recusa."""
    kernel, governanca = _montar()

    gravada = governanca.gravar_projeto("proj-01", RequisicaoGovernanca(operacao={"gravacao_do_gerente": "durante_alinhamento"}))
    recusada = governanca.gravar_projeto("proj-01", RequisicaoGovernanca(operacao={"gravacao_do_gerente": "sempre"}))

    assert gravada.status == HTTPStatus.OK, gravada.corpo
    assert kernel.obter_estado().nos["proj-01"].propriedades["gravacao_do_gerente"] == "durante_alinhamento"
    assert recusada.status == HTTPStatus.BAD_REQUEST
    assert "apos_aprovacao, durante_alinhamento" in recusada.corpo["problemas"][0]


def test_projeto_inexistente_responde_404_edge_case() -> None:
    """Caso de borda: ler ou gravar a governança de um id que não é Projeto é 404, e `task-01` não é Projeto."""
    _, governanca = _montar()

    assert governanca.obter_projeto("nao-existe").status == HTTPStatus.NOT_FOUND
    assert governanca.obter_projeto("task-01").status == HTTPStatus.NOT_FOUND
    assert governanca.gravar_projeto("sess-01", RequisicaoGovernanca(preset="arbitragem_maxima")).status == HTTPStatus.NOT_FOUND


def test_auditoria_traz_so_o_papel_arbitro_mais_recente_primeiro_nominal() -> None:
    """Os eventos do humano ficam de fora; os do árbitro vêm do mais recente ao mais antigo."""
    kernel, governanca = _montar()
    _escrever_como_arbitro(kernel, "dec-a")
    _escrever_como_arbitro(kernel, "dec-b")

    resposta = governanca.obter_auditoria()

    eventos = resposta.corpo["eventos"]
    assert resposta.corpo["total"] == 4
    assert {evento["papel"] for evento in eventos} == {"arbitro"}
    assert {evento["autor"] for evento in eventos} == {"arbitro-1"}
    assert [evento["seq"] for evento in eventos] == sorted((evento["seq"] for evento in eventos), reverse=True)
    assert eventos[0]["ids_tocados"] == ["prod-dec-b", "sess-01", "dec-b"]
    assert eventos[1]["ids_tocados"] == ["dec-b"]
    assert eventos[0]["instante"]
    assert "justificativa" in eventos[0]


def test_auditoria_respeita_o_limite_e_o_piso_edge_case() -> None:
    """Caso de borda: o limite corta os mais antigos, e um limite zero ou negativo vira um evento."""
    kernel, governanca = _montar()
    _escrever_como_arbitro(kernel, "dec-a")
    _escrever_como_arbitro(kernel, "dec-b")

    assert len(governanca.obter_auditoria(limite=2).corpo["eventos"]) == 2
    assert len(governanca.obter_auditoria(limite=0).corpo["eventos"]) == 1
    assert governanca.obter_auditoria(limite=2).corpo["total"] == 4


def test_auditoria_sem_arbitro_e_vazia_edge_case() -> None:
    """Caso de borda: sem escrita do árbitro a lista é vazia, e o humano não aparece."""
    _, governanca = _montar()

    corpo = governanca.obter_auditoria().corpo

    assert corpo["eventos"] == []
    assert corpo["total"] == 0


def test_liberar_posse_de_qualquer_dono_nominal() -> None:
    """O humano libera o lock de um subagente que não voltou, e a Task fica livre para outro."""
    kernel, governanca = _montar()
    assert kernel.adquirir_lock_task("task-01", "executor-sonnet#abc") is True

    resposta = governanca.liberar_posse("task-01")

    assert resposta.status == HTTPStatus.OK, resposta.corpo
    assert resposta.corpo["dono_anterior"] == "executor-sonnet#abc"
    assert kernel.obter_dono_do_lock("task-01") is None
    assert kernel.adquirir_lock_task("task-01", "outro#1") is True


def test_liberar_posse_sem_dono_e_conflito_e_sem_task_e_404_edge_case() -> None:
    """Caso de borda: Task livre é 409, e um id que não é Task é 404."""
    _, governanca = _montar()

    assert governanca.liberar_posse("task-01").status == HTTPStatus.CONFLICT
    assert governanca.liberar_posse("sess-01").status == HTTPStatus.NOT_FOUND
    assert governanca.liberar_posse("nao-existe").status == HTTPStatus.NOT_FOUND
