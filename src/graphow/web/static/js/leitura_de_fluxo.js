/**
 * Leitura do fluxo de trabalho a partir dos nós e arestas do canvas.
 *
 * O canvas desenha o grafo como ele é; o quadro e o painel de impacto precisam
 * de outra pergunta respondida: a que objetivo cada nó pertence, que tarefa ele
 * cerca, o que o afeta e o que ele afeta. Nada disso é gravado no grafo. É
 * derivado aqui, das arestas que já existem, e por isso este módulo não toca DOM
 * nem estado: recebe listas e devolve respostas, e roda igual no Node.
 */

// Task sem status gravado ainda não começou; Question sem status está aberta,
// que é como o kernel a cria e como o inspetor a lê.
const STATUS_PADRAO = { Task: "pendente", Question: "aberta" };

export const ORDEM_DAS_COLUNAS = ["pendente", "em_andamento", "pronto_para_revisao", "bloqueado", "concluido"];

export const ARESTAS_ESTRUTURAIS = new Set(["produz", "contem", "ocorreu_em"]);

// Nestes tipos quem está na origem depende de quem está no destino: o destino
// vem antes, a montante. Nos demais é o contrário — quem bloqueia, orienta,
// escopa, justifica ou decompõe age sobre o destino.
const MONTANTE_QUANDO_ORIGEM = new Set(["depende_de", "deriva_de", "ocorreu_em", "substitui"]);

/**
 * Onde cada tipo se pendura no trabalho, em ordem de preferência: a aresta e o
 * lado em que o nó está nela. A primeira que existir decide a âncora.
 */
const ANCORAS = {
  Task: [["decompoe", "destino"]],
  Question: [["bloqueia", "origem"]],
  Decision: [["orienta", "origem"]],
  Constraint: [["escopa", "origem"]],
  Artifact: [["deriva_de", "origem"]],
  Evidence: [["deriva_de", "origem"], ["justifica", "origem"], ["contradiz", "origem"]],
  Note: [["deriva_de", "origem"]],
};

const TIPOS_DE_ESTRUTURA = new Set(["Projeto", "Setor", "Sessao", "Run"]);

export function statusDe(no) {
  return no?.propriedades?.status || STATUS_PADRAO[no?.tipo] || null;
}

/** Lado da aresta em que o vizinho fica, visto do nó: "montante" ou "jusante". */
export function ladoDoVizinho(tipoDaAresta, noEstaNaOrigem) {
  return MONTANTE_QUANDO_ORIGEM.has(tipoDaAresta) === noEstaNaOrigem ? "montante" : "jusante";
}

const porCriacao = (a, b) => (a.seq_criacao ?? 0) - (b.seq_criacao ?? 0);

export function lerFluxo(nos, arestas) {
  const porId = new Map();
  for (const no of nos) porId.set(no.id, no);
  const saidas = new Map();
  const entradas = new Map();
  for (const aresta of arestas) {
    if (!porId.has(aresta.origem_id) || !porId.has(aresta.destino_id)) continue;
    if (!saidas.has(aresta.origem_id)) saidas.set(aresta.origem_id, []);
    if (!entradas.has(aresta.destino_id)) entradas.set(aresta.destino_id, []);
    saidas.get(aresta.origem_id).push(aresta);
    entradas.get(aresta.destino_id).push(aresta);
  }
  const saidasDe = (id) => saidas.get(id) || [];
  const entradasDe = (id) => entradas.get(id) || [];

  const ancoras = new Map();
  for (const no of nos) {
    for (const [tipo, lado] of ANCORAS[no.tipo] || []) {
      const aresta = (lado === "origem" ? saidasDe(no.id) : entradasDe(no.id)).find((candidata) => candidata.tipo === tipo);
      if (!aresta) continue;
      ancoras.set(no.id, lado === "origem" ? aresta.destino_id : aresta.origem_id);
      break;
    }
  }

  // Sobe pelas âncoras até achar o que se procura. Um ciclo de âncoras não
  // existe numa ontologia bem formada, mas um grafo em edição pode tê-lo por um
  // instante, e a tela não pode travar por isso.
  function subirAte(id, achou) {
    const visitados = new Set();
    let atual = id;
    while (atual && !visitados.has(atual)) {
      if (achou(porId.get(atual))) return atual;
      visitados.add(atual);
      atual = ancoras.get(atual);
    }
    return null;
  }

  const objetivoDe = (id) => subirAte(id, (no) => no?.tipo === "Goal");
  const tarefaDe = (id) => subirAte(id, (no) => no?.tipo === "Task");
  const status = (id) => statusDe(porId.get(id));

  const vizinhosPorAresta = (id, tipo, lado) =>
    (lado === "origem" ? saidasDe(id) : entradasDe(id)).filter((aresta) => aresta.tipo === tipo).map((aresta) => (lado === "origem" ? aresta.destino_id : aresta.origem_id));

  const dependeDe = (id) => vizinhosPorAresta(id, "depende_de", "origem");
  const liberaQuem = (id) => vizinhosPorAresta(id, "depende_de", "destino");
  const perguntasAbertas = (id) => vizinhosPorAresta(id, "bloqueia", "destino").filter((pergunta) => status(pergunta) === "aberta");

  /** Os nós que cercam a tarefa: tudo que se pendura nela sem ser outra tarefa. */
  function contextoDe(idTarefa) {
    return nos.filter((no) => no.tipo !== "Task" && no.id !== idTarefa && tarefaDe(no.id) === idTarefa).sort(porCriacao).map((no) => no.id);
  }

  /**
   * O que afeta o nó e o que ele afeta. As arestas de estrutura só contam para
   * contêineres e execuções, que não têm outra coisa; para o trabalho elas
   * repetiriam a sessão em todo nó.
   */
  function vizinhos(id, { estrutura = false } = {}) {
    const no = porId.get(id);
    const comEstrutura = estrutura || TIPOS_DE_ESTRUTURA.has(no?.tipo);
    const resultado = { montante: [], jusante: [] };
    const incluir = (aresta, noEstaNaOrigem) => {
      if (!comEstrutura && ARESTAS_ESTRUTURAIS.has(aresta.tipo)) return;
      const vizinho = noEstaNaOrigem ? aresta.destino_id : aresta.origem_id;
      resultado[ladoDoVizinho(aresta.tipo, noEstaNaOrigem)].push({ aresta, id: vizinho, direcao: noEstaNaOrigem ? "saida" : "entrada" });
    };
    saidasDe(id).forEach((aresta) => incluir(aresta, true));
    entradasDe(id).forEach((aresta) => incluir(aresta, false));
    return resultado;
  }

  /** Uma raia por objetivo com tarefa, na ordem de criação; as órfãs vão numa raia sem objetivo, no fim. */
  function raias() {
    const porObjetivo = new Map();
    for (const tarefa of nos.filter((no) => no.tipo === "Task").sort(porCriacao)) {
      const objetivo = objetivoDe(tarefa.id);
      if (!porObjetivo.has(objetivo)) porObjetivo.set(objetivo, []);
      porObjetivo.get(objetivo).push(tarefa.id);
    }
    const objetivos = nos.filter((no) => no.tipo === "Goal").sort(porCriacao).map((no) => no.id);
    const lista = objetivos.filter((id) => porObjetivo.has(id)).map((id) => ({ objetivo: id, tarefas: porObjetivo.get(id) }));
    if (porObjetivo.has(null)) lista.push({ objetivo: null, tarefas: porObjetivo.get(null) });
    return lista;
  }

  /** Grupos do minimapa: cada objetivo com tudo que sobe até ele, depois estrutura, memória e o que ficou solto. */
  function grupos() {
    const mapa = new Map();
    const colocar = (chave, no) => {
      if (!mapa.has(chave)) mapa.set(chave, []);
      mapa.get(chave).push(no);
    };
    for (const no of [...nos].sort(porCriacao)) {
      const objetivo = objetivoDe(no.id);
      if (objetivo) colocar(objetivo, no);
      else if (TIPOS_DE_ESTRUTURA.has(no.tipo)) colocar("estrutura", no);
      else if (no.tipo === "Aprendizado") colocar("memoria", no);
      else colocar("solto", no);
    }
    const objetivos = nos.filter((no) => no.tipo === "Goal").sort(porCriacao).map((no) => no.id);
    return [...objetivos, "solto", "estrutura", "memoria"]
      .filter((chave) => mapa.has(chave))
      .map((chave) => ({ chave, objetivo: porId.has(chave) ? chave : null, nos: mapa.get(chave).map((no) => no.id) }));
  }

  return { porId, status, objetivoDe, tarefaDe, dependeDe, liberaQuem, perguntasAbertas, contextoDe, vizinhos, raias, grupos };
}
