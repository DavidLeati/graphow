"""Modelos imutáveis do Grafo, Nós, Arestas e Metadados Temporais."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any

from graphow.core.types import PapelAutor, TipoAresta, TipoNo


@dataclass(frozen=True)
class ProvenienciaNo:
    """Quem escreveu o nó, sob qual papel e por qual origem.

    Autor e papel estavam em cada evento do log e em nenhuma linha da vista: o
    agente lia o conteúdo sem saber quem o pôs ali, e uma Evidence trazida por
    ferramenta chegava com a mesma autoridade de uma escrita pelo humano. Ver
    achado A-17.
    """

    autor: str = ""
    papel: str = ""
    origem: str = ""
    atualizado_por: str = ""

    @property
    def eh_de_agente(self) -> bool:
        """Indica conteúdo que não passou pela mão do humano ao ser criado."""
        return self.papel not in ("", PapelAutor.HUMANO.value)

    def descrever(self) -> str:
        """Assinatura curta para a linha da vista materializada."""
        if not self.autor:
            return ""
        return f"{self.autor} ({self.papel})" if self.papel else self.autor

    def com_atualizacao(self, autor: str) -> "ProvenienciaNo":
        """Registra quem tocou o nó por último, preservando quem o criou."""
        return ProvenienciaNo(
            autor=self.autor, papel=self.papel, origem=self.origem, atualizado_por=autor
        )


@dataclass(frozen=True)
class MetadadosTemporais:
    """Estrutura bitemporal de rastreabilidade de validade e log."""

    criado_em: str
    registrado_em: str
    valido_de: str | None = None
    valido_ate: str | None = None

    @classmethod
    def agora(cls, valido_de: str | None = None) -> "MetadadosTemporais":
        """Cria metadados temporais com timestamp UTC atual."""
        momento_atual: str = datetime.now(timezone.utc).isoformat()
        return cls(
            criado_em=momento_atual,
            registrado_em=momento_atual,
            valido_de=valido_de or momento_atual,
            valido_ate=None,
        )


@dataclass(frozen=True)
class NoGrafo:
    """Representação imutável de um nó do grafo de conhecimento."""

    id: str
    tipo: TipoNo
    rotulo: str
    propriedades: Mapping[str, Any] = field(default_factory=dict)
    metadados: MetadadosTemporais = field(default_factory=MetadadosTemporais.agora)
    proveniencia: ProvenienciaNo = field(default_factory=ProvenienciaNo)

    def obter_propriedade(self, chave: str, padrao: Any = None) -> Any:
        """Obtém o valor de uma propriedade com valor de fallback."""
        return self.propriedades.get(chave, padrao)

    def com_propriedades(self, novas_propriedades: Mapping[str, Any]) -> "NoGrafo":
        """Retorna uma nova instância com propriedades mescladas de forma imutável."""
        propriedades_mescladas: dict[str, Any] = {**self.propriedades, **novas_propriedades}
        return NoGrafo(
            id=self.id,
            tipo=self.tipo,
            rotulo=self.rotulo,
            propriedades=propriedades_mescladas,
            metadados=self.metadados,
            proveniencia=self.proveniencia,
        )


@dataclass(frozen=True)
class ArestaGrafo:
    """Representação imutável de uma aresta direcionada e tipada."""

    id: str
    origem_id: str
    destino_id: str
    tipo: TipoAresta
    metadados: MetadadosTemporais = field(default_factory=MetadadosTemporais.agora)


@dataclass(frozen=True)
class GrafoEstado:
    """Estado integral imutável da projeção do grafo em memória."""

    nos: Mapping[str, NoGrafo] = field(default_factory=dict)
    arestas: Mapping[str, ArestaGrafo] = field(default_factory=dict)
    versao_log: int = 0

    def contem_no(self, id_no: str) -> bool:
        """Verifica existência de um nó por ID."""
        return id_no in self.nos

    def contem_aresta(self, id_aresta: str) -> bool:
        """Verifica existência de uma aresta por ID."""
        return id_aresta in self.arestas

    def serializar_para_json(self) -> str:
        """Serialização determinística ordenada por chaves para asserção de paridade."""
        dados_nos: list[dict[str, Any]] = [
            _serializar_no(no) for _, no in sorted(self.nos.items())
        ]
        dados_arestas: list[dict[str, Any]] = [
            {
                "id": aresta.id,
                "origem_id": aresta.origem_id,
                "destino_id": aresta.destino_id,
                "tipo": aresta.tipo.value,
            }
            for _, aresta in sorted(self.arestas.items())
        ]
        estrutura: dict[str, Any] = {
            "versao_log": self.versao_log,
            "nos": dados_nos,
            "arestas": dados_arestas,
        }
        return json.dumps(estrutura, sort_keys=True, separators=(",", ":"))


def _serializar_no(no: NoGrafo) -> dict[str, Any]:
    """Forma determinística de um nó, com a proveniência que o log registrou."""
    return {
        "id": no.id,
        "tipo": no.tipo.value,
        "rotulo": no.rotulo,
        "propriedades": dict(sorted(no.propriedades.items())),
        "proveniencia": {
            "autor": no.proveniencia.autor,
            "papel": no.proveniencia.papel,
            "origem": no.proveniencia.origem,
        },
    }
