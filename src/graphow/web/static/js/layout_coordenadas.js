/**
 * Coordenadas de um componente já organizado em camadas.
 *
 * O x vem da camada: colunas lado a lado, com folga para a curva respirar. O y
 * sai de uma relaxação: cada cartão quer ficar na altura média dos vizinhos —
 * o que endireita as arestas —, mas não pode trocar de lugar com quem está
 * acima ou abaixo nem encostar nele. Esse desejo com restrição de ordem é uma
 * regressão isotônica, resolvida exatamente, camada a camada, pelo algoritmo de
 * juntar vizinhos violadores. Diferente de empurrar colisões sempre para baixo,
 * ela desloca o grupo inteiro para onde ele pesa menos, e o arranjo não escorre.
 *
 * Os vértices intermediários de uma aresta longa não seguem os vizinhos:
 * seguem a própria curva que o renderer vai desenhar, e ocupam exatamente a
 * faixa por onde ela atravessa a coluna. Assim o corredor fica onde a linha
 * passa, e a linha não passa por cima de um cartão.
 */

import { alturaDaCurvaEm, tracarCurva } from "./geometria_aresta.js";

const FOLGA_ENTRE_CAMADAS = 130;
const FOLGA_ENTRE_CARTOES = 28;
const FOLGA_DO_CORREDOR = 12;
const ALTURA_INICIAL_DO_CORREDOR = 20;
// Espessura de um corredor quando o vizinho é outro corredor.
const ALTURA_DE_PASSAGEM = 14;
const LARGURA_PADRAO = 220;
const RELAXACOES = 40;
const PESO_DO_CORREDOR = 2;

/**
 * Posiciona o grafo em camadas e devolve um bloco { largura, altura, itens },
 * com itens em coordenadas relativas ao canto do bloco.
 */
export function posicionarComponente(grafo, tamanhoDe) {
  const estado = { grafo, medidas: medirVertices(grafo, tamanhoDe) };
  estado.colunas = calcularColunas(estado);
  estado.corredorDe = mapearCorredores(grafo);
  estado.centro = empilharCentrado(estado);
  for (let passo = 0; passo < RELAXACOES; passo++) relaxar(estado, passo % 2 === 0);
  return extrairBloco(estado);
}

function medirVertices(grafo, tamanhoDe) {
  const largura = new Float64Array(grafo.vertices.length);
  const altura = new Float64Array(grafo.vertices.length);
  grafo.vertices.forEach((vertice, v) => {
    const tamanho = vertice.id === null ? { largura: 0, altura: ALTURA_INICIAL_DO_CORREDOR } : tamanhoDe(vertice.id);
    largura[v] = tamanho.largura;
    altura[v] = tamanho.altura;
  });
  return { largura, altura };
}

function calcularColunas({ grafo, medidas }) {
  const x = [];
  const largura = [];
  let cursor = 0;
  for (const camada of grafo.camadas) {
    const maior = Math.max(0, ...camada.map((v) => medidas.largura[v]));
    x.push(cursor);
    largura.push(maior || LARGURA_PADRAO);
    cursor += largura[largura.length - 1] + FOLGA_ENTRE_CAMADAS;
  }
  return { x, largura };
}

/** Para cada vértice intermediário, a cadeia a que ele pertence. */
function mapearCorredores(grafo) {
  const corredorDe = new Map();
  for (const cadeia of grafo.cadeias) {
    for (const v of cadeia.slice(1, -1)) corredorDe.set(v, cadeia);
  }
  return corredorDe;
}

function empilharCentrado(estado) {
  const centro = new Float64Array(estado.grafo.vertices.length);
  for (const camada of estado.grafo.camadas) {
    let cursor = 0;
    camada.forEach((v, i) => {
      if (i > 0) cursor += folgaEntre(estado, camada[i - 1], v);
      centro[v] = cursor;
    });
    camada.forEach((v) => { centro[v] -= cursor / 2; });
  }
  return centro;
}

/**
 * Distância mínima entre os centros de dois vizinhos na mesma camada.
 *
 * Um corredor ocupa toda a faixa que a curva varre ao atravessar a coluna —
 * mas só contra um cartão. Contra outro corredor ele é uma linha fina: duas
 * curvas que não se cruzam podem dividir a mesma faixa, uma por cima da outra,
 * e reservar faixa inteira para cada uma inflaria a coluna sem motivo.
 */
function folgaEntre({ grafo, medidas }, u, v) {
  const uCorredor = grafo.vertices[u].id === null;
  const vCorredor = grafo.vertices[v].id === null;
  const meia = (w, contraCorredor) => (grafo.vertices[w].id === null && contraCorredor ? ALTURA_DE_PASSAGEM / 2 : medidas.altura[w] / 2);
  const folga = uCorredor || vCorredor ? FOLGA_DO_CORREDOR : FOLGA_ENTRE_CARTOES;
  return meia(u, vCorredor) + meia(v, uCorredor) + folga;
}

function relaxar(estado, descendo) {
  const indices = estado.grafo.camadas.map((_, i) => i);
  if (!descendo) indices.reverse();
  for (const i of indices) {
    const camada = estado.grafo.camadas[i];
    const desejos = camada.map((v) => desejoDe(estado, v, i));
    const folgas = camada.map((v, k) => (k === 0 ? 0 : folgaEntre(estado, camada[k - 1], v)));
    const posicoes = projetarEmOrdem(desejos, folgas);
    camada.forEach((v, k) => { estado.centro[v] = posicoes[k]; });
  }
}

/**
 * Onde o vértice quer ficar e com que força. Um cartão quer a média dos seus
 * vizinhos reais; quem tem mais ligações pesa mais, e cede menos. Um corredor
 * quer a faixa que a curva ocupa na sua coluna — e já ajusta a própria altura.
 */
function desejoDe(estado, v, indiceCamada) {
  const cadeia = estado.corredorDe.get(v);
  if (cadeia) return desejoDoCorredor(estado, { v, cadeia, indiceCamada });
  const vizinhos = estado.grafo.vizinhosReais[v];
  if (vizinhos.length === 0) return { alvo: estado.centro[v], peso: 1 };
  const media = vizinhos.reduce((soma, w) => soma + estado.centro[w], 0) / vizinhos.length;
  return { alvo: media, peso: vizinhos.length };
}

function desejoDoCorredor(estado, { v, cadeia, indiceCamada }) {
  const curva = tracarCurva(retanguloDe(estado, cadeia[0]), retanguloDe(estado, cadeia[cadeia.length - 1]));
  const inicio = estado.colunas.x[indiceCamada];
  const yEntrada = alturaDaCurvaEm(curva, inicio);
  const ySaida = alturaDaCurvaEm(curva, inicio + estado.colunas.largura[indiceCamada]);
  estado.medidas.altura[v] = Math.abs(ySaida - yEntrada) + FOLGA_DO_CORREDOR;
  return { alvo: (yEntrada + ySaida) / 2, peso: PESO_DO_CORREDOR };
}

function retanguloDe({ grafo, medidas, colunas, centro }, v) {
  const altura = medidas.altura[v];
  return { x: colunas.x[grafo.vertices[v].camada], y: centro[v] - altura / 2, largura: medidas.largura[v], altura };
}

/**
 * Regressão isotônica com folga mínima: a posição de cada vértice, em ordem,
 * o mais perto possível do alvo, ponderado pelo peso, sem que dois vizinhos
 * fiquem a menos da folga entre eles. Descontada a folga acumulada, vira a
 * regressão monótona clássica, e juntar blocos violadores a resolve.
 */
function projetarEmOrdem(desejos, folgas) {
  const acumulada = [];
  folgas.forEach((folga, i) => acumulada.push(i === 0 ? 0 : acumulada[i - 1] + folga));
  const blocos = [];
  desejos.forEach(({ alvo, peso }, i) => {
    let bloco = { soma: peso * (alvo - acumulada[i]), peso, tamanho: 1 };
    while (blocos.length && mediaDe(blocos[blocos.length - 1]) > mediaDe(bloco)) bloco = fundir(blocos.pop(), bloco);
    blocos.push(bloco);
  });
  const posicoes = [];
  for (const bloco of blocos) {
    for (let k = 0; k < bloco.tamanho; k++) posicoes.push(mediaDe(bloco) + acumulada[posicoes.length]);
  }
  return posicoes;
}

function mediaDe(bloco) {
  return bloco.soma / bloco.peso;
}

function fundir(a, b) {
  return { soma: a.soma + b.soma, peso: a.peso + b.peso, tamanho: a.tamanho + b.tamanho };
}

/** Recorta o bloco pelo que ocupa espaço — cartões e corredores — e devolve só os cartões. */
function extrairBloco(estado) {
  const { grafo, medidas, colunas, centro } = estado;
  let topo = Infinity;
  let base = -Infinity;
  grafo.vertices.forEach((_, v) => {
    topo = Math.min(topo, centro[v] - medidas.altura[v] / 2);
    base = Math.max(base, centro[v] + medidas.altura[v] / 2);
  });
  const itens = grafo.vertices
    .map((vertice, v) => ({ vertice, v }))
    .filter(({ vertice }) => vertice.id !== null)
    .map(({ vertice, v }) => ({ id: vertice.id, x: colunas.x[vertice.camada], y: centro[v] - medidas.altura[v] / 2 - topo }));
  const ultima = colunas.x.length - 1;
  return { largura: colunas.x[ultima] + colunas.largura[ultima], altura: base - topo, itens };
}
