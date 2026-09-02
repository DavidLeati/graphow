"""Despacho e execução dos subcomandos da linha de comando do Graphow."""

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from graphow.api.cli import GraphowCLI, descrever_localizacao_banco
from graphow.api.console import EscritorConsole, EscritorConsolePadrao
from graphow.documentacao import MontadorDocumentacaoDoRepositorio
from graphow.documentacao.publicacao import DocumentoGerado
from graphow.documentacao.verificacao_guias import VerificadorDeGuias
from graphow.core.exceptions import GraphowError
from graphow.kernel.composicao import montar_kernel_sqlite
from graphow.kernel.write_kernel import WriteKernel
from graphow.observability.exportador_spans import TracerArquivoNDJSON
from graphow.observability.tracer import Tracer
from graphow.storage.localizador_banco import (
    LocalizacaoBanco,
    LocalizadorBancoEventos,
    PreparadorDiretorioBanco,
)
from graphow.storage.migrador_banco import AnalisadorMigracaoBanco, MigradorBancoEventos
from graphow.storage.reparo_sequencia import (
    AcessoSequenciasSQLite,
    AnalisadorSequencias,
    DiagnosticoRamo,
    ReparadorSequencias,
)
from graphow.storage.sqlite_store import SQLiteEventStore

CODIGO_SUCESSO: int = 0
CODIGO_FALHA_DOMINIO: int = 1

RAIZ_PROJETO: Path = Path(__file__).resolve().parents[3]
RAIZ_CODIGO_FONTE: Path = RAIZ_PROJETO / "src" / "graphow"
RAIZ_DOCUMENTACAO: Path = RAIZ_PROJETO / "docs"


@dataclass(frozen=True)
class ContextoExecucao:
    """Dependências resolvidas para a execução de um subcomando."""

    argumentos: argparse.Namespace
    localizacao_banco: LocalizacaoBanco
    console: EscritorConsole


class ExecutorLinhaDeComando:
    """Resolve dependências de infraestrutura e executa o subcomando solicitado."""

    def __init__(
        self,
        console: EscritorConsole | None = None,
        localizador: LocalizadorBancoEventos | None = None,
    ) -> None:
        self._console: EscritorConsole = console or EscritorConsolePadrao()
        self._localizador: LocalizadorBancoEventos = localizador or LocalizadorBancoEventos()
        self._preparador: PreparadorDiretorioBanco = PreparadorDiretorioBanco()

    def executar(self, argumentos: argparse.Namespace) -> int:
        """Executa o subcomando e devolve o código de saída do processo."""
        localizacao = self._localizador.resolver(getattr(argumentos, "db", None))
        contexto = ContextoExecucao(argumentos=argumentos, localizacao_banco=localizacao, console=self._console)
        try:
            return self._despachar(contexto)
        except GraphowError as erro:
            self._console.escrever_linha(erro.formatar_para_llm())
            return CODIGO_FALHA_DOMINIO

    def _despachar(self, contexto: ContextoExecucao) -> int:
        """Encaminha para o manipulador do subcomando, sem abrir banco à toa."""
        manipuladores_sem_banco: Mapping[str, Callable[[ContextoExecucao], int]] = {
            "banco-info": self._executar_banco_info,
            "migrar-banco": self._executar_migrar_banco,
            "reparar-sequencias": self._executar_reparar_sequencias,
            "docs-gerar": self._executar_docs_gerar,
            "avaliar": self._executar_avaliar,
        }
        manipulador = manipuladores_sem_banco.get(contexto.argumentos.comando)
        if manipulador is not None:
            return manipulador(contexto)
        return self._executar_com_banco_aberto(contexto)

    def _executar_banco_info(self, contexto: ContextoExecucao) -> int:
        """Exibe o caminho resolvido do banco e alerta sobre pastas sincronizadas."""
        for linha in descrever_localizacao_banco(contexto.localizacao_banco):
            contexto.console.escrever_linha(linha)
        return CODIGO_SUCESSO

    def _executar_migrar_banco(self, contexto: ContextoExecucao) -> int:
        """Copia um banco antigo para o diretório de dados, preservando a origem."""
        self._preparador.garantir_diretorio(contexto.localizacao_banco)
        origem = Path(contexto.argumentos.origem).expanduser()
        plano = AnalisadorMigracaoBanco().planejar(origem, contexto.localizacao_banco.caminho)
        if not plano.deve_migrar:
            contexto.console.escrever_linha(f"Migracao nao realizada: {plano.motivo}")
            return CODIGO_SUCESSO
        MigradorBancoEventos().executar(plano)
        contexto.console.escrever_linha(
            f"Migrados {plano.eventos_na_origem} eventos para {plano.caminho_destino}"
        )
        contexto.console.escrever_linha(f"A origem permanece intacta em {plano.caminho_origem}")
        return CODIGO_SUCESSO

    def _executar_reparar_sequencias(self, contexto: ContextoExecucao) -> int:
        """Deduplica e renumera o log, abrindo o arquivo fora do repositorio de eventos."""
        caminho = contexto.localizacao_banco.caminho
        acesso = AcessoSequenciasSQLite(caminho)
        diagnosticos = AnalisadorSequencias(acesso).diagnosticar_todos_os_ramos()
        for diagnostico in diagnosticos:
            self._relatar_e_reparar(diagnostico, acesso, contexto)
        return CODIGO_SUCESSO

    def _relatar_e_reparar(
        self,
        diagnostico: DiagnosticoRamo,
        acesso: AcessoSequenciasSQLite,
        contexto: ContextoExecucao,
    ) -> None:
        """Informa o estado do ramo e aplica o reparo apenas quando ele e necessario."""
        if not diagnostico.precisa_reparo:
            contexto.console.escrever_linha(
                f"Ramo '{diagnostico.ramo_id}': {diagnostico.total_eventos} eventos, sequencias integras"
            )
            return
        ReparadorSequencias(acesso).reparar(diagnostico)
        contexto.console.escrever_linha(
            f"Ramo '{diagnostico.ramo_id}': {diagnostico.posicoes_duplicadas} posicoes duplicadas, "
            f"{len(diagnostico.ids_a_remover)} copias removidas, "
            f"{diagnostico.posicoes_alteradas} eventos renumerados"
        )

    def _executar_avaliar(self, contexto: ContextoExecucao) -> int:
        """Mede o corpus gravado e imprime o relatorio com os proprios limites.

        A metrica numero um do plano nao era medida: o unico numero existente
        vinha de uma mensagem de commit sobre uma vista. Ver achado A-15.
        """
        from graphow.avaliacao import executar_avaliacao

        for linha in executar_avaliacao().formatar():
            contexto.console.escrever_linha(linha)
        return CODIGO_SUCESSO

    def _executar_docs_gerar(self, contexto: ContextoExecucao) -> int:
        """Regenera o indice e os dossies, ou apenas confere se estao em dia."""
        montador = MontadorDocumentacaoDoRepositorio(RAIZ_CODIGO_FONTE, RAIZ_DOCUMENTACAO)
        if contexto.argumentos.conferir:
            return self._conferir_documentacao(montador, contexto)
        resultado = montador.publicar()
        contexto.console.escrever_linha(
            f"{resultado.documentos_escritos} documentos gerados "
            f"({resultado.bytes_totais // 1024} KB) em {RAIZ_DOCUMENTACAO}"
        )
        for removido in resultado.documentos_removidos:
            contexto.console.escrever_linha(f"Removido (ala extinta): {removido}")
        return CODIGO_SUCESSO

    def _conferir_documentacao(
        self,
        montador: MontadorDocumentacaoDoRepositorio,
        contexto: ContextoExecucao,
    ) -> int:
        """Confere o catalogo gerado e os exemplos executaveis dos guias."""
        codigo_catalogo = self._conferir_catalogo(montador, contexto)
        codigo_guias = self._conferir_guias(contexto)
        if codigo_catalogo == CODIGO_SUCESSO and codigo_guias == CODIGO_SUCESSO:
            return CODIGO_SUCESSO
        return CODIGO_FALHA_DOMINIO

    def _conferir_catalogo(
        self,
        montador: MontadorDocumentacaoDoRepositorio,
        contexto: ContextoExecucao,
    ) -> int:
        """Compara o que esta em disco com o que o codigo produziria agora."""
        desatualizados = [
            documento.caminho_relativo
            for documento in montador.montar_documentos()
            if not self._documento_esta_em_dia(documento)
        ]
        if not desatualizados:
            contexto.console.escrever_linha("Catalogo em dia com o codigo.")
            return CODIGO_SUCESSO
        contexto.console.escrever_linha("Documentacao desatualizada. Rode 'graphow docs-gerar':")
        for caminho in desatualizados:
            contexto.console.escrever_linha(f"  {caminho}")
        return CODIGO_FALHA_DOMINIO

    def _conferir_guias(self, contexto: ContextoExecucao) -> int:
        """Passa cada exemplo de linha de comando dos guias pelo parser real.

        O gerador cobria apenas `docs/`. Os guias de `.agents/` apodreciam em
        silencio, e dois deles subiam o servidor MCP sem `--papel`. Ver A-14.
        """
        problemas = VerificadorDeGuias(RAIZ_PROJETO).verificar()
        if not problemas:
            contexto.console.escrever_linha("Exemplos de linha de comando dos guias validos.")
            return CODIGO_SUCESSO
        contexto.console.escrever_linha("Exemplos de linha de comando invalidos nos guias:")
        for problema in problemas:
            contexto.console.escrever_linha(f"  {problema.descrever()}")
        return CODIGO_FALHA_DOMINIO

    def _documento_esta_em_dia(self, documento: DocumentoGerado) -> bool:
        """Verifica se o arquivo em disco corresponde ao conteudo regenerado."""
        caminho = RAIZ_DOCUMENTACAO / documento.caminho_relativo
        if not caminho.is_file():
            return False
        return caminho.read_text(encoding="utf-8") == documento.conteudo

    def _executar_com_banco_aberto(self, contexto: ContextoExecucao) -> int:
        """Abre o repositório de eventos, executa o comando e garante o fechamento."""
        self._preparador.garantir_diretorio(contexto.localizacao_banco)
        self._avisar_sobre_pasta_sincronizada(contexto.localizacao_banco)
        tracer = self._montar_tracer(contexto.argumentos)
        with SQLiteEventStore(contexto.localizacao_banco.caminho_absoluto_texto) as repositorio:
            kernel = montar_kernel_sqlite(repositorio, tracer)
            return self._executar_subcomando_de_grafo(contexto, kernel)

    def _montar_tracer(self, argumentos: argparse.Namespace) -> Tracer | None:
        """Liga o exportador de spans quando o operador indica um arquivo."""
        caminho = getattr(argumentos, "spans", None)
        if not caminho:
            return None
        return TracerArquivoNDJSON(caminho)

    def _avisar_sobre_pasta_sincronizada(self, localizacao: LocalizacaoBanco) -> None:
        """Emite o alerta de risco quando o banco reside em pasta de nuvem."""
        if not localizacao.esta_em_pasta_sincronizada:
            return
        self._console.escrever_linha(
            "AVISO: o banco esta em pasta sincronizada por nuvem. Rode 'graphow banco-info'."
        )

    def _executar_subcomando_de_grafo(self, contexto: ContextoExecucao, kernel: WriteKernel) -> int:
        """Despacha os subcomandos que dependem de um kernel operacional."""
        from graphow.api.cli_execucao_grafo import DependenciasComandosGrafo, ManipuladorComandosGrafo

        dependencias = DependenciasComandosGrafo(
            cli=GraphowCLI(kernel, contexto.console),
            kernel=kernel,
            console=contexto.console,
        )
        return ManipuladorComandosGrafo(dependencias).executar(contexto.argumentos, contexto.localizacao_banco)
