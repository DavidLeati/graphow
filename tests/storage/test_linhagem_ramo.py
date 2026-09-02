"""Testes unitários para a persistência e a resolução da linhagem entre ramos."""

from pathlib import Path

import pytest

from graphow.core.exceptions import GraphowError
from graphow.storage.linhagem_ramo import (
    DefinicaoRamo,
    RepositorioRamos,
    RepositorioRamosEmMemoria,
    RepositorioRamosSQLite,
    ResolvedorLinhagem,
)
from graphow.storage.sqlite_store import SQLiteEventStore


def test_registra_e_recupera_definicao_nominal() -> None:
    """Uma definição gravada volta idêntica na consulta."""
    repositorio = RepositorioRamosEmMemoria()
    repositorio.registrar(DefinicaoRamo("filho", "main", 42, "evento-x"))

    definicao = repositorio.obter_definicao("filho")
    assert definicao is not None
    assert definicao.ramo_base == "main"
    assert definicao.seq_corte == 42
    assert definicao.evento_corte_id == "evento-x"


def test_ramo_raiz_nao_possui_definicao_nominal() -> None:
    """Um ramo sem linhagem registrada é raiz e não herda nada."""
    repositorio = RepositorioRamosEmMemoria()
    assert repositorio.obter_definicao("main") is None
    assert ResolvedorLinhagem(repositorio).obter_seq_corte("main") == 0


def test_redefinicao_de_ramo_e_recusada_edge_case() -> None:
    """Caso de borda: um ramo não pode ter a linhagem sobrescrita."""
    repositorio = RepositorioRamosEmMemoria()
    repositorio.registrar(DefinicaoRamo("filho", "main", 10))
    with pytest.raises(GraphowError):
        repositorio.registrar(DefinicaoRamo("filho", "outro", 99))


def test_resolve_cadeia_de_multiplos_niveis_edge_case() -> None:
    """Caso de borda: a cadeia percorre avô, pai e ramo consultado."""
    repositorio = RepositorioRamosEmMemoria()
    repositorio.registrar(DefinicaoRamo("filho", "main", 10))
    repositorio.registrar(DefinicaoRamo("neto", "filho", 20))

    cadeia = ResolvedorLinhagem(repositorio).resolver_cadeia("neto")
    assert [definicao.ramo_id for definicao in cadeia] == ["neto", "filho"]
    assert [definicao.ramo_base for definicao in cadeia] == ["filho", "main"]


def test_ciclo_na_linhagem_nao_causa_laco_infinito_edge_case() -> None:
    """Caso de borda: uma linhagem circular termina, em vez de travar a leitura."""
    repositorio = RepositorioRamosEmMemoria()
    repositorio.registrar(DefinicaoRamo("a", "b", 5))
    repositorio.registrar(DefinicaoRamo("b", "a", 5))

    cadeia = ResolvedorLinhagem(repositorio).resolver_cadeia("a")
    assert len(cadeia) <= 2


def test_listagem_de_ramos_derivados_e_ordenada() -> None:
    """A listagem devolve os ramos derivados em ordem estável."""
    repositorio = RepositorioRamosEmMemoria()
    repositorio.registrar(DefinicaoRamo("zeta", "main", 1))
    repositorio.registrar(DefinicaoRamo("alfa", "main", 1))
    assert repositorio.listar_ramos_derivados() == ("alfa", "zeta")


def test_linhagem_sqlite_persiste_entre_conexoes(tmp_path: Path) -> None:
    """A definição gravada por uma conexão é vista pela outra no mesmo arquivo."""
    caminho = tmp_path / "graphow.db"
    with SQLiteEventStore(str(caminho)) as store_a, SQLiteEventStore(str(caminho)) as store_b:
        repositorio_a: RepositorioRamos = RepositorioRamosSQLite(store_a.conexao)
        repositorio_b: RepositorioRamos = RepositorioRamosSQLite(store_b.conexao)

        repositorio_a.registrar(DefinicaoRamo("experimento", "main", 7, "evento-7"))
        definicao = repositorio_b.obter_definicao("experimento")

        assert definicao is not None
        assert definicao.seq_corte == 7
        assert repositorio_b.listar_ramos_derivados() == ("experimento",)


def test_linhagem_sqlite_recusa_redefinicao_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a chave primária impede sobrescrever a linhagem de um ramo."""
    caminho = tmp_path / "graphow.db"
    with SQLiteEventStore(str(caminho)) as store:
        repositorio = RepositorioRamosSQLite(store.conexao)
        repositorio.registrar(DefinicaoRamo("experimento", "main", 7))
        with pytest.raises(GraphowError):
            repositorio.registrar(DefinicaoRamo("experimento", "main", 9))
