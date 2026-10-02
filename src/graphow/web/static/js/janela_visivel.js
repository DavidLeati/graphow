/**
 * Quais cartões e arestas cabem na janela do canvas, sem tocar o DOM.
 *
 * Num grafo de mil nós só umas dezenas cabem na tela, mas o navegador recalcula
 * estilo, layout e pintura de todos os que estão no DOM a cada pan e a cada
 * zoom. O renderer mantém só o que está perto da janela; a conta de "perto"
 * mora aqui, pura, para ser testada sem navegador.
 *
 * Tudo é em coordenadas do mundo — o plano do canvas antes de pan e zoom.
 */

// Quanto cada lado da janela cresce, como fração do tamanho dela: meia janela.
// Um cartão que acabou de entrar na margem já existe quando o pan o traz à
// vista, em vez de aparecer com atraso na borda.
export const MARGEM_EM_JANELAS = 0.5;

// Quanto a curva de uma aresta pode se afastar do retângulo que une os dois
// cartões: as alças de geometria_aresta.js passam de 100 unidades da ponta.
export const FOLGA_DA_CURVA = 120;

/**
 * O retângulo do mundo que a janela do canvas mostra, dado o pan, o zoom e o
 * tamanho do viewport em pixels. O pan é o deslocamento da superfície em
 * pixels, então o canto superior esquerdo do mundo visível é -pan / zoom.
 */
export function retanguloVisivel({ panX, panY, zoom, larguraDoViewport, alturaDoViewport }) {
  return {
    // 0 - n e nao -n: com pan zero o menos unario daria -0.
    x: 0 - panX / zoom,
    y: 0 - panY / zoom,
    largura: larguraDoViewport / zoom,
    altura: alturaDoViewport / zoom,
  };
}

/** O retângulo crescido de `margemX` para cada lado na horizontal e `margemY` na vertical. */
export function expandirRetangulo(retangulo, margemX, margemY = margemX) {
  return {
    x: retangulo.x - margemX,
    y: retangulo.y - margemY,
    largura: retangulo.largura + 2 * margemX,
    altura: retangulo.altura + 2 * margemY,
  };
}

/** A janela visível crescida da margem padrão: meia janela de cada lado. */
export function janelaComMargem(visivel, fracao = MARGEM_EM_JANELAS) {
  return expandirRetangulo(visivel, visivel.largura * fracao, visivel.altura * fracao);
}

/** Dois retângulos se cruzam? Encostar na borda conta: um cartão rente à janela fica. */
export function retangulosSeCruzam(a, b) {
  return (
    a.x <= b.x + b.largura &&
    b.x <= a.x + a.largura &&
    a.y <= b.y + b.altura &&
    b.y <= a.y + a.altura
  );
}

/**
 * Os ids cujo cartão cruza a janela. `janela` já vem com a margem aplicada.
 * Quem não tem tamanho medido — nunca foi para o DOM — ocupa o `tamanhoPadrao`.
 *
 * É uma varredura linear: para alguns milhares de nós custa menos que manter
 * um índice espacial em dia a cada arrasto.
 */
export function idsNaJanela({ posicoes, tamanhos, janela, tamanhoPadrao }) {
  const ids = new Set();
  for (const [id, posicao] of posicoes) {
    const tamanho = tamanhos?.get(id);
    const retangulo = {
      x: posicao.x,
      y: posicao.y,
      largura: tamanho?.largura || tamanhoPadrao.largura,
      altura: tamanho?.altura || tamanhoPadrao.altura,
    };
    if (retangulosSeCruzam(retangulo, janela)) ids.add(id);
  }
  return ids;
}

/**
 * O retângulo que envolve uma aresta: a união dos dois cartões, crescida da
 * folga da curva. Mais largo que a curva de fato, e é o que se quer — pior
 * caso é desenhar uma aresta a mais, nunca faltar uma que cruza a janela.
 */
export function retanguloDaAresta(origem, destino, folga = FOLGA_DA_CURVA) {
  const esquerda = Math.min(origem.x, destino.x) - folga;
  const topo = Math.min(origem.y, destino.y) - folga;
  const direita = Math.max(origem.x + origem.largura, destino.x + destino.largura) + folga;
  const base = Math.max(origem.y + origem.altura, destino.y + destino.altura) + folga;
  return { x: esquerda, y: topo, largura: direita - esquerda, altura: base - topo };
}
