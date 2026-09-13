/**
 * Geometria da aresta: por onde passa a curva entre dois cartões.
 *
 * Mora aqui, e não dentro do renderer, porque o arranjo automático também
 * precisa dela — para reservar, nas colunas intermediárias, o trecho por onde
 * uma aresta longa vai de fato passar. Se as duas contas divergissem, o arranjo
 * abriria um corredor num lugar e a curva passaria em outro, por cima de um
 * cartão.
 */

// Folga horizontal a partir da qual a curva sai pela lateral do cartão, mesmo
// que o destino esteja muito mais abaixo do que ao lado. Num arranjo em colunas
// é o caso comum: sair por baixo e entrar por cima atravessaria a coluna.
const FOLGA_PARA_SAIR_PELA_LATERAL = 40;
const CURVATURA_MAXIMA_LATERAL = 100;
const CURVATURA_MAXIMA_VERTICAL = 80;

/**
 * Pontos da curva cúbica entre dois retângulos { x, y, largura, altura }.
 * Devolve { x1, y1, c1x, c1y, c2x, c2y, x2, y2 }.
 */
export function tracarCurva(origem, destino) {
  return saiPelaLateral(origem, destino) ? curvaLateral(origem, destino) : curvaVertical(origem, destino);
}

/** O `d` de um <path> SVG para a curva. */
export function caminhoSvg(curva) {
  const { x1, y1, c1x, c1y, c2x, c2y, x2, y2 } = curva;
  return `M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2} ${y2}`;
}

/**
 * A altura da curva lateral na abscissa dada. As alças da curva lateral têm a
 * mesma ordenada das pontas, então y(t) é um smoothstep; basta achar o t cujo
 * x é o pedido — x(t) é monótono, e a bissecção resolve.
 */
export function alturaDaCurvaEm(curva, x) {
  const { x1, y1, c1x, c2x, x2, y2 } = curva;
  let baixo = 0;
  let alto = 1;
  const crescente = x2 >= x1;
  for (let passo = 0; passo < 24; passo++) {
    const t = (baixo + alto) / 2;
    const xt = cubica(x1, c1x, c2x, x2, t);
    if ((xt < x) === crescente) baixo = t;
    else alto = t;
  }
  const t = (baixo + alto) / 2;
  return y1 + (y2 - y1) * (3 * t * t - 2 * t * t * t);
}

function cubica(p0, p1, p2, p3, t) {
  const u = 1 - t;
  return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3;
}

/** Quanto sobra entre os dois cartões em cada eixo; negativo quando se sobrepõem. */
function folgas(a, b) {
  return {
    horizontal: Math.max(b.x - (a.x + a.largura), a.x - (b.x + b.largura)),
    vertical: Math.max(b.y - (a.y + a.altura), a.y - (b.y + b.altura)),
  };
}

function saiPelaLateral(origem, destino) {
  const { horizontal, vertical } = folgas(origem, destino);
  return horizontal >= FOLGA_PARA_SAIR_PELA_LATERAL || horizontal >= vertical;
}

function curvaLateral(origem, destino) {
  const paraDireita = destino.x + destino.largura / 2 >= origem.x + origem.largura / 2;
  const x1 = paraDireita ? origem.x + origem.largura : origem.x;
  const x2 = paraDireita ? destino.x : destino.x + destino.largura;
  const y1 = origem.y + origem.altura / 2;
  const y2 = destino.y + destino.altura / 2;
  const curvatura = Math.min(Math.max(Math.abs(x2 - x1), 20) * 0.45, CURVATURA_MAXIMA_LATERAL);
  const sentido = paraDireita ? 1 : -1;
  return { x1, y1, c1x: x1 + sentido * curvatura, c1y: y1, c2x: x2 - sentido * curvatura, c2y: y2, x2, y2 };
}

function curvaVertical(origem, destino) {
  const paraBaixo = destino.y + destino.altura / 2 >= origem.y + origem.altura / 2;
  const x1 = origem.x + origem.largura / 2;
  const x2 = destino.x + destino.largura / 2;
  const y1 = paraBaixo ? origem.y + origem.altura : origem.y;
  const y2 = paraBaixo ? destino.y : destino.y + destino.altura;
  const curvatura = Math.min(Math.max(Math.abs(y2 - y1), 16) * 0.5, CURVATURA_MAXIMA_VERTICAL);
  const sentido = paraBaixo ? 1 : -1;
  // Um desvio mínimo evita a curva degenerada quando os centros estão alinhados.
  const desvio = Math.abs(x2 - x1) < 0.01 ? 0.2 : 0;
  return { x1, y1, c1x: x1 + desvio, c1y: y1 + sentido * curvatura, c2x: x2 - desvio, c2y: y2 - sentido * curvatura, x2, y2 };
}
