"""O autor de aceite: testes escritos antes da implementação, por outra sessão, vermelhos, e intocáveis pelo executor."""

import copy
from pathlib import Path
import sys
from typing import Any

import pytest

from graphow.core.types import TipoAresta
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal, LoteRecusado

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    ACEITE_C1,
    PLANO,
    SOMA_CERTA,
    VERIFICAR,
    aceite_em_pytest,
    autor_de_aceite,
    executor_pronto,
    montar_bancada,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
PYTHON: str = f'"{sys.executable}"'


def _roteiro_limpo() -> dict[str, list[dict[str, Any]]]:
    """Plano, aceite, duas fatias e uma verificação limpa."""
    roteiro = roteiro_completo()
    roteiro["executor"] = roteiro["executor"][:2]
    roteiro["verificador"] = [verificacao("atende")]
    return roteiro


def test_autor_de_aceite_escreve_testes_vermelhos_antes_de_qualquer_fatia_nominal(tmp_path: Path) -> None:
    """F2.2: o autor é outra sessão, antes do executor; o teste nasce vermelho, é commitado e ligado ao critério."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    papeis = [chamada["papel"] for chamada in bancada.chamadas()]
    assert papeis[:3] == ["planejador", "aceite", "executor"]
    autor = bancada.chamadas("aceite")[0]
    assert Path(autor["argv"][autor["argv"].index("--append-system-prompt-file") + 1]).name == "aceite.md"
    view = bancada.kernel.obter_view()
    artefato = view.obter_no("art-aceite-goal-soma")
    assert artefato is not None
    vermelhos = artefato.obter_propriedade("vermelhos_antes_da_implementacao")
    assert [(e["criterio"], e["passou"]) for e in vermelhos] == [("C1", False), ("", False)]
    assert sorted(a.destino_id for a in view.obter_arestas_saida(artefato.id, TipoAresta.DERIVA_DE)) == ["crit-soma-c1", "crit-soma-c2"]
    c1, c2 = view.obter_no("crit-soma-c1"), view.obter_no("crit-soma-c2")
    assert [t["nome"] for t in c1.obter_propriedade("testes_de_aceite")] == ["test_c1_soma"]
    assert c2.obter_propriedade("checagem") == ["abrir o README.md e achar um exemplo de somar com o resultado"]
    estado = ler_estado(view, "goal-soma")
    assert estado is not None and estado.arquivos_protegidos() == ("aceite/aceite_c1.py",)
    assuntos = git(bancada.repositorio, "log", "--format=%s", "main").splitlines()
    assert assuntos.index("Escreve os testes de aceite do Goal soma (C1, C2)") > assuntos.index("Fatia F1: Funcao somar (C1)")
    assert "## Testes de aceite" in (bancada.repositorio / "docs" / "goals" / "soma.md").read_text(encoding="utf-8")
    assert (bancada.repositorio / "aceite" / "aceite_c1.py").read_text(encoding="utf-8") == ACEITE_C1


def test_teste_que_ja_passa_sem_justificativa_volta_ao_autor_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o teste que passa sem implementação é sinalizado; a mesma sessão corrige e o Goal segue."""
    roteiro = _roteiro_limpo()
    vazio = autor_de_aceite()
    vazio["arquivos"] = {"aceite/aceite_c1.py": '"""C1."""\n\ndef test_c1_soma():\n    pass\n\n\ntest_c1_soma()\nprint("ok")\n'}
    roteiro["aceite"] = [vazio, autor_de_aceite()]
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    primeira, retomada = bancada.chamadas("aceite")
    assert "--resume" in retomada["argv"] and "--resume" not in primeira["argv"]
    assert "o teste test_c1_soma de C1 ja passa sem implementacao" in retomada["stdin"]


def test_teste_que_ja_passa_com_justificativa_vale_e_fica_registrado_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o critério que o código já atendia é aceito, com o porquê gravado no Criterio e no documento."""
    roteiro = _roteiro_limpo()
    roteiro["aceite"] = [autor_de_aceite(ja_atendido="somar ja soma certo na base")]
    bancada = montar_bancada(tmp_path, roteiro)
    (bancada.repositorio / "soma.py").write_text(SOMA_CERTA, encoding="utf-8", newline="\n")
    git(bancada.repositorio, "commit", "-qam", "Soma certa na base")

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    c1 = bancada.kernel.obter_view().obter_no("crit-soma-c1")
    assert c1 is not None and c1.obter_propriedade("ja_atendido") == "somar ja soma certo na base"
    assert "o codigo ja atendia: somar ja soma certo na base" in (bancada.repositorio / "docs/goals/soma.md").read_text(encoding="utf-8")


def test_autor_que_mexe_fora_de_aceite_nao_e_aceito_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o autor que altera um arquivo do projeto volta com o problema; insistindo, o laço para sem commit."""
    roteiro = _roteiro_limpo()
    invasor = autor_de_aceite()
    invasor["arquivos"] = {**invasor["arquivos"], "soma.py": SOMA_CERTA}
    roteiro["aceite"] = [invasor, copy.deepcopy(invasor)]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA
    assert "soma.py foi criado ou mudado fora de aceite/" in parada.mensagem
    assert bancada.chamadas("executor") == []
    assert "Escreve os testes de aceite" not in git(bancada.repositorio, "log", "--format=%s", "graphow/soma")


def test_executor_que_mexe_no_teste_de_aceite_e_recusado_nominal(tmp_path: Path) -> None:
    """F2.2: a fatia que altera o teste de aceite falha; a nova tentativa, que não o toca, fecha; o teste segue o original."""
    roteiro = _roteiro_limpo()
    trapaceiro = executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR, "aceite/aceite_c1.py": "print('ok')\n"})
    roteiro["executor"].insert(0, trapaceiro)
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    segunda = bancada.chamadas("executor")[1]["stdin"]
    assert "alterou, apagou, moveu ou criou em aceite/ os arquivos aceite/aceite_c1.py" in segunda
    assert (bancada.repositorio / "aceite" / "aceite_c1.py").read_text(encoding="utf-8") == ACEITE_C1
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.fatias[0].falhas == 1


def test_suite_do_plano_roda_sem_os_testes_de_aceite_e_a_final_os_junta_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a suíte que falha vendo aceite/ passa nas fatias (roda sem eles), e a final, que junta os dois, a pega."""
    plano = copy.deepcopy(PLANO)
    plano["comando_suite"] = f"{PYTHON} verificar.py && {PYTHON} -c \"import os, sys; sys.exit(os.path.exists('aceite/aceite_c1.py'))\""
    roteiro = _roteiro_limpo()
    roteiro["planejador"] = [{"saida": plano, "custo": 0.4}]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert not parada.fechou
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and [f.falhas for f in estado.fatias[:2]] == [0, 0]
    final = estado.verificacoes[0]
    juntos = final.propriedades["aceite_do_orquestrador"][-1]
    assert juntos["teste"] == "suite_e_aceite" and not juntos["passou"]
    assert [a.texto("titulo") for a in final.bloqueantes()] == ["A suite e os testes de aceite juntos falharam no commit verificado"]
    assert (tmp_path / "estado" / "goal-soma" / "area" / "aceite" / "aceite_c1.py").is_file()


def test_teste_de_aceite_vermelho_na_verificacao_reprova_o_criterio_que_o_verificador_aprovou_nominal(tmp_path: Path) -> None:
    """O verificador diz que C1 atende, o teste de aceite falha: C1 fica nao_atende, vira Achado bloqueante e correção."""
    roteiro = _roteiro_limpo()
    aceite = autor_de_aceite()
    borda = ACEITE_C1.replace("assert somar(2, 3) == 5", "assert somar(2, 3) == 5 and somar(-2, -3) == -5")
    aceite["arquivos"] = {"aceite/aceite_c1.py": borda}
    roteiro["aceite"] = [aceite]
    roteiro["executor"][0] = executor_pronto({"soma.py": "def somar(a, b):\n    return abs(a) + abs(b)\n", "verificar.py": VERIFICAR})
    roteiro["executor"].append(executor_pronto({"soma.py": SOMA_CERTA}))
    roteiro["verificador"] = [verificacao("atende"), verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    primeira = estado.verificacoes[0]
    assert {p["id"]: p["veredito"] for p in primeira.propriedades["pareceres"]}["C1"] == "nao_atende"
    assert [a.texto("titulo") for a in primeira.bloqueantes()] == ["O teste de aceite test_c1_soma de C1 falhou"]
    assert [f.codigo for f in estado.fatias] == ["F1", "F2", "M1.K1.1"]
    assert [e["passou"] for e in estado.verificacoes[-1].propriedades["aceite_do_orquestrador"]] == [True, True, True]


def test_supervisionado_para_depois_do_autor_e_aprova_plano_e_testes_juntos_nominal(tmp_path: Path) -> None:
    """F2 item 3: o portão vem depois do aceite; aprovar grava o commit dos testes; o kernel recusa fechar com verificação velha."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())
    orquestrador = bancada.orquestrador()

    no_portao = orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco())
    assert no_portao.motivo == MotivoDaParada.AGUARDANDO_APROVACAO
    assert "testes de aceite esperam aprovacao" in no_portao.mensagem
    assert [c["papel"] for c in bancada.chamadas()] == ["planejador", "aceite"]
    orquestrador.aprovar_plano("goal-soma", "david")
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.aceite is not None
    assert estado.propriedades["aprovacao_do_plano"]["documento"] == estado.aceite["commit"]
    pronto = orquestrador.rodar("goal-soma", OpcoesDoLaco())
    assert pronto.motivo == MotivoDaParada.PRONTO_PARA_INTEGRAR, pronto.mensagem
    livro = LivroRazaoDoGoal(bancada.kernel, "goal-soma")
    livro.gravar_ponta({"commit": "f" * 40, "commit_do_codigo": "f" * 40})

    with pytest.raises(LoteRecusado) as recusa:
        livro.fechar("f" * 40)

    assert recusa.value.contexto["modo"] == "fechamento_sem_verificacao_limpa"
    assert "a ultima verificacao foi feita no commit" in recusa.value.contexto["motivo"]


def test_teste_vermelho_por_erro_de_coleta_volta_ao_autor_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o teste que falha porque o import do topo quebra a coleta não vale como vermelho; o autor corrige."""
    roteiro = _roteiro_limpo()
    coleta = '"""C1."""\nfrom modulo_que_nao_existe import somar\n\n\ndef test_c1_soma():\n    assert somar(2, 3) == 5\n'
    roteiro["aceite"] = [aceite_em_pytest(coleta), aceite_em_pytest()]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    retomada = bancada.chamadas("aceite")[1]["stdin"]
    assert "o teste test_c1_soma de C1 esta vermelho pelo motivo errado: o pytest saiu com 4" in retomada


def test_teste_de_aceite_pulado_pelo_modulo_do_executor_nao_passa_edge_case(tmp_path: Path) -> None:
    """Caso de borda (bloqueante 1c): o código que faz o teste de aceite se pular sai com zero, e mesmo assim reprova C1."""
    roteiro = _roteiro_limpo()
    roteiro["aceite"] = [aceite_em_pytest()]
    pula = ("import sys\n\nif 'pytest' in sys.modules:\n    import pytest\n    pytest.skip('pulado', allow_module_level=True)\n\n\n"
            "def somar(a, b):\n    return a - b\n")
    roteiro["executor"][0] = executor_pronto({"soma.py": pula, "verificar.py": "print('ok')\n"})
    roteiro["executor"].append(executor_pronto({"soma.py": SOMA_CERTA}))
    roteiro["verificador"] = [verificacao("atende"), verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    primeira = estado.verificacoes[0]
    assert {p["id"]: p["veredito"] for p in primeira.propriedades["pareceres"]}["C1"] == "nao_atende"
    assert "1 teste(s) foram pulados" in primeira.bloqueantes()[0].texto("descricao")
    assert [e["passou"] for e in estado.verificacoes[-1].propriedades["aceite_do_orquestrador"]] == [True, True, True]
