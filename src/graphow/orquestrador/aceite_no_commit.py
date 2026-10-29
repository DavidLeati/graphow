"""O aceite que o orquestrador roda no commit verificado: com a configuração entregue e, se ela mudou, também com a do commit do aceite.

Na rodada 3 os testes de aceite rodavam só com a configuração de teste do
commit do aceite. A revisão mostrou o custo: no projeto que passa a ter o
layout `src/` com `pythonpath`, o aceite isolado reprovava o que o repositório
entregue aprova, e o Goal travava. Agora:

- o aceite roda com a configuração entregue, com `aceite/` intocado (de volta
  ao commit do aceite, sem arquivo solto): é essa rodada que reprova o
  critério. As defesas contra a neutralização seguem nela: cada teste roda
  sozinho, e o pulado, o xfail e o desselecionado (o runner não conta nenhum
  passado) não contam como verde (orquestrador/resultado_de_teste.py);
- se a configuração de teste mudou desde o commit do aceite, os testes rodam de
  novo com a configuração daquele commit (orquestrador/configuracao_do_aceite.py);
- o teste que passa com a configuração entregue e não com a do commit do
  aceite é julgado pelo código primeiro. Se, com a do aceite, ele falha numa
  asserção (o vermelho válido de orquestrador/resultado_de_teste.py), a
  configuração entregue esconde uma falha real: o critério fica `nao_atende`,
  e um Achado bloqueante leva as duas saídas. Na revisão da T2a, um conftest
  com `pytest_pyfunc_call` que devolve True fechava o Goal com `somar`
  devolvendo 0. Se falha por import, coleta ou ambiente, é provável que seja
  um layout novo: vai ao verificador com o fim das duas saídas e o hash do
  commit do aceite, e ele deve um parecer por diferença (`legitima` ou
  `ilegitima`, com o motivo). O `ilegitima` vira bloqueante, e o parecer que
  falta invalida a saída. O comando de todos só conta quando nenhum teste
  sozinho mudou de resultado, e o teste que falha com a configuração entregue
  já reprova o critério pela rodada dela;
- a mudança de configuração continua indo à revisão de risco
  (orquestrador/execucao_da_fatia.py).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from graphow.core import aceite as a
from graphow.orquestrador.configuracao_do_aceite import configuracao_do_aceite, trocas_da_configuracao
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal
from graphow.orquestrador.gravacao_do_aceite import commit_da_configuracao
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.saida_do_aceite import (
    ExecucaoDeAceite,
    SaidaDoAceite,
    rodar_a_suite_com_o_aceite,
    rodar_o_comando_de_aceite,
    rodar_testes,
)
from graphow.orquestrador.saida_do_verificador import PARECER_ILEGITIMA, ParecerDaDiferenca, Verificacao
from graphow.orquestrador.suite import ResultadoDaSuite, rodar_suite

LIMITE_DO_MOTIVO: int = 300
# Quanto do fim de cada saída vai ao verificador e ao achado: as duas cabem na prova do achado.
LIMITE_DE_CADA_SAIDA: int = 900
DESTINO_DO_CODIGO: str = "achado_automatico"
DESTINO_DO_VERIFICADOR: str = "verificador"
# O par de execuções de um teste: com a configuração entregue e com a do commit do aceite.
Par = tuple[ExecucaoDeAceite, ExecucaoDeAceite]


@dataclass(frozen=True)
class AceiteNoCommit:
    """As execuções do aceite com a configuração entregue e, quando ela mudou, com a do commit do aceite."""

    execucoes: tuple[ExecucaoDeAceite, ...]
    com_a_do_aceite: tuple[ExecucaoDeAceite, ...] = ()
    trocados: tuple[str, ...] = ()
    commit: str = ""

    def diferencas(self) -> tuple[Par, ...]:
        """Cada teste que passou numa configuração e não na outra: (com a entregue, com a do aceite)."""
        do_aceite = {(e.criterio, e.teste): e for e in self.com_a_do_aceite}
        pares = ((e, do_aceite.get((e.criterio, e.teste))) for e in self.execucoes)
        return tuple((entregue, isolada) for entregue, isolada in pares if isolada is not None and isolada.passou != entregue.passou)

    def _so_com_a_entregue(self) -> tuple[Par, ...]:
        """Os que passam só com a configuração entregue; o comando de todos, só quando nenhum teste sozinho mudou."""
        pares = [(entregue, isolada) for entregue, isolada in self.diferencas() if entregue.passou]
        dos_testes = [par for par in pares if par[0].criterio]
        return tuple(dos_testes or pares)

    def escondidas(self) -> tuple[Par, ...]:
        """Os que, com a configuração do aceite, falham numa asserção: a entregue esconde uma falha real."""
        return tuple(par for par in self._so_com_a_entregue() if not par[1].vermelho_invalido())

    def a_julgar(self) -> tuple[Par, ...]:
        """Os que, com a configuração do aceite, falham por import, coleta ou ambiente: vão ao verificador."""
        return tuple(par for par in self._so_com_a_entregue() if par[1].vermelho_invalido())

    def chaves_a_julgar(self) -> tuple[tuple[str, str], ...]:
        """O critério e o teste de cada diferença que pede o parecer do verificador."""
        return tuple(_chave(par) for par in self.a_julgar())

    def diferencas_em_json(self, pareceres: Sequence[ParecerDaDiferenca] = ()) -> list[dict[str, Any]]:
        """As diferenças como a verificação as grava, com quem as julgou e o parecer do verificador, quando houve."""
        destinos = {**{_chave(par): DESTINO_DO_VERIFICADOR for par in self.a_julgar()},
                    **{_chave(par): DESTINO_DO_CODIGO for par in self.escondidas()}}
        dados = {parecer.chave: parecer.em_json() for parecer in pareceres}
        return [{"criterio": entregue.criterio, "teste": entregue.teste, "com_a_entregue": entregue.passou,
                 "com_a_do_aceite": isolada.passou, "motivo_com_a_entregue": entregue.motivo,
                 "motivo_com_a_do_aceite": isolada.motivo, "destino": destinos.get(_chave((entregue, isolada)), ""),
                 **dados.get(_chave((entregue, isolada)), {})} for entregue, isolada in self.diferencas()]

    def para_o_verificador(self) -> list[str]:
        """As diferenças que o verificador julga, com o fim das duas saídas, o commit do aceite e o que mudou."""
        a_julgar = self.a_julgar()
        if not a_julgar:
            return []
        linhas = [f"A configuracao de teste mudou desde o commit do aceite {self.commit} ({', '.join(self.trocados)}). Estes testes "
                  "de aceite passam com a configuracao entregue e, com a do commit do aceite, falham fora de uma assercao (import, "
                  "coleta, ambiente): pode ser um layout novo. Para cada um, de em `diferencas` o parecer, com o criterio e o teste "
                  "como aqui: `legitima` quando o teste ainda prova o criterio com a configuracao entregue (o modulo so mudou de "
                  "lugar), `ilegitima` quando ela muda o que ele prova (pula, desseleciona, troca o modulo que ele importa, finge "
                  "o resultado), com o motivo. O `ilegitima` reprova a entrega; faltar parecer invalida a verificacao."]
        for entregue, isolada in a_julgar:
            linhas += [f"- criterio \"{entregue.criterio}\", teste \"{entregue.teste}\": passa com a configuracao entregue; com a "
                       f"do commit do aceite, {_situacao(isolada)}.", "Fim da saida com a configuracao entregue:",
                       _trecho(entregue.saida), "Fim da saida com a configuracao do commit do aceite:", _trecho(isolada.saida)]
        return linhas

    def julgar(self, verificacao: Verificacao) -> Verificacao:
        """A verificação com o que as diferenças decidem: a falha escondida reprova o critério, e o `ilegitima` vira bloqueante."""
        for par in self.escondidas():
            verificacao = self._com_a_escondida(verificacao, par)
        ilegitimos = {p.chave: p for p in verificacao.diferencas if p.parecer == PARECER_ILEGITIMA}
        for par, parecer in [(par, ilegitimos[_chave(par)]) for par in self.a_julgar() if _chave(par) in ilegitimos]:
            verificacao = self._com_a_ilegitima(verificacao, par, parecer)
        return verificacao

    def _com_a_escondida(self, verificacao: Verificacao, par: Par) -> Verificacao:
        """O critério `nao_atende` e o Achado do orquestrador com as duas saídas."""
        entregue = par[0]
        prova = (f"o teste de aceite {entregue.teste} passa com a configuracao entregue e falha numa assercao com a do commit do "
                 f"aceite {self.commit[:12]}: a configuracao entregue esconde uma falha real")
        if entregue.criterio:
            verificacao = verificacao.com_parecer(entregue.criterio, a.VEREDITO_NAO_ATENDE, prova)
        titulo = f"A configuracao entregue esconde a falha do teste de aceite {entregue.teste} de {entregue.criterio or 'todos'}"
        return verificacao.com_achado_do_orquestrador(titulo, _com_as_duas_saidas(prova, par), _criterios(entregue))

    def _com_a_ilegitima(self, verificacao: Verificacao, par: Par, parecer: ParecerDaDiferenca) -> Verificacao:
        """O Achado bloqueante do parecer `ilegitima`, com o motivo do verificador e as duas saídas."""
        entregue, isolada = par
        texto = (f"o verificador julgou ilegitima a diferenca de configuracao ({parecer.motivo}); com a do commit do aceite "
                 f"{self.commit[:12]}, {_situacao(isolada)}")
        titulo = f"A configuracao entregue muda o que o teste de aceite {entregue.teste} de {entregue.criterio or 'todos'} prova"
        return verificacao.com_achado_do_orquestrador(titulo, _com_as_duas_saidas(texto, par), _criterios(entregue))


def rodar_o_aceite(contexto: ContextoDoGoal, estado: EstadoDoGoal, criterios: Sequence[str], *, final: bool) -> AceiteNoCommit:
    """O aceite dos critérios dados com a configuração entregue (na final, o de todos e a suíte junto) e, se ela mudou, com a do aceite."""
    aceite = SaidaDoAceite.do_livro(estado.aceite)

    def rodar(comando: str) -> ResultadoDaSuite:
        return rodar_suite(contexto.area, comando, contexto.banco_descartavel,
                           tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s, do_aceite=True)

    execucoes = rodar_testes(aceite, rodar, criterios)
    todos = (rodar_o_comando_de_aceite(aceite, rodar),) if final and execucoes else ()
    juntos = (rodar_a_suite_com_o_aceite(aceite, str((estado.plano or {}).get("comando_suite", "")), rodar),) if todos else ()
    commit = commit_da_configuracao(estado.aceite)
    if not commit or not trocas_da_configuracao(contexto.area, commit):
        return AceiteNoCommit((*execucoes, *todos, *juntos))
    with configuracao_do_aceite(contexto.area, commit) as trocados:
        isoladas = rodar_testes(aceite, rodar, criterios)
        isoladas_todos = (rodar_o_comando_de_aceite(aceite, rodar),) if todos else ()
    return AceiteNoCommit((*execucoes, *todos, *juntos), (*isoladas, *isoladas_todos), trocados, commit)


def _situacao(execucao: ExecucaoDeAceite) -> str:
    """Passa, ou falha com o motivo (e, no vermelho, por que ele não é asserção)."""
    if execucao.passou:
        return "passa"
    fora = execucao.vermelho_invalido()
    return f"falha ({execucao.motivo[:LIMITE_DO_MOTIVO]}{'; ' + fora[:LIMITE_DO_MOTIVO] if fora else ''})"


def _chave(par: Par) -> tuple[str, str]:
    """O critério e o teste do par."""
    return (par[0].criterio, par[0].teste)


def _criterios(execucao: ExecucaoDeAceite) -> tuple[str, ...]:
    """O critério que o achado toca; nenhum no comando de todos."""
    return (execucao.criterio,) if execucao.criterio else ()


def _trecho(saida: str) -> str:
    """O fim da saída num bloco de código."""
    return "```\n" + saida[-LIMITE_DE_CADA_SAIDA:].strip() + "\n```"


def _com_as_duas_saidas(texto: str, par: Par) -> str:
    """A descrição do achado: o que se viu, o comando e o fim das duas saídas."""
    entregue, isolada = par
    return (f"{texto}. Comando: `{entregue.comando}`. Fim da saida com a configuracao entregue:\n"
            f"{entregue.saida[-LIMITE_DE_CADA_SAIDA:]}\nFim da saida com a configuracao do commit do aceite:\n"
            f"{isolada.saida[-LIMITE_DE_CADA_SAIDA:]}")
