"""Testes das rotas HTTP da governança, pelo servidor real: leitura, escrita, auditoria e posse."""

from collections.abc import Iterator
from contextlib import contextmanager
import json
import socket
import time
from typing import Any
import urllib.error
import urllib.request

from graphow.core.types import PapelAutor
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.server import EnderecoServidor, GraphowWebServer
from tests.web.cliente_http import cabecalhos_de_escrita

Resposta = tuple[int, dict[str, Any]]


def _obter_porta_livre() -> int:
    """Encontra uma porta TCP livre no localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def _servidor() -> Iterator[tuple[str, WriteKernel]]:
    """Sobe o servidor sobre um kernel em memória e devolve a URL base e o kernel."""
    kernel = WriteKernel(InMemoryEventStore())
    porta = _obter_porta_livre()
    servidor = GraphowWebServer(kernel, EnderecoServidor(porta=porta))
    servidor.iniciar(bloqueante=False)
    time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{porta}", kernel
    finally:
        servidor.parar()


def _chamar(metodo: str, url: str, corpo: dict[str, Any] | None = None, *, com_token: bool = True) -> Resposta:
    """Chama a rota com JSON, devolvendo status e corpo mesmo nas recusas."""
    cabecalhos = cabecalhos_de_escrita(url) if com_token else {"Content-Type": "application/json"}
    dados = json.dumps(corpo if corpo is not None else {}).encode("utf-8") if metodo != "GET" else None
    requisicao = urllib.request.Request(url, data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(requisicao) as resposta:
            return resposta.status, json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read().decode("utf-8"))


def _montar_hierarquia(base_url: str) -> None:
    """Um Projeto, um Setor, uma Sessão e uma Task pela própria API."""
    nos = (
        {"tipo": "Projeto", "rotulo": "Projeto HTTP", "id_no": "p-http"},
        {"tipo": "Setor", "rotulo": "Setor HTTP", "id_no": "s-http", "contido_em": "p-http"},
        {"tipo": "Sessao", "rotulo": "Sessao HTTP", "id_no": "sess-http", "contido_em": "s-http"},
        {"tipo": "Task", "rotulo": "Task HTTP", "id_no": "task-http", "sessao_id": "sess-http"},
    )
    for corpo in nos:
        status, recibo = _chamar("POST", f"{base_url}/api/nodes", corpo)
        assert status == 201 and recibo["sucesso"] is True, recibo


def _arbitro_escreve(kernel: WriteKernel) -> None:
    """O árbitro registra uma Decision pendurada na sessão: eventos de papel `arbitro` no log."""
    no = {"id": "dec-arb", "tipo": "Decision", "rotulo": "Decisao do arbitro", "propriedades": {}}
    aresta = {"id": "prod-dec-arb", "origem_id": "sess-http", "destino_id": "dec-arb", "tipo": "produz"}
    dados = DadosPropostaPatch(
        autor="arbitro-1",
        papel=PapelAutor.ARBITRO,
        operacoes=(
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/dec-arb", value=no),
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/prod-dec-arb", value=aresta),
        ),
        justificativa="Decisao de teste",
    )
    assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso is True


def test_ler_a_governanca_global_pelo_servidor_nominal() -> None:
    """O GET traz o catálogo, a configuração guardada e a política global efetiva."""
    with _servidor() as (base_url, _):
        status, corpo = _chamar("GET", f"{base_url}/api/governanca")

    assert status == 200 and corpo["sucesso"] is True
    assert corpo["configuracao"]["preset"] == "governanca_maxima"
    assert corpo["politica_efetiva"]["excluir"] == "humano"
    assert {item["gesto"] for item in corpo["catalogo"]["gestos"]} >= {"excluir", "max_correcoes", "estrutura"}
    assert [item["preset"] for item in corpo["catalogo"]["presets"]] == [
        "governanca_maxima",
        "arbitragem_maxima",
        "personalizada",
    ]


def test_gravar_a_governanca_global_pelo_servidor_nominal() -> None:
    """O PUT grava a política, e o GET seguinte a lê de volta."""
    with _servidor() as (base_url, _):
        status, recibo = _chamar(
            "PUT",
            f"{base_url}/api/governanca/global",
            {"preset": "personalizada", "personalizada": {"excluir": "arbitro"}},
        )
        _, lido = _chamar("GET", f"{base_url}/api/governanca")

    assert status == 200 and recibo["sucesso"] is True, recibo
    assert recibo["politica_efetiva"]["excluir"] == "arbitro"
    assert lido["configuracao"] == {"preset": "personalizada", "personalizada": {"excluir": "arbitro"}}
    assert lido["declarada"] is True


def test_escrita_invalida_responde_400_com_os_problemas_edge_case() -> None:
    """Caso de borda: valor fora do domínio e campo desconhecido voltam como 400, com cada problema."""
    with _servidor() as (base_url, _):
        status, invalido = _chamar(
            "PUT",
            f"{base_url}/api/governanca/global",
            {"preset": "personalizada", "personalizada": {"excluir": "ninguem"}},
        )
        status_campo, campo = _chamar("PUT", f"{base_url}/api/governanca/global", {"preset": "governanca_maxima", "x": 1})
        status_vazio, vazio = _chamar("PUT", f"{base_url}/api/governanca/global", {})
        _, lido = _chamar("GET", f"{base_url}/api/governanca")

    assert status == 400 and invalido["sucesso"] is False
    assert len(invalido["problemas"]) == 1 and "excluir" in invalido["problemas"][0]
    assert status_campo == 400 and "x" in campo["problemas"][0]
    assert status_vazio == 400 and vazio["problemas"]
    assert lido["declarada"] is False


def test_escrita_sem_token_e_recusada_e_nao_grava_edge_case() -> None:
    """Caso de borda: sem o token da sessão nenhuma das três escritas passa, e nada é gravado."""
    with _servidor() as (base_url, kernel):
        _montar_hierarquia(base_url)
        kernel.adquirir_lock_task("task-http", "executor#1")
        versao = kernel.obter_estado().versao_log
        global_ = _chamar("PUT", f"{base_url}/api/governanca/global", {"preset": "arbitragem_maxima"}, com_token=False)
        projeto = _chamar("PUT", f"{base_url}/api/projetos/p-http/governanca", {"preset": "arbitragem_maxima"}, com_token=False)
        posse = _chamar("POST", f"{base_url}/api/tarefas/task-http/liberar-posse", {}, com_token=False)
        dono = kernel.obter_dono_do_lock("task-http")
        versao_depois = kernel.obter_estado().versao_log

    assert (global_[0], projeto[0], posse[0]) == (403, 403, 403)
    assert dono == "executor#1"
    assert versao_depois == versao


def test_identidade_declarada_no_corpo_e_recusada_edge_case() -> None:
    """Caso de borda: o corpo não escolhe autor nem papel; a identidade é a do servidor."""
    with _servidor() as (base_url, _):
        status, recusa = _chamar("PUT", f"{base_url}/api/governanca/global", {"preset": "arbitragem_maxima", "papel": "arbitro"})

    assert status == 400 and "papel" in recusa["mensagem"]


def test_governanca_do_projeto_herdar_por_gesto_e_operacao_nominal() -> None:
    """O Projeto sobrescreve um gesto, `herdar` o devolve à global, e a operação grava no mesmo lote."""
    with _servidor() as (base_url, _):
        _montar_hierarquia(base_url)
        rota = f"{base_url}/api/projetos/p-http/governanca"
        _chamar("PUT", f"{base_url}/api/governanca/global", {"preset": "personalizada", "personalizada": {"excluir": "arbitro"}})
        _, inicial = _chamar("GET", rota)
        _, sobrescrita = _chamar(
            "PUT",
            rota,
            {
                "preset": "personalizada",
                "personalizada": {"excluir": "humano"},
                "operacao": {"cadencia": "setor", "teto_rodadas": 5, "ramo_base": "origin/stage", "caminhos_de_colisao": ["db/*"]},
            },
        )
        _, herdada = _chamar("PUT", rota, {"personalizada": {"excluir": "herdar"}})
        _, lida = _chamar("GET", rota)

    assert inicial["origens"]["excluir"] == "global" and inicial["configuracao"]["preset"] == "herdar"
    assert sobrescrita["origens"]["excluir"] == "projeto" and sobrescrita["politica_efetiva"]["excluir"] == "humano"
    assert herdada["configuracao"] == {"preset": "personalizada", "personalizada": {}}
    assert herdada["origens"]["excluir"] == "global"
    assert lida["operacao"] == {
        "cadencia": "setor",
        "teto_rodadas": 5,
        "ramo_base": "origin/stage",
        "caminhos_de_colisao": ["db/*"],
    }
    assert lida["politica_global"]["excluir"] == "arbitro"


def test_governanca_do_projeto_invalida_e_inexistente_edge_case() -> None:
    """Caso de borda: operação inválida é 400 com os problemas, e Projeto que não existe é 404 na leitura e na escrita."""
    with _servidor() as (base_url, _):
        _montar_hierarquia(base_url)
        rota = f"{base_url}/api/projetos/p-http/governanca"
        status, invalida = _chamar("PUT", rota, {"operacao": {"teto_rodadas": "muitas"}})
        leitura = _chamar("GET", f"{base_url}/api/projetos/nao-existe/governanca")
        escrita = _chamar("PUT", f"{base_url}/api/projetos/nao-existe/governanca", {"preset": "arbitragem_maxima"})
        sem_operacao_no_global = _chamar("PUT", f"{base_url}/api/governanca/global", {"operacao": {"cadencia": "goal"}})

    assert status == 400 and "teto_rodadas" in invalida["problemas"][0]
    assert leitura[0] == 404 and escrita[0] == 404
    assert sem_operacao_no_global[0] == 400


def test_auditoria_traz_so_o_papel_arbitro_e_respeita_o_limite_nominal() -> None:
    """Só os eventos do árbitro, os mais recentes primeiro, cortados pelo `limite`."""
    with _servidor() as (base_url, kernel):
        _montar_hierarquia(base_url)
        _arbitro_escreve(kernel)
        _, todos = _chamar("GET", f"{base_url}/api/governanca/auditoria")
        _, um = _chamar("GET", f"{base_url}/api/governanca/auditoria?limite=1")
        _, ilegivel = _chamar("GET", f"{base_url}/api/governanca/auditoria?limite=abc")

    assert todos["total"] == 2
    assert [evento["tipo"] for evento in todos["eventos"]] == ["aresta_criada", "no_criado"]
    assert {evento["papel"] for evento in todos["eventos"]} == {"arbitro"}
    assert todos["eventos"][0]["autor"] == "arbitro-1"
    assert todos["eventos"][1]["ids_tocados"] == ["dec-arb"]
    assert len(um["eventos"]) == 1 and um["eventos"][0]["seq"] == todos["eventos"][0]["seq"]
    assert len(ilegivel["eventos"]) == 2


def test_liberar_posse_pelo_servidor_nominal() -> None:
    """O humano libera a posse de qualquer dono; liberar de novo é conflito, e id errado é 404."""
    with _servidor() as (base_url, kernel):
        _montar_hierarquia(base_url)
        kernel.adquirir_lock_task("task-http", "executor-sonnet#morto")
        rota = f"{base_url}/api/tarefas/task-http/liberar-posse"
        status, recibo = _chamar("POST", rota)
        repetida = _chamar("POST", rota)
        inexistente = _chamar("POST", f"{base_url}/api/tarefas/nao-existe/liberar-posse")
        dono = kernel.obter_dono_do_lock("task-http")

    assert status == 200 and recibo["dono_anterior"] == "executor-sonnet#morto"
    assert repetida[0] == 409 and inexistente[0] == 404
    assert dono is None


def test_o_no_governanca_nao_aparece_no_canvas_na_busca_nem_no_replay_nominal() -> None:
    """O nó que guarda a política existe no grafo e fica fora do canvas, da busca e do estado histórico."""
    with _servidor() as (base_url, kernel):
        _montar_hierarquia(base_url)
        _chamar("PUT", f"{base_url}/api/governanca/global", {"preset": "arbitragem_maxima"})
        _, canvas = _chamar("GET", f"{base_url}/api/canvas")
        _, busca = _chamar("GET", f"{base_url}/api/busca?termo=governanca")
        _, so_governanca = _chamar("GET", f"{base_url}/api/busca?termo=governanca&tipos=Governanca")
        _, historico = _chamar("GET", f"{base_url}/api/timeline/state?versao={kernel.obter_estado().versao_log}")

    assert "governanca-global" in kernel.obter_estado().nos
    assert "Governanca" not in {no["tipo"] for no in canvas["nos"]}
    assert canvas["total_nos"] == 4
    assert busca["resultados"] == [] and busca["total"] == 0
    assert so_governanca["resultados"] == [] and so_governanca["total"] == 0
    assert "Governanca" not in {no["tipo"] for no in historico["nos"]}
    assert canvas["total_por_ambito"] == {"projetos": 4, "hook": 0}
