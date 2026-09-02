"""Controlador REST especializado no rastreamento de linhagem causal e proveniência."""

from typing import Any

from graphow.kernel.write_kernel import WriteKernel
from graphow.lineage.lineage_tracer import CaminhoLinhagem, LineageTracer


class LineageWebController:
    """Controlador para expor trilhas causais do entregável até o objetivo raiz."""

    def __init__(self, kernel: WriteKernel, tracer: LineageTracer | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._tracer: LineageTracer = tracer or LineageTracer()

    def obter_linhagem(self, id_no: str, ramo_id: str = "main") -> dict[str, Any]:
        """Rastreia passos causais e nós intermediários desde o nó alvo até o Goal raiz."""
        view = self._kernel.obter_view(ramo_id)
        caminho: CaminhoLinhagem = self._tracer.rastrear_linhagem(id_no, view)
        nos_detalhados: list[dict[str, Any]] = [
            {"id": n.id, "tipo": n.tipo.value, "rotulo": n.rotulo, "propriedades": dict(n.propriedades)}
            for n in caminho.nos_cadeia
        ]
        goal_info: dict[str, Any] | None = None
        if caminho.goal_raiz is not None:
            goal_info = {
                "id": caminho.goal_raiz.id,
                "tipo": caminho.goal_raiz.tipo.value,
                "rotulo": caminho.goal_raiz.rotulo,
                "propriedades": dict(caminho.goal_raiz.propriedades),
            }
        return {
            "id_alvo": caminho.id_alvo,
            "passos": list(caminho.passos),
            "nos_cadeia": nos_detalhados,
            "goal_raiz": goal_info,
        }
