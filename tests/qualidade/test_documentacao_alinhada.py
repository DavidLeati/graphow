"""Guarda contra a deriva entre o que a documentação afirma e o que o código faz.

A auditoria encontrou três contagens diferentes de ferramentas MCP (README dizia 5,
a skill dizia 12, o código expunha 14) e duas promessas que o código contradizia.
Documentação que discorda do código custa mais do que rende — para a pessoa e para
qualquer agente que a leia como contexto.
"""

from pathlib import Path

from graphow.mcp.tool_definitions import DEFINICOES_FERRAMENTAS_MCP

RAIZ_PROJETO: Path = Path(__file__).parent.parent.parent
CAMINHO_README: Path = RAIZ_PROJETO / "README.md"
CAMINHO_SKILL: Path = RAIZ_PROJETO / ".agents" / "skills" / "graphow-mcp" / "SKILL.md"
CAMINHO_COOKBOOK: Path = RAIZ_PROJETO / ".agents" / "skills" / "graphow-mcp" / "references" / "patch_cookbook.md"

CONTAGENS_ANTIGAS_DE_FERRAMENTAS: tuple[str, ...] = ("expõe 5 ferramentas", "expõe 12 ferramentas")

# Afirmações que o código passou a sustentar. Se alguma sumir do README, ou o
# comportamento regrediu, ou a documentação parou de descrevê-lo.
MECANISMOS_QUE_O_README_DEVE_DESCREVER: tuple[str, ...] = (
    "ponteiro `(ramo_base, seq_corte)`",
    "BEGIN IMMEDIATE",
    "UNIQUE(ramo_id, seq)",
)


def _ler(caminho: Path) -> str:
    """Lê um documento do repositório em UTF-8."""
    return caminho.read_text(encoding="utf-8")


def test_contagem_de_ferramentas_bate_com_o_codigo_nominal() -> None:
    """README e skill precisam citar o mesmo número de ferramentas que o servidor expõe."""
    total = len(DEFINICOES_FERRAMENTAS_MCP)
    assert f"{total} ferramentas" in _ler(CAMINHO_README)
    assert f"{total} ferramentas" in _ler(CAMINHO_SKILL)


def test_contagens_antigas_de_ferramentas_nao_reaparecem_edge_case() -> None:
    """Caso de borda: as três contagens divergentes não podem voltar."""
    readme = _ler(CAMINHO_README)
    skill = _ler(CAMINHO_SKILL)
    for contagem in CONTAGENS_ANTIGAS_DE_FERRAMENTAS:
        assert contagem not in readme, contagem
        assert contagem not in skill, contagem


def test_readme_descreve_os_mecanismos_que_sustentam_as_promessas_edge_case() -> None:
    """Caso de borda: promessa sem mecanismo descrito volta a ser afirmação vazia."""
    readme = _ler(CAMINHO_README)
    ausentes = [mecanismo for mecanismo in MECANISMOS_QUE_O_README_DEVE_DESCREVER if mecanismo not in readme]
    assert not ausentes, ausentes


def test_skill_nao_instrui_agente_a_declarar_papel_edge_case() -> None:
    """Caso de borda: instruir o agente a mandar 'papel' voltaria a quebrar o portão."""
    for caminho in (CAMINHO_SKILL, CAMINHO_COOKBOOK):
        conteudo = _ler(caminho)
        assert '"papel":' not in conteudo, caminho.name


def test_toda_ferramenta_do_codigo_aparece_no_readme() -> None:
    """Cada ferramenta exposta precisa estar documentada na tabela do README."""
    readme = _ler(CAMINHO_README)
    ausentes = [
        ferramenta["name"]
        for ferramenta in DEFINICOES_FERRAMENTAS_MCP
        if f"`{ferramenta['name']}`" not in readme
    ]
    assert not ausentes, ausentes


def test_nenhuma_descricao_promete_agente_respondendo_duvida_edge_case() -> None:
    """Caso de borda: a descrição de `abrir_questao` ficou para trás do kernel.

    Ela dizia que a dúvida bloqueia "até que o humano ou agente responda". Desde
    que o RoleGate passou a reservar `respondida` e `descartada` ao humano, isso
    é uma promessa que o produto recusa — e é o agente quem a lê.
    """
    descricoes = " ".join(str(ferramenta["description"]) for ferramenta in DEFINICOES_FERRAMENTAS_MCP)

    assert "humano ou agente responda" not in descricoes


def test_nenhum_schema_de_ferramenta_expoe_papel() -> None:
    """O contrato publicado aos agentes não pode reintroduzir o campo recusado."""
    for ferramenta in DEFINICOES_FERRAMENTAS_MCP:
        propriedades = ferramenta["inputSchema"]["properties"]
        assert "papel" not in propriedades, ferramenta["name"]


def test_catalogo_gerado_esta_em_dia_com_o_codigo() -> None:
    """O que está em docs/ tem de ser exatamente o que o código produziria agora.

    Este é o teste que substitui a manutenção manual: se alguém alterar o código
    sem regenerar, ou editar um documento gerado à mão, a suíte acusa aqui.
    """
    from graphow.documentacao import MontadorDocumentacaoDoRepositorio

    montador = MontadorDocumentacaoDoRepositorio(RAIZ_PROJETO / "src" / "graphow", RAIZ_PROJETO / "docs")
    desatualizados = [
        documento.caminho_relativo
        for documento in montador.montar_documentos()
        if not _documento_confere(documento.caminho_relativo, documento.conteudo)
    ]
    assert not desatualizados, "Rode 'graphow docs-gerar':\n" + "\n".join(desatualizados)


def _documento_confere(caminho_relativo: str, conteudo_esperado: str) -> bool:
    """Compara um documento gerado com o arquivo presente em docs/."""
    caminho = RAIZ_PROJETO / "docs" / caminho_relativo
    if not caminho.is_file():
        return False
    return caminho.read_text(encoding="utf-8") == conteudo_esperado


def test_toda_ala_declarada_tem_dossie_no_disco_nominal() -> None:
    """Cada ala do catálogo precisa ter o próprio dossiê publicado."""
    from graphow.documentacao.setores import DEFINICOES_DE_SETOR

    ausentes = [
        definicao.pacote
        for definicao in DEFINICOES_DE_SETOR
        if not (RAIZ_PROJETO / "docs" / "setores" / f"{definicao.numero:02d}_{definicao.pacote}.md").is_file()
    ]
    assert not ausentes, ausentes


def test_indice_nao_volta_a_ser_um_catalogo_monolitico_edge_case() -> None:
    """Caso de borda: o índice é o mapa, não o acervo. 197 KB indicavam o inverso."""
    tamanho = (RAIZ_PROJETO / "docs" / "INDEX.md").stat().st_size
    assert tamanho < 32_000, f"INDEX.md com {tamanho} bytes: o detalhe pertence aos dossiês"
