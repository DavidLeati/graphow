"""A saída do verificador como objeto tipado: os pareceres, os comandos e os achados, com a gravidade decidida pelo código.

No portão da fase 1 os verificadores acharam os defeitos que o auditor depois
chamou de bloqueantes (o título contado em unidades UTF-16 contra "até 200
caracteres", a quantidade negativa que aumentava o saldo, o CSV em ANSI com
traceback), mas os classificaram como acompanhamento, e o Goal fechou com eles.
Por isso o verificador não diz mais a gravidade: diz, por achado, os critérios
e as decisões que ele toca (a lista pode ser vazia), a prova e o alcance. O
código decide: o achado que toca critério ou decisão é bloqueante, inclusive o
defeito que "já existia antes", quando é de uso previsto; o que não toca nada
e o de entrada extrema são acompanhamento. Na bancada de 12/10 a regra sem o
alcance virou esteira: cada verificação caçava uma borda patológica nova (NUL,
surrogate, id de 4300 dígitos, a última semana de 9999), toda borda tocava
algum critério, e nenhum Goal fechou. Extremo é a entrada patológica de cujo
limite nenhuma decisão fala; quando uma fala (D3, "não ocupar a sala para
sempre", diante de uma série até 9999), o verificador a cita em
`decisao_do_limite`, e o achado é de uso previsto e toca a decisão. Rebaixar
a extremo exige que a segunda opinião concorde (orquestrador/segunda_opiniao.py).
O que o próprio orquestrador viu falhar (a suíte, o teste de aceite) é
bloqueante por origem. A `severidade` que o verificador sugere fica gravada,
informativa, e não muda o destino.

Uma verificação abre no máximo 5 bloqueantes (`TETO_DE_BLOQUEANTES`): o
primeiro marco da agenda, na bancada, abriu 12, e cada correção trazia bordas
novas. Os de maior prioridade ficam; o resto vira acompanhamento marcado
"excedeu o teto do ciclo", visível nas pendências, e volta a bloquear se uma
verificação seguinte o achar de novo.

Na conferência, que roda depois de cada ciclo de correção, a gravidade tem
mais uma regra (orquestrador/tipo_da_verificacao.py): cada achado conferido
ganha um parecer, `corrigido` ou `persiste`, com a prova, e faltar um é saída
inválida; o que persiste é bloqueante; o achado novo só vale se for regressão
de critério (`regressao`), e o que não é vira acompanhamento marcado "achado
novo da conferencia, sem regressao". Na bancada de 12/10, cada verificação
depois de uma correção era outra caçada, que achava bordas novas, e o laço não
convergia.

Quando a configuração de teste entregue faz passar um teste de aceite que a do
commit do aceite reprova fora de uma asserção (import, coleta, ambiente), o
verificador julga a diferença: cada uma pede um parecer, `legitima` ou
`ilegitima`, com o motivo, e faltar parecer é saída inválida
(orquestrador/aceite_no_commit.py).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from graphow.core import aceite as a

ORIGEM_DO_VERIFICADOR: str = "verificador"
ORIGEM_DO_ORQUESTRADOR: str = "orquestrador"
ORIGEM_DA_REVISAO: str = "revisao_de_risco"
TITULO_DA_SUITE_VERMELHA: str = "A suite do plano falhou no commit verificado"
# Quanto do fim da saída vai como prova do achado que o orquestrador registra.
LIMITE_DA_PROVA: int = 2000
PARECER_LEGITIMA: str = "legitima"
PARECER_ILEGITIMA: str = "ilegitima"
PARECERES_DA_DIFERENCA: tuple[str, ...] = (PARECER_LEGITIMA, PARECER_ILEGITIMA)
# De onde vem a entrada que dispara o achado: do uso que a spec, as decisões ou um usuário normal produzem, ou de um extremo.
ALCANCE_USO_PREVISTO: str = "uso_previsto"
ALCANCE_EXTREMO: str = "extremo"
ALCANCES: tuple[str, ...] = (ALCANCE_USO_PREVISTO, ALCANCE_EXTREMO)
# Quantos bloqueantes uma verificação abre no máximo; os que passam disso ficam visíveis como acompanhamento.
TETO_DE_BLOQUEANTES: int = 5
MARCA_DO_TETO: str = "excedeu o teto do ciclo"
MARCA_DA_CONFERENCIA: str = "achado novo da conferencia, sem regressao"
# O que a conferência diz de cada achado conferido: só o `corrigido` o resolve.
PARECER_CORRIGIDO: str = "corrigido"
PARECER_PERSISTE: str = "persiste"
PARECERES_DO_CONFERIDO: tuple[str, ...] = (PARECER_CORRIGIDO, PARECER_PERSISTE)


def _textos(valor: object) -> tuple[str, ...]:
    """A lista de textos do JSON, sem vazios."""
    return tuple(str(item).strip() for item in valor if str(item).strip()) if isinstance(valor, list) else ()


def alcance_de(valor: object) -> str:
    """O alcance dito; o que falta ou não é um dos dois é uso previsto, o que não rebaixa nada."""
    return ALCANCE_EXTREMO if str(valor or "").strip() == ALCANCE_EXTREMO else ALCANCE_USO_PREVISTO


@dataclass(frozen=True)
class Parecer:
    """O veredito do verificador sobre um critério ou uma decisão, com a prova."""

    id: str
    veredito: str
    prova: str


@dataclass(frozen=True)
class ParecerDaDiferenca:
    """O que o verificador julgou de um teste de aceite que só passa com a configuração entregue."""

    criterio: str
    teste: str
    parecer: str
    motivo: str

    @property
    def chave(self) -> tuple[str, str]:
        """O critério e o teste, como a diferença os tem."""
        return (self.criterio, self.teste)

    def em_json(self) -> dict[str, str]:
        """O parecer para gravar com a diferença."""
        return {"parecer": self.parecer, "motivo_do_parecer": self.motivo}

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "ParecerDaDiferenca":
        """O parecer como o verificador o devolveu."""
        return cls(str(dados.get("criterio", "")).strip(), str(dados["teste"]).strip(), str(dados["parecer"]),
                   str(dados["motivo"]).strip())


@dataclass(frozen=True)
class ParecerDoConferido:
    """O que a conferência diz de um achado conferido: corrigido ou persiste, com a prova."""

    achado: str
    parecer: str
    prova: str

    @property
    def persiste(self) -> bool:
        """A conferência reproduziu o achado."""
        return self.parecer == PARECER_PERSISTE

    def em_json(self) -> dict[str, str]:
        """O parecer para gravar na verificação."""
        return {"achado": self.achado, "parecer": self.parecer, "prova": self.prova}

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "ParecerDoConferido":
        """O parecer como a conferência o devolveu."""
        return cls(str(dados["achado"]).strip(), str(dados["parecer"]).strip(), str(dados.get("prova", "")).strip())


@dataclass(frozen=True)
class Achado:
    """Um problema achado na verificação: o que é, a prova, onde, o que ele toca, o alcance e de quem veio."""

    titulo: str
    descricao: str
    prova: str = ""
    local: str = ""
    criterios: tuple[str, ...] = ()
    decisoes: tuple[str, ...] = ()
    severidade: str = ""
    origem: str = ORIGEM_DO_VERIFICADOR
    segunda_opiniao: str = ""
    sem_acordo: bool = False
    reproducao: tuple[str, ...] = ()
    alcance: str = ALCANCE_USO_PREVISTO
    decisao_do_limite: str = ""
    # Vazio quando a segunda opinião não julgou o achado.
    alcance_da_segunda_opiniao: str = ""
    excedeu_o_teto: bool = False
    # Na conferência: o id do achado conferido que persiste, a regressão de critério e o achado novo que não é nenhum dos dois.
    persiste: str = ""
    regressao: bool = False
    novo_na_conferencia: bool = False

    @property
    def toca(self) -> tuple[str, ...]:
        """Os critérios e as decisões que o achado toca, sem repetir; a decisão que fala do limite inclusive."""
        return tuple(dict.fromkeys((*self.criterios, *self.decisoes, *((self.decisao_do_limite,) if self.decisao_do_limite else ()))))

    @property
    def extremo(self) -> bool:
        """Entrada extrema de cujo limite nenhuma decisão fala, sem a segunda opinião dizer que é de uso previsto."""
        return (self.alcance == ALCANCE_EXTREMO and not self.decisao_do_limite
                and self.alcance_da_segunda_opiniao != ALCANCE_USO_PREVISTO)

    @property
    def gravidade(self) -> str:
        """Bloqueante quando o orquestrador viu falhar, quando a segunda opinião não concordou ou quando toca algo e não é extremo.

        O que passou do teto da verificação e o achado novo da conferência que não
        é regressão são acompanhamento, sejam o que forem; o achado conferido que
        persiste é bloqueante, como era.
        """
        if self.excedeu_o_teto or self.novo_na_conferencia:
            return a.GRAVIDADE_ACOMPANHAMENTO
        if self.persiste or self.origem == ORIGEM_DO_ORQUESTRADOR or self.sem_acordo or (self.toca and not self.extremo):
            return a.GRAVIDADE_BLOQUEANTE
        return a.GRAVIDADE_ACOMPANHAMENTO

    def em_json(self) -> dict[str, Any]:
        """O achado para a lista de pendências e para o nó Achado."""
        return {"gravidade": self.gravidade, "titulo": self.titulo, "descricao": self.descricao, "prova": self.prova,
                "local": self.local, "criterios": list(self.criterios), "decisoes": list(self.decisoes),
                "severidade": self.severidade, "origem": self.origem, "segunda_opiniao": self.segunda_opiniao,
                "reproducao": list(self.reproducao), "alcance": self.alcance, "decisao_do_limite": self.decisao_do_limite,
                "alcance_da_segunda_opiniao": self.alcance_da_segunda_opiniao, "persiste": self.persiste,
                "regressao": self.regressao, "marca": self.marca}

    @property
    def marca(self) -> str:
        """Por que o código rebaixou o achado que tocava algo; vazio quando não rebaixou."""
        return MARCA_DO_TETO if self.excedeu_o_teto else MARCA_DA_CONFERENCIA if self.novo_na_conferencia and self.toca else ""

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "Achado":
        """O achado como o verificador o devolveu; sem alcance, de uso previsto."""
        return cls(
            titulo=str(dados["titulo"]).strip(), descricao=str(dados["descricao"]).strip(),
            prova=str(dados.get("prova", "")).strip(), local=str(dados.get("local", "")).strip(),
            criterios=_textos(dados.get("criterios")), decisoes=_textos(dados.get("decisoes")),
            severidade=str(dados.get("severidade", "")), reproducao=_textos(dados.get("reproducao")),
            alcance=alcance_de(dados.get("alcance")), decisao_do_limite=str(dados.get("decisao_do_limite", "") or "").strip(),
            persiste=str(dados.get("persiste", "") or "").strip(), regressao=dados.get("regressao") is True,
        )


@dataclass(frozen=True)
class ComandoRodado:
    """Um comando que o verificador rodou: o que, com que código saiu e um trecho do que imprimiu."""

    comando: str
    codigo: int
    saida: str

    def em_json(self) -> dict[str, Any]:
        """O comando para gravar na Evidence."""
        return {"comando": self.comando, "codigo": self.codigo, "saida": self.saida}


def _comandos(valor: object) -> tuple[ComandoRodado, ...]:
    """Os comandos rodados do JSON; a falta deles é problema da conferência, não da leitura."""
    itens = valor if isinstance(valor, list) else []
    return tuple(ComandoRodado(str(c["comando"]).strip(), int(c["codigo"]), str(c["saida"]).strip()) for c in itens)


def _parecer(item: Mapping[str, Any]) -> Parecer:
    """Um parecer do JSON."""
    return Parecer(str(item["id"]).strip(), str(item["veredito"]), str(item["prova"]).strip())


@dataclass(frozen=True)
class Verificacao:
    """O que o verificador devolveu de um marco, ou do Goal inteiro na verificação final."""

    resumo: str
    criterios: tuple[Parecer, ...]
    decisoes: tuple[Parecer, ...] = ()
    achados: tuple[Achado, ...] = field(default_factory=tuple)
    comandos: tuple[ComandoRodado, ...] = ()
    diferencas: tuple[ParecerDaDiferenca, ...] = ()
    conferidos: tuple[ParecerDoConferido, ...] = ()

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "Verificacao":
        """A verificação como o verificador a devolveu."""
        return cls(
            resumo=str(dados["resumo"]).strip(),
            criterios=tuple(_parecer(item) for item in dados["criterios"]),
            decisoes=tuple(_parecer(item) for item in dados.get("decisoes", [])),
            achados=tuple(Achado.de_json(item) for item in dados["achados"]),
            comandos=_comandos(dados.get("comandos")),
            diferencas=tuple(ParecerDaDiferenca.de_json(item) for item in dados.get("diferencas", [])),
            conferidos=tuple(ParecerDoConferido.de_json(item) for item in dados.get("conferidos", [])),
        )

    @property
    def confirmados(self) -> tuple[str, ...]:
        """Os achados conferidos que a conferência deu por corrigidos."""
        return tuple(parecer.achado for parecer in self.conferidos if not parecer.persiste)

    def com_achado_do_orquestrador(self, titulo: str, descricao: str, criterios: tuple[str, ...] = ()) -> "Verificacao":
        """A verificação com o que o orquestrador viu falhar no commit verificado (a suíte, um teste de aceite)."""
        achado = Achado(titulo, descricao, descricao[-LIMITE_DA_PROVA:], criterios=criterios, origem=ORIGEM_DO_ORQUESTRADOR)
        return replace(self, achados=(*self.achados, achado))

    def com_parecer(self, id_criterio: str, veredito: str, prova: str) -> "Verificacao":
        """A verificação com o parecer do critério trocado pelo que o orquestrador viu."""
        pareceres = tuple(Parecer(id_criterio, veredito, prova) if p.id == id_criterio else p for p in self.criterios)
        return replace(self, criterios=pareceres)

    def bloqueantes(self) -> tuple[Achado, ...]:
        """Os bloqueantes dentro do teto, na ordem de sempre."""
        return self._no_teto()[0]

    def _no_teto(self) -> tuple[tuple[Achado, ...], tuple[Achado, ...]]:
        """Os bloqueantes dentro do teto e os que passaram dele, marcados.

        Ficam os de maior prioridade: os que o orquestrador viu falhar (a suíte,
        o teste de aceite, o critério reprovado sem achado), que são fato, e
        depois os do verificador, na ordem em que ele os listou. Com até o teto,
        nada muda; a saída mantém a ordem, e o id de cada nó Achado com ela.
        """
        candidatos = self._candidatos()
        ordem = sorted(range(len(candidatos)), key=lambda i: candidatos[i].origem != ORIGEM_DO_ORQUESTRADOR)
        dentro = set(ordem[:TETO_DE_BLOQUEANTES])
        return (tuple(c for i, c in enumerate(candidatos) if i in dentro),
                tuple(replace(c, excedeu_o_teto=True) for i, c in enumerate(candidatos) if i not in dentro))

    def _candidatos(self) -> tuple[Achado, ...]:
        """Os achados bloqueantes e, para o critério ou decisão sem `atende` que nenhum bloqueante toca, um sintético.

        O critério reprovado que só um achado extremo toca ganha o sintético:
        sem ele, a verificação não teria o que corrigir e ainda assim não fecharia.
        """
        declarados = tuple(achado for achado in self.achados if achado.gravidade == a.GRAVIDADE_BLOQUEANTE)
        tocados = {id_c for achado in declarados for id_c in achado.toca}
        sinteticos = tuple(
            Achado(f"{parecer.id} {parecer.veredito}", parecer.prova, parecer.prova, "", *_lados(parecer.id),
                   origem=ORIGEM_DO_ORQUESTRADOR)
            for parecer in (*self.criterios, *self.decisoes)
            if parecer.veredito != a.VEREDITO_QUE_ATENDE and parecer.id not in tocados
        )
        return declarados + sinteticos

    def acompanhamentos(self) -> tuple[Achado, ...]:
        """Os achados que não tocam critério nem decisão, os de entrada extrema e, marcados, os bloqueantes que passaram do teto."""
        return tuple(achado for achado in self.achados if achado.gravidade == a.GRAVIDADE_ACOMPANHAMENTO) + self._no_teto()[1]

    def achados_finais(self) -> tuple[Achado, ...]:
        """Os bloqueantes e depois os acompanhamentos, na ordem em que viram nós Achado."""
        return self.bloqueantes() + self.acompanhamentos()


def _lados(id_parecer: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """O parecer de critério toca o critério; o de decisão (D...), a decisão."""
    return ((), (id_parecer,)) if id_parecer.upper().startswith("D") else ((id_parecer,), ())


def conferir_verificacao(
    verificacao: Verificacao, criterios: Sequence[str], decisoes: Sequence[str], *, conhecidos: Sequence[str] | None = None,
    diferencas: Sequence[tuple[str, str]] = (), conferidos: Sequence[str] = (),
) -> tuple[str, ...]:
    """Um parecer por critério, por decisão e por diferença de configuração pedidos, e achado que toca só o que pode tocar.

    O que o achado pode tocar é o que a verificação julga, ou, quando dito, os
    critérios já entregues e as decisões (`conhecidos`). Na conferência, um
    parecer por achado conferido. Os comandos vêm do stream.
    """
    dados = [parecer.id for parecer in verificacao.criterios]
    dadas = [parecer.id for parecer in verificacao.decisoes]
    tocaveis = set(conhecidos) if conhecidos is not None else {*criterios, *decisoes}
    return (
        *(f"falta o parecer do criterio {id_c}" for id_c in criterios if id_c not in dados),
        *(f"falta o parecer da decisao {id_d}" for id_d in decisoes if id_d not in dadas),
        *(f"parecer {id_p} repetido" for id_p in sorted({i for i in dados + dadas if (dados + dadas).count(i) > 1})),
        *(
            f"o achado '{achado.titulo}' toca {id_c}, que nao e criterio nem decisao desta verificacao"
            for achado in verificacao.achados for id_c in achado.toca if id_c not in tocaveis
        ),
        *_conferir_diferencas(verificacao.diferencas, diferencas),
        *_conferir_os_conferidos(verificacao, conferidos),
    )


def _conferir_os_conferidos(verificacao: Verificacao, conferidos: Sequence[str]) -> tuple[str, ...]:
    """Um parecer por achado conferido, sem repetir nem inventar, e o `persiste` do achado só com um conferido que persiste."""
    dados = [parecer.achado for parecer in verificacao.conferidos]
    corrigidos = set(verificacao.confirmados)
    return (
        *(f"falta o parecer do achado conferido {id_a} (corrigido ou persiste)" for id_a in conferidos if id_a not in dados),
        *(f"parecer do achado conferido {id_a} repetido" for id_a in sorted({i for i in dados if dados.count(i) > 1})),
        *(f"o parecer de {id_a} nao corresponde a nenhum achado conferido" for id_a in dados if id_a not in conferidos),
        *(f"o achado '{achado.titulo}' persiste {achado.persiste}, que nao e achado conferido"
          for achado in verificacao.achados if achado.persiste and achado.persiste not in conferidos),
        *(f"o achado '{achado.titulo}' persiste {achado.persiste}, e o parecer dele diz corrigido"
          for achado in verificacao.achados if achado.persiste in corrigidos),
    )


def _conferir_diferencas(dados: Sequence[ParecerDaDiferenca], pedidas: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    """Um parecer por diferença pedida, sem repetir e sem parecer de diferença que o pedido não trouxe."""
    chaves = [parecer.chave for parecer in dados]
    return (
        *(f"falta o parecer da diferenca de configuracao do teste {teste} de {criterio or 'todos'}"
          for criterio, teste in pedidas if (criterio, teste) not in chaves),
        *(f"parecer da diferenca do teste {teste} de {criterio or 'todos'} repetido"
          for criterio, teste in sorted({c for c in chaves if chaves.count(c) > 1})),
        *(f"o parecer da diferenca do teste {teste} de {criterio or 'todos'} nao corresponde a nenhuma diferenca do pedido"
          for criterio, teste in chaves if (criterio, teste) not in pedidas),
    )
