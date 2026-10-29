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
  com um briefing curto: os achados, as provas e o diff das correções
  (orquestrador/diff_das_correcoes.py). Não caça
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

Na mesma revisão, a borda nova chamada de regressão e o critério que ela
reprovava por uma borda nova eram só a palavra dela. Agora o código decide
os dois, com a regra da conferência (orquestrador/regra_da_conferencia.py):
a regressão só bloqueia quando ele a confirma, e o reprovado sem bloqueante
que o toque, que a regra dá por `atende`, sai `atende`, com o parecer dela
em acompanhamento. A caçada não muda. Os fatos da regra saem daqui: os
conferidos, os excedentes do teto ainda pendentes (o reachado e resolvido
sai da lista), os pareceres de antes, os arquivos que as correções mudaram
(sem o documento do Goal e o aceite), os das fatias do plano de cada
critério e os critérios em desacordo sobre o teste de aceite.

O tipo vai na Evidence da verificação (`tipo_da_verificacao`) e no `--status`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from graphow.core import aceite as a
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.documento_do_goal import caminho_do_documento
from graphow.orquestrador.esquemas import PAPEL_CONFERENCIA, PAPEL_VERIFICADOR, PAPEL_VERIFICADOR_DO_MARCO
from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, MarcoRegistrado
from graphow.orquestrador.regra_da_conferencia import RegraDaConferencia, repeticoes_de
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


@dataclass(frozen=True)
class TipoDaVerificacao:
    """O tipo da verificação que o laço vai rodar e, na conferência, de onde ela partiu e a regra com os fatos dela."""

    tipo: str
    antes: str = ""
    regra: RegraDaConferencia = field(default_factory=RegraDaConferencia)

    @property
    def papel(self) -> str:
        """O papel da sessão: o prompt, o schema e o modelo do tipo."""
        return PAPEL_DO_TIPO[self.tipo]

    @property
    def conferidos(self) -> tuple[AchadoRegistrado, ...]:
        """Os achados que as correções trataram: cada um pede um parecer."""
        return self.regra.conferidos

    @property
    def excedentes(self) -> tuple[AchadoRegistrado, ...]:
        """Os excedentes do teto ainda pendentes, que a conferência pode citar em `persiste`."""
        return self.regra.excedentes

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
        return na_conferencia(verificacao, self.regra) if self.conferencia else verificacao

    def sustentar(self, verificacao: Verificacao) -> Verificacao:
        """Na conferência, o reprovado que a regra dá por `atende` sai `atende` (`RegraDaConferencia.com_os_pareceres`); nos outros, como veio."""
        return self.regra.com_os_pareceres(verificacao) if self.conferencia else verificacao


def escolher_o_tipo(estado: EstadoDoGoal, marco: MarcoRegistrado, git: GitDoGoal | None = None) -> TipoDaVerificacao:
    """A conferência quando o marco já tem verificação gravada; senão a do marco intermediário, ou a caçada na final."""
    verificacoes = estado.verificacoes_do_marco(marco)
    if not verificacoes:
        return TipoDaVerificacao(TIPO_CACA if marco.final else TIPO_MARCO)
    ultima = verificacoes[-1]
    todos = tuple(achado for v in estado.verificacoes for achado in v.achados)
    excedentes = _excedentes(estado, marco, todos)
    diff = _arquivos_do_diff(git, ultima.commit, fora=_fora_do_diff(estado))
    regra = RegraDaConferencia(
        conferidos=_conferidos(estado, ultima.id), excedentes=excedentes,
        repeticoes={e.id: repeticoes_de(todos, e.id) for e in excedentes},
        anteriores=pareceres_gravados(ultima.propriedades.get(m.CAMPO_PARECERES)), diff=diff,
        arquivos=_arquivos_do_plano(estado, git) if git is not None and diff is not None else {},
        em_desacordo=criterios_em_desacordo(estado),
    )
    return TipoDaVerificacao(TIPO_CONFERENCIA, ultima.commit, regra)


def pareceres_gravados(itens: object) -> tuple[Parecer, ...]:
    """Os pareceres de critério e de decisão como a verificação os gravou."""
    lidos = [item for item in itens if isinstance(item, Mapping)] if isinstance(itens, list) else []
    return tuple(Parecer(str(item.get("id", "")), str(item.get("veredito", "")), str(item.get("prova", ""))) for item in lidos)


def _excedentes(estado: EstadoDoGoal, marco: MarcoRegistrado, todos: Sequence[AchadoRegistrado]) -> tuple[AchadoRegistrado, ...]:
    """Os excedentes do teto do marco (na final, do Goal) ainda pendentes: o que um achado repetiu e se resolveu sai."""
    escopo = estado.verificacoes if marco.final else estado.verificacoes_do_marco(marco)
    resolvidos = {*estado.corrigidos(marco), *(achado.id for achado in todos if achado.encerrado)}
    return tuple(achado for v in escopo for achado in v.achados
                 if achado.texto("marca") == MARCA_DO_TETO and achado.estado == a.ESTADO_DO_ACOMPANHAMENTO
                 and not repeticoes_de(todos, achado.id) & resolvidos)


def criterios_em_desacordo(estado: EstadoDoGoal) -> frozenset[str]:
    """Os critérios cujo teste de aceite está em desacordo: o autor manteve o que o executor disse errado, ou o refazer ficou com o antigo."""
    respostas = (fatia.propriedades.get("resposta_do_autor_de_aceite") for fatia in estado.fatias)
    desacordos = (fatia.propriedades.get("desacordo_sobre_o_teste") for fatia in estado.fatias)
    refeitos = estado.propriedades.get("refeito_sem_vermelho")
    itens = (*(r for r in respostas if isinstance(r, Mapping) and not r.get("mudou")), *desacordos,
             *(refeitos if isinstance(refeitos, list) else ()))
    return frozenset(str(item.get("criterio")) for item in itens if isinstance(item, Mapping) and item.get("criterio"))


def _fora_do_diff(estado: EstadoDoGoal) -> frozenset[str]:
    """O que não conta no diff das correções: o documento do Goal e os testes de aceite, que nenhuma fatia escreve."""
    documento = (caminho_do_documento(estado.configuracao.slug),) if estado.configuracao is not None else ()
    return frozenset((*documento, *estado.arquivos_protegidos()))


def _arquivos_do_diff(git: GitDoGoal | None, antes: str, *, fora: frozenset[str]) -> frozenset[str] | None:
    """Os arquivos que as correções mudaram desde o commit de antes, sem os de fora; None quando não há como saber."""
    saida = git.tentar("diff", "--name-only", f"{antes}..HEAD") if git is not None and antes else None
    return None if saida is None or saida.codigo != 0 else frozenset(_linhas(saida.saida)) - fora


def _arquivos_do_plano(estado: EstadoDoGoal, git: GitDoGoal) -> dict[str, frozenset[str]]:
    """Os arquivos de cada critério do plano: os que as fatias do plano dele (sem as de correção) previram e commitaram."""
    ids = (str(criterio.get("id")) for criterio in (estado.plano or {}).get("criterios", []))
    return {id_c: _arquivos_do_criterio(estado, git, id_c) for id_c in ids}


def _arquivos_do_criterio(estado: EstadoDoGoal, git: GitDoGoal, id_criterio: str) -> frozenset[str]:
    """Os arquivos que as fatias do plano que entregam o critério previram e os que os commits delas mudaram."""
    fatias = [fatia for fatia in estado.fatias if id_criterio in fatia.lista(m.CAMPO_CRITERIOS) and not fatia.texto(m.CAMPO_CORRIGE)]
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


def na_conferencia(verificacao: Verificacao, regra: RegraDaConferencia) -> Verificacao:
    """A conferência com o destino de cada achado do verificador e um bloqueante por conferido que persiste.

    O que persiste (um conferido ou um excedente do teto) toca também o que o
    original tocava, e é bloqueante; a regressão que a regra confirma segue a
    regra de sempre, e a outra vira acompanhamento marcado "regressao nao
    confirmada"; o achado novo que não é regressão vira acompanhamento
    marcado. Os do orquestrador (a suíte, o teste de aceite) ficam como vieram,
    depois dos do verificador. O parecer `persiste` que nenhum achado listado
    repete vira o achado, com o que o conferido dizia e a prova do parecer.
    """
    por_id = {achado.id: achado for achado in (*regra.excedentes, *regra.conferidos)}
    achados = tuple(_com_o_destino(achado, por_id, regra=regra, verificacao=verificacao) for achado in verificacao.achados)
    listados = {achado.persiste for achado in achados}
    repetidos = tuple(_o_que_persiste(parecer, por_id[parecer.achado]) for parecer in verificacao.conferidos
                      if parecer.persiste and parecer.achado in por_id and parecer.achado not in listados)
    proprios = tuple(achado for achado in achados if achado.origem == ORIGEM_DO_VERIFICADOR)
    return replace(verificacao, achados=(*proprios, *repetidos, *(x for x in achados if x.origem != ORIGEM_DO_VERIFICADOR)))


def _o_que_persiste(parecer: ParecerDoConferido, original: AchadoRegistrado) -> Achado:
    """O achado conferido que persiste, como ele era, com a prova nova."""
    return Achado(original.texto("titulo"), original.texto("descricao"), prova=parecer.prova, local=original.texto("local"),
                  criterios=original.lista("criterios"), decisoes=original.lista("decisoes"),
                  severidade=original.texto("severidade"), reproducao=original.lista("reproducao"), persiste=original.id)


def _com_o_destino(
    achado: Achado, por_id: Mapping[str, AchadoRegistrado], *, regra: RegraDaConferencia, verificacao: Verificacao
) -> Achado:
    """O achado do verificador que persiste, a regressão confirmada, ou o que não vira correção (o novo, a regressão sem confirmação)."""
    if achado.origem != ORIGEM_DO_VERIFICADOR:
        return achado
    original = por_id.get(achado.persiste)
    if original is not None:
        return replace(achado, criterios=tuple(dict.fromkeys((*achado.criterios, *original.lista("criterios")))),
                       decisoes=tuple(dict.fromkeys((*achado.decisoes, *original.lista("decisoes")))))
    if achado.regressao and regra.confirmada(achado, verificacao):
        return achado
    return replace(achado, persiste="", rebaixado_na_conferencia=MARCA_DA_REGRESSAO if achado.regressao else MARCA_DA_CONFERENCIA)
