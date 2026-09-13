"""Interface abstrata para adaptadores de ciclo de vida do harness."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class AdaptadorDeHarness(ABC):
    """Contrato para captura e injeção desacoplada do ciclo de vida de sessões."""

    @abstractmethod
    def registrar_inicio_sessao(
        self,
        id_sessao: str,
        id_setor: str,
        metadados: Mapping[str, Any] | None = None,
    ) -> bool:
        """Registra a criação de uma nova sessão e vincula ao Setor correspondente."""
        raise NotImplementedError

    @abstractmethod
    def registrar_fim_sessao(
        self,
        id_sessao: str,
        resumo: str = "",
    ) -> bool:
        """Marca a conclusão de uma sessão no grafo compartilhado."""
        raise NotImplementedError

    @abstractmethod
    def registrar_execucao_run(
        self,
        id_sessao: str,
        modelo: str,
        dados_execucao: Mapping[str, Any],
    ) -> str:
        """Registra um nó Run associado à sessão e retorna o ID gerado."""
        raise NotImplementedError
