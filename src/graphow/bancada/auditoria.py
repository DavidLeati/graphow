"""`graphow bancada auditar`: o auditor do laboratório numa sessão `claude -p`, e o placar extraído do relatório.

O auditor recebe o prompt de `bancada/auditor.md` preenchido com o repositório
e a spec da execução, por caminho absoluto, o ramo descrito como os auditores
do laboratório o receberam e as sondas do projeto. Ele roda em `auditoria/`,
uma pasta só dele dentro da execução: fora do repositório que audita (um
CLAUDE.md que o agente tenha deixado ali não o orienta) e fora da pasta da
execução, onde ficam o stream e o relato final do implementador em
`sessoes/`. O auditor julga a entrega pelo que roda, e o relato de quem
implementou não pode estar à mão, no diretório de trabalho dele. O banco
graphow também é só dele: o da execução fica com o que a arquitetura gravou.

Do relatório sai a linha `PLACAR:`, no formato que o prompt pede. A leitura
aceita o que um modelo costuma mudar na linha (negrito, acento, `não atende`
com espaço) e exige os números na ordem do formato; sem linha legível, o
placar fica nulo e a auditoria sai com erro, em vez de um número inventado.

Uma auditoria nunca apaga outra. A execução que já tem `auditoria.json` ou a
pasta `auditoria/` (a de um auditor que morreu no meio também conta) recusa;
com `refazer`, a anterior é guardada com o sufixo `-anterior-N` antes de a
nova começar. E o `auditoria.json` existe desde antes da sessão, dizendo que
ela não terminou: se o auditor morrer, e com ele o processo da bancada, o
registro fica com o erro, e não ausente. A sessão que não abre, ou que morre
no tempo limite, também grava o erro.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from graphow.bancada.entrega import descrever_ramo, ler_estado_da_entrega
from graphow.bancada.execucao import ARQUIVO_DA_EXECUCAO, VERSAO_DO_REGISTRO, gravar_json, ler_json
from graphow.bancada.medicao import Invocacao, Medicao, medir
from graphow.bancada.projetos import Bancada, ErroDaBancada, preencher_modelo
from graphow.core.exceptions import GraphowError
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao

ARQUIVO_DA_AUDITORIA: str = "auditoria.json"
PASTA_DA_AUDITORIA: str = "auditoria"
MODELO_DO_AUDITOR: str = "opus"
PERMISSAO_DO_AUDITOR: str = "bypassPermissions"
TEMPO_LIMITE_DO_AUDITOR_S: float = 3600.0
MARCA_DO_PLACAR: str = "PLACAR"
PADRAO_DOS_CRITERIOS: re.Pattern[str] = re.compile(
    r"atende\D{0,3}(\d+)\s*/\s*parcial\D{0,3}(\d+)\s*/\s*n[aã]o[_ ]atende\D{0,3}(\d+)", re.IGNORECASE
)
PADRAO_DAS_SONDAS: re.Pattern[str] = re.compile(r"ok\D{0,3}(\d+)\s*/\s*defeitos?\D{0,3}(\d+)", re.IGNORECASE)
PADRAO_DOS_BLOQUEANTES: re.Pattern[str] = re.compile(r"bloqueantes?\D{0,3}(\d+)", re.IGNORECASE)
PADRAO_DE_ITEM: re.Pattern[str] = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(?P<texto>.+)$")
SUFIXO_DA_ANTERIOR: str = "-anterior-{numero}"
ERRO_SESSAO_NAO_TERMINOU: str = "a sessao do auditor nao terminou (interrompida, ou ainda rodando)"


@dataclass(frozen=True)
class Placar:
    """A linha `PLACAR:` do auditor, em números."""

    atende: int
    parcial: int
    nao_atende: int
    sondas_ok: int
    sondas_defeito: int
    bloqueantes: int
    linha: str

    def em_dicionario(self) -> dict[str, Any]:
        """O placar para gravar em JSON, com a linha original."""
        return {
            "criterios": {"atende": self.atende, "parcial": self.parcial, "nao_atende": self.nao_atende},
            "sondas_ok": self.sondas_ok,
            "sondas_defeito": self.sondas_defeito,
            "bloqueantes": self.bloqueantes,
            "linha": self.linha,
        }


def extrair_placar(texto: str) -> Placar | None:
    """O último `PLACAR:` legível do relatório; None quando nenhum traz os números."""
    candidatas = [linha.strip() for linha in texto.splitlines() if MARCA_DO_PLACAR in linha]
    legiveis = [placar for placar in map(_ler_linha_do_placar, candidatas) if placar is not None]
    return legiveis[-1] if legiveis else None


def bloqueantes_listados(texto: str) -> tuple[str, ...]:
    """Os itens de lista depois da última linha `PLACAR:`, onde o prompt pede os defeitos bloqueantes."""
    linhas = texto.splitlines()
    posicoes = [indice for indice, linha in enumerate(linhas) if MARCA_DO_PLACAR in linha]
    if not posicoes:
        return ()
    itens = (PADRAO_DE_ITEM.match(linha) for linha in linhas[posicoes[-1] + 1 :])
    return tuple(item["texto"].strip() for item in itens if item is not None)


def pedido_do_auditor(execucao: Path, bancada: Bancada, tempo_limite_s: float = TEMPO_LIMITE_DO_AUDITOR_S) -> PedidoDeSessao:
    """A sessão do auditor sobre a execução: prompt preenchido, pasta própria em `auditoria/` e banco próprio."""
    registro = ler_json(execucao / ARQUIVO_DA_EXECUCAO)
    projeto = bancada.projeto(registro["projeto"])
    repositorio = execucao / registro["repositorio"]
    valores = {
        "REPO": str(repositorio),
        "SPEC": str(execucao / registro["spec"]),
        "RAMO": descrever_ramo(ler_estado_da_entrega(repositorio, projeto)),
        "SONDAS": projeto.texto_das_sondas(),
    }
    pasta = execucao / PASTA_DA_AUDITORIA
    return PedidoDeSessao(
        prompt=preencher_modelo(bancada.modelo_do_auditor(), valores),
        pasta=pasta,
        arquivo_stream=pasta / "auditor.jsonl",
        modelo=MODELO_DO_AUDITOR,
        modo_de_permissao=PERMISSAO_DO_AUDITOR,
        banco_graphow=pasta / "graphow.db",
        tempo_limite_s=tempo_limite_s,
    )


def auditar(
    execucao: Path, pedido: PedidoDeSessao, sessoes: ExecutorDeSessao, *, transcricoes: Path | None, refazer: bool = False
) -> dict[str, Any]:
    """Roda o auditor, guarda prompt e relatório e grava `auditoria.json` com o placar ou com o erro.

    A auditoria que já existe recusa; com `refazer`, ela é guardada antes.
    """
    anterior = reservar_auditoria(execucao, refazer=refazer)
    pasta = pedido.arquivo_stream.parent
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "prompt.md").write_text(pedido.prompt, encoding="utf-8", newline="\n")
    base = {"versao": VERSAO_DO_REGISTRO, "execucao": execucao.name, "prompt": f"{PASTA_DA_AUDITORIA}/prompt.md"}
    base["auditoria_anterior"] = anterior
    gravar_json(execucao / ARQUIVO_DA_AUDITORIA, {**base, **_sem_sessao(ERRO_SESSAO_NAO_TERMINOU)})
    try:
        resultado = sessoes.rodar(pedido)
    except (GraphowError, OSError) as erro:
        motivo = erro.formatar_para_llm() if isinstance(erro, GraphowError) else str(erro)
        registro = {**base, **_sem_sessao(f"a sessao do auditor nao abriu: {motivo}")}
    else:
        registro = {**base, **_com_sessao(resultado, pasta, transcricoes)}
    gravar_json(execucao / ARQUIVO_DA_AUDITORIA, registro)
    return registro


def reservar_auditoria(execucao: Path, *, refazer: bool) -> str | None:
    """Deixa a execução sem auditoria para a nova: recusa se já há uma, ou, com `refazer`, guarda a anterior.

    Devolve o nome com que a anterior foi guardada (`auditoria-anterior-N`, a
    pasta, e o mesmo nome com `.json`), ou None quando não havia nenhuma.
    """
    existentes = [caminho for caminho in (execucao / ARQUIVO_DA_AUDITORIA, execucao / PASTA_DA_AUDITORIA) if caminho.exists()]
    if not existentes:
        return None
    if not refazer:
        raise ErroDaBancada(
            "a execucao ja tem auditoria",
            {"execucao": str(execucao), "existente": ", ".join(c.name for c in existentes), "dica": "use --refazer"},
        )
    sufixo = _sufixo_livre(execucao)
    try:
        for caminho in existentes:
            caminho.rename(caminho.with_name(f"{caminho.stem}{sufixo}{caminho.suffix}"))
    except OSError as erro:
        raise ErroDaBancada("a auditoria anterior nao pode ser guardada", {"execucao": str(execucao), "erro": str(erro)}) from erro
    return f"{PASTA_DA_AUDITORIA}{sufixo}"


def _sufixo_livre(execucao: Path) -> str:
    """O primeiro `-anterior-N` que nenhuma auditoria guardada usa."""
    numero = 1
    while _guardada(execucao, SUFIXO_DA_ANTERIOR.format(numero=numero)):
        numero += 1
    return SUFIXO_DA_ANTERIOR.format(numero=numero)


def _guardada(execucao: Path, sufixo: str) -> bool:
    """Já há uma auditoria guardada com o sufixo, como pasta ou como registro."""
    return (execucao / f"{PASTA_DA_AUDITORIA}{sufixo}").exists() or (execucao / f"{PASTA_DA_AUDITORIA}{sufixo}.json").exists()


def _sem_sessao(erro: str) -> dict[str, Any]:
    """O registro de uma auditoria cuja sessão não chegou ao fim: nada medido, nada lido, só o erro."""
    return {
        "placar": None,
        "bloqueantes_listados": [],
        "erro": erro,
        "relatorio": None,
        "metricas": Medicao(None, None, "", None, ()).em_dicionario(),
        "sessao": None,
    }


def _com_sessao(resultado: ResultadoDeSessao, pasta: Path, transcricoes: Path | None) -> dict[str, Any]:
    """O relatório guardado, o placar lido dele e o custo; sem texto final, não há relatório a guardar."""
    if resultado.texto_final:
        (pasta / "relatorio.md").write_text(resultado.texto_final, encoding="utf-8", newline="\n")
    placar = extrair_placar(resultado.texto_final)
    return {
        "placar": placar.em_dicionario() if placar else None,
        "bloqueantes_listados": list(bloqueantes_listados(resultado.texto_final)),
        "erro": _erro_da_auditoria(resultado, placar),
        "relatorio": f"{PASTA_DA_AUDITORIA}/relatorio.md" if resultado.texto_final else None,
        "metricas": _metricas_do_auditor(resultado, transcricoes),
        "sessao": resultado.em_dicionario(),
    }


def _ler_linha_do_placar(linha: str) -> Placar | None:
    """Os seis números da linha, na ordem do formato; None se faltar algum."""
    criterios = PADRAO_DOS_CRITERIOS.search(linha)
    sondas = PADRAO_DAS_SONDAS.search(linha)
    bloqueantes = PADRAO_DOS_BLOQUEANTES.search(linha)
    if criterios is None or sondas is None or bloqueantes is None:
        return None
    numeros = [int(numero) for numero in (*criterios.groups(), *sondas.groups(), bloqueantes.group(1))]
    return Placar(*numeros, linha=linha)


def _erro_da_auditoria(resultado: ResultadoDeSessao, placar: Placar | None) -> str:
    """Vazio quando a sessão terminou bem e o placar foi lido; senão, o que faltou."""
    if resultado.is_error:
        return f"a sessao do auditor terminou com erro: {resultado.motivo_do_erro}"
    return "" if placar else "o relatorio do auditor nao tem linha PLACAR legivel"


def _metricas_do_auditor(resultado: ResultadoDeSessao, transcricoes: Path | None) -> dict[str, Any]:
    """Quanto a auditoria custou, com a mesma medição das execuções."""
    invocacao = Invocacao(resultado.session_id, resultado.inicio, resultado.fim, resultado.leitura.resultado)
    return medir((invocacao,), transcricoes).em_dicionario()
