"""Validação de um valor JSON contra o subconjunto de JSON Schema que os papéis usam.

O Claude Code confere a saída estruturada contra o `--json-schema`, mas a
sessão pode terminar sem ela (o modelo respondeu em texto, a sessão morreu, a
versão do executável mudou), e o orquestrador não grava nada que não
conferiu. Sem dependência de runtime: o pacote não tem nenhuma, e o
subconjunto (tipo, enum, required, properties, additionalProperties falso,
items, minItems e minLength) cabe em poucas funções.
"""

from collections.abc import Mapping
from typing import Any

TIPOS_DO_JSON: Mapping[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
}


def validar_contra_esquema(valor: Any, esquema: Mapping[str, Any], caminho: str = "$") -> tuple[str, ...]:
    """Os problemas do valor diante do esquema, cada um com o caminho; vazio quando ele confere."""
    problema_de_tipo = _problema_de_tipo(valor, esquema, caminho)
    if problema_de_tipo:
        return (problema_de_tipo,)
    problemas = list(_problemas_de_valor(valor, esquema, caminho))
    if isinstance(valor, dict):
        problemas.extend(_problemas_do_objeto(valor, esquema, caminho))
    if isinstance(valor, list):
        problemas.extend(_problemas_da_lista(valor, esquema, caminho))
    return tuple(problemas)


def _problema_de_tipo(valor: Any, esquema: Mapping[str, Any], caminho: str) -> str:
    """O tipo declarado, com o booleano fora de inteiro e número, como o JSON os separa."""
    tipo = esquema.get("type")
    if tipo is None:
        return ""
    aceitos = TIPOS_DO_JSON.get(str(tipo), ())
    if isinstance(valor, bool) and tipo != "boolean":
        return f"{caminho}: esperava {tipo}, veio booleano"
    if not isinstance(valor, aceitos):
        return f"{caminho}: esperava {tipo}, veio {type(valor).__name__}"
    return ""


def _problemas_de_valor(valor: Any, esquema: Mapping[str, Any], caminho: str) -> list[str]:
    """Enum e tamanho mínimo do texto."""
    problemas: list[str] = []
    if "enum" in esquema and valor not in esquema["enum"]:
        problemas.append(f"{caminho}: '{valor}' fora de {list(esquema['enum'])}")
    if isinstance(valor, str) and len(valor.strip()) < int(esquema.get("minLength", 0)):
        problemas.append(f"{caminho}: texto vazio")
    return problemas


def _problemas_do_objeto(valor: dict[str, Any], esquema: Mapping[str, Any], caminho: str) -> list[str]:
    """Campos obrigatórios, campos a mais e cada propriedade declarada."""
    propriedades: Mapping[str, Any] = esquema.get("properties", {})
    problemas = [f"{caminho}: falta '{chave}'" for chave in esquema.get("required", ()) if chave not in valor]
    if esquema.get("additionalProperties") is False:
        problemas.extend(f"{caminho}: campo nao previsto '{chave}'" for chave in valor if chave not in propriedades)
    for chave, subesquema in propriedades.items():
        if chave in valor:
            problemas.extend(validar_contra_esquema(valor[chave], subesquema, f"{caminho}.{chave}"))
    return problemas


def _problemas_da_lista(valor: list[Any], esquema: Mapping[str, Any], caminho: str) -> list[str]:
    """Tamanho mínimo e cada item contra o esquema dos itens."""
    problemas: list[str] = []
    if len(valor) < int(esquema.get("minItems", 0)):
        problemas.append(f"{caminho}: precisa de ao menos {esquema['minItems']} item(ns)")
    itens = esquema.get("items")
    if isinstance(itens, Mapping):
        for indice, item in enumerate(valor):
            problemas.extend(validar_contra_esquema(item, itens, f"{caminho}[{indice}]"))
    return problemas
