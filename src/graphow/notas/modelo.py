"""Modelos imutáveis do acervo de notas: uma nota por aprendizado promovido.

A nota é a forma de leitura de um Aprendizado, nunca a fonte dele. Tudo que ela
diz vem do grafo: a afirmação é o rótulo, a origem são as arestas `deriva_de`,
o alcance são as arestas `vale_para` e a marca global, e os avisos de
substituição e contradição são as arestas que os registram.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OrigemDaNota:
    """Um nó de onde o aprendizado saiu, ou que o contradiz, na forma que a nota cita."""

    id: str
    tipo: str
    rotulo: str
    seq: int

    def descrever(self) -> str:
        """Citação em uma linha: tipo, rótulo, identificador e posição no log."""
        return f"[{self.tipo}] {self.rotulo} (`{self.id}`, log #{self.seq})"


@dataclass(frozen=True)
class NotaDeAprendizado:
    """O que uma nota do acervo diz sobre um aprendizado, tirado do grafo."""

    id: str
    afirmacao: str
    como_aplicar: str
    autor: str
    papel: str
    seq_criacao: int
    alcances: tuple[str, ...] = field(default_factory=tuple)
    origens: tuple[OrigemDaNota, ...] = field(default_factory=tuple)
    substituto: str | None = None
    contradicoes: tuple[OrigemDaNota, ...] = field(default_factory=tuple)
    valido_ate: str = ""

    @property
    def nome_arquivo(self) -> str:
        """Nome do arquivo da nota dentro do acervo."""
        return f"{self.id}.md"

    @property
    def esta_vigente(self) -> bool:
        """Uma nota sem substituto segue valendo; a substituída fica, marcada."""
        return self.substituto is None
