/**
 * Leitura estrutural do grafo para o arranjo automático.
 *
 * O arranjo trata as arestas por três papéis, não por tipo de nó:
 *
 * - árvore (`contem`): a espinha de navegação. O pai fica à esquerda e os
 *   filhos descem numa coluna ao lado dele, e o leque de arestas não cruza nada;
 * - pertença (`produz`, `ocorreu_em`): o pai é o título de um bloco e os nós que
 *   ele produziu se empacotam embaixo. Essas arestas ficam ocultas por padrão —
 *   quem mostra a pertença é a proximidade;
 * - trabalho (todo o resto): o fluxo causal, desenhado em camadas da esquerda
 *   para a direita.
 *
 * Um componente de trabalho que atravessa sessões não é partido entre elas:
 * mora inteiro no menor contêiner que abriga todos os seus nós. Assim nenhuma
 * aresta de trabalho visível precisa atravessar um bloco alheio.
 */

const ARESTAS_DE_ARVORE = new Set(["contem"]);
const ARESTAS_DE_PERTENCA = new Set(["produz"]);
// ocorreu_em aponta do filho (a Run) para o pai (a Sessao).
const ARESTAS_DE_PERTENCA_INVERTIDA = new Set(["ocorreu_em"]);
// Setas que apontam para trás no tempo: quem depende, deriva ou substitui vem
// depois, à direita daquilo de que depende.
const ARESTAS_CONTRA_O_FLUXO = new Set(["depende_de", "deriva_de", "substitui"]);

/**
 * Monta a leitura estrutural: quem é pai de quem, por qual papel, e as arestas
 * de trabalho já orientadas no sentido do fluxo.
 */
export function lerEstrutura(nodes, edges) {
  const ids = new Set(nodes.map((n) => n.id));
  const validas = edges.filter((e) => ids.has(e.origem_id) && ids.has(e.destino_id) && e.origem_id !== e.destino_id);
  const { pai, papel } = atribuirPais(validas);
  const filhos = agruparFilhos(pai);
  const trabalho = validas.filter((e) => !ehEstrutural(e.tipo)).map(orientar);
  return { pai, papel, filhos, trabalho };
}

function ehEstrutural(tipo) {
  return ARESTAS_DE_ARVORE.has(tipo) || ARESTAS_DE_PERTENCA.has(tipo) || ARESTAS_DE_PERTENCA_INVERTIDA.has(tipo);
}

function orientar(aresta) {
  const contra = ARESTAS_CONTRA_O_FLUXO.has(aresta.tipo);
  return { de: contra ? aresta.destino_id : aresta.origem_id, para: contra ? aresta.origem_id : aresta.destino_id };
}

/** O primeiro pai estrutural de cada nó vence; um pai que fecharia ciclo é recusado. */
function atribuirPais(arestas) {
  const pai = new Map();
  const papel = new Map();
  for (const aresta of arestas) {
    const vinculo = lerVinculo(aresta);
    if (!vinculo || pai.has(vinculo.filho) || ehAncestral(pai, vinculo.filho, vinculo.pai)) continue;
    pai.set(vinculo.filho, vinculo.pai);
    papel.set(vinculo.filho, vinculo.papel);
  }
  return { pai, papel };
}

function lerVinculo(aresta) {
  if (ARESTAS_DE_ARVORE.has(aresta.tipo)) return { pai: aresta.origem_id, filho: aresta.destino_id, papel: "arvore" };
  if (ARESTAS_DE_PERTENCA.has(aresta.tipo)) return { pai: aresta.origem_id, filho: aresta.destino_id, papel: "pertenca" };
  if (ARESTAS_DE_PERTENCA_INVERTIDA.has(aresta.tipo)) return { pai: aresta.destino_id, filho: aresta.origem_id, papel: "pertenca" };
  return null;
}

/** Diz se `talvez` é `id` ou está acima dele na cadeia de pais. */
function ehAncestral(pai, talvez, id) {
  for (let atual = id; atual !== undefined; atual = pai.get(atual)) {
    if (atual === talvez) return true;
  }
  return false;
}

function agruparFilhos(pai) {
  const filhos = new Map();
  for (const [filho, dono] of pai) {
    if (!filhos.has(dono)) filhos.set(dono, []);
    filhos.get(dono).push(filho);
  }
  return filhos;
}

/**
 * Distribui o conteúdo pelos contêineres. Conteúdo é todo nó sem filhos que
 * não pende da espinha; ele se junta em componentes pelas arestas de trabalho,
 * e cada componente vai para o menor contêiner que abriga os seus nós.
 * Devolve um Map de contêiner (null para a raiz) para uma lista de componentes.
 */
export function distribuirConteudo(estrutura, nodes) {
  const conteudo = nodes.filter((n) => !estrutura.filhos.has(n.id) && estrutura.papel.get(n.id) !== "arvore").map((n) => n.id);
  const porContainer = new Map();
  for (const componente of separarComponentes(conteudo, estrutura.trabalho)) {
    const dono = menorContainerComum(componente, estrutura.pai);
    if (!porContainer.has(dono)) porContainer.set(dono, []);
    porContainer.get(dono).push(componente);
  }
  return porContainer;
}

/** Componentes conexos entre os ids dados, por união e busca. */
function separarComponentes(ids, arestas) {
  const representante = new Map(ids.map((id) => [id, id]));
  const raiz = (id) => {
    while (representante.get(id) !== id) {
      representante.set(id, representante.get(representante.get(id)));
      id = representante.get(id);
    }
    return id;
  };
  for (const { de, para } of arestas) {
    if (representante.has(de) && representante.has(para)) representante.set(raiz(de), raiz(para));
  }
  const grupos = new Map();
  for (const id of ids) {
    const r = raiz(id);
    if (!grupos.has(r)) grupos.set(r, []);
    grupos.get(r).push(id);
  }
  return [...grupos.values()];
}

/**
 * O contêiner mais baixo que contém todos os pais do componente. Nós sem pai
 * não puxam o componente para a raiz: eles acompanham os que têm.
 */
function menorContainerComum(componente, pai) {
  const cadeias = componente.filter((id) => pai.has(id)).map((id) => cadeiaDeAncestrais(pai.get(id), pai));
  if (cadeias.length === 0) return null;
  let comum = cadeias[0];
  for (const cadeia of cadeias.slice(1)) {
    const conjunto = new Set(cadeia);
    comum = comum.filter((id) => conjunto.has(id));
  }
  return comum[0] ?? null;
}

/** O próprio id seguido dos seus ancestrais, do mais próximo ao mais distante. */
function cadeiaDeAncestrais(id, pai) {
  const cadeia = [];
  for (let atual = id; atual !== undefined; atual = pai.get(atual)) cadeia.push(atual);
  return cadeia;
}
