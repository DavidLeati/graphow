/**
 * Como a interface apresenta a ontologia: nome legível, ícone e cor de cada tipo.
 *
 * O que o kernel aceita — pares de aresta e vocabulário de status — não mora
 * aqui: vem de `/api/ontologia`, lido da mesma tabela que o `SchemaGate` aplica.
 * Este arquivo só guarda o que é apresentação, e por isso pode divergir sem
 * quebrar nada além da aparência.
 */

export const TIPOS_CONTEINER = ["Projeto", "Setor", "Sessao"];

// Ordem de leitura dentro de uma sessão: intenção, trabalho, bloqueio, decisão, prova.
export const ORDEM_DE_TRABALHO = ["Goal", "Task", "Question", "Decision", "Constraint", "Evidence", "Artifact", "Run", "Note"];

const APRESENTACAO_DOS_TIPOS = {
  Projeto: { nome: "Projeto", plural: "Projetos", icone: "briefcase", descricao: "Raiz macro da iniciativa" },
  Setor: { nome: "Setor", plural: "Setores", icone: "folder", descricao: "Domínio ou subsistema técnico" },
  Sessao: { nome: "Sessão", plural: "Sessões", icone: "folder-clock", descricao: "Janela de contexto temporal" },
  Goal: { nome: "Goal", plural: "Goals", icone: "target", descricao: "Intenção ou objetivo de alto nível" },
  Task: { nome: "Task", plural: "Tasks", icone: "square-check", descricao: "Unidade atômica de trabalho" },
  Decision: { nome: "Decision", plural: "Decisions", icone: "scale", descricao: "Decisão arquitetural ou técnica" },
  Question: { nome: "Question", plural: "Questions", icone: "help-circle", descricao: "Dúvida que bloqueia uma tarefa" },
  Constraint: { nome: "Constraint", plural: "Constraints", icone: "shield", descricao: "Restrição inviolável" },
  Artifact: { nome: "Artifact", plural: "Artifacts", icone: "package", descricao: "Entregável concreto" },
  Evidence: { nome: "Evidence", plural: "Evidences", icone: "flask", descricao: "Dado empírico que justifica decisões" },
  Run: { nome: "Run", plural: "Runs", icone: "activity", descricao: "Execução e telemetria de um agente" },
  Note: { nome: "Note", plural: "Notes", icone: "sticky-note", descricao: "Anotação livre ou aviso reativo" },
};

export function apresentarTipo(tipo) {
  return APRESENTACAO_DOS_TIPOS[tipo] || { nome: tipo || "?", plural: tipo || "?", icone: "circle", descricao: "" };
}

/** Cor do tipo como referência às variáveis do tema, que o canvas também usa. */
export function corDoTipo(tipo) {
  return `var(--color-${String(tipo || "note").toLowerCase()}, var(--color-note))`;
}

export function ehConteiner(tipo) {
  return TIPOS_CONTEINER.includes(tipo);
}

// Leitura em duas direções: quem está na origem "decompõe"; quem está no destino "é decomposto por".
const LEITURA_DAS_ARESTAS = {
  contem: { saida: "contém", entrada: "contido em", descricao: "Hierarquia estrutural de navegação" },
  produz: { saida: "produz", entrada: "produzido por", descricao: "Item de trabalho criado no escopo da sessão" },
  ocorreu_em: { saida: "ocorreu em", entrada: "palco de", descricao: "Execução agêntica associada à sessão" },
  decompoe: { saida: "decompõe", entrada: "decomposto de", descricao: "Decomposição hierárquica de tarefas" },
  depende_de: { saida: "depende de", entrada: "pré-requisito de", descricao: "Pré-requisito de execução (DAG estrito)" },
  bloqueia: { saida: "bloqueia", entrada: "bloqueado por", descricao: "Impede a conclusão até resolução humana" },
  justifica: { saida: "justifica", entrada: "justificado por", descricao: "Fundamentação empírica de decisões" },
  contradiz: { saida: "contradiz", entrada: "contradito por", descricao: "Registro de evidência conflitante" },
  substitui: { saida: "substitui", entrada: "substituído por", descricao: "Evolução e invalidação histórica" },
  escopa: { saida: "escopa", entrada: "escopado por", descricao: "Restrição mandatória sobre a execução" },
  deriva_de: { saida: "deriva de", entrada: "origem de", descricao: "Proveniência de artefatos e notas" },
};

export function lerAresta(tipo) {
  return LEITURA_DAS_ARESTAS[tipo] || { saida: tipo, entrada: tipo, descricao: "" };
}

export function corDaAresta(tipo) {
  return `var(--edge-${tipo}, var(--edge-default))`;
}

// Classe visual de cada status: o que está feito, o que anda, o que para e o que espera.
const TOM_DOS_STATUS = {
  concluido: "ok",
  respondida: "ok",
  adotada: "ok",
  concluida: "ok",
  em_andamento: "andamento",
  pronto_para_revisao: "andamento",
  iniciada: "andamento",
  ativa: "andamento",
  bloqueado: "alerta",
  refutada: "alerta",
  falha: "alerta",
  aberta: "espera",
  pendente: "espera",
  solicitada: "espera",
  descartada: "neutro",
};

export function tomDoStatus(status) {
  return TOM_DOS_STATUS[status] || "neutro";
}

export function apresentarStatus(status) {
  return String(status || "").replace(/_/g, " ");
}

/**
 * Vocabulário que o kernel aplica, preenchido por `/api/ontologia` na partida.
 * Os valores iniciais só existem para a tela funcionar se essa leitura falhar.
 */
const vocabulario = {
  tiposNo: [...TIPOS_CONTEINER, ...ORDEM_DE_TRABALHO],
  arestas: {},
  status: {
    Task: ["pendente", "em_andamento", "pronto_para_revisao", "concluido", "bloqueado"],
    Question: ["aberta", "respondida", "descartada"],
    Sessao: ["ativa", "concluida"],
  },
  niveisAutonomia: ["estrito", "ilimitado"],
};

export function definirVocabulario(publicado) {
  if (!publicado || !publicado.arestas) return;
  vocabulario.tiposNo = publicado.tipos_no || vocabulario.tiposNo;
  vocabulario.arestas = publicado.arestas;
  vocabulario.status = publicado.status || vocabulario.status;
  vocabulario.niveisAutonomia = publicado.niveis_autonomia || vocabulario.niveisAutonomia;
}

export function tiposDeAresta() {
  const conhecidos = Object.keys(vocabulario.arestas);
  return conhecidos.length ? conhecidos : Object.keys(LEITURA_DAS_ARESTAS);
}

/** Tipos de aresta que o portão aceita entre os dois tipos de nó, na ordem da ontologia. */
export function arestasPermitidas(tipoOrigem, tipoDestino) {
  return tiposDeAresta().filter((tipo) =>
    (vocabulario.arestas[tipo] || []).some(([origem, destino]) => origem === tipoOrigem && destino === tipoDestino)
  );
}

export function statusDoTipo(tipo) {
  return vocabulario.status[tipo] || null;
}

export function niveisDeAutonomia() {
  return vocabulario.niveisAutonomia;
}

export function tiposDeTrabalho() {
  return vocabulario.tiposNo.filter((tipo) => !ehConteiner(tipo));
}
