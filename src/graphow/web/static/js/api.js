/**
 * Camada de acesso à API REST do servidor.
 *
 * Cada painel chamava `fetch` do seu jeito, e metade deles tratava a falha de rede
 * como exceção solta no console. Aqui toda chamada devolve um objeto: o corpo da
 * resposta quando ele existe, ou `{ sucesso: false, mensagem }` quando nem isso
 * chegou. Quem chama só precisa olhar `sucesso`.
 */

async function pedir(url, opcoes = {}) {
  try {
    const resposta = await fetch(url, await opcoes);
    const corpo = await resposta.json().catch(() => ({}));
    if (!resposta.ok && corpo.sucesso === undefined) {
      return { ...corpo, sucesso: false, mensagem: corpo.mensagem || corpo.erro || `HTTP ${resposta.status}` };
    }
    return corpo;
  } catch (erro) {
    return { sucesso: false, mensagem: `Sem conexão com o servidor: ${erro.message}` };
  }
}

/**
 * O servidor escreve como o humano e só aceita escrita com o token desta sessão:
 * sem ele, qualquer site aberto no navegador escreveria no grafo. O token vem de
 * `/api/identity`, que só a própria página consegue ler, uma vez por carga.
 */
let tokenDaSessao = null;

function obterToken() {
  tokenDaSessao ??= fetch("/api/identity")
    .then((resposta) => resposta.json())
    .then((corpo) => corpo.token || "")
    .catch(() => "");
  return tokenDaSessao;
}

async function comCorpo(metodo, corpo) {
  return {
    method: metodo,
    headers: { "Content-Type": "application/json", "X-Graphow-Token": await obterToken() },
    body: JSON.stringify(corpo),
  };
}

/** Monta a query sem os parâmetros vazios: vazio faria o servidor decidir por omissão. */
export function montarQuery(parametros) {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(parametros)) {
    if (valor === null || valor === undefined || valor === "") continue;
    busca.set(chave, String(valor));
  }
  return busca.toString();
}

export const api = {
  identidade: () => pedir("/api/identity"),
  ramos: () => pedir("/api/branches"),
  ontologia: () => pedir("/api/ontologia"),
  canvas: (query) => pedir(`/api/canvas?${query}`),
  // A camada de navegação inteira cabe em poucos KB: é ela que alimenta o explorador.
  navegacao: (ramo) => pedir(`/api/canvas?${montarQuery({ ramo, colapsar: "sessao" })}`),
  sessao: (ramo, sessao) => pedir(`/api/canvas?${montarQuery({ ramo, sessao })}`),
  expandir: (id, ramo) => pedir(`/api/simulation/expand?${montarQuery({ id, ramo })}`),
  linhagem: (id, ramo) => pedir(`/api/lineage?${montarQuery({ id, ramo })}`),
  simular: (corpo) => pedir("/api/simulation/view", comCorpo("POST", corpo)),
  timeline: (ramo, papel) => pedir(`/api/timeline?${montarQuery({ ramo, papel })}`),
  estadoNaVersao: (versao, ramo) => pedir(`/api/timeline/state?${montarQuery({ versao, ramo })}`),
  buscar: ({ termo, tipos = [], limite = 20, ramo }) =>
    pedir(`/api/busca?${montarQuery({ termo, tipos: tipos.join(","), limite, ramo })}`),
  criarNo: (corpo) => pedir("/api/nodes", comCorpo("POST", corpo)),
  editarNo: (corpo) => pedir("/api/nodes", comCorpo("PUT", corpo)),
  criarAresta: (corpo) => pedir("/api/edges", comCorpo("POST", corpo)),
  remover: (corpo) => pedir("/api/elements", comCorpo("DELETE", corpo)),
  removerLote: (corpo) => pedir("/api/elements/batch", comCorpo("DELETE", corpo)),
  removerProjeto: (corpo) => pedir("/api/projects", comCorpo("DELETE", corpo)),
  criarFork: (corpo) => pedir("/api/forks", comCorpo("POST", corpo)),
  diff: (ramoA, ramoB) => pedir(`/api/diff?${montarQuery({ ramo_a: ramoA, ramo_b: ramoB })}`),
  // A memória do ramo inteiro: aprendizados com origem e alcance, sessões com fechamento.
  memoria: (ramo) => pedir(`/api/memoria?${montarQuery({ ramo })}`),
  registrarAprendizado: (corpo) => pedir("/api/memoria/aprendizados", comCorpo("POST", corpo)),
  promoverAprendizado: (corpo) => pedir("/api/memoria/promocoes", comCorpo("POST", corpo)),
  // Gesto humano: devolve a posse de qualquer dono, para a tarefa que o subagente deixou travada.
  liberarPosse: (id, ramo) => pedir(`/api/tarefas/${encodeURIComponent(id)}/liberar-posse`, comCorpo("POST", { ramo_id: ramo })),
  salvarLayout: (corpo) => pedir("/api/layout", comCorpo("PUT", corpo)),
  // Governança: o catálogo e a política global, a do projeto, o que o árbitro fez e a escrita (sempre humana).
  governanca: (ramo) => pedir(`/api/governanca?${montarQuery({ ramo })}`),
  governancaDoProjeto: (id, ramo) => pedir(`/api/projetos/${encodeURIComponent(id)}/governanca?${montarQuery({ ramo })}`),
  auditoriaDoArbitro: (ramo, limite) => pedir(`/api/governanca/auditoria?${montarQuery({ ramo, limite })}`),
  gravarGovernancaGlobal: (corpo) => pedir("/api/governanca/global", comCorpo("PUT", corpo)),
  gravarGovernancaDoProjeto: (id, corpo) => pedir(`/api/projetos/${encodeURIComponent(id)}/governanca`, comCorpo("PUT", corpo)),
};
