"""Os dados da bancada: três projetos completos, sementes que reproduzem o laboratório e prompts fiéis a ele."""

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from graphow.bancada.projetos import Bancada, ErroDaBancada, preencher_modelo
from graphow.bancada.semente import GitDaBancada, criar_repositorio

PROJETOS: tuple[str, ...] = ("agenda-salas", "api-tarefas", "estoque-loja")

# sha256 dos prompts que o laboratório deu às três sessões de controle
# (graphow-lab/b/prompt-<projeto>.txt): o modelo preenchido tem de ser byte a byte o mesmo.
SHA_DO_PROMPT_DA_ENXUTA: dict[str, str] = {
    "agenda-salas": "f1cc2ffa8d05aca01086b5981fbd37300641a54fcbd3291b097b9a1eff775057",
    "api-tarefas": "344c4d19a0d760564ec8a108ef7f0a012fdd6ac7ca86e3b1e67cf194eb4a0a42",
    "estoque-loja": "dac177034263de2255917af1e2ac8f2faf155228ce4bc5f75633852ed25b0dc2",
}

# O prompt que o auditor do controle do estoque recebeu (graphow-lab/b/auditor-b-estoque-loja.md,
# com fim de linha LF), e os valores com que foi preenchido.
SHA_DO_AUDITOR_DO_LABORATORIO: str = "270b57a9dbb4fe0060b1081422a19caa444a12429eb82455bd7506a94bf061b0"
VALORES_DO_AUDITOR_DO_LABORATORIO: dict[str, str] = {
    "REPO": r"C:\Users\david\Documents\graphow-lab\b\estoque-loja",
    "SPEC": r"C:\Users\david\Documents\graphow-lab\b\spec-estoque-loja.md",
    "RAMO": "chamado-142",
}
FRASE_ORIGINAL_DA_PASTA_TEMPORARIA: str = "Rode o programa com dados em pasta temporária."
FRASE_NOVA_DA_PASTA_TEMPORARIA: str = (
    "Rode o programa com dados em pasta temporária: crie a sua com `mktemp -d` (nunca uma pasta de nome fixo: "
    "outro auditor pode estar rodando ao mesmo tempo), use-a para tudo o que for temporário e remova-a no fim."
)


def _sha(texto: str) -> str:
    """O sha256 do texto em UTF-8."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def test_bancada_tem_os_tres_projetos_completos_nominal() -> None:
    """Cada projeto tem semente, spec, sondas (oito) e projeto.json com ramo e semente."""
    projetos = Bancada().projetos()

    assert tuple(projeto.nome for projeto in projetos) == PROJETOS
    for projeto in projetos:
        assert any(projeto.pasta_da_semente.iterdir()), projeto.nome
        assert projeto.spec.read_text(encoding="utf-8").startswith("# Pedido do humano"), projeto.nome
        assert len(projeto.texto_das_sondas().splitlines()) == 8, projeto.nome
        assert projeto.ramo and projeto.semente.mensagem == "Estado inicial"
    assert {projeto.nome: projeto.ramo for projeto in projetos}["estoque-loja"] == "chamado-142"


def test_bancada_tem_os_dois_prompts_com_os_marcadores_nominal() -> None:
    """O prompt da enxuta pede spec e ramo; o do auditor, repositório, spec, ramo e sondas; a linha de base e o README estão lá."""
    bancada = Bancada()
    assert bancada.linha_de_base.is_file()
    assert "## Como ler o placar" in (bancada.raiz / "README.md").read_text(encoding="utf-8")

    assert "{SPEC}" in bancada.modelo_da_arquitetura("enxuta") and "{RAMO}" in bancada.modelo_da_arquitetura("enxuta")
    for marcador in ("{REPO}", "{SPEC}", "{RAMO}", "{SONDAS}"):
        assert marcador in bancada.modelo_do_auditor()


@pytest.mark.parametrize("nome", PROJETOS)
def test_semente_recriada_reproduz_o_commit_do_laboratorio_nominal(tmp_path: Path, nome: str) -> None:
    """Mesmo autor, data, mensagem e árvore: o mesmo hash do commit inicial do laboratório."""
    projeto = Bancada().projeto(nome)

    commit = criar_repositorio(projeto, tmp_path / nome)

    git = GitDaBancada(tmp_path / nome)
    assert commit == projeto.semente.commit == git.rodar("rev-parse", "HEAD").strip()
    assert git.rodar("branch", "--show-current").strip() == "main"
    assert git.rodar("status", "--porcelain") == ""


@pytest.mark.parametrize("nome", PROJETOS)
def test_prompt_da_enxuta_preenchido_e_o_do_laboratorio_nominal(nome: str) -> None:
    """Os três prompts do controle só diferiam no caminho da spec e no ramo."""
    bancada = Bancada()
    projeto = bancada.projeto(nome)

    prompt = preencher_modelo(bancada.modelo_da_arquitetura("enxuta"), {"SPEC": f"../spec-{nome}.md", "RAMO": projeto.ramo})

    assert _sha(prompt) == SHA_DO_PROMPT_DA_ENXUTA[nome]


def test_auditor_so_difere_do_laboratorio_pela_pasta_temporaria_nominal() -> None:
    """Desfeita a correção da pasta temporária, o prompt preenchido é o que os auditores receberam."""
    bancada = Bancada()
    modelo = bancada.modelo_do_auditor()
    assert modelo.count(FRASE_NOVA_DA_PASTA_TEMPORARIA) == 1
    valores = {**VALORES_DO_AUDITOR_DO_LABORATORIO, "SONDAS": bancada.projeto("estoque-loja").texto_das_sondas()}

    prompt = preencher_modelo(modelo.replace(FRASE_NOVA_DA_PASTA_TEMPORARIA, FRASE_ORIGINAL_DA_PASTA_TEMPORARIA), valores)

    assert _sha(prompt) == SHA_DO_AUDITOR_DO_LABORATORIO


def test_modelo_com_marcador_sem_valor_ou_valor_sem_marcador_recusa_edge_case() -> None:
    """Caso de borda: o prompt não roda com um pedaço faltando nem com valor que ninguém usa."""
    with pytest.raises(ErroDaBancada) as sem_valor:
        preencher_modelo("em {SPEC} no ramo {RAMO}", {"SPEC": "x"})
    with pytest.raises(ErroDaBancada) as sem_marcador:
        preencher_modelo("em {SPEC}", {"SPEC": "x", "RAMO": "y"})

    assert sem_valor.value.contexto["sem_valor"] == "RAMO"
    assert sem_marcador.value.contexto["sem_marcador"] == "RAMO"


def test_valor_com_chaves_nao_e_preenchido_de_novo_edge_case() -> None:
    """Caso de borda: uma sonda que cite `{RAMO}` fica como está; só o modelo tem marcadores."""
    assert preencher_modelo("{SONDAS} e {RAMO}", {"SONDAS": "- S1: {RAMO}?", "RAMO": "main"}) == "- S1: {RAMO}? e main"


def test_semente_divergente_recusa_antes_da_sessao_edge_case(tmp_path: Path) -> None:
    """Caso de borda: um byte a mais na semente muda a árvore, e a recusa diz o projeto."""
    copia = tmp_path / "bancada"
    shutil.copytree(Bancada().raiz / "projetos" / "agenda-salas", copia / "projetos" / "agenda-salas")
    (copia / "projetos" / "agenda-salas" / "semente" / "README.md").write_text("mexido\n", encoding="utf-8")

    with pytest.raises(ErroDaBancada) as recusa:
        criar_repositorio(Bancada(copia).projeto("agenda-salas"), tmp_path / "repo")

    assert recusa.value.contexto["projeto"] == "agenda-salas"


def test_destino_que_ja_existe_recusa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a execução nunca escreve por cima de um repositório que já está lá."""
    (tmp_path / "repo").mkdir()

    with pytest.raises(ErroDaBancada):
        criar_repositorio(Bancada().projeto("agenda-salas"), tmp_path / "repo")


def test_projeto_desconhecido_ou_incompleto_recusa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: nome que não existe lista os que existem; projeto.json sem ramo recusa."""
    with pytest.raises(ErroDaBancada) as desconhecido:
        Bancada().projeto("nao-existe")
    pasta = tmp_path / "projetos" / "x"
    pasta.mkdir(parents=True)
    (pasta / "projeto.json").write_text(json.dumps({"nome": "x", "descricao": "", "semente": {}}), encoding="utf-8")

    with pytest.raises(ErroDaBancada) as incompleto:
        Bancada(tmp_path).projetos()

    assert "estoque-loja" in desconhecido.value.contexto["existentes"]
    assert incompleto.value.contexto["projeto"] == "x"
