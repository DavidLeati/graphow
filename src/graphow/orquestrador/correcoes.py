"""As fatias de correção de um ciclo: os bloqueantes dele todos numa fatia só.

Na bancada da fase 2, cada bloqueante virava uma fatia e uma sessão de
executor: os 8 bloqueantes de um marco do estoque-loja estavam todos no mesmo
arquivo, e cada sessão pagava de novo a partida a frio, para mexer no mesmo
lugar. Depois os bloqueantes se juntaram pela área (o arquivo do `local`),
mas os de arquivos diferentes ainda pagavam uma partida a frio cada. Agora
o ciclo inteiro vira uma fatia só: a verificação abre no máximo
`TETO_DE_BLOQUEANTES` bloqueantes (orquestrador/saida_do_verificador.py), e a
sessão de correção leva todos, com as provas e as chamadas que os
reproduzem. Só a verificação final, que cobra também os bloqueantes que os
outros marcos deixaram, passa do teto; aí o ciclo se divide em fatias de
`MAXIMO_POR_FATIA`, na ordem, para a sessão não virar um marco inteiro.

A área do achado (o arquivo do local, sem local o primeiro critério ou
decisão que ele fere) segue servindo para achar a correção de um ciclo
anterior na mesma área (orquestrador/historico_da_correcao.py). O caminho se
compara normalizado (`./x.py` é `x.py`, a barra invertida é barra e, no
Windows, a caixa não conta).

A fatia agrupada que falha duas vezes não vira pendência inteira: ela se
divide numa fatia por achado (orquestrador/execucao_da_fatia.py), para que os
que dão para corrigir sejam corrigidos. O que a tentativa agrupada fez não se
aproveita em parte: a entrega é um commit só, provado pela suíte inteira, e
não há como saber que pedaço do diff corrige que achado; ela fica no .patch.

Os arquivos da fatia são todos os que os locais citam (`cli.py:28; estatistica.py:32`),
e não só o primeiro: na fumaça real da rodada 3, a correção listava só `cli.py`,
o executor se ateve a ele, e a verificação seguinte achou a causa em
`estatistica.py`.
"""

from collections.abc import Iterable, Sequence
import os
import re
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado
from graphow.orquestrador.saida_do_verificador import TETO_DE_BLOQUEANTES

MAXIMO_POR_FATIA: int = TETO_DE_BLOQUEANTES
# Um caminho com extensão no texto do local (`src/x.py`, `C:/x.py`, `.\\x.py`); `1.5` não é caminho.
CAMINHO_NO_LOCAL: re.Pattern[str] = re.compile(r"(?:[A-Za-z]:)?[\w./\\-]*\w\.[A-Za-z][A-Za-z0-9]{0,7}\b")


def normalizar_caminho(caminho: str) -> str:
    """O caminho como o agrupamento o compara: barras para a frente, sem `./` no começo e, no Windows, sem caixa."""
    normalizado = caminho.strip().replace("\\", "/")
    while normalizado.startswith("./"):
        normalizado = normalizado[2:]
    return normalizado.lower() if os.name == "nt" else normalizado


def area_do_achado(achado: AchadoRegistrado) -> str:
    """A área em que o achado mora: o arquivo do local, o primeiro critério ou decisão que ele fere, ou ele mesmo."""
    arquivo = normalizar_caminho(_arquivo_do_local(achado.texto("local")))
    if arquivo:
        return f"arquivo:{arquivo}"
    feridos = (*achado.lista("criterios"), *achado.lista("decisoes"))
    return f"criterio:{feridos[0]}" if feridos else f"achado:{achado.id}"


def agrupar_o_ciclo(achados: Iterable[AchadoRegistrado]) -> list[tuple[AchadoRegistrado, ...]]:
    """Os bloqueantes do ciclo numa fatia só, na ordem e sem repetir achado; acima de `MAXIMO_POR_FATIA`, em pedaços dele."""
    unicos = list({achado.id: achado for achado in achados}.values())
    return [tuple(unicos[inicio:inicio + MAXIMO_POR_FATIA]) for inicio in range(0, len(unicos), MAXIMO_POR_FATIA)]


def _arquivo_do_local(local: str) -> str:
    """O arquivo do local `arquivo:linha` (a letra do drive do Windows, `C:/x.py:3`, fica no arquivo)."""
    partes = local.strip().split(":")
    if len(partes) > 1 and len(partes[0]) == 1 and partes[0].isalpha():
        return f"{partes[0]}:{partes[1]}"
    return partes[0]


def arquivos_do_local(local: str) -> list[str]:
    """Todos os arquivos que o local cita, na ordem, com a barra para a frente e sem `./`."""
    primeiro = _arquivo_do_local(local).strip()
    citados = CAMINHO_NO_LOCAL.findall(local)
    if primeiro and (" " not in primeiro or not citados):
        citados.insert(0, primeiro)
    limpos = (caminho.strip().replace("\\", "/").removeprefix("./") for caminho in citados)
    return list(dict.fromkeys(caminho for caminho in limpos if caminho))


def titulo_da_correcao(grupo: Sequence[AchadoRegistrado]) -> str:
    """O título da fatia: o primeiro achado, e quantos outros ela corrige junto."""
    outros = f" (e mais {len(grupo) - 1})" if len(grupo) > 1 else ""
    return f"Corrige: {grupo[0].texto('titulo')}{outros}"


def propriedades_da_correcao(grupo: Sequence[AchadoRegistrado]) -> dict[str, Any]:
    """O objetivo, os critérios, os arquivos e os achados da fatia que corrige o grupo."""
    objetivos = [achado.texto("descricao") + (f" (local: {achado.texto('local')})" if achado.texto("local") else "")
                 for achado in grupo]
    arquivos = [arquivo for achado in grupo for arquivo in arquivos_do_local(achado.texto("local"))]
    return {
        m.CAMPO_OBJETIVO: objetivos[0] if len(grupo) == 1 else "\n".join(f"{n}. {texto}" for n, texto in enumerate(objetivos, 1)),
        m.CAMPO_CRITERIOS: list(dict.fromkeys(c for achado in grupo for c in achado.lista("criterios"))),
        m.CAMPO_ARQUIVOS_ALVO: list(dict.fromkeys(arquivos)),
        m.CAMPO_ACHADO: grupo[0].id,
        m.CAMPO_ACHADOS: [achado.id for achado in grupo],
    }
