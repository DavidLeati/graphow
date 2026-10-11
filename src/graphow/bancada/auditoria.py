"""`graphow bancada auditar`: o auditor do laboratório numa sessão `claude -p`, e o placar extraído do relatório.

O auditor recebe o prompt de `bancada/auditor.md` preenchido com o repositório
e a spec da execução, o ramo descrito como os auditores do laboratório o
receberam e as sondas do projeto. Ele roda na pasta da execução, fora do
repositório que audita (um CLAUDE.md que o agente tenha deixado ali não o
orienta), com um banco graphow só dele: o da execução fica com o que a
arquitetura gravou.

Do relatório sai a linha `PLACAR:`, no formato que o prompt pede. A leitura
aceita o que um modelo costuma mudar na linha (negrito, acento, `não atende`
com espaço) e exige os números na ordem do formato; sem linha legível, o
placar fica nulo e a auditoria sai com erro, em vez de um número inventado.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from graphow.bancada.entrega import descrever_ramo, ler_estado_da_entrega
from graphow.bancada.execucao import ARQUIVO_DA_EXECUCAO, VERSAO_DO_REGISTRO, gravar_json, ler_json
from graphow.bancada.medicao import Invocacao, medir
from graphow.bancada.projetos import Bancada, preencher_modelo
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
    """A sessão do auditor sobre a execução: prompt preenchido, pasta da execução e banco próprio."""
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
        pasta=execucao,
        arquivo_stream=pasta / "auditor.jsonl",
        modelo=MODELO_DO_AUDITOR,
        modo_de_permissao=PERMISSAO_DO_AUDITOR,
        banco_graphow=pasta / "graphow.db",
        tempo_limite_s=tempo_limite_s,
    )


def auditar(execucao: Path, pedido: PedidoDeSessao, sessoes: ExecutorDeSessao, *, transcricoes: Path | None) -> dict[str, Any]:
    """Roda o auditor, guarda prompt e relatório e grava `auditoria.json` com o placar."""
    pedido.arquivo_stream.parent.mkdir(parents=True, exist_ok=True)
    (pedido.arquivo_stream.parent / "prompt.md").write_text(pedido.prompt, encoding="utf-8", newline="\n")
    resultado = sessoes.rodar(pedido)
    (pedido.arquivo_stream.parent / "relatorio.md").write_text(resultado.texto_final, encoding="utf-8", newline="\n")
    placar = extrair_placar(resultado.texto_final)
    registro = {
        "versao": VERSAO_DO_REGISTRO,
        "execucao": execucao.name,
        "placar": placar.em_dicionario() if placar else None,
        "bloqueantes_listados": list(bloqueantes_listados(resultado.texto_final)),
        "erro": _erro_da_auditoria(resultado, placar),
        "relatorio": f"{PASTA_DA_AUDITORIA}/relatorio.md",
        "prompt": f"{PASTA_DA_AUDITORIA}/prompt.md",
        "metricas": _metricas_do_auditor(resultado, transcricoes),
        "sessao": resultado.em_dicionario(),
    }
    gravar_json(execucao / ARQUIVO_DA_AUDITORIA, registro)
    return registro


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
        return f"a sessao do auditor terminou com erro (codigo {resultado.codigo_saida}, tempo esgotado: {resultado.tempo_esgotado})"
    return "" if placar else "o relatorio do auditor nao tem linha PLACAR legivel"


def _metricas_do_auditor(resultado: ResultadoDeSessao, transcricoes: Path | None) -> dict[str, Any]:
    """Quanto a auditoria custou, com a mesma medição das execuções."""
    invocacao = Invocacao(resultado.session_id, resultado.inicio, resultado.fim, resultado.leitura.resultado)
    return medir((invocacao,), transcricoes).em_dicionario()
