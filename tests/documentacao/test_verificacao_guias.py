"""O verificador precisa alcançar a fiação de hooks, não só o Markdown.

O arquivo `.agents/hooks/graphow_harness_hooks.json` estava quebrado e nenhum
teste o via: o verificador só lia `*.md`, e o argparse aceitava
`"$CLAUDE_SESSION_ID"` como texto qualquer. As duas lacunas fechadas aqui.
Ver defeito V-02.
"""

import json
from pathlib import Path

from graphow.documentacao.verificacao_guias import VerificadorDeGuias

RAIZ_PROJETO: Path = Path(__file__).parent.parent.parent


def _escrever_hook(raiz: Path, comando: str) -> None:
    """Publica uma fiação de hook mínima com o comando informado."""
    destino = raiz / ".agents" / "hooks"
    destino.mkdir(parents=True, exist_ok=True)
    conteudo = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": comando}]}]}}
    (destino / "teste_hooks.json").write_text(json.dumps(conteudo, indent=2), encoding="utf-8")


def test_hook_com_variavel_de_ambiente_e_recusado_nominal(tmp_path: Path) -> None:
    """O ambiente não define essas variáveis: o comando chegaria com texto cru."""
    _escrever_hook(tmp_path, 'graphow harness --fase inicio --sessao "$CLAUDE_SESSION_ID"')

    problemas = VerificadorDeGuias(tmp_path).verificar()

    assert len(problemas) == 1
    assert "variavel de ambiente" in problemas[0].motivo


def test_hook_com_argumento_invalido_e_recusado_nominal(tmp_path: Path) -> None:
    """Sem `--sessao` nem `--entrada-hook` o comando não tem sessão para registrar."""
    _escrever_hook(tmp_path, "graphow harness --fase inicio --setor setor-1")

    problemas = VerificadorDeGuias(tmp_path).verificar()

    assert len(problemas) == 1
    assert "harness" in problemas[0].invocacao


def test_hook_corrigido_passa_nominal(tmp_path: Path) -> None:
    """A forma que lê o payload na entrada padrão é aceita pelo parser real."""
    _escrever_hook(tmp_path, "graphow harness --fase inicio --entrada-hook --setor setor-1")

    assert VerificadorDeGuias(tmp_path).verificar() == ()


def test_fiacao_publicada_no_repositorio_esta_valida_nominal() -> None:
    """A fiação que o repositório entrega precisa passar pelo próprio verificador."""
    problemas = [
        problema.descrever()
        for problema in VerificadorDeGuias(RAIZ_PROJETO).verificar()
        if "hooks" in problema.arquivo
    ]

    assert not problemas, problemas


def test_json_sem_comando_algum_nao_gera_problema_edge_case(tmp_path: Path) -> None:
    """Caso de borda: JSON de configuração sem invocação não é assunto do verificador."""
    destino = tmp_path / ".agents"
    destino.mkdir(parents=True)
    (destino / "config.json").write_text('{"tema": "escuro"}', encoding="utf-8")

    assert VerificadorDeGuias(tmp_path).verificar() == ()
