"""A regra da conferência num ponto só: o que ela reprova e o código dá por `atende`, e a regressão que o código confirma.

Na revisão da T2c+T2d, duas saídas da conferência eram só a palavra dela: a
borda nova chamada de regressão num critério que já estava `parcial` virava
correção, e o critério que atendia e ela reprovava por uma borda nova ganhava
o bloqueante sintético. A T2h e a T2j passaram a decidir as duas por código,
em três peças (os critérios que podiam regredir, os conferidos corrigidos e os
pareceres sustentados), e a revisão delas achou quatro furos. O critério
`parcial` cuja correção pôs no README um exemplo errado fechava, porque a
regressão de quem não atendia nunca se confirmava; o 6º bloqueante, fora do
teto, não segurava o critério que os 5 conferidos corrigidos davam por
`atende`; a correção que quebrava um módulo que nenhuma fatia tocou não
confirmava a regressão; e os arquivos do critério cresciam com cada correção,
e uma borda antiga virava regressão de um diff que não a tocou. Na revisão
da T2i, o critério cujo teste de aceite estava em desacordo, que a conferência
julgava e reprovava, voltava ao parecer anterior, e o Goal fechava.

Na conferência, um critério ou decisão só sai `atende` se:
1. todo bloqueante conhecido que o cita está resolvido:
   - os conferidos receberam `corrigido`;
   - nenhum excedente do teto está pendente;
2. nenhuma regressão confirmada o cita;
3. nenhum teste de aceite dele falha.

Uma regressão que cita X está confirmada se as duas condições valem:
- X atendia antes, ou viraria `atende` agora pela regra acima;
- o diff das correções toca um destes arquivos:
  - o `local` do achado;
  - um arquivo das fatias do plano de X (sem as fatias de correção);
  - um arquivo que não pertence a nenhum critério ("sem como saber").

O parecer que a conferência reprova, com as três condições, sem bloqueante
que o toque e com um motivo para atender (atendia antes, ou um conferido
bloqueante o citava), sai `atende`, e o parecer dela vira acompanhamento
marcado. O critério em desacordo sobre o teste de aceite (o executor disse
que o teste está errado e o autor o manteve, ou o refazer ficou com o antigo)
ela julga, e o parecer dela vale como está. O `atende` que ela dá fica, menos
com um excedente do teto pendente que o cita: na revisão da T2k+T2l, a
conferência dava C2 `atende` sem citar o 6º bloqueante, e o Goal fechava com
ele só em pendência. Agora o critério sai `parcial`, e o excedente volta como
bloqueante, com o `persiste` dele, dentro do teto: é um achado conhecido, como
o conferido que persiste, e não uma borda nova, e a conferência seguinte o
confere. O conferido que persiste, a regressão confirmada e o teste de aceite
que falha já são bloqueantes. Sem o diff, ele vale como "sem como saber". O
excedente sai de pendente quando um achado que o repete (a cadeia de
`persiste`) é resolvido, ou recebe `corrigido` agora.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from graphow.core import aceite as a
from graphow.orquestrador.correcoes import arquivos_do_local, normalizar_caminho
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado
from graphow.orquestrador.saida_do_verificador import (
    MARCA_DO_CORRIGIDO,
    MARCA_DO_PARECER,
    ORIGEM_DO_ORQUESTRADOR,
    Achado,
    Parecer,
    Verificacao,
)


@dataclass(frozen=True)
class RegraDaConferencia:
    """O que a conferência não decide sozinha, com os fatos de antes dela: os conferidos, os excedentes, os pareceres e os arquivos.

    `excedentes` são os do teto ainda pendentes, e `repeticoes` os achados que
    repetem cada um; `diff` são os arquivos que as correções mudaram (None sem
    como saber); `arquivos`, os das fatias do plano de cada critério.
    """

    conferidos: tuple[AchadoRegistrado, ...] = ()
    excedentes: tuple[AchadoRegistrado, ...] = ()
    repeticoes: Mapping[str, frozenset[str]] = field(default_factory=dict)
    anteriores: tuple[Parecer, ...] = ()
    diff: frozenset[str] | None = None
    arquivos: Mapping[str, frozenset[str]] = field(default_factory=dict)
    em_desacordo: frozenset[str] = frozenset()

    def confirmada(self, regressao: Achado, verificacao: Verificacao) -> bool:
        """A regressão cita um X que atendia ou viraria `atende`, e o diff das correções toca o local, o plano de X ou arquivo sem critério."""
        return any((self._atendia(id_x) or self._viraria_atende(id_x, verificacao)) and self._no_diff(regressao, id_x)
                   for id_x in regressao.toca)

    def com_os_pareceres(self, verificacao: Verificacao) -> Verificacao:
        """O que ela reprova sem bloqueante que o toque, e que a regra dá por `atende`, sai `atende`; o `atende` com excedente pendente, não."""
        tocados = {id_t for achado in verificacao.achados if achado.gravidade == a.GRAVIDADE_BLOQUEANTE for id_t in achado.toca}
        soltos = {p.id: p for p in (*verificacao.criterios, *verificacao.decisoes) if p.veredito != a.VEREDITO_QUE_ATENDE
                  and p.id not in tocados and self._viraria_atende(p.id, verificacao)}
        no_lugar = {id_x: self._no_lugar(id_x, verificacao) for id_x in soltos}
        return self._com_os_excedentes(replace(
            verificacao, criterios=tuple(no_lugar[p.id][0] if p.id in soltos else p for p in verificacao.criterios),
            decisoes=tuple(no_lugar[p.id][0] if p.id in soltos else p for p in verificacao.decisoes),
            achados=(*verificacao.achados, *(_reprovado_sem_achado(p, no_lugar[p.id][1]) for p in soltos.values())),
        ))

    def _com_os_excedentes(self, verificacao: Verificacao) -> Verificacao:
        """O `atende` que ela deu com excedente do teto pendente que o cita sai `parcial`, e o excedente volta bloqueante, com o `persiste`."""
        pendentes = self._pendentes(verificacao)
        presos = {p.id: [e.id for e in pendentes if p.id in _o_que_cita(e)] for p in (*verificacao.criterios, *verificacao.decisoes)
                  if p.veredito == a.VEREDITO_QUE_ATENDE}
        presos = {id_x: ids for id_x, ids in presos.items() if ids}
        listados = {achado.persiste for achado in verificacao.achados}
        de_volta = [e for e in pendentes if e.id not in listados and any(e.id in ids for ids in presos.values())]
        trocado = {p.id: Parecer(p.id, a.VEREDITO_PARCIAL, f"o excedente do teto que o cita segue pendente ({', '.join(presos[p.id])}); "
                                 f"a conferencia deu atende: {p.prova}")
                   for p in (*verificacao.criterios, *verificacao.decisoes) if p.id in presos}
        return replace(
            verificacao, criterios=tuple(trocado.get(p.id, p) for p in verificacao.criterios),
            decisoes=tuple(trocado.get(p.id, p) for p in verificacao.decisoes),
            achados=(*verificacao.achados, *(copia_que_persiste(e, e.texto("prova")) for e in de_volta)),
        )

    def _atendia(self, id_x: str) -> bool:
        """X atendia na verificação de antes do marco."""
        return any(p.id == id_x and p.veredito == a.VEREDITO_QUE_ATENDE for p in self.anteriores)

    def _citam(self, id_x: str) -> tuple[AchadoRegistrado, ...]:
        """Os conferidos bloqueantes que citam X."""
        return tuple(c for c in self.conferidos if c.bloqueante and id_x in _o_que_cita(c))

    def _viraria_atende(self, id_x: str, verificacao: Verificacao) -> bool:
        """As condições 1 e 3, com um motivo para atender (atendia, ou um conferido o citava), fora do desacordo."""
        motivo = self._atendia(id_x) or bool(self._citam(id_x))
        return motivo and id_x not in self.em_desacordo and self._resolvido(id_x, verificacao) and _sem_aceite_vermelho(id_x, verificacao)

    def _resolvido(self, id_x: str, verificacao: Verificacao) -> bool:
        """Condição 1: os conferidos que citam X receberam `corrigido`, e nenhum excedente que o cita segue pendente."""
        corrigidos = frozenset(verificacao.confirmados)
        return (all(c.id in corrigidos for c in self._citam(id_x))
                and not any(id_x in _o_que_cita(e) for e in self._pendentes(verificacao)))

    def _pendentes(self, verificacao: Verificacao) -> tuple[AchadoRegistrado, ...]:
        """Os excedentes do teto que seguem pendentes: nenhum achado que os repete recebeu `corrigido` agora."""
        corrigidos = frozenset(verificacao.confirmados)
        return tuple(e for e in self.excedentes if not self.repeticoes.get(e.id, frozenset()) & corrigidos)

    def _no_diff(self, regressao: Achado, id_x: str) -> bool:
        """O diff toca o local da regressão, um arquivo do plano de X ou um que não é de critério nenhum; sem o diff, toca."""
        if self.diff is None:
            return True
        diff = frozenset(normalizar_caminho(caminho) for caminho in self.diff)
        de_criterio = {normalizar_caminho(caminho) for arquivos in self.arquivos.values() for caminho in arquivos}
        alvos = {normalizar_caminho(caminho) for caminho in (*arquivos_do_local(regressao.local), *self.arquivos.get(id_x, ()))}
        return bool(diff & alvos or diff - de_criterio)

    def _no_lugar(self, id_x: str, verificacao: Verificacao) -> tuple[Parecer, str]:
        """O `atende` que fica no lugar e a marca: o parecer anterior, ou o dos conferidos que o reprovavam e foram corrigidos."""
        anterior = next((p for p in self.anteriores if p.id == id_x and p.veredito == a.VEREDITO_QUE_ATENDE), None)
        if anterior is not None:
            return anterior, MARCA_DO_PARECER
        provas = {parecer.achado: parecer.prova for parecer in verificacao.conferidos if not parecer.persiste}
        texto = "; ".join(f"{c.id} conferido corrigido: {provas[c.id]}" for c in self._citam(id_x))
        return Parecer(id_x, a.VEREDITO_QUE_ATENDE, texto), MARCA_DO_CORRIGIDO


def _sem_aceite_vermelho(id_x: str, verificacao: Verificacao) -> bool:
    """Condição 3: nenhum achado do orquestrador (o teste de aceite que falhou, a configuração que o esconde) cita X."""
    return not any(achado.origem == ORIGEM_DO_ORQUESTRADOR and id_x in achado.toca for achado in verificacao.achados)


def copia_que_persiste(original: AchadoRegistrado, prova: str) -> Achado:
    """O achado conhecido que persiste (o conferido, ou o excedente do teto), como ele era, com a prova dada: bloqueante."""
    return Achado(original.texto("titulo"), original.texto("descricao"), prova=prova, local=original.texto("local"),
                  criterios=original.lista("criterios"), decisoes=original.lista("decisoes"),
                  severidade=original.texto("severidade"), reproducao=original.lista("reproducao"), persiste=original.id)


def _o_que_cita(achado: AchadoRegistrado) -> tuple[str, ...]:
    """Os critérios e as decisões que o achado registrado cita, a decisão do limite inclusive."""
    return (*achado.lista("criterios"), *achado.lista("decisoes"), *filter(None, (achado.texto("decisao_do_limite"),)))


def _reprovado_sem_achado(parecer: Parecer, marca: str) -> Achado:
    """O acompanhamento do parecer que a conferência deu sem bloqueante que o sustente, com a marca do que vale no lugar."""
    decisao = parecer.id.upper().startswith("D")
    descricao = f"a conferencia deu {parecer.id} {parecer.veredito} sem achado que bloqueie nem teste de aceite falhando"
    return Achado(f"{parecer.id} {parecer.veredito} na conferencia", descricao, prova=parecer.prova,
                  criterios=() if decisao else (parecer.id,), decisoes=(parecer.id,) if decisao else (),
                  rebaixado_na_conferencia=marca)


def repeticoes_de(achados: Sequence[AchadoRegistrado], id_achado: str) -> frozenset[str]:
    """Os achados que repetem o dado pela cadeia de `persiste` (a cópia da cópia inclusive), sem ele."""
    cadeia = {id_achado}
    mais = {achado.id for achado in achados if achado.texto("persiste") in cadeia} - cadeia
    while mais:
        cadeia |= mais
        mais = {achado.id for achado in achados if achado.texto("persiste") in cadeia} - cadeia
    return frozenset(cadeia - {id_achado})
