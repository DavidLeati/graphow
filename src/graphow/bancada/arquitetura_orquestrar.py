"""A arquitetura `orquestrar` da bancada: o `graphow orquestrar` em modo autônomo sobre a spec do projeto.

O laço roda no processo da bancada, com o banco descartável da execução como
livro-razão e o executor de sessão que a bancada recebeu (o `claude` de
`GRAPHOW_CLAUDE`, ou o falso dos testes). Cria o Goal da `spec-<projeto>.md`
ao lado do repositório, trabalha na branch de entrega do `projeto.json`,
criada da branch da semente, e integra por fast-forward no fim. As sessões
que a bancada mede são todas as que a telemetria do orquestrador registrou
para o Goal, relidas dos streams gravados; a parada do laço e o status vão
para `orquestrar.json` ao lado de `execucao.json`.
"""

import json

from graphow.bancada.arquiteturas import PedidoDeExecucao
from graphow.kernel.composicao import montar_kernel_sqlite
from graphow.orquestrador.contexto_do_laco import DependenciasDoLaco, OpcoesDoLaco, Parada
from graphow.orquestrador.laco import Orquestrador
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.modelo_do_goal import MODO_AUTONOMO
from graphow.orquestrador.sessoes_de_papel import resultados_da_telemetria
from graphow.orquestrador.status import formatar_status
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao
from graphow.storage.sqlite_store import SQLiteEventStore
from graphow.storage.telemetria_de_sessoes import RepositorioTelemetria

NOME_DO_ORQUESTRAR: str = "orquestrar"
PASTA_DO_ESTADO: str = "orquestrar"
ARQUIVO_DA_PARADA: str = "orquestrar.json"


class ArquiteturaOrquestrar:
    """O orquestrador em código, em modo autônomo, com o banco e a branch da execução."""

    nome: str = NOME_DO_ORQUESTRAR

    def executar(self, pedido: PedidoDeExecucao, sessoes: ExecutorDeSessao) -> tuple[ResultadoDeSessao, ...]:
        """Roda o laço do Goal da spec até ele fechar ou parar, e devolve as sessões da telemetria."""
        with SQLiteEventStore(pedido.banco) as store:
            kernel = montar_kernel_sqlite(store)
            telemetria = RepositorioTelemetria(store.conexao)
            dependencias = DependenciasDoLaco(
                kernel=kernel, executor=sessoes, telemetria=telemetria,
                pasta_de_estado=pedido.diretorio / PASTA_DO_ESTADO, tempo_limite_da_sessao_s=pedido.tempo_limite_s,
            )
            opcoes = OpcoesDoLaco(modo=MODO_AUTONOMO, ramo=pedido.projeto.ramo, base=pedido.projeto.semente.ramo)
            parada = Orquestrador(dependencias).iniciar_da_spec(pedido.spec, pedido.repositorio, opcoes)
            registros = telemetria.listar(parada.id_goal)
            estado = ler_estado(kernel.obter_view(), parada.id_goal)
            _gravar_parada(pedido, parada, formatar_status(estado, registros) if estado else [])
        return resultados_da_telemetria(registros)


def _gravar_parada(pedido: PedidoDeExecucao, parada: Parada, status: list[str]) -> None:
    """Por que o laço parou e o status do Goal, ao lado de `execucao.json`."""
    dados = {"id_goal": parada.id_goal, "motivo": parada.motivo.value, "mensagem": parada.mensagem, "status": status}
    caminho = pedido.diretorio / ARQUIVO_DA_PARADA
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
