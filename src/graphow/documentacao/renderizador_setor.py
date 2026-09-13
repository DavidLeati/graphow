"""Renderização do dossiê Markdown de uma ala temática."""

from graphow.documentacao.modelo import (
    ClasseDocumentada,
    FuncaoDocumentada,
    ModuloDocumentado,
    SetorDocumentado,
    ordenar_por_nome,
)

AVISO_DE_GERACAO: str = (
    "> Documento gerado a partir do código por `graphow docs-gerar`.\n"
    "> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão\n"
    "> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`."
)


class RenderizadorSetor:
    """Converte um setor catalogado no seu dossiê Markdown."""

    def renderizar(self, setor: SetorDocumentado) -> str:
        """Monta o dossiê completo do setor."""
        linhas = self._montar_cabecalho(setor)
        linhas.extend(self._montar_inventario(setor))
        for modulo in setor.modulos_com_conteudo:
            linhas.extend(self._montar_modulo(modulo))
        return "\n".join(linhas) + "\n"

    def _montar_cabecalho(self, setor: SetorDocumentado) -> list[str]:
        """Título, aviso de geração e missão da ala."""
        return [
            f"# Setor {setor.numero:02d} — {setor.titulo}",
            "",
            AVISO_DE_GERACAO,
            "",
            f"**Pacote:** `graphow.{setor.identificador}`",
            "",
            setor.missao,
            "",
        ]

    def _montar_inventario(self, setor: SetorDocumentado) -> list[str]:
        """Tabela sinóptica dos módulos do setor."""
        linhas = [
            "## Inventário",
            "",
            f"{len(setor.modulos)} módulos · {setor.total_linhas} linhas · {setor.total_classes} classes",
            "",
            "| Módulo | Linhas | Papel |",
            "| :--- | ---: | :--- |",
        ]
        linhas.extend(
            f"| [`{modulo.caminho_relativo}`](#{self._ancora(modulo)}) | {modulo.linhas} | {modulo.resumo} |"
            for modulo in setor.modulos_com_conteudo
        )
        linhas.append("")
        return linhas

    def _ancora(self, modulo: ModuloDocumentado) -> str:
        """Âncora estável do módulo dentro do documento."""
        return modulo.caminho_relativo.replace("/", "").replace(".py", "").replace("_", "")

    def _montar_modulo(self, modulo: ModuloDocumentado) -> list[str]:
        """Bloco completo de um módulo: constantes, classes e funções."""
        linhas = [
            f"## `{modulo.caminho_relativo}`",
            "",
            modulo.resumo,
            "",
        ]
        linhas.extend(self._montar_constantes(modulo))
        for classe in ordenar_por_nome(modulo.classes):
            linhas.extend(self._montar_classe(classe))
        linhas.extend(self._montar_funcoes_de_modulo(modulo))
        return linhas

    def _montar_constantes(self, modulo: ModuloDocumentado) -> list[str]:
        """Tabela das constantes públicas do módulo."""
        if not modulo.constantes:
            return []
        linhas = ["| Constante | Tipo | Valor |", "| :--- | :--- | :--- |"]
        linhas.extend(
            f"| `{constante.nome}` | `{constante.anotacao}` | `{constante.valor}` |"
            for constante in modulo.constantes
        )
        linhas.append("")
        return linhas

    def _montar_classe(self, classe: ClasseDocumentada) -> list[str]:
        """Bloco de uma classe: natureza, bases, campos e métodos públicos."""
        heranca = f" ({', '.join(classe.bases)})" if classe.bases else ""
        linhas = [
            f"### `{classe.nome}`{heranca}",
            "",
            f"*{classe.natureza}* — {classe.resumo}",
            "",
        ]
        linhas.extend(self._montar_campos(classe))
        linhas.extend(self._montar_metodos(classe))
        return linhas

    def _montar_campos(self, classe: ClasseDocumentada) -> list[str]:
        """Lista os atributos declarados na classe."""
        if not classe.campos:
            return []
        campos = ", ".join(f"`{campo.formatar()}`" for campo in classe.campos)
        return [f"**Campos:** {campos}", ""]

    def _montar_metodos(self, classe: ClasseDocumentada) -> list[str]:
        """Lista as assinaturas públicas da classe."""
        if not classe.metodos_publicos:
            return []
        linhas = [f"- {self._formatar_metodo(metodo)}" for metodo in classe.metodos_publicos]
        return linhas + [""]

    def _formatar_metodo(self, metodo: FuncaoDocumentada) -> str:
        """Assinatura com marcadores e resumo em uma linha."""
        marcadores = "".join(f" `[{rotulo}]`" for rotulo in metodo.marcadores)
        return f"`{metodo.formatar_assinatura()}`{marcadores} — {metodo.resumo}"

    def _montar_funcoes_de_modulo(self, modulo: ModuloDocumentado) -> list[str]:
        """Lista as funções públicas declaradas fora de classes."""
        if not modulo.funcoes_publicas:
            return []
        linhas = ["### Funções do módulo", ""]
        linhas.extend(f"- {self._formatar_metodo(funcao)}" for funcao in modulo.funcoes_publicas)
        linhas.append("")
        return linhas
