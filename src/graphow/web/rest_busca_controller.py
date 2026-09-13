"""Controlador REST da busca textual da interface, na mesma ordem que o agente vê.

A busca rápida e o painel de busca olhavam só os nós carregados no canvas. Com o
recorte resolvido no servidor, isso deixou de ser o grafo: um canvas colapsado em
sessões tem dezoito nós, e procurar uma tarefa ali devolvia nada. Aqui a busca
corre sobre o ramo inteiro, com o ranking e o corte de `buscar` do MCP, e cada
linha volta com o que a tela precisa para chegar ao nó — a sessão que o contém e
o trecho onde o termo apareceu.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from graphow.core.models import NoGrafo
from graphow.core.types import TipoNo
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.ranking_busca import CASOU_NAS_PROPRIEDADES, CriterioBusca, ResultadoRanqueado
from graphow.web.dto import RequisicaoBusca
from graphow.web.mapeamento_escopo import MapeadorEscopo

FOLGA_ANTES_DO_TERMO: int = 60
FOLGA_DEPOIS_DO_TERMO: int = 100
RETICENCIAS: str = "…"

# Coordenada do canvas casa com qualquer busca por número e não diz nada a quem lê.
CHAVES_FORA_DO_TRECHO: frozenset[str] = frozenset({"pos_x", "pos_y"})


class BuscaWebController:
    """Busca textual ranqueada sobre o grafo inteiro do ramo."""

    def __init__(self, kernel: WriteKernel, mapeador: MapeadorEscopo | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._mapeador: MapeadorEscopo = mapeador or MapeadorEscopo()

    def buscar(self, req: RequisicaoBusca) -> dict[str, Any]:
        """Ranqueia, corta no limite e diz quantos existem no total."""
        tipos, invalidos = converter_tipos_de_no(req.tipos)
        if invalidos:
            return {"sucesso": False, "mensagem": f"Tipos de no desconhecidos: {', '.join(invalidos)}"}
        view = self._kernel.obter_view(req.ramo_id)
        resultado = view.buscar_ranqueado(CriterioBusca(termo=req.termo, tipos=tipos, limite=req.limite))
        sessoes = self._mapeador.mapear_sessoes(view)
        return {
            "sucesso": True,
            "termo": req.termo,
            "total": resultado.total_encontrado,
            "exibidos": len(resultado.itens),
            "truncado": resultado.truncado,
            "resultados": [self._linha(item, sessoes, req.termo) for item in resultado.itens],
        }

    def _linha(self, item: ResultadoRanqueado, sessoes: Mapping[str, str], termo: str) -> dict[str, Any]:
        """Linha esquelética do ranking, acrescida do caminho até o nó e do trecho."""
        casou_nas_propriedades = item.onde_casou == CASOU_NAS_PROPRIEDADES
        return {
            **item.em_dicionario(),
            "sessao_id": sessoes.get(item.no.id),
            "status": item.no.obter_propriedade("status"),
            "trecho": extrair_trecho(item.no, termo) if casou_nas_propriedades else None,
        }


def converter_tipos_de_no(brutos: Iterable[str]) -> tuple[tuple[TipoNo, ...], tuple[str, ...]]:
    """Separa os tipos textuais entre membros da ontologia e desconhecidos."""
    aceitos: list[TipoNo] = []
    invalidos: list[str] = []
    for bruto in brutos:
        tipo = _tipo_ou_none(bruto)
        if tipo is None:
            invalidos.append(bruto)
            continue
        aceitos.append(tipo)
    return (tuple(aceitos), tuple(invalidos))


def _tipo_ou_none(bruto: str) -> TipoNo | None:
    """Converte o texto em tipo de nó com a mesma tolerância de caixa do MCP."""
    try:
        return TipoNo(bruto.strip().capitalize())
    except ValueError:
        return None


def extrair_trecho(no: NoGrafo, termo: str) -> dict[str, str] | None:
    """Primeira propriedade em que o termo aparece, com uma janela de texto em volta."""
    termo_normalizado = termo.strip().lower()
    if not termo_normalizado:
        return None
    for chave, valor in no.propriedades.items():
        texto = str(valor)
        posicao = texto.lower().find(termo_normalizado)
        if chave in CHAVES_FORA_DO_TRECHO or posicao < 0:
            continue
        return {"chave": chave, "texto": _janela(texto, posicao, len(termo_normalizado))}
    return None


def _janela(texto: str, posicao: int, tamanho_termo: int) -> str:
    """Recorta o texto em volta do termo, marcando com reticências o que ficou de fora."""
    inicio = max(0, posicao - FOLGA_ANTES_DO_TERMO)
    fim = min(len(texto), posicao + tamanho_termo + FOLGA_DEPOIS_DO_TERMO)
    prefixo = RETICENCIAS if inicio > 0 else ""
    sufixo = RETICENCIAS if fim < len(texto) else ""
    return f"{prefixo}{texto[inicio:fim].strip()}{sufixo}"
