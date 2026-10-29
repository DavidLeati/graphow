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
  bordas: dá um parecer por achado conferido, `corrigido` ou `persiste`, com a
  prova (faltar um é saída inválida); o que persiste é bloqueante, o achado
  novo só vale se for regressão de critério, e o resto vira acompanhamento
  marcado. A conferência da final é final: a limpa no commit atual fecha o Goal.

Na revisão da T2c+T2d, o achado conferido que a conferência não listava contava
como corrigido, e o que ela achava de novo sem o `persiste` (opcional) virava
acompanhamento novo: um defeito que persistia sumia do ciclo. Agora o silêncio
não resolve nada: só o parecer `corrigido` confirma a correção, e o `persiste`
sem achado listado vira o bloqueante, com o que o achado conferido dizia. O
acompanhamento que passou do teto de bloqueantes (o excedente) vai na lista
da conferência com o id: se ela o acha de novo e o cita em `persiste`, ele
volta a bloquear, em vez de virar achado novo sem regressão.

Na mesma revisão, a borda nova marcada `regressao` num critério que já estava
`parcial` virava bloqueante e correção: era só a palavra da conferência. Agora
o código decide. A regressão só bloqueia se cita um critério que atendia na
verificação anterior do marco e cujos arquivos (os que as fatias dele
previram e commitaram) o diff das correções toca; sem como saber, vale só a
primeira condição; o resto vira acompanhamento marcado "regressao nao
confirmada". A caçada não muda.

O tipo vai na Evidence da verificação (`tipo_da_verificacao`) e no `--status`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from graphow.core import aceite as a
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.documento_do_goal import caminho_do_documento
from graphow.orquestrador.esquemas import PAPEL_CONFERENCIA, PAPEL_VERIFICADOR, PAPEL_VERIFICADOR_DO_MARCO
from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, MarcoRegistrado
from graphow.orquestrador.saida_do_verificador import (
    MARCA_DA_CONFERENCIA,
    MARCA_DA_REGRESSAO,
    MARCA_DO_TETO,
    ORIGEM_DO_VERIFICADOR,
    Achado,
    Parecer,
    ParecerDoConferido,
    Verificacao,
)

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
    """O tipo da verificação que o laço vai rodar e, na conferência, o que ela confere, de onde partiu e o que pode ter regredido.

    Na conferência, `podem_regredir` são os critérios que atendiam na
    verificação de antes e cujos arquivos o diff das correções toca (ou todos
    os que atendiam, quando não há como saber).
    """

    tipo: str
    conferidos: tuple[AchadoRegistrado, ...] = ()
    antes: str = ""
    excedentes: tuple[AchadoRegistrado, ...] = ()
    podem_regredir: tuple[str, ...] = ()

    @property
    def papel(self) -> str:
        """O papel da sessão: o prompt, o schema e o modelo do tipo."""
        return PAPEL_DO_TIPO[self.tipo]

    @property
    def ids_dos_conferidos(self) -> tuple[str, ...]:
        """Os ids dos achados que a conferência confere: cada um pede um parecer."""
        return tuple(achado.id for achado in self.conferidos)

    @property
    def ids_dos_excedentes(self) -> tuple[str, ...]:
        """Os ids dos excedentes do teto que a conferência pode citar em `persiste`."""
        return tuple(achado.id for achado in self.excedentes)

    @property
    def conferencia(self) -> bool:
        """É a conferência de depois de uma correção."""
        return self.tipo == TIPO_CONFERENCIA

    def ajustar(self, verificacao: Verificacao) -> Verificacao:
        """Na conferência, cada achado do verificador com o destino dela; nos outros tipos, como veio."""
        if not self.conferencia:
            return verificacao
        return na_conferencia(verificacao, self.conferidos, self.excedentes, podem_regredir=self.podem_regredir)


def escolher_o_tipo(estado: EstadoDoGoal, marco: MarcoRegistrado, git: GitDoGoal | None = None) -> TipoDaVerificacao:
    """A conferência quando o marco já tem verificação gravada; senão a do marco intermediário, ou a caçada na final."""
    verificacoes = estado.verificacoes_do_marco(marco)
    if not verificacoes:
        return TipoDaVerificacao(TIPO_CACA if marco.final else TIPO_MARCO)
    ultima = verificacoes[-1]
    excedentes = tuple(achado for v in (estado.verificacoes if marco.final else verificacoes) for achado in v.achados
                       if achado.texto("marca") == MARCA_DO_TETO and achado.estado == a.ESTADO_DO_ACOMPANHAMENTO)
    anteriores = pareceres_gravados(ultima.propriedades.get(m.CAMPO_PARECERES))
    do_plano = {str(criterio.get("id")) for criterio in (estado.plano or {}).get("criterios", [])}
    atendiam = tuple(p.id for p in anteriores if p.veredito == a.VEREDITO_QUE_ATENDE and p.id in do_plano)
    diff = _arquivos_do_diff(git, ultima.commit)
    arquivos = {id_c: _arquivos_do_criterio(estado, git, id_c) for id_c in atendiam} if git is not None and diff is not None else {}
    return TipoDaVerificacao(TIPO_CONFERENCIA, _conferidos(estado, ultima.id), ultima.commit, excedentes,
                             podem_regredir=que_podem_regredir(atendiam, arquivos, diff))


def pareceres_gravados(itens: object) -> tuple[Parecer, ...]:
    """Os pareceres de critério e de decisão como a verificação os gravou."""
    lidos = [item for item in itens if isinstance(item, Mapping)] if isinstance(itens, list) else []
    return tuple(Parecer(str(item.get("id", "")), str(item.get("veredito", "")), str(item.get("prova", ""))) for item in lidos)


def que_podem_regredir(
    atendiam: Sequence[str], arquivos: Mapping[str, frozenset[str]], diff: frozenset[str] | None
) -> tuple[str, ...]:
    """Os critérios que atendiam e cujos arquivos o diff das correções toca; sem o diff ou sem os arquivos de um, ele entra."""
    return tuple(id_c for id_c in atendiam if diff is None or not arquivos.get(id_c) or arquivos[id_c] & diff)


def _arquivos_do_diff(git: GitDoGoal | None, antes: str) -> frozenset[str] | None:
    """Os arquivos que as correções mudaram desde o commit de antes; None quando não há como saber."""
    saida = git.tentar("diff", "--name-only", f"{antes}..HEAD") if git is not None and antes else None
    return None if saida is None or saida.codigo != 0 else frozenset(_linhas(saida.saida))


def _arquivos_do_criterio(estado: EstadoDoGoal, git: GitDoGoal, id_criterio: str) -> frozenset[str]:
    """Os arquivos que a evidência do critério cobre: os que as fatias que o entregam previram e os que os commits delas mudaram."""
    fatias = [fatia for fatia in estado.fatias if id_criterio in fatia.lista(m.CAMPO_CRITERIOS)]
    commits = (git.tentar("show", "--name-only", "--format=", fatia.texto(m.CAMPO_COMMIT)) for fatia in fatias
               if fatia.texto(m.CAMPO_COMMIT))
    do_commit = (caminho for saida in commits if saida.codigo == 0 for caminho in _linhas(saida.saida))
    return frozenset((*(caminho for fatia in fatias for caminho in fatia.lista(m.CAMPO_ARQUIVOS_ALVO)), *do_commit))


def _linhas(saida: str) -> tuple[str, ...]:
    """Os caminhos que o git listou, um por linha, sem vazios."""
    return tuple(linha.strip() for linha in saida.splitlines() if linha.strip())


def _conferidos(estado: EstadoDoGoal, id_verificacao: str) -> tuple[AchadoRegistrado, ...]:
    """Os achados que as correções da verificação dada trataram (na final, também os que ela cobrou dos outros marcos)."""
    ids = dict.fromkeys(id_achado for fatia in estado.fatias if fatia.texto(m.CAMPO_CORRIGE) == id_verificacao
                        for id_achado in m.achados_da_correcao(fatia.propriedades))
    return tuple(achado for id_achado in ids if (achado := estado.achado(id_achado)) is not None)


def na_conferencia(
    verificacao: Verificacao, conferidos: Sequence[AchadoRegistrado], excedentes: Sequence[AchadoRegistrado] = (), *,
    podem_regredir: Sequence[str] = (),
) -> Verificacao:
    """A conferência com o destino de cada achado do verificador e um bloqueante por conferido que persiste.

    O que persiste (um conferido ou um excedente do teto) toca também o que o
    original tocava, e é bloqueante; a regressão que cita um critério que pode
    ter regredido segue a regra de sempre, e a outra vira acompanhamento
    marcado "regressao nao confirmada"; o achado novo que não é regressão vira
    acompanhamento marcado. Os do orquestrador (a suíte, o teste de aceite)
    ficam como vieram. O parecer `persiste` que nenhum achado listado repete
    vira o achado, com o que o conferido dizia e a prova do parecer.
    """
    por_id = {achado.id: achado for achado in (*excedentes, *conferidos)}
    achados = tuple(_com_o_destino(achado, por_id, frozenset(podem_regredir)) for achado in verificacao.achados)
    listados = {achado.persiste for achado in achados}
    repetidos = tuple(_o_que_persiste(parecer, por_id[parecer.achado]) for parecer in verificacao.conferidos
                      if parecer.persiste and parecer.achado in por_id and parecer.achado not in listados)
    return replace(verificacao, achados=(*achados, *repetidos))


def _o_que_persiste(parecer: ParecerDoConferido, original: AchadoRegistrado) -> Achado:
    """O achado conferido que persiste, como ele era, com a prova nova."""
    return Achado(original.texto("titulo"), original.texto("descricao"), prova=parecer.prova, local=original.texto("local"),
                  criterios=original.lista("criterios"), decisoes=original.lista("decisoes"),
                  severidade=original.texto("severidade"), reproducao=original.lista("reproducao"), persiste=original.id)


def _com_o_destino(achado: Achado, por_id: Mapping[str, AchadoRegistrado], podem_regredir: frozenset[str]) -> Achado:
    """O achado do verificador que persiste, a regressão confirmada, ou o que não vira correção (o novo, a regressão sem confirmação)."""
    if achado.origem != ORIGEM_DO_VERIFICADOR:
        return achado
    original = por_id.get(achado.persiste)
    if original is not None:
        return replace(achado, criterios=tuple(dict.fromkeys((*achado.criterios, *original.lista("criterios")))),
                       decisoes=tuple(dict.fromkeys((*achado.decisoes, *original.lista("decisoes")))))
    if achado.regressao and podem_regredir.intersection(achado.criterios):
        return achado
    return replace(achado, persiste="", rebaixado_na_conferencia=MARCA_DA_REGRESSAO if achado.regressao else MARCA_DA_CONFERENCIA)


def diff_das_correcoes(git: GitDoGoal, antes: str, slug: str) -> str:
    """O diff do commit da verificação anterior até o atual, sem o documento do Goal, cortado; vazio sem o commit de antes."""
    if not antes:
        return ""
    saida = git.tentar("diff", f"{antes}..HEAD", "--", ".", f":(exclude){caminho_do_documento(slug)}").saida
    return saida[:LIMITE_DO_DIFF_DAS_CORRECOES]
