"""Definições de enumerações e tipos de valor base para a ontologia do Graphow."""

from enum import Enum


class TipoNo(str, Enum):
    """Tipos de nós suportados pela ontologia de duas camadas."""

    # Camada de Navegação
    PROJETO = "Projeto"
    SETOR = "Setor"
    SESSAO = "Sessao"

    # Camada de Trabalho
    GOAL = "Goal"
    TASK = "Task"
    DECISION = "Decision"
    QUESTION = "Question"
    CONSTRAINT = "Constraint"
    ARTIFACT = "Artifact"
    EVIDENCE = "Evidence"
    RUN = "Run"
    NOTE = "Note"


class TipoAresta(str, Enum):
    """Tipos de arestas tipadas da ontologia."""

    CONTEM = "contem"
    PRODUZ = "produz"
    OCORREU_EM = "ocorreu_em"
    DECOMPOE = "decompoe"
    DEPENDE_DE = "depende_de"
    BLOQUEIA = "bloqueia"
    JUSTIFICA = "justifica"
    CONTRADIZ = "contradiz"
    SUBSTITUI = "substitui"
    ESCOPA = "escopa"
    DERIVA_DE = "deriva_de"


class PapelAutor(str, Enum):
    """Papéis de autoria com contratos específicos de permissão de escrita."""

    HUMANO = "humano"
    PLANEJADOR = "planejador"
    EXECUTOR = "executor"
    REVISOR = "revisor"
    SISTEMA = "sistema"


class OrigemEvento(str, Enum):
    """Origem do disparo de mutações no log."""

    HUMANO = "humano"
    HARNESS = "harness"
    COMPORTAMENTO = "comportamento"


class StatusTask(str, Enum):
    """Estados do ciclo de vida de um nó Task."""

    PENDENTE = "pendente"
    EM_ANDAMENTO = "em_andamento"
    PRONTO_PARA_REVISAO = "pronto_para_revisao"
    CONCLUIDO = "concluido"
    BLOQUEADO = "bloqueado"


class StatusQuestion(str, Enum):
    """Estados de resolução de uma dúvida/questão."""

    ABERTA = "aberta"
    RESPONDIDA = "respondida"
    DESCARTADA = "descartada"


class StatusExecucao(str, Enum):
    """Estados do ciclo de vida de execução de um agente (Run)."""

    SOLICITADA = "solicitada"
    INICIADA = "iniciada"
    CONCLUIDA = "concluida"
    FALHA = "falha"


class NivelAutonomiaProjeto(str, Enum):
    """Níveis de permissividade e autonomia concedidos a agentes no escopo do projeto."""

    ESTRITO = "estrito"
    ILIMITADO = "ilimitado"

