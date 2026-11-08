"""A janela da foto do repositório do humano: da foto de antes da sessão ao fim do código do agente que o orquestrador roda.

A foto de antes (orquestrador/foto_do_humano.py) era tirada e conferida em
volta de cada sessão de papel. Mas o orquestrador roda no clone, fora da
sessão, código que o agente escreveu: os testes de aceite, a suíte, o aceite
na branch rebaseada. Um teste que fazia `git -C <humano> checkout -- .`
apagava o trabalho do humano sem que foto nenhuma visse: a da sessão seguinte
já nascia depois dele. Agora a foto de antes vale até o fim da janela, e a
conferência (orquestrador/conferencia_do_humano.py) é uma por janela:
- a da fatia vai da foto de antes do executor ao fim da suíte, do aceite e da
  revisão de risco da entrega (orquestrador/execucao_da_fatia.py);
- a da verificação, do aceite que o orquestrador roda antes do verificador ao
  fim da suíte de depois dele e da segunda opinião
  (orquestrador/verificacao_do_marco.py);
- a do rebase é só da suíte e do aceite na branch rebaseada, que não têm
  sessão antes (orquestrador/base_que_andou.py);
- a sessão que não é seguida por código do agente tem a sua, como antes: o
  planejador, e o autor de aceite, que roda os testes dentro da conferência da
  própria saída (o aceite refeito também), antes de a sessão acabar.
A janela fecha antes de o orquestrador mexer no repositório do humano (o
commit leva a branch a ele: `ContextoDoGoal.commitar`) e no fim de todo passo
do laço, mesmo por exceção.

Logo depois de cada sessão, antes do primeiro git (o do clone inclusive:
`trava_mexida`, `restaurar_o_clone`), `conferir_o_git` relê em bytes os
arquivos que mudam o git (a global, a do XDG, os includes), sem processo: a
sessão que plantou ali um programa que o `-c` do orquestrador não desliga (um
filtro, um driver de diff, um `uploadpack.packObjectsHook`) para o laço sem
que git nenhum rode (`GitDoHumanoMexido`). A janela aberta fica gravada em
disco (orquestrador/janela_gravada.py), e `retomar`, no começo da chamada
seguinte a uma queda, faz a mesma conferência antes do primeiro git.

Para dizer quem mexeu sem outra conferência, cada trecho da janela (cada
invocação de sessão, cada vez que o orquestrador roda o código do agente)
começa com uma marca, lida sem processo: o sha256 de cada arquivo que a foto
de antes listou, dos arquivos que mudam o git (orquestrador/arquivos_do_git.py)
e das refs (`HEAD`, `packed-refs`, `refs/`). Cada mudança que a conferência
acha é do trecho em que o arquivo dela mudou por último; a que não é de
arquivo marcado (o rastreado limpo apagado, a entrada do índice sem mudança
no arquivo, o arquivo novo) é de todos os trechos. O índice fica fora da marca de propósito: o
`git status` do editor do humano o regrava a toda hora.
"""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from graphow.core.types import PapelAutor
from graphow.orquestrador.arquivos_do_git import conteudo_do_arquivo, ler_os_arquivos_do_git
from graphow.orquestrador.conferencia_do_humano import LeitorDosOutrosGoals, conferir_os_arquivos_do_git, mexido_desde, relatar
from graphow.orquestrador.foto_do_humano import FotoDoHumano, foto_antes_da_sessao
from graphow.orquestrador.humano_mexido import Durante, HumanoMexido, RegistroDoHumanoMexido, RepositorioDoHumanoMexido
from graphow.orquestrador.janela_gravada import apagar_a_gravada, foto_gravada, gravar_a_janela

PAPEL_DO_ORQUESTRADOR: str = PapelAutor.ORQUESTRADOR.value
# A mudança da conferência que não é de arquivo: a troca de HEAD vem com a ref que andou.
SEM_ARQUIVO: tuple[str, ...] = ("HEAD: ",)
# O que se diz da janela que fechou sem trecho nenhum (a sessão que não chegou a abrir).
SEM_TRECHO: str = "o passo do laco, desde a foto de antes"
# O que se diz da janela que a execução anterior deixou aberta ao cair, conferida na retomada.
NA_QUEDA: str = "a execucao anterior do laco, que caiu com a janela da foto aberta"


class GitDoHumanoMexido(RepositorioDoHumanoMexido):
    """Um arquivo que muda o git do humano mudou: o laço para sem rodar mais git, nem no clone."""


@dataclass(frozen=True)
class ConfiguracaoDaJanela:
    """De onde a janela tira a foto e para onde manda o que achou: o repositório do humano (None: nada a conferir), a pasta
    da salvaguarda, o registro no livro-razão, o leitor dos outros Goals e onde a janela aberta fica gravada."""

    repositorio: Path | None = None
    salvaguarda: Path | None = None
    registrar: RegistroDoHumanoMexido | None = None
    outros_goals: LeitorDosOutrosGoals | None = None
    gravada: Path | None = None


@dataclass(frozen=True)
class Trecho:
    """Um trecho da janela: o que rodou (a sessão de um papel, ou o código do agente que o orquestrador rodou, sem papel), a
    fatia e a marca do começo."""

    quem: str
    papel: str
    fatia: str
    marca: Mapping[str, str]


class JanelaDoHumano:
    """A foto de antes, aberta até a conferência que a fecha, e os trechos do meio."""

    def __init__(self, configuracao: ConfiguracaoDaJanela | None = None) -> None:
        self._configuracao: ConfiguracaoDaJanela = configuracao or ConfiguracaoDaJanela()
        self._antes: FotoDoHumano | None = None
        self._trechos: list[Trecho] = []

    @property
    def aberta(self) -> bool:
        """Há foto de antes esperando a conferência."""
        return self._antes is not None

    @property
    def trechos(self) -> tuple[Trecho, ...]:
        """Os trechos da janela aberta, na ordem."""
        return tuple(self._trechos)

    def abrir(self) -> None:
        """A foto de antes e a salvaguarda, gravadas para a retomada, quando a janela está fechada; aberta, nada."""
        if self._antes is None:
            configuracao = self._configuracao
            self._antes = foto_antes_da_sessao(configuracao.repositorio, salvaguarda=configuracao.salvaguarda)
            if self._antes is not None and configuracao.gravada is not None:
                gravar_a_janela(self._antes, configuracao.gravada)

    def marcar(self, quem: str, *, papel: str = "", fatia: str = "") -> None:
        """Um trecho novo (a janela abre, se estava fechada), com a marca lida sem processo; o mesmo de antes segue."""
        self.abrir()
        if self._antes is None or (self._trechos and self._trechos[-1].quem == quem):
            return
        self._trechos.append(Trecho(quem, papel, fatia, marca_do_humano(self._antes)))

    def fechar(self) -> None:
        """A conferência do que mudou desde a foto de antes, com quem rodou no trecho de cada mudança; fechada, nada."""
        antes, trechos = self._fechada()
        mexido = mexido_desde(antes, self._configuracao.outros_goals) if antes is not None else None
        if antes is not None and mexido is not None:
            self._relatar(trechos, mexido, marca_do_humano(antes))

    def conferir_o_git(self) -> None:
        """Logo depois da sessão, antes de qualquer git: os arquivos que mudam o git, relidos em bytes; mudou algum, a janela
        fecha e o laço para sem rodar git (`GitDoHumanoMexido`). Iguais, ou sem janela, nada."""
        mexido = conferir_os_arquivos_do_git(self._antes) if self._antes is not None else None
        if self._antes is not None and mexido is not None:
            marca = marca_do_humano(self._antes)
            self._relatar(self._fechada()[1], mexido, marca)

    def retomar(self) -> None:
        """Antes do primeiro git da chamada: a janela que a execução que caiu deixou gravada, conferida pelos arquivos que
        mudam o git, sem processo, e apagada; mudou algum, o laço para sem rodar git (`GitDoHumanoMexido`)."""
        caminho = self._configuracao.gravada
        antes = foto_gravada(caminho) if caminho is not None and self._antes is None else None
        apagar_a_gravada(caminho if antes is not None else None)
        mexido = conferir_os_arquivos_do_git(antes) if antes is not None else None
        if mexido is not None:
            self._relatar((), replace(mexido, durante=Durante(NA_QUEDA)), {})

    def _fechada(self) -> tuple[FotoDoHumano | None, tuple[Trecho, ...]]:
        """A janela fechada (a gravação sai), e a foto de antes e os trechos que ela tinha."""
        antes, trechos = self._antes, tuple(self._trechos)
        self._antes, self._trechos = None, []
        apagar_a_gravada(self._configuracao.gravada if antes is not None else None)
        return antes, trechos

    def _relatar(self, trechos: Sequence[Trecho], mexido: HumanoMexido | None, final: Mapping[str, str]) -> None:
        """O que mudou vai ao livro-razão, com quem rodou, e a perda para o laço; a do arquivo do git, sem mais git."""
        if mexido is None:
            return
        sessoes = [trecho for trecho in trechos if trecho.papel]
        papel = sessoes[0].papel if sessoes else PAPEL_DO_ORQUESTRADOR
        fatia = next((trecho.fatia for trecho in trechos if trecho.fatia), "")
        mexido = mexido if mexido.durante.texto else replace(mexido, durante=durante(trechos, final, mexido))
        try:
            relatar(mexido, papel, fatia, registrar=self._configuracao.registrar)
        except RepositorioDoHumanoMexido as erro:
            if not mexido.git_mexido:
                raise
            raise GitDoHumanoMexido(erro.mensagem, erro.contexto) from None

    @contextmanager
    def trecho(self, quem: str = "") -> Iterator[None]:
        """O bloco dentro da janela: na aberta, um trecho dela (sem `quem`, os trechos que ele marcar); sem janela, uma só do
        bloco, que fecha quando ele acaba."""
        propria = not self.aberta
        if quem:
            self.marcar(quem)
        else:
            self.abrir()
        try:
            yield
        finally:
            if propria:
                self.fechar()


def marca_do_humano(antes: FotoDoHumano) -> dict[str, str]:
    """O sha256 de cada arquivo que a foto listou, dos que mudam o git e das refs, pelo nome que a conferência usa; só
    leitura de arquivo."""
    vigia = antes.vigia
    refs = replace(vigia, arquivos=(vigia.pasta_do_git / "HEAD", vigia.comum / "packed-refs"), pastas=(vigia.comum / "refs",))
    listados = {caminho: conteudo_do_arquivo(antes.repositorio / caminho) for caminho in antes.listados}
    return {**listados, **ler_os_arquivos_do_git(vigia), **ler_os_arquivos_do_git(refs)}


def durante(trechos: Sequence[Trecho], final: Mapping[str, str], mexido: HumanoMexido) -> Durante:
    """Quem rodou nos trechos das perdas (sem perda, dos avanços): o texto, se foi só o código do agente fora da sessão e as
    sessões que não mexeram ali."""
    if not trechos:
        return Durante(SEM_TRECHO)
    culpados = _trechos_das_mudancas(trechos, final, mexido.perdas or mexido.avancos)
    fora = not any(trechos[indice].papel for indice in culpados)
    limpas = [trecho.quem for indice, trecho in enumerate(trechos) if trecho.papel and indice not in culpados] if fora else []
    return Durante(" e ".join(dict.fromkeys(trechos[indice].quem for indice in culpados)), fora, " e ".join(dict.fromkeys(limpas)))


def _trechos_das_mudancas(trechos: Sequence[Trecho], final: Mapping[str, str], textos: Sequence[str]) -> tuple[int, ...]:
    """O trecho em que mudou por último o arquivo de cada mudança; todos, quando alguma não é de arquivo marcado."""
    marcas = [*(trecho.marca for trecho in trechos), final]
    dono = {chave: indice for indice in range(len(trechos)) for chave in _mudadas(marcas[indice], marcas[indice + 1])}
    grupos = [{indice for chave, indice in dono.items() if _toca(chave, texto)} for texto in textos if not texto.startswith(SEM_ARQUIVO)]
    if not grupos or not all(grupos):
        return tuple(range(len(trechos)))
    return tuple(sorted(set().union(*grupos)))


def _mudadas(antes: Mapping[str, str], depois: Mapping[str, str]) -> set[str]:
    """As chaves cuja marca mudou de uma para a outra."""
    return {chave for chave in set(antes) | set(depois) if antes.get(chave) != depois.get(chave)}


def _toca(chave: str, texto: str) -> bool:
    """A mudança da conferência é do arquivo marcado: o caminho (na árvore ou no índice), o arquivo do git ou a ref."""
    if texto.startswith("ref "):
        nome = texto.removeprefix("ref ").partition(" ")[0]
        return chave.endswith(("/packed-refs", f"/{nome}"))
    return texto.startswith((f"{chave} ", f"indice {chave}:"))
