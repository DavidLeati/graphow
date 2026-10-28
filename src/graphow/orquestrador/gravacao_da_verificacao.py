"""A verificação gravada no livro-razão: a Evidence, um nó Achado por problema, o estado dos critérios e as pendências, num lote só.

A Evidence de verificação deriva do Goal e guarda o número, o marco, se é a
final, o commit e o commit do código verificados, os comandos do verificador,
a suíte e os testes de aceite que o orquestrador rodou, e um parecer por
critério e decisão com o nó de cada um. Cada achado vira um nó Achado que
deriva da Evidence e fere (`fere`) os critérios e as decisões que toca, com a
gravidade que o código decidiu: o bloqueante nasce aberto e vai virar fatia de
correção, o acompanhamento nasce pendente e fica como pendência do Goal. Nunca
uma Note. No mesmo lote, cada Criterio julgado ganha o estado do parecer, e,
quando a verificação sai limpa, os achados que as correções do marco
entregaram passam a resolvidos.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from graphow.core import aceite as a
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal, aresta, propriedade
from graphow.orquestrador.saida_do_verificador import Achado, Verificacao
from graphow.orquestrador.suite import LIMITE_DO_TRECHO, ResultadoDaSuite


@dataclass(frozen=True)
class RegistroDaVerificacao:
    """O que a verificação deixa no livro-razão: o número, o commit verificado, o parecer e o que o orquestrador rodou."""

    numero: int
    verificacao: Verificacao
    commit: str
    commit_do_codigo: str
    suite: ResultadoDaSuite
    nos: Mapping[str, str] = field(default_factory=dict)
    pendencias: Sequence[Mapping[str, Any]] = ()
    ciclo: int = 0
    final: bool = True
    marco: str = ""
    aceite: Sequence[Mapping[str, Any]] = ()
    resolver: Sequence[str] = ()
    tirado_antes_do_aceite: Sequence[str] = ()
    configuracao_do_aceite: Sequence[str] = ()
    aceite_com_a_configuracao_do_aceite: Sequence[Mapping[str, Any]] = ()
    diferencas_de_configuracao: Sequence[Mapping[str, Any]] = ()

    @property
    def limpa(self) -> bool:
        """Sem bloqueante."""
        return not self.verificacao.bloqueantes()

    def propriedades(self, id_goal: str) -> dict[str, Any]:
        """As propriedades da Evidence; cada parecer leva o nó do critério ou da decisão que julga."""
        verificacao, suite = self.verificacao, self.suite
        return {
            "acao": m.ACAO_DA_VERIFICACAO, m.CAMPO_VEREDITO: m.VEREDITO_LIMPO if self.limpa else m.VEREDITO_COM_BLOQUEANTE,
            m.CAMPO_NUMERO: self.numero, m.CAMPO_FINAL: self.final, a.CAMPO_MARCO: self.marco,
            m.CAMPO_COMMIT: self.commit, m.CAMPO_COMMIT_DO_CODIGO: self.commit_do_codigo, m.CAMPO_CICLO: self.ciclo,
            "fonte": "graphow orquestrar: sessao do verificador",
            "resumo": verificacao.resumo,
            "comandos": [comando.em_json() for comando in verificacao.comandos],
            "suite_do_orquestrador": {"comando": suite.comando, "shell": suite.shell, "codigo": suite.codigo, "passou": suite.passou,
                                      "tempo_esgotado": suite.tempo_esgotado, "saida": suite.saida[-LIMITE_DO_TRECHO:]},
            "aceite_do_orquestrador": [dict(item) for item in self.aceite],
            "tirado_antes_do_aceite": list(self.tirado_antes_do_aceite),
            "configuracao_do_aceite": list(self.configuracao_do_aceite),
            "aceite_com_a_configuracao_do_aceite": [dict(item) for item in self.aceite_com_a_configuracao_do_aceite],
            "diferencas_de_configuracao": [dict(item) for item in self.diferencas_de_configuracao],
            m.CAMPO_PARECERES: [{"id": p.id, "no": self.nos.get(p.id, ""), "veredito": p.veredito, "prova": p.prova}
                                for p in (*verificacao.criterios, *verificacao.decisoes)],
            "achados": [id_achado for id_achado, _ in self.achados(id_goal)],
        }

    def achados(self, id_goal: str) -> list[tuple[str, Achado]]:
        """Os achados que viram nós, com o id de cada um: os bloqueantes e depois os acompanhamentos."""
        return [(m.id_do_achado(id_goal, self.numero, indice), achado)
                for indice, achado in enumerate(self.verificacao.achados_finais(), start=1)]


def gravar_verificacao(livro: LivroRazaoDoGoal, registro: RegistroDaVerificacao) -> str:
    """Grava a verificação inteira num lote; devolve o id da Evidence."""
    id_evidencia = m.id_da_verificacao(livro.id_goal, registro.numero)
    bloqueantes = len(registro.verificacao.bloqueantes())
    alvo = f"marco {registro.marco}" if registro.marco and not registro.final else "Goal inteiro"
    rotulo = f"Verificacao {registro.numero} ({alvo}) em {registro.commit[:12]}: " + (f"{bloqueantes} bloqueante(s)" if bloqueantes else "limpa")
    operacoes = [
        *livro.produzido(id_evidencia, TipoNo.EVIDENCE, rotulo, propriedades=registro.propriedades(livro.id_goal)),
        aresta(id_evidencia, livro.id_goal, TipoAresta.DERIVA_DE),
        *_operacoes_dos_achados(livro, registro, id_evidencia),
        *_estado_dos_criterios(livro, registro),
        *(propriedade(id_achado, a.CAMPO_ESTADO, a.ESTADO_RESOLVIDO) for id_achado in (registro.resolver if registro.limpa else ())),
        propriedade(livro.id_goal, m.CAMPO_PENDENCIAS, [dict(item) for item in registro.pendencias]),
    ]
    livro.gravar(operacoes, f"Verificacao {registro.numero} do Goal {livro.id_goal}")
    return id_evidencia


def _operacoes_dos_achados(livro: LivroRazaoDoGoal, registro: RegistroDaVerificacao, id_evidencia: str) -> list[ItemPatch]:
    """Cada achado num nó que deriva da verificação e fere o que toca (o Criterio e a Decision; a Constraint de antes, não)."""
    view = livro.view()
    feriveis = {codigo: id_no for codigo, id_no in registro.nos.items()
                if (no := view.obter_no(id_no)) is not None and no.tipo in (TipoNo.CRITERIO, TipoNo.DECISION)}
    operacoes: list[ItemPatch] = []
    for id_achado, achado in registro.achados(livro.id_goal):
        estado = a.ESTADO_ABERTO if achado.gravidade == a.GRAVIDADE_BLOQUEANTE else a.ESTADO_DO_ACOMPANHAMENTO
        propriedades = {**achado.em_json(), a.CAMPO_ESTADO: estado, "verificacao": id_evidencia, a.CAMPO_MARCO: registro.marco}
        operacoes += livro.produzido(id_achado, TipoNo.ACHADO, f"[{achado.gravidade}] {achado.titulo}", propriedades=propriedades)
        operacoes.append(aresta(id_achado, id_evidencia, TipoAresta.DERIVA_DE))
        operacoes += [aresta(id_achado, feriveis[codigo], TipoAresta.FERE) for codigo in achado.toca if codigo in feriveis]
    return operacoes


def _estado_dos_criterios(livro: LivroRazaoDoGoal, registro: RegistroDaVerificacao) -> list[ItemPatch]:
    """O estado de cada Criterio julgado, igual ao parecer que ele recebeu; a Constraint de antes não tem estado."""
    view = livro.view()
    julgados = ((registro.nos.get(parecer.id, ""), parecer.veredito) for parecer in registro.verificacao.criterios)
    return [
        propriedade(id_no, a.CAMPO_ESTADO, veredito)
        for id_no, veredito in julgados
        if id_no and (no := view.obter_no(id_no)) is not None and no.tipo == TipoNo.CRITERIO
    ]
