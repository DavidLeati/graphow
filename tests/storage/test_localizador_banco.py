"""Testes unitários para a resolução do caminho do banco de eventos."""

from pathlib import Path

from graphow.storage.localizador_banco import (
    AmbienteEmMemoria,
    LocalizadorBancoEventos,
    OrigemCaminhoBanco,
    PreparadorDiretorioBanco,
    caminho_esta_em_pasta_sincronizada,
)

HOME_FICTICIA: Path = Path("/lar/david")


def _localizador(variaveis: dict[str, str]) -> LocalizadorBancoEventos:
    """Constrói o localizador sobre um ambiente controlado."""
    return LocalizadorBancoEventos(AmbienteEmMemoria(variaveis, HOME_FICTICIA))


def test_caminho_relativo_vira_absoluto_edge_case() -> None:
    """Caso de borda: caminho relativo e resolvido antes da deteccao de nuvem."""
    localizacao = _localizador({}).resolver("graphow.db")
    assert localizacao.caminho.is_absolute()


def test_resolve_para_diretorio_de_dados_do_usuario_nominal() -> None:
    """Sem argumento nem variável, o banco vai para o diretório de dados da plataforma."""
    localizacao = _localizador({"LOCALAPPDATA": "C:/Users/david/AppData/Local"}).resolver()
    assert localizacao.origem == OrigemCaminhoBanco.DIRETORIO_DADOS_USUARIO
    assert localizacao.caminho.name == "graphow.db"
    assert "graphow" in localizacao.caminho.parts
    assert localizacao.esta_em_pasta_sincronizada is False


def test_argumento_explicito_tem_precedencia_sobre_ambiente_nominal() -> None:
    """O caminho passado na linha de comando vence a variável de ambiente."""
    localizador = _localizador({"GRAPHOW_DB": "/da/variavel.db", "LOCALAPPDATA": "C:/AppData"})
    localizacao = localizador.resolver("/do/argumento.db")
    assert localizacao.origem == OrigemCaminhoBanco.ARGUMENTO_EXPLICITO
    assert localizacao.caminho == Path("/do/argumento.db").resolve()


def test_variavel_de_ambiente_usada_quando_nao_ha_argumento_nominal() -> None:
    """Sem argumento explícito, a variável dedicada define o caminho."""
    localizacao = _localizador({"GRAPHOW_DB": "/da/variavel.db"}).resolver()
    assert localizacao.origem == OrigemCaminhoBanco.VARIAVEL_AMBIENTE
    assert localizacao.caminho == Path("/da/variavel.db").resolve()


def test_detecta_caminho_em_pasta_sincronizada_edge_case() -> None:
    """Caso de borda: caminho dentro do OneDrive é sinalizado como arriscado."""
    localizacao = _localizador({}).resolver("C:/Users/david/OneDrive/Documentos/graphow/graphow.db")
    assert localizacao.esta_em_pasta_sincronizada is True


def test_banco_em_memoria_nao_e_tratado_como_caminho_edge_case() -> None:
    """Caso de borda: o banco efêmero do SQLite não tem diretório nem risco de sincronização."""
    localizacao = _localizador({}).resolver(":memory:")
    assert localizacao.caminho_absoluto_texto == ":memory:"
    assert localizacao.esta_em_pasta_sincronizada is False


def test_fallback_para_home_quando_plataforma_nao_declara_diretorio_edge_case() -> None:
    """Caso de borda: sem LOCALAPPDATA nem XDG_DATA_HOME, cai no padrão POSIX."""
    localizacao = _localizador({}).resolver()
    esperado = HOME_FICTICIA / ".local" / "share" / "graphow" / "graphow.db"
    assert localizacao.caminho == esperado.resolve()


def test_deteccao_de_pasta_sincronizada_reconhece_variantes() -> None:
    """A detecção cobre os sincronizadores mais comuns e ignora pastas comuns."""
    assert caminho_esta_em_pasta_sincronizada(Path("/home/x/Dropbox/graphow.db")) is True
    assert caminho_esta_em_pasta_sincronizada(Path("/home/x/Google Drive/graphow.db")) is True
    assert caminho_esta_em_pasta_sincronizada(Path("/home/x/projetos/graphow.db")) is False


def test_preparador_cria_diretorio_e_ignora_memoria_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o preparador cria o diretório real e não faz nada para :memory:."""
    destino = tmp_path / "nivel1" / "nivel2" / "graphow.db"
    localizacao = _localizador({}).resolver(str(destino))
    PreparadorDiretorioBanco().garantir_diretorio(localizacao)
    assert destino.parent.is_dir()

    PreparadorDiretorioBanco().garantir_diretorio(_localizador({}).resolver(":memory:"))
