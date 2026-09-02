"""Renderização do índice de navegação da biblioteca de documentação."""

from graphow.documentacao.modelo import CatalogoRepositorio, SetorDocumentado
from graphow.documentacao.renderizador_setor import AVISO_DE_GERACAO

PILARES: tuple[tuple[str, str], ...] = (
    (
        "O Log é a Verdade",
        "Event store append-only. O grafo é uma dobra determinística dos eventos, "
        "com `UNIQUE(ramo_id, seq)` garantindo ordem total e commit em transação única.",
    ),
    (
        "Caminho Único de Escrita",
        "Humanos e agentes submetem o mesmo JSON Patch (RFC 6902) aos quatro portões. "
        "O papel do autor vem da conexão, nunca do payload.",
    ),
    (
        "Divulgação Progressiva",
        "As políticas caminham no grafo a partir do alvo e a renderização descarta "
        "seções por prioridade, preservando restrições e a afordância de expansão.",
    ),
    (
        "Linhagem e Fork Barato",
        "Rastreio reverso do Artifact até o Goal. Ramificação é o ponteiro "
        "`(ramo_base, seq_corte)`, sem cópia de prefixo.",
    ),
)

ROTEAMENTO_POR_INTENCAO: tuple[tuple[str, str], ...] = (
    ("Entender o vocabulário do domínio", "Setor 01 — `graphow.core`"),
    ("Mudar regra de permissão ou invariante", "Setor 02 — `graphow.kernel`"),
    ("Mexer em persistência, migração ou reparo", "Setor 03 — `graphow.storage`"),
    ("Investigar divergência entre grafo e log", "Setores 03 e 04"),
    ("Ajustar o que o agente recebe de contexto", "Setor 06 — `graphow.context`"),
    ("Alterar ferramentas expostas ao agente", "Setor 10 — `graphow.mcp`"),
    ("Trabalhar no canvas ou no tempo real", "Setor 12 — `graphow.web`"),
    ("Regenerar esta documentação", "Setor 13 — `graphow docs-gerar`"),
)

REGRAS_DE_ENGENHARIA: tuple[tuple[str, str], ...] = (
    ("Linhas por arquivo", "no máximo 400"),
    ("Linhas por função", "no máximo 30"),
    ("Níveis de aninhamento", "no máximo 2, com cláusulas de guarda"),
    ("Parâmetros posicionais", "no máximo 3, agrupados em DTOs acima disso"),
    ("Tipagem", "100% das assinaturas anotadas"),
    ("Exceções", "captura sempre específica, nunca `Exception` nu"),
    ("Imutabilidade", "`@dataclass(frozen=True)` como padrão"),
)


class RenderizadorIndice:
    """Converte o catálogo no mapa de navegação da biblioteca."""

    def renderizar(self, catalogo: CatalogoRepositorio) -> str:
        """Monta o índice completo em Markdown."""
        linhas = self._montar_cabecalho(catalogo)
        linhas.extend(self._montar_pilares())
        linhas.extend(self._montar_roteamento())
        linhas.extend(self._montar_regras())
        linhas.extend(self._montar_inventario(catalogo))
        return "\n".join(linhas) + "\n"

    def _montar_cabecalho(self, catalogo: CatalogoRepositorio) -> list[str]:
        """Título, aviso de geração e números do repositório."""
        return [
            "# Índice da Biblioteca do Graphow",
            "",
            AVISO_DE_GERACAO,
            "",
            "Este índice é o mapa: pilares, roteamento por intenção, regras de engenharia",
            "e o inventário das alas. O catálogo detalhado de cada ala vive em",
            "[`docs/setores/`](setores/), um dossiê por pacote.",
            "",
            f"**{len(catalogo.setores)} alas · {catalogo.total_modulos} módulos · "
            f"{catalogo.total_linhas} linhas · {catalogo.total_classes} classes**",
            "",
            "---",
            "",
        ]

    def _montar_pilares(self) -> list[str]:
        """Os quatro pilares, cada um com o mecanismo que o sustenta."""
        linhas = ["## Pilares", ""]
        linhas.extend(f"{indice}. **{nome}** — {descricao}" for indice, (nome, descricao) in enumerate(PILARES, 1))
        linhas.extend(["", "---", ""])
        return linhas

    def _montar_roteamento(self) -> list[str]:
        """Tabela que leva da intenção ao setor certo."""
        linhas = [
            "## Por onde começar",
            "",
            "| Se você quer… | Vá para |",
            "| :--- | :--- |",
        ]
        linhas.extend(f"| {intencao} | {destino} |" for intencao, destino in ROTEAMENTO_POR_INTENCAO)
        linhas.extend(["", "---", ""])
        return linhas

    def _montar_regras(self) -> list[str]:
        """Regras de engenharia verificadas automaticamente em `tests/qualidade/`."""
        linhas = [
            "## Regras de engenharia",
            "",
            "Verificadas por AST em `tests/qualidade/`. Uma violação quebra a suíte.",
            "",
            "| Regra | Limite |",
            "| :--- | :--- |",
        ]
        linhas.extend(f"| {regra} | {limite} |" for regra, limite in REGRAS_DE_ENGENHARIA)
        linhas.extend(["", "---", ""])
        return linhas

    def _montar_inventario(self, catalogo: CatalogoRepositorio) -> list[str]:
        """Inventário sinóptico das alas, com link para cada dossiê."""
        linhas = [
            "## As alas da biblioteca",
            "",
            "| # | Ala | Pacote | Módulos | Linhas | Classes |",
            "| ---: | :--- | :--- | ---: | ---: | ---: |",
        ]
        linhas.extend(self._montar_linha_de_setor(setor) for setor in catalogo.setores)
        linhas.append("")
        linhas.extend(self._montar_missoes(catalogo))
        return linhas

    def _montar_linha_de_setor(self, setor: SetorDocumentado) -> str:
        """Uma linha da tabela de inventário."""
        return (
            f"| {setor.numero:02d} | [{setor.titulo}](setores/{setor.nome_arquivo}) "
            f"| `graphow.{setor.identificador}` | {len(setor.modulos)} "
            f"| {setor.total_linhas} | {setor.total_classes} |"
        )

    def _montar_missoes(self, catalogo: CatalogoRepositorio) -> list[str]:
        """Missão de cada ala, para triagem sem abrir os dossiês."""
        linhas = ["### Missão de cada ala", ""]
        for setor in catalogo.setores:
            linhas.append(f"**{setor.numero:02d}. {setor.titulo}** — {setor.missao}")
            linhas.append("")
        return linhas
