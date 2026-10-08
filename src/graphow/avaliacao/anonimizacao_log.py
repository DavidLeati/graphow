"""Anonimização do log real para o corpus de regressão do escopo governado.

A função `anonimizar_eventos` recebe as linhas da tabela `eventos` e devolve
só o recorte que a análise de escopo lê (ver recorte_do_log.py), com a forma e
sem o conteúdo: o corpus guarda quem fez o quê e quando, nunca o que foi escrito.

Lista branca de propriedades, a única coisa que sobrevive de um nó. Tudo o que
não está aqui é descartado, inclusive o rótulo e todo texto livre.

- Categóricas (valor mantido só se for identificador em minúsculas, até 40
  caracteres, o que barra texto livre que cai num campo categórico): `status`,
  `veredito`, `acao`, `tipo`, `modelo`, `trilha`, `entrega`, `cadencia`,
  `nivel_autonomia`, `preset`, `papel_de_quem_abriu`, `respondida_por_papel`,
  `promovido_por_papel`.
- Autores, trocados por `humano-N`, `agente-N` ou `sistema`: `assumida_por`,
  `posse_retomada_de`, `aberta_por`, `respondida_por`, `promovido_por`.
- Referências, trocadas pelo id anonimizado quando o alvo está no recorte:
  `corrige`, `id_alvo`, `substitui`.
- Contagens, em vez do texto: lista ou mapa vira `n_<campo>`, texto não vazio
  vira `tem_<campo>: true`. Campos: `criterio_pronto`, `criterios`,
  `criterios_aceite`, `fora_do_escopo`, `em_aberto`, `arquivos_alvo`,
  `arquivos`, `descricao`, `motivo`, `decisao`, `pergunta`, `resposta`,
  `como_aplicar`.

Descartam-se as atualizações que, depois do filtro, não deixam propriedade
alguma, o que inclui as só de posição (`pos_x`, `pos_y`). Dos eventos de
execução ficam apenas o id do Run e o da sessão. Ids viram
`<prefixo-do-tipo>-<hash curto estável>`; o id do evento vira `ev-<seq>`.
"""

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

from graphow.avaliacao.recorte_do_log import (
    CAMPOS_DE_REFERENCIA,
    EventoBruto,
    Recorte,
    calcular_recorte,
    eventos_brutos,
    id_do_run,
    levantar_historia,
)

SAL: str = "graphow-corpus-escopo-v1"
PREFIXO_POR_TIPO: dict[str, str] = {
    "Task": "task", "Goal": "goal", "Decision": "dec", "Evidence": "evid", "Question": "quest",
    "Constraint": "restr", "Artifact": "art", "Sessao": "sess", "Run": "run", "Setor": "setor",
    "Projeto": "proj", "Note": "nota", "Aprendizado": "apr", "Governanca": "gov",
}
CATEGORICAS: frozenset[str] = frozenset({
    "status", "veredito", "acao", "tipo", "modelo", "trilha", "entrega", "cadencia",
    "nivel_autonomia", "preset", "papel_de_quem_abriu", "respondida_por_papel", "promovido_por_papel",
})
AUTORES: frozenset[str] = frozenset({
    "assumida_por", "posse_retomada_de", "aberta_por", "respondida_por", "promovido_por",
})
CONTAGENS: frozenset[str] = frozenset({
    "criterio_pronto", "criterios", "criterios_aceite", "fora_do_escopo", "em_aberto",
    "arquivos_alvo", "arquivos", "descricao", "motivo", "decisao", "pergunta", "resposta", "como_aplicar",
})
IDENTIFICADOR = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
TAMANHO_INICIAL_DO_HASH: int = 6


class Pseudonimos:
    """Troca ids por prefixo e hash estável, alongando o hash se dois ids colidirem."""

    def __init__(self) -> None:
        self._por_original: dict[str, str] = {}
        self._por_pseudonimo: dict[str, str] = {}

    def atribuir(self, original: str, prefixo: str) -> str:
        """Pseudônimo do id, o mesmo em toda chamada com o mesmo original."""
        if original in self._por_original:
            return self._por_original[original]
        digest = hashlib.sha256(f"{SAL}:{original}".encode("utf-8")).hexdigest()
        tamanho = TAMANHO_INICIAL_DO_HASH
        while self._por_pseudonimo.get(f"{prefixo}-{digest[:tamanho]}", original) != original:
            tamanho += 2
        pseudonimo = f"{prefixo}-{digest[:tamanho]}"
        self._por_original[original] = pseudonimo
        self._por_pseudonimo[pseudonimo] = original
        return pseudonimo


class RotulosDeAutor:
    """`humano-N`, `agente-N` ou `sistema`, na ordem em que cada autor aparece."""

    def __init__(self, papeis_por_autor: Mapping[str, set[str]]) -> None:
        self._papeis = papeis_por_autor
        self._rotulos: dict[str, str] = {}
        self._contagem: dict[str, int] = {}

    def de(self, autor: str) -> str:
        """Rótulo anônimo do autor, sem nada do nome original."""
        if autor not in self._rotulos:
            self._rotulos[autor] = self._novo(self._categoria(autor))
        return self._rotulos[autor]

    def _categoria(self, autor: str) -> str:
        """Humano só se o autor nunca agiu noutro papel; sistema só se agiu apenas como tal."""
        papeis = self._papeis.get(autor, set())
        if papeis == {"humano"}:
            return "humano"
        return "sistema" if papeis == {"sistema"} else "agente"

    def _novo(self, categoria: str) -> str:
        """Próximo rótulo da categoria; o sistema é um só."""
        if categoria == "sistema":
            return categoria
        self._contagem[categoria] = self._contagem.get(categoria, 0) + 1
        return f"{categoria}-{self._contagem[categoria]}"


def papeis_por_autor(linhas: Sequence[Mapping[str, Any]]) -> dict[str, set[str]]:
    """Papéis com que cada autor escreveu no log inteiro."""
    papeis: dict[str, set[str]] = {}
    for linha in linhas:
        papeis.setdefault(str(linha["autor"]), set()).add(str(linha["papel"]))
    return papeis


class Anonimizador:
    """Converte evento a evento, mantendo os mesmos pseudônimos de ponta a ponta."""

    def __init__(self, recorte: Recorte, autores: RotulosDeAutor) -> None:
        self._recorte = recorte
        self._autores = autores
        self._ids: dict[str, str] = {}
        pseudonimos = Pseudonimos()
        for id_no in sorted(recorte.nos):
            self._ids[id_no] = pseudonimos.atribuir(id_no, PREFIXO_POR_TIPO.get(recorte.nos[id_no], "no"))
        for id_aresta in sorted(recorte.arestas):
            self._ids[id_aresta] = pseudonimos.atribuir(id_aresta, "aresta")

    def converter(self, linha: Mapping[str, Any], bruto: EventoBruto) -> dict[str, Any] | None:
        """Evento anonimizado, ou None quando ele fica fora do recorte ou nada guarda."""
        payload = self._payload(bruto)
        if payload is None:
            return None
        return {
            "seq": bruto.seq,
            "timestamp_utc": str(linha["timestamp_utc"]),
            "autor": self._autores.de(str(linha["autor"])),
            "papel": str(linha["papel"]),
            "origem": str(linha["origem"]),
            "tipo_evento": bruto.tipo_evento,
            "payload": payload,
            "versao_ontologia": linha["versao_ontologia"],
        }

    def _payload(self, bruto: EventoBruto) -> dict[str, Any] | None:
        """Payload anonimizado do evento, escolhido pelo tipo."""
        if bruto.tipo_evento.startswith("execucao_"):
            return self._payload_de_execucao(bruto)
        carga = bruto.payload
        if bruto.tipo_evento.startswith("aresta_"):
            return self._payload_de_aresta(bruto.tipo_evento, carga)
        if str(carga.get("id")) not in self._recorte.nos:
            return None
        if bruto.tipo_evento == "no_removido":
            return {"id": self._ids[str(carga["id"])]}
        return self._payload_de_no(bruto.tipo_evento, carga)

    def _payload_de_no(self, tipo_evento: str, carga: Mapping[str, Any]) -> dict[str, Any] | None:
        """Criação ou atualização de nó: só as propriedades da lista branca."""
        id_no = str(carga["id"])
        propriedades = self.propriedades(carga.get("propriedades") or {})
        removidas = self.nomes_removidos(carga.get("propriedades_removidas") or ())
        if tipo_evento == "no_criado":
            return {"id": self._ids[id_no], "tipo": carga["tipo"], "propriedades": propriedades}
        if not propriedades and not removidas:
            return None
        saida: dict[str, Any] = {"id": self._ids[id_no], "propriedades": propriedades}
        if removidas:
            saida["propriedades_removidas"] = removidas
        return saida

    def _payload_de_aresta(self, tipo_evento: str, carga: Mapping[str, Any]) -> dict[str, Any] | None:
        """Aresta só entra se foi escolhida no recorte, o que garante as duas pontas."""
        id_aresta = str(carga["id"])
        if id_aresta not in self._recorte.arestas:
            return None
        if tipo_evento == "aresta_removida":
            return {"id": self._ids[id_aresta]}
        return {
            "id": self._ids[id_aresta],
            "origem_id": self._ids[str(carga["origem_id"])],
            "destino_id": self._ids[str(carga["destino_id"])],
            "tipo": carga["tipo"],
        }

    def _payload_de_execucao(self, bruto: EventoBruto) -> dict[str, Any] | None:
        """Do Run ficam o id e a sessão; o resto do payload é texto do harness."""
        id_run = id_do_run(bruto)
        if id_run not in self._recorte.nos:
            return None
        saida = {"id": self._ids[id_run]}
        sessao = str(bruto.payload.get("id_sessao") or "")
        if sessao in self._recorte.nos:
            saida["id_sessao"] = self._ids[sessao]
        return saida

    def propriedades(self, propriedades: Mapping[str, Any]) -> dict[str, Any]:
        """Aplica a lista branca às propriedades de um nó."""
        saida: dict[str, Any] = {}
        for chave, valor in propriedades.items():
            saida.update(self._valor(str(chave), valor))
        return saida

    def _valor(self, chave: str, valor: Any) -> dict[str, Any]:
        """Uma propriedade convertida, ou vazio se ela não pode sair do banco."""
        if chave in CONTAGENS:
            return _contagem(chave, valor)
        if valor is None and (chave in CATEGORICAS or chave in AUTORES or chave in CAMPOS_DE_REFERENCIA):
            return {chave: None}
        if chave in CATEGORICAS:
            return {chave: valor} if isinstance(valor, str) and IDENTIFICADOR.match(valor) else {}
        if chave in AUTORES:
            return {chave: self._autores.de(valor)} if isinstance(valor, str) else {}
        if chave in CAMPOS_DE_REFERENCIA:
            return {chave: self._ids[valor]} if isinstance(valor, str) and valor in self._ids else {}
        return {}

    def nomes_removidos(self, chaves: Sequence[str]) -> list[str]:
        """Nomes de propriedade removida que o corpus conhece, já na forma em que foram gravados."""
        nomes: list[str] = []
        for chave in map(str, chaves):
            nomes += _nomes_gravados(chave)
        return nomes


def _nomes_gravados(chave: str) -> list[str]:
    """Como a propriedade de origem aparece no corpus: contagem vira dois nomes."""
    if chave in CONTAGENS:
        return [f"n_{chave}", f"tem_{chave}"]
    if chave in CATEGORICAS or chave in AUTORES or chave in CAMPOS_DE_REFERENCIA:
        return [chave]
    return []


def _contagem(chave: str, valor: Any) -> dict[str, Any]:
    """Tamanho da lista ou do mapa; presença do texto. Nunca o conteúdo."""
    if isinstance(valor, (list, tuple, dict)):
        return {f"n_{chave}": len(valor)}
    if isinstance(valor, str) and valor.strip():
        return {f"tem_{chave}": True}
    return {}


def anonimizar_eventos(linhas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Recorta e anonimiza as linhas da tabela `eventos`, na ordem de `seq`."""
    ordenadas = sorted(linhas, key=lambda linha: int(linha["seq"]))
    brutos = eventos_brutos(ordenadas)
    recorte = calcular_recorte(levantar_historia(brutos))
    anonimizador = Anonimizador(recorte, RotulosDeAutor(papeis_por_autor(ordenadas)))
    convertidos = (anonimizador.converter(linha, bruto) for linha, bruto in zip(ordenadas, brutos))
    return [evento for evento in convertidos if evento is not None]
