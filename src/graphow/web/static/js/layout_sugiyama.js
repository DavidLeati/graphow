/**
 * Camadas e ordem de um componente de trabalho, no método de Sugiyama.
 *
 * 1. Ciclos são quebrados invertendo as arestas de retorno de uma busca em
 *    profundidade — o fluxo precisa de um sentido para virar colunas.
 * 2. Cada nó ganha a camada do maior caminho até ele; depois fontes e
 *    sorvedouros escorregam para perto dos vizinhos, encurtando as arestas.
 * 3. Arestas que pulam camadas ganham vértices intermediários, que reservam o
 *    corredor por onde a curva vai passar.
 * 4. A ordem dentro de cada camada alterna varreduras pelo baricentro dos
 *    vizinhos com trocas entre adjacentes, guardando a melhor ordem vista.
 *
 * Tudo é determinístico: o mesmo grafo produz sempre o mesmo arranjo.
 */

const MAXIMO_DE_VARREDURAS = 24;
const VARREDURAS_SEM_MELHORA = 6;
const PASSADAS_DE_EQUILIBRIO = 12;
// Quanto uma aresta que atravessa uma camada custa em altura, na conta de
// quando parar de abrir colunas. Bem menos que um cartão, mas não zero.
const CUSTO_DO_CORREDOR = 44;

/**
 * Organiza os ids em camadas. Em `opcoes`: `comparar` dá a ordem de leitura que
 * desempata, `alturaDe` mede cada cartão e `orcamentoDeAltura` limita o quanto
 * uma camada pode crescer antes de transbordar para outra coluna.
 * Devolve { vertices, camadas, cadeias, vizinhosReais }: vértices reais têm
 * `id`; os intermediários têm `id` nulo. Cada cadeia vai de um vértice real a
 * outro passando pelos intermediários da mesma aresta.
 */
export function organizarEmCamadas(ids, arestas, opcoes) {
  const ordenados = [...ids].sort(opcoes.comparar);
  const indice = new Map(ordenados.map((id, i) => [id, i]));
  const pares = quebrarCiclos(ordenados.length, paresUnicos(arestas, indice));
  const camada = atribuirCamadas(ordenados.length, pares);
  desafogarCamadas(camada, listasDeAdjacencia(ordenados.length, pares), {
    alturaDe: (v) => opcoes.alturaDe(ordenados[v]),
    orcamento: opcoes.orcamentoDeAltura,
  });
  const grafo = inserirIntermediarios(ordenados, pares, camada);
  ordenarCamadas(grafo);
  return grafo;
}

function paresUnicos(arestas, indice) {
  const pares = arestas.map(({ de, para }) => [indice.get(de), indice.get(para)]);
  return semRepetidos(pares.filter(([a, b]) => a !== undefined && b !== undefined && a !== b));
}

/** Arestas paralelas contam uma vez só: para o arranjo, basta saber que há ligação. */
function semRepetidos(pares) {
  const vistos = new Set();
  return pares.filter(([a, b]) => {
    const chave = `${a}>${b}`;
    if (vistos.has(chave)) return false;
    vistos.add(chave);
    return true;
  });
}

function listasDeAdjacencia(total, pares) {
  const saidas = Array.from({ length: total }, () => []);
  const entradas = Array.from({ length: total }, () => []);
  for (const [a, b] of pares) {
    saidas[a].push(b);
    entradas[b].push(a);
  }
  return { saidas, entradas };
}

/** Busca em profundidade iterativa; a aresta que volta para a pilha é invertida. */
function quebrarCiclos(total, pares) {
  const { saidas } = listasDeAdjacencia(total, pares);
  const estado = new Uint8Array(total);
  const retorno = new Set();
  for (let raiz = 0; raiz < total; raiz++) {
    if (estado[raiz]) continue;
    const pilha = [[raiz, 0]];
    estado[raiz] = 1;
    while (pilha.length) {
      const topo = pilha[pilha.length - 1];
      const proximo = saidas[topo[0]][topo[1]++];
      if (proximo === undefined) {
        estado[topo[0]] = 2;
        pilha.pop();
      } else if (estado[proximo] === 1) retorno.add(`${topo[0]}>${proximo}`);
      else if (estado[proximo] === 0) {
        estado[proximo] = 1;
        pilha.push([proximo, 0]);
      }
    }
  }
  // Um ciclo de duas arestas vira duas arestas no mesmo sentido; fica uma.
  return semRepetidos(pares.map(([a, b]) => (retorno.has(`${a}>${b}`) ? [b, a] : [a, b])));
}

/** Maior caminho a partir das fontes, seguido do equilíbrio de fontes e sorvedouros. */
function atribuirCamadas(total, pares) {
  const { saidas, entradas } = listasDeAdjacencia(total, pares);
  const ordem = ordemTopologica(total, saidas, entradas);
  const camada = new Array(total).fill(0);
  for (const v of ordem) {
    for (const p of entradas[v]) camada[v] = Math.max(camada[v], camada[p] + 1);
  }
  equilibrarCamadas(ordem, { saidas, entradas }, camada);
  const menor = Math.min(...camada);
  return camada.map((c) => c - menor);
}

function ordemTopologica(total, saidas, entradas) {
  const pendentes = entradas.map((lista) => lista.length);
  const fila = [];
  for (let v = 0; v < total; v++) if (pendentes[v] === 0) fila.push(v);
  for (let i = 0; i < fila.length; i++) {
    for (const s of saidas[fila[i]]) if (--pendentes[s] === 0) fila.push(s);
  }
  return fila;
}

/**
 * Leva cada nó para a ponta do seu intervalo livre onde há mais arestas: quem
 * tem mais saídas que entradas encosta nos sucessores, e o contrário encosta
 * nos predecessores. É o que tira uma evidência solta da coluna zero e a põe
 * colada na decisão que ela justifica.
 */
function equilibrarCamadas(ordem, { saidas, entradas }, camada) {
  for (let passada = 0; passada < PASSADAS_DE_EQUILIBRIO; passada++) {
    let mudou = false;
    for (const v of ordem) {
      const alvo = camadaPreferida(v, { saidas, entradas }, camada);
      if (alvo === camada[v]) continue;
      camada[v] = alvo;
      mudou = true;
    }
    if (!mudou) return;
  }
}

function camadaPreferida(v, { saidas, entradas }, camada) {
  const puxaParaDireita = saidas[v].length > entradas[v].length;
  const puxaParaEsquerda = entradas[v].length > saidas[v].length;
  if (puxaParaDireita) return Math.min(...saidas[v].map((s) => camada[s])) - 1;
  if (puxaParaEsquerda) return Math.max(...entradas[v].map((p) => camada[p])) + 1;
  return camada[v];
}

/**
 * Uma camada cheia demais vira uma coluna alta demais: vinte evidências
 * justificando a mesma decisão empilham quatro metros de cartão, e o bloco
 * inteiro fica com a forma de uma fita. Quem não tem predecessor pode recuar
 * uma coluna, e quem não tem sucessor pode avançar uma, sem inverter o sentido
 * do fluxo: a estrela se abre em duas ou três colunas. A aresta passa a pular
 * camadas, e o corredor que ela abre no meio custa bem menos que um cartão —
 * mas custa, e por isso entra na conta que decide parar.
 */
function desafogarCamadas(camada, adjacencia, { alturaDe, orcamento }) {
  const desistidas = new Set();
  for (let rodada = 0; rodada < 60; rodada++) {
    const cargas = calcularCargas(camada, adjacencia, alturaDe);
    const alvo = maisCarregada(cargas, orcamento, desistidas);
    if (alvo === null) break;
    const pedido = { alvo, excedente: cargas.get(alvo) - orcamento, alturaDe };
    if (!aliviar(pedido, camada, adjacencia)) desistidas.add(alvo);
  }
  const menor = Math.min(...camada);
  camada.forEach((c, v) => { camada[v] = c - menor; });
}

/** A altura que cada camada já pede: os cartões dela mais os corredores que a atravessam. */
function calcularCargas(camada, { saidas }, alturaDe) {
  const cargas = new Map();
  const somar = (c, quanto) => cargas.set(c, (cargas.get(c) ?? 0) + quanto);
  camada.forEach((c, v) => {
    somar(c, alturaDe(v));
    for (const s of saidas[v]) {
      for (let meio = c + 1; meio < camada[s]; meio++) somar(meio, CUSTO_DO_CORREDOR);
    }
  });
  return cargas;
}

function maisCarregada(cargas, orcamento, desistidas) {
  let alvo = null;
  let maior = orcamento;
  for (const [c, carga] of cargas) {
    if (desistidas.has(c) || carga <= maior) continue;
    maior = carga;
    alvo = c;
  }
  return alvo;
}

/** Empurra para a coluna vizinha o excedente da camada, começando por quem tem menos ligações. */
function aliviar({ alvo, excedente, alturaDe }, camada, { saidas, entradas }) {
  const grau = (v) => entradas[v].length + saidas[v].length;
  const moveis = [];
  camada.forEach((c, v) => {
    if (c === alvo && (entradas[v].length === 0) !== (saidas[v].length === 0)) moveis.push(v);
  });
  moveis.sort((a, b) => grau(a) - grau(b) || a - b);
  let sobra = excedente;
  let moveu = false;
  for (const v of moveis.slice(0, Math.max(0, moveis.length - 1))) {
    if (sobra <= 0) break;
    camada[v] += entradas[v].length === 0 ? -1 : 1;
    // O que a camada ganha: o cartão sai, mas a aresta dele passa a atravessá-la.
    sobra -= alturaDe(v) - CUSTO_DO_CORREDOR;
    moveu = true;
  }
  return moveu;
}

/** Substitui cada aresta longa por uma cadeia que passa por todas as camadas do meio. */
function inserirIntermediarios(ids, pares, camada) {
  const vertices = ids.map((id, i) => ({ id, camada: camada[i], antes: [], depois: [] }));
  const vizinhosReais = ids.map(() => []);
  const cadeias = [];
  for (const [a, b] of pares) {
    const cadeia = [a];
    for (let c = camada[a] + 1; c < camada[b]; c++) {
      vertices.push({ id: null, camada: c, antes: [], depois: [] });
      cadeia.push(vertices.length - 1);
    }
    cadeia.push(b);
    for (let k = 1; k < cadeia.length; k++) ligar(vertices, cadeia[k - 1], cadeia[k]);
    vizinhosReais[a].push(b);
    vizinhosReais[b].push(a);
    cadeias.push(cadeia);
  }
  const camadas = Array.from({ length: Math.max(...camada) + 1 }, () => []);
  return { vertices, camadas, cadeias, vizinhosReais };
}

function ligar(vertices, de, para) {
  vertices[de].depois.push(para);
  vertices[para].antes.push(de);
}

/** Ordem inicial por profundidade, depois varreduras até parar de melhorar. */
function ordenarCamadas(grafo) {
  ordemInicial(grafo);
  const posicao = new Int32Array(grafo.vertices.length);
  grafo.camadas.forEach((c) => c.forEach((v, i) => { posicao[v] = i; }));
  let melhor = { camadas: grafo.camadas.map((c) => [...c]), cruzamentos: contarCruzamentos(grafo, posicao) };
  let semMelhora = 0;
  for (let varredura = 0; varredura < MAXIMO_DE_VARREDURAS && melhor.cruzamentos > 0; varredura++) {
    varrer(grafo, posicao, varredura % 2 === 0);
    transpor(grafo, posicao);
    const cruzamentos = contarCruzamentos(grafo, posicao);
    if (cruzamentos < melhor.cruzamentos) {
      melhor = { camadas: grafo.camadas.map((c) => [...c]), cruzamentos };
      semMelhora = 0;
    } else if (++semMelhora >= VARREDURAS_SEM_MELHORA) break;
  }
  grafo.camadas = melhor.camadas;
}

/** Visita em profundidade pelos sucessores, a partir das fontes em ordem de leitura. */
function ordemInicial(grafo) {
  const visitado = new Uint8Array(grafo.vertices.length);
  const visitar = (inicio) => {
    const pilha = [inicio];
    while (pilha.length) {
      const v = pilha.pop();
      if (visitado[v]) continue;
      visitado[v] = 1;
      grafo.camadas[grafo.vertices[v].camada].push(v);
      for (let k = grafo.vertices[v].depois.length - 1; k >= 0; k--) pilha.push(grafo.vertices[v].depois[k]);
    }
  };
  const fontes = grafo.vertices.map((_, v) => v).filter((v) => grafo.vertices[v].antes.length === 0);
  fontes.sort((a, b) => grafo.vertices[a].camada - grafo.vertices[b].camada || a - b);
  fontes.forEach(visitar);
  grafo.vertices.forEach((_, v) => visitar(v));
}

/** Uma varredura: cada camada se reordena pelo baricentro da camada vizinha já fixada. */
function varrer(grafo, posicao, paraDireita) {
  const { camadas, vertices } = grafo;
  const indices = camadas.map((_, i) => i);
  if (!paraDireita) indices.reverse();
  for (const i of indices.slice(1)) {
    const vizinhos = (v) => (paraDireita ? vertices[v].antes : vertices[v].depois);
    camadas[i] = reordenarPorBaricentro(camadas[i], vizinhos, posicao);
    camadas[i].forEach((v, k) => { posicao[v] = k; });
  }
}

/** Quem não tem vizinho na camada fixada fica onde está; os demais se ordenam em volta. */
function reordenarPorBaricentro(camada, vizinhos, posicao) {
  const moveis = [];
  const fixos = camada.map((v) => {
    const lista = vizinhos(v);
    if (lista.length === 0) return v;
    moveis.push({ v, baricentro: lista.reduce((soma, w) => soma + posicao[w], 0) / lista.length });
    return null;
  });
  moveis.sort((a, b) => a.baricentro - b.baricentro);
  let proximo = 0;
  return fixos.map((v) => (v === null ? moveis[proximo++].v : v));
}

/** Troca vizinhos adjacentes enquanto a troca diminuir os cruzamentos locais. */
function transpor(grafo, posicao) {
  const { camadas, vertices } = grafo;
  for (let passada = 0, melhorou = true; passada < 4 && melhorou; passada++) {
    melhorou = false;
    for (const camada of camadas) {
      for (let k = 0; k + 1 < camada.length; k++) {
        const [u, v] = [camada[k], camada[k + 1]];
        if (cruzamentosDoPar(vertices, [v, u], posicao) >= cruzamentosDoPar(vertices, [u, v], posicao)) continue;
        [camada[k], camada[k + 1], posicao[u], posicao[v]] = [v, u, k + 1, k];
        melhorou = true;
      }
    }
  }
}

/** Cruzamentos entre as arestas de `u` e as de `v` quando `u` vem antes de `v`. */
function cruzamentosDoPar(vertices, [u, v], posicao) {
  let total = 0;
  for (const lado of ["antes", "depois"]) {
    for (const a of vertices[u][lado]) {
      for (const b of vertices[v][lado]) if (posicao[a] > posicao[b]) total++;
    }
  }
  return total;
}

/** Cruzamentos de todas as camadas, contando inversões com uma árvore de Fenwick. */
export function contarCruzamentos(grafo, posicao) {
  let total = 0;
  for (let i = 0; i + 1 < grafo.camadas.length; i++) {
    const ligacoes = [];
    for (const u of grafo.camadas[i]) {
      for (const w of grafo.vertices[u].depois) ligacoes.push([posicao[u], posicao[w]]);
    }
    ligacoes.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    total += contarInversoes(ligacoes.map((l) => l[1]), grafo.camadas[i + 1].length);
  }
  return total;
}

function contarInversoes(sequencia, tamanho) {
  const arvore = new Int32Array(tamanho + 1);
  let inversoes = 0;
  sequencia.forEach((valor, lidos) => {
    let menoresOuIguais = 0;
    for (let i = valor + 1; i > 0; i -= i & -i) menoresOuIguais += arvore[i];
    inversoes += lidos - menoresOuIguais;
    for (let i = valor + 1; i <= tamanho; i += i & -i) arvore[i]++;
  });
  return inversoes;
}
