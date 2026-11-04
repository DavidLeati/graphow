"""A Evidence que o orquestrador grava leva o commit e os arquivos, e a conferência diz se ela ainda vale na ponta."""

import copy
from pathlib import Path
from typing import Any

from graphow.core.models import NoGrafo
from graphow.kernel.ancora_do_artifact import PADRAO_DO_COMMIT
from graphow.orquestrador.conferencia_da_evidencia import DESATUALIZADA, VIGENTE, conferir_evidencia
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.documento_do_goal import caminho_do_documento
from graphow.orquestrador.git_do_goal import GitDoGoal

from tests.orquestrador.apoio_laco import (
    PLANO,
    Bancada,
    montar_bancada,
    revisao,
    roteiro_completo,
    roteiro_em_dois_marcos_com_um_ciclo_cada,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


def _no(bancada: Bancada, id_no: str) -> NoGrafo:
    """O nó gravado no livro-razão."""
    no = bancada.kernel.obter_view().obter_no(id_no)
    assert no is not None, id_no
    return no


def test_verificacao_fica_desatualizada_quando_uma_fatia_mexe_num_arquivo_dela_nominal(tmp_path: Path) -> None:
    """T3d1.1: a fatia que mexe num arquivo da verificação a desatualiza, com ele; a que mexe noutro, não.

    A correção de M1 mexe em soma.py, que a verificação do marco M1 afirma. A
    conferência de M1, depois da correção, segue vigente: as fatias seguintes
    mexem só no README.
    """
    bancada = montar_bancada(tmp_path, roteiro_em_dois_marcos_com_um_ciclo_cada())

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    primeira, segunda = _no(bancada, "ver-goal-soma-1"), _no(bancada, "ver-goal-soma-2")
    assert PADRAO_DO_COMMIT.fullmatch(str(primeira.obter_propriedade("commit")))
    assert primeira.obter_propriedade("arquivos") == ["aceite/aceite_c1.py", "soma.py", "verificar.py"]
    assert caminho_do_documento("soma") not in segunda.obter_propriedade("arquivos")
    repositorio = GitDoGoal(bancada.repositorio)
    desatualizada = conferir_evidencia(primeira.propriedades, repositorio, ponta="main")
    vigente = conferir_evidencia(segunda.propriedades, repositorio, ponta="main")
    assert (desatualizada.estado, desatualizada.arquivos) == (DESATUALIZADA, ("soma.py",))
    assert (vigente.estado, vigente.arquivos, vigente.motivo) == (VIGENTE, (), "")
    final, conferencia_final = _no(bancada, "ver-goal-soma-3"), _no(bancada, "ver-goal-soma-4")
    assert conferir_evidencia(final.propriedades, repositorio, ponta="main").arquivos == ("README.md",)
    assert conferir_evidencia(conferencia_final.propriedades, repositorio, ponta="main").vigente


def _roteiro_com_f1_de_risco() -> dict[str, list[dict[str, Any]]]:
    """F1 marcada como risco pelo planejador e aprovada pelo revisor; F2 mexe só no README."""
    plano = copy.deepcopy(PLANO)
    plano["fatias"][0].update(risco=True, motivo_do_risco="regra de dominio da soma")
    roteiro = roteiro_completo()
    roteiro.update(planejador=[{"saida": plano, "custo": 0.4}], executor=roteiro["executor"][:2], verificador=[verificacao("atende")],
                   revisor=[revisao()])
    return roteiro


def test_revisao_de_risco_ancora_na_arvore_revisada_e_o_commit_da_fatia_nao_a_desatualiza_nominal(tmp_path: Path) -> None:
    """A revisão julga a mudança fora de commit: guarda o HEAD, a árvore revisada e os arquivos, e o commit dela a mantém vigente."""
    bancada = montar_bancada(tmp_path, _roteiro_com_f1_de_risco())

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    revisada = _no(bancada, "rev-task-soma-f1-t1")
    fatia = _no(bancada, "art-task-soma-f1-t1")
    assert revisada.obter_propriedade("arquivos") == ["soma.py", "verificar.py"]
    assert PADRAO_DO_COMMIT.fullmatch(str(revisada.obter_propriedade("arvore")))
    assert revisada.obter_propriedade("commit") != fatia.obter_propriedade("commit"), "a revisao vem antes do commit da fatia"
    conferencia = conferir_evidencia(revisada.propriedades, GitDoGoal(bancada.repositorio), ponta="main")
    assert (conferencia.estado, conferencia.arquivos) == (VIGENTE, ())


def test_briefing_da_conferencia_nao_lista_a_verificacao_desatualizada_como_fato_vigente_nominal(tmp_path: Path) -> None:
    """T3d2.1: os pareceres da verificação anterior que a correção desatualizou vêm com o aviso, e não como fato vigente.

    A correção de M1 mexe em soma.py, que a verificação ver-1 afirma; a de M2,
    no README, que a ver-3 afirma. Cada conferência recebe os pareceres de
    antes sob o aviso, com o arquivo que mudou.
    """
    bancada = montar_bancada(tmp_path, roteiro_em_dois_marcos_com_um_ciclo_cada())

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    primeira, segunda = (chamada["stdin"] for chamada in bancada.chamadas("conferencia"))
    for briefing, anterior, arquivo in ((primeira, "ver-goal-soma-1", "soma.py"), (segunda, "ver-goal-soma-3", "README.md")):
        assert f"## Pareceres da verificacao anterior ({anterior}), DESATUALIZADA: {arquivo} mudaram desde o commit dela: " \
               "sao historico, nao fato vigente" in briefing, briefing
        assert f"## Pareceres da verificacao anterior ({anterior})\n" not in briefing
