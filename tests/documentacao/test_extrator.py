"""Testes unitários para a extração do catálogo a partir da árvore sintática."""

import pytest

from graphow.core.exceptions import GraphowError
from graphow.documentacao.extrator import ANOTACAO_AUSENTE, ExtratorCatalogo
from graphow.documentacao.leitura_fonte import ArquivoFonte
from graphow.documentacao.modelo import ModuloDocumentado

MODULO_EXEMPLO: str = '''"""Resumo do modulo exemplo.

Parágrafo adicional que não deve entrar no resumo.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

LIMITE_DE_ITENS: int = 42
_privado: int = 1


@dataclass(frozen=True)
class RegistroImutavel:
    """Um DTO congelado."""

    identificador: str
    quantidade: int = 0

    @property
    def rotulo(self) -> str:
        """Rotulo derivado."""
        return self.identificador


class Contrato(ABC):
    """Contrato abstrato."""

    @abstractmethod
    def executar(self, entrada: str) -> bool:
        """Executa a operacao."""
        raise NotImplementedError


class Servico(Contrato):
    """Implementacao concreta."""

    def executar(self, entrada: str) -> bool:
        """Executa de verdade."""
        return bool(entrada)

    def _interno(self) -> None:
        """Detalhe de implementacao."""
        return None


def funcao_publica(valor, outro: int) -> str:
    """Faz alguma coisa."""
    return str(valor) + str(outro)


def _funcao_privada() -> None:
    """Nao aparece no catalogo."""
    return None
'''


def _extrair() -> ModuloDocumentado:
    """Extrai o catálogo do módulo de exemplo."""
    arquivo = ArquivoFonte(caminho_relativo="exemplo/modulo.py", conteudo=MODULO_EXEMPLO)
    return ExtratorCatalogo().extrair_modulo(arquivo)


def test_resumo_do_modulo_e_a_primeira_frase_nominal() -> None:
    """O resumo vem da primeira linha da docstring, não do parágrafo inteiro."""
    modulo = _extrair()
    assert modulo.resumo == "Resumo do modulo exemplo."
    assert modulo.nome_modulo == "graphow.exemplo.modulo"


def test_classes_sao_classificadas_por_natureza_nominal() -> None:
    """DTO congelado, contrato abstrato e serviço recebem naturezas distintas."""
    classes = {classe.nome: classe for classe in _extrair().classes}
    assert classes["RegistroImutavel"].natureza == "DTO imutável"
    assert classes["Contrato"].natureza == "contrato"
    assert classes["Servico"].natureza == "serviço"


def test_campos_de_dataclass_sao_capturados_nominal() -> None:
    """Os atributos anotados viram campos do DTO no catálogo."""
    registro = {classe.nome: classe for classe in _extrair().classes}["RegistroImutavel"]
    assert [campo.formatar() for campo in registro.campos] == [
        "identificador: str",
        "quantidade: int",
    ]


def test_metodos_privados_ficam_fora_do_contrato_publico_edge_case() -> None:
    """Caso de borda: só o que não começa com underscore compõe a superfície."""
    servico = {classe.nome: classe for classe in _extrair().classes}["Servico"]
    nomes = [metodo.nome for metodo in servico.metodos_publicos]
    assert nomes == ["executar"]
    assert len(servico.metodos) == 2


def test_propriedade_e_metodo_abstrato_recebem_marcadores_edge_case() -> None:
    """Caso de borda: property e abstractmethod aparecem rotulados."""
    classes = {classe.nome: classe for classe in _extrair().classes}
    propriedade = classes["RegistroImutavel"].metodos_publicos[0]
    abstrato = classes["Contrato"].metodos_publicos[0]
    assert propriedade.marcadores == ("property",)
    assert abstrato.marcadores == ("abstract",)


def test_parametro_sem_anotacao_e_sinalizado_edge_case() -> None:
    """Caso de borda: a ausência de tipo aparece explicitamente no catálogo."""
    funcao = _extrair().funcoes_publicas[0]
    assert funcao.formatar_assinatura() == f"funcao_publica(valor: {ANOTACAO_AUSENTE}, outro: int) -> str"


def test_apenas_constantes_maiusculas_entram_no_catalogo_edge_case() -> None:
    """Caso de borda: atribuições privadas ou minúsculas não são constantes públicas."""
    constantes = _extrair().constantes
    assert [constante.nome for constante in constantes] == ["LIMITE_DE_ITENS"]
    assert constantes[0].valor == "42"


def test_modulo_com_sintaxe_invalida_falha_apontando_o_arquivo_edge_case() -> None:
    """Caso de borda: erro de sintaxe vira erro de domínio com o caminho no contexto."""
    arquivo = ArquivoFonte(caminho_relativo="quebrado.py", conteudo="def (:\n")
    with pytest.raises(GraphowError) as capturado:
        ExtratorCatalogo().extrair_modulo(arquivo)
    assert capturado.value.contexto["caminho"] == "quebrado.py"


def test_modulo_vazio_e_reconhecido_como_sem_conteudo_edge_case() -> None:
    """Caso de borda: um __init__ apenas com docstring não rende seção no dossiê."""
    arquivo = ArquivoFonte(caminho_relativo="pacote/__init__.py", conteudo='"""So a docstring."""\n')
    modulo = ExtratorCatalogo().extrair_modulo(arquivo)
    assert modulo.esta_vazio is True
    assert modulo.nome_modulo == "graphow.pacote"
