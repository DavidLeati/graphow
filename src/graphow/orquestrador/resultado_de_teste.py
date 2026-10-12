"""O que a saída de um teste de aceite diz: passou de verdade, ou falhou pelo motivo certo.

O código de saída não basta. O pytest sai com zero quando o teste foi pulado
(`skip`, `xfail`) e o unittest diz `OK (skipped=1)`: o teste que não rodou não
prova o critério. Por isso o orquestrador lê a saída dos runners que conhece
(pytest, unittest, node:test, jest, vitest, mocha) e só dá o teste por verde
quando ao menos um passou e nenhum foi pulado, esperado falho ou deixado por
fazer. Quando o comando chama um runner conhecido e a saída não tem o resumo
dele, o runner foi trocado ou calado: não passou. A saída de runner que ele não
conhece é lida com cautela: sai com zero, diz alguma coisa e não fala em pular.

O vermelho de antes da implementação também é lido. Ele só vale quando o teste
declarado rodou e falhou numa asserção: erro de import ou de coleta (o pytest
sai com 2, 4 ou 5; o unittest diz `errors=`), comando que não existe (126 e
127) e teste com o nome errado são vermelho pelo motivo errado, e não provam
que o teste mede o critério.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import re

RUNNER_DESCONHECIDO: str = "desconhecido"
CODIGOS_DE_COMANDO_AUSENTE: frozenset[int] = frozenset({126, 127})
# O pytest sai com 1 só quando testes falharam; 2 (interrompido, a coleta falhou), 3, 4 (uso) e 5 (nenhum teste) não são vermelho.
CODIGO_DO_PYTEST_COM_FALHA: int = 1
# As exceções que contam como asserção: a do assert e a do pytest.fail.
EXCECOES_DE_ASSERCAO: frozenset[str] = frozenset({"AssertionError", "Failed", "pytest.fail.Exception", "_pytest.outcomes.Failed"})
PALAVRAS_DE_PULO: re.Pattern[str] = re.compile(r"\b(skip|skipped|skipping|xfail|xfailed|xpass|xpassed|todo|pending|ignored)\b", re.I)
ERRO_FORA_DA_ASSERCAO: re.Pattern[str] = re.compile(
    r"\b(ModuleNotFoundError|ImportError|SyntaxError|IndentationError|NameError|ReferenceError|"
    r"ERR_MODULE_NOT_FOUND|Cannot find module|Test suite failed to run|Failed to load|command not found|is not a function|"
    r"No such file or directory|is not recognized as an internal or external command)\b"
)
MARCAS_DE_FALHA: re.Pattern[str] = re.compile(r"^(FAILED|FAIL:|FAIL |not ok|\s*[✖✕×●]|_{3,} |\s*\d+\) )")
RUNNERS_NO_COMANDO: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pytest", re.compile(r"\b(pytest|py\.test)\b")),
    ("unittest", re.compile(r"\bunittest\b")),
    ("node:test", re.compile(r"\bnode\b.*--test\b")),
    ("vitest", re.compile(r"\bvitest\b")),
    ("jest", re.compile(r"\bjest\b")),
    ("mocha", re.compile(r"\bmocha\b")),
)


@dataclass(frozen=True)
class Contagem:
    """Quantos testes passaram, falharam, deram erro e foram pulados, como o runner disse."""

    runner: str
    passados: int = 0
    falhos: int = 0
    erros: int = 0
    pulados: int = 0


def _somar(runner: str, itens: Iterable[tuple[str, int]], categorias: dict[str, str]) -> Contagem:
    """A contagem dos pares (rótulo, número), pela categoria de cada rótulo; rótulo sem categoria não conta."""
    total = {"passados": 0, "falhos": 0, "erros": 0, "pulados": 0}
    for rotulo, numero in itens:
        categoria = categorias.get(rotulo.strip().lower())
        if categoria:
            total[categoria] += numero
    return Contagem(runner, **total)


_RESUMO_PYTEST = re.compile(r"^=*\s*((?:\d+ [a-z]+(?:, )?)+|no tests ran) in \d+(?:\.\d+)?s\b", re.M)
_PYTEST = {"passed": "passados", "failed": "falhos", "error": "erros", "errors": "erros",
           "skipped": "pulados", "xfailed": "pulados", "xpassed": "pulados"}


# Com `-qq` (o `-q` do comando somado ao `addopts` do projeto) o pytest não imprime o
# resumo, só a linha de progresso: um caractere por teste.
_PROGRESSO_PYTEST = re.compile(r"^([.sxXFE]+)\s+\[\s*\d+%\]\s*$", re.M)
_PROGRESSO = {".": "passados", "s": "pulados", "x": "pulados", "f": "falhos", "e": "erros"}


def _pytest(saida: str) -> Contagem | None:
    """As linhas de resumo do pytest (`1 failed, 2 passed in 0.1s`), somadas; sem elas, a linha de progresso."""
    corpos = _RESUMO_PYTEST.findall(saida)
    if corpos:
        pares = ((rotulo, int(n)) for corpo in corpos for n, rotulo in re.findall(r"(\d+) ([a-z]+)", corpo))
        return _somar("pytest", pares, _PYTEST)
    progresso = "".join(_PROGRESSO_PYTEST.findall(saida))
    return _somar("pytest", ((caractere, 1) for caractere in progresso), _PROGRESSO) if progresso else None


_RAN = re.compile(r"^Ran (\d+) tests? in ", re.M)
_FIM_UNITTEST = re.compile(r"^(?:OK|FAILED)(?: \(([^)]*)\))?\s*$", re.M)
_UNITTEST = {"failures": "falhos", "errors": "erros", "skipped": "pulados", "expected failures": "pulados",
             "unexpected successes": "pulados"}


def _unittest(saida: str) -> Contagem | None:
    """O `Ran N tests` e a linha `OK (...)`/`FAILED (...)` do unittest; os que não falharam nem foram pulados passaram."""
    rodados = [int(n) for n in _RAN.findall(saida)]
    if not rodados:
        return Contagem("unittest") if "NO TESTS RAN" in saida else None
    pares = [(rotulo, int(n)) for detalhe in _FIM_UNITTEST.findall(saida) for rotulo, n in re.findall(r"([a-z ]+)=(\d+)", detalhe)]
    contagem = _somar("unittest", pares, _UNITTEST)
    passados = sum(rodados) - contagem.falhos - contagem.erros - contagem.pulados
    return Contagem("unittest", max(passados, 0), contagem.falhos, contagem.erros, contagem.pulados)


_RESUMO_NODE = re.compile(r"^(?:#|ℹ)\s*(tests|pass|fail|cancelled|skipped|todo) (\d+)\s*$", re.M)
_NODE = {"pass": "passados", "fail": "falhos", "cancelled": "erros", "skipped": "pulados", "todo": "pulados"}


def _node(saida: str) -> Contagem | None:
    """O resumo do node:test (`# pass 1`, ou `ℹ pass 1` no relator spec)."""
    pares = [(rotulo, int(n)) for rotulo, n in _RESUMO_NODE.findall(saida)]
    return _somar("node:test", pares, _NODE) if any(rotulo == "tests" for rotulo, _ in pares) else None


_RESUMO_JEST = re.compile(r"^Tests:\s+(.*?)\d+ total\s*$", re.M)
_RESUMO_VITEST = re.compile(r"^\s*Tests\s+(.*?)(?:\(\d+\))?\s*$", re.M)
_RESUMO_MOCHA = re.compile(r"^\s*(\d+) (passing|failing|pending)\b", re.M)
_JS = {"passed": "passados", "failed": "falhos", "skipped": "pulados", "todo": "pulados", "passing": "passados",
       "failing": "falhos", "pending": "pulados"}


def _jest(saida: str) -> Contagem | None:
    """A linha `Tests: 1 failed, 2 passed, 3 total` do jest."""
    corpos = _RESUMO_JEST.findall(saida)
    pares = ((rotulo, int(n)) for corpo in corpos for n, rotulo in re.findall(r"(\d+) ([a-z]+)", corpo))
    return _somar("jest", pares, _JS) if corpos else None


def _vitest(saida: str) -> Contagem | None:
    """A linha `Tests  1 failed | 2 passed (3)` do vitest (e `Tests  no tests`)."""
    corpos = [corpo for corpo in _RESUMO_VITEST.findall(saida) if "|" in corpo or re.search(r"\d+ [a-z]+|no tests", corpo)]
    pares = ((rotulo, int(n)) for corpo in corpos for n, rotulo in re.findall(r"(\d+) ([a-z]+)", corpo))
    return _somar("vitest", pares, _JS) if corpos else None


def _mocha(saida: str) -> Contagem | None:
    """As linhas `2 passing`, `1 failing` e `1 pending` do mocha."""
    pares = [(rotulo, int(n)) for n, rotulo in _RESUMO_MOCHA.findall(saida)]
    return _somar("mocha", pares, _JS) if pares else None


LEITORES: tuple[Callable[[str], Contagem | None], ...] = (_pytest, _unittest, _node, _jest, _vitest, _mocha)


def runner_do_comando(comando: str) -> str:
    """O runner que o comando chama, quando é um que o orquestrador conhece; senão, desconhecido."""
    return next((nome for nome, padrao in RUNNERS_NO_COMANDO if padrao.search(comando)), RUNNER_DESCONHECIDO)


def ler_saida(saida: str) -> Contagem | None:
    """A contagem do primeiro runner conhecido cujo resumo está na saída; None quando nenhum está."""
    texto = _sem_retorno_de_carro(saida)
    return next((contagem for leitor in LEITORES if (contagem := leitor(texto)) is not None), None)


def _sem_retorno_de_carro(saida: str) -> str:
    """A saída com as quebras de linha do Windows (CRLF) como LF, para o fim de linha das expressões valer."""
    return saida.replace("\r\n", "\n").replace("\r", "\n")


def por_que_nao_passou(comando: str, codigo: int | None, saida: str) -> str:
    """Por que o teste não conta como verde; vazio quando conta."""
    if codigo is None:
        return "o tempo acabou"
    if codigo != 0:
        return f"saiu com codigo {codigo}"
    contagem = ler_saida(saida)
    if contagem is None:
        return _sem_resumo(comando, saida)
    if contagem.pulados:
        return f"o {contagem.runner} diz que {contagem.pulados} teste(s) foram pulados, esperados falhos ou deixados por fazer"
    if contagem.falhos or contagem.erros:
        return f"o {contagem.runner} diz que {contagem.falhos + contagem.erros} teste(s) falharam, mas o comando saiu com zero"
    return "" if contagem.passados else f"o {contagem.runner} diz que nenhum teste passou"


def _sem_resumo(comando: str, saida: str) -> str:
    """A saída sem resumo conhecido: do runner conhecido, não passou; do desconhecido, passa com cautela."""
    runner = runner_do_comando(comando)
    if runner != RUNNER_DESCONHECIDO:
        return f"o comando chama o {runner}, e a saida nao tem o resumo dele: o runner foi trocado, calado ou nao rodou"
    if not saida.strip():
        return "o comando saiu com zero sem dizer nada: nao ha como saber que algum teste rodou"
    pulo = PALAVRAS_DE_PULO.search(saida)
    return f"a saida fala em '{pulo.group(0)}': o teste pode nao ter rodado" if pulo else ""


def por_que_o_vermelho_nao_vale(comando: str, codigo: int | None, saida: str, *, nome: str) -> str:
    """Por que a falha não é a asserção do teste declarado; vazio quando é."""
    saida = _sem_retorno_de_carro(saida)
    if codigo is None:
        return "o tempo acabou: o teste nao terminou"
    if codigo == 0:
        return "o comando saiu com zero"
    if codigo in CODIGOS_DE_COMANDO_AUSENTE:
        return f"saiu com codigo {codigo}: o comando nao existe ou nao executa"
    contagem = ler_saida(saida)
    runner = contagem.runner if contagem is not None else runner_do_comando(comando)
    motivo = _contagem_do_vermelho(contagem, runner, codigo)
    if motivo:
        return motivo
    if not _nome_falhou(saida, nome, conhecido=contagem is not None):
        return f"o teste {nome} nao aparece como falho na saida: o nome esta errado ou ele nao rodou"
    return _falha_fora_da_assercao(saida, runner)


def _contagem_do_vermelho(contagem: Contagem | None, runner: str, codigo: int) -> str:
    """O que a contagem diz contra o vermelho: erro, nenhum falho, código do pytest que não é de falha."""
    if contagem is None:
        return "" if runner == RUNNER_DESCONHECIDO else f"o comando chama o {runner}, e a saida nao tem o resumo dele"
    if contagem.runner == "pytest" and codigo != CODIGO_DO_PYTEST_COM_FALHA:
        return f"o pytest saiu com {codigo}, que nao e falha de teste (2 coleta interrompida, 4 uso errado, 5 nenhum teste)"
    if contagem.erros:
        return f"o {contagem.runner} conta {contagem.erros} erro(s): o teste quebrou fora da assercao (import, coleta, fixture)"
    return "" if contagem.falhos else f"o {contagem.runner} nao conta teste falho"


def _nomes(nome: str) -> tuple[str, ...]:
    """O nome declarado e as formas curtas dele que a saída mostra (sem o arquivo, sem a classe)."""
    curto = nome.split("::")[-1]
    formas = {nome, curto, curto.split("[")[0]}
    if " " not in curto:
        formas.add(curto.split(".")[-1])
    return tuple(forma for forma in formas if len(forma) >= 3)


def _nome_falhou(saida: str, nome: str, *, conhecido: bool) -> bool:
    """O nome aparece numa linha de falha do runner (no runner desconhecido, em qualquer linha)."""
    linhas = saida.splitlines() if not conhecido else [linha for linha in saida.splitlines() if MARCAS_DE_FALHA.match(linha)]
    return any(forma in linha for linha in linhas for forma in _nomes(nome))


_EXCECAO_DO_PYTEST = re.compile(r"^\S+:\d+: ([A-Za-z_][\w.]*)(?::|$)", re.M)
# O fim da linha que o pytest cortou na largura do terminal.
CORTE_DO_PYTEST: str = "..."
_MENSAGEM_DO_FAILED = re.compile(r"^FAILED \S+ - (assert\b|[A-Za-z_][\w.]*)", re.M)


def _falha_fora_da_assercao(saida: str, runner: str) -> str:
    """A falha que não é asserção; vazio quando é.

    No pytest vale a exceção que ele mostra em cada falha; no unittest a
    contagem já separa (`failures` são asserções, `errors` o resto); nos
    outros, o erro de import, sintaxe ou comando que aparece na saída.
    """
    if runner == "unittest":
        return ""
    if runner == "pytest":
        return _excecao_do_pytest(saida)
    erro = ERRO_FORA_DA_ASSERCAO.search(saida)
    return f"a saida mostra '{erro.group(0)}': o teste quebrou antes da assercao" if erro else ""


def _excecao_do_pytest(saida: str) -> str:
    """As exceções das falhas do pytest, do traceback ou da linha FAILED; só asserção vale.

    O pytest corta a linha FAILED na largura do terminal (`- Ass...`): o nome
    cortado não é exceção nenhuma, e vale o que o traceback mostra. Na fumaça
    da rodada 3, o corte custou duas retomadas ao autor de aceite.
    """
    vistas = set(_EXCECAO_DO_PYTEST.findall(saida))
    vistas |= {"AssertionError" if m == "assert" else m for m in _MENSAGEM_DO_FAILED.findall(saida) if not m.endswith(CORTE_DO_PYTEST)}
    if not vistas:
        return "a saida do pytest nao mostra com que excecao o teste falhou (rode-o sem --tb=no)"
    fora = sorted(vistas - EXCECOES_DE_ASSERCAO)
    return f"o teste falhou com {', '.join(fora)}, e nao numa assercao" if fora else ""
