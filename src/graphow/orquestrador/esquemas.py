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
from graphow.orquestrador.saida_do_verificador import ALCANCES, PARECERES_DA_DIFERENCA, PARECERES_DO_CONFERIDO

PAPEL_PLANEJADOR: str = "planejador"
# O autor de aceite: uma sessão separada do executor, depois do plano, que escreve os testes de aceite.
PAPEL_AUTOR_DE_ACEITE: str = "aceite"
PAPEL_EXECUTOR: str = "executor"
# O revisor da fatia de risco, e só dela: julga o diff antes do commit.
PAPEL_REVISOR: str = "revisor"
# A verificação tem três tipos, cada um com o papel, o prompt, o schema e o modelo dele (orquestrador/tipo_da_verificacao.py):
# a caçada adversarial, uma vez, na primeira verificação final; a do marco intermediário; e a conferência dos ciclos.
PAPEL_VERIFICADOR: str = "verificador"
PAPEL_VERIFICADOR_DO_MARCO: str = "marco"
PAPEL_CONFERENCIA: str = "conferencia"
# A sessão curta, sem ferramentas, que diz o que o achado sem citação fere (orquestrador/segunda_opiniao.py).
PAPEL_SEGUNDA_OPINIAO: str = "segunda_opiniao"
PAPEIS: tuple[str, ...] = (PAPEL_PLANEJADOR, PAPEL_AUTOR_DE_ACEITE, PAPEL_EXECUTOR, PAPEL_REVISOR, PAPEL_VERIFICADOR,
                           PAPEL_VERIFICADOR_DO_MARCO, PAPEL_CONFERENCIA, PAPEL_SEGUNDA_OPINIAO)
# Os prompts de papel moram no pacote e vão à sessão por `--append-system-prompt-file`:
# nada é instalado em ~/.claude para o orquestrador funcionar.
PASTA_DOS_PROMPTS: Path = Path(__file__).parent / "prompts"
LIMITE_DO_PROMPT_BYTES: int = 5 * 1024

VERIFICACOES_DE_CRITERIO: tuple[str, ...] = a.VERIFICACOES_DE_CRITERIO
MODELOS_SUGERIDOS: tuple[str, ...] = ("opus", "sonnet", "haiku")
STATUS_DO_EXECUTOR: tuple[str, ...] = ("pronto", "duvida", "falhou")
# No modo autônomo não há humano para responder: a única parada é o teste de aceite errado.
STATUS_DO_EXECUTOR_AUTONOMO: tuple[str, ...] = ("pronto", "teste_errado", "falhou")
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

# O comando de cada teste é opcional: o modelo `comando_do_teste` o monta. O JSON
# repetia o comando de cada teste, e era a maior parte do que o autor escrevia de
# saída, paga de novo em cada retomada.
TESTE_DE_ACEITE: dict[str, Any] = _objeto({"arquivo": TEXTO, "nome": TEXTO, "comando": TEXTO}, opcionais=("comando",))
ACEITE_DO_CRITERIO: dict[str, Any] = _objeto(
    {"id": TEXTO, "testes": _lista_de(TESTE_DE_ACEITE), "checagem": LISTA_DE_TEXTOS, "ja_atendido": TEXTO_LIVRE}
)
ESQUEMA_DO_ACEITE: dict[str, Any] = _objeto(
    {"resumo": TEXTO, "comando_aceite": TEXTO, "comando_do_teste": TEXTO_LIVRE, "criterios": _lista_de(ACEITE_DO_CRITERIO, 1)},
    opcionais=("comando_do_teste",),
)

PROBLEMA_DA_REVISAO: dict[str, Any] = _objeto(
    {"titulo": TEXTO, "descricao": TEXTO, "prova": PROVA, "local": TEXTO_LIVRE, "criterios": LISTA_DE_TEXTOS}
)
ESQUEMA_DA_REVISAO: dict[str, Any] = _objeto(
    {"veredito": {"type": "string", "enum": ["aprovado", "rejeitado"]}, "resumo": TEXTO,
     "problemas": _lista_de(PROBLEMA_DA_REVISAO)}
)

DECISAO_DO_AGENTE: dict[str, Any] = _objeto({"questao": TEXTO, "decisao": TEXTO, "motivo": TEXTO})
ESQUEMA_DA_EXECUCAO: dict[str, Any] = _objeto(
    {
        "status": {"type": "string", "enum": list(STATUS_DO_EXECUTOR)},
        "resumo": TEXTO,
        "arquivos": LISTA_DE_TEXTOS,
        "testes": LISTA_DE_TEXTOS,
        "duvida": TEXTO_LIVRE,
        "teste_errado": TEXTO_LIVRE,
        "decisoes": _lista_de(DECISAO_DO_AGENTE),
    },
    opcionais=("teste_errado", "decisoes"),
)
ESQUEMA_DA_EXECUCAO_AUTONOMA: dict[str, Any] = {
    **ESQUEMA_DA_EXECUCAO,
    "properties": {**ESQUEMA_DA_EXECUCAO["properties"], "status": {"type": "string", "enum": list(STATUS_DO_EXECUTOR_AUTONOMO)}},
}

PARECER: dict[str, Any] = _objeto(
    {"id": TEXTO, "veredito": {"type": "string", "enum": list(VEREDITOS_DE_CRITERIO)}, "prova": PROVA}
)
ALCANCE: Mapping[str, Any] = {"type": "string", "enum": list(ALCANCES)}
# A gravidade não vem do verificador: o código a decide pelo que o achado toca e pelo alcance
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
        "reproducao": LISTA_DE_TEXTOS,
        "alcance": ALCANCE,
        "decisao_do_limite": TEXTO_LIVRE,
    },
    opcionais=("reproducao", "decisao_do_limite"),
)
# O parecer sobre o teste de aceite que só passa com a configuração entregue (orquestrador/aceite_no_commit.py).
PARECER_DA_DIFERENCA: dict[str, Any] = _objeto(
    {"criterio": TEXTO_LIVRE, "teste": TEXTO, "parecer": {"type": "string", "enum": list(PARECERES_DA_DIFERENCA)}, "motivo": PROVA}
)
# Na conferência, o achado diz se é o achado conferido que persiste (o id dele) ou uma regressão de critério:
# o achado novo que não é nenhum dos dois não vira correção (orquestrador/tipo_da_verificacao.py).
ACHADO_DA_CONFERENCIA: dict[str, Any] = _objeto(
    {**ACHADO["properties"], "persiste": TEXTO_LIVRE, "regressao": {"type": "boolean"}},
    opcionais=("reproducao", "decisao_do_limite", "persiste", "regressao"),
)
# Na conferência, um parecer por achado conferido; só o `corrigido` o resolve.
PARECER_DO_CONFERIDO: dict[str, Any] = _objeto(
    {"achado": TEXTO, "parecer": {"type": "string", "enum": list(PARECERES_DO_CONFERIDO)}, "prova": PROVA}
)


def _esquema_da_verificacao(achado: Mapping[str, Any], extras: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """O schema de uma verificação com o achado dado e os campos a mais (os pareceres dos conferidos, na conferência).

    O verificador não declara mais os comandos: o orquestrador os tira do
    stream (orquestrador/comandos_do_stream.py). `diferencas` é opcional no
    schema; a falta do parecer pedido a conferência da saída acusa.
    """
    return _objeto(
        {
            "resumo": TEXTO,
            "criterios": _lista_de(PARECER, 1),
            "decisoes": _lista_de(PARECER),
            "achados": _lista_de(achado),
            "diferencas": _lista_de(PARECER_DA_DIFERENCA),
            **(extras or {}),
        },
        opcionais=("diferencas",),
    )


ESQUEMA_DA_VERIFICACAO: dict[str, Any] = _esquema_da_verificacao(ACHADO)
ESQUEMA_DA_CONFERENCIA: dict[str, Any] = _esquema_da_verificacao(ACHADO_DA_CONFERENCIA, {"conferidos": _lista_de(PARECER_DO_CONFERIDO)})

ESQUEMA_DA_SEGUNDA_OPINIAO: dict[str, Any] = _objeto(
    {"criterios": LISTA_DE_TEXTOS, "decisoes": LISTA_DE_TEXTOS, "alcance": ALCANCE, "motivo": TEXTO}
)

ESQUEMA_POR_PAPEL: Mapping[str, Mapping[str, Any]] = {
    PAPEL_PLANEJADOR: ESQUEMA_DO_PLANO,
    PAPEL_AUTOR_DE_ACEITE: ESQUEMA_DO_ACEITE,
    PAPEL_EXECUTOR: ESQUEMA_DA_EXECUCAO,
    PAPEL_REVISOR: ESQUEMA_DA_REVISAO,
    PAPEL_VERIFICADOR: ESQUEMA_DA_VERIFICACAO,
    PAPEL_VERIFICADOR_DO_MARCO: ESQUEMA_DA_VERIFICACAO,
    PAPEL_CONFERENCIA: ESQUEMA_DA_CONFERENCIA,
    PAPEL_SEGUNDA_OPINIAO: ESQUEMA_DA_SEGUNDA_OPINIAO,
}


def caminho_do_prompt(papel: str) -> Path:
    """O prompt de sistema do papel, no pacote."""
    return PASTA_DOS_PROMPTS / f"{papel}.md"
