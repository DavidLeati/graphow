"""O briefing de cada sessão, montado por código a partir do livro-razão e do git.

O agente não lê o grafo: tudo o que ele precisa chega aqui, com o texto
inteiro dos critérios e das decisões, citados pelo código. O autor de aceite
recebe a spec, os critérios, as decisões e a suíte. O executor recebe a fatia,
os critérios que ela cobre com os testes de aceite que os provam, todas as
decisões, o comando da suíte, o que as fatias anteriores entregaram (assuntos
e hashes dos commits, diff resumido da anterior), a resposta do humano à
dúvida dele e, numa nova tentativa, o erro da anterior. O verificador recebe
só a spec, o plano, os testes de aceite e o commit: nada das sessões que
implementaram.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.historico_da_correcao import chamadas_que_falharam
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada, MarcoRegistrado
from graphow.orquestrador.saida_do_aceite import PASTA_DO_ACEITE, SaidaDoAceite
from graphow.orquestrador.suite import descrever_shell, shell_dos_agentes

LIMITE_DO_ERRO: int = 6000


def _criterios(plano: Mapping[str, Any], ids: Sequence[str] | None = None) -> list[str]:
    """Os critérios do plano por extenso, todos ou só os pedidos."""
    return [
        f"- {c['id']} ({c['verificacao']}): {c['texto']}"
        for c in plano.get("criterios", []) if ids is None or c["id"] in ids
    ]


def _criterios_com_aceite(estado: EstadoDoGoal, ids: Sequence[str] | None = None) -> list[str]:
    """Os critérios por extenso, cada um com os testes de aceite e a checagem que o provam."""
    plano, aceite = estado.plano or {}, SaidaDoAceite.do_livro(estado.aceite)
    linhas: list[str] = []
    for criterio in plano.get("criterios", []):
        if ids is not None and criterio["id"] not in ids:
            continue
        linhas.append(f"- {criterio['id']} ({criterio['verificacao']}): {criterio['texto']}")
        provas = aceite.do_criterio(str(criterio["id"]))
        linhas += [f"  - teste de aceite `{t.arquivo}::{t.nome}`: `{t.comando}`" for t in (provas.testes if provas else ())]
        linhas += [f"  - checagem: {passo}" for passo in (provas.checagem if provas else ())]
    return linhas


def _decisoes(plano: Mapping[str, Any]) -> list[str]:
    """As decisões do plano por extenso, com o motivo."""
    return [f"- {d['id']}: {d['texto']} Motivo: {d['motivo']}" for d in plano.get("decisoes", [])]


def _bloco(titulo: str, linhas: Sequence[str]) -> str:
    """Uma seção do briefing; vazia quando não há linha."""
    conteudo = [linha for linha in linhas if str(linha).strip()]
    return f"## {titulo}\n" + "\n".join(conteudo) if conteudo else ""


def _juntar(partes: Sequence[str]) -> str:
    """As partes não vazias, separadas por linha em branco."""
    return "\n\n".join(parte for parte in partes if parte.strip()) + "\n"


def briefing_do_planejador(estado: EstadoDoGoal, spec: str, tem_fixados: bool) -> str:
    """O pedido ao planejador: a spec inteira e onde está o repositório."""
    configuracao = estado.configuracao
    ramo = configuracao.ramo if configuracao else ""
    aviso = (
        "Os criterios (C) e as decisoes (D) com id na spec ja foram fixados pelo humano: devolva-os com o mesmo id e o mesmo texto "
        "(o orquestrador grava o texto e o tipo de verificacao do criterio como o humano os escreveu)."
        if tem_fixados else ""
    )
    return _juntar([
        f"# Plano do Goal {estado.id_goal}",
        f"O repositorio esta na pasta atual, na branch {ramo}, criada da base.",
        f"O orquestrador roda o `comando_suite` na raiz da area em {descrever_shell(shell_dos_agentes())}, "
        "o mesmo shell da sua ferramenta Bash: escreva o comando para ele.",
        f"Depois do plano, outra sessao escreve os testes de aceite em `{PASTA_DO_ACEITE}/`, e o orquestrador os roda a parte: "
        "o `comando_suite` nao pode roda-los (em pytest, restrinja a coleta, por exemplo `python -m pytest -q tests`).",
        aviso,
        "## Spec do Goal\n" + spec.strip(),
        "Devolva o plano no JSON do schema.",
    ])


@dataclass(frozen=True)
class ContextoDaFatia:
    """O que o git e o livro-razão dizem em volta da fatia que vai rodar."""

    tentativa: int
    entregues: tuple[str, ...] = ()
    diff_da_anterior: str = ""
    correcoes_anteriores: tuple[str, ...] = ()


def briefing_do_executor(estado: EstadoDoGoal, fatia: FatiaRegistrada, contexto: ContextoDaFatia) -> str:
    """O pedido ao executor da fatia, com tudo o que a governa por extenso."""
    plano = estado.plano or {}
    return _juntar([
        f"# Fatia {fatia.codigo} do Goal {estado.id_goal}: {fatia.titulo}",
        f"Sessao {contexto.tentativa} desta fatia; {fatia.falhas} falha(s) ate agora (na segunda, a fatia vira pendencia). "
        "Pasta: a area de trabalho do Goal, na branch dele.",
        _bloco("Objetivo da fatia", [fatia.texto(m.CAMPO_OBJETIVO), _arquivos(fatia), _correcao(estado, fatia)]),
        _bloco("Achado que esta fatia corrige", _achado_da_correcao(estado, fatia)),
        _bloco("Comandos da verificacao que falharam (reproduza com eles)", chamadas_que_falharam(estado, fatia)),
        _bloco("A mesma falha ja teve correcao num ciclo anterior", list(contexto.correcoes_anteriores)),
        _bloco("Criterios que esta fatia cobre, com os testes de aceite que os provam (nao os altere)",
               _criterios_com_aceite(estado, fatia.lista(m.CAMPO_CRITERIOS))),
        _bloco("Todos os criterios do Goal (contexto)", _criterios(plano)),
        _bloco("Decisoes que o trabalho segue", _decisoes(plano)),
        _bloco("Suite e aceite", _suite_e_aceite(estado)),
        _bloco("O que as fatias anteriores entregaram", [*contexto.entregues, _diff(contexto.diff_da_anterior)]),
        _bloco("Respostas do humano as suas duvidas", _respostas(fatia)),
        _bloco("O autor de aceite respondeu sobre o teste que voce disse errado", _resposta_do_autor(fatia)),
        _modo_autonomo(estado),
        _bloco("A tentativa anterior falhou", _falha_anterior(fatia)),
        "## Spec completa do Goal\n" + str(estado.propriedades.get(m.CAMPO_SPEC, "")).strip(),
    ])


def _suite_e_aceite(estado: EstadoDoGoal) -> list[str]:
    """A suíte, que o orquestrador roda sem os testes de aceite, e o comando que roda só eles."""
    plano, aceite = estado.plano or {}, estado.aceite or {}
    linhas = [f"`{plano.get('comando_suite', '')}`: o orquestrador roda de novo depois de voce, sem os arquivos de "
              f"`{PASTA_DO_ACEITE}/`, e ela precisa passar."]
    if aceite.get("comando"):
        linhas.append(f"Testes de aceite: `{aceite['comando']}` roda todos. Os dos criterios que outras fatias ainda vao "
                      "atender seguem vermelhos ate elas. Nao altere, apague nem mova nada de "
                      f"`{PASTA_DO_ACEITE}/`: se um teste de aceite estiver errado, diga o criterio em `teste_errado` "
                      "e o porque em `duvida`.")
    return linhas


def briefing_do_revisor(estado: EstadoDoGoal, fatia: FatiaRegistrada, mudados: Sequence[str], *, motivo: str = "") -> str:
    """O pedido ao revisor da fatia de risco: a fatia, os critérios dela com os testes de aceite, as decisões e o que mudou."""
    plano = estado.plano or {}
    return _juntar([
        f"# Revisao da fatia de risco {fatia.codigo} do Goal {estado.id_goal}: {fatia.titulo}",
        "A mudanca da fatia esta na pasta atual, fora de commit: veja com `git status` e `git diff HEAD`.",
        _bloco("Objetivo da fatia", [fatia.texto(m.CAMPO_OBJETIVO), _arquivos(fatia), f"Por que ela e revisada: {motivo}" if motivo else ""]),
        _bloco("Criterios que a fatia cobre, com os testes de aceite que os provam", _criterios_com_aceite(estado, fatia.lista(m.CAMPO_CRITERIOS))),
        _bloco("Decisoes que o trabalho segue", _decisoes(plano)),
        _bloco("Arquivos mudados", [f"- {caminho}" for caminho in mudados]),
        _bloco("Suite e aceite", [f"Suite: `{plano.get('comando_suite', '')}` (ja passou, rodada pelo orquestrador). "
                                  f"Testes de aceite: `{(estado.aceite or {}).get('comando', '')}`."]),
        "## Spec completa do Goal\n" + str(estado.propriedades.get(m.CAMPO_SPEC, "")).strip(),
        "Devolva a revisao no JSON do schema.",
    ])


def briefing_do_autor_de_aceite(estado: EstadoDoGoal) -> str:
    """O pedido ao autor de aceite: a spec, os critérios com o tipo de verificação, as decisões e a suíte."""
    plano, configuracao = estado.plano or {}, estado.configuracao
    return _juntar([
        f"# Testes de aceite do Goal {estado.id_goal}: {estado.rotulo}",
        f"O repositorio esta na pasta atual, na branch {configuracao.ramo if configuracao else ''}, antes de qualquer "
        f"implementacao. Escreva os testes so em arquivos novos de `{PASTA_DO_ACEITE}/`.",
        f"Os comandos rodam na raiz em {descrever_shell(shell_dos_agentes())}, o mesmo shell da sua ferramenta Bash.",
        _bloco("Criterios de aceite", _criterios(plano)),
        _bloco("Decisoes", _decisoes(plano)),
        _bloco("Suite do plano", [f"`{plano.get('comando_suite', '')}`: roda sem os testes de aceite; nao a mude."]),
        "## Spec completa do Goal\n" + str(estado.propriedades.get(m.CAMPO_SPEC, "")).strip(),
        "Devolva o JSON do schema.",
    ])


def _arquivos(fatia: FatiaRegistrada) -> str:
    """Os arquivos que o plano previu para a fatia."""
    arquivos = fatia.lista(m.CAMPO_ARQUIVOS_ALVO)
    return f"Arquivos: {', '.join(arquivos)}" if arquivos else ""


def _correcao(estado: EstadoDoGoal, fatia: FatiaRegistrada) -> str:
    """Na fatia de correção, de onde ela veio."""
    origem = fatia.texto(m.CAMPO_CORRIGE)
    return f"Esta fatia corrige um achado bloqueante da verificacao {origem} do Goal." if origem else ""


def _achado_da_correcao(estado: EstadoDoGoal, fatia: FatiaRegistrada) -> list[str]:
    """Cada Achado inteiro que a fatia de correção corrige, o que ele fere e a ordem: o teste de regressão antes."""
    achados = [achado for id_achado in m.achados_da_correcao(fatia.propriedades) if (achado := estado.achado(id_achado))]
    if not achados:
        return []
    plano = estado.plano or {}
    textos = {item["id"]: item["texto"] for item in (*plano.get("criterios", []), *plano.get("decisoes", []))}
    linhas = [linha for achado in achados for linha in (
        f"{achado.id}: {achado.texto('titulo')}",
        f"  Descricao: {achado.texto('descricao')}",
        f"  Prova (como reproduzir): {achado.texto('prova')}",
        *([f"  Local: {achado.texto('local')}"] if achado.texto("local") else []),
        *(f"  Fere {codigo}: {textos.get(codigo, '')}" for codigo in (*achado.lista("criterios"), *achado.lista("decisoes"))),
    )]
    return [*linhas, "Para cada achado, escreva primeiro o teste de regressao que o reproduz e veja-o falhar; so depois corrija. "
            "Os achados ferem o que o humano pediu: corrija no ambito do criterio, mesmo que o defeito ja existisse antes."]


def _diff(diff: str) -> str:
    """O diff resumido da fatia anterior."""
    return f"Diff da fatia anterior:\n```\n{diff}\n```" if diff else ""


def _respostas(fatia: FatiaRegistrada) -> list[str]:
    """Cada dúvida que o humano respondeu, com a resposta, e onde está o que a tentativa pausada tinha feito."""
    respostas = [f"- Pergunta: {d.pergunta}\n  Resposta: {d.resposta or '(sem texto)'}" for d in fatia.duvidas if not d.aberta]
    patch = fatia.texto(m.CAMPO_PATCH)
    if respostas and patch and not fatia.texto(m.CAMPO_ULTIMO_ERRO):
        respostas.append(f"O que a tentativa pausada tinha mudado foi descartado da area e guardado em {patch} (pode ler).")
    return respostas


def _resposta_do_autor(fatia: FatiaRegistrada) -> list[str]:
    """O que o autor de aceite fez com o teste que o executor apontou: refez, ou manteve e por quê."""
    resposta = fatia.propriedades.get("resposta_do_autor_de_aceite")
    if not isinstance(resposta, Mapping):
        return []
    feito = "refez os testes" if resposta.get("mudou") else "manteve os testes"
    return [f"O autor de aceite {feito} de {resposta.get('criterio', '')}: {resposta.get('resumo', '')}",
            "Faca os testes de aceite passarem como estao; se o desacordo continua, a verificacao o julga."]


def _modo_autonomo(estado: EstadoDoGoal) -> str:
    """No modo autônomo, o que o executor faz em vez de perguntar."""
    configuracao = estado.configuracao
    if configuracao is None or configuracao.modo != m.MODO_AUTONOMO:
        return ""
    return ("## Modo autonomo\nNao ha humano para responder: nao ha duvida. Decida pela spec e registre em `decisoes` cada "
            "decisao que tomou por conta propria (questao, decisao, motivo); o humano as revisa depois. A unica parada e "
            "`teste_errado`: um teste de aceite esta errado; devolva `status` `teste_errado`, o criterio em `teste_errado` e o "
            "porque em `duvida`.")


def _falha_anterior(fatia: FatiaRegistrada) -> list[str]:
    """O erro da tentativa anterior e onde está o que ela tinha mudado."""
    erro = fatia.texto(m.CAMPO_ULTIMO_ERRO)
    if not erro:
        return []
    patch = fatia.texto(m.CAMPO_PATCH)
    linhas = [erro[-LIMITE_DO_ERRO:]]
    if patch:
        linhas.append(f"O que ela tinha mudado foi descartado da area e guardado em {patch} (pode ler).")
    return linhas


def briefing_do_verificador(estado: EstadoDoGoal, commit: str, entregues: Sequence[str], *, marco: MarcoRegistrado) -> str:
    """O pedido ao verificador do marco: spec, critérios que ele julga, decisões, suíte e o commit, sem nada de quem implementou."""
    plano = estado.plano or {}
    return _juntar([
        f"# Verificacao do Goal {estado.id_goal}: {estado.rotulo}",
        f"Commit verificado: {commit}. A pasta atual esta nesse commit.",
        _alcance_do_marco(marco),
        _bloco("Suite", [f"`{plano.get('comando_suite', '')}`"]),
        _bloco("Criterios que esta verificacao julga, com os testes de aceite e a checagem", _criterios_com_aceite(estado, marco.criterios)),
        _bloco("Testes de aceite", [f"`{(estado.aceite or {}).get('comando', '')}` roda todos. Depois de voce, o orquestrador "
                                    "roda cada teste de aceite dos criterios julgados: teste vermelho reprova o criterio."]),
        _bloco("Decisoes", _decisoes(plano)),
        _bloco("Desacordos sobre testes de aceite (julgue o criterio)", _desacordos(estado)),
        _bloco("Commits do Goal desde a base", list(entregues)),
        "## Spec completa do Goal\n" + str(estado.propriedades.get(m.CAMPO_SPEC, "")).strip(),
        "Devolva a verificacao no JSON do schema, com um parecer para cada criterio que esta verificacao julga "
        + ("e para cada decisao" if marco.final else "(e para as decisoes que o marco toca)")
        + ". O orquestrador grava as chamadas Bash desta sessao, com o codigo de saida e um trecho da saida: na prova, "
        "cite o comando que rodou e o que ele mostrou. Depois de voce, ele roda a suite nesse commit: suite vermelha "
        "reprova a entrega.",
    ])


def _desacordos(estado: EstadoDoGoal) -> list[str]:
    """O executor que disse que um teste de aceite está errado e o autor que o manteve: a verificação julga o critério."""
    linhas = []
    for fatia in estado.fatias:
        resposta, desacordo = fatia.propriedades.get("resposta_do_autor_de_aceite"), fatia.propriedades.get("desacordo_sobre_o_teste")
        if isinstance(resposta, Mapping) and not resposta.get("mudou"):
            linhas.append(f"- {resposta.get('criterio')}: o executor de {fatia.codigo} disse que o teste esta errado; o autor o manteve: "
                          f"{resposta.get('resumo', '')}")
        if isinstance(desacordo, Mapping):
            linhas.append(f"- {desacordo.get('criterio')}: o executor de {fatia.codigo} insistiu: {desacordo.get('argumento', '')}")
    return linhas


def _alcance_do_marco(marco: MarcoRegistrado) -> str:
    """O que esta verificação cobre: o marco, ou o Goal inteiro na final."""
    if marco.final:
        return f"Esta e a verificacao final ({marco.id}), sobre o Goal inteiro: julgue todos os criterios e todas as decisoes."
    return (
        f"Esta e a verificacao do marco {marco.id} ({marco.titulo}), fatias {', '.join(marco.fatias)}: julgue os criterios que "
        "ele completa. Os criterios de marcos seguintes ainda nao foram construidos: nao os julgue nem os cite em achado."
    )


def pedido_de_correcao_da_saida(problemas: Sequence[str]) -> str:
    """O que vai à mesma sessão quando a saída dela não conferiu."""
    lista = "\n".join(f"- {problema}" for problema in problemas)
    return f"A sua saida nao conferiu com o que o orquestrador precisa:\n{lista}\n\nDevolva de novo o JSON inteiro, corrigido."
