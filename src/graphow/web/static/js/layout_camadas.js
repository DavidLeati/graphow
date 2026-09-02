/**
 * Posição de nascimento para os nós que chegam ao canvas sem coordenada.
 *
 * O canvas espalhava esses nós com `100 + (n * 50) % 600` — um passo de 50 px
 * entre cartões de 220 px de largura, embrulhando numa caixa de 600×400. Não era
 * um arranjo ruim: era uma pilha. Com mais de doze nós a sobreposição deixava de
 * ser provável e passava a ser aritmética.
 *
 * Aqui eles entram em camadas: um nó fica à direita de tudo que aponta para ele.
 * A regra é a do grafo, não da ontologia — vale para qualquer tipo de nó, e faz
 * a direção da seta significar alguma coisa na leitura.
 */

export const LARGURA_CARTAO = 220;
export const PASSO_COLUNA = 300;
// O cartão mais alto medido no canvas real tem 137 px — um rótulo longo, sem
// truncamento. O passo precisa folgar isso, ou a linha de baixo encosta.
export const PASSO_LINHA = 190;

/**
 * Distribui em camadas os nós indicados, a partir do deslocamento vertical dado.
 * Devolve um Map de id para { x, y }.
 */
export function posicionarEmCamadas(idsSemPosicao, nodes, edges, deslocamentoY = 0) {
  const pendentes = new Set(idsSemPosicao);
  if (pendentes.size === 0) return new Map();
  return distribuir(calcularCamadas(pendentes, edges), nodes, deslocamentoY);
}

/**
 * Índice da camada de cada id: o maior caminho até ele, partindo de quem não tem
 * entrada. Recebe as incidências já montadas, para servir a mais de um critério
 * de aresta — o canvas usa todas, o arranjo hierárquico usa só `depende_de`.
 */
export function calcularCamadasPorEntradas(ids, origensPorDestino) {
  const camada = new Map([...ids].map((id) => [id, 0]));
  // Relaxação com teto: um ciclo nunca convergiria, e o limite o interrompe sem
  // travar o navegador. Um ciclo sai achatado numa camada só, não sai perdido.
  for (let passo = 0; passo < camada.size; passo++) {
    if (!relaxarUmaVez(origensPorDestino, camada)) break;
  }
  return camada;
}

function calcularCamadas(pendentes, edges) {
  return calcularCamadasPorEntradas(pendentes, mapearEntradas(pendentes, edges));
}

/** Uma passada de relaxação. Devolve se alguma camada mudou. */
function relaxarUmaVez(origensPorDestino, camada) {
  let mudou = false;
  for (const [destino, origens] of origensPorDestino) {
    const conhecidas = origens.filter((origem) => camada.has(origem));
    if (!camada.has(destino) || conhecidas.length === 0) continue;
    const maior = Math.max(...conhecidas.map((origem) => camada.get(origem)));
    if (maior + 1 <= camada.get(destino)) continue;
    camada.set(destino, maior + 1);
    mudou = true;
  }
  return mudou;
}

/** Quem aponta para quem, restrito aos nós que ainda esperam posição. */
function mapearEntradas(pendentes, edges) {
  const entradas = new Map();
  for (const aresta of edges.values()) {
    if (!pendentes.has(aresta.origem_id) || !pendentes.has(aresta.destino_id)) continue;
    if (aresta.origem_id === aresta.destino_id) continue;
    if (!entradas.has(aresta.destino_id)) entradas.set(aresta.destino_id, []);
    entradas.get(aresta.destino_id).push(aresta.origem_id);
  }
  return entradas;
}

/** Converte camada e ordem dentro dela em coordenada, com folga maior que o cartão. */
function distribuir(camadas, nodes, deslocamentoY) {
  const posicoes = new Map();
  for (const [indice, ids] of agruparPorCamada(camadas)) {
    ordenarParaLeitura(ids, nodes).forEach((id, linha) => {
      posicoes.set(id, {
        x: indice * PASSO_COLUNA,
        y: deslocamentoY + linha * PASSO_LINHA,
      });
    });
  }
  return posicoes;
}

/** Agrupa os identificadores pela camada a que pertencem. */
function agruparPorCamada(camadas) {
  const porCamada = new Map();
  for (const [id, indice] of camadas) {
    if (!porCamada.has(indice)) porCamada.set(indice, []);
    porCamada.get(indice).push(id);
  }
  return porCamada;
}

/** Ordena uma camada por tipo e depois por id: nós do mesmo tipo ficam vizinhos. */
function ordenarParaLeitura(ids, nodes) {
  return [...ids].sort((a, b) => {
    const tipoA = nodes.get(a)?.tipo ?? "";
    const tipoB = nodes.get(b)?.tipo ?? "";
    return tipoA === tipoB ? a.localeCompare(b) : tipoA.localeCompare(tipoB);
  });
}
