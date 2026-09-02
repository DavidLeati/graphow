/**
 * Sugiyama Layered Layout with 2-Way Barycentric Sweeps & Edge Crossing Minimization
 *
 * Algoritmo com minimização matemática de cruzamentos de arestas:
 * 1. Atribuição de Camadas Topológicas (DAG Layering) respeitando a direção causal.
 * 2. Varreduras bidirecionais (Forward/Backward Barycentric Sweeps) para alinhar nós vizinhos.
 * 3. Otimização combinatória por permutações adjacentes para eliminar cruzamentos residuais.
 * 4. Alinhamento vertical contínuo: nós com poucas conexões alinham-se na mesma altura do alvo.
 * 5. Resolução física AABB para garantir espaçamento mínimo e zero sobreposição de cartões.
 */

export const LARGURA_CARD = 220;
export const ALTURA_CARD = 75;
export const PASSO_COLUNA = 330;
export const ESPACAMENTO_MIN_Y = 135;

/**
 * Calcula o layout ótimo com cruzamentos mínimos para todos os nós e arestas.
 * Devolve um Map de id para { x, y }.
 */
export function calcularLayoutHierarquico(nodes, edges) {
  if (!nodes || nodes.length === 0) return new Map();

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const posicoes = new Map();

  // 1. Filtrar arestas funcionais de trabalho (ignora 'produz' que é estrutural de sessão)
  const workEdges = edges.filter((e) => e.tipo !== "produz" && nodeMap.has(e.origem_id) && nodeMap.has(e.destino_id));

  // 2. Mapeamento de Adjacência
  const adjOut = new Map();
  const adjIn = new Map();
  for (const n of nodes) {
    adjOut.set(n.id, []);
    adjIn.set(n.id, []);
  }
  for (const e of workEdges) {
    adjOut.get(e.origem_id).push(e.destino_id);
    adjIn.get(e.destino_id).push(e.origem_id);
  }

  // 3. Atribuição de Ranks / Camadas (X)
  const ranks = atribuirRanksTopologicos(nodes, workEdges, nodeMap);
  const maxRank = Math.max(...ranks.values(), 0);

  // 4. Agrupar nós por camada
  const layers = Array.from({ length: maxRank + 1 }, () => []);
  for (const [id, r] of ranks.entries()) {
    layers[r].push(id);
  }

  // 5. Minimização de Cruzamentos (Sugiyama Barycentric Sweeps + Adjacent Swaps)
  minimizarCruzamentos(layers, maxRank, workEdges, adjIn, adjOut, ranks);

  // 6. Atribuição de Coordenadas Y com Alinhamento Suave e Resolução de Colisões
  atribuirCoordenadasFinais(layers, maxRank, workEdges, adjIn, adjOut, ranks, posicoes);

  return posicoes;
}

/**
 * Atribui ranks topológicos baseados na semântica causal das arestas
 */
function atribuirRanksTopologicos(nodes, workEdges, nodeMap) {
  const ranks = new Map();

  // Inicialização por tipo ontológico
  for (const n of nodes) {
    if (n.tipo === "Projeto" || n.tipo === "Constraint") {
      ranks.set(n.id, 0);
    } else if (n.tipo === "Setor" || n.tipo === "Goal") {
      ranks.set(n.id, 1);
    } else if (n.tipo === "Sessao" || n.tipo === "Question") {
      ranks.set(n.id, 2);
    } else {
      ranks.set(n.id, 3);
    }
  }

  // Relaxação progressiva seguindo a direção causal
  const FORWARD_EDGES = new Set(["decompoe", "justifica", "escopa", "bloqueia", "contradiz", "contem"]);
  const BACKWARD_EDGES = new Set(["depende_de", "deriva_de", "substitui", "ocorreu_em"]);

  for (let iter = 0; iter < 30; iter++) {
    let mudou = false;
    for (const e of workEdges) {
      const u = e.origem_id;
      const v = e.destino_id;
      const t = e.tipo;
      if (!ranks.has(u) || !ranks.has(v)) continue;

      const rU = ranks.get(u);
      const rV = ranks.get(v);

      if (FORWARD_EDGES.has(t)) {
        // v deve estar à direita de u
        if (rV < rU + 1) {
          ranks.set(v, rU + 1);
          mudou = true;
        }
      } else if (BACKWARD_EDGES.has(t)) {
        // u deve estar à direita de v
        if (rU < rV + 1) {
          ranks.set(u, rV + 1);
          mudou = true;
        }
      }
    }
    if (!mudou) break;
  }

  // Notas e alertas automáticos: colocar na coluna do nó referenciado + 1
  for (const n of nodes) {
    if (n.tipo === "Note") {
      for (const [otherId] of nodeMap) {
        if (otherId !== n.id && n.rotulo && n.rotulo.includes(otherId)) {
          const rOther = ranks.get(otherId) || 0;
          if (ranks.get(n.id) < rOther + 1) {
            ranks.set(n.id, rOther + 1);
          }
        }
      }
    }
  }

  return ranks;
}

/**
 * Minimização de Cruzamentos via Varreduras Baricêntricas e Trocas Adjacentes
 */
function minimizarCruzamentos(layers, maxRank, workEdges, adjIn, adjOut, ranks) {
  const edgePairs = workEdges.map((e) => [e.origem_id, e.destino_id]);
  const posY = new Map();

  // Inicializar índices
  for (let i = 0; i <= maxRank; i++) {
    layers[i].forEach((id, idx) => posY.set(id, idx));
  }

  for (let sweep = 0; sweep < 25; sweep++) {
    // 1. Forward sweep (da esquerda para a direita)
    for (let i = 1; i <= maxRank; i++) {
      layers[i].sort((a, b) => {
        const baryA = calcularBaricentro(a, adjIn, adjOut, posY, ranks, i, true);
        const baryB = calcularBaricentro(b, adjIn, adjOut, posY, ranks, i, true);
        return baryA - baryB;
      });
      layers[i].forEach((id, idx) => posY.set(id, idx));
    }

    // 2. Backward sweep (da direita para a esquerda)
    for (let i = maxRank - 1; i >= 0; i--) {
      layers[i].sort((a, b) => {
        const baryA = calcularBaricentro(a, adjIn, adjOut, posY, ranks, i, false);
        const baryB = calcularBaricentro(b, adjIn, adjOut, posY, ranks, i, false);
        return baryA - baryB;
      });
      layers[i].forEach((id, idx) => posY.set(id, idx));
    }

    // 3. Local Adjacent Swap Optimization
    for (let i = 0; i <= maxRank; i++) {
      const layer = layers[i];
      for (let j = 0; j < layer.length - 1; j++) {
        const u = layer[j];
        const v = layer[j + 1];

        let cBefore = 0;
        if (i > 0) cBefore += contarCruzamentos(layers[i - 1], layer, edgePairs);
        if (i < maxRank) cBefore += contarCruzamentos(layer, layers[i + 1], edgePairs);

        // Testar troca
        layer[j] = v;
        layer[j + 1] = u;

        let cAfter = 0;
        if (i > 0) cAfter += contarCruzamentos(layers[i - 1], layer, edgePairs);
        if (i < maxRank) cAfter += contarCruzamentos(layer, layers[i + 1], edgePairs);

        if (cAfter < cBefore) {
          // Troca vantajosa: manter!
          posY.set(v, j);
          posY.set(u, j + 1);
        } else {
          // Reverter troca
          layer[j] = u;
          layer[j + 1] = v;
        }
      }
    }
  }
}

/**
 * Calcula o baricentro dos vizinhos conectados
 */
function calcularBaricentro(nodeId, adjIn, adjOut, posY, ranks, currentRank, isForward) {
  const neighbors = [];
  const inList = adjIn.get(nodeId) || [];
  const outList = adjOut.get(nodeId) || [];

  for (const n of [...inList, ...outList]) {
    if (!posY.has(n) || !ranks.has(n)) continue;
    const r = ranks.get(n);
    if (isForward && r < currentRank) {
      neighbors.push(posY.get(n));
    } else if (!isForward && r > currentRank) {
      neighbors.push(posY.get(n));
    }
  }

  if (neighbors.length === 0) return posY.get(nodeId) || 0;
  return neighbors.reduce((acc, val) => acc + val, 0) / neighbors.length;
}

/**
 * Conta o número de cruzamentos entre duas camadas adjacentes
 */
function contarCruzamentos(layer1, layer2, edgePairs) {
  const pos1 = new Map(layer1.map((id, i) => [id, i]));
  const pos2 = new Map(layer2.map((id, i) => [id, i]));

  const edgesBetween = [];
  for (const [u, v] of edgePairs) {
    if (pos1.has(u) && pos2.has(v)) {
      edgesBetween.push([pos1.get(u), pos2.get(v)]);
    } else if (pos1.has(v) && pos2.has(u)) {
      edgesBetween.push([pos1.get(v), pos2.get(u)]);
    }
  }

  let crossings = 0;
  for (let i = 0; i < edgesBetween.length; i++) {
    for (let j = i + 1; j < edgesBetween.length; j++) {
      const [u1, v1] = edgesBetween[i];
      const [u2, v2] = edgesBetween[j];
      if ((u1 < u2 && v1 > v2) || (u1 > u2 && v1 < v2)) {
        crossings++;
      }
    }
  }
  return crossings;
}

/**
 * Atribui coordenadas { x, y } com alinhamento contínuo por vizinhos e sem sobreposição
 */
function atribuirCoordenadasFinais(layers, maxRank, workEdges, adjIn, adjOut, ranks, posicoes) {
  const rawY = new Map();

  // Primeira passada: distribuir uniformemente
  for (let i = 0; i <= maxRank; i++) {
    const layer = layers[i];
    layer.forEach((id, idx) => {
      rawY.set(id, 50 + idx * ESPACAMENTO_MIN_Y);
    });
  }

  // Segunda passada: alinhar verticalmente com a média dos vizinhos para conexões retas
  for (let iter = 0; iter < 10; iter++) {
    for (let i = 0; i <= maxRank; i++) {
      const layer = layers[i];
      for (const id of layer) {
        const inList = adjIn.get(id) || [];
        const outList = adjOut.get(id) || [];
        const conn = [...inList, ...outList].filter((v) => rawY.has(v) && ranks.get(v) !== i);
        if (conn.length > 0) {
          const avgY = conn.reduce((acc, v) => acc + rawY.get(v), 0) / conn.length;
          // Mover suavemente em direção à média dos vizinhos
          rawY.set(id, rawY.get(id) * 0.4 + avgY * 0.6);
        }
      }

      // Preservar ordem e aplicar espaçamento mínimo anti-colisão na camada
      layer.sort((a, b) => rawY.get(a) - rawY.get(b));
      let curY = 50;
      for (const id of layer) {
        if (rawY.get(id) < curY) {
          rawY.set(id, curY);
        } else {
          curY = rawY.get(id);
        }
        curY += ESPACAMENTO_MIN_Y;
      }
    }
  }

  // Normalização final para { x, y }
  for (let i = 0; i <= maxRank; i++) {
    const layer = layers[i];
    const colX = 50 + i * PASSO_COLUNA;
    for (const id of layer) {
      posicoes.set(id, {
        x: colX,
        y: Math.round(rawY.get(id)),
      });
    }
  }
}
