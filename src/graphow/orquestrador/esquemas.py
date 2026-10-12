"""Os schemas da saída de cada papel: o que o planejador, o autor de aceite, o executor e o verificador devolvem.

Vão à sessão pelo `--json-schema` e voltam a ser conferidos em código
(orquestrador/validacao_json.py) antes de qualquer gravação. Sem `description`
nem texto livre: o schema viaja na linha de comando, e no Windows um `.cmd`
no meio leria `<`, `>`, `|` e `&` como redirecionamento.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from graphow.core import aceite as a

PAPEL_PLANEJADOR: str = "planejador"
# O autor de aceite: uma sessão separada do executor, depois do plano, que escreve os testes de aceite.
PAPEL_AUTOR_DE_ACEITE: str = "aceite"
PAPEL_EXECUTOR: str = "executor"
# O revisor da fatia de risco, e só dela: julga o diff antes do commit.
PAPEL_REVISOR: str = "revisor"
PAPEL_VERIFICADOR: str = "verificador"
PAPEIS: tuple[str, ...] = (PAPEL_PLANEJADOR, PAPEL_AUTOR_DE_ACEITE, PAPEL_EXECUTOR, PAPEL_REVISOR, PAPEL_VERIFICADOR)
# Os prompts de papel moram no pacote e vão à sessão por `--append-system-prompt-file`:
# nada é instalado em ~/.claude para o orquestrador funcionar.
PASTA_DOS_PROMPTS: Path = Path(__file__).parent / "prompts"
LIMITE_DO_PROMPT_BYTES: int = 5 * 1024

VERIFICACOES_DE_CRITERIO: tuple[str, ...] = a.VERIFICACOES_DE_CRITERIO
MODELOS_SUGERIDOS: tuple[str, ...] = ("opus", "sonnet", "haiku")
STATUS_DO_EXECUTOR: tuple[str, ...] = ("pronto", "duvida", "falhou")
VEREDITOS_DE_CRITERIO: tuple[str, ...] = a.VEREDITOS_DE_CRITERIO
SEVERIDADES: tuple[str, ...] = ("alta", "media", "baixa")

# A prova de um parecer diz o comando e o que se viu, ou o arquivo:linha: "." não é prova.
TAMANHO_MINIMO_DA_PROVA: int = 10

TEXTO: Mapping[str, Any] = {"type": "string", "minLength": 1}
PROVA: Mapping[str, Any] = {"type": "string", "minLength": TAMANHO_MINIMO_DA_PROVA}
TEXTO_LIVRE: Mapping[str, Any] = {"type": "string"}
LISTA_DE_TEXTOS: Mapping[str, Any] = {"type": "array", "items": {"type": "string"}}


def _objeto(propriedades: Mapping[str, Any], opcionais: tuple[str, ...] = ()) -> dict[str, Any]:
    """Objeto fechado: todo campo declarado, nada a mais, os não opcionais obrigatórios."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [chave for chave in propriedades if chave not in opcionais],
        "properties": dict(propriedades),
    }


def _lista_de(item: Mapping[str, Any], minimo: int = 0) -> dict[str, Any]:
    """Lista de itens do esquema dado, com tamanho mínimo."""
    return {"type": "array", "minItems": minimo, "items": dict(item)}


CRITERIO: dict[str, Any] = _objeto(
    {"id": TEXTO, "texto": TEXTO, "verificacao": {"type": "string", "enum": list(VERIFICACOES_DE_CRITERIO)}}
)
DECISAO: dict[str, Any] = _objeto({"id": TEXTO, "texto": TEXTO, "motivo": TEXTO})
FATIA: dict[str, Any] = _objeto(
    {
        "id": TEXTO,
        "titulo": TEXTO,
        "objetivo": TEXTO,
        "criterios": LISTA_DE_TEXTOS,
        "arquivos": LISTA_DE_TEXTOS,
        "depende_de": LISTA_DE_TEXTOS,
        "modelo": {"type": "string", "enum": list(MODELOS_SUGERIDOS)},
        "risco": {"type": "boolean"},
        "motivo_do_risco": TEXTO_LIVRE,
    },
    opcionais=("risco", "motivo_do_risco"),
)
MARCO: dict[str, Any] = _objeto({"id": TEXTO, "titulo": TEXTO, "fatias": LISTA_DE_TEXTOS})
ESQUEMA_DO_PLANO: dict[str, Any] = _objeto(
    {
        "titulo": TEXTO,
        "comando_suite": TEXTO,
        "criterios": _lista_de(CRITERIO, 1),
        "decisoes": _lista_de(DECISAO),
        "fatias": _lista_de(FATIA, 1),
        "marcos": _lista_de(MARCO, 1),
        "fora_do_escopo": LISTA_DE_TEXTOS,
    },
    opcionais=("fora_do_escopo",),
)

TESTE_DE_ACEITE: dict[str, Any] = _objeto({"arquivo": TEXTO, "nome": TEXTO, "comando": TEXTO})
ACEITE_DO_CRITERIO: dict[str, Any] = _objeto(
    {"id": TEXTO, "testes": _lista_de(TESTE_DE_ACEITE), "checagem": LISTA_DE_TEXTOS, "ja_atendido": TEXTO_LIVRE}
)
ESQUEMA_DO_ACEITE: dict[str, Any] = _objeto(
    {"resumo": TEXTO, "comando_aceite": TEXTO, "criterios": _lista_de(ACEITE_DO_CRITERIO, 1)}
)

PROBLEMA_DA_REVISAO: dict[str, Any] = _objeto(
    {"titulo": TEXTO, "descricao": TEXTO, "prova": PROVA, "local": TEXTO_LIVRE, "criterios": LISTA_DE_TEXTOS}
)
ESQUEMA_DA_REVISAO: dict[str, Any] = _objeto(
    {"veredito": {"type": "string", "enum": ["aprovado", "rejeitado"]}, "resumo": TEXTO,
     "problemas": _lista_de(PROBLEMA_DA_REVISAO)}
)

ESQUEMA_DA_EXECUCAO: dict[str, Any] = _objeto(
    {
        "status": {"type": "string", "enum": list(STATUS_DO_EXECUTOR)},
        "resumo": TEXTO,
        "arquivos": LISTA_DE_TEXTOS,
        "testes": LISTA_DE_TEXTOS,
        "duvida": TEXTO_LIVRE,
        "teste_errado": TEXTO_LIVRE,
    },
    opcionais=("teste_errado",),
)

PARECER: dict[str, Any] = _objeto(
    {"id": TEXTO, "veredito": {"type": "string", "enum": list(VEREDITOS_DE_CRITERIO)}, "prova": PROVA}
)
COMANDO_RODADO: dict[str, Any] = _objeto({"comando": TEXTO, "codigo": {"type": "integer"}, "saida": TEXTO})
# A gravidade não vem do verificador: o código a decide pelo que o achado toca
# (orquestrador/saida_do_verificador.py). A severidade é a opinião dele, informativa.
ACHADO: dict[str, Any] = _objeto(
    {
        "titulo": TEXTO,
        "descricao": TEXTO,
        "prova": PROVA,
        "local": TEXTO_LIVRE,
        "criterios": LISTA_DE_TEXTOS,
        "decisoes": LISTA_DE_TEXTOS,
        "severidade": {"type": "string", "enum": list(SEVERIDADES)},
    }
)
ESQUEMA_DA_VERIFICACAO: dict[str, Any] = _objeto(
    {
        "resumo": TEXTO,
        "comandos": _lista_de(COMANDO_RODADO, 1),
        "criterios": _lista_de(PARECER, 1),
        "decisoes": _lista_de(PARECER),
        "achados": _lista_de(ACHADO),
    }
)

ESQUEMA_POR_PAPEL: Mapping[str, Mapping[str, Any]] = {
    PAPEL_PLANEJADOR: ESQUEMA_DO_PLANO,
    PAPEL_AUTOR_DE_ACEITE: ESQUEMA_DO_ACEITE,
    PAPEL_EXECUTOR: ESQUEMA_DA_EXECUCAO,
    PAPEL_REVISOR: ESQUEMA_DA_REVISAO,
    PAPEL_VERIFICADOR: ESQUEMA_DA_VERIFICACAO,
}


def caminho_do_prompt(papel: str) -> Path:
    """O prompt de sistema do papel, no pacote."""
    return PASTA_DOS_PROMPTS / f"{papel}.md"
