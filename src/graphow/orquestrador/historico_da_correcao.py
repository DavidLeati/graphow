"""O que a fatia de correção recebe além do achado: o comando que o reproduz e, quando a falha volta, a tentativa anterior.

Na bancada, o bloqueante das mensagens em inglês da agenda sobrou depois de
dois ciclos: a correção recebia a prova do verificador, mas não o comando
exato que ele rodou, e a do ciclo seguinte recebia só o `diff --stat` do
commit anterior e o id da verificação. Agora:

- a correção leva as chamadas Bash da verificação que reproduzem o achado (o
  comando, o código e o fim da saída, que o orquestrador tirou do stream): as
  que o verificador marcou em `reproducao` e as que a prova ou a descrição do
  achado citam. Não vão as outras que saíram com erro: a revisão da rodada 3
  viu a correção receber as sondas negativas esperadas (o `lista vazia` que
  sai com 2 de propósito) como "reproduza com eles";
- quando um achado do mesmo arquivo, ou do mesmo critério, já teve correção
  num ciclo anterior do marco, a correção leva o diff daquela tentativa e o
  que a verificação seguinte disse dela;
- e a correção roda em Opus (orquestrador/execucao_da_fatia.py).
"""

from collections.abc import Mapping, Sequence
import re

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.correcoes import area_do_achado
from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada

LIMITE_DO_DIFF: int = 4000
MAXIMO_DE_CHAMADAS: int = 8
MAXIMO_DE_TENTATIVAS_ANTERIORES: int = 2
# O trecho entre crases que a prova cita como comando: duas palavras ou mais (`python cli.py media`, e não `cli.py`).
CITACAO_DE_COMANDO: re.Pattern[str] = re.compile(r"`([^`\n]*\S\s+\S[^`\n]*)`")
CAMPO_REPRODUCAO: str = "reproducao"


def chamadas_que_reproduzem(estado: EstadoDoGoal, fatia: FatiaRegistrada) -> list[str]:
    """As chamadas Bash da verificação que reproduzem os achados da correção, e os comandos marcados que o stream não mostra."""
    verificacao = next((v for v in estado.verificacoes if v.id == fatia.texto(m.CAMPO_CORRIGE)), None)
    chamadas = [c for c in (verificacao.propriedades.get("comandos") or []) if isinstance(c, Mapping)] if verificacao else []
    linhas: list[str] = []
    for achado in (a for id_achado in m.achados_da_correcao(fatia.propriedades) if (a := estado.achado(id_achado))):
        marcados = [str(comando) for comando in achado.lista(CAMPO_REPRODUCAO)]
        texto = "\n".join((achado.texto("prova"), achado.texto("descricao")))
        trechos = [_normal(trecho) for trecho in (*marcados, *CITACAO_DE_COMANDO.findall(texto)) if trecho.strip()]
        escolhidas = [c for c in chamadas if _reproduz(_normal(str(c.get("comando", ""))), trechos, _normal(texto))]
        linhas += [f"- `{c.get('comando', '')}` saiu com {c.get('codigo')}: {str(c.get('saida', ''))[-300:]}" for c in escolhidas]
        vistos = {_normal(str(c.get("comando", ""))) for c in escolhidas}
        linhas += [f"- `{comando}` (o verificador o marcou como reproducao)" for comando in marcados if _normal(comando) not in vistos]
    return list(dict.fromkeys(linhas))[:MAXIMO_DE_CHAMADAS]


def _normal(texto: str) -> str:
    """O comando com os espaços colapsados, para comparar o que a prova cita com o que o stream mostra."""
    return " ".join(texto.split())


def _reproduz(comando: str, trechos: Sequence[str], citado: str) -> bool:
    """A chamada é a que a prova cita, ou contém um comando que o verificador marcou ou citou entre crases."""
    return bool(comando) and (comando in citado or any(trecho == comando or trecho in comando for trecho in trechos))


def tentativas_anteriores(area: GitDoGoal, estado: EstadoDoGoal, fatia: FatiaRegistrada) -> tuple[str, ...]:
    """O diff das correções de ciclos anteriores do marco na mesma área, e o que a verificação seguinte disse delas."""
    if not fatia.texto(m.CAMPO_CORRIGE):
        return ()
    areas = _areas(estado, fatia)
    anteriores = [f for f in estado.fatias if f.texto(m.CAMPO_CORRIGE) and f.texto(m.CAMPO_CORRIGE) != fatia.texto(m.CAMPO_CORRIGE)
                  and f.status == m.STATUS_CONCLUIDO and f.texto(m.CAMPO_MARCO) == fatia.texto(m.CAMPO_MARCO) and areas & _areas(estado, f)]
    linhas = [_diff_da_tentativa(area, f) for f in anteriores[-MAXIMO_DE_TENTATIVAS_ANTERIORES:]]
    return (*linhas, *_verificacao_que_reprovou(estado, fatia)) if linhas else ()


def _areas(estado: EstadoDoGoal, fatia: FatiaRegistrada) -> set[str]:
    """As áreas (arquivo, ou critério) dos achados que a fatia corrige."""
    return {area_do_achado(achado) for id_achado in m.achados_da_correcao(fatia.propriedades) if (achado := estado.achado(id_achado))}


def _diff_da_tentativa(area: GitDoGoal, fatia: FatiaRegistrada) -> str:
    """O diff do commit da correção anterior, cortado."""
    diff = area.tentar("show", "--format=", "--patch", fatia.texto(m.CAMPO_COMMIT)).saida[:LIMITE_DO_DIFF]
    return f"A correcao {fatia.codigo} ({fatia.titulo}) mudou isto, e a falha voltou:\n```diff\n{diff}\n```"


def _verificacao_que_reprovou(estado: EstadoDoGoal, fatia: FatiaRegistrada) -> Sequence[str]:
    """O resumo e os pareceres sem `atende` da verificação que pediu esta correção."""
    verificacao = next((v for v in estado.verificacoes if v.id == fatia.texto(m.CAMPO_CORRIGE)), None)
    if verificacao is None:
        return ()
    pareceres = verificacao.propriedades.get(m.CAMPO_PARECERES)
    reprovados = [f"  - {p.get('id')} {p.get('veredito')}: {p.get('prova', '')}" for p in pareceres or []
                  if isinstance(p, Mapping) and p.get("veredito") != "atende"]
    return [f"A verificacao {verificacao.id}, depois dela, disse: {verificacao.propriedades.get('resumo', '')}", *reprovados]
