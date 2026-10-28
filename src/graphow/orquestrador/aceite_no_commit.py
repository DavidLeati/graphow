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
- o teste que dá resultado diferente nas duas rodadas vai ao verificador, no
  briefing, para ele julgar se a mudança é legítima; se não for, ele registra o
  achado citando o critério, e o código o faz bloqueante. A diferença sozinha
  não reprova o critério;
- a mudança de configuração continua indo à revisão de risco
  (orquestrador/execucao_da_fatia.py).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

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
from graphow.orquestrador.suite import ResultadoDaSuite, rodar_suite

LIMITE_DO_MOTIVO: int = 300


@dataclass(frozen=True)
class AceiteNoCommit:
    """As execuções do aceite com a configuração entregue e, quando ela mudou, com a do commit do aceite."""

    execucoes: tuple[ExecucaoDeAceite, ...]
    com_a_do_aceite: tuple[ExecucaoDeAceite, ...] = ()
    trocados: tuple[str, ...] = ()

    def diferencas(self) -> tuple[tuple[ExecucaoDeAceite, ExecucaoDeAceite], ...]:
        """Cada teste que passou numa configuração e não na outra: (com a entregue, com a do aceite)."""
        do_aceite = {(e.criterio, e.teste): e for e in self.com_a_do_aceite}
        pares = ((e, do_aceite.get((e.criterio, e.teste))) for e in self.execucoes)
        return tuple((entregue, isolada) for entregue, isolada in pares if isolada is not None and isolada.passou != entregue.passou)

    def diferencas_em_json(self) -> list[dict[str, Any]]:
        """As diferenças como a verificação as grava."""
        return [{"criterio": entregue.criterio, "teste": entregue.teste, "com_a_entregue": entregue.passou,
                 "com_a_do_aceite": isolada.passou, "motivo_com_a_entregue": entregue.motivo,
                 "motivo_com_a_do_aceite": isolada.motivo} for entregue, isolada in self.diferencas()]

    def para_o_verificador(self) -> list[str]:
        """As diferenças para o verificador julgar, com os arquivos de configuração que mudaram."""
        diferencas = self.diferencas()
        if not diferencas:
            return []
        linhas = [f"A configuracao de teste mudou desde o commit do aceite ({', '.join(self.trocados)}), e estes testes de aceite "
                  "deram resultado diferente com cada uma. Vale para o criterio a rodada com a configuracao entregue. Julgue se a "
                  "mudanca e legitima (um layout novo, um caminho de import) ou se muda o que o teste prova (pula, desseleciona, "
                  "troca o que ele importa); se mudar, registre um achado que cite o criterio."]
        linhas += [f"- {e.teste} de {e.criterio or 'todos'}: {_situacao(e)} com a configuracao entregue; {_situacao(i)} com a do "
                   "commit do aceite" for e, i in diferencas]
        return linhas


def rodar_o_aceite(contexto: ContextoDoGoal, estado: EstadoDoGoal, criterios: Sequence[str], *, final: bool) -> AceiteNoCommit:
    """O aceite dos critérios dados com a configuração entregue (na final, o de todos e a suíte junto) e, se ela mudou, com a do aceite."""
    aceite = SaidaDoAceite.do_livro(estado.aceite)

    def rodar(comando: str) -> ResultadoDaSuite:
        return rodar_suite(contexto.area, comando, contexto.banco_descartavel, tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s)

    execucoes = rodar_testes(aceite, rodar, criterios)
    todos = (rodar_o_comando_de_aceite(aceite, rodar),) if final and execucoes else ()
    juntos = (rodar_a_suite_com_o_aceite(aceite, str((estado.plano or {}).get("comando_suite", "")), rodar),) if todos else ()
    commit = commit_da_configuracao(estado.aceite)
    if not commit or not trocas_da_configuracao(contexto.area, commit):
        return AceiteNoCommit((*execucoes, *todos, *juntos))
    with configuracao_do_aceite(contexto.area, commit) as trocados:
        isoladas = rodar_testes(aceite, rodar, criterios)
        isoladas_todos = (rodar_o_comando_de_aceite(aceite, rodar),) if todos else ()
    return AceiteNoCommit((*execucoes, *todos, *juntos), (*isoladas, *isoladas_todos), trocados)


def _situacao(execucao: ExecucaoDeAceite) -> str:
    """Passa, ou falha com o motivo."""
    return "passa" if execucao.passou else f"falha ({execucao.motivo[:LIMITE_DO_MOTIVO]})"
