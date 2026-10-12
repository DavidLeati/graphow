"""As fatias de correção de um ciclo: os bloqueantes do mesmo arquivo, ou do mesmo critério, juntos numa fatia só.

Na bancada da fase 2, cada bloqueante virava uma fatia e uma sessão de
executor: os 8 bloqueantes de um marco do estoque-loja estavam todos no mesmo
arquivo, e cada sessão pagava de novo a partida a frio, para mexer no mesmo
lugar. Agora os bloqueantes se juntam pela área: o arquivo do `local` do
achado; sem local, o primeiro critério ou decisão que ele fere; sem nada,
ele sozinho. Um grupo passa de `MAXIMO_POR_FATIA` achados só se dividindo,
para a sessão não virar um marco inteiro.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado

MAXIMO_POR_FATIA: int = 6


def area_do_achado(achado: AchadoRegistrado) -> str:
    """A área em que o achado mora: o arquivo do local, o primeiro critério ou decisão que ele fere, ou ele mesmo."""
    arquivo = achado.texto("local").split(":")[0].strip().replace("\\", "/")
    if arquivo:
        return f"arquivo:{arquivo}"
    feridos = (*achado.lista("criterios"), *achado.lista("decisoes"))
    return f"criterio:{feridos[0]}" if feridos else f"achado:{achado.id}"


def agrupar_por_area(achados: Iterable[AchadoRegistrado]) -> list[tuple[AchadoRegistrado, ...]]:
    """Os achados em grupos da mesma área, na ordem em que cada área apareceu, sem repetir achado."""
    grupos: dict[str, list[AchadoRegistrado]] = {}
    vistos: set[str] = set()
    for achado in achados:
        if achado.id not in vistos:
            vistos.add(achado.id)
            grupos.setdefault(area_do_achado(achado), []).append(achado)
    return [tuple(grupo[inicio:inicio + MAXIMO_POR_FATIA]) for grupo in grupos.values()
            for inicio in range(0, len(grupo), MAXIMO_POR_FATIA)]


def titulo_da_correcao(grupo: Sequence[AchadoRegistrado]) -> str:
    """O título da fatia: o primeiro achado, e quantos outros ela corrige junto."""
    outros = f" (e mais {len(grupo) - 1})" if len(grupo) > 1 else ""
    return f"Corrige: {grupo[0].texto('titulo')}{outros}"


def propriedades_da_correcao(grupo: Sequence[AchadoRegistrado]) -> dict[str, Any]:
    """O objetivo, os critérios, os arquivos e os achados da fatia que corrige o grupo."""
    objetivos = [achado.texto("descricao") + (f" (local: {achado.texto('local')})" if achado.texto("local") else "")
                 for achado in grupo]
    arquivos = [local.split(":")[0].strip() for achado in grupo if (local := achado.texto("local"))]
    return {
        m.CAMPO_OBJETIVO: objetivos[0] if len(grupo) == 1 else "\n".join(f"{n}. {texto}" for n, texto in enumerate(objetivos, 1)),
        m.CAMPO_CRITERIOS: list(dict.fromkeys(c for achado in grupo for c in achado.lista("criterios"))),
        m.CAMPO_ARQUIVOS_ALVO: list(dict.fromkeys(arquivos)),
        m.CAMPO_ACHADO: grupo[0].id,
        m.CAMPO_ACHADOS: [achado.id for achado in grupo],
    }
