"""O relatório de `graphow escopo-medir`: as tabelas A a E da regressão do escopo governado, em Markdown.

Cada tabela responde uma pergunta da validação da seção 7 da proposta. O Goal sai
pelo identificador anonimizado do corpus; quem quiser um nome legível passa
`rotulos` (identificador para texto), o que o comando não faz: o mapa entre o log
real e o anonimizado não fica no repositório.
"""

from collections.abc import Callable, Mapping, Sequence
from statistics import median

from graphow.avaliacao.cenario_expansao_lateral import ResultadoDaExpansaoLateral
from graphow.avaliacao.escopo_desvio import DesvioDoGoal
from graphow.avaliacao.escopo_historico import MedicaoDeEscopo, MedicaoDoGoal

Nomeador = Callable[[MedicaoDoGoal], str]

# O que a seção 7 mediu, por (Tasks do plano, Tasks no fim): rótulo do caso e eventos de desvio.
SECAO_7: Mapping[tuple[int, int], tuple[str, int]] = {
    (12, 14): ("conduzido de perto pelo humano", 0),
    (5, 35): ("decomposto pelo condutor em ondas", 6),
    (3, 100): ("modo continuo, por ordem do humano", 23),
}
NOTAS_DE_METODO: tuple[str, ...] = (
    "- Corpus: logs reais anonimizados, anteriores a ontologia 1.5.0. Limiares K = 3 por raiz e M = 5 por Goal.",
    "- Plano: as Tasks que existiam quando a primeira Task do Goal foi para `em_andamento` (aprovacao humana sintetica).",
    "- Lote: Tasks do mesmo autor sem pausa maior que 120 s entre uma e outra; o log carimba cada chamada, entao o mesmo segundo nao serve.",
    "- Alerta: o placar de producao no fim do lote; depois de cada evento uma resposta humana sem raiz zera K e M.",
    "- `motivada_por` nao existe no log: vem de `orienta` (Decision para Task). A Task tem ate 11 Decisions e o log nao diz qual a motivou, "
    "por isso a raiz varia por hipotese: mais recente, mais antiga, mais abrangente (a que orienta mais Tasks) ou o menor id entre todas.",
    "- A secao 7 contou so o K e separou correcao, rebase e PR pelo nome; o corpus nao tem nome, e aqui a correcao e a estrutural.",
    "- Os ids do corpus sao hashes: a ordem antiga da fila (por id) e arbitraria em relacao ao plano, a de um sorteio.",
)
GATILHOS: Mapping[str, str] = {"raiz": "K", "goal": "M", "inanicao": "I"}


def formatar_relatorio(medicao: MedicaoDeEscopo, rotulos: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """O relatório inteiro: método, tabelas A a D por Goal e o cenário E."""
    nome = _nomeador(rotulos or {})
    secoes = (
        (f"# Escopo governado: regressao no historico ({medicao.eventos_do_corpus} eventos, {len(medicao.goals)} Goals)",),
        ("", "## Metodo", *NOTAS_DE_METODO),
        _tabela_a(medicao, nome),
        _tabela_b(medicao, nome),
        _tabela_c(medicao, nome),
        _tabela_d(medicao, nome),
        _secao_e(medicao.expansao),
    )
    return tuple(linha for secao in secoes for linha in secao)


def _nomeador(rotulos: Mapping[str, str]) -> Nomeador:
    """A função que escreve o Goal: o identificador e, se houver, o rótulo legível."""

    def nome(goal: MedicaoDoGoal) -> str:
        """O Goal como a primeira coluna o mostra."""
        rotulo = rotulos.get(goal.id_goal)
        return f"{goal.id_goal} ({rotulo})" if rotulo else goal.id_goal

    return nome


def _tabela(titulo: str, cabecalho: Sequence[str], linhas: Sequence[Sequence[str]]) -> tuple[str, ...]:
    """Uma tabela Markdown com título."""
    separador = "|" + "|".join("---" for _ in cabecalho) + "|"
    corpo = tuple("| " + " | ".join(linha) + " |" for linha in linhas)
    return ("", titulo, "", "| " + " | ".join(cabecalho) + " |", separador, *corpo)


def _tabela_a(medicao: MedicaoDeEscopo, nome: Nomeador) -> tuple[str, ...]:
    """A: eventos de desvio, contra a seção 7 e sob cada hipótese de raiz."""
    cabecalho = (
        "Goal", "Plano -> total", "Lotes", "Secao 7", "K so: recente", "K so: antiga", "K so: abrangente",
        "K so: todas (menor id)", "K+M+inanicao", "idem sem resposta",
    )
    linhas = [
        (
            nome(g), f"{g.plano} -> {g.total}", str(g.lotes), _secao_7(g), *(str(g.so_k[h].total) for h in _HIPOTESES),
            _final(g.desvio), str(g.desvio_sem_resposta.total),
        )
        for g in medicao.goals
    ]
    return _tabela("## A. Eventos de desvio", cabecalho, linhas)


_HIPOTESES: tuple[str, ...] = ("mais_recente", "mais_antiga", "mais_abrangente", "todas")


def _secao_7(goal: MedicaoDoGoal) -> str:
    """O número da seção 7 para o Goal de mesmo tamanho de plano e total, ou o traço."""
    caso = SECAO_7.get((goal.plano, goal.total))
    return str(caso[1]) if caso else "-"


def _final(desvio: DesvioDoGoal) -> str:
    """Os eventos do desenho final e quantos foram de cada gatilho: K, M e inanição."""
    por_gatilho = desvio.por_gatilho()
    partes = " ".join(f"{GATILHOS[tipo]}{por_gatilho.get(tipo, 0)}" for tipo in GATILHOS)
    return f"{desvio.total} ({partes})"


def _tabela_b(medicao: MedicaoDeEscopo, nome: Nomeador) -> tuple[str, ...]:
    """B: o alerta chega antes do trabalho que ele cobre?"""
    cabecalho = (
        "Goal", "Eventos", "Com Task coberta ainda nao iniciada", "Cobertas", "Nao iniciadas no alerta",
        "Horas ate a 1a execucao (min / mediana / max)",
    )
    linhas = [
        (
            nome(g), str(g.desvio.total), str(g.desvio.antes_do_trabalho), str(g.desvio.cobertas),
            str(g.desvio.nao_comecadas), _horas(g.desvio.horas_ate_a_primeira_execucao),
        )
        for g in medicao.goals
    ]
    return _tabela("## B. Antecedencia do alerta", cabecalho, linhas)


def _horas(horas: Sequence[float]) -> str:
    """Mínimo, mediana e máximo das horas, ou o traço sem nenhuma."""
    if not horas:
        return "-"
    return f"{min(horas):.2f} / {median(horas):.2f} / {max(horas):.2f}"


def _tabela_c(medicao: MedicaoDeEscopo, nome: Nomeador) -> tuple[str, ...]:
    """C: a fila serviria outra coisa no histórico?"""
    cabecalho = (
        "Goal", "Saidas de pendente", "Pendentes liberadas (media)", "Emergente escolhida",
        "...com plano pendente", "...pedida pelo plano", "...com plano liberado", "Posicao do plano: antiga -> nova",
        "...so nas emergentes",
    )
    linhas = [
        (
            nome(g), str(len(g.fila.momentos)), f"{g.fila.pendentes_por_momento:.2f}", str(g.fila.emergentes_escolhidas),
            str(g.fila.com_plano_pendente), str(g.fila.pedidas_pelo_plano), str(g.fila.com_plano_liberado),
            _posicoes(g.fila.posicao_media()), _posicoes(g.fila.posicao_media(so_emergentes=True)),
        )
        for g in medicao.goals
    ]
    return _tabela("## C. Fila (D4)", cabecalho, linhas)


def _posicoes(medias: tuple[float, float] | None) -> str:
    """A posição média antiga e nova do plano, ou o traço quando nunca havia plano liberado."""
    return "-" if medias is None else f"{medias[0]:.2f} -> {medias[1]:.2f}"


def _tabela_d(medicao: MedicaoDeEscopo, nome: Nomeador) -> tuple[str, ...]:
    """D: das Tasks depois do plano, quantas o kernel 1.5.0 aceitaria pela ligação estrutural."""
    cabecalho = ("Goal", "Depois do plano", "Classes", "Com ligacao valida", "Recusadas (ligacao_de_escopo_ausente)", "% recusadas")
    linhas = [
        (
            nome(g), str(g.cobertura.depois_do_plano), _classes(g.cobertura.por_classe), str(g.cobertura.aceitas),
            str(g.cobertura.recusadas), f"{100 * g.cobertura.recusadas / max(g.cobertura.depois_do_plano, 1):.0f}%",
        )
        for g in medicao.goals
    ]
    return _tabela("## D. Cobertura de origem", cabecalho, linhas)


def _classes(por_classe: Mapping[str, int]) -> str:
    """As classes e a contagem de cada uma."""
    return ", ".join(f"{classe} {total}" for classe, total in por_classe.items())


def _secao_e(r: ResultadoDaExpansaoLateral) -> tuple[str, ...]:
    """E: o cenário do caso 14 para 121, pelos portões reais."""
    teto = r.teto
    linhas = (
        ("Plano humano / subdivisoes / emergentes", f"{r.tasks_do_plano} / {r.subdivisoes} / {r.emergentes}"),
        ("Alvos fora da fronteira da raiz", str(len(r.alvos_da_raiz))),
        ("Contador de K por emergente criada", ", ".join(str(k) for k in r.contador_k_por_emergente)),
        ("K dispara na emergente", str(r.k_dispara_na_emergente)),
        ("Contador de M por emergente criada", ", ".join(str(m) for m in r.contador_m_por_emergente)),
        ("M dispara na emergente", str(r.m_dispara_na_emergente)),
        ("Raizes sem veredito de escopo", ", ".join(r.raizes_sem_veredito) or "-"),
        ("Tasks iniciadas quando o K dispara", str(r.tasks_iniciadas_no_alerta)),
        ("Posicao do plano na fila: antiga -> nova", "{} -> {}".format(*r.posicao_do_plano())),
        ("Emergentes servidas antes do plano: antiga -> nova", "{} -> {}".format(*r.emergentes_a_frente_do_plano())),
        ("Posicao da 1a emergente: antiga -> nova", "{} -> {}".format(*r.posicao_da_primeira_emergente())),
        ("Task do planejador sem ligacao", str(r.sem_ligacao_recusada)),
        (f"Teto {teto.teto}: aceitas antes da recusa", str(teto.aceitas_antes_da_recusa)),
        ("Teto: recusada e modo de falha", f"{teto.recusada}, {teto.modo_de_falha}"),
        ("Teto: aceita depois do responder_desvio do humano", str(teto.aceita_depois_da_resposta)),
        ("Teto: as 9 num lote so sao recusadas inteiras", str(teto.lote_inteiro_recusado)),
    )
    return _tabela("## E. Cenario 14 -> 121 (sintetico, pelos portoes reais)", ("Medida", "Resultado"), linhas)
