"""O `--status` do orquestrador: onde o Goal está, o que cada fatia fez e quanto as sessões custaram.

Lê só o livro-razão e a tabela de telemetria: não roda sessão nem git.
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
    linhas.extend(["Fatias:", *(_linha_da_fatia(fatia) for fatia in estado.fatias)] if estado.fatias else [])
    linhas.extend(
        ["Verificacoes:", *(f"  {v.id}: {v.veredito} em {v.commit[:12]} ({len(v.lista('bloqueantes'))} bloqueante(s))"
                            for v in estado.verificacoes)] if estado.verificacoes else []
    )
    pendencias = estado.pendencias
    linhas.append(f"Pendencias: {len(pendencias)}")
    linhas.extend(f"  - [{p.get('gravidade', '')}] {p.get('titulo', '')} {p.get('local', '')}".rstrip() for p in pendencias)
    linhas.extend(_linhas_da_telemetria(registros))
    if estado.propriedades.get(m.CAMPO_INTEGRADO_EM):
        linhas.append(f"Integrado em {estado.propriedades[m.CAMPO_INTEGRADO_EM]}")
    return linhas


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
    return f"  {fatia.codigo:<6} {situacao:<28} {commit:<12} {fatia.titulo} (tentativas: {fatia.tentativas})"


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
