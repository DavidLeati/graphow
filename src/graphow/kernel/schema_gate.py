"""Portão 1: Validação de Conformidade Estrutural com a Ontologia (Schema Gate)."""

from collections.abc import Mapping, Set
from typing import Any

from graphow.core.exceptions import ErroPatchInvalido, ErroSegurancaPatch
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.governanca import (
    ID_GOVERNANCA_GLOBAL,
    PROPRIEDADE_GOVERNANCA_DO_PROJETO,
    validar_configuracao_do_projeto,
    validar_configuracao_global,
)
from graphow.core.models import GrafoEstado
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.forma_e_identidade import (
    COLECAO_DE_NOS,
    SEGMENTOS_ATE_O_IDENTIFICADOR,
    ContextoValidacaoNo,
    CriadosNoLote,
    validar_caminho,
    validar_identidade,
)
from graphow.kernel.pares_de_escopo import PARES_DE_ARESTAS_DO_ESCOPO
from graphow.kernel.patch_models import (
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
    ResultadoValidacao,
    SanitizadorPatch,
)


# '/nos/<id>/propriedades/<chave>': o caminho que escreve uma propriedade.
SEGMENTOS_ATE_A_CHAVE: int = 4


class SchemaGate:
    """Portão de validação estrutural contra as regras formais da ontologia.

    Esta tabela responde "que pares de tipos essa aresta admite". Quem responde
    "que papel pode criá-la ou removê-la" é `kernel/matriz_papeis.py`, aplicada
    pelo RoleGate. As duas vivem lado a lado de propósito: uma aresta nova exige
    entrada nas duas, e o teste de estrutura recusa qualquer tipo sem dono.
    """

    PARES_ARESTAS_PERMITIDOS: Mapping[TipoAresta, Set[tuple[TipoNo, TipoNo]]] = {
        TipoAresta.CONTEM: frozenset({(TipoNo.PROJETO, TipoNo.SETOR), (TipoNo.SETOR, TipoNo.SESSAO)}),
        TipoAresta.PRODUZ: frozenset({
            (TipoNo.SESSAO, TipoNo.GOAL),
            (TipoNo.SESSAO, TipoNo.TASK),
            (TipoNo.SESSAO, TipoNo.DECISION),
            (TipoNo.SESSAO, TipoNo.QUESTION),
            (TipoNo.SESSAO, TipoNo.CONSTRAINT),
            (TipoNo.SESSAO, TipoNo.ARTIFACT),
            (TipoNo.SESSAO, TipoNo.EVIDENCE),
            (TipoNo.SESSAO, TipoNo.RUN),
            (TipoNo.SESSAO, TipoNo.NOTE),
            (TipoNo.SESSAO, TipoNo.APRENDIZADO),
        }),
        TipoAresta.OCORREU_EM: frozenset({(TipoNo.RUN, TipoNo.SESSAO)}),
        TipoAresta.DECOMPOE: frozenset({(TipoNo.GOAL, TipoNo.TASK), (TipoNo.TASK, TipoNo.TASK)}),
        TipoAresta.DEPENDE_DE: frozenset({(TipoNo.TASK, TipoNo.TASK)}),
        TipoAresta.BLOQUEIA: frozenset({(TipoNo.QUESTION, TipoNo.TASK)}),
        TipoAresta.JUSTIFICA: frozenset({(TipoNo.EVIDENCE, TipoNo.DECISION)}),
        # Evidence -> Aprendizado: o achado novo que sinaliza que a memória
        # precisa de revisão. O aprendizado não é apagado; fica marcado.
        TipoAresta.CONTRADIZ: frozenset({
            (TipoNo.EVIDENCE, TipoNo.DECISION),
            (TipoNo.EVIDENCE, TipoNo.EVIDENCE),
            (TipoNo.EVIDENCE, TipoNo.APRENDIZADO),
        }),
        TipoAresta.SUBSTITUI: frozenset({
            (TipoNo.DECISION, TipoNo.DECISION),
            (TipoNo.TASK, TipoNo.TASK),
            (TipoNo.APRENDIZADO, TipoNo.APRENDIZADO),
        }),
        # Alcance de um aprendizado: onde ele passa a valer. O humano promove.
        TipoAresta.VALE_PARA: frozenset({
            (TipoNo.APRENDIZADO, TipoNo.PROJETO),
            (TipoNo.APRENDIZADO, TipoNo.SETOR),
        }),
        TipoAresta.ESCOPA: frozenset({
            (TipoNo.CONSTRAINT, TipoNo.GOAL),
            (TipoNo.CONSTRAINT, TipoNo.TASK),
        }),
        # A decisão aponta o trabalho em que vale. No Goal, alcança as Tasks
        # que o decompõem; na Task, chega à vista de quem a executa e revisa.
        TipoAresta.ORIENTA: frozenset({
            (TipoNo.DECISION, TipoNo.TASK),
            (TipoNo.DECISION, TipoNo.GOAL),
        }),
        # Note -> Task/Decision existe para que a nota reativa aponte para algo:
        # sem esse par ela nascia órfã e nenhum agente a encontrava. Note ->
        # Evidence/Artifact existe para a condensação de uma sessão apontar para
        # o achado e para a entrega que ela resume.
        # Aprendizado -> origem: a aresta que o InvariantGate exige no mesmo lote.
        # Evidence -> Artifact/Task: o teste do executor e o veredito do revisor
        # apontam para o trabalho que avaliam, em vez de ficarem presos à sessão.
        TipoAresta.DERIVA_DE: frozenset({
            (TipoNo.ARTIFACT, TipoNo.TASK),
            (TipoNo.ARTIFACT, TipoNo.ARTIFACT),
            (TipoNo.EVIDENCE, TipoNo.ARTIFACT),
            (TipoNo.EVIDENCE, TipoNo.TASK),
            (TipoNo.NOTE, TipoNo.TASK),
            (TipoNo.NOTE, TipoNo.DECISION),
            (TipoNo.NOTE, TipoNo.EVIDENCE),
            (TipoNo.NOTE, TipoNo.ARTIFACT),
            (TipoNo.APRENDIZADO, TipoNo.EVIDENCE),
            (TipoNo.APRENDIZADO, TipoNo.DECISION),
            (TipoNo.APRENDIZADO, TipoNo.NOTE),
            (TipoNo.APRENDIZADO, TipoNo.ARTIFACT),
            (TipoNo.APRENDIZADO, TipoNo.TASK),
        }),
        **PARES_DE_ARESTAS_DO_ESCOPO,
    }

    def validar(self, proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
        """Avalia todas as operações do patch contra o schema da ontologia."""
        criados = CriadosNoLote()
        for item in proposta.operacoes:
            resultado_item = self._validar_operacao(item, estado, criados)
            if not resultado_item.aprovado:
                return resultado_item
        return ResultadoValidacao.sucesso()

    def _validar_operacao(
        self,
        item: ItemPatch,
        estado: GrafoEstado,
        criados: CriadosNoLote,
    ) -> ResultadoValidacao:
        """Sanitiza a operação e, se ela for segura, valida contra a ontologia."""
        resultado_sanitizacao = self._sanitizar(item)
        if not resultado_sanitizacao.aprovado:
            return resultado_sanitizacao
        return self._validar_item(item, estado, criados)

    def _sanitizar(self, item: ItemPatch) -> ResultadoValidacao:
        """Converte as falhas de sanitização em veredito, preservando o caminho ofensor."""
        try:
            SanitizadorPatch.sanitizar_item(item)
        except ErroSegurancaPatch as erro:
            return self._recusar_sanitizacao(item, erro, ModoFalhaMAST.PROTOTYPE_POLLUTION)
        except ErroPatchInvalido as erro:
            return self._recusar_sanitizacao(item, erro, ModoFalhaMAST.CAMINHO_INVALIDO)
        return ResultadoValidacao.sucesso()

    def _recusar_sanitizacao(
        self,
        item: ItemPatch,
        erro: ErroPatchInvalido | ErroSegurancaPatch,
        modo: ModoFalhaMAST,
    ) -> ResultadoValidacao:
        """Converte a excecao do sanitizador em veredito, preservando o caminho."""
        contexto = {"path": item.path, **erro.contexto}
        return ResultadoValidacao.falha(erro.mensagem, "SchemaGate", contexto, modo=modo)

    def _validar_item(
        self,
        item: ItemPatch,
        estado: GrafoEstado,
        criados: CriadosNoLote,
    ) -> ResultadoValidacao:
        """Confere o caminho e despacha a validação para nó ou aresta."""
        segmentos = tuple(seg for seg in item.path.split("/") if seg)
        resultado_caminho = validar_caminho(item, segmentos)
        if not resultado_caminho.aprovado:
            return resultado_caminho
        ctx = ContextoValidacaoNo(segmentos=segmentos, item=item, estado=estado)
        if segmentos[0] == COLECAO_DE_NOS:
            return self._validar_operacao_no(ctx, criados)
        return self._validar_operacao_aresta(ctx, criados)

    def _validar_operacao_no(
        self,
        ctx: ContextoValidacaoNo,
        criados: CriadosNoLote,
    ) -> ResultadoValidacao:
        """Valida inserção ou alteração de nó."""
        if len(ctx.segmentos) == SEGMENTOS_ATE_O_IDENTIFICADOR and ctx.item.op == OperacaoPatch.ADD:
            return self._validar_criacao_no(ctx, criados)
        id_no = ctx.segmentos[1]
        if ctx.estado.contem_no(id_no) or id_no in criados.nos:
            return self._validar_propriedade_de_governanca(ctx, criados)
        return ResultadoValidacao.falha(
            f"Nó '{id_no}' não existe no grafo",
            "SchemaGate",
            modo=ModoFalhaMAST.REFERENCIA_INEXISTENTE,
        )

    def _validar_propriedade_de_governanca(
        self,
        ctx: ContextoValidacaoNo,
        criados: CriadosNoLote,
    ) -> ResultadoValidacao:
        """Confere a escrita de uma propriedade do Governanca ou da `governanca` de um Projeto."""
        if len(ctx.segmentos) != SEGMENTOS_ATE_A_CHAVE or ctx.item.op == OperacaoPatch.REMOVE:
            return ResultadoValidacao.sucesso()
        id_no, chave = ctx.segmentos[1], ctx.segmentos[3]
        tipo = criados.nos.get(id_no) or ctx.estado.nos[id_no].tipo
        if tipo == TipoNo.GOVERNANCA:
            return self._recusar_governanca_malformada(validar_configuracao_global({chave: ctx.item.value}))
        if tipo == TipoNo.PROJETO and chave == PROPRIEDADE_GOVERNANCA_DO_PROJETO:
            return self._recusar_governanca_malformada(validar_configuracao_do_projeto(ctx.item.value))
        return ResultadoValidacao.sucesso()

    def _validar_governanca_declarada(self, tipo: TipoNo, valor: dict[str, Any]) -> ResultadoValidacao:
        """Confere a política declarada na criação de um Governanca ou de um Projeto."""
        propriedades = valor.get("propriedades", {})
        if tipo == TipoNo.GOVERNANCA:
            if valor["id"] != ID_GOVERNANCA_GLOBAL:
                return self._recusar_governanca_fantasma(str(valor["id"]))
            return self._recusar_governanca_malformada(validar_configuracao_global(propriedades))
        if tipo == TipoNo.PROJETO and PROPRIEDADE_GOVERNANCA_DO_PROJETO in propriedades:
            problemas = validar_configuracao_do_projeto(propriedades[PROPRIEDADE_GOVERNANCA_DO_PROJETO])
            return self._recusar_governanca_malformada(problemas)
        return ResultadoValidacao.sucesso()

    def _recusar_governanca_fantasma(self, id_no: str) -> ResultadoValidacao:
        """Só o singleton `governanca-global` é lido pela resolução: um segundo nó seria configuração fantasma."""
        return ResultadoValidacao.falha(
            f"O nó 'Governanca' '{id_no}' é recusado: a política de governança global vive só no "
            f"nó '{ID_GOVERNANCA_GLOBAL}', e um segundo nó seria configuração que nenhum portão lê",
            "SchemaGate",
            {"id_esperado": ID_GOVERNANCA_GLOBAL},
            modo=ModoFalhaMAST.ESTRUTURA_INCOMPLETA,
        )

    def _recusar_governanca_malformada(self, problemas: list[str]) -> ResultadoValidacao:
        """Recusa a configuração de governança que a validação do domínio apontou como inválida."""
        if not problemas:
            return ResultadoValidacao.sucesso()
        detalhe = "; ".join(problemas)
        return ResultadoValidacao.falha(
            f"Configuração de governança inválida: {detalhe}",
            "SchemaGate",
            {"problemas": detalhe},
            modo=ModoFalhaMAST.ESTRUTURA_INCOMPLETA,
        )

    def _validar_criacao_no(self, ctx: ContextoValidacaoNo, criados: CriadosNoLote) -> ResultadoValidacao:
        """Checa estrutura, identidade e tipo formal do nó a ser criado."""
        valor = ctx.item.value
        resultado_estrutura = self._validar_estrutura_do_no(valor)
        if not resultado_estrutura.aprovado:
            return resultado_estrutura
        resultado_identidade = validar_identidade(ctx, criados)
        if not resultado_identidade.aprovado:
            return resultado_identidade
        try:
            tipo = TipoNo(valor["tipo"])
        except ValueError:
            return ResultadoValidacao.falha(
                f"Tipo de nó inválido: '{valor.get('tipo')}'",
                "SchemaGate",
                modo=ModoFalhaMAST.TIPO_DESCONHECIDO,
            )
        criados.nos[str(valor["id"])] = tipo
        return self._validar_governanca_declarada(tipo, valor)

    def _validar_estrutura_do_no(self, valor: Any) -> ResultadoValidacao:
        """Um objeto com 'id' e 'tipo', e 'propriedades', quando vier, também objeto.

        O acumulador copia as propriedades com `dict(...)`. Um texto ali passava
        pelos portões e estourava na projeção, depois de gravado.
        """
        if not isinstance(valor, dict):
            return ResultadoValidacao.falha(
                "Valor do nó deve ser um objeto JSON",
                "SchemaGate",
                modo=ModoFalhaMAST.ESTRUTURA_INCOMPLETA,
            )
        if "id" not in valor or "tipo" not in valor:
            return ResultadoValidacao.falha(
                "Nó deve conter obrigatoriamente 'id' e 'tipo'",
                "SchemaGate",
                modo=ModoFalhaMAST.ESTRUTURA_INCOMPLETA,
            )
        if not isinstance(valor.get("propriedades", {}), dict):
            return ResultadoValidacao.falha(
                "'propriedades' do nó deve ser um objeto JSON",
                "SchemaGate",
                modo=ModoFalhaMAST.ESTRUTURA_INCOMPLETA,
            )
        return ResultadoValidacao.sucesso()

    def _validar_operacao_aresta(
        self,
        ctx: ContextoValidacaoNo,
        criados: CriadosNoLote,
    ) -> ResultadoValidacao:
        """Valida criação e semântica de conexão da aresta."""
        if len(ctx.segmentos) == SEGMENTOS_ATE_O_IDENTIFICADOR and ctx.item.op == OperacaoPatch.ADD:
            return self._validar_criacao_aresta(ctx, criados)
        return ResultadoValidacao.sucesso()

    def _validar_criacao_aresta(
        self,
        ctx: ContextoValidacaoNo,
        criados: CriadosNoLote,
    ) -> ResultadoValidacao:
        """Verifica campos, identidade e o par de tipos de origem e destino da aresta."""
        valor = ctx.item.value
        if not isinstance(valor, dict):
            return ResultadoValidacao.falha(
                "Valor da aresta deve ser um objeto JSON",
                "SchemaGate",
                modo=ModoFalhaMAST.ESTRUTURA_INCOMPLETA,
            )
        for campo in ("id", "origem_id", "destino_id", "tipo"):
            if campo not in valor:
                return ResultadoValidacao.falha(
                    f"Aresta sem campo obrigatório: '{campo}'",
                    "SchemaGate",
                    modo=ModoFalhaMAST.ESTRUTURA_INCOMPLETA,
                )
        resultado_identidade = validar_identidade(ctx, criados)
        if not resultado_identidade.aprovado:
            return resultado_identidade
        criados.arestas.add(ctx.segmentos[1])
        return self._validar_par_aresta(valor, ctx.estado, criados.nos)

    def _validar_par_aresta(
        self,
        valor: dict[str, Any],
        estado: GrafoEstado,
        nos_criados: dict[str, TipoNo],
    ) -> ResultadoValidacao:
        """Valida compatibilidade ontológica do par (Origem, Destino)."""
        try:
            tipo_aresta = TipoAresta(valor["tipo"])
        except ValueError:
            return ResultadoValidacao.falha(
                f"Tipo de aresta inválido: '{valor.get('tipo')}'",
                "SchemaGate",
                modo=ModoFalhaMAST.TIPO_DESCONHECIDO,
            )
        tipo_origem = self._obter_tipo_no(valor["origem_id"], estado, nos_criados)
        tipo_destino = self._obter_tipo_no(valor["destino_id"], estado, nos_criados)
        if tipo_origem is None or tipo_destino is None:
            return ResultadoValidacao.falha(
                f"Nó de origem ou destino inexistente para a aresta '{valor['id']}'",
                "SchemaGate",
                modo=ModoFalhaMAST.REFERENCIA_INEXISTENTE,
            )
        if TipoNo.GOVERNANCA in (tipo_origem, tipo_destino):
            return self._recusar_aresta_em_governanca(tipo_aresta)
        return self._validar_par_declarado(tipo_aresta, (tipo_origem, tipo_destino))

    def _recusar_aresta_em_governanca(self, tipo_aresta: TipoAresta) -> ResultadoValidacao:
        """O Governanca é raiz isolada: nenhuma aresta o toca, como origem ou destino."""
        return ResultadoValidacao.falha(
            f"Aresta '{tipo_aresta.value}' não pode tocar um nó 'Governanca', "
            "nem como origem nem como destino: ele é raiz isolada da política de governança",
            "SchemaGate",
            modo=ModoFalhaMAST.PAR_DE_ARESTA_INVALIDO,
        )

    def _validar_par_declarado(
        self,
        tipo_aresta: TipoAresta,
        par: tuple[TipoNo, TipoNo],
    ) -> ResultadoValidacao:
        """Consulta a tabela de pares admitidos para o tipo de aresta informado."""
        if par in self.PARES_ARESTAS_PERMITIDOS.get(tipo_aresta, frozenset()):
            return ResultadoValidacao.sucesso()
        return ResultadoValidacao.falha(
            f"Aresta '{tipo_aresta.value}' não permite conexão entre '{par[0].value}' e '{par[1].value}'",
            "SchemaGate",
            modo=ModoFalhaMAST.PAR_DE_ARESTA_INVALIDO,
        )

    def _obter_tipo_no(
        self,
        id_no: str,
        estado: GrafoEstado,
        nos_criados: dict[str, TipoNo],
    ) -> TipoNo | None:
        """Recupera tipo de nó do estado persistido ou da lista de criados no patch."""
        if id_no in nos_criados:
            return nos_criados[id_no]
        no = estado.nos.get(id_no)
        return no.tipo if no else None
