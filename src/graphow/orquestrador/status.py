"""O `--status` do orquestrador: onde o Goal está, o que prova que ele está pronto, o que cada fatia fez e quanto custou.

Lê só o livro-razão e a tabela de telemetria: não roda sessão nem git. Mostra
o estado de cada critério, os testes de aceite, os marcos e as verificações
deles, os Achados bloqueantes que seguem abertos e as pendências.
"""

from collections.abc import Sequence

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.esquemas import PAPEIS
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada
from graphow.storage.telemetria_de_sessoes import SessaoRegistrada, TotaisDeTelemetria, totalizar

SEGUNDOS_POR_MINUTO: float = 60.0


def formatar_status(estado: EstadoDoGoal, registros: Sequence[SessaoRegistrada]) -> list[str]:
    """As linhas do status do Goal."""
    configuracao = estado.configuracao
    linhas = [f"Goal {estado.id_goal}: {estado.rotulo} [{'fechado' if estado.fechado else 'aberto'}]"]
    if configuracao is not None:
        linhas.append(f"Modo {configuracao.modo} | base {configuracao.base} | branch {configuracao.ramo}")
        linhas.append(f"Area: {configuracao.area}")
    linhas.append(_linha_do_plano(estado))
    linhas.extend(_linhas_do_aceite(estado))
    linhas.extend(["Fatias:", *(_linha_da_fatia(fatia) for fatia in estado.fatias)] if estado.fatias else [])
    linhas.extend(
        ["Verificacoes:", *(f"  {v.id} ({v.marco or '-'}): {v.veredito} em {v.commit[:12]} ({len(v.bloqueantes())} bloqueante(s))"
                            for v in estado.verificacoes)] if estado.verificacoes else []
    )
    abertos = [a for v in estado.verificacoes for a in v.bloqueantes() if a.estado not in ("resolvido", "descartado")]
    linhas.extend(["Achados bloqueantes sem resolver:", *(f"  - {a.id}: {a.texto('titulo')} ({a.estado})" for a in abertos)]
                  if abertos else [])
    pendencias = estado.pendencias
    linhas.append(f"Pendencias: {len(pendencias)}")
    linhas.extend(f"  - [{p.get('gravidade', '')}] {p.get('titulo', '')} {p.get('local', '')}".rstrip() for p in pendencias)
    linhas.extend(_linhas_da_telemetria(registros))
    if estado.propriedades.get(m.CAMPO_INTEGRADO_EM):
        linhas.append(f"Integrado em {estado.propriedades[m.CAMPO_INTEGRADO_EM]}")
    return linhas


def _linhas_do_aceite(estado: EstadoDoGoal) -> list[str]:
    """Os testes de aceite, os critérios com o estado de cada um e os marcos."""
    if estado.plano is None:
        return []
    aceite = estado.aceite
    linhas = [f"Aceite: commit {str(aceite.get('commit', ''))[:12]}, `{aceite.get('comando', '')}`" if aceite else "Aceite: ainda nao escrito"]
    estados = _estados_dos_criterios(estado)
    linhas.append("Criterios: " + ", ".join(f"{c['id']} {estados.get(str(c['id']), 'pendente')}" for c in estado.plano.get("criterios", [])))
    linhas.extend(f"Marco {marco.id}{' (final)' if marco.final else ''}: fatias {', '.join(marco.fatias)}; "
                  + ("verificado limpo" if any(v.limpa for v in estado.verificacoes_do_marco(marco)) else
                     "ciclos esgotados, bloqueantes seguem para a final" if estado.marco_esgotado(marco) else "sem verificacao limpa")
                  for marco in estado.marcos())
    return linhas


def _estados_dos_criterios(estado: EstadoDoGoal) -> dict[str, str]:
    """O estado de cada critério: o veredito da verificação mais recente que o julgou."""
    estados: dict[str, str] = {}
    for verificacao in estado.verificacoes:
        pareceres = verificacao.propriedades.get(m.CAMPO_PARECERES)
        estados.update({str(p.get("id")): str(p.get("veredito")) for p in pareceres if isinstance(p, dict)} if isinstance(pareceres, list) else {})
    return estados


def _linha_do_plano(estado: EstadoDoGoal) -> str:
    """O plano: se existe, se foi aprovado, quantas fatias e a suíte."""
    plano = estado.plano
    if plano is None:
        return "Plano: ainda nao planejado"
    modo = estado.configuracao.modo if estado.configuracao else ""
    aprovacao = "aprovado" if estado.plano_aprovado else ("vale direto (autonomo)" if modo == m.MODO_AUTONOMO else "aguardando aprovacao")
    return f"Plano: {aprovacao}, {len(plano.get('fatias', []))} fatia(s), suite `{plano.get('comando_suite', '')}`"


def _linha_da_fatia(fatia: FatiaRegistrada) -> str:
    """Uma fatia: código, situação, commit e título."""
    duvida = fatia.duvida_aberta
    situacao = f"pausada ({duvida.id})" if duvida else fatia.status
    commit = fatia.texto(m.CAMPO_COMMIT)[:12] or "-"
    risco = " [risco]" if fatia.propriedades.get(m.CAMPO_RISCO) is True else ""
    return f"  {fatia.codigo:<8} {situacao:<28} {commit:<12} {fatia.titulo}{risco} (tentativas: {fatia.tentativas})"


def _linhas_da_telemetria(registros: Sequence[SessaoRegistrada]) -> list[str]:
    """Os totais do Goal e de cada papel."""
    linhas = ["Sessoes: " + _descrever(totalizar(registros))]
    for papel in PAPEIS:
        do_papel = [registro for registro in registros if registro.papel == papel]
        if do_papel:
            linhas.append(f"  {papel}: " + _descrever(totalizar(do_papel)))
    return linhas


def _descrever(totais: TotaisDeTelemetria) -> str:
    """Invocações, sessões, custo, tokens e minutos."""
    desconhecidos = f" (+{totais.custos_desconhecidos} sem custo)" if totais.custos_desconhecidos else ""
    erros = f", {totais.com_erro} com erro" if totais.com_erro else ""
    erros += f", {totais.em_andamento} em andamento" if totais.em_andamento else ""
    return (
        f"{totais.invocacoes} invocacao(oes) em {totais.sessoes} sessao(oes){erros} | US$ {totais.custo_usd:.2f}{desconhecidos} | "
        f"{totais.tokens} tokens | {totais.duracao_s / SEGUNDOS_POR_MINUTO:.1f} min"
    )
