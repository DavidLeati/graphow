"""O tipo de cada verificação: a caçada uma vez, na primeira final; a do marco intermediário; a conferência depois de cada correção.

Na bancada de 12/10 (a agenda), toda verificação era uma caçada adversarial em
Opus, e depois de cada ciclo de correção vinha outra caçada, que achava bordas
novas: 6 verificações (US$ 4,06) e 22 sessões de executor, e o laço não
convergia. Agora o laço escolhe o tipo pelo que o marco já teve:

- `marco`: a primeira verificação de um marco intermediário. Confere só os
  critérios dele, rodando os testes e o programa, sem sondar bordas (papel
  `marco`, Sonnet, `--modelo-marco`).
- `caca`: a primeira verificação final, sobre o Goal inteiro, adversarial e com
  sondagem de bordas (papel `verificador`, Opus, `--modelo-verificador`). Roda
  uma vez por Goal.
- `conferencia`: toda verificação seguinte do marco, a de depois de um ciclo de
  correção, em qualquer marco (papel `conferencia`, Sonnet,
  `--modelo-conferencia`). Roda a suíte e o aceite, reproduz cada achado que
  as correções trataram e confere regressão nos critérios que elas tocaram,
  com um briefing curto: os achados, as provas e o diff das correções. Não caça
  bordas: o achado conferido que persiste é bloqueante, o achado novo só vale se
  for regressão de critério, e o resto vira acompanhamento marcado. A
  conferência da final é final: a limpa no commit atual fecha o Goal.

O tipo vai na Evidence da verificação (`tipo_da_verificacao`) e no `--status`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.documento_do_goal import caminho_do_documento
from graphow.orquestrador.esquemas import PAPEL_CONFERENCIA, PAPEL_VERIFICADOR, PAPEL_VERIFICADOR_DO_MARCO
from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, MarcoRegistrado
from graphow.orquestrador.saida_do_verificador import ORIGEM_DO_VERIFICADOR, Achado, Verificacao

TIPO_CACA: str = "caca"
TIPO_MARCO: str = "marco"
TIPO_CONFERENCIA: str = "conferencia"
TIPOS_DE_VERIFICACAO: tuple[str, ...] = (TIPO_CACA, TIPO_MARCO, TIPO_CONFERENCIA)
PAPEL_DO_TIPO: Mapping[str, str] = {
    TIPO_CACA: PAPEL_VERIFICADOR, TIPO_MARCO: PAPEL_VERIFICADOR_DO_MARCO, TIPO_CONFERENCIA: PAPEL_CONFERENCIA,
}
# Quanto do diff das correções vai à conferência.
LIMITE_DO_DIFF_DAS_CORRECOES: int = 8000


@dataclass(frozen=True)
class TipoDaVerificacao:
    """O tipo da verificação que o laço vai rodar e, na conferência, os achados que ela confere e de onde as correções partiram."""

    tipo: str
    conferidos: tuple[AchadoRegistrado, ...] = ()
    antes: str = ""

    @property
    def papel(self) -> str:
        """O papel da sessão: o prompt, o schema e o modelo do tipo."""
        return PAPEL_DO_TIPO[self.tipo]

    @property
    def conferencia(self) -> bool:
        """É a conferência de depois de uma correção."""
        return self.tipo == TIPO_CONFERENCIA

    def ajustar(self, verificacao: Verificacao) -> Verificacao:
        """Na conferência, cada achado do verificador com o destino dela; nos outros tipos, como veio."""
        return na_conferencia(verificacao, self.conferidos) if self.conferencia else verificacao


def escolher_o_tipo(estado: EstadoDoGoal, marco: MarcoRegistrado) -> TipoDaVerificacao:
    """A conferência quando o marco já tem verificação gravada; senão a do marco intermediário, ou a caçada na final."""
    verificacoes = estado.verificacoes_do_marco(marco)
    if not verificacoes:
        return TipoDaVerificacao(TIPO_CACA if marco.final else TIPO_MARCO)
    ultima = verificacoes[-1]
    return TipoDaVerificacao(TIPO_CONFERENCIA, _conferidos(estado, ultima.id), ultima.commit)


def _conferidos(estado: EstadoDoGoal, id_verificacao: str) -> tuple[AchadoRegistrado, ...]:
    """Os achados que as correções da verificação dada trataram (na final, também os que ela cobrou dos outros marcos)."""
    ids = dict.fromkeys(id_achado for fatia in estado.fatias if fatia.texto(m.CAMPO_CORRIGE) == id_verificacao
                        for id_achado in m.achados_da_correcao(fatia.propriedades))
    return tuple(achado for id_achado in ids if (achado := estado.achado(id_achado)) is not None)


def na_conferencia(verificacao: Verificacao, conferidos: Sequence[AchadoRegistrado]) -> Verificacao:
    """A conferência com o destino de cada achado do verificador.

    O que persiste toca também o que o achado conferido tocava, e é
    bloqueante; o que é regressão segue a regra de sempre; o achado novo que
    não é regressão vira acompanhamento marcado. Os do orquestrador (a suíte,
    o teste de aceite) ficam como vieram.
    """
    por_id = {achado.id: achado for achado in conferidos}
    return replace(verificacao, achados=tuple(_com_o_destino(achado, por_id) for achado in verificacao.achados))


def _com_o_destino(achado: Achado, por_id: Mapping[str, AchadoRegistrado]) -> Achado:
    """O achado do verificador que persiste, que é regressão, ou que é novo e não vira correção."""
    if achado.origem != ORIGEM_DO_VERIFICADOR:
        return achado
    original = por_id.get(achado.persiste)
    if original is not None:
        return replace(achado, criterios=tuple(dict.fromkeys((*achado.criterios, *original.lista("criterios")))),
                       decisoes=tuple(dict.fromkeys((*achado.decisoes, *original.lista("decisoes")))))
    return achado if achado.regressao else replace(achado, persiste="", novo_na_conferencia=True)


def diff_das_correcoes(git: GitDoGoal, antes: str, slug: str) -> str:
    """O diff do commit da verificação anterior até o atual, sem o documento do Goal, cortado; vazio sem o commit de antes."""
    if not antes:
        return ""
    saida = git.tentar("diff", f"{antes}..HEAD", "--", ".", f":(exclude){caminho_do_documento(slug)}").saida
    return saida[:LIMITE_DO_DIFF_DAS_CORRECOES]
