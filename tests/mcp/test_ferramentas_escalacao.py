"""Testes do caminho de volta: listar as próprias dúvidas e esperar a resposta."""

from graphow.core.types import PapelAutor, StatusQuestion, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.espera import PoliticaEspera, RelogioSimulado
from graphow.mcp.ferramentas_escalacao import FerramentasEscalacao
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.submissao import ContextoFerramentaMCP

POLITICA_DE_TESTE: PoliticaEspera = PoliticaEspera(
    prazo_padrao_segundos=4.0, intervalo_segundos=1.0, prazo_maximo_segundos=10.0
)


def _montar_kernel_com_questao(autor_da_questao: str = "agente-a") -> WriteKernel:
    """Cria uma Question aberta atribuída ao autor informado."""
    kernel = montar_kernel_em_memoria()
    kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=(
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/nos/quest-1",
                        value={
                            "id": "quest-1",
                            "tipo": TipoNo.QUESTION.value,
                            "rotulo": "TTL estrito ou LRU?",
                            "propriedades": {
                                "status": StatusQuestion.ABERTA.value,
                                "aberta_por": autor_da_questao,
                            },
                        },
                    ),
                ),
                justificativa="bootstrap",
            )
        )
    )
    return kernel


def _responder(kernel: WriteKernel) -> None:
    """O humano encerra a dúvida com uma resposta registrada no grafo."""
    kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=(
                    ItemPatch(
                        op=OperacaoPatch.REPLACE,
                        path="/nos/quest-1/propriedades/status",
                        value=StatusQuestion.RESPONDIDA.value,
                    ),
                    ItemPatch(
                        op=OperacaoPatch.REPLACE,
                        path="/nos/quest-1/propriedades/resposta",
                        value="LRU por contagem",
                    ),
                ),
                justificativa="resposta humana",
            )
        )
    )


def _ferramentas(kernel: WriteKernel, relogio: RelogioSimulado) -> FerramentasEscalacao:
    """Monta o grupo de ferramentas de escalação sob a identidade do agente."""
    contexto = ContextoFerramentaMCP(
        kernel=kernel, identidade=IdentidadeSessaoMCP.criar("agente-a", "executor")
    )
    return FerramentasEscalacao(contexto, relogio, POLITICA_DE_TESTE)


def test_minhas_questoes_lista_apenas_as_do_autor_nominal() -> None:
    """A lista é do autor da sessão, não do grafo inteiro."""
    kernel = _montar_kernel_com_questao("agente-a")
    ferramentas = _ferramentas(kernel, RelogioSimulado())

    resposta = ferramentas.minhas_questoes({})

    assert resposta["total"] == 1
    assert resposta["questoes"][0]["id"] == "quest-1"


def test_minhas_questoes_ignora_duvidas_de_outro_agente_edge_case() -> None:
    """Caso de borda: a dúvida de outro agente não aparece nesta sessão."""
    kernel = _montar_kernel_com_questao("agente-b")
    ferramentas = _ferramentas(kernel, RelogioSimulado())

    assert ferramentas.minhas_questoes({})["total"] == 0


def test_minhas_questoes_filtra_por_status_nominal() -> None:
    """O filtro separa o que ainda trava do que já foi respondido."""
    kernel = _montar_kernel_com_questao()
    ferramentas = _ferramentas(kernel, RelogioSimulado())

    assert ferramentas.minhas_questoes({"status": "respondida"})["total"] == 0
    _responder(kernel)
    assert ferramentas.minhas_questoes({"status": "respondida"})["total"] == 1


def test_aguardar_resposta_retorna_de_imediato_quando_ja_respondida_nominal() -> None:
    """Quem chega depois da resposta não espera nada."""
    kernel = _montar_kernel_com_questao()
    _responder(kernel)
    relogio = RelogioSimulado()

    resposta = _ferramentas(kernel, relogio).aguardar_resposta({"id_questao": "quest-1"})

    assert resposta["sucesso"] is True
    assert resposta["resposta"] == "LRU por contagem"
    assert relogio.esperas_registradas == ()


def test_aguardar_resposta_expira_e_instrui_a_retomada_edge_case() -> None:
    """Caso de borda: o prazo acaba e o agente recebe como retomar."""
    kernel = _montar_kernel_com_questao()
    relogio = RelogioSimulado()

    resposta = _ferramentas(kernel, relogio).aguardar_resposta({"id_questao": "quest-1"})

    assert resposta["sucesso"] is False
    assert resposta["expirou"] is True
    assert resposta["status"] == StatusQuestion.ABERTA.value
    assert "minhas_questoes" in resposta["mensagem"]
    assert sum(relogio.esperas_registradas) >= POLITICA_DE_TESTE.prazo_padrao_segundos


def test_aguardar_resposta_de_questao_inexistente_falha_edge_case() -> None:
    """Caso de borda: esperar por algo que não existe é erro, não espera infinita."""
    kernel = _montar_kernel_com_questao()
    relogio = RelogioSimulado()

    resposta = _ferramentas(kernel, relogio).aguardar_resposta({"id_questao": "fantasma"})

    assert resposta["sucesso"] is False
    assert relogio.esperas_registradas == ()


def test_politica_limita_prazo_pedido_pelo_agente_edge_case() -> None:
    """Caso de borda: um prazo absurdo não pode prender o transporte stdio."""
    politica = PoliticaEspera()

    assert politica.prazo_valido(10_000) == politica.prazo_maximo_segundos
    assert politica.prazo_valido(-5) == 0.0
    assert politica.prazo_valido(None) == politica.prazo_padrao_segundos
    assert politica.prazo_valido("nao numerico") == politica.prazo_padrao_segundos
