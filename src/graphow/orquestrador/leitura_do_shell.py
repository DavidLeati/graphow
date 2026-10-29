"""A leitura de um comando Bash em comandos simples, para a trava do git decidir sobre cada um.

Não é um shell inteiro; é o que basta para achar, no texto que o agente manda
ao Bash, cada comando simples e as palavras dele já sem aspas:
- os separadores são `&&`, `||`, `;`, `|`, `&`, a quebra de linha e os
  parênteses de subshell; no `case`, o padrão até o `)` não é comando;
- o texto de cada substituição (`$(...)`, crase, `<(...)`, `>(...)`, e as
  que estão dentro de `${...}`, de `$((...))` e do heredoc sem aspas) volta
  como texto, para ser lido de novo como comando;
- o heredoc e o here-string viram a entrada do comando que os recebe, e o
  alvo de redirecionamento sai das palavras.
A palavra cujo valor só o shell sabe (variável, substituição, glob, chaves com
vírgula, `$'...'`) fica marcada como dinâmica. O que esta leitura não fecha
(aspas, parêntese, substituição ou heredoc sem fim) é `ComandoIlegivel`, e
quem decide recusa o que não leu. Só usa a biblioteca padrão: roda no hook.
"""

from dataclasses import dataclass
import re

SEPARADORES: tuple[str, ...] = ("&&", "||", ";;&", ";;", ";&", "|&", ";", "|", "&", "(", ")")
# Os que fecham um item do `case`: depois deles vem o padrão seguinte, ou o `esac`.
FIM_DO_ITEM_DO_CASE: frozenset[str] = frozenset({";;", ";;&", ";&"})
PALAVRAS_RESERVADAS: frozenset[str] = frozenset({"!", "{", "}", "if", "then", "else", "elif", "fi", "do", "done",
                                                 "while", "until", "function"})
REDIRECIONAMENTOS: tuple[str, ...] = ("<<<", "<<-", "&>>", "<<", ">>", "<&", ">&", "<>", ">|", "&>", "<", ">")
INICIO_DE_OPERADOR: str = ";&|()<>"
ESCAPAVEIS_NAS_ASPAS: str = '$`"\\\n'
NOME_DE_VARIAVEL: re.Pattern[str] = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
PARES: dict[str, str] = {"(": ")", "{": "}"}


class ComandoIlegivel(ValueError):
    """O texto não fecha como shell: aspas, parêntese, substituição ou heredoc sem fim."""


@dataclass(frozen=True)
class Palavra:
    """Uma palavra do comando, sem aspas; dinâmica quando o valor só se sabe ao rodar."""

    texto: str
    dinamica: bool = False
    atribuicao: bool = False

    @property
    def nome_atribuido(self) -> str:
        """O nome da variável de `NOME=valor`; vazio quando a palavra não é atribuição."""
        return self.texto.split("=", 1)[0] if self.atribuicao else ""


@dataclass(frozen=True)
class ComandoSimples:
    """Um comando simples: as palavras e o texto que entra por heredoc ou here-string."""

    palavras: tuple[Palavra, ...]
    entrada: str | None = None
    entrada_dinamica: bool = False


@dataclass(frozen=True)
class LeituraDoShell:
    """Os comandos simples do texto e o texto de cada substituição que ele faz."""

    comandos: tuple[ComandoSimples, ...]
    substituicoes: tuple[str, ...]


def ler_shell(texto: str) -> LeituraDoShell:
    """Os comandos simples e as substituições do texto; `ComandoIlegivel` quando ele não fecha."""
    return _Leitor(texto).ler()


def substituicoes_em(texto: str) -> list[str]:
    """O texto de cada `$(...)` e crase de um trecho que o shell expande sem separar em palavras."""
    achadas: list[str] = []
    i = 0
    while i < len(texto):
        i = _depois_da_substituicao(texto, i, achadas)
    return achadas


def _depois_da_substituicao(texto: str, i: int, achadas: list[str]) -> int:
    """Onde a busca de substituições segue; a que começa em `i` vai para `achadas`."""
    if texto[i] == "\\":
        return i + 2
    if texto.startswith("$(", i):
        fim = fechamento(texto, i + 1)
        achadas.append(texto[i + 2:fim])
        return fim + 1
    if texto[i] == "`":
        fim = _fim_da_crase(texto, i)
        achadas.append(_texto_da_crase(texto[i + 1:fim]))
        return fim + 1
    return i + 1


def fechamento(texto: str, abre: int) -> int:
    """O índice do parêntese ou da chave que fecha o de `abre`, pulando aspas e escapes."""
    abertura, fecho = texto[abre], PARES[texto[abre]]
    profundidade, i = 0, abre
    while i < len(texto):
        caractere = texto[i]
        if caractere == "\\" or caractere in "'\"":
            i = i + 2 if caractere == "\\" else fim_das_aspas(texto, i) + 1
            continue
        profundidade += 1 if caractere == abertura else -1 if caractere == fecho else 0
        if profundidade == 0:
            return i
        i += 1
    raise ComandoIlegivel(f"'{abertura}' sem '{fecho}'")


def fim_das_aspas(texto: str, abre: int) -> int:
    """O índice da aspa que fecha a de `abre`; nas duplas, pula escapes e substituições."""
    if texto[abre] == "'":
        fim = texto.find("'", abre + 1)
        if fim < 0:
            raise ComandoIlegivel("aspas simples sem fecho")
        return fim
    i = abre + 1
    while i < len(texto) and texto[i] != '"':
        i = _depois_nas_aspas(texto, i)
    if i >= len(texto):
        raise ComandoIlegivel("aspas duplas sem fecho")
    return i


def _depois_nas_aspas(texto: str, i: int) -> int:
    """Onde a leitura das aspas duplas segue: depois do escape, da substituição ou da letra."""
    if texto[i] == "\\":
        return i + 2
    if texto.startswith("$(", i):
        return fechamento(texto, i + 1) + 1
    return i + 1


def _fim_da_crase(texto: str, abre: int) -> int:
    """O índice da crase que fecha a de `abre`."""
    i = abre + 1
    while i < len(texto) and texto[i] != "`":
        i += 2 if texto[i] == "\\" else 1
    if i >= len(texto):
        raise ComandoIlegivel("crase sem fecho")
    return i


def _texto_da_crase(bruto: str) -> str:
    """O comando de dentro da crase, com os escapes que ela pede desfeitos."""
    return re.sub(r"\\([`$\\])", r"\1", bruto)


class _Leitor:
    """O cursor da leitura: a palavra em obra, os comandos fechados e o que espera um heredoc."""

    def __init__(self, texto: str) -> None:
        self.texto: str = texto
        self.i: int = 0
        self.comandos: list[tuple[Palavra, ...]] = []
        self.palavras: list[Palavra] = []
        self.entradas: dict[int, tuple[str, bool]] = {}
        self.heredocs: list[tuple[int, str, bool, bool]] = []
        self.substituicoes: list[str] = []
        self.alvo: str = ""
        self.profundidade: int = 0
        self.casos, self.padrao = 0, False
        self._nova_palavra()

    def _nova_palavra(self) -> None:
        """Zera a palavra em obra."""
        self.letras: list[str] = []
        self.iniciada, self.dinamica, self.citada = False, False, False
        self.atribuicao, self.viu_igual, self.colchete, self.chave = False, False, False, False

    def ler(self) -> LeituraDoShell:
        """Lê o texto inteiro e confere que nada ficou aberto."""
        while self.i < len(self.texto):
            self._passo()
        self._fim_do_comando()
        if self.heredocs:
            raise ComandoIlegivel(f"heredoc sem fim: {self.heredocs[0][1]}")
        if self.profundidade or self.casos:
            raise ComandoIlegivel("parentese ou case sem fecho")
        comandos = (
            ComandoSimples(palavras, *self.entradas.get(indice, (None, False)))
            for indice, palavras in enumerate(self.comandos)
            if palavras
        )
        return LeituraDoShell(tuple(comandos), tuple(self.substituicoes))

    def _passo(self) -> None:
        """Consome o próximo caractere ou operador."""
        caractere = self.texto[self.i]
        if caractere in " \t\r":
            self._fim_da_palavra()
            self.i += 1
            return
        if caractere == "\n":
            self._quebra_de_linha()
            return
        if caractere == "#" and not self.iniciada:
            fim = self.texto.find("\n", self.i)
            self.i = len(self.texto) if fim < 0 else fim
            return
        if caractere in INICIO_DE_OPERADOR:
            self._operador()
            return
        self._caractere_da_palavra(caractere)

    def _caractere_da_palavra(self, caractere: str) -> None:
        """Aspas, escape, cifrão, crase ou letra comum da palavra em obra."""
        self.iniciada = True
        especiais = {"\\": self._escape, "'": self._aspas_simples, '"': self._aspas_duplas, "$": self._cifrao,
                     "`": self._crase}
        tratador = especiais.get(caractere)
        if tratador is not None:
            tratador()
            return
        self._letra(caractere)
        self.i += 1

    def _aspas_simples(self) -> None:
        """Aspas simples: o trecho entra literal."""
        fim = fim_das_aspas(self.texto, self.i)
        self._citado(self.texto[self.i + 1:fim])
        self.i = fim + 1

    def _letra(self, caractere: str) -> None:
        """Uma letra fora de aspas: glob, chaves com vírgula e o `=` da atribuição contam aqui."""
        if caractere == "=" and not self.viu_igual:
            self.viu_igual = True
            self.atribuicao = not self.citada and bool(NOME_DE_VARIAVEL.fullmatch("".join(self.letras)))
        self.colchete = self.colchete or caractere == "["
        self.chave = self.chave or caractere == "{"
        glob = caractere in "*?" or (caractere == "]" and self.colchete) or (caractere == "," and self.chave)
        self.dinamica = self.dinamica or glob
        self.letras.append(caractere)

    def _citado(self, trecho: str) -> None:
        """Um trecho entre aspas ou escapado: entra literal e tira da palavra o papel de nome de variável."""
        self.citada = True
        self.letras.append(trecho)

    def _escape(self) -> None:
        """A barra invertida: continuação de linha, ou a letra seguinte literal."""
        seguinte = self.texto[self.i + 1:self.i + 2]
        if seguinte == "\n":
            self.iniciada = bool(self.letras)
        else:
            self._citado(seguinte or "\\")
        self.i += 2

    def _aspas_duplas(self) -> None:
        """Aspas duplas: escapes, substituições e variáveis dentro delas."""
        fim = fim_das_aspas(self.texto, self.i)
        self.citada = True
        self.i += 1
        while self.i < fim:
            self._letra_nas_aspas()
        self.i = fim + 1

    def _letra_nas_aspas(self) -> None:
        """Um passo dentro das aspas duplas: escape, cifrão, crase ou letra literal."""
        caractere = self.texto[self.i]
        if caractere == "\\" and self.texto[self.i + 1] in ESCAPAVEIS_NAS_ASPAS:
            self.letras.append(self.texto[self.i + 1].replace("\n", ""))
            self.i += 2
            return
        if caractere == "$":
            self._cifrao(nas_aspas=True)
            return
        if caractere == "`":
            self._crase()
            return
        self.letras.append(caractere)
        self.i += 1

    def _cifrao(self, *, nas_aspas: bool = False) -> None:
        """`$(...)`, `$((...))`, `${...}`, `$'...'` ou variável: a palavra fica dinâmica.

        `$((` só é conta quando o parêntese de dentro fecha logo antes do de
        fora; senão é `$(` com um subshell dentro, que roda comando.
        """
        self.dinamica = True
        seguinte = self.texto[self.i + 1:self.i + 2]
        if seguinte in ("(", "{"):
            fim = fechamento(self.texto, self.i + 1)
            interno = self.texto[self.i + 2:fim]
            conta = interno.startswith("(") and fechamento(self.texto, self.i + 2) == fim - 1
            self.substituicoes.extend(substituicoes_em(interno) if seguinte == "{" or conta else [interno])
            self.i = fim + 1
        elif seguinte == "'" and not nas_aspas:
            self.i = fim_das_aspas(self.texto, self.i + 1) + 1
        else:
            self.letras.append("$")
            self.i += 1

    def _crase(self) -> None:
        """A substituição por crase: o texto de dentro é lido de novo como comando."""
        fim = _fim_da_crase(self.texto, self.i)
        self.substituicoes.append(_texto_da_crase(self.texto[self.i + 1:fim]))
        self.dinamica = True
        self.i = fim + 1

    def _operador(self) -> None:
        """Substituição de processo, redirecionamento ou separador de comandos."""
        if self.padrao and self.texto[self.i] in "|()":
            self._no_padrao()
            return
        if self.texto.startswith(("<(", ">("), self.i):
            fim = fechamento(self.texto, self.i + 1)
            self.substituicoes.append(self.texto[self.i + 2:fim])
            self.iniciada, self.dinamica, self.i = True, True, fim + 1
            return
        redirecionamento = next((op for op in REDIRECIONAMENTOS if self.texto.startswith(op, self.i)), "")
        if redirecionamento:
            self._redirecionamento(redirecionamento)
            return
        separador = next(op for op in SEPARADORES if self.texto.startswith(op, self.i))
        self._fim_do_comando()
        self.profundidade += {"(": 1, ")": -1}.get(separador, 0)
        if self.profundidade < 0:
            raise ComandoIlegivel("')' sem '('")
        self.padrao = self.padrao or (bool(self.casos) and separador in FIM_DO_ITEM_DO_CASE)
        self.i += len(separador)

    def _no_padrao(self) -> None:
        """No padrão do `case`, `|` separa as alternativas e `)` o fecha: as palavras dele não são comando."""
        self._fim_da_palavra()
        if self.texto[self.i] == ")":
            self.palavras, self.padrao = [], False
        self.i += 1

    def _palavra_do_case(self) -> None:
        """`case x in` passa a esperar o padrão (o x já deu as substituições dele); o `esac` no lugar do comando fecha."""
        textos = [palavra.texto for palavra in self.palavras]
        if len(textos) >= 3 and textos[-3] == "case" and textos[-1] == "in" and set(textos[:-3]) <= PALAVRAS_RESERVADAS:
            self.palavras, self.casos, self.padrao = [], self.casos + 1, True
        elif self.casos and textos == ["esac"]:
            self.palavras, self.casos, self.padrao = [], self.casos - 1, False

    def _redirecionamento(self, operador: str) -> None:
        """O operador de redirecionamento; o descritor numérico antes dele não é palavra."""
        if self.iniciada and not self.citada and "".join(self.letras).isdigit():
            self._nova_palavra()
        self._fim_da_palavra()
        if self.alvo:
            raise ComandoIlegivel(f"redirecionamento sem alvo antes de {operador}")
        self.alvo = operador
        self.i += len(operador)

    def _fim_da_palavra(self) -> None:
        """Fecha a palavra em obra: vai às palavras do comando, ou é o alvo do redirecionamento."""
        if not self.iniciada:
            return
        palavra = Palavra("".join(self.letras), self.dinamica, self.atribuicao)
        citada = self.citada
        self._nova_palavra()
        alvo, self.alvo = self.alvo, ""
        if not alvo:
            self.palavras.append(palavra)
            self._palavra_do_case()
        if alvo in ("<<", "<<-"):
            self.heredocs.append((len(self.comandos), palavra.texto, citada, alvo == "<<-"))
        if alvo == "<<<":
            self.entradas[len(self.comandos)] = (palavra.texto, palavra.dinamica)

    def _fim_do_comando(self) -> None:
        """Fecha o comando simples em obra."""
        self._fim_da_palavra()
        if self.alvo:
            raise ComandoIlegivel(f"redirecionamento sem alvo: {self.alvo}")
        self.comandos.append(tuple(self.palavras))
        self.palavras = []

    def _quebra_de_linha(self) -> None:
        """A quebra de linha fecha o comando e começa os heredocs que esperavam por ela."""
        self._fim_do_comando()
        self.i += 1
        for indice, delimitador, citado, sem_tabs in self.heredocs:
            corpo = self._corpo_do_heredoc(delimitador, sem_tabs)
            self.entradas[indice] = (corpo, not citado and ("$" in corpo or "`" in corpo))
            self.substituicoes.extend([] if citado else substituicoes_em(corpo))
        self.heredocs = []

    def _corpo_do_heredoc(self, delimitador: str, sem_tabs: bool) -> str:
        """As linhas até o delimitador; sem ele, o heredoc não fecha."""
        linhas: list[str] = []
        while self.i <= len(self.texto):
            fim = self.texto.find("\n", self.i)
            linha = self.texto[self.i:] if fim < 0 else self.texto[self.i:fim]
            self.i = len(self.texto) + 1 if fim < 0 else fim + 1
            if (linha.lstrip("\t") if sem_tabs else linha).rstrip("\r") == delimitador:
                self.i = min(self.i, len(self.texto))
                return "\n".join(linhas)
            linhas.append(linha)
        raise ComandoIlegivel(f"heredoc sem fim: {delimitador}")
